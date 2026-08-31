from dataclasses import dataclass

from providers.resolver import ResolverLimits, resolve_media
from providers.url_safety import UnsafeUrl, ValidatedUrl


@dataclass
class FakeFrame:
    url: str
    html: str = ""

    def content(self) -> str:
        return self.html


class FakeResponse:
    def __init__(self, url: str, content_type: str):
        self.url = url
        self.content_type = content_type

    def header_value(self, name: str) -> str | None:
        return self.content_type if name.lower() == "content-type" else None


class FakePage:
    def __init__(self, context, html="", frames=(), responses=()):
        self.context = context
        self.html = html
        self.frames = [FakeFrame("about:blank"), *frames]
        self.responses = responses
        self.url = "about:blank"

    def goto(self, url: str, **kwargs) -> None:
        self.url = url
        self.frames[0].url = url
        for response in self.responses:
            self.context.emit("response", response)

    def content(self) -> str:
        return self.html

    def evaluate(self, expression: str) -> str:
        return "Fake Browser"


class FakeContext:
    def __init__(self, html="", frames=(), responses=()):
        self.callbacks = {}
        self.closed = False
        self.page = FakePage(self, html, frames, responses)

    def route(self, pattern: str, callback) -> None:
        self.callbacks["route"] = callback

    def on(self, event: str, callback) -> None:
        self.callbacks[event] = callback

    def emit(self, event: str, value) -> None:
        self.callbacks[event](value)

    def new_page(self) -> FakePage:
        return self.page

    def cookies(self) -> list[dict[str, str]]:
        return [{"name": "session", "value": "secret"}]

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, context: FakeContext):
        self.context = context

    def new_context(self, **kwargs) -> FakeContext:
        return self.context


class FakeRequest:
    def __init__(self, url: str, resource_type: str):
        self.url = url
        self.resource_type = resource_type


class FakeRoute:
    def __init__(self, url: str, resource_type: str):
        self.request = FakeRequest(url, resource_type)
        self.action = None

    def abort(self) -> None:
        self.action = "abort"

    def continue_(self) -> None:
        self.action = "continue"


def validator(url: str) -> ValidatedUrl:
    if "127.0.0.1" in url:
        raise UnsafeUrl("private")
    return ValidatedUrl(url, "public.example", ("93.184.216.34",))


def test_response_media_is_returned_and_context_is_closed():
    context = FakeContext(
        responses=[FakeResponse("https://cdn.example/video.mp4?token=abc", "video/mp4")]
    )

    result = resolve_media(
        "https://public.example/watch/1",
        ResolverLimits(),
        browser=FakeBrowser(context),
        validator=validator,
    )

    assert result.url == "https://cdn.example/video.mp4?token=abc"
    assert result.cookies == "session=secret"
    assert context.closed is True


def test_private_iframe_is_skipped_and_context_is_closed():
    context = FakeContext(frames=[FakeFrame("http://127.0.0.1/admin", "secret")])

    result = resolve_media(
        "https://public.example/watch/1",
        ResolverLimits(),
        browser=FakeBrowser(context),
        validator=validator,
    )

    assert result is None
    assert context.closed is True


def test_html_media_url_is_detected():
    context = FakeContext(html='<video src="https://cdn.example/movie.m3u8?key=1"></video>')

    result = resolve_media(
        "https://public.example/watch/1",
        ResolverLimits(),
        browser=FakeBrowser(context),
        validator=validator,
    )

    assert result.url == "https://cdn.example/movie.m3u8?key=1"


def test_response_capture_respects_candidate_limit():
    context = FakeContext(
        responses=[
            FakeResponse(f"https://cdn.example/video-{index}.mp4", "video/mp4")
            for index in range(5)
        ]
    )

    result = resolve_media(
        "https://public.example/watch/1",
        ResolverLimits(max_captured_urls=2),
        browser=FakeBrowser(context),
        validator=validator,
    )

    assert result.url == "https://cdn.example/video-0.mp4"


def test_private_and_unneeded_resources_are_aborted():
    context = FakeContext()
    resolve_media(
        "https://public.example/watch/1",
        ResolverLimits(),
        browser=FakeBrowser(context),
        validator=validator,
    )

    route_callback = context.callbacks["route"]
    private_route = FakeRoute("http://127.0.0.1/admin", "xhr")
    image_route = FakeRoute("https://public.example/poster.jpg", "image")
    media_route = FakeRoute("https://public.example/video.mp4", "media")
    route_callback(private_route)
    route_callback(image_route)
    route_callback(media_route)

    assert private_route.action == "abort"
    assert image_route.action == "abort"
    assert media_route.action == "continue"


def test_redirect_to_private_url_is_rejected_and_context_is_closed():
    context = FakeContext()
    original_goto = context.page.goto

    def redirect(url: str, **kwargs) -> None:
        original_goto(url, **kwargs)
        context.page.url = "http://127.0.0.1/admin"

    context.page.goto = redirect

    try:
        resolve_media(
            "https://public.example/watch/1",
            ResolverLimits(),
            browser=FakeBrowser(context),
            validator=validator,
        )
    except UnsafeUrl:
        pass
    else:
        raise AssertionError("private redirect should be rejected")

    assert context.closed is True


def test_context_is_closed_when_navigation_fails():
    context = FakeContext()

    def fail_navigation(url: str, **kwargs) -> None:
        raise RuntimeError("navigation failed")

    context.page.goto = fail_navigation

    try:
        resolve_media(
            "https://public.example/watch/1",
            ResolverLimits(),
            browser=FakeBrowser(context),
            validator=validator,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("navigation error should propagate")

    assert context.closed is True
