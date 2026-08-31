from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class MediaFormat:
    id: str
    label: str
    extension: str
    kind: str
    height: int | None = None
    estimated_bytes: int | None = None
    selector: str = "best"
    playlist_item: int | None = None

    def to_public_dict(self) -> dict[str, str | int | None]:
        return {
            "id": self.id,
            "label": self.label,
            "extension": self.extension,
            "kind": self.kind,
            "height": self.height,
            "estimated_bytes": self.estimated_bytes,
        }


@dataclass(frozen=True)
class InspectionResult:
    provider: str
    canonical_url: str
    title: str
    formats: tuple[MediaFormat, ...]
    thumbnail_url: str | None = None
    duration_seconds: int | None = None
    resolver_context: dict[str, str] = field(default_factory=dict)

    def to_public_dict(self) -> dict:
        return {
            "provider": self.provider,
            "title": self.title,
            "thumbnail_url": self.thumbnail_url,
            "duration_seconds": self.duration_seconds,
            "formats": [media_format.to_public_dict() for media_format in self.formats],
        }


@dataclass(frozen=True)
class ResolvedMedia:
    url: str
    referer: str | None = None
    cookies: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    format: MediaFormat
    output_path: Path
    max_bytes: int
    resolver_context: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DownloadResult:
    success: bool
    file_path: Path | None = None
    bytes_written: int = 0
    error_code: str | None = None
    error_detail: str | None = None


class Provider(Protocol):
    key: str

    def inspect(self, url: str) -> InspectionResult: ...

    def download(self, request: DownloadRequest) -> DownloadResult: ...
