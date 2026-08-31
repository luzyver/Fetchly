from pathlib import Path


def test_legacy_stack_is_gone():
    root = Path(__file__).parents[1]
    for path in ("app.py", "core", "routes", "requirements.txt"):
        assert not (root / path).exists(), f"legacy path remains: {path}"

    source = "\n".join(
        path.read_text(encoding="utf-8")
        for package in ("fetchly", "downloads", "providers", "usage", "dashboard")
        for path in (root / package).rglob("*.py")
    ).lower()
    assert "import flask" not in source
    assert "cloudflare-warp" not in source
