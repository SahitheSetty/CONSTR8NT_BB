from pathlib import Path

import numpy as np
import pytest

from blackbox_engine.mocks import SCENARIOS, FlakyMock, ReplayMock, ScenarioMock
from blackbox_engine.orchestrator import (
    BeliefUpdated,
    Investigation,
    ProbeSelected,
    ProbeUnmeasured,
    Verdict,
)
from blackbox_engine.spec_loader import Hypothesis, Likelihood, Spec, load_spec
from blackbox_engine.symbols import OBSERVATION_SPACE

SPEC_PATH = Path(__file__).parent.parent / "src" / "blackbox_engine" / "hypotheses.yaml"

# The engine's hand-filled spec currently ships with placeholder uniform
# likelihoods (see hypotheses.yaml), which by design carry zero information
# gain. That makes it unsuitable for testing whether the orchestrator can
# actually *diagnose* anything. These tests instead build a synthetic spec
# that reuses SCENARIOS' hand-written fingerprints as a strong (but still
# smoothed, still valid) signal, so diagnostic-accuracy tests stay correct
# regardless of what's currently filled into hypotheses.yaml.
_SIGNAL_STRENGTH = 0.9

# Realistic per-probe costs (cheap network-layer checks, expensive external
# vantage calls), matching the intent behind hypotheses.yaml's own costs.
# This matters for more than pacing: several hypotheses in SCENARIOS are
# only distinguishable behind a PRECONDITIONS chain (tcp_443 -> tls_handshake
# -> http_status), and cheap network-layer/tcp/tls probes vs. expensive
# path/vantage probes is exactly what lets greedy EIG explore that chain
# *before* redundant "everything looks healthy" evidence from the pricier
# probes erodes tcp_443's own marginal information gain to near zero --
# the "correlated evidence" trap the handbook calls out.
_TEST_PROBE_COSTS: dict[str, float] = {
    "dns_resolution": 0.8,
    "dns_consistency": 1.5,
    "tcp_443": 0.5,
    "tcp_80": 0.5,
    "tls_handshake": 1.0,
    "http_status": 1.5,
    "latency_profile": 3.0,
    "packet_loss": 3.0,
    "path_reachability": 3.0,
    "path_change": 3.0,
    "external_vantage": 6.0,
    "mtu_behaviour": 4.0,
}


def _calibrated_table(probe: str, hypotheses: list[str]) -> dict[str, dict[str, float]]:
    symbols = OBSERVATION_SPACE[probe]
    table = {symbol: {} for symbol in symbols}
    for hypothesis in hypotheses:
        target_symbol = SCENARIOS[hypothesis][probe]
        spread = (1.0 - _SIGNAL_STRENGTH) / (len(symbols) - 1)
        for symbol in symbols:
            table[symbol][hypothesis] = _SIGNAL_STRENGTH if symbol == target_symbol else spread
    return table


def _build_calibrated_spec() -> Spec:
    hypotheses = list(SCENARIOS)
    hyp_objects = {
        h: Hypothesis(key=h, prior=1.0 / len(hypotheses), label=h, remediation="n/a")
        for h in hypotheses
    }
    likelihoods = {
        probe: Likelihood(
            probe_id=probe,
            cost_seconds=_TEST_PROBE_COSTS[probe],
            table=_calibrated_table(probe, hypotheses),
        )
        for probe in OBSERVATION_SPACE
    }
    return Spec(hypotheses=hyp_objects, likelihoods=likelihoods)


def _build_ambiguous_spec() -> Spec:
    """A spec where every probe is uniform across hypotheses -- zero EIG anywhere."""
    hypotheses = list(SCENARIOS)
    hyp_objects = {
        h: Hypothesis(key=h, prior=1.0 / len(hypotheses), label=h, remediation="n/a")
        for h in hypotheses
    }
    likelihoods = {}
    for probe, symbols in OBSERVATION_SPACE.items():
        p = 1.0 / len(symbols)
        likelihoods[probe] = Likelihood(
            probe_id=probe, cost_seconds=1.0, table={s: dict.fromkeys(hypotheses, p) for s in symbols}
        )
    return Spec(hypotheses=hyp_objects, likelihoods=likelihoods)


def _spec_with_table(
    hypotheses: list[str], probe: str, table: dict[str, dict[str, float]], cost_seconds: float = 1.0
) -> Spec:
    hyp_objects = {
        h: Hypothesis(key=h, prior=1.0 / len(hypotheses), label=h, remediation="n/a")
        for h in hypotheses
    }
    return Spec(hypotheses=hyp_objects, likelihoods={probe: Likelihood(probe, cost_seconds, table)})


async def _run_to_verdict(investigation: Investigation) -> tuple[Verdict, list]:
    events = [event async for event in investigation.run()]
    verdict = events[-1]
    assert isinstance(verdict, Verdict)
    return verdict, events


@pytest.fixture(scope="module")
def calibrated_spec() -> Spec:
    return _build_calibrated_spec()


@pytest.fixture(scope="module")
def real_spec() -> Spec:
    return load_spec(SPEC_PATH)


