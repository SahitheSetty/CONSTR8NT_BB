from pathlib import Path

import numpy as np
import pytest

from blackbox_engine.mocks import (
    SCENARIOS,
    FlakyMock,
    ReplayMock,
    ScenarioMock,
    StochasticMock,
)
from blackbox_engine.spec_loader import load_spec
from blackbox_engine.symbols import OBSERVATION_SPACE, Observation

SPEC_PATH = Path(__file__).parent.parent / "src" / "blackbox_engine" / "hypotheses.yaml"


@pytest.fixture(scope="module")
def spec():
    return load_spec(SPEC_PATH)


async def test_scenario_mock_returns_scripted_symbol():
    mock = ScenarioMock({"dns_resolution": "nxdomain"}, latency_ms=1.0)

    obs = await mock("dns_resolution", "example.com")

    assert obs.symbol == "nxdomain"
    assert obs.measured is True
    obs.validate()


async def test_scenario_mock_is_unmeasured_for_unscripted_probe():
    mock = ScenarioMock({"dns_resolution": "ok"}, latency_ms=1.0)

    obs = await mock("tcp_443", "example.com")

    assert obs.measured is False
    assert obs.symbol is None
    obs.validate()


async def test_replay_mock_returns_precollected_observation():
    canned = Observation("tcp_443", "open", True, 12.0, {}, None)
    mock = ReplayMock({"tcp_443": canned})

    obs = await mock("tcp_443", "example.com")

    assert obs is canned


async def test_replay_mock_raises_for_missing_probe():
    mock = ReplayMock({"tcp_443": Observation("tcp_443", "open", True, 12.0, {}, None)})

    with pytest.raises(KeyError, match="dns_resolution"):
        await mock("dns_resolution", "example.com")


async def test_stochastic_mock_is_seedable_and_reproducible(spec):
    mock_a = StochasticMock(spec, truth="dns_failure", rng=np.random.default_rng(123))
    mock_b = StochasticMock(spec, truth="dns_failure", rng=np.random.default_rng(123))

    symbols_a = [(await mock_a("dns_resolution", "example.com")).symbol for _ in range(50)]
    symbols_b = [(await mock_b("dns_resolution", "example.com")).symbol for _ in range(50)]

    assert symbols_a == symbols_b


async def test_stochastic_mock_frequencies_match_likelihood_table(spec):
    rng = np.random.default_rng(2024)
    mock = StochasticMock(spec, truth="dns_failure", rng=rng)

    n_draws = 10_000
    counts = {symbol: 0 for symbol in OBSERVATION_SPACE["dns_resolution"]}
    for _ in range(n_draws):
        obs = await mock("dns_resolution", "example.com")
        counts[obs.symbol] += 1

    expected = spec.likelihoods["dns_resolution"].table
    for symbol, count in counts.items():
        empirical = count / n_draws
        expected_probability = expected[symbol]["dns_failure"]
        assert abs(empirical - expected_probability) < 0.02, (
            f"{symbol}: empirical={empirical}, expected={expected_probability}"
        )


async def test_flaky_mock_produces_roughly_the_configured_failure_rate():
    async def always_succeeds(probe_id: str, target: str) -> Observation:
        return Observation(probe_id, "open", True, 1.0, {}, None)

    rng = np.random.default_rng(99)
    mock = FlakyMock(always_succeeds, failure_rate=0.3, rng=rng)

    n_draws = 10_000
    failures = 0
    for _ in range(n_draws):
        obs = await mock("tcp_443", "example.com")
        if not obs.measured:
            failures += 1

    observed_rate = failures / n_draws
    assert abs(observed_rate - 0.3) < 0.02


async def test_flaky_mock_delegates_to_inner_when_not_failing():
    async def always_succeeds(probe_id: str, target: str) -> Observation:
        return Observation(probe_id, "open", True, 1.0, {}, None)

    mock = FlakyMock(always_succeeds, failure_rate=0.0, rng=np.random.default_rng(1))

    obs = await mock("tcp_443", "example.com")

    assert obs.measured is True
    assert obs.symbol == "open"


def test_scenarios_cover_every_hypothesis_and_every_probe(spec):
    assert set(SCENARIOS) == set(spec.hypotheses)
    for hypothesis, mapping in SCENARIOS.items():
        assert set(mapping) == set(OBSERVATION_SPACE), hypothesis
        for probe_id, symbol in mapping.items():
            assert symbol in OBSERVATION_SPACE[probe_id], (hypothesis, probe_id, symbol)


async def test_scenario_mock_replays_a_full_scenario_and_validates():
    scenario = SCENARIOS["server_down"]
    mock = ScenarioMock(scenario, latency_ms=0.1)

    for probe_id in OBSERVATION_SPACE:
        obs = await mock(probe_id, "example.com")
        assert obs.symbol == scenario[probe_id]
        obs.validate()
