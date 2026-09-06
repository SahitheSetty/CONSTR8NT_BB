from __future__ import annotations

from pathlib import Path

from app.service import investigate_target
from backend.person2.path_analysis import compare_paths
from blackbox_engine.adapter import to_observations
from blackbox_engine.mocks import ReplayMock
from blackbox_engine.orchestrator import Investigation, Verdict
from blackbox_engine.spec_loader import load_spec


SPEC_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "blackbox_engine"
    / "hypotheses.yaml"
)


def _format_path(path: list[dict]) -> list[dict]:
    formatted = []

    for hop in path or []:
        hop_number = hop.get("hop", hop.get("hopNumber"))
        ip = hop.get("ip")
        hostname = hop.get("hostname")
        rtt = hop.get("rttMs", hop.get("rtt"))
        packet_loss = hop.get(
            "packetLossPercent",
            hop.get("packetLoss", 0),
        )

        if hop_number is None:
            continue

        is_destination = bool(
            ip
            and (
                hop_number == len(path)
                or not hop.get("error")
            )
        )

        status = "destination" if is_destination else "normal"

        formatted.append(
            {
                "hopNumber": hop_number,
                "ip": ip,
                "rtt": rtt,
                "packetLoss": packet_loss or 0,
                "asn": None,
                "network": hostname or "Unknown Network",
                "status": status,
                "anomaly": None,
                "evidence": [],
            }
        )

    return formatted


def _build_path_comparison(
    previous_data: dict | None,
    current_data: dict,
    p2_analysis: dict | None,
) -> dict:
    if previous_data is None:
        return {
            "status": "no_baseline",
            "message": "NO BASELINE AVAILABLE",
            "addedHops": [],
            "removedHops": [],
            "commonHops": [],
            "divergencePoint": None,
        }

    previous_path = previous_data.get("path", [])
    current_path = current_data.get("path", [])

    previous_ips = [
        hop.get("ip")
        for hop in previous_path
        if hop.get("ip")
    ]

    current_ips = [
        hop.get("ip")
        for hop in current_path
        if hop.get("ip")
    ]

    added_hops = [
        ip for ip in current_ips
        if ip not in previous_ips
    ]

    removed_hops = [
        ip for ip in previous_ips
        if ip not in current_ips
    ]

    common_hops = [
        ip for ip in current_ips
        if ip in previous_ips
    ]

    divergence_point = None

    for index, (previous_hop, current_hop) in enumerate(
        zip(previous_path, current_path),
        start=1,
    ):
        if previous_hop.get("ip") != current_hop.get("ip"):
            divergence_point = index
            break

    if divergence_point is None and (
        len(previous_path) != len(current_path)
    ):
        divergence_point = min(
            len(previous_path),
            len(current_path),
        ) + 1

    path_changed = bool(
        added_hops
        or removed_hops
        or divergence_point is not None
    )

    if not path_changed:
        status = "unchanged"
        message = "PATH UNCHANGED"
    else:
        status = "path_changed"
        message = "PATH CHANGE DETECTED"

    return {
        "status": status,
        "message": message,
        "addedHops": added_hops,
        "removedHops": removed_hops,
        "commonHops": common_hops,
        "divergencePoint": divergence_point,
        "pathChanged": path_changed,
        "changes": (
            p2_analysis.get("changes", [])
            if p2_analysis
            else []
        ),
    }


def _build_performance_comparison(
    previous_data: dict | None,
    current_data: dict,
) -> dict | None:
    if previous_data is None:
        return None

    previous_path = previous_data.get("path", [])
    current_path = current_data.get("path", [])

    def final_rtt(path):
        values = [
            hop.get("rttMs")
            for hop in path
            if hop.get("rttMs") is not None
        ]
        return values[-1] if values else None

    def final_packet_loss(path):
        values = [
            hop.get("packetLossPercent")
            for hop in path
            if hop.get("packetLossPercent") is not None
        ]
        return values[-1] if values else 0

    previous_rtt = final_rtt(previous_path)
    current_rtt = final_rtt(current_path)

    previous_loss = final_packet_loss(previous_path)
    current_loss = final_packet_loss(current_path)

    previous_http = previous_data.get("http", {})
    current_http = current_data.get("http", {})

    previous_response_time = previous_http.get(
        "responseTimeMs"
    )
    current_response_time = current_http.get(
        "responseTimeMs"
    )

    previous_status_code = previous_http.get("status")
    current_status_code = current_http.get("status")

    rtt_difference = (
        current_rtt - previous_rtt
        if current_rtt is not None
        and previous_rtt is not None
        else None
    )

    loss_difference = (
        current_loss - previous_loss
        if current_loss is not None
        and previous_loss is not None
        else None
    )

    response_difference = (
        current_response_time - previous_response_time
        if current_response_time is not None
        and previous_response_time is not None
        else None
    )

    degraded = (
        (rtt_difference is not None and rtt_difference >= 50)
        or (
            loss_difference is not None
            and loss_difference >= 10
        )
        or (
            response_difference is not None
            and response_difference >= 50
        )
    )

    return {
        "status": "degraded" if degraded else "normal",
        "previous": {
            "rtt": previous_rtt,
            "packetLoss": previous_loss,
            "httpResponseTime": previous_response_time,
            "httpStatusCode": previous_status_code,
        },
        "current": {
            "rtt": current_rtt,
            "packetLoss": current_loss,
            "httpResponseTime": current_response_time,
            "httpStatusCode": current_status_code,
        },
        "difference": {
            "rtt": rtt_difference,
            "packetLoss": loss_difference,
            "httpResponseTime": response_difference,
        },
    }


