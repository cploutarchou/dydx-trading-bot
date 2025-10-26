"""
Database configuration and connection management for backtest results storage.
Supports both SQLite (development) and PostgreSQL (production).
"""

import config.config

import logging
import os
import sqlite3
import psycopg2
from contextlib import contextmanager

logger = logging.getLogger(__name__)

db = None
# Global database config (populated by init)
db_config = {}


def init():
    global db_config, db
    db_settings = config.config.DatabaseSettings

    if db_settings.type == "postgresql":
        logger.info("Using PostgreSQL database.")
        db_config = {
            "type": "postgresql",
            "name": getattr(db_settings, "name", None),
            "user": getattr(db_settings, "user", None),
            "password": getattr(db_settings, "password", None),
            "host": getattr(db_settings, "host", None),
            "port": getattr(db_settings, "port", 5432),
        }
        try:
            db = psycopg2.connect(
                dbname=db_config["name"],
                user=db_config["user"],
                password=db_config["password"],
                host=db_config["host"],
                port=db_config["port"],
            )
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            db = None
    else:
        logger.info("Using SQLite database.")
        db_config = {
            "type": "sqlite",
            "name": getattr(db_settings, "name", "dydx_backtest.db"),
        }
        try:
            db = sqlite3.connect(get_sqlite_path())
            db.row_factory = sqlite3.Row
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            db = None


def get_sqlite_path():
    db_name = db_config.get("name", "dydx_backtest.db")
    return os.path.join(os.path.dirname(__file__), "..", "app", db_name)


@contextmanager
def get_db_connection():
    db_type = db_config.get("type", "sqlite")
    if db_type == "postgresql":
        conn = psycopg2.connect(
            dbname=db_config["name"],
            user=db_config["user"],
            password=db_config["password"],
            host=db_config["host"],
            port=db_config["port"],
        )
    else:
        conn = sqlite3.connect(get_sqlite_path())
        conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# Example utility for executing a query
def execute_query(query, params=None, fetchone=False, fetchall=False, commit=False):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, params or ())
        result = None
        if fetchone:
            result = cur.fetchone()
        elif fetchall:
            result = cur.fetchall()
        if commit:
            conn.commit()
        cur.close()
        return result