@pytest.mark.parametrize("true_hypothesis", list(SCENARIOS))
async def test_every_scenario_is_diagnosed_correctly(calibrated_spec, true_hypothesis):
    scenario = SCENARIOS[true_hypothesis]
    mock = ScenarioMock(scenario, latency_ms=0.0)
    investigation = Investigation("example.com", calibrated_spec, mock, budget_s=60.0, threshold=0.85)

    verdict, _ = await _run_to_verdict(investigation)

    assert verdict.top_hypothesis == true_hypothesis
    assert verdict.confidence >= 0.85
    assert verdict.stop_reason == "confident"


async def test_beliefs_are_unchanged_across_an_unmeasured_probe(calibrated_spec):
    inner = ScenarioMock(SCENARIOS["server_down"], latency_ms=0.0)
    flaky = FlakyMock(inner, failure_rate=1.0, rng=np.random.default_rng(0))
    investigation = Investigation("example.com", calibrated_spec, flaky, budget_s=60.0, threshold=0.85)

    before = investigation.belief.probs().copy()

    saw_unmeasured = False
    async for event in investigation.run():
        if isinstance(event, ProbeUnmeasured):
            saw_unmeasured = True
            after = investigation.belief.probs()
            assert np.array_equal(before, after)
            assert investigation.elapsed_s == 0.0
            break

    assert saw_unmeasured


async def test_flaky_mock_that_always_fails_never_updates_beliefs_for_whole_run(calibrated_spec):
    inner = ScenarioMock(SCENARIOS["server_down"], latency_ms=0.0)
    flaky = FlakyMock(inner, failure_rate=1.0, rng=np.random.default_rng(0))
    investigation = Investigation("example.com", calibrated_spec, flaky, budget_s=60.0, threshold=0.85)

    before = investigation.belief.probs().copy()
    verdict, events = await _run_to_verdict(investigation)

    assert not any(isinstance(e, BeliefUpdated) for e in events)
    assert np.array_equal(before, investigation.belief.probs())
    assert investigation.elapsed_s == 0.0
    assert verdict.stop_reason == "no_eligible_tests"


async def test_ambiguous_scenario_terminates_inconclusive_not_falsely_confident():
    ambiguous_spec = _build_ambiguous_spec()
    mock = ScenarioMock(SCENARIOS["dns_failure"], latency_ms=0.0)
    investigation = Investigation("example.com", ambiguous_spec, mock, budget_s=60.0, threshold=0.85)

    verdict, _ = await _run_to_verdict(investigation)

    assert verdict.stop_reason == "no_informative_tests"
    assert verdict.confidence < 0.5


async def test_replay_mock_reproduces_the_same_verdict_as_scenario_mock(calibrated_spec):
    true_hypothesis = "tls_failure"
    scenario = SCENARIOS[true_hypothesis]
    scenario_mock = ScenarioMock(scenario, latency_ms=0.0)

    precollected = {
        probe_id: await scenario_mock(probe_id, "example.com") for probe_id in OBSERVATION_SPACE
    }

    investigation_a = Investigation(
        "example.com", calibrated_spec, ScenarioMock(scenario, latency_ms=0.0), budget_s=60.0, threshold=0.85
    )
    verdict_a, _ = await _run_to_verdict(investigation_a)

    investigation_b = Investigation(
        "example.com", calibrated_spec, ReplayMock(precollected), budget_s=60.0, threshold=0.85
    )
    verdict_b, _ = await _run_to_verdict(investigation_b)

    assert verdict_a.top_hypothesis == verdict_b.top_hypothesis
    assert verdict_a.confidence == pytest.approx(verdict_b.confidence)
    assert verdict_a.stop_reason == verdict_b.stop_reason
    assert [e.probe for e in verdict_a.evidence] == [e.probe for e in verdict_b.evidence]


async def test_single_probe_investigation_emits_expected_event_shapes():
    # tcp_443 is a real probe with no precondition of its own, so it stays
    # freely eligible; its table here only needs the two symbols this test
    # actually exercises.
    hypotheses = ["h0", "h1"]
    table = {
        "open": {"h0": 0.9, "h1": 0.1},
        "refused": {"h0": 0.1, "h1": 0.9},
    }
    spec = _spec_with_table(hypotheses, "tcp_443", table, cost_seconds=1.0)
    mock = ScenarioMock({"tcp_443": "open"}, latency_ms=0.0)
    investigation = Investigation("example.com", spec, mock, budget_s=10.0, threshold=0.99)

    events = [event async for event in investigation.run()]

    selected = next(e for e in events if isinstance(e, ProbeSelected))
    assert selected.probe == "tcp_443"
    assert selected.chose_over == []
    assert selected.type == "probe_selected"

    updated = next(e for e in events if isinstance(e, BeliefUpdated))
    assert updated.probe == "tcp_443"
    assert updated.symbol == "open"
    assert updated.before["h0"] == pytest.approx(0.5)
    assert updated.after["h0"] > updated.before["h0"]
    assert updated.entropy_after < updated.entropy_before
    assert updated.type == "belief_updated"

    verdict = events[-1]
    assert isinstance(verdict, Verdict)
    assert verdict.stop_reason == "no_eligible_tests"  # only one probe existed, now consumed
    assert verdict.type == "verdict"
