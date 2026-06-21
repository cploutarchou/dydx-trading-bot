"""Placeholder MinIO artifact store adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .artifacts import ArtifactStore, LocalArtifactStore


class MinIOArtifactStore(ArtifactStore):
    """A feature-flagged artifact adapter that can fall back to local files.

    The implementation is intentionally conservative for the initial rollout:
    if MinIO is not enabled or not configured yet, writes are delegated to the
    supplied fallback store. This keeps the current runtime safe while the
    deployment layer is introduced.
    """

    def __init__(
        self,
        *,
        bucket: str,
        enabled: bool = False,
        fallback: ArtifactStore | None = None,
        endpoint_url: str | None = None,
        secure: bool = True,
        extra_config: Mapping[str, Any] | None = None,
    ):
        self.bucket = bucket.strip()
        self.enabled = enabled
        self.fallback = fallback or LocalArtifactStore("bot_states/backtest_artifacts")
        self.endpoint_url = (endpoint_url or "").strip()
        self.secure = secure
        self.extra_config = dict(extra_config or {})

    def reference_for(self, key: str) -> str:
        safe_key = str(key).strip().lstrip("/")
        if not safe_key:
            raise ValueError("artifact key is required")
        return f"s3://{self.bucket}/{safe_key}"

    def put_bytes(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> str:
        del content_type
        if not self.enabled:
            return self.fallback.put_bytes(key, data)
        # Initial rollout placeholder: keep writes local until the MinIO client
        # wiring lands in the deployment PR.
        if self.fallback is not None:
            return self.fallback.put_bytes(key, data)
        raise RuntimeError(
            "MinIO artifact storage is enabled but no fallback store is configured"
        )

    def read_bytes(self, key: str) -> bytes:
        return self.fallback.read_bytes(key)

    def exists(self, key: str) -> bool:
        return self.fallback.exists(key)
