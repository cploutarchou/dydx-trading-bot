"""Bot instance lifecycle API routes.

This module owns the manager-backed create/list/get/delete/start/stop/restart and
quick-deploy HTTP operations. Process ownership remains in ``BotInstanceManager``;
the canonical server injects its manager provider and instance-create rate limiter
when mounting this router.

The provider indirection is intentional: ``src.api.server`` can still start in its
documented degraded mode when the manager import is unavailable, and tests or
operators that replace ``server.bot_manager`` continue to affect these handlers.
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from loguru import logger

from internal.domain.models import BotStatusEnum
from src.api.responses import api_response
from src.infrastructure.database import db
from src.infrastructure.db_offload import run_db
from src.infrastructure.domain.bot_api_models import (
    BotCredentials,
    BotInstanceConfig,
    BotInstanceList,
    BotInstanceStatus,
    BotOperationResult,
    TradingParameters,
)
from src.infrastructure.domain.models.auth_models import User
from src.infrastructure.persistence.repository import UnitOfWork
from src.middleware.auth_middleware import get_current_active_user
from src.shared.credentials_cipher import open_config_secrets, seal_config_secrets
from src.shared.live_risk_controls import assert_supported_live_risk_controls
from src.shared.notifications import TelegramMessenger

BotManagerProvider = Callable[[], Any]
InstanceRateLimiter = Callable[[Request], None]


def _missing_bot_manager() -> None:
    return None


def _allow_instance_request(_: Request) -> None:
    return None


_bot_manager_provider: BotManagerProvider = _missing_bot_manager
_instance_rate_limiter: InstanceRateLimiter = _allow_instance_request


def configure_bot_lifecycle(
    *,
    bot_manager_provider: BotManagerProvider,
    instance_rate_limiter: InstanceRateLimiter,
) -> None:
    """Connect the router to canonical server-owned runtime dependencies."""

    global _bot_manager_provider, _instance_rate_limiter
    _bot_manager_provider = bot_manager_provider
    _instance_rate_limiter = instance_rate_limiter


def _get_bot_manager() -> Any:
    return _bot_manager_provider()


def _check_instance_rate_limit(request: Request) -> None:
    _instance_rate_limiter(request)


def _bot_manager_unavailable_response() -> JSONResponse:
    return api_response(
        success=False,
        message="Bot manager unavailable in this environment",
        status_code=503,
    )


def _resolve_operator_name(current_user: Optional[User]) -> str:
    if current_user is None:
        return "system"
    return (
        str(getattr(current_user, "full_name", "") or "").strip()
        or str(getattr(current_user, "username", "") or "").strip()
        or str(getattr(current_user, "email", "") or "").strip()
        or "system"
    )


def _resolve_action_details(message: Optional[str], fallback: str) -> str:
    text = str(message or "").strip()
    return text or fallback


def _build_bot_lifecycle_context(
    instance_id: str,
    config_payload: Optional[Dict[str, Any]],
    current_user: Optional[User],
    *,
    details: str = "",
    reason: str = "",
) -> Dict[str, Any]:
    payload = config_payload or {}
    trading_params = payload.get("trading_params") or {}
    credentials = payload.get("credentials") or {}
    is_testnet = bool(trading_params.get("is_testnet", True))
    return {
        "instance_id": instance_id,
        "instance_name": payload.get("instance_name") or instance_id,
        "strategy": trading_params.get("strategy", "unknown"),
        "is_testnet": is_testnet,
        "account_address": credentials.get("address"),
        "operator": _resolve_operator_name(current_user),
        "details": details,
        "reason": reason,
    }


def _send_bot_lifecycle_notification(
    action: str,
    instance_id: str,
    config_payload: Optional[Dict[str, Any]],
    current_user: Optional[User],
    *,
    success: bool = True,
    details: str = "",
    reason: str = "",
) -> bool:
    payload = config_payload or {}
    telegram = payload.get("telegram") or {}
    messenger = TelegramMessenger(
        bot_token=str(telegram.get("token") or "").strip(),
        chat_id=str(telegram.get("chat_id") or "").strip(),
        instance_id=instance_id,
        environment=os.getenv("ENVIRONMENT", "development"),
    )
    return messenger.send_lifecycle_message(
        action,
        _build_bot_lifecycle_context(
            instance_id,
            payload,
            current_user,
            details=details,
            reason=reason,
        ),
        success=success,
    )


def _persist_bot_status_and_event(
    instance_id: str,
    *,
    status: Optional[BotStatusEnum] = None,
    process_id: Optional[int] = None,
    event_type: Optional[str] = None,
    severity: str = "info",
    message: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Persist lifecycle status/event updates and return decrypted bot config."""

    session = None
    try:
        session = db.get_session()
        uow = UnitOfWork(session)
        bot = uow.bots.get_by_instance_id(instance_id)
        if bot is None:
            return None

        if status is not None:
            uow.bots.update_status(instance_id, status, process_id=process_id)
            bot = uow.bots.get_by_instance_id(instance_id)
            if bot is None:
                return None

        if event_type:
            uow.events.log_event(
                int(bot.id),  # type: ignore[arg-type]
                event_type,
                severity,
                message,
                details=details,
            )

        raw_config = dict(bot.config) if bot.config is not None else {}  # type: ignore[arg-type]
        return open_config_secrets(raw_config)
    except Exception as db_error:
        logger.warning(
            "Failed to persist bot lifecycle state for {}: {}",
            instance_id,
            db_error,
        )
        if session is not None:
            session.rollback()
        return None
    finally:
        if session is not None:
            session.close()


