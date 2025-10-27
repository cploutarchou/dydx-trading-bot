"""Raw SQL/SQLAlchemy Core Database utilities used by tests.

Provides a Database class with static methods that execute SQL using the
SQLAlchemy engine from `db_init`. Methods return simple dicts/lists so tests
can remain lightweight and repository-local.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text, create_engine
import os

# Use in-memory SQLite for tests to avoid importing db_init/sqlmodel at import time
engine = create_engine(os.getenv("TEST_DB_URL", "sqlite:///:memory:"), echo=False)

# Verify connection; if it fails (no Postgres available in test environment),
# create an in-memory SQLite fallback and initialize tables from SQLModel metadata.
try:
    with engine.connect() as conn:  # quick check
        pass
except Exception:
    # fallback to sqlite in-memory for tests
    engine = create_engine("sqlite:///:memory:", echo=False)
    try:
        from models.sqlmodel_models import SQLModel

        SQLModel.metadata.create_all(engine)
    except Exception:
        # If SQLModel can't be imported/used, continue and create minimal tables below
        pass

    def _create_sqlite_tables(conn):
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(100) NOT NULL UNIQUE,
                hashed_password VARCHAR(500) NOT NULL,
                full_name VARCHAR(100),
                avatar TEXT,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                last_login TIMESTAMP
            )
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS backtest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id VARCHAR(50) NOT NULL UNIQUE,
                status VARCHAR(20),
                created_at TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                duration_seconds REAL,
                start_date VARCHAR(10) NOT NULL,
                end_date VARCHAR(10) NOT NULL,
                num_pairs INTEGER NOT NULL,
                total_markets INTEGER NOT NULL,
                config JSON,
                total_trades INTEGER,
                profitable_trades INTEGER,
                losing_trades INTEGER,
                win_rate REAL,
                total_pnl REAL,
                total_pnl_usd REAL,
                sharpe_ratio REAL,
                sortino_ratio REAL,
                calmar_ratio REAL,
                max_drawdown REAL,
                profit_factor REAL,
                starting_balance REAL,
                ending_balance REAL,
                max_balance REAL,
                min_balance REAL,
                error_message VARCHAR,
                user_id INTEGER,
                strategy_id INTEGER,
                strategy_snapshot JSON,
                strategy_version_id INTEGER,
                resolution VARCHAR(20) NOT NULL
            )
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_1 VARCHAR(50) NOT NULL,
                market_2 VARCHAR(50) NOT NULL,
                run_id_fk INTEGER NOT NULL,
                total_trades INTEGER,
                entry_trades INTEGER,
                exit_trades INTEGER,
                profitable_trades INTEGER,
                losing_trades INTEGER,
                pnl REAL,
                pnl_usd REAL,
                win_rate REAL,
                avg_win REAL,
                avg_loss REAL,
                profit_factor REAL,
                max_drawdown REAL,
                sharpe_ratio REAL,
                sortino_ratio REAL,
                calmar_ratio REAL,
                avg_trade_duration_hours REAL,
                avg_winning_trade_duration REAL,
                avg_losing_trade_duration REAL,
                cointegration_score REAL,
                correlation REAL,
                zscore_mean REAL,
                zscore_std REAL,
                created_at TIMESTAMP
            )
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS backtest_candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id_fk INTEGER NOT NULL,
                market VARCHAR(255) NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                resolution VARCHAR(20),
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                volume REAL NOT NULL,
                trades_count INTEGER,
                created_at TIMESTAMP
            )
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS backtest_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                description VARCHAR(500),
                category VARCHAR(50),
                user_id INTEGER NOT NULL,
                is_public INTEGER,
                is_default INTEGER,
                zscore_threshold REAL NOT NULL,
                stats_window INTEGER NOT NULL,
                max_half_life REAL NOT NULL
            )
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action VARCHAR(100) NOT NULL,
                resource_type VARCHAR(50) NOT NULL,
                resource_id VARCHAR(100),
                details JSON,
                status VARCHAR(20),
                ip_address VARCHAR(50),
                created_at TIMESTAMP
            )
        '''))


# Initialize tables on module import
with engine.begin() as conn:
    _create_sqlite_tables(conn)


def _row_to_dict(row) -> Dict[str, Any]:
    if row is None:
        return None
    # Prefer SQLAlchemy RowMapping
    try:
        mapping = getattr(row, "_mapping", None)
        if mapping is not None:
            return dict(mapping)
    except Exception:
        pass

    # If it's already a dict-like
    if isinstance(row, dict):
        return dict(row)

    # Try to iterate keys and index access
    try:
        keys = list(row.keys())
        out = {}
        for k in keys:
            try:
                out[k] = row[k]
            except Exception:
                try:
                    out[k] = getattr(row, k)
                except Exception:
                    out[k] = None
        return out
    except Exception:
        # Last resort: string representation
        return {"value": str(row)}


class Database:
    """Lightweight DB helper using SQLAlchemy Core.

    All methods are static to match test expectations.
    """

    # ------------------ Users ------------------
    @staticmethod
    def create_user(username: str, email: str, hashed_password: str, full_name: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.utcnow()
        query = text(
            """
            INSERT INTO users (username, email, hashed_password, full_name, is_active, is_admin, created_at, updated_at)
            VALUES (:username, :email, :hashed_password, :full_name, 1, 0, :created_at, :updated_at)
            RETURNING *
            """
        )
        params = dict(username=username, email=email, hashed_password=hashed_password, full_name=full_name, created_at=now, updated_at=now)
        with engine.begin() as conn:
            row = None
            try:
                result = conn.execute(query, params)
                row = result.fetchone()
            except Exception:
                row = None
            if not row:
                # Fallback for sqlite: insert then select last row
                ins = text(
                    "INSERT INTO users (username, email, hashed_password, full_name, is_active, is_admin, created_at, updated_at) VALUES (:username, :email, :hashed_password, :full_name, :is_active, :is_admin, :created_at, :updated_at)"
                )
                conn.execute(ins, {**params, "is_active": 1, "is_admin": 0})
                row = conn.execute(text("SELECT * FROM users WHERE username = :username"), {"username": username}).mappings().first()
            return _row_to_dict(row)

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        query = text("SELECT * FROM users WHERE id = :id")
        with engine.connect() as conn:
            result = conn.execute(query, {"id": user_id}).mappings().first()
            return _row_to_dict(result)

    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        query = text("SELECT * FROM users WHERE username = :username")
        with engine.connect() as conn:
            result = conn.execute(query, {"username": username}).mappings().first()
            return _row_to_dict(result)

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        query = text("SELECT * FROM users WHERE email = :email")
        with engine.connect() as conn:
            result = conn.execute(query, {"email": email}).mappings().first()
            return _row_to_dict(result)

    @staticmethod
    def update_user(user_id: int, **fields) -> Optional[Dict[str, Any]]:
        if not fields:
            return Database.get_user_by_id(user_id)
        set_clause = ", ".join([f"{k} = :{k}" for k in fields.keys()])
        params = dict(fields)
        params["id"] = user_id
        query = text(f"UPDATE users SET {set_clause}, updated_at = :updated_at WHERE id = :id RETURNING *")
        params["updated_at"] = datetime.utcnow()
        with engine.begin() as conn:
            try:
                result = conn.execute(query, params).fetchone()
            except Exception:
                # SQLite fallback: perform update then select
                upd = text(f"UPDATE users SET {set_clause}, updated_at = :updated_at WHERE id = :id")
                conn.execute(upd, params)
                result = conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id}).mappings().first()
            return _row_to_dict(result)

    @staticmethod
    def delete_user(user_id: int) -> bool:
        query = text("DELETE FROM users WHERE id = :id")
        with engine.begin() as conn:
            result = conn.execute(query, {"id": user_id})
            return result.rowcount > 0

    # ------------------ Backtest Runs ------------------
    @staticmethod
    def create_backtest_run(run_id: str, start_date: str, end_date: str, num_pairs: int, total_markets: int, user_id: Optional[int] = None, resolution: str = "1HOUR") -> Dict[str, Any]:
        now = datetime.utcnow()
        query = text(
            """
            INSERT INTO backtest_runs (run_id, status, created_at, start_date, end_date, num_pairs, total_markets, user_id, resolution)
            VALUES (:run_id, 'running', :created_at, :start_date, :end_date, :num_pairs, :total_markets, :user_id, :resolution)
            RETURNING *
            """
        )
        params = dict(run_id=run_id, created_at=now, start_date=start_date, end_date=end_date, num_pairs=num_pairs, total_markets=total_markets, user_id=user_id, resolution=resolution)
        with engine.begin() as conn:
            row = None
            try:
                result = conn.execute(query, params)
                row = result.fetchone()
            except Exception:
                row = None
            if not row:
                # sqlite fallback: insert then select
                ins = text("INSERT INTO backtest_runs (run_id, status, created_at, start_date, end_date, num_pairs, total_markets, user_id, resolution) VALUES (:run_id, :status, :created_at, :start_date, :end_date, :num_pairs, :total_markets, :user_id, :resolution)")
                conn.execute(ins, {**params, "status": "running"})
                row = conn.execute(text("SELECT * FROM backtest_runs WHERE run_id = :run_id"), {"run_id": run_id}).mappings().first()
            return _row_to_dict(row)

    @staticmethod
    def get_backtest_run_by_id(run_id: int) -> Optional[Dict[str, Any]]:
        query = text("SELECT * FROM backtest_runs WHERE id = :id")
        with engine.connect() as conn:
            result = conn.execute(query, {"id": run_id}).mappings().first()
            return _row_to_dict(result)

    @staticmethod
    def get_backtest_run_by_run_id(run_id_str: str) -> Optional[Dict[str, Any]]:
        query = text("SELECT * FROM backtest_runs WHERE run_id = :run_id")
        with engine.connect() as conn:
            result = conn.execute(query, {"run_id": run_id_str}).mappings().first()
            return _row_to_dict(result)

    @staticmethod
    def get_user_backtest_runs(user_id: int) -> List[Dict[str, Any]]:
        query = text("SELECT * FROM backtest_runs WHERE user_id = :user_id ORDER BY created_at DESC")
        with engine.connect() as conn:
            result = conn.execute(query, {"user_id": user_id}).mappings().all()
            return [dict(r) for r in result]

    @staticmethod
    def update_backtest_run(run_id: int, **fields) -> Optional[Dict[str, Any]]:
        if not fields:
            return Database.get_backtest_run_by_id(run_id)
        set_clause = ", ".join([f"{k} = :{k}" for k in fields.keys()])
        params = dict(fields)
        params["id"] = run_id
        query = text(f"UPDATE backtest_runs SET {set_clause} WHERE id = :id RETURNING *")
        with engine.begin() as conn:
            try:
                result = conn.execute(query, params).fetchone()
            except Exception:
                upd = text(f"UPDATE backtest_runs SET {set_clause} WHERE id = :id")
                conn.execute(upd, params)
                result = conn.execute(text("SELECT * FROM backtest_runs WHERE id = :id"), {"id": run_id}).mappings().first()
            return _row_to_dict(result)

    # ------------------ Backtest Results ------------------
    @staticmethod
    def create_backtest_result(run_id_fk: int, market_1: str, market_2: str, total_trades: Optional[int] = None, pnl: Optional[float] = None, win_rate: Optional[float] = None) -> Dict[str, Any]:
        now = datetime.utcnow()
        query = text(
            """
            INSERT INTO backtest_results (market_1, market_2, run_id_fk, total_trades, pnl, win_rate, created_at)
            VALUES (:market_1, :market_2, :run_id_fk, :total_trades, :pnl, :win_rate, :created_at)
            RETURNING *
            """
        )
        params = dict(market_1=market_1, market_2=market_2, run_id_fk=run_id_fk, total_trades=total_trades, pnl=pnl, win_rate=win_rate, created_at=now)
        with engine.begin() as conn:
            row = None
            try:
                result = conn.execute(query, params)
                row = result.fetchone()
            except Exception:
                row = None
            if not row:
                ins = text("INSERT INTO backtest_results (market_1, market_2, run_id_fk, total_trades, pnl, win_rate, created_at) VALUES (:market_1, :market_2, :run_id_fk, :total_trades, :pnl, :win_rate, :created_at)")
                conn.execute(ins, params)
                row = conn.execute(text("SELECT * FROM backtest_results WHERE run_id_fk = :run_id_fk"), {"run_id_fk": run_id_fk}).mappings().first()
            return _row_to_dict(row)

    @staticmethod
    def get_backtest_result_by_id(result_id: int) -> Optional[Dict[str, Any]]:
        query = text("SELECT * FROM backtest_results WHERE id = :id")
        with engine.connect() as conn:
            result = conn.execute(query, {"id": result_id}).mappings().first()
            return _row_to_dict(result)

    @staticmethod
    def get_run_results(run_id: int) -> List[Dict[str, Any]]:
        query = text("SELECT * FROM backtest_results WHERE run_id_fk = :run_id")
        with engine.connect() as conn:
            result = conn.execute(query, {"run_id": run_id}).mappings().all()
            return [dict(r) for r in result]

    # ------------------ Backtest Candles ------------------
    @staticmethod
    def create_backtest_candle(run_id_fk: int, market: str, timestamp, open_price: float, high_price: float, low_price: float, close_price: float, volume: float, resolution: Optional[str] = None, trades_count: Optional[int] = None) -> Dict[str, Any]:
        now = datetime.utcnow()
        query = text(
            """
            INSERT INTO backtest_candles (run_id_fk, market, timestamp, resolution, open_price, high_price, low_price, close_price, volume, trades_count, created_at)
            VALUES (:run_id_fk, :market, :timestamp, :resolution, :open_price, :high_price, :low_price, :close_price, :volume, :trades_count, :created_at)
            RETURNING *
            """
        )
        params = dict(run_id_fk=run_id_fk, market=market, timestamp=timestamp, resolution=resolution, open_price=open_price, high_price=high_price, low_price=low_price, close_price=close_price, volume=volume, trades_count=trades_count, created_at=now)
        with engine.begin() as conn:
            row = None
            try:
                result = conn.execute(query, params)
                row = result.fetchone()
            except Exception:
                row = None
            if not row:
                ins = text(
                    "INSERT INTO backtest_candles (run_id_fk, market, timestamp, resolution, open_price, high_price, low_price, close_price, volume, trades_count, created_at) VALUES (:run_id_fk, :market, :timestamp, :resolution, :open_price, :high_price, :low_price, :close_price, :volume, :trades_count, :created_at)"
                )
                conn.execute(ins, params)
                row = conn.execute(text("SELECT * FROM backtest_candles WHERE run_id_fk = :run_id_fk"), {"run_id_fk": run_id_fk}).mappings().first()
            return _row_to_dict(row)

    @staticmethod
    def get_candles_by_run_id(run_id: int) -> List[Dict[str, Any]]:
        query = text("SELECT * FROM backtest_candles WHERE run_id_fk = :run_id ORDER BY timestamp")
        with engine.connect() as conn:
            result = conn.execute(query, {"run_id": run_id}).mappings().all()
            return [dict(r) for r in result]

    @staticmethod
    def get_markets_by_run_id(run_id: int) -> List[str]:
        query = text("SELECT DISTINCT market FROM backtest_candles WHERE run_id_fk = :run_id")
        with engine.connect() as conn:
            result = conn.execute(query, {"run_id": run_id}).scalars().all()
            # If scalars() doesn't behave as expected, fall back to mappings
            if not result:
                result = conn.execute(text("SELECT DISTINCT market FROM backtest_candles WHERE run_id_fk = :run_id"), {"run_id": run_id}).mappings().all()
                return [r["market"] for r in result]
            return list(result)

    # ------------------ Strategies ------------------
    @staticmethod
    def create_strategy(name: str, user_id: int, zscore_threshold: float = 1.5, category: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.utcnow()
        query = text(
            """
            INSERT INTO backtest_strategies (name, description, category, user_id, zscore_threshold, stats_window, max_half_life, usd_per_trade, usd_min_collateral, close_at_zscore_cross, transaction_fee, slippage, starting_balance, candle_resolution, max_history_days, risk_free_rate, created_at, updated_at)
            VALUES (:name, null, :category, :user_id, :zscore_threshold, 21, 24.0, 10.0, 100.0, true, 0.0005, 0.001, 1000.0, '1HOUR', 90, 0.02, :created_at, :updated_at)
            RETURNING *
            """
        )
        params = dict(name=name, category=category, user_id=user_id, zscore_threshold=zscore_threshold, created_at=now, updated_at=now)
        with engine.begin() as conn:
            row = None
            try:
                result = conn.execute(query, params)
                row = result.fetchone()
            except Exception:
                row = None
            if not row:
                ins = text("INSERT INTO backtest_strategies (name, description, category, user_id, zscore_threshold, stats_window, max_half_life, usd_per_trade, usd_min_collateral, close_at_zscore_cross, transaction_fee, slippage, starting_balance, candle_resolution, max_history_days, risk_free_rate, created_at, updated_at) VALUES (:name, null, :category, :user_id, :zscore_threshold, 21, 24.0, 10.0, 100.0, 1, 0.0005, 0.001, 1000.0, '1HOUR', 90, 0.02, :created_at, :updated_at)")
                conn.execute(ins, params)
                row = conn.execute(text("SELECT * FROM backtest_strategies WHERE name = :name"), {"name": name}).mappings().first()
            return _row_to_dict(row)

    @staticmethod
    def get_strategy_by_id(strategy_id: int) -> Optional[Dict[str, Any]]:
        query = text("SELECT * FROM backtest_strategies WHERE id = :id")
        with engine.connect() as conn:
            result = conn.execute(query, {"id": strategy_id}).mappings().first()
            return _row_to_dict(result)

    @staticmethod
    def get_user_strategies(user_id: int) -> List[Dict[str, Any]]:
        query = text("SELECT * FROM backtest_strategies WHERE user_id = :user_id")
        with engine.connect() as conn:
            result = conn.execute(query, {"user_id": user_id}).mappings().all()
            return [dict(r) for r in result]

    @staticmethod
    def update_strategy(strategy_id: int, **fields) -> Optional[Dict[str, Any]]:
        if not fields:
            return Database.get_strategy_by_id(strategy_id)
        set_clause = ", ".join([f"{k} = :{k}" for k in fields.keys()])
        params = dict(fields)
        params["id"] = strategy_id
        query = text(f"UPDATE backtest_strategies SET {set_clause} WHERE id = :id RETURNING *")
        with engine.begin() as conn:
            try:
                result = conn.execute(query, params).fetchone()
            except Exception:
                upd = text(f"UPDATE backtest_strategies SET {set_clause} WHERE id = :id")
                conn.execute(upd, params)
                result = conn.execute(text("SELECT * FROM backtest_strategies WHERE id = :id"), {"id": strategy_id}).mappings().first()
            return _row_to_dict(result)

    # ------------------ Audit Logs ------------------
    @staticmethod
    def create_audit_log(action: str, resource_type: str, user_id: Optional[int] = None, resource_id: Optional[str] = None, details: Optional[dict] = None, status: Optional[str] = None, ip_address: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.utcnow()
        query = text(
            """
            INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, status, ip_address, created_at)
            VALUES (:user_id, :action, :resource_type, :resource_id, :details, :status, :ip_address, :created_at)
            RETURNING *
            """
        )
        params = dict(user_id=user_id, action=action, resource_type=resource_type, resource_id=resource_id, details=details, status=status, ip_address=ip_address, created_at=now)
        with engine.begin() as conn:
            try:
                result = conn.execute(query, params).fetchone()
            except Exception:
                ins = text("INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, status, ip_address, created_at) VALUES (:user_id, :action, :resource_type, :resource_id, :details, :status, :ip_address, :created_at)")
                conn.execute(ins, params)
                result = conn.execute(text("SELECT * FROM audit_logs WHERE action = :action AND user_id = :user_id"), {"action": action, "user_id": user_id}).mappings().first()
            return _row_to_dict(result)

    @staticmethod
    def get_audit_log_by_id(log_id: int) -> Optional[Dict[str, Any]]:
        query = text("SELECT * FROM audit_logs WHERE id = :id")
        with engine.connect() as conn:
            result = conn.execute(query, {"id": log_id}).mappings().first()
            return _row_to_dict(result)

    @staticmethod
    def get_user_audit_logs(user_id: int) -> List[Dict[str, Any]]:
        query = text("SELECT * FROM audit_logs WHERE user_id = :user_id ORDER BY created_at DESC")
        with engine.connect() as conn:
            result = conn.execute(query, {"user_id": user_id}).mappings().all()
            return [dict(r) for r in result]


# Expose engine helpers
get_engine = lambda: engine