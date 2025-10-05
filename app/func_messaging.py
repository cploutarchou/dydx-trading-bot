import requests
from constants import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN


# Send Message
def send_message(message):
    """Send a Telegram message using configured credentials.

    If credentials are not set, the function returns 'no-token' to avoid
    raising exceptions during startup.
    """
    bot_token = TELEGRAM_TOKEN
    chat_id = TELEGRAM_CHAT_ID

    if not bot_token or not chat_id:
        # Messaging is optional; avoid crashing the bot when not configured.
        return "no-token"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={message}"
    try:
        res = requests.get(url, timeout=10)
        return "sent" if res.status_code == 200 else "failed"
    except Exception:
        return "failed"
