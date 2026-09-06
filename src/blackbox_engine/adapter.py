"""Translates Person 1 (raw collection) and Person 2 (analysis) JSON into
Observations expressed in the OBSERVATION_SPACE vocabulary.

The adapter accepts both:
1. The original engine fixture contract (`hops`, `rtt_ms`, `duration_ms`,
   `isDestination`, `tcp`, `tls`).
2. The current Person 1 API contract (`path`, `rttMs`, `responseTimeMs`).

Every upstream contract gap must fail safe: measured=False, symbol=None,
and a note explaining the gap -- never a guessed symbol.
"""

from __future__ import annotations

from typing import Any

from blackbox_engine.symbols import OBSERVATION_SPACE, Observation

# Absolute delta from a baseline RTT, in milliseconds, used when Person 2
# supplies rtt.delta_ms.
_LATENCY_DELTA_THRESHOLDS_MS = (20.0, 150.0)

# Absolute RTT at the final hop, in milliseconds, used when no baseline delta
# is available.
_LATENCY_ABSOLUTE_THRESHOLDS_MS = (80.0, 250.0)

_WAF_STATUS_CODES = {403, 429}


def to_observations(
    p1_raw: dict,
    p2_analysis: dict | None,
) -> dict[str, Observation]:
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
        probe_id=probe_id,
        symbol=None,
        measured=False,
        duration_ms=None,
        raw=raw,
        note=note,
    )


def _dns_resolution(p1_raw: dict) -> Observation:
    dns = p1_raw.get("dns")

    if not isinstance(dns, dict):
        return _unmeasured(
            "dns_resolution",
            "no dns block from Person 1",
            {},
        )

    duration_ms = dns.get("duration_ms", dns.get("responseTimeMs"))
    resolved = dns.get("resolved")

    if resolved is True:
        return Observation(
            "dns_resolution",
            "ok",
            True,
            duration_ms,
            dns,
            None,
        )

    if resolved is False:
        outcome = dns.get("outcome")

        if outcome in OBSERVATION_SPACE["dns_resolution"]:
            return Observation(
                "dns_resolution",
                outcome,
                True,
                duration_ms,
                dns,
                None,
            )

        error = dns.get("error")

        if error:
            note = (
                "dns resolution failed with only a free-text error, "
                "refusing to guess a symbol: "
                f"{error!r}"
            )
        else:
            note = (
                "dns resolution failed with no structured outcome "
                "and no error text"
            )

        return _unmeasured(
            "dns_resolution",
            note,
            dns,
        )

    return _unmeasured(
        "dns_resolution",
        "dns.resolved is null/absent",
        dns,
    )


def _tcp(p1_raw: dict, port: str) -> Observation:
    probe_id = f"tcp_{port}"
    tcp = p1_raw.get("tcp")

    # Original engine/fixture contract.
    if isinstance(tcp, dict) and isinstance(tcp.get(port), dict):
        block = tcp[port]
        status = block.get("status")
        duration_ms = block.get("duration_ms")

        if status is None:
            return _unmeasured(
                probe_id,
                f"tcp.{port}.status is null/absent",
                block,
            )

        if status not in OBSERVATION_SPACE[probe_id]:
            raise ValueError(
                f"upstream tcp.{port}.status {status!r} "
                f"is not a known {probe_id} symbol"
            )

        return Observation(
            probe_id,
            status,
            True,
            duration_ms,
            block,
            None,
        )

    # Current Person 1 does not expose TCP separately.
    #
    # We deliberately do NOT infer TCP status from HTTP reachability because
    # an HTTP boolean cannot distinguish open/refused/timeout/reset.
    http = p1_raw.get("http")

    if port == "443" and isinstance(http, dict) and "reachable" in http:
        return _unmeasured(
            probe_id,
            "Person 1 currently does not expose tcp.443 separately; "
            "http.reachable is a boolean and cannot distinguish open/refused/timeout/reset",
            {"http_reachable": http.get("reachable")},
        )

    return _unmeasured(
        probe_id,
        f"no tcp.{port} block and no usable fallback",
        {},
    )


