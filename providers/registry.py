from dataclasses import dataclass
from urllib.parse import urlsplit

from providers.contracts import Provider


@dataclass(frozen=True)
class ProviderRegistration:
    provider: Provider
    domains: tuple[str, ...]


def build_default_registry(client, session) -> tuple[ProviderRegistration, ...]:
    from providers.generic import GenericProvider
    from providers.instagram import InstagramProvider
    from providers.tiktok import TikTokProvider
    from providers.twitter import TwitterProvider
    from providers.youtube import YouTubeProvider

    return (
        ProviderRegistration(
            YouTubeProvider(client),
            ("youtube.com", "youtu.be", "youtube-nocookie.com"),
        ),
        ProviderRegistration(
            TikTokProvider(session),
            ("tiktok.com", "vm.tiktok.com", "vt.tiktok.com"),
        ),
        ProviderRegistration(TwitterProvider(client), ("twitter.com", "x.com")),
        ProviderRegistration(InstagramProvider(client), ("instagram.com",)),
        ProviderRegistration(GenericProvider(client), ()),
    )


def get_provider(
    url: str,
    registrations: tuple[ProviderRegistration, ...],
) -> Provider:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    fallback = None
    for registration in registrations:
        if not registration.domains:
            fallback = registration.provider
            continue
        if any(host == domain or host.endswith(f".{domain}") for domain in registration.domains):
            return registration.provider
    if fallback is None:
        raise LookupError(f"No provider registered for {host}")
    return fallback
