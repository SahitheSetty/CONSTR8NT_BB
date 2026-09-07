import uuid
from datetime import datetime, timezone

from app.collectors.dns import collect_dns
from app.collectors.http import collect_http
from app.collectors.tcp import collect_tcp
from app.collectors.tls import collect_tls
from app.collectors.traceroute import collect_traceroute
from app.models import InvestigationResult, TLSResult


def investigate_target(target: str) -> InvestigationResult:
    """
    Run all Person 1 network data collectors and combine
    their results into the agreed raw-evidence format.

    Person 1 responsibility:
        OBSERVE -> MEASURE -> RETURN RAW EVIDENCE

    This function does NOT perform:
        - anomaly detection
        - path comparison
        - hypothesis generation
        - root-cause diagnosis
    """

    investigation_id = str(uuid.uuid4())

    timestamp = datetime.now(timezone.utc).isoformat()

    errors = []

    # ---------------------------------------------------------
    # DNS COLLECTION
    # ---------------------------------------------------------

    try:
        dns_result = collect_dns(target)

        if dns_result.error:
            errors.append(
                f"DNS: {dns_result.error}"
            )

    except Exception as e:
        from app.models import DNSResult

        dns_result = DNSResult(
            resolved=False,
            addresses=[],
            responseTimeMs=None,
            error=str(e)
        )

        errors.append(
            f"DNS collector error: {str(e)}"
        )

    # ---------------------------------------------------------
    # HTTP COLLECTION
    # ---------------------------------------------------------

    try:
        http_result = collect_http(target)

        if http_result.error:
            errors.append(
                f"HTTP: {http_result.error}"
            )

    except Exception as e:
        from app.models import HTTPResult

        http_result = HTTPResult(
            reachable=False,
            status=None,
            responseTimeMs=None,
            error=str(e)
        )

        errors.append(
            f"HTTP collector error: {str(e)}"
        )

    # ---------------------------------------------------------
    # TCP COLLECTION
    # ---------------------------------------------------------

    try:
        tcp443_result = collect_tcp(target, 443)

        if tcp443_result.status is None and tcp443_result.error:
            errors.append(
                f"TCP 443: {tcp443_result.error}"
            )

    except Exception as e:
        from app.models import TCPResult

        tcp443_result = TCPResult(status=None, durationMs=None, error=str(e))

        errors.append(
            f"TCP 443 collector error: {str(e)}"
        )

    try:
        tcp80_result = collect_tcp(target, 80)

        if tcp80_result.status is None and tcp80_result.error:
            errors.append(
                f"TCP 80: {tcp80_result.error}"
            )

    except Exception as e:
        from app.models import TCPResult

        tcp80_result = TCPResult(status=None, durationMs=None, error=str(e))

        errors.append(
            f"TCP 80 collector error: {str(e)}"
        )

    # ---------------------------------------------------------
    # TLS COLLECTION
    #
    # Only meaningful once TCP/443 is known open -- otherwise there is
    # nothing to shake hands with, so we record "not_attempted" rather
    # than trying (and misreporting a TCP-layer failure as a TLS one).
    # ---------------------------------------------------------

    if tcp443_result.status == "open":
        try:
            tls_result = collect_tls(target)

            if tls_result.handshake is None and tls_result.error:
                errors.append(
                    f"TLS: {tls_result.error}"
                )

        except Exception as e:
            tls_result = TLSResult(handshake=None, durationMs=None, error=str(e))

            errors.append(
                f"TLS collector error: {str(e)}"
            )
    else:
        tls_result = TLSResult(handshake="not_attempted", durationMs=None, error=None)

    # ---------------------------------------------------------
    # TRACEROUTE COLLECTION
    # ---------------------------------------------------------

    try:
        path = collect_traceroute(target)

        # Our temporary traceroute error representation
        # uses hop=0. Do not expose that as a real network hop.
        if path and path[0].hop == 0:
            traceroute_error = path[0].error

            if traceroute_error:
                errors.append(
                    f"Traceroute: {traceroute_error}"
                )

            path = []

    except Exception as e:

        path = []

        errors.append(
            f"Traceroute collector error: {str(e)}"
        )

    # ---------------------------------------------------------
    # FINAL STATUS
    # ---------------------------------------------------------

    if dns_result.resolved or http_result.reachable or path:
        status = "completed"
    else:
        status = "failed"

    # ---------------------------------------------------------
    # COMBINE RAW EVIDENCE
    # ---------------------------------------------------------

    return InvestigationResult(
        target=target,
        timestamp=timestamp,
        investigationId=investigation_id,
        dns=dns_result,
        http=http_result,
        tcp443=tcp443_result,
        tcp80=tcp80_result,
        tls=tls_result,
        path=path,
        status=status,
        errors=errors
    )