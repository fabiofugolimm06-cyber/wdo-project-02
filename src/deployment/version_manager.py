"""
version_manager.py — registro e tags de versão deployment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

WDO_VERSION_EPOCH = "2000-01-01T00:00:00Z"


@dataclass(frozen=True)
class VersionRecord:
    version: str
    fingerprint: str
    tagged_at: str
    tag: str = "release"


class VersionManager:
    """Registry append-only de versões deployment."""

    _instance: VersionManager | None = None
    _versions: dict[str, VersionRecord] = {}
    _tags: dict[str, str] = {}

    def __new__(cls) -> VersionManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register_version(
        self,
        *,
        version: str,
        fingerprint: str,
    ) -> VersionRecord:
        if version in self._versions:
            return self._versions[version]
        record = VersionRecord(
            version=version,
            fingerprint=fingerprint,
            tagged_at=WDO_VERSION_EPOCH,
        )
        self._versions[version] = record
        return record

    def tag_release(self, *, version: str, tag: str = "release") -> dict[str, Any]:
        if version not in self._versions:
            return {
                "status": "FAIL",
                "failures": [f"version: {version!r} não registrada."],
            }
        self._tags[tag] = version
        record = self._versions[version]
        tagged = VersionRecord(
            version=record.version,
            fingerprint=record.fingerprint,
            tagged_at=WDO_VERSION_EPOCH,
            tag=tag,
        )
        self._versions[version] = tagged
        return {"status": "PASS", "failures": [], "version": version, "tag": tag}

    def get_version(self, version: str) -> VersionRecord | None:
        return self._versions.get(version)

    def list_versions(self) -> list[str]:
        return sorted(self._versions.keys())

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
        cls._versions = {}
        cls._tags = {}
