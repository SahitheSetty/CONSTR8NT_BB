def _normalize_hop(hop):
    if hasattr(hop, "model_dump"):
        return hop.model_dump()

    if hasattr(hop, "dict"):
        return hop.dict()

    return hop


def compare_paths(previous_data, current_data):

    previous_path = [
        _normalize_hop(hop)
        for hop in previous_data["path"]
    ]

    current_path = [
        _normalize_hop(hop)
        for hop in current_data["path"]
    ]

    previous_hops = {
        hop["hop"]
        for hop in previous_path
    }

    current_hops = {
        hop["hop"]
        for hop in current_path
    }

    changes = []
    anomalies = []

    added_hops = current_hops - previous_hops

    for hop_number in added_hops:
        changes.append({
            "type": "ADDED_HOP",
            "hop": hop_number
        })

    removed_hops = previous_hops - current_hops

    for hop_number in removed_hops:
        changes.append({
            "type": "REMOVED_HOP",
            "hop": hop_number
        })

    common_hops = current_hops & previous_hops

    for hop_number in common_hops:

        previous_hop = next(
            hop for hop in previous_path
            if hop["hop"] == hop_number
        )

        current_hop = next(
            hop for hop in current_path
            if hop["hop"] == hop_number
        )

        previous_ip = previous_hop.get("ip")
        current_ip = current_hop.get("ip")

        if (
            previous_ip is not None
            and current_ip is not None
            and previous_ip != current_ip
        ):
            changes.append({
                "type": "IP_CHANGED",
                "hop": hop_number,
                "previousIp": previous_ip,
                "currentIp": current_ip
            })

        previous_hostname = previous_hop.get("hostname")
        current_hostname = current_hop.get("hostname")

        if (
            previous_hostname is not None
            and current_hostname is not None
            and previous_hostname != current_hostname
        ):
            changes.append({
                "type": "HOSTNAME_CHANGED",
                "hop": hop_number,
                "previousHostname": previous_hostname,
                "currentHostname": current_hostname
            })

        previous_rtt = previous_hop.get("rttMs")
        current_rtt = current_hop.get("rttMs")

        if (
            previous_rtt is not None
            and current_rtt is not None
        ):
            rtt_delta = current_rtt - previous_rtt

            if rtt_delta >= 50:
                anomalies.append({
                    "hop": hop_number,
                    "type": "LATENCY_SPIKE",
                    "previousRttMs": previous_rtt,
                    "currentRttMs": current_rtt,
                    "rttDeltaMs": rtt_delta
                })

        previous_loss = previous_hop.get(
            "packetLossPercent"
        )

        current_loss = current_hop.get(
            "packetLossPercent"
        )

        if (
            previous_loss is not None
            and current_loss is not None
        ):
            loss_delta = current_loss - previous_loss

            if loss_delta >= 10:
                anomalies.append({
                    "hop": hop_number,
                    "type": "PACKET_LOSS_SPIKE",
                    "previousPacketLossPercent": previous_loss,
                    "currentPacketLossPercent": current_loss,
                    "packetLossDeltaPercent": loss_delta
                })

    result = {
        "investigationId": current_data.get("investigationId"),
        "target": current_data.get("target"),
        "pathChanged": len(changes) > 0,
        "changes": changes,
        "anomalies": anomalies
    }

    return result


if __name__ == "__main__":

    previous = {
        "target": "github.com",
        "timestamp": "2026-09-06T10:00:00Z",
        "investigationId": "old123",
        "path": [
            {
                "hop": 1,
                "ip": "192.168.1.1",
                "hostname": "router",
                "rttMs": 2,
                "packetLossPercent": 0,
                "error": None
            },
            {
                "hop": 2,
                "ip": "10.0.0.1",
                "hostname": "isp",
                "rttMs": 27,
                "packetLossPercent": 0,
                "error": None
            }
        ]
    }

    current = {
        "target": "github.com",
        "timestamp": "2026-09-06T10:30:00Z",
        "investigationId": "new456",
        "path": [
            {
                "hop": 1,
                "ip": "192.168.1.1",
                "hostname": "router",
                "rttMs": 3,
                "packetLossPercent": 0,
                "error": None
            },
            {
                "hop": 2,
                "ip": "20.0.0.1",
                "hostname": "isp",
                "rttMs": 184,
                "packetLossPercent": 14,
                "error": None
            },
            {
                "hop": 3,
                "ip": "20.30.40.50",
                "hostname": "new-hop",
                "rttMs": 30,
                "packetLossPercent": 0,
                "error": None
            }
        ]
    }

    result = compare_paths(previous, current)

    print(result)