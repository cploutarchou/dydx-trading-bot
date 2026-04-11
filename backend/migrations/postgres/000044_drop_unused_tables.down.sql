-- Migration 000043 Down: Recreate tables dropped in 000043_drop_unused_tables.up.sql
-- Run this to restore the tables if a rollback is needed.

-- Restore dydx_key_settings (originally from 000006)
CREATE TABLE IF NOT EXISTS dydx_key_settings (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER     NOT NULL UNIQUE,
    default_network     VARCHAR(50) NOT NULL,
    auto_switch_testnet BOOLEAN     NOT NULL,
    created_at          TIMESTAMP   NOT NULL,
    updated_at          TIMESTAMP   NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE INDEX IF NOT EXISTS ix_dydx_key_settings_id ON dydx_key_settings (id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_dydx_key_settings_user_id ON dydx_key_settings (user_id);

-- Restore cointegration_results (originally from 000020)
CREATE TABLE IF NOT EXISTS cointegration_results (
    id                 SERIAL PRIMARY KEY,
    base_market        VARCHAR(50) NOT NULL,
    quote_market       VARCHAR(50) NOT NULL,
    hedge_ratio        REAL        NOT NULL,
    half_life          REAL        NOT NULL,
    zero_crossings     INTEGER      DEFAULT 0,
    p_value            REAL         DEFAULT NULL,
    z_score_mean       REAL         DEFAULT 0.0,
    z_score_std        REAL         DEFAULT 1.0,
    analysis_timestamp VARCHAR(255) DEFAULT NULL,
    confidence_score   REAL         DEFAULT 0.5,
    created_at         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (base_market, quote_market)
);
CREATE INDEX IF NOT EXISTS idx_cointegration_results_base_market ON cointegration_results (base_market);
CREATE INDEX IF NOT EXISTS idx_cointegration_results_quote_market ON cointegration_results (quote_market);
CREATE INDEX IF NOT EXISTS idx_cointegration_results_confidence_score ON cointegration_results (confidence_score);
CREATE INDEX IF NOT EXISTS idx_cointegration_results_half_life ON cointegration_results (half_life);
CREATE INDEX IF NOT EXISTS idx_cointegration_results_created_at ON cointegration_results (created_at);

-- Restore backtest_metrics (originally from 000019)
CREATE TABLE IF NOT EXISTS backtest_metrics (
    id                       SERIAL PRIMARY KEY,
    run_id                   INTEGER NOT NULL UNIQUE,
    total_pnl                REAL    NOT NULL,
    total_return_pct         REAL    NOT NULL,
    total_trades             INTEGER NOT NULL,
    winning_trades           INTEGER NOT NULL,
    losing_trades            INTEGER NOT NULL,
    win_rate                 REAL    NOT NULL,
    avg_win                  REAL    NOT NULL,
    avg_loss                 REAL    NOT NULL,
    profit_factor            REAL    NOT NULL,
    max_drawdown             REAL    NOT NULL,
    max_drawdown_pct         REAL    NOT NULL,
    sharpe_ratio             REAL    NOT NULL,
    calmar_ratio             REAL    NOT NULL,
    max_consecutive_losses   INTEGER NOT NULL,
    avg_trade_duration_hours REAL    NOT NULL,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES backtest_runs (id)
);
CREATE INDEX IF NOT EXISTS idx_backtest_metrics_run_id ON backtest_metrics (run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_metrics_created_at ON backtest_metrics (created_at);
CREATE INDEX IF NOT EXISTS idx_backtest_metrics_total_pnl ON backtest_metrics (total_pnl);
CREATE INDEX IF NOT EXISTS idx_backtest_metrics_sharpe_ratio ON backtest_metrics (sharpe_ratio);

-- Restore backtest_comparisons (originally from 000016)
CREATE TABLE IF NOT EXISTS backtest_comparisons (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    description         VARCHAR(500) DEFAULT NULL,
    user_id             INTEGER      NOT NULL,
    strategy_id_1       INTEGER      NOT NULL,
    strategy_id_2       INTEGER      NOT NULL,
    run_id_1            INTEGER      NOT NULL,
    run_id_2            INTEGER      NOT NULL,
    winner_run_id       INTEGER      DEFAULT NULL,
    pnl_difference      REAL         DEFAULT NULL,
    sharpe_difference   REAL         DEFAULT NULL,
    win_rate_difference REAL         DEFAULT NULL,
    drawdown_difference REAL         DEFAULT NULL,
    comparison_metrics  JSON         DEFAULT NULL,
    created_at          TIMESTAMP    DEFAULT NULL,
    updated_at          TIMESTAMP    DEFAULT NULL,
    FOREIGN KEY (run_id_1) REFERENCES backtest_runs (id),
    FOREIGN KEY (run_id_2) REFERENCES backtest_runs (id),
    FOREIGN KEY (strategy_id_1) REFERENCES backtest_strategies (id),
    FOREIGN KEY (strategy_id_2) REFERENCES backtest_strategies (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
CREATE INDEX IF NOT EXISTS idx_comparison_runs ON backtest_comparisons (run_id_1, run_id_2);
CREATE INDEX IF NOT EXISTS idx_comparison_strategies ON backtest_comparisons (strategy_id_1, strategy_id_2);
CREATE INDEX IF NOT EXISTS idx_comparison_user_created ON backtest_comparisons (user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_backtest_comparisons_created_at ON backtest_comparisons (created_at);
CREATE INDEX IF NOT EXISTS ix_backtest_comparisons_id ON backtest_comparisons (id);
CREATE INDEX IF NOT EXISTS ix_backtest_comparisons_name ON backtest_comparisons (name);
CREATE INDEX IF NOT EXISTS ix_backtest_comparisons_user_id ON backtest_comparisons (user_id);

-- Restore bot_alerts (originally from 000025)
CREATE TABLE IF NOT EXISTS bot_alerts (
    id              SERIAL PRIMARY KEY,
    bot_instance_id INTEGER NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
    alert_type      TEXT    NOT NULL,
    severity        TEXT    NOT NULL DEFAULT 'info',
    title           TEXT    NOT NULL,
    message         TEXT    NOT NULL,
    details         TEXT,
    is_read         INTEGER NOT NULL DEFAULT 0,
    acknowledged_at TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_bot_alerts_bot_instance_id ON bot_alerts (bot_instance_id);
CREATE INDEX IF NOT EXISTS idx_bot_alerts_is_read ON bot_alerts (is_read);
CREATE INDEX IF NOT EXISTS idx_bot_alerts_created_at ON bot_alerts (created_at DESC);

