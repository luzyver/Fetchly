import hashlib
import hmac
import ipaddress
from dataclasses import dataclass

from django.conf import settings
from django.http import HttpRequest


@dataclass(frozen=True)
class VisitorIdentity:
    fingerprint_id: str
    ip_id: str
    owner_id: str
    key_version: int


def normalize_ip(value: str) -> str:
    address = ipaddress.ip_address(value)
    if address.version == 6 and address.ipv4_mapped:
        return str(address.ipv4_mapped)
    return address.compressed


def _digest(secret: str, namespace: str, value: str) -> str:
    message = f"{namespace}:{value}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def build_identity(fingerprint: str, ip: str) -> VisitorIdentity:
    if not fingerprint.strip():
        raise ValueError("Fingerprint is required")
    normalized_ip = normalize_ip(ip)
    secret = settings.IDENTITY_HMAC_KEYS[0]
    return VisitorIdentity(
        fingerprint_id=_digest(secret, "fingerprint", fingerprint.strip()),
        ip_id=_digest(secret, "ip", normalized_ip),
        owner_id=_digest(secret, "owner", f"{fingerprint.strip()}:{normalized_ip}"),
        key_version=0,
    )


def _client_ip(request: HttpRequest) -> str:
    remote = normalize_ip(request.META.get("REMOTE_ADDR", ""))
    address = ipaddress.ip_address(remote)
    trusted = any(
        address in ipaddress.ip_network(network) for network in settings.TRUSTED_PROXY_NETWORKS
    )
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if trusted and forwarded:
        return normalize_ip(forwarded.split(",", 1)[0].strip())
    return remote


def identity_from_request(request: HttpRequest, fingerprint: str) -> VisitorIdentity:
    return build_identity(fingerprint, _client_ip(request))
