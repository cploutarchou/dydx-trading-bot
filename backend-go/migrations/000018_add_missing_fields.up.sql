-- Migration 000018: Add missing fields to backtest_results table
-- NOTE: backtest_positions columns already exist in migration 000014

-- Add updated_at column to backtest_results if it doesn't exist
ALTER TABLE backtest_results ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;
CREATE INDEX idx_backtest_results_updated_at ON backtest_results(updated_at);


