import math

import numpy as np
import pytest

from blackbox_engine.belief_state import BeliefState


def _uniform_belief(n: int) -> BeliefState:
    hypotheses = [f"h{i}" for i in range(n)]
    priors = np.full(n, 1.0 / n)
    return BeliefState(hypotheses, priors)


def test_uniform_likelihood_leaves_probabilities_unchanged():
    hypotheses = ["h0", "h1", "h2", "h3", "h4"]
    priors = [0.1, 0.2, 0.3, 0.15, 0.25]
    belief = BeliefState(hypotheses, priors)
    before = belief.probs().copy()

    belief.update(np.log(np.full(5, 0.4)))

    assert np.allclose(before, belief.probs(), atol=1e-9)


def test_strongly_peaked_likelihood_makes_correct_hypothesis_dominate():
    belief = _uniform_belief(12)
    log_likelihood = np.full(12, np.log(0.01))
    log_likelihood[3] = np.log(0.99)

    belief.update(log_likelihood)
    probs = belief.probs()

    assert np.argmax(probs) == 3
    assert probs[3] > 0.5


def test_probabilities_sum_to_one_after_100_random_updates():
    rng = np.random.default_rng(42)
    belief = _uniform_belief(12)

    for _ in range(100):
        raw = rng.uniform(0.01, 0.99, size=12)
        belief.update(np.log(raw))

    assert abs(belief.probs().sum() - 1.0) < 1e-9


def test_entropy_of_uniform_12_hypothesis_distribution_is_log2_12_bits():
    belief = _uniform_belief(12)

    assert abs(belief.entropy() - math.log2(12)) < 1e-9
    assert round(belief.entropy(), 3) == 3.585


def test_no_nan_or_inf_after_1000_extreme_updates():
    rng = np.random.default_rng(7)
    belief = _uniform_belief(12)

    for _ in range(1000):
        target = rng.integers(0, 12)
        raw = np.full(12, 0.01)
        raw[target] = 0.99
        belief.update(np.log(raw))

    probs = belief.probs()
    assert np.all(np.isfinite(probs))
    assert abs(probs.sum() - 1.0) < 1e-6
    assert len(belief.history) == 1000


def test_top_returns_k_highest_probability_hypotheses_descending():
    belief = _uniform_belief(5)
    log_likelihood = np.log([0.01, 0.9, 0.01, 0.05, 0.03])

    belief.update(log_likelihood)
    top2 = belief.top(2)

    assert [name for name, _ in top2] == ["h1", "h3"]
    assert top2[0][1] > top2[1][1]


def test_history_records_one_snapshot_per_update():
    belief = _uniform_belief(4)
    assert belief.history == []

    belief.update(np.log([0.5, 0.2, 0.2, 0.1]))
    belief.update(np.log([0.1, 0.6, 0.2, 0.1]))

    assert len(belief.history) == 2
    assert np.allclose(belief.history[-1], belief.probs())


def test_update_rejects_mismatched_length():
    belief = _uniform_belief(3)
    with pytest.raises(ValueError, match="3"):
        belief.update(np.log([0.5, 0.5]))
