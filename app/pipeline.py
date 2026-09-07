"""Wires Person 1 collection + Person 2 path analysis into the Person 3
diagnosis engine, and shapes the combined result for the frontend.

This is the only module that knows about all three layers at once. Each
layer stays ignorant of the others -- Person 1 never sees hypotheses,
the diagnosis engine never parses raw text (see CLAUDE.md) -- and this
module is where their three independently-designed JSON contracts get
translated into each other.
"""

from __future__ import annotations

from typing import Any

from app.models import InvestigationResult
from backend.person2.path_analysis import compare_paths
from blackbox_engine.adapter import to_observations
from blackbox_engine.orchestrator import BeliefUpdated, Investigation, ProbeUnmeasured, Verdict
from blackbox_engine.spec_loader import Spec
from blackbox_engine.symbols import Observation

_CONFIDENCE_HIGH = 0.7
_CONFIDENCE_MEDIUM = 0.4


def normalize_for_adapter(result: InvestigationResult) -> dict[str, Any]:
    """Translate Person 1's InvestigationResult into the raw shape adapter.py expects.

    Person 1's collectors and adapter.py were built against slightly
    different field-naming conventions (rttMs vs rtt_ms, "path" vs
    "hops"); this is the one place that gap gets closed.
    """
    hops = []
    last_index = len(result.path) - 1
    for index, hop in enumerate(result.path):
        hops.append({
            "hop": hop.hop,
            "ip": hop.ip,
            "hostname": hop.hostname,
            "rtt_ms": hop.rttMs,
            "packetLossPercent": hop.packetLossPercent,
            "isDestination": index == last_index and hop.error is None,
            "error": hop.error,
        })

    raw: dict[str, Any] = {
        "dns": result.dns.model_dump(),
        "http": result.http.model_dump(),
        "hops": hops,
    }

    if result.tcp443.status is not None or result.tcp80.status is not None:
        raw["tcp"] = {
            "443": {"status": result.tcp443.status, "duration_ms": result.tcp443.durationMs},
            "80": {"status": result.tcp80.status, "duration_ms": result.tcp80.durationMs},
        }

    if result.tls.handshake is not None:
        raw["tls"] = {"handshake": result.tls.handshake, "duration_ms": result.tls.durationMs}

    return raw


def _final_hop_rtt(result: InvestigationResult) -> float | None:
    if not result.path:
        return None
    return result.path[-1].rttMs


