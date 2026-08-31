from providers.contracts import DownloadRequest, DownloadResult, InspectionResult, MediaFormat


class TwitterProvider:
    key = "twitter"

    def __init__(self, client):
        self.client = client

    def inspect(self, url: str) -> InspectionResult:
        return normalize_twitter(url, self.client.inspect(url))

    def download(self, request: DownloadRequest) -> DownloadResult:
        return self.client.download(request)


def normalize_twitter(url: str, info: dict) -> InspectionResult:
    entries = info.get("entries") or [info]
    formats = []
    for index, entry in enumerate(entries, start=1):
        candidates = [
            item
            for item in entry.get("formats", [])
            if item.get("height") and item.get("vcodec", "none") != "none"
        ]
        best = max(candidates, key=lambda item: item.get("height", 0), default={})
        height = best.get("height")
        duration = entry.get("duration") or info.get("duration")
        size = best.get("filesize") or best.get("filesize_approx")
        if not size and best.get("tbr") and duration:
            size = int(best["tbr"] * 1000 / 8 * duration)
        label = f"Video {index}" + (f" ({height}p)" if height else "")
        formats.append(
            MediaFormat(
                id=f"twitter_{index - 1}",
                label=label,
                extension="mp4",
                kind="video",
                height=height,
                estimated_bytes=int(size) if size else None,
                selector="bestvideo+bestaudio/best",
                playlist_item=index,
            )
        )
    return InspectionResult(
        provider="twitter",
        canonical_url=url,
        title=info.get("title") or "Video X",
        formats=tuple(formats),
        thumbnail_url=info.get("thumbnail"),
        duration_seconds=info.get("duration"),
    )
