import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


class UnsafeUrl(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedUrl:
    url: str
    host: str
    addresses: tuple[str, ...]


Resolver = Callable[..., list[tuple]]


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_unspecified,
        )
    )


def _resolve(host: str, port: int, resolver: Resolver) -> tuple[str, ...]:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        try:
            answers = resolver(host, port, type=socket.SOCK_STREAM)
        except OSError as error:
            raise UnsafeUrl("Hostname could not be resolved") from error
        addresses = tuple(dict.fromkeys(answer[4][0] for answer in answers))
    else:
        addresses = (literal.compressed,)

    if not addresses or any(not _is_public(address) for address in addresses):
        raise UnsafeUrl("URL resolves to a non-public address")
    return addresses


def validate_public_url(
    url: str,
    resolver: Resolver = socket.getaddrinfo,
) -> ValidatedUrl:
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except ValueError as error:
        raise UnsafeUrl("Malformed URL") from error

    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrl("Only HTTP and HTTPS URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrl("Credentials are not allowed in URLs")
    if not parsed.hostname:
        raise UnsafeUrl("URL hostname is required")

    default_port = 443 if parsed.scheme == "https" else 80
    if port is not None and port != default_port:
        raise UnsafeUrl("URL port is not allowed")

    host = parsed.hostname.lower().rstrip(".").encode("idna").decode("ascii")
    if host == "localhost" or host.endswith(".localhost"):
        raise UnsafeUrl("Localhost is not allowed")

    addresses = _resolve(host, default_port, resolver)
    netloc = f"[{host}]" if ":" in host else host
    normalized = urlunsplit(
        (
            parsed.scheme,
            netloc,
            parsed.path or "/",
            parsed.query,
            "",
        )
    )
    return ValidatedUrl(normalized, host, addresses)
