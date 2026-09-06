from app.collectors.traceroute import (
    parse_windows_tracert
)


def test_normal_hop():
    output = """
  1    12 ms    18 ms    11 ms  172.18.224.1
"""

    hops = parse_windows_tracert(output)

    assert len(hops) == 1
    assert hops[0].hop == 1
    assert hops[0].ip == "172.18.224.1"
    assert hops[0].rttMs == 13.67
    assert hops[0].packetLossPercent == 0.0
    assert hops[0].error is None


def test_timeout_hop():
    output = """
  6     *        *        *     Request timed out.
"""

    hops = parse_windows_tracert(output)

    assert len(hops) == 1
    assert hops[0].hop == 6
    assert hops[0].ip is None
    assert hops[0].rttMs is None
    assert hops[0].packetLossPercent == 100.0
    assert hops[0].error == "Request timed out"


def test_partial_packet_loss():
    output = """
 12    38 ms     *       40 ms  104.44.11.186
"""

    hops = parse_windows_tracert(output)

    assert len(hops) == 1
    assert hops[0].hop == 12
    assert hops[0].ip == "104.44.11.186"
    assert hops[0].rttMs == 39.0
    assert hops[0].packetLossPercent == 33.33
    assert hops[0].error is None


def test_hostname_and_ip():
    output = """
 17    51 ms   110 ms   288 ms  pu-in-f102.1e100.net [142.250.146.102]
"""

    hops = parse_windows_tracert(output)

    assert len(hops) == 1
    assert hops[0].hop == 17
    assert hops[0].ip == "142.250.146.102"
    assert hops[0].hostname == "pu-in-f102.1e100.net"
    assert hops[0].rttMs == 149.67
    assert hops[0].packetLossPercent == 0.0 