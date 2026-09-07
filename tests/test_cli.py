import io
import json
from pathlib import Path

import pytest
from rich.console import Console

from blackbox_engine.cli import (
    _build_probe_runner,
    _format_chose_over,
    _main_async,
    _parse_args,
    _resolve_target,
    _run_investigation,
)
from blackbox_engine.mocks import SCENARIOS, ReplayMock, ScenarioMock
from blackbox_engine.orchestrator import Alternative, Investigation, Verdict
from blackbox_engine.spec_loader import Hypothesis, Likelihood, Spec


def _two_hypothesis_spec() -> Spec:
    hypotheses = ["h0", "h1"]
    table = {
        "open": {"h0": 0.9, "h1": 0.1},
        "refused": {"h0": 0.1, "h1": 0.9},
    }
    return Spec(
        hypotheses={
            h: Hypothesis(h, 0.5, h, "n/a") for h in hypotheses
        },
        likelihoods={
            "tcp_443": Likelihood("tcp_443", cost_seconds=0.5, table=table),
            "tcp_80": Likelihood("tcp_80", cost_seconds=2.0, table=table),
        },
    )


def test_parse_args_requires_exactly_one_source():
    with pytest.raises(SystemExit):
        _parse_args(["example.com"])
    with pytest.raises(SystemExit):
        _parse_args(["example.com", "--scenario", "dns_failure", "--replay", "x.json"])


def test_parse_args_accepts_scenario():
    args = _parse_args(["example.com", "--scenario", "dns_failure"])
    assert args.target == "example.com"
    assert args.scenario == "dns_failure"
    assert args.replay is None
    assert args.budget == 30.0
    assert args.threshold == 0.85
    assert args.slow is False


def test_parse_args_accepts_slow_flag():
    args = _parse_args(["example.com", "--scenario", "dns_failure", "--slow"])
    assert args.slow is True


def test_parse_args_target_is_optional():
    args = _parse_args(["--scenario", "dns_failure"])
    assert args.target is None


def test_resolve_target_prefers_explicit_target():
    args = _parse_args(["acme.example.com", "--scenario", "routing_blackhole"])
    assert _resolve_target(args) == "acme.example.com"


def test_resolve_target_defaults_to_scenario_name_when_omitted():
    args = _parse_args(["--scenario", "routing_blackhole"])
    assert _resolve_target(args) == "demo-routing_blackhole"


def test_resolve_target_defaults_to_replay_files_own_target_when_omitted(tmp_path):
    replay_file = tmp_path / "replay.json"
    replay_file.write_text(json.dumps({"p1_raw": {"target": "example.com"}}))

    args = _parse_args(["--replay", str(replay_file)])

    assert _resolve_target(args) == "example.com"


def test_resolve_target_falls_back_when_replay_file_has_no_target(tmp_path):
    replay_file = tmp_path / "replay.json"
    replay_file.write_text(json.dumps({"p1_raw": {}}))

    args = _parse_args(["--replay", str(replay_file)])

    assert _resolve_target(args) == "unknown-target"


def test_build_probe_runner_scenario_returns_scenario_mock():
    args = _parse_args(["example.com", "--scenario", "server_down"])
    runner = _build_probe_runner(args)
    assert isinstance(runner, ScenarioMock)
    assert runner.scenario == SCENARIOS["server_down"]


def test_build_probe_runner_unknown_scenario_raises_and_lists_available():
    args = _parse_args(["example.com", "--scenario", "not_a_real_scenario"])
    with pytest.raises(SystemExit, match="not_a_real_scenario"):
        _build_probe_runner(args)


def test_build_probe_runner_replay_builds_observations_from_p1_p2_json(tmp_path):
    fixtures = Path(__file__).parent / "fixtures"
    p1 = json.loads((fixtures / "p1_sample.json").read_text())
    p2 = json.loads((fixtures / "p2_sample.json").read_text())
    replay_file = tmp_path / "replay.json"
    replay_file.write_text(json.dumps({"p1_raw": p1, "p2_analysis": p2}))

    args = _parse_args(["example.com", "--replay", str(replay_file)])
    runner = _build_probe_runner(args)

    assert isinstance(runner, ReplayMock)
    assert "dns_resolution" in runner.observations
    assert runner.observations["dns_resolution"].symbol == "ok"


def test_format_chose_over_computes_cost_ratio():
    spec = _two_hypothesis_spec()
    alternatives = [Alternative(probe="tcp_80", expected_bits=0.5)]

    text = _format_chose_over(spec, "tcp_443", alternatives)

    assert "tcp_80" in text
    assert "0.500 bits" in text
    assert "4.0x cost" in text  # tcp_80 costs 2.0s vs tcp_443's 0.5s


def test_format_chose_over_with_no_alternatives():
    spec = _two_hypothesis_spec()
    assert _format_chose_over(spec, "tcp_443", []) == "(only eligible probe)"


async def test_run_investigation_renders_dashboard_and_returns_verdict():
    spec = _two_hypothesis_spec()
    mock = ScenarioMock({"tcp_443": "open"}, latency_ms=0.0)
    investigation = Investigation("example.com", spec, mock, budget_s=10.0, threshold=0.99)

    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)

    verdict = await _run_investigation(investigation, spec, console, slow=False)

    assert isinstance(verdict, Verdict)
    assert verdict.top_hypothesis == "h0"
    output = buffer.getvalue()
    assert "belief distribution" in output
    assert "investigation steps" in output
    assert "tcp_443" in output


async def test_main_async_runs_end_to_end_with_bundled_spec(capsys):
    exit_code = await _main_async(["example.com", "--scenario", "dns_failure"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "verdict" in captured.out
    assert "stop reason" in captured.out
