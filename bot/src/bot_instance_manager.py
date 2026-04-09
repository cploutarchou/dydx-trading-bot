"""
Bot Instance Manager - Handles multiple bot instances with API control
"""

from src.shared.env_loader import load_repo_env

load_repo_env(__file__)

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, List, Optional, TextIO

from loguru import logger
import psutil
from config.config import config as load_app_config
from internal.domain.models import BotStatusEnum
from sqlalchemy import text
from src.infrastructure.database import db
from src.infrastructure.domain.bot_api_models import (
    BotInstanceConfig,
    BotInstanceState,
    BotInstanceStatus,
    BotOperationResult,
    BotStatus,
)
from src.infrastructure.persistence.repository import UnitOfWork


class BotInstanceManager:
    """Manages multiple bot instances with isolated state and configuration"""

    def __init__(self, state_dir: str = "./bot_states", max_instances: int = 10):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.max_instances = max_instances

        # In-memory instance tracking
        self.instances: Dict[str, BotInstanceState] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.log_handles: Dict[str, TextIO] = {}
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
            "last_error": None,
        }

        # Load existing instances from disk
        self._load_existing_instances()

    def set_status_event_publisher(
        self,
        publisher: Optional[Callable[[Dict[str, object]], Awaitable[None]]],
    ):
        """Register async publisher for strategy runtime status events."""
        self.status_event_publisher = publisher

    def _load_existing_instances(self):
        """Load bot instances from the database, with file fallback for compatibility."""
        self.recovery_diagnostics.update(
            {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "source": "none",
                "attempted": 0,
                "loaded": 0,
                "skipped": 0,
                "skipped_instances": [],
                "last_error": None,
            }
        )
        loaded_from_db = self._load_existing_instances_from_db()
        if loaded_from_db is not None:
            self.recovery_diagnostics["source"] = "database"
            self.recovery_diagnostics["loaded"] = loaded_from_db
            self.recovery_diagnostics["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("Loaded {} existing bot instances from database", loaded_from_db)
            return

        self._load_existing_instances_from_disk()
        self.recovery_diagnostics["source"] = "disk_snapshot"
        self.recovery_diagnostics["completed_at"] = datetime.now(timezone.utc).isoformat()

    def _record_recovery_skip(self, instance_id: str, reason: str):
        skipped_instances = self.recovery_diagnostics.setdefault("skipped_instances", [])
        if isinstance(skipped_instances, list):
            skipped_instances.append({"instance_id": instance_id, "reason": reason})
        self.recovery_diagnostics["skipped"] = int(self.recovery_diagnostics.get("skipped", 0)) + 1

    def _load_existing_instances_from_db(self) -> Optional[int]:
        """Hydrate manager state from persisted bot instances in PostgreSQL."""
        session = None
        try:
            session = db.get_session()
            loaded = 0

            # Use a raw query here instead of ORM model hydration so legacy
            # lowercase status values (e.g. "error") do not raise enum decode
            # errors before we can normalize them.
            rows = session.execute(
                text(
                    """
                    SELECT
                        instance_id,
                        network,
                        strategy,
                        config,
                        process_id,
                        created_at,
                        updated_at,
                        CAST(status AS TEXT) AS status
                    FROM bot_instances
                    """
                )
            ).mappings()

            for row in rows:
                record = SimpleNamespace(**dict(row))
                self.recovery_diagnostics["attempted"] = int(self.recovery_diagnostics.get("attempted", 0)) + 1
                config = self._build_instance_config_from_record(record)
                if config is None:
                    continue

                status = self._coerce_record_status(record.status)
                payload = self._coerce_record_config_payload(getattr(record, "config", None))
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
                        self.recovery_diagnostics["attempted"] = int(self.recovery_diagnostics.get("attempted", 0)) + 1
                        # Reconstruct instance state (without active processes)
                        instance_id = instance_data["instance_id"]
                        self.instances[instance_id] = BotInstanceState(
                            instance_id=instance_id,
                            config=BotInstanceConfig.model_validate(instance_data["config"]),
                            status=BotStatus.STOPPED,
                            process_info={},
                            trading_stats=instance_data.get("trading_stats", {}),
                            created_at=datetime.fromisoformat(instance_data["created_at"]),
                            last_update=datetime.now(),
                        )
                self.recovery_diagnostics["loaded"] = len(self.instances)
                logger.info("Loaded {} existing bot instances from disk snapshot", len(self.instances))
            except Exception as e:
                logger.error(f"Error loading instances: {e}")
                self.recovery_diagnostics["last_error"] = str(e)

    @staticmethod
    def _coerce_record_config_payload(raw_config: Any) -> dict[str, Any]:
        """Normalize persisted bot config payloads from dict or JSON-string forms."""
        if isinstance(raw_config, dict):
            return dict(raw_config)
        if isinstance(raw_config, str):
            raw = raw_config.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError):
                return {}
            return dict(parsed) if isinstance(parsed, dict) else {}
        return {}

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
            trading_payload["is_testnet"] = str(record.network).strip().lower() != "mainnet"
        if "strategy" not in trading_payload or not str(trading_payload["strategy"]).strip():
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

    def _record_runtime_event(
        self,
        instance_id: str,
        event_type: str,
        severity: str,
        message: str,
        details: Optional[dict] = None,
    ):
        """Persist runtime events so failures survive process restarts."""
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
            logger.warning("Failed to record runtime event for {}: {}", instance_id, exc)
            if session is not None:
                session.rollback()
        finally:
            if session is not None:
                session.close()

    def _persist_instances_to_db(self):
        """Sync runtime state back into PostgreSQL so it stays authoritative across restarts."""
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
                persisted_config.update(
                    {
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
                        "runtime_state": {
                            "status": instance.status.value,
                            "process_id": instance.process_info.get("pid"),
                            "last_error": instance.process_info.get("last_error"),
                            "exit_code": instance.process_info.get("exit_code"),
                            "started_at": (
                                instance.process_info.get("started_at").isoformat()
                                if isinstance(instance.process_info.get("started_at"), datetime)
                                else instance.process_info.get("started_at")
                            ),
                            "stopped_at": (
                                instance.process_info.get("stopped_at").isoformat()
                                if isinstance(instance.process_info.get("stopped_at"), datetime)
                                else instance.process_info.get("stopped_at")
                            ),
                            "last_update": instance.last_update.isoformat(),
                            "trading_stats": instance.trading_stats,
                        },
                    }
                )
                record.config = persisted_config

            session.commit()
        except Exception as exc:
            logger.warning("Failed to sync bot manager state to database: {}", exc)
            if session is not None:
                session.rollback()
        finally:
            if session is not None:
                session.close()

    def _save_instances_state(self):
        """Persist instance state to DB first, plus a compatibility snapshot on disk."""
        self._persist_instances_to_db()

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
                "last_saved": datetime.now().isoformat(),
            }
            with open(state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving instances state: {e}")

    def _strategy_id_from_instance_id(self, instance_id: str) -> Optional[int]:
        """Extract strategy id from deterministic strategy runtime instance ids."""
        parts = instance_id.split("-")
        if len(parts) == 3 and parts[0] == "strategy" and parts[1].isdigit() and parts[2].isdigit():
            return int(parts[2])
        return None

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

        status = instance.status.value if isinstance(instance.status, BotStatus) else str(instance.status)
        network = (
            "testnet"
            if instance.config.trading_params.is_testnet
            else "mainnet"
        )
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
    ):
        """Publish status update for strategy-managed instances when configured."""
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
            logger.warning("Failed to publish strategy status for {}: {}", instance_id, exc)

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
            "cointegrated_pairs": self.state_dir / f"cointegrated_pairs_{instance_id}.json",
            "config": self.state_dir / f"config_{instance_id}.yaml",
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
        instance.last_update = datetime.now()
        instance.process_info["stopped_at"] = datetime.now()
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

    def _create_instance_config_file(self, instance_id: str, config: BotInstanceConfig) -> Path:
        """Create instance-specific configuration file"""
        files = self._get_instance_state_files(instance_id)
        runtime_defaults = load_app_config()
        if runtime_defaults is None:
            raise RuntimeError("Failed to resolve runtime configuration defaults")

        telegram_defaults = runtime_defaults.telegram
        backtest_defaults = runtime_defaults.backtesting
        logging_defaults = runtime_defaults.logging
        loki_defaults = logging_defaults.loki

        # Create dynamic config YAML for this instance
        config_data = {
            "is_testnet": config.trading_params.is_testnet,
            "environment": runtime_defaults.environment,
            "telegram": {
                "token": (
                    config.telegram.token
                    if config.telegram and getattr(config.telegram, "token", "")
                    else telegram_defaults.token
                ),
                "chat_id": (
                    config.telegram.chat_id
                    if config.telegram and getattr(config.telegram, "chat_id", "")
                    else telegram_defaults.chat_id
                ),
            },
            "botSettings": {
                "subaccountNumber": config.trading_params.subaccount_number,
                "capitalAllocationUsd": config.trading_params.capital_allocation_usd,
                "abortAllPositions": config.trading_params.abort_all_positions,
                "findCointegratedPairs": config.trading_params.find_cointegrated_pairs,
                "manageExits": config.trading_params.manage_exits,
                "placeTrades": config.trading_params.place_trades,
                "resolutionTimeframe": config.trading_params.resolution_timeframe,
                "strategy": config.trading_params.strategy,
                "statsWindow": config.trading_params.stats_window,
                "maxHalfLife": config.trading_params.max_half_life,
                "ZScoreThreshold": config.trading_params.zscore_threshold,
                "usdPerTrade": config.trading_params.usd_per_trade,
                "usdMinCollateral": config.trading_params.usd_min_collateral,
                "closeAtZscoreCross": config.trading_params.close_at_zscore_cross,
                "maxPositions": config.trading_params.max_positions,
                "maxDrawdownPct": config.trading_params.max_drawdown_pct,
                "stopLossPct": config.trading_params.stop_loss_pct,
                "takeProfitPct": config.trading_params.take_profit_pct,
                "trailingStopPct": config.trading_params.trailing_stop_pct,
                "rebalanceIntervalHours": config.trading_params.rebalance_interval_hours,
                "positionTimeoutHours": config.trading_params.position_timeout_hours,
            },
            "backtesting": {
                "candleResolution": (
                    config.backtesting_params.candle_resolution
                    if config.backtesting_params
                    else backtest_defaults.candleResolution
                ),
                "maxHistoryDays": (
                    config.backtesting_params.max_history_days
                    if config.backtesting_params
                    else backtest_defaults.maxHistoryDays
                ),
                "startingBalance": (
                    config.backtesting_params.starting_balance
                    if config.backtesting_params
                    else backtest_defaults.startingBalance
                ),
                "transactionFee": (
                    config.backtesting_params.transaction_fee
                    if config.backtesting_params
                    else backtest_defaults.transactionFee
                ),
                "slippage": (
                    config.backtesting_params.slippage
                    if config.backtesting_params
                    else backtest_defaults.slippage
                ),
                "benchmarkSymbol": (
                    config.backtesting_params.benchmark_symbol
                    if config.backtesting_params
                    else backtest_defaults.benchmarkSymbol
                ),
                "riskFreeRate": (
                    config.backtesting_params.risk_free_rate
                    if config.backtesting_params
                    else backtest_defaults.riskFreeRate
                ),
            },
            "dydx_testnet": {
                "dydx_chain_address": (
                    config.credentials.address if config.trading_params.is_testnet else ""
                ),
                "dydx_chain_secret": (
                    config.credentials.mnemonic if config.trading_params.is_testnet else ""
                ),
            },
            "dydx_mainnet": {
                "dydx_chain_address": (
                    config.credentials.address if not config.trading_params.is_testnet else ""
                ),
                "dydx_chain_secret": (
                    config.credentials.mnemonic if not config.trading_params.is_testnet else ""
                ),
            },
            "logging": {
                "level": logging_defaults.level,
                "loki": {
                    "enabled": loki_defaults.enabled,
                    "url": loki_defaults.url,
                    "username": loki_defaults.username,
                    "password": loki_defaults.password,
                    "labels": {
                        **(loki_defaults.labels or {}),
                        "instance": instance_id,
                    },
                },
            },
        }

        # Write YAML config
        import yaml

        with open(files["config"], "w") as f:
            yaml.dump(config_data, f, default_flow_style=False)

        return files["config"]

    async def create_instance(self, config: BotInstanceConfig) -> BotOperationResult:
        """Create new bot instance"""
        try:
            # Validate instance limit
            if len(self.instances) >= self.max_instances:
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
                created_at=datetime.now(),
                last_update=datetime.now(),
            )

            # Create instance-specific configuration file
            config_file = self._create_instance_config_file(config.instance_id, config)

            # Initialize empty state files
            files = self._get_instance_state_files(config.instance_id)

            # Create empty bot agents file
            with open(files["bot_agents"], "w") as f:
                json.dump([], f)

            # Store instance
            self.instances[config.instance_id] = instance_state
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
        try:
            if instance_id not in self.instances:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {instance_id} not found",
                    instance_id=instance_id,
                    status=BotStatus.ERROR,
                )

            instance = self.instances[instance_id]

            if instance.status == BotStatus.RUNNING:
                return BotOperationResult(
                    success=False,
                    message=f"Instance {instance_id} is already running",
                    instance_id=instance_id,
                    status=BotStatus.RUNNING,
                )

            # Update status
            instance.status = BotStatus.STARTING
            instance.last_update = datetime.now()
            instance.process_info.pop("last_error", None)
            await self._publish_strategy_status(instance_id, event="starting")

            # Get instance files
            files = self._get_instance_state_files(instance_id)
            bot_root = Path(__file__).resolve().parents[1]

            # Prepare environment for bot process
            bot_env = os.environ.copy()
            bot_env.update(
                {
                    "BOT_INSTANCE_ID": instance_id,
                    "BOT_CONFIG_FILE": str(files["config"]),
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
                "--config",
                str(files["config"]),
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

            # Store process reference
            self.processes[instance_id] = process

            startup_grace = float(os.getenv("BOT_STARTUP_GRACE_SECONDS", "0.2"))
            await asyncio.sleep(max(0.0, startup_grace))
            exit_code = process.poll()
            if exit_code is not None:
                log_tail = self._read_recent_log_tail(instance_id)
                error_message = (
                    f"Instance {instance_id} exited during startup (exit_code={exit_code})"
                )
                if log_tail:
                    error_message = f"{error_message}: {log_tail.splitlines()[-1]}"

                self._mark_instance_error(instance_id, error_message, exit_code=exit_code)
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
                "started_at": datetime.now(),
                "cmd": " ".join(cmd),
                "log_path": str(files["log"]),
            }
            instance.last_update = datetime.now()

            self._save_instances_state()

            logger.info(f"Started bot instance {instance_id} with PID {process.pid}")
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

    async def stop_instance(self, instance_id: str, force: bool = False) -> BotOperationResult:
        """Stop bot instance"""
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

            # Update status
            instance.status = BotStatus.STOPPING
            instance.last_update = datetime.now()
            await self._publish_strategy_status(instance_id, event="stopping")

            # Stop process if running
            if instance_id in self.processes:
                process = self.processes[instance_id]

                if process.poll() is None:  # Process is still running
                    if force:
                        process.kill()
                        logger.info(f"Force killed bot instance {instance_id}")
                    else:
                        process.terminate()
                        logger.info(f"Gracefully terminating bot instance {instance_id}")

                        # Wait for graceful shutdown
                        try:
                            process.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            logger.warning(f"Force killed bot instance {instance_id} after timeout")

                # Remove process reference
                del self.processes[instance_id]
            else:
                external_process, probe_error = self._resolve_external_runtime_process(instance_id)
                if external_process is not None:
                    try:
                        if force:
                            external_process.kill()
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
                                external_process.wait(timeout=30)
                            except psutil.TimeoutExpired:
                                external_process.kill()
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
                    logger.warning("Stop requested for {} but {}", instance_id, probe_error)

            # Update instance state
            instance.status = BotStatus.STOPPED
            instance.process_info["stopped_at"] = datetime.now()
            instance.process_info.pop("pid", None)
            instance.process_info.pop("last_error", None)
            instance.last_update = datetime.now()
            self._close_instance_log(instance_id)

            self._save_instances_state()

            logger.info(f"Stopped bot instance: {instance_id}")
            await self._publish_strategy_status(instance_id, event="stopped")

            return BotOperationResult(
                success=True,
                message=f"Bot instance {instance_id} stopped successfully",
                instance_id=instance_id,
                status=BotStatus.STOPPED,
            )

        except Exception as e:
            logger.error(f"Error stopping instance {instance_id}: {e}")
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
        try:
            # Stop instance first if running
            if (
                instance_id in self.instances
                and self.instances[instance_id].status == BotStatus.RUNNING
            ):
                stop_result = await self.stop_instance(instance_id, force=True)
                if not stop_result.success:
                    return stop_result

            # Remove from memory
            if instance_id in self.instances:
                del self.instances[instance_id]
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

    async def get_instance_status(self, instance_id: str) -> Optional[BotInstanceStatus]:
        """Get current status of bot instance"""
        if instance_id not in self.instances:
            return None

        instance = self.instances[instance_id]

        # Update process info if running
        if instance_id in self.processes:
            process = self.processes[instance_id]
            if process.poll() is not None:  # Process died
                error_message = (
                    f"Instance {instance_id} exited unexpectedly (exit_code={process.returncode})"
                )
                if self._mark_instance_error(instance_id, error_message, exit_code=process.returncode):
                    await self._publish_strategy_status(
                        instance_id,
                        event="error",
                        last_error=error_message,
                    )
            else:
                # Update resource usage
                try:
                    proc = psutil.Process(process.pid)
                    instance.process_info.update(
                        {
                            "cpu_usage": proc.cpu_percent(),
                            "memory_usage_mb": proc.memory_info().rss / (1024 * 1024),
                        }
                    )
                except psutil.NoSuchProcess:
                    error_message = (
                        f"Runtime process for {instance_id} disappeared before metrics could be collected"
                    )
                    if self._mark_instance_error(instance_id, error_message):
                        await self._publish_strategy_status(
                            instance_id,
                            event="error",
                            last_error=error_message,
                        )
        elif instance.status in {BotStatus.RUNNING, BotStatus.STARTING, BotStatus.STOPPING}:
            external_process, probe_error = self._resolve_external_runtime_process(instance_id)
            if external_process is not None:
                try:
                    instance.process_info.update(
                        {
                            "pid": external_process.pid,
                            "cpu_usage": external_process.cpu_percent(),
                            "memory_usage_mb": external_process.memory_info().rss / (1024 * 1024),
                        }
                    )
                except (psutil.NoSuchProcess, psutil.ZombieProcess):
                    probe_error = f"Runtime process for {instance_id} is no longer running"
                    external_process = None

            if external_process is None:
                error_message = probe_error or f"Runtime process for {instance_id} is not attached"
                if self._mark_instance_error(instance_id, error_message):
                    await self._publish_strategy_status(
                        instance_id,
                        event="error",
                        last_error=error_message,
                    )

        # Update trading stats from state files
        self._update_instance_trading_stats(instance_id)

        instance.last_update = datetime.now()
        return instance.to_api_status()

    def _update_instance_trading_stats(self, instance_id: str):
        """Update trading statistics from bot state files"""
        try:
            files = self._get_instance_state_files(instance_id)

            # Read bot agents file for active positions
            if files["bot_agents"].exists():
                with open(files["bot_agents"], "r") as f:
                    agents = json.load(f)
                    active_positions = len([a for a in agents if a.get("pair_status") == "LIVE"])
                    self.instances[instance_id].trading_stats["active_positions"] = active_positions

            # Additional stats can be added here (total trades, P&L, etc.)

        except Exception as e:
            logger.error(f"Error updating trading stats for {instance_id}: {e}")

    async def list_instances(self) -> List[BotInstanceStatus]:
        """Get list of all bot instances"""
        statuses = []
        for instance_id in list(self.instances.keys()):
            status = await self.get_instance_status(instance_id)
            if status:
                statuses.append(status)

        return statuses

    async def cleanup_dead_processes(self):
        """Cleanup dead processes and update instance statuses"""
        for instance_id in list(self.processes.keys()):
            process = self.processes[instance_id]
            if process.poll() is not None:  # Process is dead
                logger.warning(f"Found dead process for instance {instance_id}")
                error_message = (
                    f"Background monitor detected crashed process for {instance_id} (exit_code={process.returncode})"
                )
                if self._mark_instance_error(instance_id, error_message, exit_code=process.returncode):
                    await self._publish_strategy_status(
                        instance_id,
                        event="error",
                        last_error=error_message,
                    )

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
            "skipped_instances": list(skipped_instances) if isinstance(skipped_instances, list) else [],
            "last_error": self.recovery_diagnostics.get("last_error"),
        }


# Global bot manager instance
bot_manager = BotInstanceManager()
