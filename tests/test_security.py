import pytest

from watchtower.security import SSRFBlockedError, validate_url


async def public_resolver(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://127.99.1.2",
        "http://localhost",
        "http://10.0.0.1",
        "http://172.16.0.1",
        "http://192.168.1.1",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]",
        "http://[fc00::1]",
        "http://[fe80::1]",
        "file:///etc/passwd",
        "ftp://example.com/file",
        "data:text/plain,hello",
        "javascript:alert(1)",
    ],
)
async def test_blocks_unsafe_targets(url: str) -> None:
    with pytest.raises(SSRFBlockedError):
        await validate_url(url, resolver=public_resolver)


async def test_blocks_hostname_resolving_to_private_ip() -> None:
    async def private_resolver(host: str, port: int) -> list[str]:
        return ["10.42.0.8"]

    with pytest.raises(SSRFBlockedError):
        await validate_url("https://public-looking.example", resolver=private_resolver)


async def test_blocks_if_any_dns_answer_is_private() -> None:
    async def mixed_resolver(host: str, port: int) -> list[str]:
        return ["93.184.216.34", "127.0.0.1"]

    with pytest.raises(SSRFBlockedError):
        await validate_url("https://example.com", resolver=mixed_resolver)


async def test_accepts_public_http_and_https() -> None:
    assert (await validate_url("https://example.com/path", resolver=public_resolver)).hostname == "example.com"
