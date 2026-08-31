from providers.contracts import MediaFormat


def test_public_format_dict_excludes_sensitive_fields():
    value = MediaFormat(
        id="720p",
        label="720p",
        extension="mp4",
        kind="video",
        height=720,
        estimated_bytes=12_000,
        selector="18+140",
    )

    assert value.to_public_dict() == {
        "id": "720p",
        "label": "720p",
        "extension": "mp4",
        "kind": "video",
        "height": 720,
        "estimated_bytes": 12_000,
    }