def _build_anomalies(
    current_data: dict,
    p2_analysis: dict | None,
) -> list[dict]:
    anomalies = []

    for anomaly in (
        p2_analysis.get("anomalies", [])
        if p2_analysis
        else []
    ):
        anomaly_type = anomaly.get(
            "type",
            "Network anomaly",
        )

        location = anomaly.get(
            "location",
            "Network path",
        )

        severity = anomaly.get(
            "severity",
            "medium",
        )

        measurement = anomaly.get(
            "measurement",
            "",
        )

        evidence = anomaly.get(
            "evidence",
            [],
        )

        anomalies.append(
            {
                "type": anomaly_type,
                "location": location,
                "severity": severity,
                "measurement": measurement,
                "evidence": evidence,
            }
        )

    path = current_data.get("path", [])

    for hop in path:
        rtt = hop.get("rttMs")
        packet_loss = hop.get("packetLossPercent", 0)

        if rtt is not None and rtt >= 200:
            anomalies.append(
                {
                    "type": "High latency",
                    "location": f"Hop {hop.get('hop')}",
                    "severity": "high",
                    "measurement": f"{rtt:.0f} ms RTT",
                    "evidence": [
                        f"Latency reached {rtt:.0f} ms"
                    ],
                }
            )

        if packet_loss is not None and packet_loss >= 10:
            anomalies.append(
                {
                    "type": "Packet loss",
                    "location": f"Hop {hop.get('hop')}",
                    "severity": "high",
                    "measurement": (
                        f"{packet_loss:.0f}% packet loss"
                    ),
                    "evidence": [
                        (
                            f"{packet_loss:.0f}% packet loss "
                            "observed"
                        )
                    ],
                }
            )

    return anomalies


def _build_evidence(
    current_data: dict,
    anomalies: list[dict],
    verdict: Verdict,
) -> list[str]:
    evidence = []

    dns = current_data.get("dns", {})
    http = current_data.get("http", {})
    path = current_data.get("path", [])

    if dns.get("resolved"):
        addresses = dns.get("addresses", [])

        if addresses:
            evidence.append(
                "DNS resolved to "
                + ", ".join(addresses)
            )
        else:
            evidence.append("DNS resolution succeeded")
    else:
        evidence.append("DNS resolution failed")

    if http.get("reachable"):
        status = http.get("status")

        if status is not None:
            evidence.append(
                f"HTTP endpoint returned status {status}"
            )
        else:
            evidence.append(
                "HTTP endpoint was reachable"
            )
    else:
        evidence.append("HTTP endpoint was not reachable")

    for anomaly in anomalies:
        measurement = anomaly.get("measurement")

        if measurement:
            evidence.append(
                f"{measurement} at "
                f"{anomaly.get('location', 'network path')}"
            )

    for entry in verdict.evidence:
        if entry.note:
            evidence.append(entry.note)

    return list(dict.fromkeys(evidence))


def _build_hypotheses(verdict: Verdict) -> list[dict]:
    hypotheses = [
        {
            "type": "Engine inference",
            "description": verdict.top_hypothesis,
            "confidence": (
                f"{verdict.confidence * 100:.1f}%"
            ),
            "evidence": [],
        }
    ]

    for hypothesis, confidence in verdict.runners_up:
        hypotheses.append(
            {
                "type": "Alternative hypothesis",
                "description": hypothesis,
                "confidence": (
                    f"{confidence * 100:.1f}%"
                ),
                "evidence": [],
            }
        )

    return hypotheses


