-- Create backtest_results table
CREATE TABLE IF NOT EXISTS backtest_results
(
  id                         INTEGER PRIMARY KEY AUTOINCREMENT,
  market_1                   VARCHAR(50) NOT NULL,
  market_2                   VARCHAR(50) NOT NULL,
  run_id_fk                  INTEGER     NOT NULL,
  total_trades               INTEGER  DEFAULT NULL,
  entry_trades               INTEGER  DEFAULT NULL,
  exit_trades                INTEGER  DEFAULT NULL,
  profitable_trades          INTEGER  DEFAULT NULL,
  losing_trades              INTEGER  DEFAULT NULL,
  pnl                        REAL     DEFAULT NULL,
  pnl_usd                    REAL     DEFAULT NULL,
  win_rate                   REAL     DEFAULT NULL,
  avg_win                    REAL     DEFAULT NULL,
  avg_loss                   REAL     DEFAULT NULL,
  profit_factor              REAL     DEFAULT NULL,
  max_drawdown               REAL     DEFAULT NULL,
  sharpe_ratio               REAL     DEFAULT NULL,
  sortino_ratio              REAL     DEFAULT NULL,
  calmar_ratio               REAL     DEFAULT NULL,
  avg_trade_duration_hours   REAL     DEFAULT NULL,
  avg_winning_trade_duration REAL     DEFAULT NULL,
  avg_losing_trade_duration  REAL     DEFAULT NULL,
  cointegration_score        REAL     DEFAULT NULL,
  correlation                REAL     DEFAULT NULL,
  zscore_mean                REAL     DEFAULT NULL,
  zscore_std                 REAL     DEFAULT NULL,
  created_at                 DATETIME DEFAULT NULL,
  FOREIGN KEY (run_id_fk) REFERENCES backtest_runs (id)
);

CREATE INDEX idx_result_pair ON backtest_results (market_1, market_2);
CREATE INDEX idx_result_run_profit ON backtest_results (run_id_fk, pnl);
CREATE INDEX ix_backtest_results_created_at ON backtest_results (created_at);
CREATE INDEX ix_backtest_results_id ON backtest_results (id);
CREATE INDEX ix_backtest_results_market_1 ON backtest_results (market_1);
CREATE INDEX ix_backtest_results_market_2 ON backtest_results (market_2);
CREATE INDEX ix_backtest_results_run_id_fk ON backtest_results (run_id_fk);

