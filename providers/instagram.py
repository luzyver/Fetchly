from providers.contracts import DownloadRequest, DownloadResult, InspectionResult, MediaFormat


class InstagramProvider:
    key = "instagram"

    def __init__(self, client):
        self.client = client

    def inspect(self, url: str) -> InspectionResult:
        return normalize_instagram(url, self.client.inspect(url))

    def download(self, request: DownloadRequest) -> DownloadResult:
        return self.client.download(request)


def normalize_instagram(url: str, info: dict) -> InspectionResult:
    title = info.get("title") or "Video Instagram"
    if len(title) > 50:
        title = f"{title[:50]}..."
    candidates = [item for item in info.get("formats", []) if item.get("height")]
    best_height = max((item.get("height", 0) for item in candidates), default=720)
    sizes = [
        item.get("filesize") or item.get("filesize_approx")
        for item in candidates
        if item.get("filesize") or item.get("filesize_approx")
    ]
    estimated = max(sizes, default=None)
    media_format = MediaFormat(
        id="instagram_hd",
        label=f"HD ({best_height}p)",
        extension="mp4",
        kind="video",
        height=best_height,
        estimated_bytes=int(estimated) if estimated else None,
        selector="bestvideo+bestaudio/best",
    )
    return InspectionResult(
        provider="instagram",
        canonical_url=url,
        title=title,
        formats=(media_format,),
        thumbnail_url=info.get("thumbnail"),
        duration_seconds=info.get("duration"),
    )
