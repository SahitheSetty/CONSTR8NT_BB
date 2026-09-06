"""Probe runners used before Person 1/2's real collectors are wired up.

Every mock is an async callable matching the production probe-runner
signature `(probe_id: str, target: str) -> Observation`, so the
orchestrator never needs to know whether it is driving a scenario replay,
a stochastic simulation, or a real upstream run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import numpy as np

from blackbox_engine.spec_loader import Spec
from blackbox_engine.symbols import OBSERVATION_SPACE, Observation

ProbeRunner = Callable[[str, str], Awaitable[Observation]]


class ScenarioMock:
    """Replays a fixed probe -> symbol mapping with simulated latency."""

    def __init__(self, scenario: dict[str, str], latency_ms: float) -> None:
        self.scenario = scenario
        self.latency_ms = latency_ms

    async def __call__(self, probe_id: str, target: str) -> Observation:
        await asyncio.sleep(self.latency_ms / 1000)

        symbol = self.scenario.get(probe_id)
        if symbol is None:
            return Observation(
                probe_id=probe_id,
                symbol=None,
                measured=False,
                duration_ms=self.latency_ms,
                raw={"target": target},
                note=f"scenario has no scripted symbol for probe {probe_id!r}",
            )
        if symbol not in OBSERVATION_SPACE[probe_id]:
            raise ValueError(
                f"scenario symbol {symbol!r} is not valid for probe {probe_id!r}; "
                f"allowed symbols are {OBSERVATION_SPACE[probe_id]}"
            )
        return Observation(
            probe_id=probe_id,
            symbol=symbol,
            measured=True,
            duration_ms=self.latency_ms,
            raw={"target": target, "scripted_symbol": symbol},
            note=None,
        )


class StochasticMock:
    """Samples each observation from the spec's likelihood table for a known-true hypothesis."""

    def __init__(self, spec: Spec, truth: str, rng: np.random.Generator) -> None:
        if truth not in spec.hypotheses:
            raise ValueError(
                f"unknown hypothesis {truth!r}; known hypotheses are {sorted(spec.hypotheses)}"
            )
        self.spec = spec
        self.truth = truth
        self.rng = rng

    async def __call__(self, probe_id: str, target: str) -> Observation:
        likelihood = self.spec.likelihoods[probe_id]
        symbols = list(likelihood.table)
        probabilities = np.array(
            [likelihood.table[symbol][self.truth] for symbol in symbols], dtype=float
        )
        probabilities = probabilities / probabilities.sum()

        symbol = str(self.rng.choice(symbols, p=probabilities))
        return Observation(
            probe_id=probe_id,
            symbol=symbol,
            measured=True,
            duration_ms=None,
            raw={"target": target, "sampled_under_truth": self.truth},
            note=None,
        )


class FlakyMock:
    """Wraps another probe runner, injecting measured=False failures at a configured rate."""

    def __init__(self, inner: ProbeRunner, failure_rate: float, rng: np.random.Generator) -> None:
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError(f"failure_rate must be within [0, 1], got {failure_rate!r}")
        self.inner = inner
        self.failure_rate = failure_rate
        self.rng = rng

    async def __call__(self, probe_id: str, target: str) -> Observation:
        if self.rng.random() < self.failure_rate:
            return Observation(
                probe_id=probe_id,
                symbol=None,
                measured=False,
                duration_ms=None,
                raw={"target": target},
                note=f"FlakyMock injected a failure (failure_rate={self.failure_rate})",
            )
        return await self.inner(probe_id, target)


class ReplayMock:
    """Returns pre-collected observations from a completed Person 1 + Person 2 run.

    This is the production path in replay mode: no simulation, no
    randomness, just the exact Observations the adapter already built.
    """

    def __init__(self, observations: dict[str, Observation]) -> None:
        self.observations = observations

    async def __call__(self, probe_id: str, target: str) -> Observation:
        try:
            return self.observations[probe_id]
        except KeyError:
            raise KeyError(
                f"no pre-collected observation for probe {probe_id!r}; "
                f"available probes: {sorted(self.observations)}"
            ) from None


