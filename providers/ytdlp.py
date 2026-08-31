import json
import subprocess
import time
from pathlib import Path

from providers.contracts import DownloadRequest, DownloadResult


class ProviderError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


class YtDlpClient:
    def __init__(self, command_runner=subprocess.run, download_runner=None):
        self.command_runner = command_runner
        self.download_runner = download_runner or run_with_size_limit

    def inspect(self, url: str) -> dict:
        command = ["yt-dlp", "--no-playlist", "--dump-single-json", url]
        try:
            result = self.command_runner(
                command,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ProviderError("timeout", "yt-dlp inspection timed out") from error
        if result.returncode != 0:
            detail = result.stderr.decode(errors="replace").strip()[-300:]
            raise ProviderError(classify_error(detail), detail)
        try:
            return json.loads(result.stdout.decode())
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderError("provider_failed", "yt-dlp returned invalid JSON") from error

    def download(self, request: DownloadRequest) -> DownloadResult:
        command = build_download_args(
            url=request.url,
            format_selector=request.format.selector,
            output_path=request.output_path,
            max_bytes=request.max_bytes,
            referer=request.resolver_context.get("referer"),
            playlist_item=request.format.playlist_item,
        )
        return self.download_runner(
            command,
            request.output_path,
            request.max_bytes,
            120,
        )


def run_with_size_limit(
    command: list[str],
    output_path: Path,
    max_bytes: int,
    timeout: float,
    poll_seconds: float = 0.25,
) -> DownloadResult:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    deadline = time.monotonic() + timeout

    def written_bytes() -> int:
        return sum(
            path.stat().st_size
            for path in output_path.parent.glob(f"{output_path.stem}*")
            if path.is_file()
        )

    def cleanup() -> None:
        for path in output_path.parent.glob(f"{output_path.stem}*"):
            if path.is_file():
                path.unlink(missing_ok=True)

    while process.poll() is None:
        current_size = written_bytes()
        if current_size > max_bytes:
            process.kill()
            process.communicate()
            cleanup()
            return DownloadResult(
                False,
                bytes_written=current_size,
                error_code="too_large",
            )
        if time.monotonic() >= deadline:
            process.kill()
            process.communicate()
            cleanup()
            return DownloadResult(
                False,
                bytes_written=current_size,
                error_code="timeout",
            )
        time.sleep(poll_seconds)

    _, stderr = process.communicate()
    final_size = written_bytes()
    if final_size > max_bytes:
        cleanup()
        return DownloadResult(
            False,
            bytes_written=final_size,
            error_code="too_large",
        )
    if process.returncode == 0 and output_path.is_file():
        return DownloadResult(
            True,
            file_path=output_path,
            bytes_written=output_path.stat().st_size,
        )

    detail = stderr.decode(errors="replace").strip()[-300:]
    cleanup()
    return DownloadResult(
        False,
        bytes_written=final_size,
        error_code=classify_error(detail),
        error_detail=detail,
    )


def build_download_args(
    url: str,
    format_selector: str,
    output_path: Path,
    max_bytes: int,
    referer: str | None = None,
    playlist_item: int | None = None,
) -> list[str]:
    args = [
        "yt-dlp",
        "--no-playlist",
        "--max-filesize",
        str(max_bytes),
    ]
    if referer:
        args.extend(["--add-header", f"Referer: {referer}"])
    if playlist_item is not None:
        args.extend(["--playlist-items", str(playlist_item)])
    args.extend(
        [
            "-f",
            format_selector,
            "--merge-output-format",
            "mp4",
            "-o",
            str(output_path),
            url,
        ]
    )
    return args


def classify_error(message: str) -> str:
    lowered = message.lower()
    if "private" in lowered:
        return "private"
    if "sign in" in lowered or "login" in lowered or "cookies" in lowered:
        return "authentication_required"
    if "429" in lowered or "rate limit" in lowered or "too many requests" in lowered:
        return "rate_limited"
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if "unavailable" in lowered or "not available" in lowered or "not found" in lowered:
        return "unavailable"
    return "provider_failed"
