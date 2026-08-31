from providers.contracts import DownloadRequest, DownloadResult, InspectionResult
from providers.generic import normalize_generic


class YouTubeProvider:
    key = "youtube"

    def __init__(self, client):
        self.client = client

    def inspect(self, url: str) -> InspectionResult:
        return normalize_generic(self.key, url, self.client.inspect(url))

    def download(self, request: DownloadRequest) -> DownloadResult:
        return self.client.download(request)