def _persist_created_bot_config(
    *,
    instance_id: str,
    instance_name: str,
    persisted_config: Dict[str, Any],
    network: str,
    strategy: str,
    config_meta: Dict[str, Any],
) -> None:
    """Persist the DB-backed bot configuration row (sync; run off the event loop).

    Owns its full ``Session`` lifecycle. Raises on failure (``Session.close()``
    releases the pending transaction) so the caller can unwind the runtime
    instance it already created.
    """
    session = db.get_session()
    try:
        uow = UnitOfWork(session)

        bot_db = uow.bots.get_by_instance_id(instance_id)
        stored_config = seal_config_secrets(
            {**persisted_config, "config_meta": config_meta}
        )
        if bot_db is None:
            bot_db = uow.bots.create_bot(
                instance_id=instance_id,
                network=network,
                strategy=strategy,
                config=stored_config,
            )
        else:
            bot_db.config = stored_config
            session.commit()

        try:
            uow.events.log_event(
                int(bot_db.id),  # type: ignore[arg-type]
                "bot_created",
                "info",
                f"Bot instance created via API: {instance_id}",
                details={"instance_name": instance_name},
            )
        except Exception as event_error:
            logger.warning(
                "Failed to record bot_created event for '{}': {}",
                instance_id,
                event_error,
            )
        logger.info(f"Bot instance '{instance_id}' persisted to database")
    finally:
        session.close()


def _delete_bot_db_record(instance_id: str) -> None:
    """Delete the bot's DB row + audit event (sync; run off the event loop).

    Best-effort like the inline block it replaces: failures are logged and
    never fail the delete request. Owns its ``Session`` lifecycle.
    """
    session = None
    try:
        session = db.get_session()
        uow = UnitOfWork(session)
        bot = uow.bots.get_by_instance_id(instance_id)
        if bot is not None:
            uow.events.log_event(
                int(bot.id),  # type: ignore[arg-type]
                "bot_deleted",
                "info",
                "Bot instance deleted via API",
            )
        uow.bots.delete_bot(instance_id)
    except Exception as db_error:
        logger.warning(
            f"Failed to delete bot instance '{instance_id}' from database: {db_error}"
        )
        if session is not None:
            session.rollback()
    finally:
        if session is not None:
            session.close()


router = APIRouter()


