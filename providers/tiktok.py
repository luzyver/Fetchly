from dataclasses import replace

from providers.contracts import DownloadRequest, DownloadResult, InspectionResult, MediaFormat
from providers.url_safety import validate_public_url


class TikTokProvider:
    key = "tiktok"

    def __init__(self, session, validator=validate_public_url):
        self.session = session
        self.validator = validator

    def inspect(self, url: str) -> InspectionResult:
        response = self.session.post(
            "https://www.tikwm.com/api/",
            data={"url": url, "hd": 1},
            timeout=20,
        )
        response.raise_for_status()
        result = normalize_tiktok(url, response.json())
        safe_context = {
            format_id: getattr(self.validator(direct_url), "url", direct_url)
            for format_id, direct_url in result.resolver_context.items()
        }
        return replace(result, resolver_context=safe_context)

    def download(self, request: DownloadRequest) -> DownloadResult:
        direct_url = request.resolver_context.get(request.format.id)
        if not direct_url:
            return DownloadResult(
                False, error_code="provider_failed", error_detail="Missing media URL"
            )
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        try:
            response = self.session.get(direct_url, stream=True, timeout=120)
            response.raise_for_status()
            with request.output_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > request.max_bytes:
                        raise _SizeExceeded
                    output.write(chunk)
        except _SizeExceeded:
            request.output_path.unlink(missing_ok=True)
            return DownloadResult(False, bytes_written=downloaded, error_code="too_large")
        except Exception as error:
            request.output_path.unlink(missing_ok=True)
            return DownloadResult(
                False,
                bytes_written=downloaded,
                error_code="provider_failed",
                error_detail=str(error)[-300:],
            )
        return DownloadResult(True, request.output_path, downloaded)


class _SizeExceeded(Exception):
    pass


def normalize_tiktok(url: str, payload: dict) -> InspectionResult:
    if payload.get("code") != 0 or not payload.get("data"):
        raise ValueError(payload.get("msg") or "TikTok returned no media")
    data = payload["data"]
    size = data.get("hd_size") or data.get("size")
    choices = (
        (
            "tiktok_no_watermark",
            "Tanpa watermark (HD)",
            "mp4",
            "video",
            data.get("hdplay") or data.get("play"),
        ),
        ("tiktok_watermark", "Dengan watermark", "mp4", "video", data.get("wmplay")),
        ("tiktok_audio", "Audio saja", "mp3", "audio", data.get("music")),
    )
    formats = tuple(
        MediaFormat(
            id=format_id,
            label=label,
            extension=extension,
            kind=kind,
            estimated_bytes=int(size) if size and kind == "video" else None,
            selector=format_id,
        )
        for format_id, label, extension, kind, direct_url in choices
        if direct_url
    )
    context = {format_id: direct_url for format_id, _, _, _, direct_url in choices if direct_url}
    return InspectionResult(
        provider="tiktok",
        canonical_url=url,
        title=data.get("title") or "Video TikTok",
        formats=formats,
        thumbnail_url=data.get("cover"),
        duration_seconds=data.get("duration"),
        resolver_context=context,
    )
