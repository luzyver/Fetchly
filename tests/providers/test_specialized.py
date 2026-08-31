import json
from pathlib import Path

from providers.instagram import normalize_instagram
from providers.tiktok import normalize_tiktok
from providers.twitter import normalize_twitter

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_tiktok_preserves_no_watermark_watermark_and_audio_choices():
    result = normalize_tiktok("https://tiktok.com/@user/video/1", load("tiktok.json"))

    assert [item.id for item in result.formats] == [
        "tiktok_no_watermark",
        "tiktok_watermark",
        "tiktok_audio",
    ]
    assert result.formats[2].extension == "mp3"
    assert result.resolver_context["tiktok_audio"].endswith("audio.mp3")


def test_twitter_creates_one_choice_per_video():
    result = normalize_twitter("https://x.com/user/status/1", load("twitter.json"))

    assert [item.label for item in result.formats] == ["Video 1 (720p)", "Video 2 (1080p)"]
    assert [item.playlist_item for item in result.formats] == [1, 2]


def test_instagram_returns_one_hd_choice_and_truncates_title():
    result = normalize_instagram("https://instagram.com/p/1", load("instagram.json"))

    assert len(result.formats) == 1
    assert result.formats[0].height == 1080
    assert result.formats[0].estimated_bytes == 5_000_000
    assert len(result.title) == 53
    assert result.title.endswith("...")
