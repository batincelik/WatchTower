from dataclasses import dataclass
from time import monotonic
from urllib.parse import urljoin

import httpx

from watchtower.config import Settings
from watchtower.security import Resolver, system_resolver, validate_url


class FetchFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FetchResult:
    final_url: str
    status_code: int
    headers: dict[str, str]
    body: bytes
    duration_ms: int


async def fetch_url(
    url: str,
    settings: Settings,
    *,
    resolver: Resolver = system_resolver,
    transport: httpx.AsyncBaseTransport | None = None,
    max_redirects: int = 10,
) -> FetchResult:
    started = monotonic()
    current = url
    visited: set[str] = set()
    timeout = httpx.Timeout(settings.default_check_timeout)
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=timeout,
            transport=transport,
            headers={"User-Agent": "Watchtower/0.1 (+self-hosted change monitor)"},
        ) as client:
            for _ in range(max_redirects + 1):
                target = await validate_url(
                    current, allow_private=settings.ssrf_allow_private_networks, resolver=resolver
                )
                if current in visited:
                    raise FetchFailure("TOO_MANY_REDIRECTS", "Redirect loop detected")
                visited.add(current)
                logical_url = httpx.URL(current)
                pinned_url = logical_url.copy_with(host=target.addresses[0])
                default_port = 443 if logical_url.scheme == "https" else 80
                host_header = target.hostname
                if target.port != default_port:
                    host_header = f"{host_header}:{target.port}"
                async with client.stream(
                    "GET",
                    pinned_url,
                    headers={"Host": host_header},
                    extensions={"sni_hostname": target.hostname.encode("idna")},
                ) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchFailure("INVALID_REDIRECT", "Redirect has no Location header")
                        destination = urljoin(current, location)
                        # Validate before issuing the next network request.
                        await validate_url(
                            destination, allow_private=settings.ssrf_allow_private_networks, resolver=resolver
                        )
                        current = destination
                        continue
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > settings.max_response_bytes:
                            raise FetchFailure("CONTENT_TOO_LARGE", "Response exceeds configured size limit")
                    return FetchResult(
                        final_url=current,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        body=bytes(body),
                        duration_ms=int((monotonic() - started) * 1000),
                    )
            raise FetchFailure("TOO_MANY_REDIRECTS", "Redirect limit exceeded")
    except httpx.TimeoutException as exc:
        raise FetchFailure("FETCH_TIMEOUT", "Target timed out") from exc
    except httpx.ConnectError as exc:
        raise FetchFailure("CONNECTION_FAILED", "Could not connect to target") from exc