def _build_diagnosis(
    verdict: Verdict,
    anomalies: list[dict],
    evidence: list[str],
) -> dict:
    if not anomalies and verdict.confidence < 0.85:
        probable_cause = "INSUFFICIENT DIAGNOSTIC EVIDENCE"
        confidence = "LOW"
    elif verdict.confidence >= 0.85:
        probable_cause = verdict.top_hypothesis.upper()
        confidence = "HIGH"
    elif verdict.confidence >= 0.60:
        probable_cause = verdict.top_hypothesis.upper()
        confidence = "MEDIUM"
    else:
        probable_cause = "INCONCLUSIVE"
        confidence = "LOW"

    alternatives = [
        hypothesis
        for hypothesis, _ in verdict.runners_up
    ]

    return {
        "probableCause": probable_cause,
        "confidence": confidence,
        "supportingEvidence": evidence,
        "alternativeHypotheses": alternatives,
    }


def _build_timeline(
    current_data: dict,
    anomalies: list[dict],
) -> list[dict]:
    timeline = [
        {
            "event": "Investigation started",
            "status": "completed",
        },
        {
            "event": "DNS resolved"
            if current_data.get("dns", {}).get("resolved")
            else "DNS resolution failed",
            "status": "completed",
        },
        {
            "event": "HTTP checked",
            "status": "completed",
        },
        {
            "event": "Path discovered",
            "status": "completed",
        },
    ]

    if anomalies:
        timeline.append(
            {
                "event": "Anomaly detected",
                "status": "completed",
            }
        )

    timeline.append(
        {
            "event": "Diagnosis generated",
            "status": "completed",
        }
    )

    return timeline


def run_investigation(
    target: str,
    previous_data: dict | None = None,
) -> dict:
    current_result = investigate_target(target)
    current_data = current_result.model_dump()

    p2_analysis = None

    if previous_data is not None:
        p2_analysis = compare_paths(
            previous_data,
            current_data,
        )

    observations = to_observations(
        current_data,
        p2_analysis,
    )

    spec = load_spec(SPEC_PATH)
    probe_runner = ReplayMock(observations)

    engine = Investigation(
        target=target,
        spec=spec,
        probe_runner=probe_runner,
    )

    events = []

    import asyncio

    async def consume_engine():
        async for event in engine.run():
            events.append(event)

    asyncio.run(consume_engine())

    verdict = next(
        event
        for event in reversed(events)
        if isinstance(event, Verdict)
    )

    formatted_path = _format_path(
        current_data.get("path", [])
    )

    path_comparison = _build_path_comparison(
        previous_data,
        current_data,
        p2_analysis,
    )

    performance_comparison = (
        _build_performance_comparison(
            previous_data,
            current_data,
        )
    )

    anomalies = _build_anomalies(
        current_data,
        p2_analysis,
    )

    evidence = _build_evidence(
        current_data,
        anomalies,
        verdict,
    )

    hypotheses = _build_hypotheses(verdict)

    diagnosis = _build_diagnosis(
        verdict,
        anomalies,
        evidence,
    )

    timeline = _build_timeline(
        current_data,
        anomalies,
    )

    dns = current_data.get("dns", {})

    http = current_data.get("http", {})

    return {
        "id": current_data["investigationId"],
        "target": current_data["target"],
        "timestamp": current_data["timestamp"],
        "investigationId": current_data["investigationId"],
        "dns": {
            "status": (
                "completed"
                if dns.get("resolved")
                else "failed"
            ),
            "resolved": dns.get("resolved", False),
            "address": (
                dns.get("addresses", [None])[0]
                if dns.get("addresses")
                else None
            ),
            "addresses": dns.get("addresses", []),
            "responseTime": dns.get("responseTimeMs"),
            "error": dns.get("error"),
        },
        "http": {
            "status": "completed",
            "reachable": http.get("reachable", False),
            "responseTime": http.get("responseTimeMs"),
            "statusCode": http.get("status"),
            "error": http.get("error"),
        },
        "currentPath": formatted_path,
        "previousPath": (
            _format_path(
                previous_data.get("path", [])
            )
            if previous_data is not None
            else None
        ),
        "pathComparison": path_comparison,
        "performanceComparison": performance_comparison,
        "anomalies": anomalies,
        "evidence": evidence,
        "hypotheses": hypotheses,
        "diagnosis": diagnosis,
        "timeline": timeline,
        "engine": {
            "topHypothesis": verdict.top_hypothesis,
            "confidence": verdict.confidence,
            "runnersUp": verdict.runners_up,
            "stopReason": verdict.stop_reason,
        },
        "observations": {
            probe: {
                "symbol": observation.symbol,
                "measured": observation.measured,
                "durationMs": observation.duration_ms,
                "note": observation.note,
            }
            for probe, observation in observations.items()
        },
        "status": current_data["status"],
        "errors": current_data["errors"],
    }