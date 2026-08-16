"""Artifact storage interfaces and local fallback implementation."""

from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ArtifactStore(ABC):
    """Store and retrieve backtest artifacts."""

    @abstractmethod
    def reference_for(self, key: str) -> str:
        """Return a stable external reference for the given artifact key."""

    @abstractmethod
    def put_bytes(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> str:
        """Persist binary artifact data and return its reference."""

    def put_text(self, key: str, text: str, *, content_type: str | None = None) -> str:
        return self.put_bytes(key, text.encode("utf-8"), content_type=content_type)

    def put_json(
        self, key: str, payload: Any, *, content_type: str = "application/json"
    ) -> str:
        return self.put_text(
            key,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            content_type=content_type,
        )

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        """Read persisted artifact bytes."""

    def read_text(self, key: str) -> str:
        return self.read_bytes(key).decode("utf-8")

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True when the artifact exists."""

    def delete(self, key: str) -> bool:
        """Best-effort delete. Returns True when the artifact was removed.

        Default no-op for stores without delete support so callers never
        depend on removal succeeding.
        """
        del key
        return False


class LocalArtifactStore(ArtifactStore):
    """Filesystem-backed artifact store used as the safe local fallback."""

    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        clean_key = str(key).strip().lstrip("/")
        if not clean_key:
            raise ValueError("artifact key is required")
        path = (self.root_dir / clean_key).resolve()
        if self.root_dir not in path.parents and path != self.root_dir:
            raise ValueError(f"artifact key escapes storage root: {key!r}")
        return path

    def reference_for(self, key: str) -> str:
        return self._resolve_path(key).as_uri()

    def put_bytes(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> str:
        del content_type
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write in the destination directory and publish with os.replace so readers
        # never observe a truncated artifact after a crash or concurrent update.
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
            temp_path = None
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        return path.as_uri()

    def read_bytes(self, key: str) -> bytes:
        return self._resolve_path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve_path(key).exists()

    def delete(self, key: str) -> bool:
        try:
            self._resolve_path(key).unlink()
            return True
        except OSError:
            return False
