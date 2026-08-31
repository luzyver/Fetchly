import json
from pathlib import Path

from providers.generic import normalize_generic

FIXTURES = Path(__file__).parent / "fixtures"


def test_generic_formats_are_unique_and_sorted_by_height():
    info = json.loads((FIXTURES / "youtube.json").read_text(encoding="utf-8"))
    info["formats"].append(
        {"format_id": "720-duplicate", "height": 720, "ext": "webm", "vcodec": "vp9"}
    )

    result = normalize_generic("youtube", "https://youtube.com/watch?v=1", info)

    assert [item.height for item in result.formats] == [1080, 720]
    assert result.formats[0].selector == "137+bestaudio/137"
    assert result.formats[1].selector == "22"
