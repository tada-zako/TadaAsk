import pytest

from app.core.exceptions import VisitorRateLimitError
from app.core.rate_limit import VisitorRateLimiter


def make_limiter(*, enabled: bool = True, requests: int = 2, streams: int = 1) -> VisitorRateLimiter:
    return VisitorRateLimiter(
        enabled=enabled,
        ip_project_per_minute=requests,
        ip_project_per_hour=requests,
        ip_per_minute=requests,
        project_per_minute=requests,
        stream_per_ip=streams,
        stream_per_project=streams,
    )


@pytest.mark.asyncio
async def test_disabled_rate_limiter_always_allows_requests_and_streams() -> None:
    limiter = make_limiter(enabled=False, requests=1, streams=1)

    await limiter.check_request(ip="127.0.0.1", project_uid="project")
    await limiter.check_request(ip="127.0.0.1", project_uid="project")
    lease = await limiter.acquire_stream(ip="127.0.0.1", project_uid="project")
    await limiter.acquire_stream(ip="127.0.0.1", project_uid="project")
    await limiter.release_stream(lease)


@pytest.mark.asyncio
async def test_request_window_rejects_requests_after_limit() -> None:
    limiter = make_limiter(requests=2)

    await limiter.check_request(ip="127.0.0.1", project_uid="project")
    await limiter.check_request(ip="127.0.0.1", project_uid="project")

    with pytest.raises(VisitorRateLimitError) as exc_info:
        await limiter.check_request(ip="127.0.0.1", project_uid="project")

    assert exc_info.value.retry_after_seconds >= 1


@pytest.mark.asyncio
async def test_stream_lease_enforces_limit_and_release_allows_reacquisition() -> None:
    limiter = make_limiter(streams=1)
    lease = await limiter.acquire_stream(ip="127.0.0.1", project_uid="project")

    with pytest.raises(VisitorRateLimitError):
        await limiter.acquire_stream(ip="127.0.0.1", project_uid="project")

    await limiter.release_stream(lease)
    replacement = await limiter.acquire_stream(ip="127.0.0.1", project_uid="project")

    assert replacement.ip == "127.0.0.1"
