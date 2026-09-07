import copy
import json
from pathlib import Path

import pytest

from blackbox_engine.adapter import to_observations

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def p1_raw() -> dict:
    return json.loads((FIXTURES / "p1_sample.json").read_text())


@pytest.fixture
def p2_analysis() -> dict:
    return json.loads((FIXTURES / "p2_sample.json").read_text())


def test_complete_input_produces_expected_symbols(p1_raw, p2_analysis):
    observations = to_observations(p1_raw, p2_analysis)

    expected = {
        "dns_resolution": "ok",
        "tcp_443": "open",
        "tcp_80": "open",
        "tls_handshake": "ok",
        "http_status": "2xx",
        "packet_loss": "none",
        "latency_profile": "normal",
        "path_change": "unchanged",
        "path_reachability": "complete",
    }
    # dns_consistency/external_vantage/mtu_behaviour have no live mapping yet;
    # to_observations() still returns them, always unmeasured, so every probe
    # in OBSERVATION_SPACE has an entry rather than silently missing one.
    always_unmeasured = {"dns_consistency", "external_vantage", "mtu_behaviour"}
    assert set(observations) == set(expected) | always_unmeasured
    for probe_id, symbol in expected.items():
        obs = observations[probe_id]
        assert obs.symbol == symbol
        assert obs.measured is True
    for probe_id in always_unmeasured:
        obs = observations[probe_id]
        assert obs.symbol is None
        assert obs.measured is False


def test_every_returned_observation_passes_validate(p1_raw, p2_analysis):
    observations = to_observations(p1_raw, p2_analysis)
    for obs in observations.values():
        obs.validate()


def test_null_packet_loss_produces_measured_false_not_none(p1_raw, p2_analysis):
    p1_raw["hops"][-1]["packetLossPercent"] = None

    observations = to_observations(p1_raw, p2_analysis)
    packet_loss = observations["packet_loss"]

    assert packet_loss.measured is False
    assert packet_loss.symbol is None
    packet_loss.validate()


def test_zero_packet_loss_produces_none_symbol(p1_raw, p2_analysis):
    p1_raw["hops"][-1]["packetLossPercent"] = 0

    observations = to_observations(p1_raw, p2_analysis)
    packet_loss = observations["packet_loss"]

    assert packet_loss.measured is True
    assert packet_loss.symbol == "none"
    packet_loss.validate()


def test_missing_person2_analysis_produces_no_baseline_path_change(p1_raw):
    observations = to_observations(p1_raw, None)
    path_change = observations["path_change"]

    assert path_change.symbol == "no_baseline"
    assert path_change.measured is True
    path_change.validate()


def test_dns_free_text_error_never_guesses_a_symbol(p1_raw, p2_analysis):
    p1_raw["dns"]["resolved"] = False
    p1_raw["dns"]["outcome"] = None
    p1_raw["dns"]["error"] = "connection refused by resolver 8.8.8.8"

    observations = to_observations(p1_raw, p2_analysis)
    dns = observations["dns_resolution"]

    assert dns.measured is False
    assert dns.symbol is None
    assert "connection refused by resolver" in dns.note
    dns.validate()


def test_dns_structured_outcome_is_used_when_present(p1_raw, p2_analysis):
    p1_raw["dns"]["resolved"] = False
    p1_raw["dns"]["outcome"] = "nxdomain"

    observations = to_observations(p1_raw, p2_analysis)
    dns = observations["dns_resolution"]

    assert dns.measured is True
    assert dns.symbol == "nxdomain"
    dns.validate()


def test_tcp_443_falls_back_to_unmeasured_when_only_http_reachable_present(p1_raw, p2_analysis):
    del p1_raw["tcp"]

    observations = to_observations(p1_raw, p2_analysis)
    tcp_443 = observations["tcp_443"]

    assert tcp_443.measured is False
    assert tcp_443.symbol is None
    assert "boolean" in tcp_443.note
    tcp_443.validate()


def test_missing_dns_block_is_measured_false(p1_raw, p2_analysis):
    del p1_raw["dns"]

    observations = to_observations(p1_raw, p2_analysis)
    dns = observations["dns_resolution"]

    assert dns.measured is False
    assert dns.symbol is None
    dns.validate()


def test_path_change_correlated_vs_uncorrelated(p1_raw, p2_analysis):
    p2_analysis["pathChanged"] = True
    p2_analysis["timingCorrelated"] = True
    correlated = to_observations(p1_raw, p2_analysis)["path_change"]
    assert correlated.symbol == "changed_correlated"

    p2_analysis["timingCorrelated"] = False
    uncorrelated = to_observations(p1_raw, copy.deepcopy(p2_analysis))["path_change"]
    assert uncorrelated.symbol == "changed_uncorrelated"


def test_http_403_and_429_map_to_waf_block(p1_raw, p2_analysis):
    for code in (403, 429):
        p1_raw["http"]["status"] = code
        observations = to_observations(p1_raw, p2_analysis)
        assert observations["http_status"].symbol == "waf_block"
