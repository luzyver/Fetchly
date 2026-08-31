import json
from pathlib import Path

from providers.contracts import DownloadRequest, DownloadResult, MediaFormat
from providers.generic import GenericProvider
from providers.instagram import InstagramProvider
from providers.registry import build_default_registry, get_provider
from providers.tiktok import TikTokProvider
from providers.twitter import TwitterProvider
from providers.youtube import YouTubeProvider

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeYtDlpClient:
    def __init__(self, info: dict):
        self.info = info

    def inspect(self, url: str) -> dict:
        return self.info

    def download(self, request: DownloadRequest) -> DownloadResult:
        return DownloadResult(True, request.output_path, 128)


class FakeResponse:
    status_code = 200

    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeStreamResponse:
    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        return iter((b"abc", b"def"))


class FakeSession:
    def __init__(self, payload: dict):
        self.payload = payload

    def post(self, url: str, data: dict, timeout: int) -> FakeResponse:
        return FakeResponse(self.payload)

    def get(self, url: str, stream: bool, timeout: int) -> FakeStreamResponse:
        return FakeStreamResponse()


def test_ytdlp_providers_normalize_client_results():
    youtube = YouTubeProvider(FakeYtDlpClient(load("youtube.json")))
    twitter = TwitterProvider(FakeYtDlpClient(load("twitter.json")))
    instagram = InstagramProvider(FakeYtDlpClient(load("instagram.json")))
    generic = GenericProvider(FakeYtDlpClient(load("youtube.json")))

    assert youtube.inspect("https://youtu.be/abc").provider == "youtube"
    assert len(twitter.inspect("https://x.com/u/status/1").formats) == 2
    assert instagram.inspect("https://instagram.com/p/1").formats[0].id == "instagram_hd"
    assert generic.inspect("https://vimeo.com/1").provider == "generic"


def test_tiktok_provider_normalizes_api_result():
    provider = TikTokProvider(FakeSession(load("tiktok.json")), validator=lambda url: url)

    result = provider.inspect("https://tiktok.com/@u/video/1")

    assert result.provider == "tiktok"
    assert len(result.formats) == 3


def test_default_registry_preserves_supported_domain_routing():
    registry = build_default_registry(
        FakeYtDlpClient(load("youtube.json")), FakeSession(load("tiktok.json"))
    )

    cases = {
        "https://youtube.com/watch?v=1": "youtube",
        "https://vm.tiktok.com/abc": "tiktok",
        "https://x.com/u/status/1": "twitter",
        "https://instagram.com/p/1": "instagram",
        "https://facebook.com/watch/1": "generic",
        "https://vimeo.com/1": "generic",
        "https://dailymotion.com/video/1": "generic",
        "https://twitch.tv/videos/1": "generic",
        "https://bilibili.com/video/1": "generic",
    }
    assert {url: get_provider(url, registry).key for url in cases} == cases


def test_ytdlp_provider_downloads_through_shared_client(tmp_path):
    provider = YouTubeProvider(FakeYtDlpClient(load("youtube.json")))
    request = DownloadRequest(
        "https://youtu.be/abc",
        MediaFormat("22", "720p", "mp4", "video", selector="22"),
        tmp_path / "video.mp4",
        1_000,
    )

    result = provider.download(request)

    assert result.success is True
    assert result.file_path == request.output_path


def test_tiktok_stream_download_uses_private_resolver_context(tmp_path):
    provider = TikTokProvider(FakeSession(load("tiktok.json")), validator=lambda url: url)
    request = DownloadRequest(
        "https://tiktok.com/@u/video/1",
        MediaFormat(
            "tiktok_no_watermark",
            "Tanpa watermark",
            "mp4",
            "video",
            selector="tiktok_no_watermark",
        ),
        tmp_path / "video.mp4",
        10,
        {"tiktok_no_watermark": "https://cdn.example/video.mp4"},
    )

    result = provider.download(request)

    assert result.success is True
    assert request.output_path.read_bytes() == b"abcdef"
