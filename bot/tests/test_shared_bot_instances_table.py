"""bot_instances is shared with the backend when BOT_DB_CUTOVER_MODE=shared.

The backend's migrations create ``config`` as TEXT. On PostgreSQL SQLAlchemy's
JSON type leaves decoding to the driver, which only decodes json/jsonb columns,
so the bot used to read its own config back as a string. The live runtime then
failed in ``dict(bot.config)`` and exited seconds after it was started.
"""

import json
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from internal.domain.models import Bot, JSONDocument

_BACKEND_BOT_INSTANCES_DDL = """
CREATE TABLE bot_instances (
  id SERIAL PRIMARY KEY,
  instance_id TEXT NOT NULL UNIQUE,
  instance_name TEXT,
  user_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'STOPPED',
  network TEXT,
  strategy TEXT,
  config TEXT,
  trading_params TEXT,
  process_id INTEGER,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def test_json_document_decodes_a_text_column_value():
    column_type = JSONDocument()

    assert column_type.process_result_value('{"a": {"b": 1}}', None) == {"a": {"b": 1}}
    assert column_type.process_result_value(b'{"a": 1}', None) == {"a": 1}


def test_json_document_leaves_decoded_and_empty_values_alone():
    column_type = JSONDocument()
    already_decoded = {"a": 1}

    assert column_type.process_result_value(already_decoded, None) is already_decoded
    assert column_type.process_result_value(None, None) is None
    assert column_type.process_result_value("not json", None) == "not json"


def test_bot_config_uses_the_tolerant_json_type():
    assert isinstance(Bot.__table__.c.config.type, JSONDocument)


def _postgres_url() -> str:
    dsn = os.getenv("POSTGRES_TEST_DSN", "").strip()
    if not dsn:
        pytest.skip("POSTGRES_TEST_DSN is not set; needs a real PostgreSQL")
    return dsn.replace("postgres://", "postgresql+psycopg2://", 1).replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )


def test_runtime_reads_its_config_from_a_backend_created_table():
    engine = create_engine(_postgres_url())
    schema = "shared_table_probe"
    with engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    scoped = engine.execution_options(schema_translate_map={None: schema})
    try:
        with scoped.begin() as connection:
            connection.execute(text(f"SET search_path TO {schema}"))
            connection.execute(text(_BACKEND_BOT_INSTANCES_DDL))
            # The backend writes the row first, as a JSON string in a TEXT column.
            connection.execute(
                text(
                    "INSERT INTO bot_instances "
                    "(instance_id, instance_name, user_id, status, network, strategy, config) "
                    "VALUES ('strategy-85-1', 'probe', 85, 'STOPPED', 'testnet', "
                    "'cointegration', :config)"
                ),
                {"config": json.dumps({"instance_name": "probe"})},
            )

        session = sessionmaker(bind=scoped)()
        try:
            bot = session.query(Bot).filter(Bot.instance_id == "strategy-85-1").one()
            assert dict(bot.config) == {"instance_name": "probe"}

            # The bot API then stores its own (sealed) config on the same row.
            bot.config = {"instance_name": "probe", "credentials": {"ciphertext": "x"}}
            session.commit()
            session.expire_all()

            bot = session.query(Bot).filter(Bot.instance_id == "strategy-85-1").one()
            assert dict(bot.config)["credentials"] == {"ciphertext": "x"}
        finally:
            session.close()
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        engine.dispose()
