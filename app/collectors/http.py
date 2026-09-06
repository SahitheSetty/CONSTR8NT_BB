import time

import httpx

from app.models import HTTPResult


def collect_http(target: str) -> HTTPResult:
    if not target.startswith(("http://", "https://")):
        url = f"https://{target}"
    else:
        url = target

    start = time.perf_counter()

    try:
        with httpx.Client(
            timeout=10.0,
            follow_redirects=True
        ) as client:
            response = client.get(url)

        response_time = (time.perf_counter() - start) * 1000

        return HTTPResult(
            reachable=True,
            status=response.status_code,
            responseTimeMs=round(response_time, 2),
            error=None
        )

    except httpx.RequestError as e:
        response_time = (time.perf_counter() - start) * 1000

        return HTTPResult(
            reachable=False,
            status=None,
            responseTimeMs=round(response_time, 2),
            error=str(e)
        )

    except Exception as e:
        response_time = (time.perf_counter() - start) * 1000

        return HTTPResult(
            reachable=False,
            status=None,
            responseTimeMs=round(response_time, 2),
            error=str(e)
        )