def _tls_handshake(p1_raw: dict) -> Observation:
    tls = p1_raw.get("tls")

    # Current Person 1 does not expose TLS separately.
    if not isinstance(tls, dict):
        return _unmeasured(
            "tls_handshake",
            "no tls block from Person 1",
            {},
        )

    handshake = tls.get("handshake")
    duration_ms = tls.get("duration_ms")

    if handshake is None:
        return _unmeasured(
            "tls_handshake",
            "tls.handshake is null/absent",
            tls,
        )

    if handshake not in OBSERVATION_SPACE["tls_handshake"]:
        raise ValueError(
            f"upstream tls.handshake {handshake!r} "
            "is not a known tls_handshake symbol"
        )

    return Observation(
        "tls_handshake",
        handshake,
        True,
        duration_ms,
        tls,
        None,
    )


def _http_status(p1_raw: dict) -> Observation:
    http = p1_raw.get("http")

    if not isinstance(http, dict):
        return _unmeasured(
            "http_status",
            "no http block from Person 1",
            {},
        )

    status = http.get("status")
    duration_ms = http.get(
        "duration_ms",
        http.get("responseTimeMs"),
    )

    if status is None:
        return _unmeasured(
            "http_status",
            "http.status is null/absent",
            http,
        )

    if not isinstance(status, int):
        raise TypeError(
            f"upstream http.status {status!r} is not an int"
        )

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
        raise ValueError(
            f"upstream http.status {status!r} "
            "is outside the known HTTP range"
        )

    return Observation(
        "http_status",
        symbol,
        True,
        duration_ms,
        http,
        None,
    )


def _get_path(p1_raw: dict) -> list:
    """Return the path using either the fixture or Person 1 field name."""

    hops = p1_raw.get("hops")

    if isinstance(hops, list):
        return hops

    path = p1_raw.get("path")

    if isinstance(path, list):
        return path

    return []


def _get_rtt_ms(hop: dict) -> Any:
    """Read RTT from either the fixture or Person 1 field name."""

    if "rtt_ms" in hop:
        return hop.get("rtt_ms")

    return hop.get("rttMs")


def _get_packet_loss(hop: dict) -> Any:
    """Read packet loss using the shared field name."""

    return hop.get("packetLossPercent")


def _packet_loss(p1_raw: dict) -> Observation:
    hops = _get_path(p1_raw)

    if not hops:
        return _unmeasured(
            "packet_loss",
            "no hop/path list from Person 1",
            {},
        )

    final_hop = hops[-1]

    if not isinstance(final_hop, dict):
        return _unmeasured(
            "packet_loss",
            "final hop/path entry is not an object",
            final_hop,
        )

    loss = _get_packet_loss(final_hop)

    if loss is None:
        return _unmeasured(
            "packet_loss",
            "final hop packetLossPercent is null",
            final_hop,
        )

    if loss == 0:
        symbol = "none"
    elif 0 < loss <= 5:
        symbol = "low"
    elif 5 < loss < 100:
        symbol = "high"
    elif loss == 100:
        symbol = "total"
    else:
        raise ValueError(
            f"final hop packetLossPercent {loss!r} "
            "is outside [0, 100]"
        )

    return Observation(
        "packet_loss",
        symbol,
        True,
        None,
        final_hop,
        None,
    )


def _bucket_latency(
    value_ms: float,
    thresholds: tuple[float, float],
) -> str:
    low, high = thresholds

    if value_ms <= low:
        return "normal"

    if value_ms <= high:
        return "elevated"

    return "severe"


