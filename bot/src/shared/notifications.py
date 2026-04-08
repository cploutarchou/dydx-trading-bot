"""Telegram messaging system for dYdX Trading Bot."""

import html
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from loguru import logger
from src.constants import DYDX_ADDRESS, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN



class TelegramMessenger:
    """Professional Telegram messaging system for dYdX Trading Bot."""

    _disabled_notice_logged = False
    _recent_messages: Dict[str, float] = {}

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        environment: Optional[str] = None,
    ):
        self.bot_token = (bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or TELEGRAM_TOKEN)
        self.chat_id = (chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip() or TELEGRAM_CHAT_ID)
        self.instance_id = str(instance_id or "").strip()
        self.environment = str(environment or "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled and not TelegramMessenger._disabled_notice_logged:
            logger.info("Telegram messaging disabled (token/chat_id not configured)")
            TelegramMessenger._disabled_notice_logged = True

    def _format_timestamp(self) -> str:
        """Format current timestamp for messages."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    def _escape_html(self, value: Any) -> str:
        """Escape dynamic values to keep Telegram HTML parse mode safe."""
        return html.escape(str(value), quote=True)

    def _instance_prefix(self) -> str:
        instance_id = self.instance_id or os.getenv("BOT_INSTANCE_ID", "").strip()
        if not instance_id:
            return ""
        return f"🧩 <b>Instance:</b> {self._escape_html(instance_id)}\n"

    def _environment_prefix(self) -> str:
        environment = (
            self.environment or os.getenv("ENVIRONMENT", "development")
        ).strip().lower()
        return f"🌍 <b>Env:</b> {self._escape_html(environment)}\n"

    def _truncate_text(self, text: str, hard_limit: int = 3900) -> str:
        """Keep payload under Telegram text limits while preserving parseability."""
        if len(text) <= hard_limit:
            return text
        return text[: hard_limit - 24].rstrip() + "\n\n<i>[message truncated]</i>"

    def _resolve_account_address(self, explicit_address: Optional[Any] = None) -> str:
        """Resolve the best available dYdX account address for notifications."""
        if explicit_address is not None:
            candidate = str(explicit_address).strip()
            if candidate:
                return candidate
        return str(DYDX_ADDRESS or "").strip()

    def _format_account_link(self, account_address: str, is_testnet: bool) -> str:
        """Render account link markup when an address is available."""
        if not account_address:
            return "Unavailable"

        if is_testnet:
            mintscan_url = f"https://www.mintscan.io/dydx-testnet/account/{account_address}"
        else:
            mintscan_url = f"https://www.mintscan.io/dydx/account/{account_address}"

        if len(account_address) > 14:
            account_display = f"{account_address[:8]}...{account_address[-6:]}"
        else:
            account_display = account_address

        return f'<a href="{mintscan_url}">{self._escape_html(account_display)}</a>'

    def _safe_env_int(self, env_name: str, default: int) -> int:
        raw = os.getenv(env_name, str(default)).strip()
        try:
            value = int(raw)
            return max(0, value)
        except (TypeError, ValueError):
            return default

    def _normalize_error_category(self, category: Optional[str], error_type: str) -> str:
        source = (category or error_type or "general").strip().lower()
        normalized = [ch if ch.isalnum() else "_" for ch in source]
        compact = "".join(normalized).strip("_")
        while "__" in compact:
            compact = compact.replace("__", "_")
        return compact or "general"

    def _resolve_error_dedupe_window_seconds(
        self,
        category: str,
        is_critical: bool,
    ) -> int:
        if is_critical:
            return self._safe_env_int("TELEGRAM_ERROR_DEDUPE_SECONDS_CRITICAL", 0)

        category_env = f"TELEGRAM_ERROR_DEDUPE_SECONDS_{category.upper()}"
        if os.getenv(category_env) is not None:
            return self._safe_env_int(category_env, 120)
        return self._safe_env_int("TELEGRAM_ERROR_DEDUPE_SECONDS_DEFAULT", 120)

    def _should_skip_duplicate(self, key: str, window_seconds: int) -> bool:
        if window_seconds <= 0 or not key:
            return False
        now = time.time()
        last_seen = TelegramMessenger._recent_messages.get(key, 0.0)
        if now - last_seen < window_seconds:
            return True
        TelegramMessenger._recent_messages[key] = now
        return False

    def _send_request(self, method: str, data: Dict[str, Any]) -> bool:
        """Send HTTP request to Telegram API."""
        if not self.enabled:
            return False

        url = f"{self.base_url}/{method}"
        attempts = max(1, int(os.getenv("TELEGRAM_SEND_RETRIES", "3") or "3"))
        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(url, json=data, timeout=15)

                if response.status_code == 200:
                    return True

                if (
                    response.status_code == 403
                    and "bots can't send messages to bots" in response.text.lower()
                ):
                    logger.error(
                        "Telegram delivery blocked: TELEGRAM_CHAT_ID '{}' appears to belong to a bot account. "
                        "Use a user/group/channel chat id and ensure that chat has started/interacted with this bot.",
                        self.chat_id,
                    )
                    return False

                transient = response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}
                if transient and attempt < attempts:
                    retry_after = 0.0
                    if response.status_code == 429:
                        try:
                            retry_after = float(response.json().get("parameters", {}).get("retry_after", 0))
                        except Exception:
                            retry_after = 0.0
                    backoff = retry_after if retry_after > 0 else min(2.0, 0.5 * attempt)
                    logger.warning(
                        "Telegram API transient error {} on attempt {}/{}; retrying in {:.2f}s",
                        response.status_code,
                        attempt,
                        attempts,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue

                logger.error("Telegram API error {}: {}", response.status_code, response.text)
                return False

            except requests.exceptions.RequestException as e:
                if attempt < attempts:
                    backoff = min(2.0, 0.5 * attempt)
                    logger.warning(
                        "Telegram request failure on attempt {}/{}: {}; retrying in {:.2f}s",
                        attempt,
                        attempts,
                        e,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue
                logger.error("Failed to send Telegram message after retries: {}", e)
                return False

        return False

    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        dedupe_key: Optional[str] = None,
        dedupe_window_seconds: Optional[int] = None,
    ) -> bool:
        """Send a formatted message to Telegram."""
        if not self.enabled:
            return False

        if dedupe_window_seconds is None:
            dedupe_window_seconds = int(os.getenv("TELEGRAM_DEDUPE_SECONDS", "0") or "0")
        if dedupe_key and self._should_skip_duplicate(dedupe_key, dedupe_window_seconds):
            logger.info("Skipping duplicate Telegram notification key={}", dedupe_key)
            return False

        safe_text = self._truncate_text(text)

        data = {
            "chat_id": self.chat_id,
            "text": safe_text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        return self._send_request("sendMessage", data)

    def send_startup_message(self, config_info: Dict[str, Any]) -> bool:
        """Send bot startup notification with configuration details."""
        environment = config_info.get("environment", "development")
        is_testnet = config_info.get("is_testnet", True)
        strategy = self._escape_html(config_info.get("strategy", "unknown"))
        account_link = self._format_account_link(
            self._resolve_account_address(config_info.get("account_address")),
            bool(is_testnet),
        )

        # Smart environment detection
        if environment in ("unknown", "development"):
            environment = "development" if is_testnet else "production"

        network = "🧪 TESTNET" if is_testnet else "🔴 MAINNET"
        env_emoji = (
            "🧪" if environment == "development" else "🚀" if environment == "production" else "⚙️"
        )

        network_text = "Testnet" if environment == "development" or is_testnet else "Mainnet"

        message = f"""
🤖 <b>dYdX Trading Bot Started</b>

{self._instance_prefix()}{self._environment_prefix()}

{env_emoji} <b>Environment:</b> {environment.upper()}
{network} <b>Network:</b> {network_text}
📈 <b>Strategy:</b> {strategy.title()}
👤 <b>Account:</b> {account_link}

⏰ <b>Started:</b> {self._format_timestamp()}

<i>Bot is now monitoring markets and will notify you of all trading activities.</i>
        """.strip()

        return self.send_message(message)

    def send_lifecycle_message(
        self,
        action: str,
        lifecycle_info: Dict[str, Any],
        *,
        success: bool = True,
    ) -> bool:
        """Send operator lifecycle notifications for runtime actions."""
        normalized_action = str(action or "updated").strip().lower()
        strategy = self._escape_html(lifecycle_info.get("strategy", "unknown"))
        instance_name = self._escape_html(lifecycle_info.get("instance_name", ""))
        operator = self._escape_html(lifecycle_info.get("operator", "system"))
        details = self._escape_html(lifecycle_info.get("details", ""))
        reason = self._escape_html(lifecycle_info.get("reason", ""))
        account_link = self._format_account_link(
            self._resolve_account_address(lifecycle_info.get("account_address")),
            bool(lifecycle_info.get("is_testnet", True)),
        )
        network_text = "Testnet" if lifecycle_info.get("is_testnet", True) else "Mainnet"

        title_map = {
            "created": ("🆕", "RUNTIME CREATED"),
            "start": ("▶️", "RUNTIME STARTED"),
            "started": ("▶️", "RUNTIME STARTED"),
            "stop": ("🛑", "RUNTIME STOPPED"),
            "stopped": ("🛑", "RUNTIME STOPPED"),
            "restart": ("🔄", "RUNTIME RESTARTED"),
            "restarted": ("🔄", "RUNTIME RESTARTED"),
            "delete": ("🗑️", "RUNTIME DELETED"),
            "deleted": ("🗑️", "RUNTIME DELETED"),
            "pause": ("⏸️", "RUNTIME PAUSED"),
            "paused": ("⏸️", "RUNTIME PAUSED"),
            "resume": ("▶️", "RUNTIME RESUMED"),
            "resumed": ("▶️", "RUNTIME RESUMED"),
            "error": ("🚨", "RUNTIME ACTION FAILED"),
            "failed": ("🚨", "RUNTIME ACTION FAILED"),
        }
        emoji, title = title_map.get(normalized_action, ("ℹ️", "RUNTIME UPDATED"))
        if not success and normalized_action not in {"error", "failed"}:
            emoji, title = ("🚨", f"{title} FAILED")

        lines = [
            f"{emoji} <b>{title}</b>",
            "",
            f"{self._instance_prefix()}{self._environment_prefix()}".rstrip(),
            "",
            f"🤖 <b>Runtime:</b> {instance_name or self._escape_html(lifecycle_info.get('instance_id', 'unknown'))}",
            f"📈 <b>Strategy:</b> {strategy.title()}",
            f"🌐 <b>Network:</b> {self._escape_html(network_text)}",
            f"👤 <b>Account:</b> {account_link}",
            f"🧑 <b>Operator:</b> {operator}",
        ]
        if reason:
            lines.append(f"🔍 <b>Reason:</b> {reason}")
        if details:
            lines.append(f"📝 <b>Details:</b> {details}")
        lines.extend(
            [
                f"⏰ <b>Time:</b> {self._format_timestamp()}",
                "",
                "<i>Operator action recorded and synchronized with runtime control.</i>",
            ]
        )

        dedupe_key = (
            f"lifecycle:{normalized_action}:{self.instance_id or lifecycle_info.get('instance_id', '')}:"
            f"{'success' if success else 'failure'}"
        )
        return self.send_message("\n".join(lines), dedupe_key=dedupe_key, dedupe_window_seconds=0)

    def send_error_message(
        self,
        error_type: str,
        error_details: str,
        is_critical: bool = False,
        category: Optional[str] = None,
    ) -> bool:
        """Send formatted error notification."""
        emoji = "🚨" if is_critical else "⚠️"
        severity = "CRITICAL ERROR" if is_critical else "ERROR"
        error_category = self._normalize_error_category(category, error_type)
        dedupe_window_seconds = self._resolve_error_dedupe_window_seconds(
            error_category,
            is_critical,
        )

        safe_type = self._escape_html(error_type)
        safe_details = self._escape_html(error_details)
        message = f"""
{emoji} <b>{severity}</b>

{self._instance_prefix()}{self._environment_prefix()}

🔍 <b>Type:</b> {safe_type}
📝 <b>Details:</b> {safe_details}
🏷️ <b>Category:</b> {self._escape_html(error_category)}
⏰ <b>Time:</b> {self._format_timestamp()}

<i>{"Bot may have stopped - check immediately!" if is_critical else "Monitoring continues - review when convenient."}</i>
        """.strip()

        dedupe_key = f"error:{'critical' if is_critical else 'normal'}:{error_category}"
        return self.send_message(
            message,
            dedupe_key=dedupe_key,
            dedupe_window_seconds=dedupe_window_seconds,
        )

    def send_trade_opened_message(self, trade_info: Dict[str, Any]) -> bool:
        """Send notification when new trade is opened."""
        market_1 = trade_info.get("market_1", "Unknown")
        market_2 = trade_info.get("market_2", "Unknown")
        z_score = trade_info.get("z_score", 0.0)
        hedge_ratio = trade_info.get("hedge_ratio", 0.0)
        size_1 = trade_info.get("size_1", 0.0)
        size_2 = trade_info.get("size_2", 0.0)
        side_1 = trade_info.get("side_1", "")
        side_2 = trade_info.get("side_2", "")

        direction_emoji = "📈" if z_score > 0 else "📉"

        message = f"""
{direction_emoji} <b>NEW POSITION OPENED</b>

🔄 <b>Pair:</b> {market_1} / {market_2}
📊 <b>Z-Score:</b> {z_score:.3f}
⚖️ <b>Hedge Ratio:</b> {hedge_ratio:.4f}

<b>Positions:</b>
• {market_1}: {side_1} {size_1}
• {market_2}: {side_2} {size_2}

⏰ <b>Opened:</b> {self._format_timestamp()}

<i>Position will be monitored for exit signals.</i>
        """.strip()

        return self.send_message(message)

    def send_trade_closed_message(
        self, trade_info: Dict[str, Any], reason: str = "Z-score reversion"
    ) -> bool:
        """Send notification when trade is closed."""
        market_1 = trade_info.get("market_1", "Unknown")
        market_2 = trade_info.get("market_2", "Unknown")
        z_score = trade_info.get("current_zscore", 0.0)

        reason_emoji = {
            "Z-score reversion": "🎯",
            "Manual close": "👨‍💼",
            "Error recovery": "🛠️",
            "Emergency stop": "🚨",
        }.get(reason, "✅")

        message = f"""
{reason_emoji} <b>POSITION CLOSED</b>

🔄 <b>Pair:</b> {market_1} / {market_2}
📊 <b>Final Z-Score:</b> {z_score:.3f}
🎯 <b>Reason:</b> {reason}

⏰ <b>Closed:</b> {self._format_timestamp()}

<i>Position successfully closed and removed from tracking.</i>
        """.strip()

        return self.send_message(message)

    def send_cointegration_results(
        self, pairs_found: int, analysis_time: float, high_confidence_pairs: int = 0
    ) -> bool:
        """Send enhanced cointegration analysis results."""
        confidence_ratio = (high_confidence_pairs / pairs_found * 100) if pairs_found > 0 else 0

        status_emoji = "🎯" if high_confidence_pairs > 0 else "📊" if pairs_found > 0 else "⚠️"

        message = f"""
🔬 <b>COINTEGRATION ANALYSIS COMPLETE</b>

{status_emoji} <b>Total Pairs Found:</b> {pairs_found}
⭐ <b>High-Confidence Pairs:</b> {high_confidence_pairs} ({confidence_ratio:.0f}%)
⏱️ <b>Analysis Time:</b> {analysis_time:.1f} seconds
⏰ <b>Completed:</b> {self._format_timestamp()}

<i>{"Ready for high-quality trading opportunities!" if high_confidence_pairs > 0 else "Ready to identify trading opportunities!" if pairs_found > 0 else "No suitable pairs found - will retry next cycle."}</i>
        """.strip()

        return self.send_message(message)

    def send_account_status(self, account_info: Dict[str, Any], is_testnet: bool = True) -> bool:
        """Send account status information."""
        balance = account_info.get("balance", 0.0)
        open_positions = account_info.get("open_positions", 0)
        available_balance = account_info.get("available_balance", 0.0)

        balance_emoji = "✅" if balance >= 100 else "⚠️" if balance >= 50 else "🚨"

        account_link = self._format_account_link(
            self._resolve_account_address(account_info.get("account_address")),
            is_testnet,
        )

        message = f"""
💰 <b>ACCOUNT STATUS</b>

{balance_emoji} <b>Total Balance:</b> ${balance:.2f}
💵 <b>Available:</b> ${available_balance:.2f}
📊 <b>Open Positions:</b> {open_positions}
👤 <b>Account:</b> {account_link}

⏰ <b>Updated:</b> {self._format_timestamp()}

<i>Minimum required balance: $100.00</i>
        """.strip()

        return self.send_message(message)

    def send_daily_summary(self, summary_info: Dict[str, Any]) -> bool:
        """Send daily trading summary."""
        trades_opened = summary_info.get("trades_opened", 0)
        trades_closed = summary_info.get("trades_closed", 0)
        active_positions = summary_info.get("active_positions", 0)

        message = f"""
📊 <b>DAILY SUMMARY</b>

📈 <b>Trades Opened:</b> {trades_opened}
📉 <b>Trades Closed:</b> {trades_closed}
⚡ <b>Active Positions:</b> {active_positions}

⏰ <b>Report Date:</b> {datetime.now().strftime("%Y-%m-%d")}

<i>Bot continues monitoring for opportunities.</i>
        """.strip()

        return self.send_message(message)

    def send_shutdown_message(self, reason: str = "Manual stop") -> bool:
        """Send bot shutdown notification."""
        safe_reason = self._escape_html(reason)
        message = f"""
🛑 <b>dYdX Trading Bot Stopped</b>

{self._instance_prefix()}{self._environment_prefix()}

🔍 <b>Reason:</b> {safe_reason}
⏰ <b>Stopped:</b> {self._format_timestamp()}

<i>Bot is no longer monitoring markets. All positions remain as they were.</i>
        """.strip()

        return self.send_message(message)


# Global messenger instance
_messenger = TelegramMessenger()


# Legacy function for backward compatibility
def send_message(message: str) -> str:
    """Legacy send message function - maintained for compatibility."""
    success = _messenger.send_message(message, parse_mode="Markdown")
    return "sent" if success else ("no-token" if not _messenger.enabled else "failed")


# New enhanced messaging functions
def send_startup_notification(config_info: Dict[str, Any]) -> bool:
    """Send professional startup notification."""
    return _messenger.send_startup_message(config_info)


def send_error_notification(
    error_type: str,
    error_details: str,
    is_critical: bool = False,
    category: Optional[str] = None,
) -> bool:
    """Send formatted error notification."""
    return _messenger.send_error_message(
        error_type,
        error_details,
        is_critical,
        category=category,
    )


def send_trade_notification(action: str, trade_info: Dict[str, Any], **kwargs) -> bool:
    """Send trade-related notifications."""
    if action == "opened":
        return _messenger.send_trade_opened_message(trade_info)
    if action == "closed":
        reason = kwargs.get("reason", "Z-score reversion")
        return _messenger.send_trade_closed_message(trade_info, reason)
    return False


def send_analysis_notification(pairs_found: int, analysis_time: float) -> bool:
    """Send cointegration analysis results."""
    return _messenger.send_cointegration_results(pairs_found, analysis_time)


def send_account_notification(account_info: Dict[str, Any], is_testnet: bool = True) -> bool:
    """Send account status notification."""
    return _messenger.send_account_status(account_info, is_testnet)


def send_daily_summary(summary_info: Dict[str, Any]) -> bool:
    """Send daily summary notification."""
    return _messenger.send_daily_summary(summary_info)


def send_lifecycle_notification(
    action: str, lifecycle_info: Dict[str, Any], success: bool = True
) -> bool:
    """Send lifecycle action notification."""
    return _messenger.send_lifecycle_message(action, lifecycle_info, success=success)


def send_shutdown_notification(reason: str = "Manual stop") -> bool:
    """Send shutdown notification."""
    return _messenger.send_shutdown_message(reason)
