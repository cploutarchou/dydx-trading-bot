"""MinIO-backed artifact store adapter with safe local fallback."""

from __future__ import annotations

import io
import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

try:  # pragma: no cover - import is optional in test/dev environments
    from minio import Minio
except Exception:  # pragma: no cover - keep adapter functional without package
    Minio = None

from .artifacts import ArtifactStore, LocalArtifactStore

logger = logging.getLogger(__name__)


class MinIOArtifactStore(ArtifactStore):
    """Feature-flagged MinIO artifact adapter with safe local fallback."""

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
        self._bucket_ready = False
        self._client = self._build_client()

    @staticmethod
    def _is_not_found_error(exc: Exception) -> bool:
        code = str(getattr(exc, "code", "") or "").lower()
        if code in {"nosuchkey", "nosuchbucket", "notfound", "404"}:
            return True
        message = str(exc).lower()
        return "no such key" in message or "not found" in message

    def _build_client(self) -> Any | None:
        if not self.enabled:
            return None

        injected_client = self.extra_config.get("client")
        if injected_client is not None:
            return injected_client

        if Minio is None:
            logger.warning("MinIO adapter enabled but minio package is not installed")
            return None

        endpoint_url = self.endpoint_url
        if endpoint_url and "://" not in endpoint_url:
            endpoint_url = f"http://{endpoint_url}"

        parsed = urlsplit(endpoint_url)
        endpoint = (parsed.netloc or parsed.path or "").strip()
        if not endpoint:
            logger.warning("MinIO adapter enabled but endpoint is missing")
            return None

        access_key = str(self.extra_config.get("access_key") or "").strip()
        secret_key = str(self.extra_config.get("secret_key") or "").strip()
        if not access_key or not secret_key:
            logger.warning("MinIO adapter enabled but credentials are missing")
            return None

        secure = self.secure
        if parsed.scheme == "http":
            secure = False
        elif parsed.scheme == "https":
            secure = True

        return Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            session_token=self.extra_config.get("session_token"),
            region=self.extra_config.get("region"),
        )

    def _ensure_bucket(self) -> None:
        if self._client is None or self._bucket_ready:
            return
        auto_create_bucket = bool(self.extra_config.get("auto_create_bucket", True))
        if self._client.bucket_exists(self.bucket):
            self._bucket_ready = True
            return
        if not auto_create_bucket:
            raise RuntimeError(f"MinIO bucket does not exist: {self.bucket}")
        self._client.make_bucket(self.bucket)
        self._bucket_ready = True

    def reference_for(self, key: str) -> str:
        safe_key = str(key).strip().lstrip("/")
        if not safe_key:
            raise ValueError("artifact key is required")
        return f"s3://{self.bucket}/{safe_key}"

    def put_bytes(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> str:
        safe_key = str(key).strip().lstrip("/")
        if not safe_key:
            raise ValueError("artifact key is required")

        if self.enabled and self._client is not None:
            try:
                self._ensure_bucket()
                self._client.put_object(
                    self.bucket,
                    safe_key,
                    io.BytesIO(data),
                    length=len(data),
                    content_type=content_type or "application/octet-stream",
                )
                return self.reference_for(safe_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "MinIO write failed; using local fallback key=%s error=%s",
                    safe_key,
                    exc,
                )

        if not self.enabled:
            return self.fallback.put_bytes(safe_key, data, content_type=content_type)

        if self.fallback is not None:
            return self.fallback.put_bytes(safe_key, data, content_type=content_type)
        raise RuntimeError(
            "MinIO artifact storage is enabled but no fallback store is configured"
        )

    def read_bytes(self, key: str) -> bytes:
        safe_key = str(key).strip().lstrip("/")
        if not safe_key:
            raise ValueError("artifact key is required")

        if self.enabled and self._client is not None:
            response = None
            try:
                response = self._client.get_object(self.bucket, safe_key)
                return response.read()
            except Exception as exc:  # noqa: BLE001
                if not self._is_not_found_error(exc):
                    logger.warning(
                        "MinIO read failed; trying fallback key=%s error=%s",
                        safe_key,
                        exc,
                    )
            finally:
                if response is not None:
                    close = getattr(response, "close", None)
                    if callable(close):
                        close()
                    release_conn = getattr(response, "release_conn", None)
                    if callable(release_conn):
                        release_conn()

        return self.fallback.read_bytes(safe_key)

    def exists(self, key: str) -> bool:
        safe_key = str(key).strip().lstrip("/")
        if not safe_key:
            return False

        if self.enabled and self._client is not None:
            try:
                self._client.stat_object(self.bucket, safe_key)
                return True
            except Exception as exc:  # noqa: BLE001
                if not self._is_not_found_error(exc):
                    logger.warning(
                        "MinIO exists check failed; trying fallback key=%s error=%s",
                        safe_key,
                        exc,
                    )

        return self.fallback.exists(safe_key)
