"""The fixed symbol vocabulary the diagnosis engine reasons over.

The engine never parses raw text or tool output — Person 1 and Person 2 do that
work and hand us Observations built from this vocabulary. This module is the
treaty with the outside world: it is the only file every upstream contract
mismatch should surface against.
"""

from __future__ import annotations

from dataclasses import dataclass

OBSERVATION_SPACE: dict[str, list[str]] = {
    "dns_resolution": ["ok", "nxdomain", "servfail", "refused", "timeout"],
    "dns_consistency": ["all_agree", "resolvers_disagree", "auth_differs_from_cache"],
    "tcp_443": ["open", "refused", "timeout", "reset"],
    "tcp_80": ["open", "refused", "timeout", "reset"],
    "tls_handshake": [
        "ok",
        "expired_cert",
        "hostname_mismatch",
        "chain_incomplete",
        "handshake_timeout",
        "not_attempted",
    ],
    "http_status": [
        "2xx",
        "3xx",
        "4xx",
        "waf_block",
        "5xx",
        "no_response",
        "not_attempted",
    ],
    "latency_profile": ["normal", "elevated", "severe", "unmeasurable"],
    "packet_loss": ["none", "low", "high", "total"],
    "path_reachability": ["complete", "stalls_midpath", "stalls_at_edge", "no_response"],
    "path_change": ["unchanged", "changed_correlated", "changed_uncorrelated", "no_baseline"],
    "external_vantage": [
        "target_ok_externally",
        "target_down_externally",
        "partial_by_region",
        "unavailable",
    ],
    "mtu_behaviour": ["normal", "large_packets_fail", "not_tested"],
}

# probe_id -> (prerequisite probe_id, symbols of that probe that satisfy it)
PRECONDITIONS: dict[str, tuple[str, set[str]]] = {
    "tls_handshake": ("tcp_443", {"open"}),
    "http_status": ("tls_handshake", {"ok"}),
    "mtu_behaviour": ("tcp_443", {"open"}),
}


@dataclass(frozen=True)
class Observation:
    """One consumed probe result, expressed only in vocabulary symbols."""

    probe_id: str
    symbol: str | None
    measured: bool
    duration_ms: float | None
    raw: dict
    note: str | None

    def validate(self) -> None:
        if self.probe_id not in OBSERVATION_SPACE:
            raise ValueError(
                f"unknown probe_id {self.probe_id!r}; "
                f"expected one of {sorted(OBSERVATION_SPACE)}"
            )

        if not self.measured:
            if self.symbol is not None:
                raise ValueError(
                    f"observation for probe {self.probe_id!r} is unmeasured "
                    f"(measured=False) but carries symbol {self.symbol!r}; "
                    "unmeasured observations must have symbol=None"
                )
            return

        allowed = OBSERVATION_SPACE[self.probe_id]
        if self.symbol not in allowed:
            raise ValueError(
                f"symbol {self.symbol!r} is not valid for probe {self.probe_id!r}; "
                f"allowed symbols are {allowed}"
            )
