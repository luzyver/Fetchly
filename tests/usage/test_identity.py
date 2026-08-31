from django.test import RequestFactory

from usage.identity import build_identity, identity_from_request, normalize_ip


def test_identity_is_stable_and_hides_inputs(settings):
    settings.IDENTITY_HMAC_KEYS = ["test-secret"]
    identity = build_identity("browser-fp", "203.0.113.8")

    assert identity == build_identity("browser-fp", "203.0.113.8")
    assert "browser-fp" not in identity.fingerprint_id
    assert "203.0.113.8" not in identity.ip_id
    assert len(identity.owner_id) == 64


def test_ipv4_mapped_ipv6_is_normalized():
    assert normalize_ip("::ffff:203.0.113.8") == "203.0.113.8"


def test_untrusted_forwarded_address_is_ignored(settings):
    settings.IDENTITY_HMAC_KEYS = ["test-secret"]
    settings.TRUSTED_PROXY_NETWORKS = ["10.0.0.0/8"]
    request = RequestFactory().get(
        "/",
        REMOTE_ADDR="203.0.113.8",
        HTTP_X_FORWARDED_FOR="198.51.100.4",
    )

    identity = identity_from_request(request, "browser-fp")

    assert identity == build_identity("browser-fp", "203.0.113.8")


def test_trusted_proxy_uses_first_forwarded_address(settings):
    settings.IDENTITY_HMAC_KEYS = ["test-secret"]
    settings.TRUSTED_PROXY_NETWORKS = ["10.0.0.0/8"]
    request = RequestFactory().get(
        "/",
        REMOTE_ADDR="10.0.0.2",
        HTTP_X_FORWARDED_FOR="198.51.100.4, 10.0.0.1",
    )

    identity = identity_from_request(request, "browser-fp")

    assert identity == build_identity("browser-fp", "198.51.100.4")
