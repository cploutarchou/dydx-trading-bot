"""
Database configuration and connection management for backtest results storage.
Supports both SQLite (development) and PostgreSQL (production).
"""

from dotenv import load_dotenv
load_dotenv()

import logging
import os
import sqlite3
import psycopg2
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

# Utility to get DB config from env or config_loader
def get_database_config():
    try:
        from backend.config_loader import get_config_loader
        config_loader = get_config_loader()
        return config_loader.get_database_config()
    except ImportError:
        return {
            "type": os.getenv("DB_TYPE", "sqlite"),
            "name": os.getenv("DB_NAME", "dydx_backtest.db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", ""),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
        }

def get_database_url():
    db_config = get_database_config()
    db_type = db_config.get("type", "sqlite")
    db_name = db_config.get("name", "dydx_backtest.db")
    db_user = db_config.get("user", "postgres")
    db_password = db_config.get("password", "")
    db_host = db_config.get("host", "localhost")
    db_port = db_config.get("port", "5432")
    if db_type == "postgresql":
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        db_path = os.path.join(os.path.dirname(__file__), "..", "app", db_name)
        return f"sqlite:///{db_path}"

DATABASE_URL = get_database_url()
db_config = get_database_config()

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

# Remove all ORM/SQLAlchemy code, session management, and model imports.
# All table creation and admin seeding logic should be moved to migration scripts or handled via raw SQL elsewhere.