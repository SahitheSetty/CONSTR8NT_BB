import socket
import time

from app.models import TCPResult

_TIMEOUT_S = 5.0

# Only these four symbols are valid tcp_443/tcp_80 observations
# (blackbox_engine.symbols.OBSERVATION_SPACE). Anything we can't cleanly
# classify (e.g. the host itself didn't resolve) comes back as
# status=None so the diagnosis engine treats it as unmeasured rather
# than guessing.


def collect_tcp(target: str, port: int) -> TCPResult:
    start = time.perf_counter()

    try:
        with socket.create_connection((target, port), timeout=_TIMEOUT_S):
            duration_ms = (time.perf_counter() - start) * 1000

            return TCPResult(
                status="open",
                durationMs=round(duration_ms, 2),
                error=None
            )

    except ConnectionRefusedError as e:
        duration_ms = (time.perf_counter() - start) * 1000

        return TCPResult(
            status="refused",
            durationMs=round(duration_ms, 2),
            error=str(e)
        )

    except ConnectionResetError as e:
        duration_ms = (time.perf_counter() - start) * 1000

        return TCPResult(
            status="reset",
            durationMs=round(duration_ms, 2),
            error=str(e)
        )

    except (socket.timeout, TimeoutError) as e:
        duration_ms = (time.perf_counter() - start) * 1000

        return TCPResult(
            status="timeout",
            durationMs=round(duration_ms, 2),
            error=str(e) or "Connection timed out"
        )

    except OSError as e:
        duration_ms = (time.perf_counter() - start) * 1000

        return TCPResult(
            status=None,
            durationMs=round(duration_ms, 2),
            error=str(e)
        )
