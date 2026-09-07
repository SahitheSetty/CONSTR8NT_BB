"""Wires Person 1 collection + Person 2 path analysis into the Person 3
diagnosis engine, and shapes the combined result for the frontend.

This is the only module that knows about all three layers at once. Each
layer stays ignorant of the others -- Person 1 never sees hypotheses,
the diagnosis engine never parses raw text (see CLAUDE.md) -- and this
module is where their three independently-designed JSON contracts get
translated into each other. The diagnosis/hypotheses/evidence fields
themselves are Person 3's own (blackbox_engine.exporter) -- this module
only adds the path/performance/anomaly visualisation data exporter.py
doesn't own.
"""

from __future__ import annotations

from typing import Any

from app.models import InvestigationResult
from backend.person2.path_analysis import compare_paths
from blackbox_engine.adapter import to_observations
from blackbox_engine.exporter import export_investigation
from blackbox_engine.orchestrator import BeliefUpdated, Investigation, ProbeUnmeasured, Verdict
from blackbox_engine.spec_loader import Spec
from blackbox_engine.symbols import Observation

_HIGH_LATENCY_RTT_MS = 200.0
_HIGH_PACKET_LOSS_PERCENT = 10.0


def normalize_for_adapter(result: InvestigationResult) -> dict[str, Any]:
    """Translate Person 1's InvestigationResult into the raw shape adapter.py expects.

    adapter.py accepts both its original fixture contract (hops/rtt_ms) and
    Person 1's live field names (path/rttMs) directly, so the only real gap
    left to close here is TCP/TLS: Person 1 stores those as flat
    tcp443/tcp80/tls fields, not the nested {"tcp": {"443": ...}} shape
    adapter.py's _tcp()/_tls_handshake() look for.
    """
    raw: dict[str, Any] = {
        "dns": result.dns.model_dump(),
        "http": result.http.model_dump(),
        "path": [hop.model_dump() for hop in result.path],
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
    resulting Observation dict. adapter.py's to_observations() already
    returns all 12 probes (unmapped ones as explicit unmeasured
    entries), so the fallback below is defensive only.
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


def _build_current_path(current: InvestigationResult, anomalies_by_hop: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
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


def _compare_anomaly_measurement(anomaly: dict[str, Any]) -> str:
    if anomaly["type"] == "LATENCY_SPIKE":
        return f"{anomaly['rttDeltaMs']} ms RTT increase"
    if anomaly["type"] == "PACKET_LOSS_SPIKE":
        return f"{anomaly['packetLossDeltaPercent']}% packet loss increase"
    return anomaly["type"].replace("_", " ").title()


def _direct_anomalies(current: InvestigationResult) -> list[dict[str, Any]]:
    """Anomalies visible from this run alone, independent of any baseline.

    Person 2's anomalies only exist when there's a previous run to compare
    against; a first-ever investigation of an already-degraded target would
    otherwise report zero anomalies no matter how bad the numbers are.
    """
    found = []
    for hop in current.path:
        if hop.rttMs is not None and hop.rttMs >= _HIGH_LATENCY_RTT_MS:
            found.append({
                "hop": hop.hop,
                "type": "HIGH_LATENCY",
                "measurement": f"{hop.rttMs:.0f} ms RTT",
            })

    if current.path:
        final_hop = current.path[-1]
        if (
            final_hop.packetLossPercent is not None
            and final_hop.packetLossPercent >= _HIGH_PACKET_LOSS_PERCENT
        ):
            found.append({
                "hop": final_hop.hop,
                "type": "PACKET_LOSS",
                "measurement": f"{final_hop.packetLossPercent:.0f}% packet loss",
            })

    return found


def _build_anomalies(
    current: InvestigationResult,
    person2_result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    compare_anomalies = person2_result.get("anomalies", []) if person2_result else []
    already_flagged_hops = {anomaly["hop"] for anomaly in compare_anomalies}
    direct_anomalies = [
        anomaly for anomaly in _direct_anomalies(current)
        if anomaly["hop"] not in already_flagged_hops
    ]

    ui_anomalies = [
        {
            "type": anomaly["type"].replace("_", " ").title(),
            "location": f"Hop {anomaly['hop']}",
            "severity": "high",
            "measurement": _compare_anomaly_measurement(anomaly),
            "evidence": [],
        }
        for anomaly in compare_anomalies
    ]
    ui_anomalies.extend(
        {
            "type": anomaly["type"].replace("_", " ").title(),
            "location": f"Hop {anomaly['hop']}",
            "severity": "high",
            "measurement": anomaly["measurement"],
            "evidence": [],
        }
        for anomaly in direct_anomalies
    )
    return ui_anomalies


def _anomalies_by_hop(anomalies: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    by_hop: dict[int, dict[str, Any]] = {}
    for anomaly in anomalies:
        hop_number = int(anomaly["location"].removeprefix("Hop ")) if anomaly["location"].startswith("Hop ") else None
        if hop_number is not None:
            by_hop[hop_number] = {"type": anomaly["type"], "severity": anomaly["severity"]}
    return by_hop


def _probe_label(probe_id: str) -> str:
    return probe_id.replace("_", " ").lower()


def _build_timeline(events: list[Any]) -> list[dict[str, Any]]:
    timeline = [{"event": "Investigation started", "status": "completed"}]
    for event in events:
        if isinstance(event, BeliefUpdated):
            timeline.append({
                "event": f"Observed {_probe_label(event.probe)}: {event.symbol}",
                "status": "completed",
            })
        elif isinstance(event, ProbeUnmeasured):
            timeline.append({
                "event": f"{_probe_label(event.probe)} could not be measured",
                "status": "completed",
            })
        elif isinstance(event, Verdict):
            timeline.append({
                "event": f"Diagnosis generated ({event.stop_reason.replace('_', ' ')})",
                "status": "completed",
            })
    return timeline


def _is_healthy(current: InvestigationResult, anomalies: list[dict[str, Any]]) -> bool:
    """True when Person 1 measured no failure signal anywhere.

    The Bayesian engine's 12 hypotheses all assume *something* is broken --
    there's no "target is fine" hypothesis among them, and several of its
    likelihood rows are intentionally tied on a clean reading (see
    hypotheses.yaml's per-probe tables), so a genuinely healthy target has
    no reliable winner for the engine to pick. Route those cases around the
    engine entirely rather than force one of the 12 failure labels onto a
    site that isn't failing.
    """
    if anomalies:
        return False
    if not current.dns.resolved:
        return False
    if not current.http.reachable or current.http.status is None or not (200 <= current.http.status < 400):
        return False
    if current.tcp443.status not in (None, "open") or current.tcp80.status not in (None, "open"):
        return False
    if current.tls.handshake not in (None, "ok"):
        return False
    return True


def _no_issues_report(current: InvestigationResult) -> tuple[dict[str, Any], list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    """Build the diagnosis/hypotheses/evidence/timeline fields for a healthy target."""
    evidence = ['dns_resolution was observed as "ok".']
    if current.tcp443.status:
        evidence.append(f'tcp_443 was observed as "{current.tcp443.status}".')
    if current.tcp80.status:
        evidence.append(f'tcp_80 was observed as "{current.tcp80.status}".')
    if current.tls.handshake:
        evidence.append(f'tls_handshake was observed as "{current.tls.handshake}".')
    if current.http.status is not None:
        evidence.append(f'http_status was observed as "{current.http.status}".')
    evidence.append("No path, latency, or packet-loss anomalies were detected.")

    diagnosis = {
        "probableCause": "No issues detected",
        "confidence": "high",
        "supportingEvidence": evidence,
        "alternativeHypotheses": [],
    }
    hypotheses = [{
        "type": "Inference",
        "hypothesis": "No issues detected",
        "confidence": "high",
        "reason": "DNS, TCP, TLS, and HTTP all completed normally with no path or performance anomalies.",
    }]
    timeline = [
        {"event": "Investigation started", "status": "completed"},
        {"event": "All checks passed -- no issues detected", "status": "completed"},
    ]
    return diagnosis, hypotheses, evidence, timeline


async def run_diagnosis(
    spec: Spec,
    baseline: InvestigationResult | None,
    current: InvestigationResult,
) -> dict[str, Any]:
    """Run one target through Person 2 comparison + the Person 3 engine.

    Returns the combined result already shaped for the frontend
    (see src/data/mockInvestigation.js for the target shape). The
    diagnosis/hypotheses/evidence fields come from Person 3's own
    exporter.export_investigation(), not reimplemented here -- except when
    the target is healthy, in which case the engine is skipped (see
    _is_healthy).
    """
    person2_result = None
    if baseline is not None:
        person2_result = compare_paths(baseline.model_dump(), current.model_dump())

    anomalies = _build_anomalies(current, person2_result)

    shared = {
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
        "currentPath": _build_current_path(current, _anomalies_by_hop(anomalies)),
        "previousPath": _build_previous_path(baseline),
        "pathComparison": _build_path_comparison(baseline, current, person2_result),
        "performanceComparison": _build_performance_comparison(baseline, current),
        "anomalies": anomalies,
    }

    if _is_healthy(current, anomalies):
        diagnosis, hypotheses, evidence, timeline = _no_issues_report(current)
        return {
            **shared,
            "evidence": evidence,
            "hypotheses": hypotheses,
            "diagnosis": diagnosis,
            "reasoningTrace": [],
            "timeline": timeline,
        }

    p1_raw = normalize_for_adapter(current)
    p2_for_adapter = build_p2_for_adapter(baseline, current, person2_result)

    probe_runner = LiveProbeRunner(p1_raw, p2_for_adapter)
    investigation = Investigation(current.target, spec, probe_runner)

    events = [event async for event in investigation.run()]
    verdict = events[-1]
    assert isinstance(verdict, Verdict)

    exported = export_investigation(events, spec)

    return {
        **shared,
        "evidence": exported["evidence"],
        "hypotheses": [
            {
                "type": "Inference" if index == 0 else "Alternative hypothesis",
                "hypothesis": hypothesis["hypothesis"],
                "confidence": hypothesis["confidence"],
                "reason": hypothesis["reason"],
            }
            for index, hypothesis in enumerate(exported["hypotheses"])
        ],
        "diagnosis": exported["diagnosis"],
        "reasoningTrace": exported["reasoningTrace"],
        "timeline": _build_timeline(events),
    }
