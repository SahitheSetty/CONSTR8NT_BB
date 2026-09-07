"""The production entry point: upstream JSON in, exporter payload out.

This is where Person 3's pieces get wired together for a real caller (the
REST API, or a test harness standing in for it) -- adapter -> probe
runner -> Investigation -> exporter. Real upstream output is expected to
differ from the hand-built fixtures used elsewhere in this repo, so
nothing here catches a shape problem and substitutes a default: every
failure surfaces as one of the named exceptions below, or as whatever
clearly-named exception the adapter/orchestrator/mocks layer already
raises for it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from blackbox_engine.adapter import to_observations
from blackbox_engine.exporter import export_investigation
from blackbox_engine.mocks import ProbeRunner, ReplayMock
from blackbox_engine.orchestrator import Investigation, Verdict
from blackbox_engine.spec_loader import Spec, load_spec

_DEFAULT_SPEC_PATH = Path(__file__).parent / "hypotheses.yaml"
_SUPPORTED_MODES = ("replay", "on-demand")


class IntegrationError(Exception):
    """Base class for integration-layer failures.

    Never caught and papered over internally -- callers see one of these
    (or a subclass) whenever the upstream contract or the call itself is
    broken, instead of a silently substituted default diagnosis.
    """


class UnknownModeError(IntegrationError):
    """`mode` was not one of the values diagnose_from_upstream supports."""


class MissingTargetError(IntegrationError):
    """p1_raw has no usable `target` for the Investigation to run against."""


class OnDemandRunnerRequiredError(IntegrationError):
    """mode="on-demand" was requested without a live_probe_runner to drive it."""


def _extract_target(p1_raw: dict[str, Any]) -> str:
    if not isinstance(p1_raw, dict):
        raise TypeError(f"p1_raw must be a dict, got {type(p1_raw).__name__}")

    target = p1_raw.get("target")
    if not isinstance(target, str) or not target:
        raise MissingTargetError(
            f"p1_raw is missing a non-empty string 'target' field; got {target!r}"
        )
    return target


async def diagnose_from_upstream(
    p1_raw: dict[str, Any],
    p2_analysis: dict[str, Any] | None,
    mode: str = "replay",
    *,
    spec: Spec | None = None,
    live_probe_runner: ProbeRunner | None = None,
    budget_s: float = 30.0,
    threshold: float = 0.85,
) -> dict[str, Any]:
    """Run one full diagnosis from upstream JSON and return the exporter payload.

    `mode="replay"` (default) treats `p1_raw`/`p2_analysis` as one completed
    Person 1 + Person 2 collection round. The adapter converts every probe
    it has a mapping for up front, and the Investigation replays from that
    fixed set via ReplayMock -- if it ever selects a probe the adapter has
    no mapping for, that surfaces immediately as ReplayMock's own KeyError
    naming the missing probe, never a guessed default.

    `mode="on-demand"` drives the Investigation against `live_probe_runner`
    instead, calling it once per probe as the engine selects it, so probes
    are collected only as needed rather than all up front. Person 3 owns
    no live network collector itself, so a runner must be supplied; a call
    with mode="on-demand" and no runner raises OnDemandRunnerRequiredError
    rather than silently falling back to replay mode.

    `spec` defaults to the bundled hypotheses.yaml; pass one explicitly to
    evaluate against a different spec (e.g. in tests).

    Every upstream shape problem -- an unrecognised symbol, a wrong type,
    a missing target -- surfaces as its own clearly-named exception raised
    by the adapter, symbols validation, or this module; nothing here
    catches an upstream error and substitutes a default.
    """
    if mode not in _SUPPORTED_MODES:
        raise UnknownModeError(f"unknown mode {mode!r}; expected one of {_SUPPORTED_MODES}")

    target = _extract_target(p1_raw)
    resolved_spec = spec if spec is not None else load_spec(_DEFAULT_SPEC_PATH)

    if mode == "on-demand":
        if live_probe_runner is None:
            raise OnDemandRunnerRequiredError(
                "mode='on-demand' requires a live_probe_runner; Person 3 has no "
                "live network collector of its own -- pass Person 1's real "
                "per-probe runner, or use mode='replay' with a completed "
                "p1_raw/p2_analysis snapshot"
            )
        probe_runner: ProbeRunner = live_probe_runner
    else:
        observations = to_observations(p1_raw, p2_analysis)
        probe_runner = ReplayMock(observations)

    investigation = Investigation(
        target, resolved_spec, probe_runner, budget_s=budget_s, threshold=threshold
    )

    verdict: Verdict | None = None
    events = []
    async for event in investigation.run():
        events.append(event)
        if isinstance(event, Verdict):
            verdict = event
    assert verdict is not None

    return export_investigation(events, resolved_spec)
