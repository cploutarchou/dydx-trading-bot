"""
Bot Instance Manager - Handles multiple bot instances with API control
"""

from src.shared.env_loader import load_repo_env

load_repo_env(__file__)

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, List, Optional, TextIO

import psutil
from loguru import logger
from sqlalchemy import text

from internal.domain.models import BotStatusEnum
from src.infrastructure.database import db
from src.infrastructure.domain.bot_api_models import (
    BotInstanceConfig,
    BotInstanceState,
    BotInstanceStatus,
    BotOperationResult,
    BotStatus,
)
from src.shared.credentials_cipher import (
    CredentialDecryptionError,
    open_config_secrets,
    seal_config_secrets,
)
from src.shared.live_risk_controls import assert_supported_live_risk_controls
from src.infrastructure.persistence.repository import UnitOfWork
from src.infrastructure.use_cases.async_job_manager import async_job_manager


class BotInstanceManager:
    """Manages multiple bot instances with isolated state and configuration"""

    CONFIG_SCHEMA_VERSION = 2

    ACTIVE_RUNTIME_STATUSES = {
        BotStatus.RUNNING,
        BotStatus.STARTING,
        BotStatus.STOPPING,
        BotStatus.DEGRADED,
        BotStatus.RECOVERING,
        BotStatus.SAFEGUARDED,
    }

    def __init__(
        self, state_dir: str = "./bot_states", max_instances: Optional[int] = None
    ):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.max_instances = self._resolve_max_instances(max_instances)

        # In-memory instance tracking
        self.instances: Dict[str, BotInstanceState] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.log_handles: Dict[str, TextIO] = {}
        self.instance_locks: Dict[str, asyncio.Lock] = {}
        self.status_event_publisher: Optional[
            Callable[[Dict[str, object]], Awaitable[None]]
        ] = None
        self.recovery_diagnostics: Dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "source": "none",
            "attempted": 0,
            "loaded": 0,
            "skipped": 0,
            "skipped_instances": [],
            "live_auto_recovery": {},
            "last_error": None,
        }
        self._db_sync_backoff_until_monotonic = 0.0
        self._db_sync_backoff_notice_after_monotonic = 0.0

        # Load existing instances from disk
        self._load_existing_instances()

    @staticmethod
    def _read_positive_float_env(name: str, default: float) -> float:
        raw = os.getenv(name, "").strip()
        if not raw:
            return max(0.0, float(default))
        try:
            parsed = float(raw)
        except ValueError:
            logger.warning("Invalid {}='{}'; using default {}", name, raw, default)
            return max(0.0, float(default))
        return max(0.0, parsed)

    @staticmethod
    def _looks_like_pool_overload(exc: BaseException) -> bool:
        message = str(exc).lower()
        return "queuepool limit" in message or (
            "connection timed out" in message and "sqlalche.me/e/20/3o7r" in message
        )

    def _db_sync_backoff_active(self) -> bool:
        return time.monotonic() < self._db_sync_backoff_until_monotonic

    def _activate_db_sync_backoff(self, exc: BaseException) -> None:
        cooldown_seconds = self._read_positive_float_env(
            "BOT_DB_SYNC_COOLDOWN_SECONDS",
            20.0,
        )
        log_every_seconds = self._read_positive_float_env(
            "BOT_DB_SYNC_BACKOFF_LOG_EVERY_SECONDS",
            15.0,
        )
        now = time.monotonic()
        self._db_sync_backoff_until_monotonic = now + cooldown_seconds
        self._db_sync_backoff_notice_after_monotonic = now + log_every_seconds
        logger.warning(
            "Activating bot manager DB sync cooldown for {:.1f}s after persistence overload: {}",
            cooldown_seconds,
            exc,
        )

    @staticmethod
    def _resolved_environment() -> str:
        return (
            (
                os.getenv("ENVIRONMENT")
                or os.getenv("APP_ENV")
                or os.getenv("APP_CONFIG_ENV")
                or "development"
            )
            .strip()
            .lower()
        )

    @classmethod
    def _is_dev_like_environment(cls) -> bool:
        return cls._resolved_environment() in {
            "development",
            "dev",
            "test",
            "testing",
            "local",
        }

    @classmethod
    def _resolve_max_instances(cls, configured_max_instances: Optional[int]) -> int:
        """Resolve runtime instance cap.

        - Explicit constructor value wins.
        - BOT_MAX_INSTANCES env override wins next.
        - Dev/test/local defaults to unlimited (0).
        - Production-like defaults to 10.
        """
        if configured_max_instances is not None:
            return int(configured_max_instances)

        raw_env = os.getenv("BOT_MAX_INSTANCES", "").strip()
        if raw_env:
            try:
                return int(raw_env)
            except ValueError:
                logger.warning(
                    "Invalid BOT_MAX_INSTANCES value '{}' ; falling back to environment default",
                    raw_env,
                )

        if cls._is_dev_like_environment():
            return 0
        return 10

    def _get_instance_lock(self, instance_id: str) -> asyncio.Lock:
        lock = self.instance_locks.get(instance_id)
        if lock is None:
            lock = asyncio.Lock()
            self.instance_locks[instance_id] = lock
        return lock

    @staticmethod
    def _db_persistence_enabled() -> bool:
        if any(
            bool(os.getenv(name, "").strip())
            for name in (
                "BOT_DATABASE_URL",
                "DATABASE_URL",
                "BOT_DB_HOST",
                "DB_HOST",
            )
        ):
            return True
        return getattr(db.get_session, "__self__", None) is not db

    def set_status_event_publisher(
        self,
        publisher: Optional[Callable[[Dict[str, object]], Awaitable[None]]],
    ):
        """Register async publisher for strategy runtime status events."""
        self.status_event_publisher = publisher

    def _load_existing_instances(self):
        """Load bot instances from the database only."""
        self.recovery_diagnostics.update(
            {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "source": "none",
                "attempted": 0,
                "loaded": 0,
                "skipped": 0,
                "skipped_instances": [],
                "live_auto_recovery": {},
                "last_error": None,
            }
        )
        loaded_from_db = self._load_existing_instances_from_db()
        if loaded_from_db is not None:
            self.recovery_diagnostics["source"] = "database"
            self.recovery_diagnostics["loaded"] = loaded_from_db
            self.recovery_diagnostics["completed_at"] = datetime.now(
                timezone.utc
            ).isoformat()
            logger.info(
                "Loaded {} existing bot instances from database", loaded_from_db
            )
            return

        self.recovery_diagnostics["source"] = "database_unavailable"
        self.recovery_diagnostics["completed_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        logger.warning(
            "Bot instance DB recovery failed; DB-backed runtime config is required"
        )

    def _record_recovery_skip(self, instance_id: str, reason: str):
        skipped_instances = self.recovery_diagnostics.setdefault(
            "skipped_instances", []
        )
        if isinstance(skipped_instances, list):
            skipped_instances.append({"instance_id": instance_id, "reason": reason})
        self.recovery_diagnostics["skipped"] = (
            int(self.recovery_diagnostics.get("skipped", 0)) + 1
        )

    @staticmethod
    def _env_flag(name: str, default: bool = False) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _live_auto_recovery_enabled(cls) -> bool:
        return cls._env_flag("BOT_AUTO_RECOVER_LIVE_RUNTIMES", default=False)

    @classmethod
    def _live_auto_recovery_allows_mainnet(cls) -> bool:
        return cls._env_flag("BOT_AUTO_RECOVER_LIVE_MAINNET", default=False)

    @staticmethod
    def _dev_invalid_recovery_cleanup_enabled(record) -> bool:
        """Allow stale invalid DB rows to be purged only in non-production runtimes."""
        if os.getenv("BOT_DEV_CLEAN_INVALID_BOT_ROWS", "true").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return False

        environment = (
            (
                os.getenv("ENVIRONMENT")
                or os.getenv("APP_ENV")
                or os.getenv("APP_CONFIG_ENV")
                or "development"
            )
            .strip()
            .lower()
        )
        if environment not in {"development", "dev", "test", "testing", "local"}:
            return False

        network = str(getattr(record, "network", "")).strip().lower()
        if network != "mainnet":
            return True

        instance_id = str(getattr(record, "instance_id", "")).strip().lower()
        return any(marker in instance_id for marker in ("test", "fixture", "dummy"))

    def _delete_invalid_recovery_record_if_dev(
        self, session, record, reason: str
    ) -> bool:
        """Delete unrecoverable dev/test bot rows so recovery warnings do not repeat."""
        if not self._dev_invalid_recovery_cleanup_enabled(record):
            return False

        try:
            stale_ids = "SELECT id FROM bot_instances WHERE instance_id = :instance_id"
            for table_name, column_name in (
                ("jobs", "bot_id"),
                ("trades", "bot_id"),
                ("event_logs", "bot_instance_id"),
                ("positions_realtime", "bot_instance_id"),
                ("market_data_realtime", "bot_instance_id"),
                ("bot_stats_realtime", "bot_instance_id"),
                ("alerts_realtime", "bot_instance_id"),
            ):
                session.execute(
                    text(
                        f"DELETE FROM {table_name} "
                        f"WHERE {column_name} IN ({stale_ids})"
                    ),
                    {"instance_id": record.instance_id},
                )
            session.execute(
                text("DELETE FROM bot_instances WHERE instance_id = :instance_id"),
                {"instance_id": record.instance_id},
            )
            session.commit()
            logger.warning(
                "Deleted invalid dev bot instance {} during DB recovery because {}",
                record.instance_id,
                reason,
            )
            return True
        except Exception as exc:
            logger.warning(
                "Failed to delete invalid dev bot instance {} during DB recovery: {}",
                record.instance_id,
                exc,
            )
            session.rollback()
            return False

    def _load_existing_instances_from_db(self) -> Optional[int]:
        """Hydrate manager state from persisted bot instances in the database."""
        if not self._db_persistence_enabled():
            logger.info(
                "Skipping bot instance DB recovery: no explicit database target configured"
            )
            return 0
        session = None
        try:
            session = db.get_session()
            loaded = 0

            # Use a raw query here instead of ORM model hydration so legacy
            # lowercase status values (e.g. "error") do not raise enum decode
            # errors before we can normalize them.
            rows = session.execute(text("""
                    SELECT instance_id,
                           network,
                           strategy,
                           config,
                           process_id,
                           created_at,
                           updated_at,
                           status
                    FROM bot_instances
                    """)).mappings()

            for row in rows:
                record = SimpleNamespace(**dict(row))
                self.recovery_diagnostics["attempted"] = (
                    int(self.recovery_diagnostics.get("attempted", 0)) + 1
                )
                config = self._build_instance_config_from_record(record)
                if config is None:
                    self._delete_invalid_recovery_record_if_dev(
                        session,
                        record,
                        "persisted credentials are incomplete",
                    )
                    continue

                status = self._coerce_record_status(record.status)
                payload = self._coerce_record_config_payload(
                    getattr(record, "config", None)
                )
                runtime_state = payload.get("runtime_state") or {}
                process_info = {}
                if getattr(record, "process_id", None) is not None:
                    process_info["pid"] = record.process_id
                if runtime_state.get("last_error"):
                    process_info["last_error"] = runtime_state["last_error"]
                if runtime_state.get("exit_code") is not None:
                    process_info["exit_code"] = runtime_state["exit_code"]

                self.instances[record.instance_id] = BotInstanceState(
                    instance_id=record.instance_id,
                    config=config,
                    status=status,
                    process_info=process_info,
                    trading_stats=runtime_state.get("trading_stats") or {},
                    created_at=record.created_at,
                    last_update=record.updated_at,
                )

                loaded += 1

            self.recovery_diagnostics["loaded"] = loaded
            return loaded
        except Exception as exc:
            logger.warning("Failed to load bot instances from database: {}", exc)
            self.recovery_diagnostics["last_error"] = str(exc)
            return None
        finally:
            if session is not None:
                session.close()

    def _load_existing_instances_from_disk(self):
        """Load bot instances from the legacy compatibility snapshot on disk."""
        state_file = self.state_dir / "instances.json"
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
                    for instance_data in data.get("instances", []):
                        self.recovery_diagnostics["attempted"] = (
                            int(self.recovery_diagnostics.get("attempted", 0)) + 1
                        )
                        # Reconstruct instance state (without active processes)
                        instance_id = instance_data["instance_id"]
                        self.instances[instance_id] = BotInstanceState(
                            instance_id=instance_id,
                            config=BotInstanceConfig.model_validate(
                                instance_data["config"]
                            ),
                            status=BotStatus.STOPPED,
                            process_info={},
                            trading_stats=instance_data.get("trading_stats", {}),
                            created_at=datetime.fromisoformat(
                                instance_data["created_at"]
                            ),
                            last_update=datetime.now(timezone.utc),
                        )
                self.recovery_diagnostics["loaded"] = len(self.instances)
                logger.info(
                    "Loaded {} existing bot instances from disk snapshot",
                    len(self.instances),
                )
            except Exception as e:
                logger.error(f"Error loading instances: {e}")
                self.recovery_diagnostics["last_error"] = str(e)

    @staticmethod
    def _coerce_record_config_payload(raw_config: Any) -> dict[str, Any]:
        """Normalize persisted bot config payloads from dict or JSON-string forms.

        Sealed credential/telegram envelopes are decrypted so downstream callers
        always observe plaintext secrets. Decryption failures degrade gracefully
        (the raw payload is returned with envelopes intact) so a single unopenable
        row cannot abort recovery or DB sync; such rows are then skipped by the
        credential-completeness checks downstream.
        """
        if isinstance(raw_config, dict):
            normalized: dict[str, Any] = dict(raw_config)
        elif isinstance(raw_config, str):
            raw = raw_config.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError):
                return {}
            if not isinstance(parsed, dict):
                return {}
            normalized = dict(parsed)
        else:
            return {}

        try:
            return open_config_secrets(normalized)
        except CredentialDecryptionError as exc:
            logger.warning(
                "Could not decrypt sealed bot config payload; returning raw "
                "payload (credentials will be treated as incomplete): {}",
                exc,
            )
            return normalized

    def _build_instance_config_from_record(self, record) -> Optional[BotInstanceConfig]:
        """Reconstruct the runtime config shape from the persisted DB payload."""
        payload = self._coerce_record_config_payload(getattr(record, "config", None))
        credentials_payload = payload.get("credentials") or {}
        trading_payload = payload.get("trading_params") or {}
        backtesting_payload = payload.get("backtesting_params") or None
        telegram_payload = payload.get("telegram") or None

        address = str(credentials_payload.get("address") or "").strip()
        mnemonic = str(credentials_payload.get("mnemonic") or "").strip()
        if not address or not mnemonic:
            skip_reason = (
                "persisted credentials are incomplete; recreate or resync the runtime instance "
                "so backend/bot metadata stores credentials in config"
            )
            logger.warning(
                "Skipping bot instance {} during DB recovery because {}",
                record.instance_id,
                skip_reason,
            )
            self._record_recovery_skip(record.instance_id, skip_reason)
            return None

        if "is_testnet" not in trading_payload:
            trading_payload["is_testnet"] = (
                str(record.network).strip().lower() != "mainnet"
            )
        if (
            "strategy" not in trading_payload
            or not str(trading_payload["strategy"]).strip()
        ):
            trading_payload["strategy"] = record.strategy

        config_payload = {
            "instance_id": record.instance_id,
            "instance_name": payload.get("instance_name") or record.instance_id,
            "credentials": {
                "chain_id": credentials_payload.get("chain_id", "dydx-testnet-4"),
                "address": address,
                "mnemonic": mnemonic,
            },
            "trading_params": trading_payload,
        }
        if telegram_payload:
            config_payload["telegram"] = telegram_payload
        if backtesting_payload:
            config_payload["backtesting_params"] = backtesting_payload

        return BotInstanceConfig.model_validate(config_payload)

    def _coerce_record_status(self, raw_status) -> BotStatus:
        """Normalize persisted status values into API-facing bot status values."""
        if hasattr(raw_status, "value"):
            value = raw_status.value
        else:
            value = str(raw_status)

        try:
            return BotStatus(str(value).strip().lower())
        except ValueError:
            return BotStatus.STOPPED

    def _db_status_for_instance(self, instance: BotInstanceState) -> BotStatusEnum:
        """Translate manager status into the SQLAlchemy enum used by persisted rows."""
        return BotStatusEnum[instance.status.name]

    @staticmethod
    def _runtime_contract_payload(instance: BotInstanceState) -> dict[str, Any]:
        """Build the canonical runtime config payload persisted in bot_instances.config."""
        return {
            "instance_name": instance.config.instance_name,
            "credentials": instance.config.credentials.model_dump(),
            "telegram": (
                instance.config.telegram.model_dump()
                if instance.config.telegram
                else {}
            ),
            "trading_params": instance.config.trading_params.model_dump(),
            "backtesting_params": (
                instance.config.backtesting_params.model_dump()
                if instance.config.backtesting_params
                else {}
            ),
        }

    @staticmethod
    def _config_payload_hash(payload: dict[str, Any]) -> str:
        """Compute deterministic hash for runtime-config drift and cache validation."""
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _build_config_meta(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Attach schema/hash metadata to persisted runtime config payloads."""
        return {
            "schema_version": self.CONFIG_SCHEMA_VERSION,
            "hash_algorithm": "sha256",
            "payload_hash": self._config_payload_hash(payload),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _seal_payload_for_storage(payload: dict[str, Any]) -> dict[str, Any]:
        """Encrypt secret-bearing blocks of a runtime config before persistence.

        Thin wrapper over :func:`seal_config_secrets` so the persistence boundary
        is named explicitly at each write site. With no encryption key
        provisioned (and encryption not required), the payload is returned
        unchanged for backward-compatible plaintext storage.
        """
        return seal_config_secrets(payload)

    def _ensure_instance_record(self, instance: BotInstanceState):
        """Create the DB row for an instance if API orchestration has not done it yet."""
        if not self._db_persistence_enabled():
            return
        session = None
        try:
            session = db.get_session()
            uow = UnitOfWork(session)
            if uow.bots.get_by_instance_id(instance.instance_id) is not None:
                return
            runtime_payload = self._runtime_contract_payload(instance)
            uow.bots.create_bot(
                instance_id=instance.instance_id,
                network=(
                    "testnet"
                    if instance.config.trading_params.is_testnet
                    else "mainnet"
                ),
                strategy=instance.config.trading_params.strategy,
                config=self._seal_payload_for_storage(
                    {
                        **runtime_payload,
                        "config_meta": self._build_config_meta(runtime_payload),
                    }
                ),
            )
        except Exception as exc:
            logger.warning(
                "Failed to ensure bot instance DB row for {}: {}",
                instance.instance_id,
                exc,
            )
            if session is not None:
                session.rollback()
        finally:
            if session is not None:
                session.close()

    def _record_runtime_event(
        self,
        instance_id: str,
        event_type: str,
        severity: str,
        message: str,
        details: Optional[dict] = None,
    ):
        """Persist runtime events so failures survive process restarts."""
        if not self._db_persistence_enabled():
            return
        session = None
        try:
            session = db.get_session()
            uow = UnitOfWork(session)
            bot = uow.bots.get_by_instance_id(instance_id)
            if bot is None:
                return
            uow.events.log_event(
                bot.id,
                event_type,
                severity,
                message,
                details=details,
            )
        except Exception as exc:
            logger.warning(
                "Failed to record runtime event for {}: {}", instance_id, exc
            )
            if session is not None:
                session.rollback()
        finally:
            if session is not None:
                session.close()

    def _persist_instances_to_db(self):
        """Sync runtime state back into the database so it stays authoritative across restarts."""
        if not self._db_persistence_enabled():
            return

        if self._db_sync_backoff_active():
            now = time.monotonic()
            if now >= self._db_sync_backoff_notice_after_monotonic:
                remaining = max(0.0, self._db_sync_backoff_until_monotonic - now)
                log_every_seconds = self._read_positive_float_env(
                    "BOT_DB_SYNC_BACKOFF_LOG_EVERY_SECONDS",
                    15.0,
                )
                self._db_sync_backoff_notice_after_monotonic = now + log_every_seconds
                logger.warning(
                    "Skipping bot manager DB sync due to active overload cooldown ({:.1f}s remaining)",
                    remaining,
                )
            return

        session = None
        try:
            session = db.get_session()
            uow = UnitOfWork(session)
            existing = {record.instance_id: record for record in uow.bots.get_all()}

            for instance_id, instance in self.instances.items():
                record = existing.get(instance_id)
                if record is None:
                    continue

                record.status = self._db_status_for_instance(instance)
                record.process_id = instance.process_info.get("pid")
                record.network = (
                    "testnet"
                    if instance.config.trading_params.is_testnet
                    else "mainnet"
                )
                record.strategy = instance.config.trading_params.strategy
                persisted_config = self._coerce_record_config_payload(
                    getattr(record, "config", None)
                )
                runtime_payload = self._runtime_contract_payload(instance)
                started_at_value = instance.process_info.get("started_at")
                stopped_at_value = instance.process_info.get("stopped_at")
                persisted_config.update(
                    {
                        **runtime_payload,
                        "config_meta": self._build_config_meta(runtime_payload),
                        "runtime_state": {
                            "status": instance.status.value,
                            "process_id": instance.process_info.get("pid"),
                            "last_error": instance.process_info.get("last_error"),
                            "exit_code": instance.process_info.get("exit_code"),
                            "started_at": (
                                started_at_value.isoformat()
                                if isinstance(started_at_value, datetime)
                                else started_at_value
                            ),
                            "stopped_at": (
                                stopped_at_value.isoformat()
                                if isinstance(stopped_at_value, datetime)
                                else stopped_at_value
                            ),
                            "last_update": instance.last_update.isoformat(),
                            "trading_stats": instance.trading_stats,
                        },
                    }
                )
                record.config = self._seal_payload_for_storage(persisted_config)

            session.commit()
            if self._db_sync_backoff_until_monotonic > 0.0:
                logger.info("Bot manager DB sync recovered; clearing overload cooldown")
            self._db_sync_backoff_until_monotonic = 0.0
            self._db_sync_backoff_notice_after_monotonic = 0.0
        except Exception as exc:
            logger.warning("Failed to sync bot manager state to database: {}", exc)
            if self._looks_like_pool_overload(exc):
                self._activate_db_sync_backoff(exc)
            if session is not None:
                session.rollback()
        finally:
            if session is not None:
                session.close()

    def _save_instances_state(self):
        """Persist instance state to DB, with opt-in legacy snapshot for debugging."""
        self._persist_instances_to_db()

        if os.getenv(
            "BOT_WRITE_LEGACY_STATE_SNAPSHOT", "false"
        ).strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return

        state_file = self.state_dir / "instances.json"
        try:
            data = {
                "instances": [
                    {
                        "instance_id": state.instance_id,
                        "config": state.config.model_dump(),
                        "trading_stats": state.trading_stats,
                        "created_at": state.created_at.isoformat(),
                        "last_update": state.last_update.isoformat(),
                    }
                    for state in self.instances.values()
                ],
                "last_saved": datetime.now(timezone.utc).isoformat(),
            }
            with open(state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Error saving legacy instance snapshot: {}", e)

    def _strategy_id_from_instance_id(self, instance_id: str) -> Optional[int]:
        """Extract strategy id from deterministic strategy runtime instance ids."""
        parts = instance_id.split("-")
        if (
            len(parts) == 3
            and parts[0] == "strategy"
            and parts[1].isdigit()
            and parts[2].isdigit()
        ):
            return int(parts[2])
        return None

    def _job_metadata(self, instance_id: str) -> Dict[str, Any]:
        instance = self.instances.get(instance_id)
        if instance is None:
            return {"bot_instance_id": instance_id}
        params = instance.config.trading_params
        return {
            "bot_instance_id": instance_id,
            "strategy_id": self._strategy_id_from_instance_id(instance_id),
            "strategy": params.strategy,
            "runtime_mode": "live",
            "environment": "testnet" if params.is_testnet else "mainnet",
            "subaccount": params.subaccount_number,
        }

    def _build_strategy_status_payload(
        self,
        instance_id: str,
        event: str = "status",
        last_error: Optional[str] = None,
    ) -> Optional[Dict[str, object]]:
        """Build websocket/frontend-compatible strategy runtime payload."""
        instance = self.instances.get(instance_id)
        if instance is None:
            return None

        strategy_id = self._strategy_id_from_instance_id(instance_id)
        if strategy_id is None:
            return None

        status = (
            instance.status.value
            if isinstance(instance.status, BotStatus)
            else str(instance.status)
        )
        network = "testnet" if instance.config.trading_params.is_testnet else "mainnet"
        updated_at = datetime.now(timezone.utc).isoformat()
        resolved_error = last_error or instance.process_info.get("last_error")

        payload: Dict[str, object] = {
            "type": "strategy_status",
            "event": event,
            "strategyId": strategy_id,
            "strategy_id": strategy_id,
            "instance_id": instance_id,
            "status": status,
            "bot_status": status,
            "updatedAt": updated_at,
            "updated_at": updated_at,
            "network": network,
            "process_id": instance.process_info.get("pid"),
        }
        if resolved_error:
            payload["lastError"] = str(resolved_error)
            payload["last_error"] = str(resolved_error)

        return payload

    async def _publish_strategy_status(
        self,
        instance_id: str,
        event: str = "status",
        last_error: Optional[str] = None,
        message: Optional[str] = None,
    ):
        """Publish status update for strategy-managed instances when configured."""
        if event in {"running", "heartbeat"}:
            self._mark_instance_liveness_verified(instance_id)

        if self.status_event_publisher is None:
            return

        payload = self._build_strategy_status_payload(
            instance_id,
            event=event,
            last_error=last_error,
        )
        if payload is None:
            return

        try:
            await self.status_event_publisher(payload)
        except Exception as exc:
            logger.warning(
                "Failed to publish strategy status for {}: {}", instance_id, exc
            )

    def get_strategy_status_snapshot(self) -> List[Dict[str, object]]:
        """Return current strategy runtime snapshot for websocket subscribers."""
        snapshot: List[Dict[str, object]] = []
        for instance_id in sorted(self.instances.keys()):
            payload = self._build_strategy_status_payload(instance_id, event="snapshot")
            if payload is not None:
                snapshot.append(payload)
        return snapshot

    def _get_instance_state_files(self, instance_id: str) -> Dict[str, Path]:
        """Get paths to instance-specific state files"""
        return {
            "bot_agents": self.state_dir / f"bot_agents_{instance_id}.json",
            "cointegrated_pairs": self.state_dir
            / f"cointegrated_pairs_{instance_id}.json",
            "log": self.state_dir / f"bot_{instance_id}.log",
        }

    def _open_instance_log(self, instance_id: str) -> TextIO:
        """Open per-instance log file handle used by subprocess stdout/stderr."""
        self._close_instance_log(instance_id)
        log_file = self._get_instance_state_files(instance_id)["log"]
        handle = open(log_file, "a", encoding="utf-8", buffering=1)
        self.log_handles[instance_id] = handle
        return handle

    def _close_instance_log(self, instance_id: str):
        """Close any open log file handle for an instance."""
        handle = self.log_handles.pop(instance_id, None)
        if handle is None:
            return
        try:
            handle.flush()
            handle.close()
        except Exception as exc:
            logger.warning("Failed to close log handle for {}: {}", instance_id, exc)

    def _read_recent_log_tail(self, instance_id: str, max_chars: int = 500) -> str:
        """Read the most recent log output for error reporting."""
        log_file = self._get_instance_state_files(instance_id)["log"]
        if not log_file.exists():
            return ""

        try:
            with open(log_file, "rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - max_chars))
                return handle.read().decode("utf-8", errors="ignore").strip()
        except Exception as exc:
            logger.warning("Failed to read log tail for {}: {}", instance_id, exc)
            return ""

    def _resolve_external_runtime_process(
        self, instance_id: str
    ) -> tuple[Optional[psutil.Process], Optional[str]]:
        """Probe a persisted runtime PID when the local subprocess handle was lost."""
        instance = self.instances.get(instance_id)
        if instance is None:
            return None, None
        if instance_id in self.processes:
            return None, None

        pid = instance.process_info.get("pid")
        if pid is None:
            return None, f"Runtime process for {instance_id} is not attached"

        try:
            normalized_pid = int(pid)
            process = psutil.Process(normalized_pid)
        except (TypeError, ValueError):
            return None, f"Stored runtime PID for {instance_id} is invalid"
        except psutil.NoSuchProcess:
            return None, f"Runtime process for {instance_id} is no longer running"

        try:
            cmdline = " ".join(process.cmdline())
        except (psutil.AccessDenied, psutil.ZombieProcess):
            cmdline = ""

        if cmdline and ("main_instance" not in cmdline or instance_id not in cmdline):
            return (
                None,
                f"Stored runtime PID {pid} for {instance_id} now belongs to a different process",
            )

        return process, None

    def _mark_instance_liveness_verified(
        self,
        instance_id: str,
        *,
        process_id: Optional[int] = None,
    ) -> bool:
        """Record a deterministic liveness heartbeat owned by the manager."""
        instance = self.instances.get(instance_id)
        if instance is None:
            return False

        now = datetime.now(timezone.utc)
        instance.last_heartbeat = now
        instance.last_update = now
        if process_id is not None:
            instance.process_info["pid"] = process_id
        if (
            instance.recovery_state in {"degraded", "recovering"}
            or instance.status == BotStatus.DEGRADED
        ):
            instance.recovery_state = None
            instance.recovery_reason = None
            if instance.status == BotStatus.DEGRADED:
                instance.status = BotStatus.RUNNING
        return True

    def _refresh_instance_liveness_from_process(self, instance_id: str) -> bool:
        """Verify attached or recovered worker process liveness without lifecycle events."""
        process = self.processes.get(instance_id)
        if process is not None:
            if process.poll() is None:
                self._mark_instance_liveness_verified(
                    instance_id,
                    process_id=getattr(process, "pid", None),
                )
                return True
            return False

        external_process, probe_error = self._resolve_external_runtime_process(
            instance_id
        )
        if external_process is None:
            if probe_error:
                logger.debug(
                    "Unable to verify liveness for {}: {}", instance_id, probe_error
                )
            return False

        try:
            if (
                external_process.is_running()
                and external_process.status() != psutil.STATUS_ZOMBIE
            ):
                self._mark_instance_liveness_verified(
                    instance_id,
                    process_id=external_process.pid,
                )
                return True
        except psutil.AccessDenied:
            self._mark_instance_liveness_verified(
                instance_id,
                process_id=external_process.pid,
            )
            return True
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return False
        return False

    def _mark_instance_error(
        self,
        instance_id: str,
        message: str,
        exit_code: Optional[int] = None,
    ) -> bool:
        """Transition an instance into ERROR state and capture failure details."""
        instance = self.instances.get(instance_id)
        if instance is None:
            return False

        status_changed = instance.status != BotStatus.ERROR
        instance.status = BotStatus.ERROR
        instance.last_update = datetime.now(timezone.utc)
        instance.process_info["stopped_at"] = datetime.now(timezone.utc)
        if exit_code is not None:
            instance.process_info["exit_code"] = exit_code
        if message:
            instance.process_info["last_error"] = message
        instance.process_info.pop("pid", None)

        self.processes.pop(instance_id, None)
        self._close_instance_log(instance_id)
        self._save_instances_state()
        if status_changed and message:
            self._record_runtime_event(
                instance_id,
                "bot_runtime_error",
                "error",
                message,
                details={"exit_code": exit_code},
            )

        return status_changed

    async def create_instance(self, config: BotInstanceConfig) -> BotOperationResult:
        """Create new bot instance"""
        try:
            assert_supported_live_risk_controls(config.trading_params.model_dump())

            # Validate instance limit
            if self.max_instances > 0 and len(self.instances) >= self.max_instances:
                return BotOperationResult(
                    success=False,
                    message=f"Maximum instances limit reached ({self.max_instances})",
                    instance_id=config.instance_id,
                    status=BotStatus.ERROR,
                )

            # Check if instance already exists
            if config.instance_id in self.instances:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {config.instance_id} already exists",
                    instance_id=config.instance_id,
                    status=BotStatus.ERROR,
                )

            # Create instance state
            instance_state = BotInstanceState(
                instance_id=config.instance_id,
                config=config,
                status=BotStatus.STOPPED,
                process_info={},
                trading_stats={},
                created_at=datetime.now(timezone.utc),
                last_update=datetime.now(timezone.utc),
            )

            # Store instance
            self.instances[config.instance_id] = instance_state
            self._ensure_instance_record(instance_state)
            self._save_instances_state()

            logger.info(f"Created bot instance: {config.instance_id}")
            await self._publish_strategy_status(config.instance_id, event="created")

            return BotOperationResult(
                success=True,
                message=f"Bot instance {config.instance_id} created successfully",
                instance_id=config.instance_id,
                status=BotStatus.STOPPED,
            )

        except Exception as e:
            logger.error(f"Error creating instance {config.instance_id}: {e}")
            return BotOperationResult(
                success=False,
                message=f"Error creating instance: {str(e)}",
                instance_id=config.instance_id,
                status=BotStatus.ERROR,
            )

    async def start_instance(self, instance_id: str) -> BotOperationResult:
        """Start bot instance"""
        lock = self._get_instance_lock(instance_id)
        if lock.locked():
            return BotOperationResult(
                success=False,
                message=f"Instance {instance_id} already has a lifecycle operation in progress",
                instance_id=instance_id,
                status=BotStatus.STARTING,
            )

        async with lock:
            return await self._start_instance_locked(instance_id)

    async def _start_instance_locked(self, instance_id: str) -> BotOperationResult:
        """Start bot instance while holding the per-instance lifecycle lock."""
        lifecycle_job_id: Optional[str] = None
        try:
            if instance_id not in self.instances:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {instance_id} not found",
                    instance_id=instance_id,
                    status=BotStatus.ERROR,
                )

            instance = self.instances[instance_id]
            assert_supported_live_risk_controls(
                instance.config.trading_params.model_dump()
            )

            if instance.status in self.ACTIVE_RUNTIME_STATUSES:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {instance_id} is already {instance.status.value}",
                    instance_id=instance_id,
                    status=instance.status,
                )

            lifecycle_job_id = async_job_manager.create_job(
                job_type="live_runtime",
                bot_instance_id=instance_id,
                parameters={"action": "start"},
                metadata=self._job_metadata(instance_id),
            )

            # Update status
            instance.status = BotStatus.STARTING
            instance.last_update = datetime.now(timezone.utc)
            instance.process_info.pop("last_error", None)
            self._save_instances_state()
            await self._publish_strategy_status(instance_id, event="starting")

            # Get instance files
            files = self._get_instance_state_files(instance_id)
            bot_root = Path(__file__).resolve().parents[1]

            # Prepare environment for bot process
            bot_env = os.environ.copy()
            bot_env.update(
                {
                    "BOT_INSTANCE_ID": instance_id,
                    "BOT_AGENTS_FILE": str(files["bot_agents"]),
                    "BOT_PAIRS_FILE": str(files["cointegrated_pairs"]),
                }
            )
            existing_pythonpath = bot_env.get("PYTHONPATH", "").strip()
            pythonpath_entries = [str(bot_root)]
            if existing_pythonpath:
                pythonpath_entries.append(existing_pythonpath)
            bot_env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
            if instance.config.telegram:
                bot_env["TELEGRAM_BOT_TOKEN"] = instance.config.telegram.token or ""
                bot_env["TELEGRAM_CHAT_ID"] = instance.config.telegram.chat_id or ""

            # Start bot process
            bot_python = os.getenv("BOT_PYTHON_PATH") or sys.executable
            cmd = [
                bot_python,
                "-m",
                "src.main_instance",
                "--instance-id",
                instance_id,
            ]
            log_handle = self._open_instance_log(instance_id)

            process = subprocess.Popen(
                cmd,
                env=bot_env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                cwd=bot_root,
                text=True,
                bufsize=1,
            )
            if lifecycle_job_id:
                async_job_manager.mark_running(lifecycle_job_id, process_id=process.pid)

            # Store process reference
            self.processes[instance_id] = process

            exit_code = process.poll()
            if exit_code is None:
                startup_grace = float(os.getenv("BOT_STARTUP_GRACE_SECONDS", "0.2"))
                await asyncio.sleep(max(0.0, startup_grace))
                exit_code = process.poll()
            if exit_code is not None:
                log_tail = self._read_recent_log_tail(instance_id)
                error_message = f"Instance {instance_id} exited during startup (exit_code={exit_code})"
                if log_tail:
                    error_message = f"{error_message}: {log_tail.splitlines()[-1]}"

                self._mark_instance_error(
                    instance_id, error_message, exit_code=exit_code
                )
                if lifecycle_job_id:
                    async_job_manager.mark_failed(lifecycle_job_id, error_message)
                await self._publish_strategy_status(
                    instance_id,
                    event="error",
                    last_error=error_message,
                )
                return BotOperationResult(
                    success=False,
                    message=error_message,
                    instance_id=instance_id,
                    status=BotStatus.ERROR,
                    error=error_message,
                )

            # Update instance state
            instance.status = BotStatus.RUNNING
            instance.process_info = {
                "pid": process.pid,
                "started_at": datetime.now(timezone.utc),
                "cmd": " ".join(cmd),
                "log_path": str(files["log"]),
            }
            instance.last_update = datetime.now(timezone.utc)

            self._save_instances_state()

            logger.info(f"Started bot instance {instance_id} with PID {process.pid}")
            if lifecycle_job_id:
                async_job_manager.mark_completed(
                    lifecycle_job_id,
                    result={"process_id": process.pid, "status": "running"},
                )
            await self._publish_strategy_status(instance_id, event="running")

            return BotOperationResult(
                success=True,
                message=f"Bot instance {instance_id} started successfully",
                instance_id=instance_id,
                status=BotStatus.RUNNING,
                data={"process_id": process.pid},
            )

        except Exception as e:
            logger.error(f"Error starting instance {instance_id}: {e}")
            if lifecycle_job_id:
                async_job_manager.mark_failed(lifecycle_job_id, e)
            if instance_id in self.instances:
                self._mark_instance_error(instance_id, str(e))
                await self._publish_strategy_status(
                    instance_id,
                    event="error",
                    last_error=str(e),
                )
            return BotOperationResult(
                success=False,
                message=f"Error starting instance: {str(e)}",
                instance_id=instance_id,
                status=BotStatus.ERROR,
            )

    async def stop_instance(
        self, instance_id: str, force: bool = False
    ) -> BotOperationResult:
        """Stop bot instance"""
        lock = self._get_instance_lock(instance_id)
        if lock.locked():
            return BotOperationResult(
                success=False,
                message=f"Instance {instance_id} already has a lifecycle operation in progress",
                instance_id=instance_id,
                status=BotStatus.STOPPING,
            )

        async with lock:
            return await self._stop_instance_locked(instance_id, force=force)

    async def _stop_instance_locked(
        self, instance_id: str, force: bool = False
    ) -> BotOperationResult:
        """Stop bot instance while holding the per-instance lifecycle lock."""
        lifecycle_job_id: Optional[str] = None
        try:
            if instance_id not in self.instances:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {instance_id} not found",
                    instance_id=instance_id,
                    status=BotStatus.ERROR,
                )

            instance = self.instances[instance_id]

            if instance.status == BotStatus.STOPPED:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {instance_id} is already stopped",
                    instance_id=instance_id,
                    status=BotStatus.STOPPED,
                )

            lifecycle_job_id = async_job_manager.create_job(
                job_type="live_runtime",
                bot_instance_id=instance_id,
                parameters={"action": "stop", "force": force},
                metadata=self._job_metadata(instance_id),
            )
            async_job_manager.mark_running(
                lifecycle_job_id, process_id=instance.process_info.get("pid")
            )

            # Update status
            instance.status = BotStatus.STOPPING
            instance.last_update = datetime.now(timezone.utc)
            self._save_instances_state()
            await self._publish_strategy_status(instance_id, event="stopping")

            # Stop process if running
            if instance_id in self.processes:
                process = self.processes[instance_id]

                if process.poll() is None:  # Process is still running
                    if force:
                        process.kill()
                        try:
                            await asyncio.to_thread(process.wait, timeout=10)
                        except subprocess.TimeoutExpired:
                            logger.warning(
                                "Killed bot instance {} but process did not reap within timeout",
                                instance_id,
                            )
                        logger.info(f"Force killed bot instance {instance_id}")
                    else:
                        process.terminate()
                        logger.info(
                            f"Gracefully terminating bot instance {instance_id}"
                        )

                        # Wait for graceful shutdown
                        try:
                            await asyncio.to_thread(process.wait, timeout=30)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            try:
                                await asyncio.to_thread(process.wait, timeout=10)
                            except subprocess.TimeoutExpired:
                                logger.warning(
                                    "Force killed bot instance {} after graceful timeout but process did not reap",
                                    instance_id,
                                )
                            logger.warning(
                                f"Force killed bot instance {instance_id} after timeout"
                            )

                # Remove process reference
                del self.processes[instance_id]
            else:
                external_process, probe_error = self._resolve_external_runtime_process(
                    instance_id
                )
                if external_process is not None:
                    try:
                        if force:
                            external_process.kill()
                            try:
                                await asyncio.to_thread(
                                    external_process.wait, timeout=10
                                )
                            except psutil.TimeoutExpired:
                                logger.warning(
                                    "Killed recovered bot instance {} but process did not reap within timeout",
                                    instance_id,
                                )
                            logger.info(
                                "Force killed recovered bot instance {} (PID {})",
                                instance_id,
                                external_process.pid,
                            )
                        else:
                            external_process.terminate()
                            logger.info(
                                "Gracefully terminating recovered bot instance {} (PID {})",
                                instance_id,
                                external_process.pid,
                            )
                            try:
                                await asyncio.to_thread(
                                    external_process.wait, timeout=30
                                )
                            except psutil.TimeoutExpired:
                                external_process.kill()
                                try:
                                    await asyncio.to_thread(
                                        external_process.wait, timeout=10
                                    )
                                except psutil.TimeoutExpired:
                                    logger.warning(
                                        "Force killed recovered bot instance {} after graceful timeout but process did not reap",
                                        instance_id,
                                    )
                                logger.warning(
                                    "Force killed recovered bot instance {} after timeout",
                                    instance_id,
                                )
                    except psutil.NoSuchProcess:
                        logger.info(
                            "Recovered runtime process already exited for {} before stop completed",
                            instance_id,
                        )
                elif probe_error:
                    logger.warning(
                        "Stop requested for {} but {}", instance_id, probe_error
                    )

            # Update instance state
            instance.status = BotStatus.STOPPED
            instance.process_info["stopped_at"] = datetime.now(timezone.utc)
            instance.process_info.pop("pid", None)
            instance.process_info.pop("last_error", None)
            instance.last_update = datetime.now(timezone.utc)
            self._close_instance_log(instance_id)

            self._save_instances_state()

            logger.info(f"Stopped bot instance: {instance_id}")
            if lifecycle_job_id:
                async_job_manager.mark_completed(
                    lifecycle_job_id,
                    result={"status": "stopped", "force": force},
                )
            await self._publish_strategy_status(instance_id, event="stopped")

            return BotOperationResult(
                success=True,
                message=f"Bot instance {instance_id} stopped successfully",
                instance_id=instance_id,
                status=BotStatus.STOPPED,
            )

        except Exception as e:
            logger.error(f"Error stopping instance {instance_id}: {e}")
            if lifecycle_job_id:
                async_job_manager.mark_failed(lifecycle_job_id, e)
            self._mark_instance_error(instance_id, str(e))
            await self._publish_strategy_status(
                instance_id,
                event="error",
                last_error=str(e),
            )
            return BotOperationResult(
                success=False,
                message=f"Error stopping instance: {str(e)}",
                instance_id=instance_id,
                status=BotStatus.ERROR,
            )

    async def delete_instance(self, instance_id: str) -> BotOperationResult:
        """Delete bot instance and cleanup files"""
        lock = self._get_instance_lock(instance_id)
        if lock.locked():
            return BotOperationResult(
                success=False,
                message=f"Instance {instance_id} already has a lifecycle operation in progress",
                instance_id=instance_id,
                status=BotStatus.STOPPING,
            )

        async with lock:
            return await self._delete_instance_locked(instance_id)

    async def _delete_instance_locked(self, instance_id: str) -> BotOperationResult:
        """Delete bot instance and cleanup files while holding per-instance lifecycle lock."""
        try:
            # Stop instance first if running
            if (
                instance_id in self.instances
                and self.instances[instance_id].status in self.ACTIVE_RUNTIME_STATUSES
            ):
                stop_result = await self.stop_instance(instance_id, force=True)
                if not stop_result.success:
                    return stop_result

            # Remove from memory
            if instance_id in self.instances:
                del self.instances[instance_id]
            self.processes.pop(instance_id, None)
            self.instance_locks.pop(instance_id, None)
            self._close_instance_log(instance_id)

            # Cleanup state files
            files = self._get_instance_state_files(instance_id)
            for file_path in files.values():
                if file_path.exists():
                    file_path.unlink()

            self._save_instances_state()

            logger.info(f"Deleted bot instance: {instance_id}")

            return BotOperationResult(
                success=True,
                message=f"Bot instance {instance_id} deleted successfully",
                instance_id=instance_id,
                status=BotStatus.STOPPED,
            )

        except Exception as e:
            logger.error(f"Error deleting instance {instance_id}: {e}")
            return BotOperationResult(
                success=False,
                message=f"Error deleting instance: {str(e)}",
                instance_id=instance_id,
                status=BotStatus.ERROR,
            )

    async def get_instance_status(
        self, instance_id: str
    ) -> Optional[BotInstanceStatus]:
        """Get current status of bot instance"""
        if instance_id not in self.instances:
            return None

        instance = self.instances[instance_id]

        # Update process info if running
        if instance_id in self.processes:
            process = self.processes[instance_id]
            if process.poll() is not None:  # Process died
                error_message = f"Instance {instance_id} exited unexpectedly (exit_code={process.returncode})"
                if self._mark_instance_error(
                    instance_id, error_message, exit_code=process.returncode
                ):
                    await self._publish_strategy_status(
                        instance_id,
                        event="error",
                        last_error=error_message,
                    )
            else:
                self._mark_instance_liveness_verified(
                    instance_id, process_id=process.pid
                )
                # Update resource usage
                try:
                    proc = psutil.Process(process.pid)
                    instance.process_info.update(
                        {
                            "cpu_usage": proc.cpu_percent(),
                            "memory_usage_mb": proc.memory_info().rss / (1024 * 1024),
                        }
                    )
                except psutil.AccessDenied:
                    logger.debug(
                        "Metrics access denied for {}; liveness verified", instance_id
                    )
                except psutil.NoSuchProcess:
                    error_message = f"Runtime process for {instance_id} disappeared before metrics could be collected"
                    if self._mark_instance_error(instance_id, error_message):
                        await self._publish_strategy_status(
                            instance_id,
                            event="error",
                            last_error=error_message,
                        )
        elif instance.status in self.ACTIVE_RUNTIME_STATUSES:
            external_process, probe_error = self._resolve_external_runtime_process(
                instance_id
            )
            if external_process is not None:
                try:
                    instance.process_info.update(
                        {
                            "pid": external_process.pid,
                            "cpu_usage": external_process.cpu_percent(),
                            "memory_usage_mb": external_process.memory_info().rss
                            / (1024 * 1024),
                        }
                    )
                    self._mark_instance_liveness_verified(
                        instance_id,
                        process_id=external_process.pid,
                    )
                except psutil.AccessDenied:
                    self._mark_instance_liveness_verified(
                        instance_id,
                        process_id=external_process.pid,
                    )
                    logger.debug(
                        "Metrics access denied for recovered {}; liveness verified",
                        instance_id,
                    )
                except (psutil.NoSuchProcess, psutil.ZombieProcess):
                    probe_error = (
                        f"Runtime process for {instance_id} is no longer running"
                    )
                    external_process = None

            if external_process is None:
                error_message = (
                    probe_error or f"Runtime process for {instance_id} is not attached"
                )
                if self._mark_instance_error(instance_id, error_message):
                    await self._publish_strategy_status(
                        instance_id,
                        event="error",
                        last_error=error_message,
                    )

        # Update trading stats from state files
        self._update_instance_trading_stats(instance_id)

        instance.last_update = datetime.now(timezone.utc)
        return instance.to_api_status()

    def _update_instance_trading_stats(self, instance_id: str):
        """Update trading statistics from database-backed trade state."""
        if instance_id not in self.instances:
            return
        if not self._db_persistence_enabled():
            return
        session = None
        try:
            session = db.get_session()
            uow = UnitOfWork(session)
            stats = uow.bots.get_statistics(instance_id)
            if stats:
                self.instances[instance_id].trading_stats.update(stats)
                self.instances[instance_id].trading_stats["source"] = "database"
        except Exception as e:
            logger.warning(
                "Error updating DB-backed trading stats for {}: {}", instance_id, e
            )
            if session is not None:
                session.rollback()
        finally:
            if session is not None:
                session.close()

    async def list_instances(self) -> List[BotInstanceStatus]:
        """Get list of all bot instances"""
        statuses = []
        for instance_id in list(self.instances.keys()):
            status = await self.get_instance_status(instance_id)
            if status:
                statuses.append(status)

        return statuses

    async def auto_recover_live_runtimes(self) -> Dict[str, Any]:
        """Reconcile active persisted live runtimes after API restart.

        Attached or externally visible worker processes are treated as healthy.
        Missing workers are marked ERROR by default. Restarting a missing worker
        is opt-in and goes through the normal manager lifecycle path.
        """
        restart_enabled = self._live_auto_recovery_enabled()
        allow_mainnet = self._live_auto_recovery_allows_mainnet()
        report: Dict[str, Any] = {
            "restart_enabled": restart_enabled,
            "allow_mainnet": allow_mainnet,
            "checked": 0,
            "verified_running": [],
            "restarted": [],
            "marked_error": [],
            "skipped": [],
        }

        for instance_id, instance in list(self.instances.items()):
            if instance.status not in self.ACTIVE_RUNTIME_STATUSES:
                continue

            report["checked"] += 1
            if self._refresh_instance_liveness_from_process(instance_id):
                instance.status = BotStatus.RUNNING
                report["verified_running"].append(instance_id)
                await self._publish_strategy_status(instance_id, event="heartbeat")
                continue

            lock = self._get_instance_lock(instance_id)
            if lock.locked():
                report["skipped"].append(
                    {
                        "instance_id": instance_id,
                        "reason": "lifecycle operation in progress",
                    }
                )
                continue

            async with lock:
                if self._refresh_instance_liveness_from_process(instance_id):
                    instance.status = BotStatus.RUNNING
                    report["verified_running"].append(instance_id)
                    await self._publish_strategy_status(instance_id, event="heartbeat")
                    continue

                _, probe_error = self._resolve_external_runtime_process(instance_id)
                error_message = (
                    probe_error or f"Runtime process for {instance_id} is not attached"
                )
                is_mainnet = not instance.config.trading_params.is_testnet
                can_restart = restart_enabled and (allow_mainnet or not is_mainnet)

                if not can_restart:
                    reason = (
                        "auto-restart disabled for mainnet runtime"
                        if restart_enabled and is_mainnet and not allow_mainnet
                        else "auto-restart disabled"
                    )
                    if self._mark_instance_error(
                        instance_id, f"{error_message}; {reason}"
                    ):
                        await self._publish_strategy_status(
                            instance_id,
                            event="error",
                            last_error=f"{error_message}; {reason}",
                        )
                    report["marked_error"].append(
                        {"instance_id": instance_id, "reason": reason}
                    )
                    continue

                instance.status = BotStatus.RECOVERING
                instance.recovery_state = "recovering"
                instance.recovery_reason = error_message
                instance.last_update = datetime.now(timezone.utc)
                instance.process_info.pop("pid", None)
                self._save_instances_state()
                await self._publish_strategy_status(
                    instance_id,
                    event="recovering",
                    last_error=error_message,
                )

                # Reuse the normal start path while holding the lifecycle lock.
                instance.status = BotStatus.STOPPED
                result = await self._start_instance_locked(instance_id)
                if result.success:
                    self._mark_instance_liveness_verified(instance_id)
                    report["restarted"].append(instance_id)
                else:
                    report["marked_error"].append(
                        {
                            "instance_id": instance_id,
                            "reason": result.error or result.message,
                        }
                    )

        self._save_instances_state()
        self.recovery_diagnostics["live_auto_recovery"] = report
        return report

    async def cleanup_dead_processes(self):
        """Cleanup dead processes and update instance statuses"""
        state_changed = False
        for instance_id in list(self.processes.keys()):
            process = self.processes[instance_id]
            if process.poll() is not None:  # Process is dead
                logger.warning(f"Found dead process for instance {instance_id}")
                error_message = f"Background monitor detected crashed process for {instance_id} (exit_code={process.returncode})"
                if self._mark_instance_error(
                    instance_id, error_message, exit_code=process.returncode
                ):
                    # P1.7: Mark as recovering state
                    if instance_id in self.instances:
                        self.instances[instance_id].recovery_state = "recovering"
                        self.instances[instance_id].recovery_reason = error_message
                    state_changed = True
                    await self._publish_strategy_status(
                        instance_id,
                        event="error",
                        last_error=error_message,
                    )
            else:
                self._mark_instance_liveness_verified(
                    instance_id,
                    process_id=getattr(process, "pid", None),
                )

        if state_changed:
            self._save_instances_state()

        # P1.7: Check for stale heartbeats and mark as degraded
        await self._check_liveness_and_degrade()

    async def _check_liveness_and_degrade(self):
        """P1.7: Monitor heartbeat staleness and degrade status if needed"""
        now = datetime.now(timezone.utc)
        state_changed = False
        for instance_id, instance in list(self.instances.items()):
            if instance.status not in {BotStatus.RUNNING, BotStatus.DEGRADED}:
                continue

            if instance.last_heartbeat is None:
                self._refresh_instance_liveness_from_process(instance_id)
                continue

            time_since_heartbeat = (now - instance.last_heartbeat).total_seconds()
            if time_since_heartbeat <= instance.heartbeat_stale_seconds:
                continue

            if self._refresh_instance_liveness_from_process(instance_id):
                continue

            # Mark as degraded if not already in recovery.
            if instance.recovery_state != "recovering":
                logger.warning(
                    f"Instance {instance_id} heartbeat stale for {time_since_heartbeat:.0f}s; marking degraded"
                )
                instance.recovery_state = "degraded"
                instance.recovery_reason = (
                    f"Heartbeat stale for {time_since_heartbeat:.0f}s"
                )
                instance.status = BotStatus.DEGRADED
                state_changed = True
                await self._publish_strategy_status(
                    instance_id,
                    event="degraded",
                    message="Runtime heartbeat stale; operating with caution",
                )

        if state_changed:
            self._save_instances_state()

    def get_recovery_diagnostics(self) -> Dict[str, Any]:
        """Return startup recovery diagnostics for observability endpoints."""
        skipped_instances = self.recovery_diagnostics.get("skipped_instances", [])
        return {
            "started_at": self.recovery_diagnostics.get("started_at"),
            "completed_at": self.recovery_diagnostics.get("completed_at"),
            "source": self.recovery_diagnostics.get("source", "none"),
            "attempted": int(self.recovery_diagnostics.get("attempted", 0)),
            "loaded": int(self.recovery_diagnostics.get("loaded", 0)),
            "skipped": int(self.recovery_diagnostics.get("skipped", 0)),
            "skipped_instances": (
                list(skipped_instances) if isinstance(skipped_instances, list) else []
            ),
            "live_auto_recovery": dict(
                self.recovery_diagnostics.get("live_auto_recovery") or {}
            ),
            "last_error": self.recovery_diagnostics.get("last_error"),
        }

    def get_db_sync_backoff_diagnostics(self) -> Dict[str, Any]:
        """Return DB sync overload cooldown diagnostics for health surfaces."""
        now = time.monotonic()
        backoff_until = float(self._db_sync_backoff_until_monotonic or 0.0)
        active = now < backoff_until
        remaining_seconds = max(0.0, backoff_until - now)
        return {
            "active": active,
            "remaining_seconds": round(remaining_seconds, 2),
            "cooldown_seconds": self._read_positive_float_env(
                "BOT_DB_SYNC_COOLDOWN_SECONDS",
                20.0,
            ),
            "log_every_seconds": self._read_positive_float_env(
                "BOT_DB_SYNC_BACKOFF_LOG_EVERY_SECONDS",
                15.0,
            ),
            "notice_after_monotonic": float(
                self._db_sync_backoff_notice_after_monotonic or 0.0
            ),
        }

    async def shutdown(self, *, stop_active: bool = False):
        """Release manager resources and optionally stop active child runtimes."""
        if stop_active:
            for instance_id, instance in list(self.instances.items()):
                if instance.status in self.ACTIVE_RUNTIME_STATUSES:
                    await self.stop_instance(instance_id, force=False)
        for instance_id in list(self.log_handles.keys()):
            self._close_instance_log(instance_id)


# Global bot manager instance
bot_manager = BotInstanceManager()
