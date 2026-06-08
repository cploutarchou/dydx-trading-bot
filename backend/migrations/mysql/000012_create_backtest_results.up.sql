-- Create backtest_results table
CREATE TABLE IF NOT EXISTS backtest_results
(
  id                         INT AUTO_INCREMENT PRIMARY KEY,
  market_1                   VARCHAR(50) NOT NULL,
  market_2                   VARCHAR(50) NOT NULL,
  run_id_fk                  INTEGER     NOT NULL,
  total_trades               INTEGER  DEFAULT NULL,
  entry_trades               INTEGER  DEFAULT NULL,
  exit_trades                INTEGER  DEFAULT NULL,
  profitable_trades          INTEGER  DEFAULT NULL,
  losing_trades              INTEGER  DEFAULT NULL,
  pnl                        FLOAT     DEFAULT NULL,
  pnl_usd                    FLOAT     DEFAULT NULL,
  win_rate                   FLOAT     DEFAULT NULL,
  avg_win                    FLOAT     DEFAULT NULL,
  avg_loss                   FLOAT     DEFAULT NULL,
  profit_factor              FLOAT     DEFAULT NULL,
  max_drawdown               FLOAT     DEFAULT NULL,
  sharpe_ratio               FLOAT     DEFAULT NULL,
  sortino_ratio              FLOAT     DEFAULT NULL,
  calmar_ratio               FLOAT     DEFAULT NULL,
  avg_trade_duration_hours   FLOAT     DEFAULT NULL,
  avg_winning_trade_duration FLOAT     DEFAULT NULL,
  avg_losing_trade_duration  FLOAT     DEFAULT NULL,
  cointegration_score        FLOAT     DEFAULT NULL,
  correlation                FLOAT     DEFAULT NULL,
  zscore_mean                FLOAT     DEFAULT NULL,
  zscore_std                 FLOAT     DEFAULT NULL,
  created_at                 TIMESTAMP DEFAULT NULL,
  KEY idx_fk_run_id_fk (run_id_fk)
);

CREATE INDEX idx_result_pair ON backtest_results (market_1, market_2);
CREATE INDEX idx_result_run_profit ON backtest_results (run_id_fk, pnl);
CREATE INDEX ix_backtest_results_created_at ON backtest_results (created_at);
CREATE INDEX ix_backtest_results_id ON backtest_results (id);
CREATE INDEX ix_backtest_results_market_1 ON backtest_results (market_1);
CREATE INDEX ix_backtest_results_market_2 ON backtest_results (market_2);
CREATE INDEX ix_backtest_results_run_id_fk ON backtest_results (run_id_fk);

