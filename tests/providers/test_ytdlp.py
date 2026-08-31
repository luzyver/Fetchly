import subprocess
import sys
from pathlib import Path

import pytest

from providers.contracts import DownloadRequest, DownloadResult, MediaFormat
from providers.ytdlp import (
    ProviderError,
    YtDlpClient,
    build_download_args,
    classify_error,
    run_with_size_limit,
)


def test_download_args_are_fixed_and_size_limited(tmp_path):
    args = build_download_args(
        url="https://media.example/video",
        format_selector="18+140",
        output_path=tmp_path / "result.mp4",
        max_bytes=10_000_000,
        referer="https://media.example/",
        playlist_item=2,
    )

    assert args == [
        "yt-dlp",
        "--no-playlist",
        "--max-filesize",
        "10000000",
        "--add-header",
        "Referer: https://media.example/",
        "--playlist-items",
        "2",
        "-f",
        "18+140",
        "--merge-output-format",
        "mp4",
        "-o",
        str(Path(tmp_path / "result.mp4")),
        "https://media.example/video",
    ]


def test_errors_are_mapped_to_stable_codes():
    assert classify_error("This video is private") == "private"
    assert classify_error("Sign in to confirm your age") == "authentication_required"
    assert classify_error("HTTP Error 429: Too Many Requests") == "rate_limited"
    assert classify_error("operation timed out") == "timeout"
    assert classify_error("unexpected extractor output") == "provider_failed"


def test_size_limited_process_returns_written_file(tmp_path):
    output = tmp_path / "video.mp4"
    command = [
        sys.executable,
        "-c",
        "from pathlib import Path; import sys; Path(sys.argv[1]).write_bytes(b'x' * 128)",
        str(output),
    ]

    result = run_with_size_limit(command, output, max_bytes=1_024, timeout=2, poll_seconds=0.01)

    assert result.success is True
    assert result.file_path == output
    assert result.bytes_written == 128


def test_size_limited_process_deletes_oversized_output(tmp_path):
    output = tmp_path / "video.mp4"
    command = [
        sys.executable,
        "-c",
        "from pathlib import Path; import sys; Path(sys.argv[1]).write_bytes(b'x' * 2048)",
        str(output),
    ]

    result = run_with_size_limit(command, output, max_bytes=1_024, timeout=2, poll_seconds=0.01)

    assert result.success is False
    assert result.error_code == "too_large"
    assert result.bytes_written == 2_048
    assert output.exists() is False


def test_size_limited_process_kills_timeout(tmp_path):
    output = tmp_path / "video.mp4"
    command = [sys.executable, "-c", "import time; time.sleep(2)"]

    result = run_with_size_limit(command, output, max_bytes=1_024, timeout=0.05, poll_seconds=0.01)

    assert result.success is False
    assert result.error_code == "timeout"


def test_client_inspect_decodes_json_and_uses_bounded_command():
    seen: list[list[str]] = []

    def run(command, **kwargs):
        seen.append(command)
        return subprocess.CompletedProcess(command, 0, b'{"title":"Sample","formats":[]}', b"")

    result = YtDlpClient(command_runner=run).inspect("https://example.com/video")

    assert result["title"] == "Sample"
    assert seen == [["yt-dlp", "--no-playlist", "--dump-single-json", "https://example.com/video"]]


def test_client_inspect_raises_stable_provider_error():
    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, b"", b"This video is private")

    with pytest.raises(ProviderError) as error:
        YtDlpClient(command_runner=run).inspect("https://example.com/video")

    assert error.value.code == "private"


def test_client_download_composes_server_owned_request(tmp_path):
    captured: list[tuple[list[str], Path, int, float]] = []

    def download_runner(command, output_path, max_bytes, timeout):
        captured.append((command, output_path, max_bytes, timeout))
        return DownloadResult(True, output_path, 128)

    request = DownloadRequest(
        url="https://example.com/video",
        format=MediaFormat("720", "720p", "mp4", "video", selector="720+bestaudio/720"),
        output_path=tmp_path / "video.mp4",
        max_bytes=1_000_000,
        resolver_context={"referer": "https://example.com/"},
    )

    result = YtDlpClient(download_runner=download_runner).download(request)

    assert result.success is True
    assert captured[0][0][-1] == "https://example.com/video"
    assert "Referer: https://example.com/" in captured[0][0]
    assert captured[0][1:] == ((tmp_path / "video.mp4"), 1_000_000, 120)
