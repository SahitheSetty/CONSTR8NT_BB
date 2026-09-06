import math
from pathlib import Path

import numpy as np
import pytest

from blackbox_engine.belief_state import BeliefState
from blackbox_engine.spec_loader import Hypothesis, Likelihood, Spec, load_spec
from blackbox_engine.symbols import OBSERVATION_SPACE
from blackbox_engine.test_selector import TestSelector

SPEC_PATH = Path(__file__).parent.parent / "src" / "blackbox_engine" / "hypotheses.yaml"


@pytest.fixture(scope="module")
def real_spec() -> Spec:
    return load_spec(SPEC_PATH)


@pytest.fixture
def real_selector(real_spec) -> TestSelector:
    return TestSelector(real_spec)


def _uniform_belief(hypotheses: list[str]) -> BeliefState:
    return BeliefState(hypotheses, np.full(len(hypotheses), 1.0 / len(hypotheses)))


def _spec_with_table(hypotheses: list[str], probe: str, table: dict[str, dict[str, float]],
                      cost_seconds: float = 1.0) -> Spec:
    hyp_objects = {h: Hypothesis(h, 1.0 / len(hypotheses), h, "n/a") for h in hypotheses}
    return Spec(
        hypotheses=hyp_objects,
        likelihoods={probe: Likelihood(probe, cost_seconds, table)},
    )


def test_eig_is_never_negative_across_1000_random_beliefs():
    rng = np.random.default_rng(0)
    hypotheses = [f"h{i}" for i in range(5)]
    symbols = [f"s{i}" for i in range(4)]

    for _ in range(1000):
        # Random valid conditional distribution: each hypothesis's column
        # over symbols sums to 1.
        columns = rng.dirichlet(np.ones(len(symbols)), size=len(hypotheses))
        table = {
            symbol: {h: float(columns[i, j]) for i, h in enumerate(hypotheses)}
            for j, symbol in enumerate(symbols)
        }
        spec = _spec_with_table(hypotheses, "probe_x", table)
        selector = TestSelector(spec)

        priors = rng.dirichlet(np.ones(len(hypotheses)))
        belief = BeliefState(hypotheses, priors)

        assert selector.eig(belief, "probe_x") >= -1e-9


def test_eig_is_near_zero_when_one_hypothesis_dominates(real_selector, real_spec):
    hypotheses = list(real_spec.hypotheses)
    priors = np.full(len(hypotheses), 0.001 / (len(hypotheses) - 1))
    priors[0] = 0.999
    belief = BeliefState(hypotheses, priors)

    gain = real_selector.eig(belief, "dns_resolution")

    assert 0.0 <= gain < 0.05


def test_eig_is_near_zero_when_likelihood_is_uniform_across_hypotheses():
    hypotheses = ["h0", "h1", "h2"]
    table = {
        "x": {"h0": 0.5, "h1": 0.5, "h2": 0.5},
        "y": {"h0": 0.3, "h1": 0.3, "h2": 0.3},
        "z": {"h0": 0.2, "h1": 0.2, "h2": 0.2},
    }
    spec = _spec_with_table(hypotheses, "probe_x", table)
    selector = TestSelector(spec)
    belief = BeliefState(hypotheses, [0.6, 0.3, 0.1])

    assert selector.eig(belief, "probe_x") < 1e-9


def test_eig_is_one_bit_for_a_perfectly_separating_probe_on_two_equal_hypotheses():
    hypotheses = ["h0", "h1"]
    table = {
        "a": {"h0": 1.0, "h1": 0.0},
        "b": {"h0": 0.0, "h1": 1.0},
    }
    spec = _spec_with_table(hypotheses, "probe_x", table)
    selector = TestSelector(spec)
    belief = _uniform_belief(hypotheses)

    gain = selector.eig(belief, "probe_x")

    assert abs(gain - 1.0) < 1e-9
    assert abs(gain - math.log2(2)) < 1e-9


def test_eligible_excludes_probes_with_unmet_preconditions(real_selector):
    remaining = set(OBSERVATION_SPACE)

    eligible_none_observed = real_selector.eligible(remaining, observed={})
    assert "tls_handshake" not in eligible_none_observed
    assert "http_status" not in eligible_none_observed
    assert "mtu_behaviour" not in eligible_none_observed
    assert "tcp_443" in eligible_none_observed  # no precondition of its own

    eligible_tcp_open = real_selector.eligible(remaining, observed={"tcp_443": "open"})
    assert "tls_handshake" in eligible_tcp_open
    assert "mtu_behaviour" in eligible_tcp_open
    assert "http_status" not in eligible_tcp_open  # still needs tls_handshake == ok

    eligible_tls_ok = real_selector.eligible(
        remaining, observed={"tcp_443": "open", "tls_handshake": "ok"}
    )
    assert "http_status" in eligible_tls_ok


def test_eligible_excludes_when_precondition_probe_observed_with_wrong_symbol(real_selector):
    remaining = {"tls_handshake"}
    eligible = real_selector.eligible(remaining, observed={"tcp_443": "refused"})
    assert eligible == set()


def test_rank_returns_full_ranking_sorted_descending_by_score(real_selector, real_spec):
    hypotheses = list(real_spec.hypotheses)
    belief = _uniform_belief(hypotheses)
    eligible = {"dns_resolution", "tcp_443", "packet_loss"}

    ranking = real_selector.rank(belief, eligible)

    assert len(ranking) == len(eligible)
    assert {row[3] for row in ranking} == eligible
    scores = [row[0] for row in ranking]
    assert scores == sorted(scores, reverse=True)
    for score, gain, cost, probe in ranking:
        assert score == pytest.approx(gain / max(cost, 0.05))


def test_probes_with_unmet_preconditions_never_appear_in_rank_output(real_selector, real_spec):
    hypotheses = list(real_spec.hypotheses)
    belief = _uniform_belief(hypotheses)
    remaining = set(OBSERVATION_SPACE)

    eligible = real_selector.eligible(remaining, observed={})
    ranking = real_selector.rank(belief, eligible)

    ranked_probes = {probe for _, _, _, probe in ranking}
    assert "tls_handshake" not in ranked_probes
    assert "http_status" not in ranked_probes
    assert "mtu_behaviour" not in ranked_probes
