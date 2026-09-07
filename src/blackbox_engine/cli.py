"""Rich-rendered terminal UI driving an Investigation live.

This is the visible demo artifact and the backup plan if the React
frontend or venue wifi dies. It only ever renders events the orchestrator
already produced -- no diagnostic decisions happen here.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from blackbox_engine.adapter import to_observations
from blackbox_engine.mocks import SCENARIOS, ReplayMock, ScenarioMock
from blackbox_engine.orchestrator import (
    BeliefUpdated,
    Investigation,
    ProbeSelected,
    ProbeUnmeasured,
    Verdict,
)
from blackbox_engine.spec_loader import Spec, load_spec

_DEFAULT_SPEC_PATH = Path(__file__).parent / "hypotheses.yaml"
_DEFAULT_REPLAY_TARGET = "unknown-target"
_BAR_WIDTH = 30
_SLOW_DELAY_S = 1.5


def _belief_bars(belief_probs: dict[str, float]) -> Table:
    table = Table.grid(padding=(0, 1))
    table.add_column("hypothesis", width=22, no_wrap=True)
    table.add_column("bar")
    table.add_column("prob", justify="right", width=7)

    for name, prob in sorted(belief_probs.items(), key=lambda kv: kv[1], reverse=True):
        # ASCII only: some terminals (notably Windows' legacy console) can't
        # encode Unicode block characters and would crash mid-render.
        filled = round(prob * _BAR_WIDTH)
        bar = Text("#" * filled + "." * (_BAR_WIDTH - filled), style="cyan")
        table.add_row(name, bar, f"{prob:.1%}")

    return table


def _format_chose_over(spec: Spec, chosen_probe: str, alternatives: list) -> str:
    if not alternatives:
        return "(only eligible probe)"
    chosen_cost = spec.likelihoods[chosen_probe].cost_seconds
    parts = []
    for alt in alternatives:
        alt_cost = spec.likelihoods[alt.probe].cost_seconds
        ratio = alt_cost / max(chosen_cost, 0.05)
        parts.append(f"{alt.probe} ({alt.expected_bits:.3f} bits, {ratio:.1f}x cost)")
    return "; ".join(parts)


def _step_history_table(steps: list[dict]) -> Table:
    table = Table(title="investigation steps", expand=True)
    table.add_column("#", justify="right", width=3)
    table.add_column("probe selected")
    table.add_column("expected bits", justify="right")
    table.add_column("chosen over (cost ratio)")
    table.add_column("result")

    for i, step in enumerate(steps, start=1):
        table.add_row(
            str(i),
            step["probe"],
            f"{step['expected_bits']:.3f}",
            step["chose_over_text"],
            step["result_text"],
        )
    return table


def _dashboard(
    target: str,
    belief_probs: dict[str, float],
    entropy_bits: float,
    elapsed_s: float,
    budget_s: float,
    steps: list[dict],
) -> Group:
    header = Panel(
        Text.from_markup(
            f"[bold]target:[/bold] {target}   "
            f"[bold]elapsed:[/bold] {elapsed_s:.1f}s / {budget_s:.1f}s   "
            f"[bold]entropy:[/bold] [bold yellow]{entropy_bits:.3f} bits[/bold yellow]"
        ),
        border_style="white",
    )
    belief_panel = Panel(_belief_bars(belief_probs), title="belief distribution", border_style="cyan")
    return Group(header, belief_panel, _step_history_table(steps))


def _verdict_panel(verdict: Verdict) -> Panel:
    runners_up = "\n".join(f"  {name}: {prob:.1%}" for name, prob in verdict.runners_up)
    body = Text.from_markup(
        f"[bold]top hypothesis:[/bold] {verdict.top_hypothesis}\n"
        f"[bold]confidence:[/bold] {verdict.confidence:.1%}\n"
        f"[bold]stop reason:[/bold] {verdict.stop_reason}\n\n"
        f"[bold]runners-up:[/bold]\n{runners_up or '  (none)'}"
    )
    border_style = "green" if verdict.stop_reason == "confident" else "yellow"
    return Panel(body, title="verdict", border_style=border_style)


async def _run_investigation(
    investigation: Investigation, spec: Spec, console: Console, slow: bool
) -> Verdict:
    steps: list[dict] = []
    pending_step: dict | None = None
    verdict: Verdict | None = None

    with Live(console=console, refresh_per_second=8) as live:
        async for event in investigation.run():
            if isinstance(event, ProbeSelected):
                pending_step = {
                    "probe": event.probe,
                    "expected_bits": event.expected_bits,
                    "chose_over_text": _format_chose_over(spec, event.probe, event.chose_over),
                    "result_text": "...",
                }
                steps.append(pending_step)
            elif isinstance(event, ProbeUnmeasured):
                assert pending_step is not None
                pending_step["result_text"] = f"[yellow]unmeasured[/yellow] ({event.note or 'no data'})"
            elif isinstance(event, BeliefUpdated):
                assert pending_step is not None
                pending_step["result_text"] = f"[green]{event.symbol}[/green]"
            elif isinstance(event, Verdict):
                verdict = event

            live.update(
                _dashboard(
                    investigation.target,
                    dict(
                        zip(investigation.belief.hypotheses, investigation.belief.probs(), strict=True)
                    ),
                    investigation.belief.entropy(),
                    investigation.elapsed_s,
                    investigation.budget_s,
                    steps,
                )
            )

            if slow:
                await asyncio.sleep(_SLOW_DELAY_S)

    assert verdict is not None
    return verdict


def _build_probe_runner(args: argparse.Namespace):
    if args.scenario is not None:
        if args.scenario not in SCENARIOS:
            raise SystemExit(
                f"unknown scenario {args.scenario!r}; available: {sorted(SCENARIOS)}"
            )
        return ScenarioMock(SCENARIOS[args.scenario], latency_ms=0.0)

    raw = json.loads(Path(args.replay).read_text())
    observations = to_observations(raw["p1_raw"], raw.get("p2_analysis"))
    return ReplayMock(observations)


def _resolve_target(args: argparse.Namespace) -> str:
    """Fill in a sensible target when the positional arg was omitted.

    --scenario mode never looks target up (ScenarioMock ignores it -- see
    _build_probe_runner), so it's only ever used for display; default to a
    label naming the scenario. --replay mode has a real target sitting in
    the replay file's own p1_raw, so prefer that over a generic fallback.
    """
    if args.target:
        return args.target
    if args.scenario is not None:
        return f"demo-{args.scenario}"

    raw = json.loads(Path(args.replay).read_text())
    target = raw.get("p1_raw", {}).get("target")
    return target if isinstance(target, str) and target else _DEFAULT_REPLAY_TARGET


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="blackbox",
        description="Run a BLACK BOX diagnosis investigation with a live rich terminal UI.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="the domain/host being investigated; optional -- defaults to the scenario "
        "name in --scenario mode, or the replay file's own p1_raw.target in --replay mode",
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--scenario", metavar="NAME", help=f"replay a scripted scenario; one of {sorted(SCENARIOS)}"
    )
    source.add_argument(
        "--replay", metavar="PATH", help="run against a saved Person 1 + Person 2 JSON output"
    )

    parser.add_argument(
        "--spec", default=str(_DEFAULT_SPEC_PATH), help="path to hypotheses.yaml (default: bundled spec)"
    )
    parser.add_argument("--budget", type=float, default=30.0, help="time budget in seconds (default: 30.0)")
    parser.add_argument(
        "--threshold", type=float, default=0.85, help="confidence threshold to stop at (default: 0.85)"
    )
    parser.add_argument(
        "--slow",
        action="store_true",
        help="add a delay between steps so the animation is watchable during a demo",
    )
    return parser.parse_args(argv)


async def _main_async(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    console = Console()

    spec = load_spec(args.spec)
    probe_runner = _build_probe_runner(args)
    target = _resolve_target(args)
    investigation = Investigation(
        target, spec, probe_runner, budget_s=args.budget, threshold=args.threshold
    )

    verdict = await _run_investigation(investigation, spec, console, args.slow)

    console.print(_verdict_panel(verdict))
    return 0


def main(argv: list[str] | None = None) -> int:
    # A real failure here (bad --spec/--replay path, malformed JSON/YAML, an
    # upstream shape the adapter can't answer) must never dump a raw
    # traceback mid-demo -- cli.py is the explicit backup plan if the React
    # frontend or venue wifi dies, so it has to fail *legibly* in front of
    # an audience. SystemExit/KeyboardInterrupt aren't Exception subclasses,
    # so argparse's own usage errors and Ctrl-C still behave normally.
    try:
        return asyncio.run(_main_async(argv))
    except Exception as exc:  # noqa: BLE001 -- outermost boundary: re-displayed below, not swallowed
        Console(stderr=True).print(
            Panel(
                f"[bold red]{type(exc).__name__}:[/bold red] {exc}",
                title="investigation failed",
                border_style="red",
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
