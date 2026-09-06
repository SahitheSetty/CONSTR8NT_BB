"""Translates Person 1 (raw collection) and Person 2 (analysis) JSON into
Observations expressed in the OBSERVATION_SPACE vocabulary.

This is the engine's only point of contact with the outside world. Every
upstream contract gap (a boolean where we need a structured outcome, a
free-text error where we need a symbol) must fail safe: measured=False,
symbol=None, and a note explaining the gap — never a guessed symbol.
"""

from __future__ import annotations

from typing import Any

from blackbox_engine.symbols import OBSERVATION_SPACE, Observation

# Absolute delta from a baseline RTT, in milliseconds, used when Person 2
# supplies rtt.delta_ms. Placeholder values pending tuning in evaluation.py.
_LATENCY_DELTA_THRESHOLDS_MS = (20.0, 150.0)

# Absolute RTT at the final hop, in milliseconds, used when no baseline delta
# is available. Placeholder values pending tuning in evaluation.py.
_LATENCY_ABSOLUTE_THRESHOLDS_MS = (80.0, 250.0)

_WAF_STATUS_CODES = {403, 429}


def to_observations(p1_raw: dict, p2_analysis: dict | None) -> dict[str, Observation]:
    """Map upstream JSON into a dict of probe_id -> Observation.

    Only probes this adapter has an explicit mapping rule for are returned.
    Every value is drawn from OBSERVATION_SPACE; nothing is inferred from
    free text, and a null/absent upstream value always yields
    measured=False, symbol=None rather than a substituted default.
    """
    observations = {
        "dns_resolution": _dns_resolution(p1_raw),
        "tcp_443": _tcp(p1_raw, "443"),
        "tcp_80": _tcp(p1_raw, "80"),
        "tls_handshake": _tls_handshake(p1_raw),
        "http_status": _http_status(p1_raw),
        "packet_loss": _packet_loss(p1_raw),
        "latency_profile": _latency_profile(p1_raw, p2_analysis),
        "path_change": _path_change(p2_analysis),
        "path_reachability": _path_reachability(p1_raw),
    }
    for observation in observations.values():
        observation.validate()
    return observations


def _unmeasured(probe_id: str, note: str, raw: Any) -> Observation:
    return Observation(
        probe_id=probe_id, symbol=None, measured=False, duration_ms=None, raw=raw, note=note
    )


def _dns_resolution(p1_raw: dict) -> Observation:
    dns = p1_raw.get("dns")
    if not isinstance(dns, dict):
        return _unmeasured("dns_resolution", "no dns block from Person 1", {})

    duration_ms = dns.get("duration_ms")
    resolved = dns.get("resolved")

    if resolved is True:
        return Observation("dns_resolution", "ok", True, duration_ms, dns, None)

    if resolved is False:
        outcome = dns.get("outcome")
        if outcome in OBSERVATION_SPACE["dns_resolution"]:
            return Observation("dns_resolution", outcome, True, duration_ms, dns, None)
        error = dns.get("error")
        if error:
            note = f"dns resolution failed with only a free-text error, refusing to guess a symbol: {error!r}"
        else:
            note = "dns resolution failed with no structured outcome and no error text"
        return Observation("dns_resolution", None, False, duration_ms, dns, note)

    # resolved is null/absent
    return _unmeasured("dns_resolution", "dns.resolved is null/absent", dns)


def _tcp(p1_raw: dict, port: str) -> Observation:
    probe_id = f"tcp_{port}"
    tcp = p1_raw.get("tcp")

    if isinstance(tcp, dict) and isinstance(tcp.get(port), dict):
        block = tcp[port]
        status = block.get("status")
        duration_ms = block.get("duration_ms")
        if status is None:
            return _unmeasured(probe_id, f"tcp.{port}.status is null/absent", block)
        if status not in OBSERVATION_SPACE[probe_id]:
            raise ValueError(
                f"upstream tcp.{port}.status {status!r} is not a known {probe_id} symbol"
            )
        return Observation(probe_id, status, True, duration_ms, block, None)

    http = p1_raw.get("http")
    if port == "443" and isinstance(http, dict) and "reachable" in http:
        return _unmeasured(
            probe_id,
            "upstream only provided http.reachable (bool); cannot infer refused vs "
            "timeout vs reset from a boolean — Person 1 needs to split this contract",
            {"http_reachable": http.get("reachable")},
        )

    return _unmeasured(probe_id, f"no tcp.{port} block and no usable fallback", {})


def _tls_handshake(p1_raw: dict) -> Observation:
    tls = p1_raw.get("tls")
    if not isinstance(tls, dict):
        return _unmeasured("tls_handshake", "no tls block from Person 1", {})

    handshake = tls.get("handshake")
    duration_ms = tls.get("duration_ms")
    if handshake is None:
        return _unmeasured("tls_handshake", "tls.handshake is null/absent", tls)
    if handshake not in OBSERVATION_SPACE["tls_handshake"]:
        raise ValueError(
            f"upstream tls.handshake {handshake!r} is not a known tls_handshake symbol"
        )
    return Observation("tls_handshake", handshake, True, duration_ms, tls, None)


