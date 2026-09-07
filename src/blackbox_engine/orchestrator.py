"""The select -> consume -> update -> stop loop that drives one investigation.

Unmeasured observations are the load-bearing invariant here: they must
never update beliefs and must never charge the time budget, or a flaky
upstream probe would silently bias the posterior toward "no evidence"
being treated as "confirmed normal".
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from blackbox_engine.belief_state import BeliefState
from blackbox_engine.mocks import ProbeRunner
from blackbox_engine.spec_loader import Spec
from blackbox_engine.test_selector import TestSelector

_TOP_ALTERNATIVES = 3
_MIN_INFORMATIVE_GAIN_BITS = 0.01


@dataclass(frozen=True)
class Alternative:
    """A probe that was ranked but not chosen at a given step."""

    probe: str
    expected_bits: float


@dataclass(frozen=True)
class ProbeSelected:
    """Emitted before a probe is run: what was chosen and what lost out."""

    probe: str
    expected_bits: float
    chose_over: list[Alternative]
    type: str = field(default="probe_selected", init=False)


@dataclass(frozen=True)
class ProbeUnmeasured:
    """Emitted when a probe came back with measured=False."""

    probe: str
    note: str | None
    type: str = field(default="probe_unmeasured", init=False)


@dataclass(frozen=True)
class BeliefUpdated:
    """Emitted after a measured observation updates the posterior."""

    probe: str
    symbol: str
    before: dict[str, float]
    after: dict[str, float]
    entropy_before: float
    entropy_after: float
    type: str = field(default="belief_updated", init=False)


@dataclass(frozen=True)
class EvidenceEntry:
    """One consumed probe, as it goes into the investigation's audit trail."""

    probe: str
    symbol: str | None
    measured: bool
    updated_belief: bool
    note: str | None


@dataclass(frozen=True)
class Verdict:
    """The terminal event: the engine's answer plus why it stopped looking."""

    top_hypothesis: str
    confidence: float
    runners_up: list[tuple[str, float]]
    stop_reason: str
    evidence: list[EvidenceEntry]
    type: str = field(default="verdict", init=False)


InvestigationEvent = ProbeSelected | ProbeUnmeasured | BeliefUpdated | Verdict


class Investigation:
    """Runs one target through the select -> consume -> update -> stop loop."""

    def __init__(
        self,
        target: str,
        spec: Spec,
        probe_runner: ProbeRunner,
        budget_s: float = 30.0,
        threshold: float = 0.85,
    ) -> None:
        if budget_s <= 0:
            raise ValueError(f"budget_s must be > 0, got {budget_s!r}")
        if not 0.0 < threshold <= 1.0:
            raise ValueError(
                f"threshold must be within (0.0, 1.0], got {threshold!r}; a threshold "
                "<= 0 would report the prior itself as a confident verdict before any "
                "evidence is gathered"
            )

        self.target = target
        self.spec = spec
        self.probe_runner = probe_runner
        self.budget_s = budget_s
        self.threshold = threshold

        self.selector = TestSelector(spec)
        hypotheses = list(spec.hypotheses)
        priors = [spec.hypotheses[h].prior for h in hypotheses]
        self.belief = BeliefState(hypotheses, priors)

        self.remaining: set[str] = set(spec.likelihoods)
        self.observed: dict[str, str] = {}
        self.evidence: list[EvidenceEntry] = []
        self.elapsed_s = 0.0

    async def run(self):
        while True:
            _, top_confidence = self.belief.top(1)[0]
            if top_confidence >= self.threshold:
                yield self._verdict("confident")
                return

            if self.elapsed_s >= self.budget_s:
                yield self._verdict("budget_exhausted")
                return

            eligible = self.selector.eligible(self.remaining, self.observed)
            if not eligible:
                yield self._verdict("no_eligible_tests")
                return

            ranking = self.selector.rank(self.belief, eligible)
            _, best_gain, _, best_probe = ranking[0]
            if best_gain < _MIN_INFORMATIVE_GAIN_BITS:
                yield self._verdict("no_informative_tests")
                return

            alternatives = [
                Alternative(probe=probe, expected_bits=gain)
                for _, gain, _, probe in ranking[1 : 1 + _TOP_ALTERNATIVES]
            ]
            yield ProbeSelected(probe=best_probe, expected_bits=best_gain, chose_over=alternatives)

            observation = await self.probe_runner(best_probe, self.target)
            observation.validate()
            if observation.probe_id != best_probe:
                raise ValueError(
                    f"probe runner was asked to run {best_probe!r} but returned an "
                    f"observation for {observation.probe_id!r}"
                )

            self.remaining.discard(best_probe)

            if not observation.measured:
                yield ProbeUnmeasured(probe=best_probe, note=observation.note)
                self.evidence.append(
                    EvidenceEntry(
                        probe=best_probe,
                        symbol=None,
                        measured=False,
                        updated_belief=False,
                        note=observation.note,
                    )
                )
                continue

            before = dict(zip(self.belief.hypotheses, self.belief.probs(), strict=True))
            entropy_before = self.belief.entropy()

            likelihood_row = self.spec.likelihoods[best_probe].table[observation.symbol]
            log_likelihood = np.log(
                [likelihood_row[h] for h in self.belief.hypotheses]
            )
            self.belief.update(log_likelihood)
            self.observed[best_probe] = observation.symbol
            self.elapsed_s += self.spec.likelihoods[best_probe].cost_seconds

            after = dict(zip(self.belief.hypotheses, self.belief.probs(), strict=True))
            entropy_after = self.belief.entropy()

            yield BeliefUpdated(
                probe=best_probe,
                symbol=observation.symbol,
                before=before,
                after=after,
                entropy_before=entropy_before,
                entropy_after=entropy_after,
            )
            self.evidence.append(
                EvidenceEntry(
                    probe=best_probe,
                    symbol=observation.symbol,
                    measured=True,
                    updated_belief=True,
                    note=None,
                )
            )

    def _verdict(self, stop_reason: str) -> Verdict:
        top_hypothesis, confidence = self.belief.top(1)[0]
        runners_up = self.belief.top(1 + _TOP_ALTERNATIVES)[1:]
        return Verdict(
            top_hypothesis=top_hypothesis,
            confidence=confidence,
            runners_up=runners_up,
            stop_reason=stop_reason,
            evidence=list(self.evidence),
        )
