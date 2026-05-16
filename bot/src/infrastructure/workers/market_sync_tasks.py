"""Optional Celery Beat market-data sync tasks."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from loguru import logger
from src.infrastructure.workers.celery_app import celery_app


def _enabled() -> bool:
    return os.getenv("MARKET_SYNC_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redis_url() -> str:
    return (
        os.getenv("CELERY_BROKER_URL")
        or os.getenv("REDIS_URL")
        or "redis://localhost:6379/0"
    )


def _sync_resolution() -> str:
    return str(os.getenv("MARKET_SYNC_RESOLUTION", "1HOUR") or "1HOUR").strip().upper()


def _sync_limit() -> int:
    raw = str(os.getenv("MARKET_SYNC_CANDLE_LIMIT", "100") or "100").strip()
    try:
        value = int(raw)
    except ValueError:
        return 100
    return max(10, min(value, 500))


def _sync_ttl_seconds() -> int:
    raw = str(os.getenv("MARKET_SYNC_REDIS_TTL_SECONDS", "30") or "30").strip()
    try:
        value = int(raw)
    except ValueError:
        return 30
    return max(5, value)


def _max_markets() -> int:
    raw = str(os.getenv("MARKET_SYNC_MAX_MARKETS", "120") or "120").strip()
    try:
        value = int(raw)
    except ValueError:
        return 120
    return max(1, value)


def _selected_markets_override() -> List[str]:
    raw = str(os.getenv("MARKET_SYNC_MARKETS", "") or "").strip()
    if not raw:
        return []
    seen = set()
    markets: List[str] = []
    for item in raw.split(","):
        market = item.strip().upper()
        if not market or market in seen:
            continue
        seen.add(market)
        markets.append(market)
    return markets


def _get_redis_client():
    try:
        import redis as _redis

        return _redis.from_url(
            _redis_url(),
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception as exc:
        logger.warning("market_sync_redis_init_failed error={!r}", exc)
        return None


async def _resolve_active_markets(client: Any) -> List[str]:
    configured = _selected_markets_override()
    if configured:
        return configured[: _max_markets()]

    payload = await client.indexer.markets.get_perpetual_markets()
    market_map = payload.get("markets", {}) if isinstance(payload, dict) else {}
    if not isinstance(market_map, dict):
        return []

    markets: List[str] = []
    for market, details in market_map.items():
        if len(markets) >= _max_markets():
            break
        if not isinstance(details, dict):
            continue
        if str(details.get("status", "")).upper() != "ACTIVE":
            continue
        normalized_market = str(market).strip().upper()
        if normalized_market:
            markets.append(normalized_market)
    return markets


async def _sync_market_candles_async() -> Dict[str, Any]:
    redis_client = _get_redis_client()
    if redis_client is None:
        return {
            "status": "skipped",
            "reason": "redis unavailable",
            "timestamp": _now_iso(),
        }

    try:
        from src.trading.dydx_client import connect_dydx
    except Exception as exc:
        try:
            redis_client.close()
        except Exception:
            pass
        return {
            "status": "skipped",
            "reason": f"dydx client import failed: {exc}",
            "timestamp": _now_iso(),
        }

    synced = 0
    failed = 0
    failures: List[str] = []
    markets: List[str] = []
    resolution = _sync_resolution()
    ttl_seconds = _sync_ttl_seconds()
    candle_limit = _sync_limit()
    client = None

    try:
        client = await connect_dydx()
        markets = await _resolve_active_markets(client)

        if not markets:
            return {
                "status": "skipped",
                "reason": "no markets resolved",
                "timestamp": _now_iso(),
                "resolution": resolution,
            }

        for market in markets:
            try:
                response = await client.indexer.markets.get_perpetual_market_candles(
                    market=market,
                    resolution=resolution,
                    limit=candle_limit,
                )
                candles = response.get("candles", []) if isinstance(response, dict) else []
                if not isinstance(candles, list) or not candles:
                    failed += 1
                    failures.append(f"{market}:empty")
                    continue

                key = f"market:candles:{market}:{resolution}"
                payload = json.dumps(response)
                redis_client.set(key, payload, ex=ttl_seconds)
                synced += 1
            except Exception as exc:
                failed += 1
                failures.append(f"{market}:{type(exc).__name__}")
                logger.debug(
                    "market_sync_candle_fetch_failed market={} resolution={} error={!r}",
                    market,
                    resolution,
                    exc,
                )

        status = "ok" if synced > 0 and failed == 0 else "partial" if synced > 0 else "failed"
        return {
            "status": status,
            "timestamp": _now_iso(),
            "resolution": resolution,
            "ttl_seconds": ttl_seconds,
            "candle_limit": candle_limit,
            "markets_requested": len(markets),
            "markets_synced": synced,
            "markets_failed": failed,
            "failures": failures[:10],
        }
    finally:
        if client is not None:
            try:
                await client.node.close()
            except Exception:
                pass
        try:
            redis_client.close()
        except Exception:
            pass


def _run_market_sync() -> Dict[str, Any]:
    return asyncio.run(_sync_market_candles_async())


@celery_app.task(name="bot.sync_market_candles")
def sync_market_candles() -> Dict[str, Any]:
    """Sync active market candles to shared Redis cache for runtime reuse."""
    if not _enabled():
        return {
            "status": "skipped",
            "reason": "MARKET_SYNC_ENABLED is false",
            "timestamp": _now_iso(),
        }

    try:
        result = _run_market_sync()
        logger.debug("market_sync_candles_result {}", result)
        return result
    except Exception as exc:
        logger.exception("market_sync_candles_failed error={!r}", exc)
        return {
            "status": "failed",
            "reason": str(exc),
            "timestamp": _now_iso(),
        }
