"""Converts a completed Investigation's event stream into the frontend contract.

Person 3 owns exactly three fields of the frontend payload: `diagnosis`,
`hypotheses`, and `evidence`. This module produces those, plus an
internal-only `reasoningTrace` the frontend may optionally render and that
feeds the (separate, LLM-based) summariser. The LLM never sees this data
and makes zero diagnostic decisions -- everything here is plain
arithmetic over already-finished JSON.

Evidence strings are strictly factual ("probe X returned symbol Y") --
never a conclusion. Conclusions belong only in `diagnosis`.
"""

from __future__ import annotations

from typing import Any

from blackbox_engine.belief_state import BeliefState
from blackbox_engine.orchestrator import (
    BeliefUpdated,
    EvidenceEntry,
    InvestigationEvent,
    ProbeSelected,
    ProbeUnmeasured,
    Verdict,
)
from blackbox_engine.spec_loader import Spec

_CONFIDENCE_HIGH = 0.80
_CONFIDENCE_MEDIUM = 0.55


def confidence_bucket(probability: float) -> str:
    """Map a numeric probability to the frontend's three-level confidence string."""
    if probability >= _CONFIDENCE_HIGH:
        return "high"
    if probability >= _CONFIDENCE_MEDIUM:
        return "medium"
    return "low"


def _evidence_statement(entry: EvidenceEntry) -> str:
    if not entry.measured:
        detail = f" ({entry.note})" if entry.note else ""
        return f"{entry.probe} could not be measured{detail}."
    return f'{entry.probe} was observed as "{entry.symbol}".'


def _hypothesis_payload(spec: Spec, hypothesis_key: str, probability: float) -> dict[str, str]:
    hypothesis = spec.hypotheses[hypothesis_key]
    return {
        "hypothesis": hypothesis.label,
        "confidence": confidence_bucket(probability),
        "reason": hypothesis.remediation,
    }


def _build_reasoning_trace(events: list[InvestigationEvent], spec: Spec) -> list[dict[str, Any]]:
    initial_belief = BeliefState(
        list(spec.hypotheses), [spec.hypotheses[h].prior for h in spec.hypotheses]
    )
    last_belief = dict(zip(initial_belief.hypotheses, initial_belief.probs(), strict=True))
    last_entropy = initial_belief.entropy()

    trace: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None

    for event in events:
        if isinstance(event, ProbeSelected):
            pending = {
                "probe": event.probe,
                "expected_bits": event.expected_bits,
                "chose_over": [
                    {"probe": alt.probe, "expected_bits": alt.expected_bits}
                    for alt in event.chose_over
                ],
                "symbol": None,
                "measured": None,
                "note": None,
                "belief_before": last_belief,
                "belief_after": last_belief,
                "entropy_before": last_entropy,
                "entropy_after": last_entropy,
            }
            trace.append(pending)
        elif isinstance(event, ProbeUnmeasured):
            assert pending is not None
            pending["measured"] = False
            pending["note"] = event.note
            # belief/entropy already default to "unchanged" above
        elif isinstance(event, BeliefUpdated):
            assert pending is not None
            pending["symbol"] = event.symbol
            pending["measured"] = True
            pending["belief_before"] = event.before
            pending["belief_after"] = event.after
            pending["entropy_before"] = event.entropy_before
            pending["entropy_after"] = event.entropy_after
            last_belief = event.after
            last_entropy = event.entropy_after

    return trace


def export_investigation(events: list[InvestigationEvent], spec: Spec) -> dict[str, Any]:
    """Build the frontend contract payload from a completed investigation's events.

    `events` must be the full ordered event list produced by consuming
    `Investigation.run()` to completion (its last element must be the
    terminal Verdict).
    """
    if not events or not isinstance(events[-1], Verdict):
        raise ValueError(
            "export_investigation requires a completed event list ending in a Verdict"
        )
    verdict = events[-1]

    evidence = [_evidence_statement(entry) for entry in verdict.evidence]

    ranked = [(verdict.top_hypothesis, verdict.confidence), *verdict.runners_up]
    hypotheses = [_hypothesis_payload(spec, key, prob) for key, prob in ranked]

    diagnosis = {
        "probableCause": spec.hypotheses[verdict.top_hypothesis].label,
        "confidence": confidence_bucket(verdict.confidence),
        "supportingEvidence": evidence,
        "alternativeHypotheses": [spec.hypotheses[key].label for key, _ in verdict.runners_up],
    }

    return {
        "diagnosis": diagnosis,
        "hypotheses": hypotheses,
        "evidence": evidence,
        "reasoningTrace": _build_reasoning_trace(events, spec),
    }
