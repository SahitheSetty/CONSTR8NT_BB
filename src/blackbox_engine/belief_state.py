"""Posterior over root-cause hypotheses, held and updated in log space.

All belief math happens here in log space with log-sum-exp normalisation,
per the engine's hard invariant against catastrophic underflow when
probabilities get pushed toward the smoothed [0.01, 0.99] extremes.
"""

from __future__ import annotations

import numpy as np


def _log_sum_exp(log_values: np.ndarray) -> float:
    peak = np.max(log_values)
    return float(peak + np.log(np.sum(np.exp(log_values - peak))))


class BeliefState:
    """A normalised log-probability distribution over an ordered hypothesis list."""

    def __init__(self, hypotheses: list[str], priors: list[float] | np.ndarray) -> None:
        if len(hypotheses) != len(priors):
            raise ValueError(
                f"got {len(hypotheses)} hypotheses but {len(priors)} priors; "
                "lengths must match"
            )
        self.hypotheses: list[str] = list(hypotheses)
        log_priors = np.log(np.asarray(priors, dtype=float))
        self._log_probs = log_priors - _log_sum_exp(log_priors)
        self.history: list[np.ndarray] = []

    def probs(self) -> np.ndarray:
        """Current posterior as a linear-space array, in hypothesis order."""
        return np.exp(self._log_probs)

    def update(self, log_likelihood: list[float] | np.ndarray) -> None:
        """Bayesian-update the posterior with per-hypothesis log-likelihoods.

        `log_likelihood[i]` must be log P(observation | hypotheses[i]) for the
        single observation just consumed. Combines additively in log space
        and renormalises via log-sum-exp, then appends a probability
        snapshot to `history`.
        """
        log_likelihood = np.asarray(log_likelihood, dtype=float)
        if log_likelihood.shape != self._log_probs.shape:
            raise ValueError(
                f"log_likelihood has shape {log_likelihood.shape}, expected "
                f"{self._log_probs.shape} ({len(self.hypotheses)} hypotheses)"
            )
        combined = self._log_probs + log_likelihood
        self._log_probs = combined - _log_sum_exp(combined)
        self.history.append(self.probs())

    def entropy(self) -> float:
        """Shannon entropy of the current posterior, in bits."""
        probs = self.probs()
        nonzero = probs[probs > 0]
        return float(-np.sum(nonzero * np.log2(nonzero)))

    def top(self, k: int) -> list[tuple[str, float]]:
        """The k most probable hypotheses as (name, probability), descending."""
        probs = self.probs()
        order = np.argsort(probs)[::-1][:k]
        return [(self.hypotheses[i], float(probs[i])) for i in order]
