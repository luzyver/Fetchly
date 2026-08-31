from types import SimpleNamespace

from downloads.capabilities import check_capabilities


def test_capability_check_uses_local_binaries_and_browser_only():
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0)

    result = check_capabilities(runner=runner, browser_check=lambda: True)

    assert result == {"ffmpeg": True, "yt_dlp": True, "playwright": True}
    assert commands == [["ffmpeg", "-version"], ["yt-dlp", "--version"]]
