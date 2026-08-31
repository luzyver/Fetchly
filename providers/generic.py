from providers.contracts import DownloadRequest, DownloadResult, InspectionResult, MediaFormat


class GenericProvider:
    key = "generic"

    def __init__(self, client):
        self.client = client

    def inspect(self, url: str) -> InspectionResult:
        return normalize_generic(self.key, url, self.client.inspect(url))

    def download(self, request: DownloadRequest) -> DownloadResult:
        return self.client.download(request)


def normalize_generic(provider: str, url: str, info: dict) -> InspectionResult:
    duration = info.get("duration")
    by_height: dict[int, MediaFormat] = {}
    for raw in info.get("formats", []):
        height = raw.get("height")
        if not height or raw.get("vcodec", "none") == "none" or height in by_height:
            continue
        size = raw.get("filesize") or raw.get("filesize_approx")
        if not size and raw.get("tbr") and duration:
            size = int(raw["tbr"] * 1000 / 8 * duration)
        format_id = str(raw.get("format_id") or "best")
        has_audio = raw.get("acodec", "none") != "none"
        selector = format_id if has_audio else f"{format_id}+bestaudio/{format_id}"
        by_height[height] = MediaFormat(
            id=format_id,
            label=f"{height}p",
            extension=raw.get("ext") or "mp4",
            kind="video",
            height=height,
            estimated_bytes=int(size) if size else None,
            selector=selector,
        )
    formats = tuple(sorted(by_height.values(), key=lambda item: item.height or 0, reverse=True))
    if not formats:
        formats = (MediaFormat("best", "Video terbaik", "mp4", "video"),)
    return InspectionResult(
        provider=provider,
        canonical_url=url,
        title=info.get("title") or "Video",
        formats=formats,
        thumbnail_url=info.get("thumbnail"),
        duration_seconds=duration,
    )
