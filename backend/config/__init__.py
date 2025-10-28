import os

from dotenv import load_dotenv
from config import config


def load_config(path: str = ".env"):
    load_dotenv(dotenv_path=path)


indexer = config.IndexerEndpoint(mainnet="https://indexer.dydx.trade",
                                 testnet="https://indexer.v4testnet.dydx.exchange")

Telegram = config.TelegramSettings(token=os.getenv("TELEGRAM_TOKEN"), chat_id=os.getenv("TELEGRAM_CHAT_ID"))

DYDX = config.DYDX(
    is_testnet=os.getenv("IS_TESTNET") == "True",
    DYDXTestnetSettings=config.DYDXTestnetSettings(os.getenv("DYDX_TESTNET_ADDRESS"), os.getenv("DYDX_TESTNET_SECRET")),
    DYDXMainnetSettings=config.DYDXMainnetSettings(os.getenv("DYDX_MAINNET_ADDRESS"), os.getenv("DYDX_MAINNET_SECRET"))
)

Loki = config.LokiSettings(
    enabled=os.getenv("LOKI_ENABLED") == "True",
    url=os.getenv("LOKI_PUSH_URL"),
    username=os.getenv("LOKI_USERNAME"),
    password=os.getenv("LOKI_PASSWORD"),
    tenant_id=os.getenv("LOKI_TENANT_ID"),
    labels=dict(label.split('=', 1) for label in os.getenv("LOKI_LABELS", "").split(",") if label))

Database = config.DatabaseSettings(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("DB_NAME", "dydx_bot"),
    user=os.getenv("DB_USER", "dydx_bot"),
    type=os.getenv("DB_TYPE", "postgresql"),
    password=os.getenv("DB_PASSWORD", ""),
    ssl=os.getenv("SSL_MODE", "false").lower() == "true",
    timeout=int(os.getenv("DB_TIMEOUT", 5)),
    max_connections=int(os.getenv("DB_MAX_CONNECTIONS", 10)),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 10)),
    enabled=os.getenv("DB_ENABLED", "true").lower() == "true",
    pool_size=int(os.getenv("DB_POOL_SIZE", 5))
)

Redis = config.RedisSettings(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    password=os.getenv("REDIS_PASSWORD", None),
    ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
    timeout=int(os.getenv("REDIS_TIMEOUT", 5)),
    cache_ttl_seconds=int(os.getenv("REDIS_CACHE_TTL", "86400")),
    max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
    enabled=os.getenv("REDIS_ENABLED", "true").lower() == "true",
)

Auth = config.AuthSettings(
    jwt_secret_key=os.getenv("JWT_SECRET_KEY",
                             "your - secret - key - change - in -production - use - strong - key - 32 - chars"),
    jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
    access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
    refresh_token_expire_days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
)

APP_CONFIG = config.Config(
    database=Database,
    indexer=indexer,
    telegram=Telegram,
    dydx=DYDX,
    loki=Loki,
    redis=Redis,
    auth=Auth
)
