from dataclasses import dataclass

import pytest

from providers.registry import ProviderRegistration, get_provider


@dataclass(frozen=True)
class NamedProvider:
    key: str


REGISTRY = (
    ProviderRegistration(NamedProvider("youtube"), ("youtube.com", "youtu.be")),
    ProviderRegistration(NamedProvider("generic"), ()),
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://youtube.com/watch?v=1", "youtube"),
        ("https://www.youtube.com/watch?v=1", "youtube"),
        ("https://youtu.be/abc", "youtube"),
        ("https://notyoutube.com/watch?v=1", "generic"),
    ],
)
def test_registry_matches_exact_hosts_and_subdomains(url, expected):
    assert get_provider(url, REGISTRY).key == expected


def test_registry_requires_generic_fallback():
    with pytest.raises(LookupError):
        get_provider("https://example.com/video", REGISTRY[:-1])
