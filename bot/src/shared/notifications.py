"""Telegram messaging system for dYdX Trading Bot."""
import logging
from datetime import datetime
from typing import Any, Dict

import requests
from src.constants import DYDX_ADDRESS, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN

logger = logging.getLogger(__name__)


class TelegramMessenger:
    """Professional Telegram messaging system for dYdX Trading Bot."""

    def __init__(self):
        self.bot_token = TELEGRAM_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            logger.warning("Telegram messaging disabled - missing token or chat_id")

    def _format_timestamp(self) -> str:
        """Format current timestamp for messages."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    def _send_request(self, method: str, data: Dict[str, Any]) -> bool:
        """Send HTTP request to Telegram API."""
        if not self.enabled:
            return False

        try:
            url = f"{self.base_url}/{method}"
            response = requests.post(url, json=data, timeout=15)

            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram API error {response.status_code}: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a formatted message to Telegram."""
        if not self.enabled:
            return False

        data = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        return self._send_request("sendMessage", data)

    def send_startup_message(self, config_info: Dict[str, Any]) -> bool:
        """Send bot startup notification with configuration details."""
        environment = config_info.get("environment", "development")
        is_testnet = config_info.get("is_testnet", True)
        strategy = config_info.get("strategy", "unknown")

        # Smart environment detection
        if environment == "unknown" or environment == "development":
            environment = "development" if is_testnet else "production"

        network = "🧪 TESTNET" if is_testnet else "🔴 MAINNET"
        env_emoji = "🧪" if environment == "development" else "🚀" if environment == "production" else "⚙️"

        # Create clickable account link based on environment
        if environment == "development" or is_testnet:
            mintscan_url = f"https://www.mintscan.io/dydx-testnet/account/{DYDX_ADDRESS}"
            network_text = "Testnet"
        else:
            mintscan_url = f"https://www.mintscan.io/dydx/account/{DYDX_ADDRESS}"
            network_text = "Mainnet"

        account_display = f"{DYDX_ADDRESS[:8]}...{DYDX_ADDRESS[-6:]}"

        message = f"""
🤖 <b>dYdX Trading Bot Started</b>

{env_emoji} <b>Environment:</b> {environment.upper()}
{network} <b>Network:</b> {network_text}
📈 <b>Strategy:</b> {strategy.title()}
👤 <b>Account:</b> <a href="{mintscan_url}">{account_display}</a>

⏰ <b>Started:</b> {self._format_timestamp()}

<i>Bot is now monitoring markets and will notify you of all trading activities.</i>
        """.strip()

        return self.send_message(message)

    def send_error_message(self, error_type: str, error_details: str, is_critical: bool = False) -> bool:
        """Send formatted error notification."""
        emoji = "🚨" if is_critical else "⚠️"
        severity = "CRITICAL ERROR" if is_critical else "ERROR"

        message = f"""
{emoji} <b>{severity}</b>

🔍 <b>Type:</b> {error_type}
📝 <b>Details:</b> {error_details}
⏰ <b>Time:</b> {self._format_timestamp()}

<i>{"Bot may have stopped - check immediately!" if is_critical else "Monitoring continues - review when convenient."}</i>
        """.strip()

        return self.send_message(message)

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

    def send_trade_closed_message(self, trade_info: Dict[str, Any], reason: str = "Z-score reversion") -> bool:
        """Send notification when trade is closed."""
        market_1 = trade_info.get("market_1", "Unknown")
        market_2 = trade_info.get("market_2", "Unknown")
        z_score = trade_info.get("current_zscore", 0.0)

        reason_emoji = {
            "Z-score reversion": "🎯",
            "Manual close": "👨‍💼",
            "Error recovery": "🛠️",
            "Emergency stop": "🚨"
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

    def send_cointegration_results(self, pairs_found: int, analysis_time: float,
                                   high_confidence_pairs: int = 0) -> bool:
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

        # Create clickable account link
        if is_testnet:
            mintscan_url = f"https://www.mintscan.io/dydx-testnet/account/{DYDX_ADDRESS}"
        else:
            mintscan_url = f"https://www.mintscan.io/dydx/account/{DYDX_ADDRESS}"

        account_display = f"{DYDX_ADDRESS[:8]}...{DYDX_ADDRESS[-6:]}"

        message = f"""
💰 <b>ACCOUNT STATUS</b>

{balance_emoji} <b>Total Balance:</b> ${balance:.2f}
💵 <b>Available:</b> ${available_balance:.2f}
📊 <b>Open Positions:</b> {open_positions}
👤 <b>Account:</b> <a href="{mintscan_url}">{account_display}</a>

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
        message = f"""
🛑 <b>dYdX Trading Bot Stopped</b>

🔍 <b>Reason:</b> {reason}
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


def send_error_notification(error_type: str, error_details: str, is_critical: bool = False) -> bool:
    """Send formatted error notification."""
    return _messenger.send_error_message(error_type, error_details, is_critical)


def send_trade_notification(action: str, trade_info: Dict[str, Any], **kwargs) -> bool:
    """Send trade-related notifications."""
    if action == "opened":
        return _messenger.send_trade_opened_message(trade_info)
    elif action == "closed":
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


def send_shutdown_notification(reason: str = "Manual stop") -> bool:
    """Send shutdown notification."""
    return _messenger.send_shutdown_message(reason)

