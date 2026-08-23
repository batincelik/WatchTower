import httpx
import pytest

from watchtower.config import Settings
from watchtower.fetcher import FetchFailure, fetch_url
from watchtower.security import SSRFBlockedError


def settings() -> Settings:
    return Settings(
        watchtower_secret_key="x" * 32,
        watchtower_encryption_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        max_response_bytes=1024,
    )


async def resolver(host: str, port: int) -> list[str]:
    return ["93.184.216.34"] if host == "example.com" else ["127.0.0.1"]


async def test_redirect_to_private_is_never_requested() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/secret"})

    with pytest.raises(SSRFBlockedError):
        await fetch_url("https://example.com", settings(), resolver=resolver, transport=httpx.MockTransport(handler))
    assert requests == ["https://93.184.216.34"]


async def test_connection_is_pinned_to_validated_dns_answer() -> None:
    observed: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append((str(request.url), request.headers["host"]))
        return httpx.Response(200, content=b"ok")

    result = await fetch_url(
        "https://example.com/path",
        settings(),
        resolver=resolver,
        transport=httpx.MockTransport(handler),
    )
    assert observed == [("https://93.184.216.34/path", "example.com")]
    assert result.final_url == "https://example.com/path"


async def test_response_size_is_bounded() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 1025))
    with pytest.raises(FetchFailure, match="size limit") as caught:
        await fetch_url("https://example.com", settings(), resolver=resolver, transport=transport)
    assert caught.value.code == "CONTENT_TOO_LARGE"