def build_p2_for_adapter(
    baseline: InvestigationResult | None,
    current: InvestigationResult,
    person2_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Translate Person 2's compare_paths() output into adapter.py's p2_analysis shape."""
    if baseline is None:
        return {"baselineAvailable": False}

    previous_rtt = _final_hop_rtt(baseline)
    current_rtt = _final_hop_rtt(current)
    rtt_block = None
    if previous_rtt is not None and current_rtt is not None:
        rtt_block = {
            "baseline_rtt_ms": previous_rtt,
            "current_rtt_ms": current_rtt,
            "delta_ms": current_rtt - previous_rtt,
        }

    return {
        "baselineAvailable": True,
        "pathChanged": person2_result.get("pathChanged") if person2_result else None,
        "timingCorrelated": None,
        "rtt": rtt_block,
    }


class LiveProbeRunner:
    """A ProbeRunner over one already-collected investigation.

    Person 1's collectors run once, up front -- a live network probe
    can't be re-issued mid-investigation the way a mock replay can --
    and each probe the orchestrator asks for is served from the
    resulting Observation dict. Probes adapter.py has no live mapping
    for yet (dns_consistency, external_vantage, mtu_behaviour) always
    come back unmeasured: never a guessed symbol.
    """

    def __init__(self, p1_raw: dict[str, Any], p2_analysis: dict[str, Any] | None) -> None:
        self.observations = to_observations(p1_raw, p2_analysis)

    async def __call__(self, probe_id: str, target: str) -> Observation:
        observation = self.observations.get(probe_id)
        if observation is not None:
            return observation
        return Observation(
            probe_id=probe_id,
            symbol=None,
            measured=False,
            duration_ms=None,
            raw={},
            note=f"probe {probe_id!r} has no live collector wired up yet",
        )


def _confidence_bucket(probability: float) -> str:
    if probability >= _CONFIDENCE_HIGH:
        return "HIGH"
    if probability >= _CONFIDENCE_MEDIUM:
        return "MEDIUM"
    return "LOW"


def _hop_by_number(result: InvestigationResult) -> dict[int, Any]:
    return {hop.hop: hop for hop in result.path}


def _to_ui_hop(hop: Any, *, is_destination: bool, anomaly: dict[str, Any] | None) -> dict[str, Any]:
    packet_loss = hop.packetLossPercent if hop.packetLossPercent is not None else 0
    status = "destination" if is_destination else ("anomalous" if anomaly else "normal")
    return {
        "hopNumber": hop.hop,
        "ip": hop.ip or "UNKNOWN",
        "rtt": hop.rttMs,
        "packetLoss": packet_loss,
        "asn": None,
        "network": hop.hostname,
        "status": status,
        "anomaly": anomaly,
        "evidence": [],
    }


def _build_current_path(current: InvestigationResult, person2_result: dict[str, Any] | None) -> list[dict[str, Any]]:
    anomalies_by_hop: dict[int, dict[str, Any]] = {}
    if person2_result:
        for anomaly in person2_result.get("anomalies", []):
            anomalies_by_hop[anomaly["hop"]] = {
                "type": anomaly["type"].replace("_", " ").title(),
                "severity": "high",
            }

    last_index = len(current.path) - 1
    return [
        _to_ui_hop(
            hop,
            is_destination=(index == last_index),
            anomaly=anomalies_by_hop.get(hop.hop),
        )
        for index, hop in enumerate(current.path)
    ]


def _build_previous_path(baseline: InvestigationResult | None) -> list[dict[str, Any]] | None:
    if baseline is None:
        return None
    last_index = len(baseline.path) - 1
    return [
        _to_ui_hop(hop, is_destination=(index == last_index), anomaly=None)
        for index, hop in enumerate(baseline.path)
    ]


def _build_path_comparison(
    baseline: InvestigationResult | None,
    current: InvestigationResult,
    person2_result: dict[str, Any] | None,
) -> dict[str, Any]:
    if baseline is None or person2_result is None:
        return {
            "status": "no_baseline",
            "message": "NO BASELINE AVAILABLE",
            "addedHops": [],
            "removedHops": [],
            "commonHops": [],
            "divergencePoint": None,
        }

    previous_by_number = _hop_by_number(baseline)
    current_by_number = _hop_by_number(current)

    added_hops = sorted(set(current_by_number) - set(previous_by_number))
    removed_hops = sorted(set(previous_by_number) - set(current_by_number))
    common_hops = sorted(set(current_by_number) & set(previous_by_number))

    has_change = bool(person2_result.get("pathChanged"))
    has_anomaly = bool(person2_result.get("anomalies"))

    if has_change and has_anomaly:
        status = "path_change_with_performance_impact"
        message = "PATH CHANGE WITH PERFORMANCE IMPACT"
    elif has_change:
        status = "path_changed"
        message = "PATH CHANGED"
    else:
        status = "unchanged"
        message = "PATH UNCHANGED"

    divergence_point = min(added_hops + removed_hops) if (added_hops or removed_hops) else None

    return {
        "status": status,
        "message": message,
        "addedHops": [current_by_number[h].ip or f"hop {h}" for h in added_hops],
        "removedHops": [previous_by_number[h].ip or f"hop {h}" for h in removed_hops],
        "commonHops": [current_by_number[h].ip or f"hop {h}" for h in common_hops],
        "divergencePoint": divergence_point,
    }


def _build_performance_comparison(
    baseline: InvestigationResult | None,
    current: InvestigationResult,
) -> dict[str, Any] | None:
    if baseline is None:
        return None

    previous = {
        "rtt": _final_hop_rtt(baseline),
        "packetLoss": baseline.path[-1].packetLossPercent if baseline.path else None,
        "httpResponseTime": baseline.http.responseTimeMs,
        "httpStatusCode": baseline.http.status,
    }
    current_metrics = {
        "rtt": _final_hop_rtt(current),
        "packetLoss": current.path[-1].packetLossPercent if current.path else None,
        "httpResponseTime": current.http.responseTimeMs,
        "httpStatusCode": current.http.status,
    }
    difference = {
        key: (
            round(current_metrics[key] - previous[key], 2)
            if previous[key] is not None and current_metrics[key] is not None
            else None
        )
        for key in ("rtt", "packetLoss", "httpResponseTime")
    }

    degraded = any((difference[key] or 0) > 0 for key in ("rtt", "packetLoss", "httpResponseTime"))

    return {
        "status": "degraded" if degraded else "stable",
        "previous": previous,
        "current": current_metrics,
        "difference": difference,
    }


def _probe_label(probe_id: str) -> str:
    return probe_id.replace("_", " ").upper()


def _build_evidence(verdict: Verdict) -> list[str]:
    return [
        f"{_probe_label(entry.probe)}: {entry.symbol}"
        for entry in verdict.evidence
        if entry.measured
    ]


def _build_hypotheses(spec: Spec, verdict: Verdict, evidence: list[str]) -> list[dict[str, Any]]:
    hypotheses = [
        {
            "type": "Inference",
            "description": spec.hypotheses[verdict.top_hypothesis].label,
            "confidence": _confidence_bucket(verdict.confidence),
            "evidence": evidence[:3],
        }
    ]
    hypotheses.extend(
        {
            "type": "Alternative hypothesis",
            "description": spec.hypotheses[name].label,
            "confidence": _confidence_bucket(probability),
            "evidence": [],
        }
        for name, probability in verdict.runners_up
    )
    return hypotheses


def _build_diagnosis(spec: Spec, verdict: Verdict, evidence: list[str]) -> dict[str, Any]:
    return {
        "probableCause": spec.hypotheses[verdict.top_hypothesis].label,
        "confidence": _confidence_bucket(verdict.confidence),
        "supportingEvidence": evidence,
        "alternativeHypotheses": [
            spec.hypotheses[name].label for name, _ in verdict.runners_up
        ],
    }


def _build_timeline(events: list[Any]) -> list[dict[str, Any]]:
    timeline = [{"event": "Investigation started", "status": "completed"}]
    for event in events:
        if isinstance(event, BeliefUpdated):
            timeline.append({
                "event": f"Observed {_probe_label(event.probe).lower()}: {event.symbol}",
                "status": "completed",
            })
        elif isinstance(event, ProbeUnmeasured):
            timeline.append({
                "event": f"{_probe_label(event.probe).lower()} could not be measured",
                "status": "completed",
            })
        elif isinstance(event, Verdict):
            timeline.append({
                "event": f"Diagnosis generated ({event.stop_reason.replace('_', ' ')})",
                "status": "completed",
            })
    return timeline


async def run_diagnosis(
    spec: Spec,
    baseline: InvestigationResult | None,
    current: InvestigationResult,
) -> dict[str, Any]:
    """Run one target through Person 2 comparison + the Person 3 engine.

    Returns the combined result already shaped for the frontend
    (see src/data/mockInvestigation.js for the target shape).
    """
    person2_result = None
    if baseline is not None:
        person2_result = compare_paths(baseline.model_dump(), current.model_dump())

    p1_raw = normalize_for_adapter(current)
    p2_for_adapter = build_p2_for_adapter(baseline, current, person2_result)

    probe_runner = LiveProbeRunner(p1_raw, p2_for_adapter)
    investigation = Investigation(current.target, spec, probe_runner)

    events = [event async for event in investigation.run()]
    verdict = events[-1]
    assert isinstance(verdict, Verdict)

    evidence = _build_evidence(verdict)

    return {
        "id": current.investigationId,
        "target": current.target,
        "timestamp": current.timestamp,
        "dns": {
            "status": "completed",
            "resolved": current.dns.resolved,
            "address": current.dns.addresses[0] if current.dns.addresses else None,
        },
        "http": {
            "status": "completed",
            "reachable": current.http.reachable,
            "responseTime": current.http.responseTimeMs,
            "statusCode": current.http.status,
        },
        "currentPath": _build_current_path(current, person2_result),
        "previousPath": _build_previous_path(baseline),
        "pathComparison": _build_path_comparison(baseline, current, person2_result),
        "performanceComparison": _build_performance_comparison(baseline, current),
        "anomalies": [
            {
                "type": anomaly["type"].replace("_", " ").title(),
                "location": f"Hop {anomaly['hop']}",
                "severity": "high",
                "measurement": _anomaly_measurement(anomaly),
                "evidence": [],
            }
            for anomaly in (person2_result.get("anomalies", []) if person2_result else [])
        ],
        "evidence": evidence,
        "hypotheses": _build_hypotheses(spec, verdict, evidence),
        "diagnosis": _build_diagnosis(spec, verdict, evidence),
        "timeline": _build_timeline(events),
    }


def _anomaly_measurement(anomaly: dict[str, Any]) -> str:
    if anomaly["type"] == "LATENCY_SPIKE":
        return f"{anomaly['rttDeltaMs']} ms RTT increase"
    if anomaly["type"] == "PACKET_LOSS_SPIKE":
        return f"{anomaly['packetLossDeltaPercent']}% packet loss increase"
    return anomaly["type"].replace("_", " ").title()
