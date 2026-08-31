import socket

import pytest

from providers.url_safety import UnsafeUrl, validate_public_url


def dns(*addresses: str):
    def resolve(host: str, port: int, type: socket.SocketKind):
        return [
            (socket.AF_INET6 if ":" in address else socket.AF_INET, type, 6, "", (address, port))
            for address in addresses
        ]

    return resolve


def test_public_https_url_is_normalized():
    result = validate_public_url(
        "https://EXAMPLE.com/video?q=1#fragment",
        resolver=dns("93.184.216.34"),
    )

    assert result.url == "https://example.com/video?q=1"
    assert result.host == "example.com"
    assert result.addresses == ("93.184.216.34",)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/video",
        "https://user:password@example.com/video",
        "https://example.com:8080/video",
        "https://localhost/video",
        "https://127.0.0.1/video",
        "https://[::1]/video",
    ],
)
def test_unsafe_url_shapes_are_rejected(url):
    with pytest.raises(UnsafeUrl):
        validate_public_url(url, resolver=dns("93.184.216.34"))


@pytest.mark.parametrize(
    "address",
    [
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "127.0.0.1",
        "::1",
        "fe80::1",
        "0.0.0.0",
        "224.0.0.1",
    ],
)
def test_any_nonpublic_dns_answer_rejects_the_url(address):
    with pytest.raises(UnsafeUrl):
        validate_public_url("https://example.com/video", resolver=dns("93.184.216.34", address))


def test_dns_failure_is_rejected():
    def failing_resolver(host: str, port: int, type: socket.SocketKind):
        raise socket.gaierror("not found")

    with pytest.raises(UnsafeUrl):
        validate_public_url("https://missing.example/video", resolver=failing_resolver)
