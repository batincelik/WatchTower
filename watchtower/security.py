import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit


class SSRFBlockedError(ValueError):
    code = "SSRF_BLOCKED"


Resolver = Callable[[str, int], Awaitable[list[str]]]


@dataclass(frozen=True)
class ValidatedTarget:
    url: str
    hostname: str
    port: int
    addresses: tuple[str, ...]


def _blocked_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # is_global rejects loopback, RFC1918/ULA, link-local, multicast, reserved,
    # unspecified, documentation, and metadata/link-local space by default.
    return not address.is_global


async def system_resolver(hostname: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise OSError("DNS_FAILURE") from exc
    return sorted({str(info[4][0]) for info in infos})


async def validate_url(
    url: str,
    *,
    allow_private: bool = False,
    resolver: Resolver = system_resolver,
) -> ValidatedTarget:
    try:
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise SSRFBlockedError("Malformed target URL") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise SSRFBlockedError("Only http and https URLs are allowed")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise SSRFBlockedError("Target must have a hostname and no embedded credentials")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        raise SSRFBlockedError("Localhost targets are blocked")
    try:
        literal = ipaddress.ip_address(hostname)
        addresses = [str(literal)]
    except ValueError:
        addresses = await resolver(hostname, port)
    if not addresses:
        raise OSError("DNS_FAILURE")
    if not allow_private:
        for raw in addresses:
            try:
                address = ipaddress.ip_address(raw.split("%", 1)[0])
            except ValueError as exc:
                raise SSRFBlockedError("DNS returned an invalid address") from exc
            if _blocked_ip(address):
                raise SSRFBlockedError("Target resolves to a non-public network address")
    return ValidatedTarget(url=url, hostname=hostname, port=port, addresses=tuple(addresses))
