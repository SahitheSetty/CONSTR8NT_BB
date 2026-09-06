import platform
import re
import subprocess

from app.models import Hop


def collect_traceroute(target: str) -> list[Hop]:
    """
    Run traceroute/tracert and return structured hop information.
    """

    system = platform.system()

    if system == "Windows":
        command = [
            "tracert",
            "-h",
            "30",
            "-w",
            "1000",
            target
        ]
    else:
        command = [
            "traceroute",
            "-n",
            "-m",
            "30",
            "-w",
            "1",
            target
        ]

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            shell=False
        )

        if system == "Windows":
            return parse_windows_tracert(process.stdout)

        return parse_unix_traceroute(process.stdout)

    except subprocess.TimeoutExpired:
        return [
            Hop(
                hop=0,
                ip=None,
                hostname=None,
                rttMs=None,
                packetLossPercent=None,
                error="Traceroute timed out"
            )
        ]

    except FileNotFoundError:
        return [
            Hop(
                hop=0,
                ip=None,
                hostname=None,
                rttMs=None,
                packetLossPercent=None,
                error="Traceroute command not found"
            )
        ]

    except Exception as e:
        return [
            Hop(
                hop=0,
                ip=None,
                hostname=None,
                rttMs=None,
                packetLossPercent=None,
                error=f"Traceroute error: {str(e)}"
            )
        ]


def parse_windows_tracert(output: str) -> list[Hop]:

    hops = []

    for line in output.splitlines():

        line = line.strip()

        if not line:
            continue

        match = re.match(r"^(\d+)\s+(.*)$", line)

        if not match:
            continue

        hop_number = int(match.group(1))
        data = match.group(2)

        # Completely timed-out hop
        if "Request timed out" in data:

            hops.append(
                Hop(
                    hop=hop_number,
                    ip=None,
                    hostname=None,
                    rttMs=None,
                    packetLossPercent=100.0,
                    error="Request timed out"
                )
            )

            continue

        # Extract IP address
        ip_match = re.search(
            r"\b(\d{1,3}(?:\.\d{1,3}){3})\b",
            data
        )

        if not ip_match:
            continue

        ip = ip_match.group(1)

        # Extract hostname
        hostname = None

        hostname_match = re.search(
            r"([A-Za-z0-9][A-Za-z0-9.\-_]+)\s+\["
            + re.escape(ip)
            + r"\]",
            data
        )

        if hostname_match:
            hostname = hostname_match.group(1)

        # Extract RTT values
        rtt_values = re.findall(
            r"(?:<\s*)?(\d+(?:\.\d+)?)\s*ms",
            data
        )

        rtts = [
            float(value)
            for value in rtt_values
        ]

        successful_probes = len(rtts)

        # Calculate RTT and packet loss
        if successful_probes == 0:

            rtt_ms = None
            packet_loss = 100.0
            error = "No response"

        else:

            rtt_ms = round(
                sum(rtts) / len(rtts),
                2
            )

            packet_loss = round(
                ((3 - successful_probes) / 3) * 100,
                2
            )

            error = None

        hops.append(
            Hop(
                hop=hop_number,
                ip=ip,
                hostname=hostname,
                rttMs=rtt_ms,
                packetLossPercent=packet_loss,
                error=error
            )
        )

    return hops


def parse_unix_traceroute(output: str) -> list[Hop]:

    hops = []

    for line in output.splitlines():

        line = line.strip()

        if not line:
            continue

        match = re.match(
            r"^(\d+)\s+(.*)$",
            line
        )

        if not match:
            continue

        hop_number = int(match.group(1))
        data = match.group(2)

        # No response
        if "*" in data and not re.search(
            r"\d{1,3}(?:\.\d{1,3}){3}",
            data
        ):

            hops.append(
                Hop(
                    hop=hop_number,
                    ip=None,
                    hostname=None,
                    rttMs=None,
                    packetLossPercent=None,
                    error="No response"
                )
            )

            continue

        # Extract IP
        ip_match = re.search(
            r"\b(\d{1,3}(?:\.\d{1,3}){3})\b",
            data
        )

        if not ip_match:
            continue

        ip = ip_match.group(1)

        # Extract RTT values
        rtt_values = re.findall(
            r"(\d+(?:\.\d+)?)\s*ms",
            data
        )

        rtts = [
            float(value)
            for value in rtt_values
        ]

        successful_probes = len(rtts)

        if successful_probes == 0:

            rtt_ms = None
            packet_loss = None
            error = "No response"

        else:

            rtt_ms = round(
                sum(rtts) / len(rtts),
                2
            )

            packet_loss = round(
                ((3 - successful_probes) / 3) * 100,
                2
            )

            error = None

        hops.append(
            Hop(
                hop=hop_number,
                ip=ip,
                hostname=None,
                rttMs=rtt_ms,
                packetLossPercent=packet_loss,
                error=error
            )
        )

    return hops
