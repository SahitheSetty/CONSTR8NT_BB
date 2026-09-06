import socket
import time

from app.models import DNSResult


def collect_dns(target: str) -> DNSResult:
    start = time.perf_counter()

    try:
        results = socket.getaddrinfo(
            target,
            None,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM
        )

        addresses = sorted({
            result[4][0]
            for result in results
            if result[4]
        })

        response_time = (time.perf_counter() - start) * 1000

        return DNSResult(
            resolved=True,
            addresses=addresses,
            responseTimeMs=round(response_time, 2),
            error=None
        )

    except socket.gaierror as e:
        response_time = (time.perf_counter() - start) * 1000

        return DNSResult(
            resolved=False,
            addresses=[],
            responseTimeMs=round(response_time, 2),
            error=str(e)
        )

    except Exception as e:
        response_time = (time.perf_counter() - start) * 1000

        return DNSResult(
            resolved=False,
            addresses=[],
            responseTimeMs=round(response_time, 2),
            error=str(e)
        )
    