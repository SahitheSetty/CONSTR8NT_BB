import socket
import ssl
import time

from app.models import TLSResult

_TIMEOUT_S = 5.0

# Only classify into a specific OBSERVATION_SPACE["tls_handshake"] symbol
# when the verification failure text clearly says so. An unrecognised
# SSL error is reported as unmeasured (handshake=None) rather than
# forced into the nearest-looking bucket -- a wrong guess here would
# silently bias the diagnosis engine's posterior.


def collect_tls(target: str, port: int = 443) -> TLSResult:
    start = time.perf_counter()
    context = ssl.create_default_context()

    try:
        with socket.create_connection((target, port), timeout=_TIMEOUT_S) as sock:
            with context.wrap_socket(sock, server_hostname=target):
                duration_ms = (time.perf_counter() - start) * 1000

                return TLSResult(
                    handshake="ok",
                    durationMs=round(duration_ms, 2),
                    error=None
                )

    except ssl.SSLCertVerificationError as e:
        duration_ms = (time.perf_counter() - start) * 1000
        reason = (getattr(e, "verify_message", "") or str(e)).lower()

        if "expired" in reason:
            handshake = "expired_cert"
        elif "hostname mismatch" in reason or "doesn't match" in reason:
            handshake = "hostname_mismatch"
        elif "unable to get local issuer certificate" in reason or "certificate chain" in reason:
            handshake = "chain_incomplete"
        else:
            handshake = None

        return TLSResult(
            handshake=handshake,
            durationMs=round(duration_ms, 2),
            error=str(e)
        )

    except ssl.SSLError as e:
        duration_ms = (time.perf_counter() - start) * 1000

        return TLSResult(
            handshake=None,
            durationMs=round(duration_ms, 2),
            error=str(e)
        )

    except (socket.timeout, TimeoutError) as e:
        duration_ms = (time.perf_counter() - start) * 1000

        return TLSResult(
            handshake="handshake_timeout",
            durationMs=round(duration_ms, 2),
            error=str(e) or "TLS handshake timed out"
        )

    except OSError as e:
        duration_ms = (time.perf_counter() - start) * 1000

        return TLSResult(
            handshake=None,
            durationMs=round(duration_ms, 2),
            error=str(e)
        )
