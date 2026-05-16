#!/usr/bin/env python3
"""Migrate deprecated per-instance YAML config caches into bot_instances.config.

This script is intentionally the only supported YAML reader for runtime bot
configs. It is a one-time operator migration tool; workers no longer read YAML.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BOT_ROOT = REPO_ROOT / "bot"
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))


class MigrationError(RuntimeError):
    """Raised when a YAML config cannot be safely migrated."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate deprecated bot_states/config_*.yaml files into bot_instances.config",
    )
    parser.add_argument(
        "--state-dir",
        default=str(BOT_ROOT / "bot_states"),
        help="Directory containing deprecated config_*.yaml files",
    )
    parser.add_argument(
        "--pattern",
        default="config_*.yaml",
        help="Glob pattern for deprecated YAML files inside --state-dir",
    )
    parser.add_argument(
        "--instance-id",
        action="append",
        default=[],
        help="Optional instance id to migrate; can be passed multiple times",
    )
    parser.add_argument(
        "--default-user-id",
        type=int,
        default=1,
        help="User id to use when inserting rows into backend-managed schemas",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing non-empty DB config payloads",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate YAML without writing to the database",
    )
    return parser.parse_args()


def payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def config_meta(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "hash_algorithm": "sha256",
        "payload_hash": payload_hash(payload),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def require_mapping(payload: dict[str, Any], key: str, file_path: Path) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise MigrationError(f"{file_path}: missing required mapping '{key}'")
    return value


def require_text(payload: dict[str, Any], key: str, file_path: Path) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise MigrationError(f"{file_path}: missing required value '{key}'")
    return value


def bool_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def instance_id_from_path(path: Path) -> str:
    stem = path.stem
    if not stem.startswith("config_"):
        raise MigrationError(f"{path}: filename must start with config_")
    instance_id = stem[len("config_") :].strip()
    if not instance_id:
        raise MigrationError(f"{path}: empty instance id in filename")
    return instance_id


def load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    print(
        f"WARNING: {path} is a deprecated runtime YAML config; migrating it to the database"
    )
    with path.open("r", encoding="utf-8") as file_handle:
        payload = yaml.safe_load(file_handle) or {}
    if not isinstance(payload, dict):
        raise MigrationError(f"{path}: YAML root must be an object")
    return payload


def yaml_to_db_payload(path: Path) -> tuple[str, str, str, dict[str, Any]]:
    raw = load_yaml(path)
    instance_id = instance_id_from_path(path)
    if isinstance(raw.get("credentials"), dict) and isinstance(
        raw.get("trading_params"), dict
    ):
        runtime_payload = {
            key: value
            for key, value in raw.items()
            if key not in {"_config_meta", "config_meta", "runtime_state"}
        }
        runtime_payload.setdefault("instance_name", instance_id)
        runtime_payload.setdefault("telegram", {})
        runtime_payload.setdefault("backtesting_params", {})
        validate_db_payload(instance_id, runtime_payload)
        trading = runtime_payload["trading_params"]
        is_testnet = bool_value(trading.get("is_testnet"), default=True)
        strategy = require_text(trading, "strategy", path)
        runtime_payload["config_meta"] = config_meta(runtime_payload)
        return (
            instance_id,
            "testnet" if is_testnet else "mainnet",
            strategy,
            runtime_payload,
        )

    bot_settings = require_mapping(raw, "botSettings", path)
    backtesting = raw.get("backtesting") if isinstance(raw.get("backtesting"), dict) else {}
    telegram = raw.get("telegram") if isinstance(raw.get("telegram"), dict) else {}
    is_testnet = bool_value(raw.get("is_testnet"), default=True)
    network_key = "dydx_testnet" if is_testnet else "dydx_mainnet"
    network_payload = require_mapping(raw, network_key, path)

    credentials = {
        "chain_id": "dydx-testnet-4" if is_testnet else "dydx-mainnet-1",
        "address": require_text(network_payload, "dydx_chain_address", path),
        "mnemonic": require_text(network_payload, "dydx_chain_secret", path),
    }
    selected_markets = bot_settings.get("selectedMarkets")
    if not isinstance(selected_markets, list):
        selected_markets = []

    trading_params = {
        "is_testnet": is_testnet,
        "subaccount_number": int(bot_settings.get("subaccountNumber", 0)),
        "capital_allocation_usd": float(bot_settings.get("capitalAllocationUsd", 0.0)),
        "find_cointegrated_pairs": bool_value(
            bot_settings.get("findCointegratedPairs"), default=False
        ),
        "manage_exits": bool_value(bot_settings.get("manageExits"), default=False),
        "place_trades": bool_value(bot_settings.get("placeTrades"), default=False),
        "abort_all_positions": bool_value(
            bot_settings.get("abortAllPositions"), default=False
        ),
        "resolution_timeframe": str(bot_settings.get("resolutionTimeframe", "1HOUR")),
        "strategy": require_text(bot_settings, "strategy", path),
        "stats_window": int(bot_settings.get("statsWindow", 21)),
        "max_half_life": int(bot_settings.get("maxHalfLife", 24)),
        "zscore_threshold": float(bot_settings.get("ZScoreThreshold", 1.5)),
        "usd_per_trade": float(bot_settings.get("usdPerTrade", 10.0)),
        "usd_min_collateral": float(bot_settings.get("usdMinCollateral", 100.0)),
        "close_at_zscore_cross": bool_value(
            bot_settings.get("closeAtZscoreCross"), default=True
        ),
        "max_positions": int(bot_settings.get("maxPositions", 5)),
        "max_drawdown_pct": float(bot_settings.get("maxDrawdownPct", 15.0)),
        "stop_loss_pct": float(bot_settings.get("stopLossPct", 2.0)),
        "take_profit_pct": float(bot_settings.get("takeProfitPct", 5.0)),
        "trailing_stop_pct": float(bot_settings.get("trailingStopPct", 1.0)),
        "rebalance_interval_hours": int(
            bot_settings.get("rebalanceIntervalHours", 24)
        ),
        "position_timeout_hours": int(bot_settings.get("positionTimeoutHours", 72)),
        "selected_markets": [
            str(market).strip() for market in selected_markets if str(market).strip()
        ],
    }

    runtime_payload = {
        "instance_name": raw.get("instance_name") or instance_id,
        "credentials": credentials,
        "telegram": {
            "token": str(telegram.get("token") or ""),
            "chat_id": str(telegram.get("chat_id") or ""),
        },
        "trading_params": trading_params,
        "backtesting_params": {
            "candle_resolution": str(backtesting.get("candleResolution", "1HOUR")),
            "max_history_days": int(backtesting.get("maxHistoryDays", 90)),
            "starting_balance": float(backtesting.get("startingBalance", 1000.0)),
            "transaction_fee": float(backtesting.get("transactionFee", 0.0005)),
            "slippage": float(backtesting.get("slippage", 0.001)),
            "benchmark_symbol": str(backtesting.get("benchmarkSymbol", "BTC-USD")),
            "risk_free_rate": float(backtesting.get("riskFreeRate", 0.02)),
        },
    }
    runtime_payload["config_meta"] = config_meta(runtime_payload)

    return (
        instance_id,
        "testnet" if is_testnet else "mainnet",
        trading_params["strategy"],
        runtime_payload,
    )


def select_config_column(columns: dict[str, Any]) -> str:
    if "config" in columns:
        return "config"
    if "config_json" in columns:
        return "config_json"
    raise MigrationError("bot_instances has no config/config_json column")


def db_value_for_column(payload: dict[str, Any], column: dict[str, Any]) -> Any:
    del column
    return json.dumps(payload, sort_keys=True)


def parse_db_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    return {}


def validate_db_payload(instance_id: str, payload: dict[str, Any]) -> None:
    credentials = require_mapping(payload, "credentials", Path(instance_id))
    trading = require_mapping(payload, "trading_params", Path(instance_id))
    require_text(credentials, "address", Path(instance_id))
    require_text(credentials, "mnemonic", Path(instance_id))
    require_text(trading, "strategy", Path(instance_id))
    if "is_testnet" not in trading:
        raise MigrationError(f"{instance_id}: missing trading_params.is_testnet")
    if "subaccount_number" not in trading:
        raise MigrationError(f"{instance_id}: missing trading_params.subaccount_number")


def migrate_one(
    connection,
    columns: dict[str, Any],
    config_column: str,
    path: Path,
    default_user_id: int,
    overwrite: bool,
    dry_run: bool,
) -> str:
    from sqlalchemy import text

    instance_id, network, strategy, payload = yaml_to_db_payload(path)
    validate_db_payload(instance_id, payload)
    existing = connection.execute(
        text(
            f"SELECT id, {config_column} AS config_payload "
            "FROM bot_instances WHERE instance_id = :instance_id"
        ),
        {"instance_id": instance_id},
    ).mappings().first()

    if dry_run:
        return f"validated {instance_id}"

    db_config_value = db_value_for_column(payload, columns[config_column])
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if existing is not None:
        existing_payload = parse_db_payload(existing.get("config_payload"))
        if existing_payload and not overwrite:
            validate_db_payload(instance_id, existing_payload)
            return f"skipped existing {instance_id}"
        set_parts = [f"{config_column} = :config", "network = :network", "strategy = :strategy"]
        params: dict[str, Any] = {
            "config": db_config_value,
            "network": network,
            "strategy": strategy,
            "instance_id": instance_id,
        }
        if "instance_name" in columns:
            set_parts.append("instance_name = :instance_name")
            params["instance_name"] = payload["instance_name"]
        if "updated_at" in columns:
            set_parts.append("updated_at = :updated_at")
            params["updated_at"] = now
        connection.execute(
            text(
                "UPDATE bot_instances SET "
                + ", ".join(set_parts)
                + " WHERE instance_id = :instance_id"
            ),
            params,
        )
        return f"updated {instance_id}"

    insert_columns = ["instance_id", "network", "strategy", config_column]
    params = {
        "instance_id": instance_id,
        "network": network,
        "strategy": strategy,
        "config": db_config_value,
    }
    if "user_id" in columns:
        insert_columns.append("user_id")
        params["user_id"] = default_user_id
    if "instance_name" in columns:
        insert_columns.append("instance_name")
        params["instance_name"] = payload["instance_name"]
    if "status" in columns:
        insert_columns.append("status")
        params["status"] = "STOPPED"
    if "created_at" in columns:
        insert_columns.append("created_at")
        params["created_at"] = now
    if "updated_at" in columns:
        insert_columns.append("updated_at")
        params["updated_at"] = now

    value_names = [
        ":config" if column == config_column else f":{column}"
        for column in insert_columns
    ]
    connection.execute(
        text(
            "INSERT INTO bot_instances ("
            + ", ".join(insert_columns)
            + ") VALUES ("
            + ", ".join(value_names)
            + ")"
        ),
        params,
    )
    return f"inserted {instance_id}"


def discover_files(state_dir: Path, pattern: str, selected_ids: set[str]) -> list[Path]:
    files = sorted(state_dir.glob(pattern))
    if selected_ids:
        files = [path for path in files if instance_id_from_path(path) in selected_ids]
    return files


def main() -> int:
    args = parse_args()
    state_dir = Path(args.state_dir).resolve()
    selected_ids = {str(value).strip() for value in args.instance_id if str(value).strip()}
    files = discover_files(state_dir, args.pattern, selected_ids)
    if not files:
        print(f"No deprecated YAML config files found in {state_dir}")
        return 0

    if args.dry_run:
        results = []
        for path in files:
            instance_id, _network, _strategy, payload = yaml_to_db_payload(path)
            validate_db_payload(instance_id, payload)
            results.append(f"validated {instance_id}")
        for result in results:
            print(result)
        print(f"Validated {len(results)} deprecated YAML config file(s)")
        return 0

    from sqlalchemy import inspect

    from src.shared.env_loader import load_repo_env

    load_repo_env(str(BOT_ROOT / "src" / "main_instance.py"))

    from src.infrastructure.database import db

    engine = db.get_engine()
    inspector = inspect(engine)
    if not inspector.has_table("bot_instances"):
        raise MigrationError("bot_instances table does not exist")
    columns = {column["name"]: column for column in inspector.get_columns("bot_instances")}
    config_column = select_config_column(columns)

    results: list[str] = []
    with engine.begin() as connection:
        for path in files:
            results.append(
                migrate_one(
                    connection,
                    columns,
                    config_column,
                    path,
                    default_user_id=args.default_user_id,
                    overwrite=args.overwrite,
                    dry_run=False,
                )
            )

    for result in results:
        print(result)
    action = "Validated" if args.dry_run else "Migrated"
    print(f"{action} {len(results)} deprecated YAML config file(s)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MigrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
