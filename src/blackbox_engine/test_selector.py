"""Chooses which probe to run next by expected information gain per second.

At each step of an investigation, EIG picks the probe whose outcome would
most reduce uncertainty over the hypothesis space, and preconditions are
enforced before that scoring ever happens -- a probe that can't yet be
meaningfully run (e.g. TLS before TCP is known open) must never compete
for the budget.
"""

from __future__ import annotations

import math

from blackbox_engine.belief_state import BeliefState
from blackbox_engine.spec_loader import Spec
from blackbox_engine.symbols import PRECONDITIONS

_MIN_OUTCOME_PROBABILITY = 1e-12
_MIN_COST_SECONDS = 0.05


class TestSelector:
    """Ranks candidate probes by expected-information-gain-per-second."""

    __test__ = False  # not a pytest test class despite the name

    def __init__(self, spec: Spec) -> None:
        self.spec = spec

    def eig(self, belief: BeliefState, probe: str) -> float:
        """Expected information gain (bits) of running `probe` given `belief`.

        For each possible outcome o of the probe: P(o) = sum_H P(o|H)*P(H).
        The posterior under o is P(o|H)*P(H)/P(o), normalised over H.
        EIG = H(belief) - sum_o P(o) * H(posterior_o).
        Outcomes with P(o) < 1e-12 are skipped as numerically negligible.
        """
        table = self.spec.likelihoods[probe].table
        prior = dict(zip(belief.hypotheses, belief.probs(), strict=True))
        prior_entropy = belief.entropy()

        expected_posterior_entropy = 0.0
        for row in table.values():
            outcome_probability = sum(row[h] * prior[h] for h in belief.hypotheses)
            if outcome_probability < _MIN_OUTCOME_PROBABILITY:
                continue

            posterior_entropy = 0.0
            for h in belief.hypotheses:
                posterior_h = (row[h] * prior[h]) / outcome_probability
                if posterior_h > 0.0:
                    posterior_entropy -= posterior_h * math.log2(posterior_h)

            expected_posterior_entropy += outcome_probability * posterior_entropy

        # Mutual information is never negative; clamp away floating-point
        # noise from subtracting two very close entropies.
        return max(prior_entropy - expected_posterior_entropy, 0.0)

    def eligible(self, remaining: set[str], observed: dict[str, str]) -> set[str]:
        """Probes in `remaining` whose PRECONDITIONS are satisfied by `observed`.

        `observed` maps probe_id -> the symbol already measured for it. A
        probe with no precondition is always eligible. A probe whose
        prerequisite hasn't been observed yet, or was observed with a
        symbol outside the required set, is excluded.
        """
        result = set()
        for probe in remaining:
            precondition = PRECONDITIONS.get(probe)
            if precondition is None:
                result.add(probe)
                continue
            prerequisite_probe, satisfying_symbols = precondition
            if observed.get(prerequisite_probe) in satisfying_symbols:
                result.add(probe)
        return result

    def rank(
        self, belief: BeliefState, eligible: set[str]
    ) -> list[tuple[float, float, float, str]]:
        """Score every probe in `eligible`, sorted by score descending.

        score = gain / max(cost_seconds, 0.05). Returns the full ranking,
        not just the winner, so a runner-up can be surfaced alongside the
        chosen probe. Callers must pass an already precondition-filtered
        set (see eligible()) -- rank() does not re-check preconditions.
        """
        scored = []
        for probe in eligible:
            gain = self.eig(belief, probe)
            cost = self.spec.likelihoods[probe].cost_seconds
            score = gain / max(cost, _MIN_COST_SECONDS)
            scored.append((score, gain, cost, probe))
        scored.sort(key=lambda row: row[0], reverse=True)
        return scored
