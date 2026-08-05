import re
from dataclasses import dataclass, field
from typing import Any, Optional


_VERSION_PATTERN = re.compile(
    r"^\s*[vV]?"
    r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:[-.]?(?P<label>alpha|beta|rc|nightly)"
    r"(?:[-.]?(?P<label_number>\d+))?)?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?\s*$",
    re.IGNORECASE,
)

_PRERELEASE_ORDER = {
    "nightly": 0,
    "alpha": 1,
    "beta": 2,
    "rc": 3,
}


@dataclass(frozen=True, slots=True)
class AppVersion:
    major: int
    minor: int
    patch: int
    label: Optional[str] = None
    label_number: int = 0
    build: Optional[str] = None

    @classmethod
    def parse(cls, value: str) -> "AppVersion":
        match = _VERSION_PATTERN.fullmatch(str(value))
        if not match:
            raise ValueError(f"Invalid version: {value!r}")

        label = match.group("label")
        if label:
            label = label.lower()

        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            label=label,
            label_number=int(match.group("label_number") or 0),
            build=match.group("build"),
        )

    @property
    def is_prerelease(self) -> bool:
        return self.label is not None

    def comparison_key(self) -> tuple[int, int, int, int, int]:
        if self.label is None:
            rank = 10
            number = 0
        else:
            rank = _PRERELEASE_ORDER.get(self.label, -1)
            number = self.label_number

        return (
            self.major,
            self.minor,
            self.patch,
            rank,
            number,
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, AppVersion):
            return NotImplemented
        return self.comparison_key() < other.comparison_key()

    def __str__(self) -> str:
        value = f"{self.major}.{self.minor}.{self.patch}"
        if self.label:
            value += f"-{self.label}"
            if self.label_number:
                value += str(self.label_number)
        if self.build:
            value += f"+{self.build}"
        return value


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int = 0
    content_type: str = ""
    asset_id: int = 0

    @classmethod
    def from_github(cls, data: dict[str, Any]) -> "ReleaseAsset":
        name = str(data.get("name", "")).strip()
        download_url = str(
            data.get("browser_download_url", "")
        ).strip()

        if not name:
            raise ValueError("GitHub release asset has no name.")
        if not download_url:
            raise ValueError(f"Asset '{name}' has no download URL.")

        return cls(
            name=name,
            download_url=download_url,
            size=max(0, int(data.get("size", 0) or 0)),
            content_type=str(data.get("content_type", "")),
            asset_id=int(data.get("id", 0) or 0),
        )


@dataclass(frozen=True, slots=True)
class UpdateManifest:
    version: AppVersion
    minimum_version: AppVersion
    channel: str = "stable"
    mandatory: bool = False
    asset_name: str = ""
    sha256: str = ""
    release_notes: tuple[str, ...] = field(default_factory=tuple)
    published_at: str = ""
    release_url: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpdateManifest":
        if not isinstance(data, dict):
            raise TypeError("Update manifest must be an object.")

        version = AppVersion.parse(str(data.get("version", "")))
        minimum_version = AppVersion.parse(
            str(data.get("minimum_version", "0.0.0"))
        )

        channel = str(
            data.get("channel", "stable")
        ).strip().lower()

        if channel not in {"stable", "beta", "nightly"}:
            raise ValueError(f"Invalid update channel: {channel}")

        asset_name = str(data.get("asset_name", "")).strip()
        sha256 = str(data.get("sha256", "")).strip().lower()

        if not asset_name:
            raise ValueError("Manifest asset_name is required.")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError(
                "Manifest sha256 must be a 64-character SHA-256 hex digest."
            )

        notes_raw = data.get("release_notes", [])
        if isinstance(notes_raw, str):
            notes = (notes_raw.strip(),)
        elif isinstance(notes_raw, list):
            notes = tuple(
                str(note).strip()
                for note in notes_raw
                if str(note).strip()
            )
        else:
            raise TypeError("release_notes must be a list or string.")

        return cls(
            version=version,
            minimum_version=minimum_version,
            channel=channel,
            mandatory=bool(data.get("mandatory", False)),
            asset_name=asset_name,
            sha256=sha256,
            release_notes=notes,
            published_at=str(data.get("published_at", "")),
            release_url=str(data.get("release_url", "")),
        )


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    current_version: AppVersion
    latest_version: AppVersion
    channel: str
    has_update: bool
    mandatory: bool
    supported: bool
    manifest: UpdateManifest
    update_asset: ReleaseAsset
    manifest_asset: ReleaseAsset
    github_tag: str = ""
    github_release_name: str = ""
    github_release_url: str = ""
    published_at: str = ""

    @property
    def can_install(self) -> bool:
        return (
            self.has_update
            and self.supported
            and bool(self.update_asset.download_url)
        )