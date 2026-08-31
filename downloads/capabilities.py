import subprocess


def _browser_check() -> bool:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        browser.close()
    return True


def check_capabilities(*, runner=subprocess.run, browser_check=_browser_check) -> dict[str, bool]:
    result = {}
    for name, command in (
        ("ffmpeg", ["ffmpeg", "-version"]),
        ("yt_dlp", ["yt-dlp", "--version"]),
    ):
        try:
            completed = runner(command, capture_output=True, timeout=5, check=False)
            result[name] = completed.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            result[name] = False
    try:
        result["playwright"] = bool(browser_check())
    except Exception:
        result["playwright"] = False
    return result
