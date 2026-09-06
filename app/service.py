import uuid
from datetime import datetime, timezone

from app.collectors.dns import collect_dns
from app.collectors.http import collect_http
from app.collectors.traceroute import collect_traceroute
from app.models import InvestigationResult


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
        path=path,
        status=status,
        errors=errors
    )