import pytest

from app.models import DNSResult, HTTPResult, Hop, InvestigationResult, TCPResult, TLSResult
from app.pipeline import LiveProbeRunner, build_p2_for_adapter, normalize_for_adapter


def _make_result(*, tcp_status="open", tls_handshake="ok", packet_loss=0.0, rtt=24.7):
    return InvestigationResult(
        target="example.com",
        timestamp="2026-09-06T10:00:00Z",
        investigationId="abc123",
        dns=DNSResult(resolved=True, addresses=["93.184.216.34"], responseTimeMs=42.1, error=None),
        http=HTTPResult(reachable=True, status=200, responseTimeMs=120.7, error=None),
        tcp443=TCPResult(status=tcp_status, durationMs=15.2, error=None),
        tcp80=TCPResult(status=tcp_status, durationMs=10.4, error=None),
        tls=TLSResult(handshake=tls_handshake, durationMs=55.3, error=None),
        path=[
            Hop(hop=1, ip="10.0.0.1", hostname=None, rttMs=2.1, packetLossPercent=0, error=None),
            Hop(hop=2, ip="93.184.216.34", hostname=None, rttMs=rtt, packetLossPercent=packet_loss, error=None),
        ],
        status="completed",
        errors=[],
    )


def test_normalize_for_adapter_passes_path_through_in_person1s_own_field_names():
    result = _make_result()

    raw = normalize_for_adapter(result)

    assert raw["path"][0]["rttMs"] == 2.1
    assert raw["path"][1]["rttMs"] == 24.7
    assert raw["tcp"]["443"]["status"] == "open"
    assert raw["tls"]["handshake"] == "ok"


def test_normalize_for_adapter_omits_tcp_tls_blocks_when_uncollected():
    result = _make_result(tcp_status=None, tls_handshake=None)

    raw = normalize_for_adapter(result)

    assert "tcp" not in raw
    assert "tls" not in raw


def test_build_p2_for_adapter_no_baseline():
    current = _make_result()

    p2 = build_p2_for_adapter(None, current, None)

    assert p2 == {"baselineAvailable": False}


def test_build_p2_for_adapter_computes_rtt_delta():
    baseline = _make_result(rtt=25.0)
    current = _make_result(rtt=40.0)

    p2 = build_p2_for_adapter(baseline, current, {"pathChanged": False})

    assert p2["baselineAvailable"] is True
    assert p2["pathChanged"] is False
    assert p2["rtt"]["delta_ms"] == pytest.approx(15.0)


@pytest.mark.asyncio
async def test_live_probe_runner_maps_collected_probes():
    result = _make_result()
    raw = normalize_for_adapter(result)
    runner = LiveProbeRunner(raw, {"baselineAvailable": False})

    observation = await runner("tcp_443", "example.com")

    assert observation.measured is True
    assert observation.symbol == "open"


@pytest.mark.asyncio
async def test_live_probe_runner_reports_unmapped_probes_as_unmeasured():
    result = _make_result()
    raw = normalize_for_adapter(result)
    runner = LiveProbeRunner(raw, {"baselineAvailable": False})

    observation = await runner("external_vantage", "example.com")

    assert observation.measured is False
    assert observation.symbol is None
    observation.validate()


@pytest.mark.asyncio
async def test_live_probe_runner_derives_packet_loss_from_persons1s_path_field():
    result = _make_result(packet_loss=0.0)
    raw = normalize_for_adapter(result)
    runner = LiveProbeRunner(raw, {"baselineAvailable": False})

    observation = await runner("packet_loss", "example.com")

    assert observation.measured is True
    assert observation.symbol == "none"


@pytest.mark.asyncio
async def test_live_probe_runner_derives_latency_profile_from_persons1s_path_field():
    result = _make_result(rtt=300.0)
    raw = normalize_for_adapter(result)
    runner = LiveProbeRunner(raw, {"baselineAvailable": False})

    observation = await runner("latency_profile", "example.com")

    assert observation.measured is True
    assert observation.symbol == "severe"
