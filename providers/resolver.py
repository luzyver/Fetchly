import atexit
import html
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from providers.contracts import ResolvedMedia
from providers.url_safety import UnsafeUrl, ValidatedUrl, validate_public_url

MEDIA_CONTENT_TYPES = (
    "application/mpegurl",
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
    "audio/mpegurl",
    "video/",
)
MEDIA_URL_PATTERN = re.compile(
    r"https?://[^\s\"'<>]+?\.(?:m3u8|mp4|webm|mkv|mov)(?:\?[^\s\"'<>]*)?",
    re.IGNORECASE,
)
BLOCKED_RESOURCE_TYPES = frozenset({"font", "image"})
_browser_runtime = None
_browser = None


@dataclass(frozen=True)
class ResolverLimits:
    max_pages: int = 8
    max_iframes: int = 12
    max_captured_urls: int = 100
    navigation_seconds: int = 30
    overall_seconds: int = 45


def resolve_media(
    url: str,
    limits: ResolverLimits,
    *,
    browser=None,
    validator: Callable[[str], ValidatedUrl] = validate_public_url,
) -> ResolvedMedia | None:
    initial_url = validator(url).url
    deadline = time.monotonic() + limits.overall_seconds
    candidates: list[str] = []
    active_browser = browser or _get_worker_browser()
    context = active_browser.new_context(
        locale="id-ID",
        viewport={"width": 1280, "height": 720},
    )

    def capture(response) -> None:
        if len(candidates) >= limits.max_captured_urls or not _is_media_response(response):
            return
        try:
            candidate = validator(response.url).url
        except UnsafeUrl:
            return
        if candidate not in candidates:
            candidates.append(candidate)

    try:
        context.route("**/*", lambda route: _route_safely(route, validator))
        context.on("response", capture)
        page = context.new_page()
        page.goto(
            initial_url,
            wait_until="domcontentloaded",
            timeout=limits.navigation_seconds * 1000,
        )
        validator(page.url)

        for candidate in candidates:
            return _result(context, page, candidate)

        documents = [page.content()]
        for frame in page.frames[1 : limits.max_iframes + 1]:
            if time.monotonic() >= deadline:
                break
            try:
                validator(frame.url)
                documents.append(frame.content())
            except UnsafeUrl:
                continue

        for document in documents[: limits.max_pages]:
            if time.monotonic() >= deadline:
                break
            for raw_candidate in _media_urls(document):
                try:
                    candidate = validator(raw_candidate).url
                except UnsafeUrl:
                    continue
                return _result(context, page, candidate)
        return None
    finally:
        context.close()


def _is_media_response(response) -> bool:
    content_type = (response.header_value("content-type") or "").lower()
    return any(media_type in content_type for media_type in MEDIA_CONTENT_TYPES)


def _media_urls(document: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(html.unescape(match) for match in MEDIA_URL_PATTERN.findall(document))
    )


def _route_safely(route, validator: Callable[[str], ValidatedUrl]) -> None:
    if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
        route.abort()
        return
    try:
        validator(route.request.url)
    except UnsafeUrl:
        route.abort()
    else:
        route.continue_()


def _result(context, page, url: str) -> ResolvedMedia:
    cookies = "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in context.cookies())
    return ResolvedMedia(
        url=url,
        referer=page.url,
        cookies=cookies or None,
        user_agent=page.evaluate("navigator.userAgent"),
    )


def _get_worker_browser():
    global _browser, _browser_runtime
    if _browser is None:
        from playwright.sync_api import sync_playwright

        _browser_runtime = sync_playwright().start()
        _browser = _browser_runtime.chromium.launch(headless=True)
    return _browser


def _close_worker_browser() -> None:
    global _browser, _browser_runtime
    if _browser is not None:
        _browser.close()
        _browser = None
    if _browser_runtime is not None:
        _browser_runtime.stop()
        _browser_runtime = None


atexit.register(_close_worker_browser)