# One hand-written fingerprint per hypothesis: every probe mapped to the
# symbol it would produce under that fault, reasoning through the
# DNS -> routing -> TCP -> TLS -> HTTP chain from the handbook. Used by
# ScenarioMock for deterministic demo/test runs.
SCENARIOS: dict[str, dict[str, str]] = {
    "dns_failure": {
        "dns_resolution": "nxdomain",
        "dns_consistency": "resolvers_disagree",
        "tcp_443": "timeout",
        "tcp_80": "timeout",
        "tls_handshake": "not_attempted",
        "http_status": "not_attempted",
        "latency_profile": "unmeasurable",
        "packet_loss": "none",
        "path_reachability": "no_response",
        "path_change": "no_baseline",
        "external_vantage": "unavailable",
        "mtu_behaviour": "not_tested",
    },
    "auth_ns_down": {
        "dns_resolution": "servfail",
        "dns_consistency": "auth_differs_from_cache",
        "tcp_443": "timeout",
        "tcp_80": "timeout",
        "tls_handshake": "not_attempted",
        "http_status": "not_attempted",
        "latency_profile": "unmeasurable",
        "packet_loss": "none",
        "path_reachability": "no_response",
        "path_change": "no_baseline",
        "external_vantage": "target_down_externally",
        "mtu_behaviour": "not_tested",
    },
    "routing_blackhole": {
        "dns_resolution": "ok",
        "dns_consistency": "all_agree",
        "tcp_443": "timeout",
        "tcp_80": "timeout",
        "tls_handshake": "not_attempted",
        "http_status": "not_attempted",
        "latency_profile": "unmeasurable",
        "packet_loss": "total",
        "path_reachability": "stalls_midpath",
        "path_change": "unchanged",
        "external_vantage": "partial_by_region",
        "mtu_behaviour": "not_tested",
    },
    "path_change_degraded": {
        "dns_resolution": "ok",
        "dns_consistency": "all_agree",
        "tcp_443": "open",
        "tcp_80": "open",
        "tls_handshake": "ok",
        "http_status": "2xx",
        "latency_profile": "severe",
        "packet_loss": "low",
        "path_reachability": "complete",
        "path_change": "changed_correlated",
        "external_vantage": "partial_by_region",
        "mtu_behaviour": "not_tested",
    },
    "congestion_loss": {
        "dns_resolution": "ok",
        "dns_consistency": "all_agree",
        "tcp_443": "open",
        "tcp_80": "open",
        "tls_handshake": "ok",
        "http_status": "2xx",
        "latency_profile": "elevated",
        "packet_loss": "high",
        "path_reachability": "complete",
        "path_change": "unchanged",
        "external_vantage": "target_ok_externally",
        "mtu_behaviour": "not_tested",
    },
    "server_down": {
        "dns_resolution": "ok",
        "dns_consistency": "all_agree",
        "tcp_443": "refused",
        "tcp_80": "refused",
        "tls_handshake": "not_attempted",
        "http_status": "not_attempted",
        "latency_profile": "normal",
        "packet_loss": "none",
        "path_reachability": "complete",
        "path_change": "unchanged",
        "external_vantage": "target_down_externally",
        "mtu_behaviour": "not_tested",
    },
    "app_layer_error": {
        "dns_resolution": "ok",
        "dns_consistency": "all_agree",
        "tcp_443": "open",
        "tcp_80": "open",
        "tls_handshake": "ok",
        "http_status": "5xx",
        "latency_profile": "normal",
        "packet_loss": "none",
        "path_reachability": "complete",
        "path_change": "unchanged",
        "external_vantage": "target_ok_externally",
        "mtu_behaviour": "not_tested",
    },
    "tls_failure": {
        "dns_resolution": "ok",
        "dns_consistency": "all_agree",
        "tcp_443": "open",
        "tcp_80": "open",
        "tls_handshake": "expired_cert",
        "http_status": "not_attempted",
        "latency_profile": "normal",
        "packet_loss": "none",
        "path_reachability": "complete",
        "path_change": "unchanged",
        "external_vantage": "target_ok_externally",
        "mtu_behaviour": "not_tested",
    },
    "waf_or_rate_limited": {
        "dns_resolution": "ok",
        "dns_consistency": "all_agree",
        "tcp_443": "open",
        "tcp_80": "open",
        "tls_handshake": "ok",
        "http_status": "waf_block",
        "latency_profile": "normal",
        "packet_loss": "none",
        "path_reachability": "complete",
        "path_change": "unchanged",
        "external_vantage": "partial_by_region",
        "mtu_behaviour": "not_tested",
    },
    "local_vantage_bad": {
        "dns_resolution": "timeout",
        "dns_consistency": "resolvers_disagree",
        "tcp_443": "timeout",
        "tcp_80": "timeout",
        "tls_handshake": "not_attempted",
        "http_status": "not_attempted",
        "latency_profile": "unmeasurable",
        "packet_loss": "total",
        "path_reachability": "stalls_at_edge",
        "path_change": "no_baseline",
        "external_vantage": "target_ok_externally",
        "mtu_behaviour": "not_tested",
    },
    "mtu_blackhole": {
        "dns_resolution": "ok",
        "dns_consistency": "all_agree",
        "tcp_443": "open",
        "tcp_80": "open",
        "tls_handshake": "handshake_timeout",
        "http_status": "no_response",
        "latency_profile": "normal",
        "packet_loss": "none",
        "path_reachability": "complete",
        "path_change": "unchanged",
        "external_vantage": "partial_by_region",
        "mtu_behaviour": "large_packets_fail",
    },
    "client_local_issue": {
        "dns_resolution": "ok",
        "dns_consistency": "all_agree",
        "tcp_443": "open",
        "tcp_80": "open",
        "tls_handshake": "ok",
        "http_status": "2xx",
        "latency_profile": "normal",
        "packet_loss": "none",
        "path_reachability": "complete",
        "path_change": "unchanged",
        "external_vantage": "target_ok_externally",
        "mtu_behaviour": "normal",
    },
}