def _latency_profile(
    p1_raw: dict,
    p2_analysis: dict | None,
) -> Observation:

    if isinstance(p2_analysis, dict):
        rtt = p2_analysis.get("rtt")

        if isinstance(rtt, dict):
            delta = rtt.get("delta_ms")

            if delta is not None:
                symbol = _bucket_latency(
                    abs(delta),
                    _LATENCY_DELTA_THRESHOLDS_MS,
                )

                return Observation(
                    "latency_profile",
                    symbol,
                    True,
                    None,
                    rtt,
                    None,
                )

    hops = _get_path(p1_raw)

    if hops:
        final_hop = hops[-1]

        if isinstance(final_hop, dict):
            final_rtt = _get_rtt_ms(final_hop)

            if final_rtt is not None:
                symbol = _bucket_latency(
                    final_rtt,
                    _LATENCY_ABSOLUTE_THRESHOLDS_MS,
                )

                return Observation(
                    "latency_profile",
                    symbol,
                    True,
                    None,
                    final_hop,
                    None,
                )

    return _unmeasured(
        "latency_profile",
        "no RTT delta from Person 2 and no absolute final-hop RTT from Person 1",
        {},
    )


def _path_change(p2_analysis: dict | None) -> Observation:

    if not isinstance(p2_analysis, dict):
        return Observation(
            "path_change",
            "no_baseline",
            True,
            None,
            {},
            "no Person 2 analysis supplied",
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
            "path_change",
            "no_baseline",
            True,
            None,
            p2_analysis,
            "pathChanged is null/absent",
        )

    if changed is False:
        return Observation(
            "path_change",
            "unchanged",
            True,
            None,
            p2_analysis,
            None,
        )

    correlated = p2_analysis.get("timingCorrelated")

    symbol = (
        "changed_correlated"
        if correlated
        else "changed_uncorrelated"
    )

    return Observation(
        "path_change",
        symbol,
        True,
        None,
        p2_analysis,
        None,
    )


def _path_reachability(p1_raw: dict) -> Observation:
    hops = _get_path(p1_raw)

    if not hops:
        return _unmeasured(
            "path_reachability",
            "no hop/path list from Person 1",
            {},
        )

    # Original fixture contract explicitly tells us whether the final hop
    # is the destination.
    final_hop = hops[-1]

    if not isinstance(final_hop, dict):
        return _unmeasured(
            "path_reachability",
            "final hop/path entry is not an object",
            final_hop,
        )

    if final_hop.get("isDestination"):
        return Observation(
            "path_reachability",
            "complete",
            True,
            None,
            final_hop,
            None,
        )

    # Current Person 1 has no isDestination field. In that case, the final
    # path entry is not enough to prove that the destination was reached.
    #
    # We can still identify explicit traceroute errors, but we must not
    # guess "complete" merely because the path contains hops.
    if "isDestination" not in final_hop:
        trailing_errors = 0

        for hop in reversed(hops):
            if isinstance(hop, dict) and hop.get("error") is not None:
                trailing_errors += 1
            else:
                break

        if trailing_errors == len(hops):
            return Observation(
                "path_reachability",
                "no_response",
                True,
                None,
                {"path": hops},
                None,
            )

        if trailing_errors > 1:
            return Observation(
                "path_reachability",
                "stalls_midpath",
                True,
                None,
                {"path": hops},
                None,
            )

        return _unmeasured(
            "path_reachability",
            "Person 1 path entries do not expose isDestination; "
            "destination reachability cannot be determined safely",
            final_hop,
        )

    # Original fixture behavior for paths without a destination flag.
    trailing_errors = 0

    for hop in reversed(hops):
        if hop.get("error") is not None:
            trailing_errors += 1
        else:
            break

    if trailing_errors == len(hops):
        return Observation(
            "path_reachability",
            "no_response",
            True,
            None,
            {"hops": hops},
            None,
        )

    if trailing_errors > 1:
        return Observation(
            "path_reachability",
            "stalls_midpath",
            True,
            None,
            {"hops": hops},
            None,
        )

    return Observation(
        "path_reachability",
        "stalls_at_edge",
        True,
        None,
        final_hop,
        None,
    )
