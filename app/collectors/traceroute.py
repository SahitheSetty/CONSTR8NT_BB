import ipaddress
import platform
import re
import subprocess

from app.models import Hop


def _extract_ip_and_hostname(data: str) -> tuple[str | None, str | None]:
    """Pull the hop's IP (v4 or v6) and, if present, its resolved hostname.

    tracert/traceroute render a resolved hop as `hostname [ip]` and an
    unresolved one as a bare address at the end of the line -- in either
    form the address itself is only ever IPv4- or IPv6-shaped, so validate
    candidates with `ipaddress` rather than an IPv4-only regex (which
    silently drops every hop when the trace runs over IPv6).
    """
    bracket_match = re.search(r"\[([0-9A-Fa-f:.]+)\]", data)
    if bracket_match:
        candidate = bracket_match.group(1)
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            return None, None

        hostname_match = re.search(
            r"([A-Za-z0-9][A-Za-z0-9.\-_]+)\s+\[" + re.escape(candidate) + r"\]",
            data,
        )
        return candidate, (hostname_match.group(1) if hostname_match else None)

    # No brackets: Windows puts the bare address last, Unix -n puts it
    # first (before the RTT samples) -- scan every token rather than
    # assume a position.
    for token in data.split():
        try:
            ipaddress.ip_address(token)
            return token, None
        except ValueError:
            continue

    return None, None


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

        # Extract IP address (v4 or v6) and hostname, if resolved
        ip, hostname = _extract_ip_and_hostname(data)

        if ip is None:
            continue

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

        # Extract IP (v4 or v6); -n mode never resolves hostnames
        ip, _hostname = _extract_ip_and_hostname(data)

        # No response
        if "*" in data and ip is None:

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

        if ip is None:
            continue

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