@router.post("/api/v1/bots", response_model=BotOperationResult)
async def create_bot_instance(
    config: BotInstanceConfig,
    current_user: User = Depends(get_current_active_user),
    _rate: None = Depends(_check_instance_rate_limit),
):
    """Create a new bot instance"""

    try:
        assert_supported_live_risk_controls(config.trading_params.model_dump())
        bot_manager = _get_bot_manager()
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        result = await bot_manager.create_instance(config)

        if result.success:
            persisted_config: Dict[str, Any] = {
                "instance_name": config.instance_name,
                "credentials": (
                    config.credentials.model_dump() if config.credentials else {}
                ),
                "telegram": (config.telegram.model_dump() if config.telegram else {}),
                "trading_params": (
                    config.trading_params.model_dump() if config.trading_params else {}
                ),
                "backtesting_params": (
                    config.backtesting_params.model_dump()
                    if config.backtesting_params
                    else {}
                ),
            }
            try:
                await run_db(
                    _persist_created_bot_config,
                    instance_id=config.instance_id,
                    instance_name=config.instance_name,
                    persisted_config=persisted_config,
                    network=(
                        "testnet"
                        if (config.trading_params and config.trading_params.is_testnet)
                        else "mainnet"
                    ),
                    strategy=(
                        config.trading_params.strategy
                        if config.trading_params
                        else "default"
                    ),
                    config_meta=bot_manager._build_config_meta(persisted_config),
                )
            except Exception as db_error:
                logger.error(f"Failed to persist bot to database: {db_error}")
                try:
                    await bot_manager.delete_instance(config.instance_id)
                except Exception as cleanup_error:
                    logger.warning(
                        "Failed to clean up bot instance '{}' after DB persistence failure: {}",
                        config.instance_id,
                        cleanup_error,
                    )
                return api_response(
                    success=False,
                    message=(
                        "Failed to persist DB-backed bot configuration; "
                        "instance was not created"
                    ),
                    status_code=500,
                )

            _send_bot_lifecycle_notification(
                "created",
                config.instance_id,
                persisted_config,
                current_user,
                success=True,
                details="Runtime instance created and ready to start.",
            )

            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{config.instance_id}' created successfully",
            )
        return api_response(success=False, message=result.message, status_code=400)

    except Exception as exc:
        if isinstance(exc, ValueError):
            return api_response(
                success=False,
                message=f"Validation error: {str(exc)}",
                data={"error": "UNSUPPORTED_RISK_CONTROL"},
                status_code=422,
            )
        logger.error(f"Error creating bot instance: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


@router.get("/api/v1/bots", response_model=BotInstanceList)
async def list_bot_instances(current_user: User = Depends(get_current_active_user)):
    """Get list of all bot instances"""

    _ = current_user
    try:
        bot_manager = _get_bot_manager()
        if bot_manager is None:
            return api_response(
                success=True,
                data={"bots": [], "total": 0},
                message="Retrieved 0 bot instances (bot manager unavailable)",
            )
        instances = await bot_manager.list_instances()

        return api_response(
            success=True,
            data={
                "bots": [instance.model_dump() for instance in instances],
                "total": len(instances),
            },
            message=f"Retrieved {len(instances)} bot instances",
        )

    except Exception as exc:
        logger.error(f"Error listing bot instances: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


@router.get("/api/v1/bots/{instance_id}", response_model=BotInstanceStatus)
async def get_bot_instance(
    instance_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get specific bot instance status"""

    _ = current_user
    try:
        bot_manager = _get_bot_manager()
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        instance = await bot_manager.get_instance_status(instance_id)

        if instance is None:
            return api_response(
                success=False,
                message=f"Bot instance '{instance_id}' not found",
                status_code=404,
            )

        return api_response(
            success=True,
            data=instance.model_dump(),
            message=f"Retrieved status for bot instance '{instance_id}'",
        )

    except Exception as exc:
        logger.error(f"Error getting bot instance {instance_id}: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


@router.delete("/api/v1/bots/{instance_id}")
async def delete_bot_instance(
    instance_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Delete bot instance"""

    try:
        bot_manager = _get_bot_manager()
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        existing_config = await run_db(
            _persist_bot_status_and_event,
            instance_id,
            event_type=None,
        )
        result = await bot_manager.delete_instance(instance_id)

        if result.success:
            await run_db(_delete_bot_db_record, instance_id)
            _send_bot_lifecycle_notification(
                "deleted",
                instance_id,
                existing_config,
                current_user,
                success=True,
                details=_resolve_action_details(
                    result.message,
                    "Runtime definition deleted successfully.",
                ),
            )
            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{instance_id}' deleted successfully",
            )

        _send_bot_lifecycle_notification(
            "delete",
            instance_id,
            existing_config,
            current_user,
            success=False,
            details=_resolve_action_details(
                result.error or result.message,
                "Runtime deletion failed.",
            ),
        )
        return api_response(success=False, message=result.message, status_code=400)

    except Exception as exc:
        logger.error(f"Error deleting bot instance {instance_id}: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


@router.post("/api/v1/bots/{instance_id}/start")
async def start_bot_instance(
    instance_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
):
    """Start bot instance"""

    _ = background_tasks
    try:
        bot_manager = _get_bot_manager()
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        result = await bot_manager.start_instance(instance_id)

        if result.success:
            persisted_config = await run_db(
                _persist_bot_status_and_event,
                instance_id,
                status=BotStatusEnum.RUNNING,
                process_id=(result.data.get("process_id") if result.data else None),
                event_type="bot_started",
                severity="info",
                message=f"Bot started via API (PID: {result.data.get('process_id') if result.data else 'unknown'})",
                details={
                    "process_id": result.data.get("process_id") if result.data else None
                },
            )
            _send_bot_lifecycle_notification(
                "started",
                instance_id,
                persisted_config,
                current_user,
                success=True,
                details=_resolve_action_details(
                    result.message,
                    "Runtime process started successfully.",
                ),
            )

            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{instance_id}' started successfully",
            )

        persisted_config = await run_db(
            _persist_bot_status_and_event,
            instance_id,
            status=BotStatusEnum.ERROR,
            process_id=None,
            event_type="bot_start_failed",
            severity="error",
            message=_resolve_action_details(result.message, "Bot failed to start"),
            details={"error": result.error or result.message},
        )
        _send_bot_lifecycle_notification(
            "start",
            instance_id,
            persisted_config,
            current_user,
            success=False,
            details=_resolve_action_details(
                result.error or result.message,
                "Runtime start failed before reaching RUNNING state.",
            ),
        )
        return api_response(success=False, message=result.message, status_code=400)

    except Exception as exc:
        logger.error(f"Error starting bot instance {instance_id}: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


@router.post("/api/v1/bots/{instance_id}/stop")
async def stop_bot_instance(
    instance_id: str,
    force: bool = False,
    current_user: User = Depends(get_current_active_user),
):
    """Stop bot instance"""

    try:
        bot_manager = _get_bot_manager()
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        result = await bot_manager.stop_instance(instance_id, force=force)

        if result.success:
            persisted_config = await run_db(
                _persist_bot_status_and_event,
                instance_id,
                status=BotStatusEnum.STOPPED,
                process_id=None,
                event_type="bot_stopped",
                severity="info",
                message=f"Bot stopped via API (force={force})",
                details={"force": force},
            )
            _send_bot_lifecycle_notification(
                "stopped",
                instance_id,
                persisted_config,
                current_user,
                success=True,
                details=_resolve_action_details(
                    result.message,
                    "Runtime process stopped successfully.",
                ),
                reason="Force stop" if force else "Operator stop",
            )

            return api_response(
                success=True,
                data=result.model_dump(),
                message=f"Bot instance '{instance_id}' stopped successfully",
            )

        persisted_config = await run_db(
            _persist_bot_status_and_event,
            instance_id,
            status=BotStatusEnum.ERROR,
            process_id=None,
            event_type="bot_stop_failed",
            severity="error",
            message=_resolve_action_details(result.message, "Bot failed to stop"),
            details={"error": result.error or result.message, "force": force},
        )
        _send_bot_lifecycle_notification(
            "stop",
            instance_id,
            persisted_config,
            current_user,
            success=False,
            details=_resolve_action_details(
                result.error or result.message,
                "Runtime stop request failed.",
            ),
            reason="Force stop" if force else "Operator stop",
        )
        return api_response(success=False, message=result.message, status_code=400)

    except Exception as exc:
        logger.error(f"Error stopping bot instance {instance_id}: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


@router.post("/api/v1/bots/{instance_id}/restart")
async def restart_bot_instance(
    instance_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Restart bot instance"""

    try:
        bot_manager = _get_bot_manager()
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        stop_result = await bot_manager.stop_instance(instance_id, force=False)
        if not stop_result.success:
            persisted_config = await run_db(
                _persist_bot_status_and_event,
                instance_id,
                status=BotStatusEnum.ERROR,
                process_id=None,
                event_type="bot_restart_failed",
                severity="error",
                message=_resolve_action_details(
                    stop_result.message,
                    "Failed to stop runtime during restart",
                ),
                details={
                    "phase": "stop",
                    "error": stop_result.error or stop_result.message,
                },
            )
            _send_bot_lifecycle_notification(
                "restart",
                instance_id,
                persisted_config,
                current_user,
                success=False,
                details=_resolve_action_details(
                    stop_result.error or stop_result.message,
                    "Restart failed during stop phase.",
                ),
                reason="Operator restart",
            )
            return api_response(
                success=False,
                message=f"Failed to stop instance: {stop_result.message}",
                status_code=400,
            )

        await asyncio.sleep(2)
        start_result = await bot_manager.start_instance(instance_id)

        if start_result.success:
            persisted_config = await run_db(
                _persist_bot_status_and_event,
                instance_id,
                status=BotStatusEnum.RUNNING,
                process_id=(
                    start_result.data.get("process_id") if start_result.data else None
                ),
                event_type="bot_restarted",
                severity="info",
                message=f"Bot restarted via API (PID: {start_result.data.get('process_id') if start_result.data else 'unknown'})",
                details={
                    "process_id": (
                        start_result.data.get("process_id")
                        if start_result.data
                        else None
                    )
                },
            )
            _send_bot_lifecycle_notification(
                "restarted",
                instance_id,
                persisted_config,
                current_user,
                success=True,
                details=_resolve_action_details(
                    start_result.message,
                    "Runtime restarted successfully.",
                ),
                reason="Operator restart",
            )
            return api_response(
                success=True,
                data=start_result.model_dump(),
                message=f"Bot instance '{instance_id}' restarted successfully",
            )

        persisted_config = await run_db(
            _persist_bot_status_and_event,
            instance_id,
            status=BotStatusEnum.ERROR,
            process_id=None,
            event_type="bot_restart_failed",
            severity="error",
            message=_resolve_action_details(
                start_result.message,
                "Failed to start runtime during restart",
            ),
            details={
                "phase": "start",
                "error": start_result.error or start_result.message,
            },
        )
        _send_bot_lifecycle_notification(
            "restart",
            instance_id,
            persisted_config,
            current_user,
            success=False,
            details=_resolve_action_details(
                start_result.error or start_result.message,
                "Restart failed during start phase.",
            ),
            reason="Operator restart",
        )
        return api_response(
            success=False,
            message=f"Failed to start instance: {start_result.message}",
            status_code=400,
        )

    except Exception as exc:
        logger.error(f"Error restarting bot instance {instance_id}: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


@router.post("/api/v1/bots/quick-deploy")
async def quick_deploy_bot(
    instance_name: str,
    credentials: BotCredentials,
    trading_params: TradingParameters,
    auto_start: bool = True,
    current_user: User = Depends(get_current_active_user),
):
    """Quick deploy and optionally start a new bot instance"""

    _ = current_user
    try:
        bot_manager = _get_bot_manager()
        if bot_manager is None:
            return _bot_manager_unavailable_response()
        instance_id = re.sub(r"[^a-zA-Z0-9_-]", "-", instance_name.lower())
        instance_id = (
            f"{instance_id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        )

        config = BotInstanceConfig(
            instance_id=instance_id,
            instance_name=instance_name,
            credentials=credentials,
            trading_params=trading_params,
        )

        create_result = await bot_manager.create_instance(config)
        if not create_result.success:
            return api_response(
                success=False,
                message=create_result.message,
                status_code=400,
            )

        if auto_start:
            await asyncio.sleep(1)
            start_result = await bot_manager.start_instance(instance_id)

            if start_result.success:
                return api_response(
                    success=True,
                    data={
                        "instance_id": instance_id,
                        "created": create_result.success,
                        "started": start_result.success,
                        "status": "running",
                    },
                    message=f"Bot '{instance_name}' deployed and started successfully",
                )
            return api_response(
                success=True,
                data={
                    "instance_id": instance_id,
                    "created": create_result.success,
                    "started": False,
                    "status": "stopped",
                    "start_error": start_result.message,
                },
                message=f"Bot '{instance_name}' deployed but failed to start: {start_result.message}",
            )

        return api_response(
            success=True,
            data={
                "instance_id": instance_id,
                "created": create_result.success,
                "started": False,
                "status": "stopped",
            },
            message=f"Bot '{instance_name}' deployed successfully (not started)",
        )

    except Exception as exc:
        logger.error(f"Error in quick deploy: {exc}")
        return api_response(
            success=False,
            message=f"Internal server error: {str(exc)}",
            status_code=500,
        )


__all__ = [
    "configure_bot_lifecycle",
    "create_bot_instance",
    "delete_bot_instance",
    "get_bot_instance",
    "list_bot_instances",
    "quick_deploy_bot",
    "restart_bot_instance",
    "router",
    "start_bot_instance",
    "stop_bot_instance",
]