def _http_status(p1_raw: dict) -> Observation:
    http = p1_raw.get("http")
    if not isinstance(http, dict):
        return _unmeasured("http_status", "no http block from Person 1", {})

    status = http.get("status")
    duration_ms = http.get("duration_ms")
    if status is None:
        return _unmeasured("http_status", "http.status is null/absent", http)
    if not isinstance(status, int):
        raise TypeError(f"upstream http.status {status!r} is not an int")

    if status in _WAF_STATUS_CODES:
        symbol = "waf_block"
    elif 200 <= status < 300:
        symbol = "2xx"
    elif 300 <= status < 400:
        symbol = "3xx"
    elif 400 <= status < 500:
        symbol = "4xx"
    elif 500 <= status < 600:
        symbol = "5xx"
    else:
        raise ValueError(f"upstream http.status {status!r} is outside the known HTTP range")

    return Observation("http_status", symbol, True, duration_ms, http, None)


def _packet_loss(p1_raw: dict) -> Observation:
    hops = p1_raw.get("hops")
    if not isinstance(hops, list) or not hops:
        return _unmeasured("packet_loss", "no hop list from Person 1", {})

    final_hop = hops[-1]
    loss = final_hop.get("packetLossPercent")
    if loss is None:
        return _unmeasured("packet_loss", "final hop packetLossPercent is null", final_hop)

    if loss == 0:
        symbol = "none"
    elif 0 < loss <= 5:
        symbol = "low"
    elif 5 < loss < 100:
        symbol = "high"
    elif loss == 100:
        symbol = "total"
    else:
        raise ValueError(f"final hop packetLossPercent {loss!r} is outside [0, 100]")

    return Observation("packet_loss", symbol, True, None, final_hop, None)


def _bucket_latency(value_ms: float, thresholds: tuple[float, float]) -> str:
    low, high = thresholds
    if value_ms <= low:
        return "normal"
    if value_ms <= high:
        return "elevated"
    return "severe"


def _latency_profile(p1_raw: dict, p2_analysis: dict | None) -> Observation:
    if isinstance(p2_analysis, dict):
        rtt = p2_analysis.get("rtt")
        if isinstance(rtt, dict):
            delta = rtt.get("delta_ms")
            if delta is not None:
                symbol = _bucket_latency(abs(delta), _LATENCY_DELTA_THRESHOLDS_MS)
                return Observation("latency_profile", symbol, True, None, rtt, None)

    hops = p1_raw.get("hops")
    if isinstance(hops, list) and hops:
        final_rtt = hops[-1].get("rtt_ms")
        if final_rtt is not None:
            symbol = _bucket_latency(final_rtt, _LATENCY_ABSOLUTE_THRESHOLDS_MS)
            return Observation("latency_profile", symbol, True, None, hops[-1], None)

    return _unmeasured(
        "latency_profile",
        "no RTT delta from Person 2 and no absolute final-hop RTT from Person 1",
        {},
    )


def _path_change(p2_analysis: dict | None) -> Observation:
    if not isinstance(p2_analysis, dict):
        return Observation(
            "path_change", "no_baseline", True, None, {}, "no Person 2 analysis supplied"
        )

    if not p2_analysis.get("baselineAvailable", True):
        return Observation(
            "path_change",
            "no_baseline",
            True,
            None,
            p2_analysis,
            "Person 2 reports no baseline available",
        )

    changed = p2_analysis.get("pathChanged")
    if changed is None:
        return Observation(
            "path_change", "no_baseline", True, None, p2_analysis, "pathChanged is null/absent"
        )
    if changed is False:
        return Observation("path_change", "unchanged", True, None, p2_analysis, None)

    correlated = p2_analysis.get("timingCorrelated")
    symbol = "changed_correlated" if correlated else "changed_uncorrelated"
    return Observation("path_change", symbol, True, None, p2_analysis, None)


def _path_reachability(p1_raw: dict) -> Observation:
    hops = p1_raw.get("hops")
    if not isinstance(hops, list) or not hops:
        return _unmeasured("path_reachability", "no hop list from Person 1", {})

    final_hop = hops[-1]
    if final_hop.get("isDestination"):
        return Observation("path_reachability", "complete", True, None, final_hop, None)

    trailing_errors = 0
    for hop in reversed(hops):
        if hop.get("error") is not None:
            trailing_errors += 1
        else:
            break

    if trailing_errors == len(hops):
        return Observation("path_reachability", "no_response", True, None, {"hops": hops}, None)
    if trailing_errors > 1:
        return Observation(
            "path_reachability", "stalls_midpath", True, None, {"hops": hops}, None
        )
    return Observation("path_reachability", "stalls_at_edge", True, None, final_hop, None)
