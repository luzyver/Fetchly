from fetchly.logging import redact


def test_redact_removes_sensitive_query_and_headers():
    value = redact(
        {
            "url": "https://cdn.example/video?token=secret&x=1",
            "cookies": "session=secret",
            "authorization": "Bearer secret",
            "nested": {"referer": "https://example.test/watch?key=secret"},
        }
    )

    assert "secret" not in str(value)
    assert value["url"] == "https://cdn.example/video"
    assert value["cookies"] == "[redacted]"
