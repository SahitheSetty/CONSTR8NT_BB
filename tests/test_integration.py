import json
from pathlib import Path

import pytest

from blackbox_engine.adapter import to_observations
from blackbox_engine.integration import (
    MissingTargetError,
    OnDemandRunnerRequiredError,
    UnknownModeError,
    diagnose_from_upstream,
)
from blackbox_engine.mocks import SCENARIOS, ScenarioMock
from blackbox_engine.spec_loader import Hypothesis, Likelihood, Spec

FIXTURES = Path(__file__).parent / "fixtures"

# The probes adapter.to_observations actually has a mapping for today.
# dns_consistency / external_vantage / mtu_behaviour have no adapter rule
# yet -- selecting one of those in replay mode is exactly the "upstream
# gap surfaces loudly" case this module has to guarantee.
_ADAPTER_COVERED_PROBES = [
    "dns_resolution", "tcp_443", "tcp_80", "tls_handshake", "http_status",
    "packet_loss", "latency_profile", "path_change", "path_reachability",
]


@pytest.fixture
def p1_raw() -> dict:
    return json.loads((FIXTURES / "p1_sample.json").read_text())


@pytest.fixture
def p2_analysis() -> dict:
    return json.loads((FIXTURES / "p2_sample.json").read_text())


def _spec_over(probes: list[str], strong_hypothesis: str = "client_local_issue") -> Spec:
    """A tiny two-hypothesis spec, calibrated so `strong_hypothesis` wins
    once every probe in `probes` comes back matching SCENARIOS[strong_hypothesis].
    """
    hypotheses = [strong_hypothesis, "server_down"]
    hyp_objects = {
        h: Hypothesis(key=h, prior=0.5, label=h, remediation="n/a") for h in hypotheses
    }
    likelihoods = {}
    for probe in probes:
        target_symbol = SCENARIOS[strong_hypothesis][probe]
        other_symbol = SCENARIOS["server_down"][probe]
        symbols = {target_symbol, other_symbol}
        if len(symbols) == 1:
            # both hypotheses produce the same symbol for this probe: no
            # information either way, just split it 50/50 for both.
            table = {target_symbol: {h: 0.5 for h in hypotheses}}
        else:
            table = {
                target_symbol: {strong_hypothesis: 0.9, "server_down": 0.1},
                other_symbol: {strong_hypothesis: 0.1, "server_down": 0.9},
            }
        likelihoods[probe] = Likelihood(probe_id=probe, cost_seconds=1.0, table=table)
    return Spec(hypotheses=hyp_objects, likelihoods=likelihoods)


async def test_replay_mode_runs_end_to_end_and_returns_exporter_shape(p1_raw, p2_analysis):
    spec = _spec_over(_ADAPTER_COVERED_PROBES)

    payload = await diagnose_from_upstream(p1_raw, p2_analysis, mode="replay", spec=spec)

    assert set(payload) == {"diagnosis", "hypotheses", "evidence", "reasoningTrace"}
    assert payload["diagnosis"]["probableCause"] in {"client_local_issue", "server_down"}
    assert isinstance(payload["evidence"], list)


async def test_replay_mode_defaults_to_mode_replay(p1_raw, p2_analysis):
    spec = _spec_over(_ADAPTER_COVERED_PROBES)

    payload = await diagnose_from_upstream(p1_raw, p2_analysis, spec=spec)

    assert "diagnosis" in payload


# Note: there used to be a test here forcing the engine to select
# dns_consistency (no adapter mapping) and asserting ReplayMock's KeyError
# surfaced. adapter.py now maps dns_consistency/external_vantage/
# mtu_behaviour explicitly to an always-unmeasured Observation, so
# to_observations() never omits a probe and ReplayMock never KeyErrors on
# any probe in OBSERVATION_SPACE -- that failure mode no longer exists.


async def test_unknown_mode_raises_named_error(p1_raw, p2_analysis):
    spec = _spec_over(_ADAPTER_COVERED_PROBES)

    with pytest.raises(UnknownModeError, match="unknown mode 'bogus'"):
        await diagnose_from_upstream(p1_raw, p2_analysis, mode="bogus", spec=spec)


async def test_missing_target_raises_named_error(p2_analysis):
    spec = _spec_over(_ADAPTER_COVERED_PROBES)

    with pytest.raises(MissingTargetError):
        await diagnose_from_upstream({"dns": {}}, p2_analysis, spec=spec)


async def test_p1_raw_must_be_a_dict(p2_analysis):
    spec = _spec_over(_ADAPTER_COVERED_PROBES)

    with pytest.raises(TypeError, match="p1_raw must be a dict"):
        await diagnose_from_upstream(None, p2_analysis, spec=spec)


async def test_upstream_shape_error_from_adapter_propagates_unmodified(p2_analysis):
    spec = _spec_over(_ADAPTER_COVERED_PROBES)
    bad_p1_raw = {
        "target": "example.com",
        "tcp": {"443": {"status": "not_a_real_status", "duration_ms": 1.0}},
    }

    with pytest.raises(ValueError, match="not_a_real_status"):
        await diagnose_from_upstream(bad_p1_raw, p2_analysis, spec=spec)


async def test_on_demand_mode_without_runner_raises_named_error(p1_raw, p2_analysis):
    spec = _spec_over(_ADAPTER_COVERED_PROBES)

    with pytest.raises(OnDemandRunnerRequiredError):
        await diagnose_from_upstream(p1_raw, p2_analysis, mode="on-demand", spec=spec)


async def test_on_demand_mode_drives_the_supplied_live_runner(p1_raw, p2_analysis):
    spec = _spec_over(_ADAPTER_COVERED_PROBES)
    live_runner = ScenarioMock(SCENARIOS["client_local_issue"], latency_ms=0.0)

    payload = await diagnose_from_upstream(
        p1_raw, p2_analysis, mode="on-demand", spec=spec, live_probe_runner=live_runner
    )

    assert payload["diagnosis"]["probableCause"] == "client_local_issue"


async def test_replay_mode_matches_manually_built_replay_mock(p1_raw, p2_analysis):
    # Sanity check that diagnose_from_upstream's replay path is exactly
    # adapter.to_observations feeding a ReplayMock, not some parallel path.
    spec = _spec_over(_ADAPTER_COVERED_PROBES)
    expected_observations = to_observations(p1_raw, p2_analysis)

    payload = await diagnose_from_upstream(p1_raw, p2_analysis, mode="replay", spec=spec)

    evidence_probes = {
        entry["probe"] for entry in payload["reasoningTrace"] if entry.get("measured")
    }
    for probe in evidence_probes:
        assert expected_observations[probe].measured
