-- Migration 000020 Down: Drop cointegration_results table

DROP INDEX IF EXISTS idx_cointegration_results_base_market;
DROP INDEX IF EXISTS idx_cointegration_results_quote_market;
DROP INDEX IF EXISTS idx_cointegration_results_confidence_score;
DROP INDEX IF EXISTS idx_cointegration_results_half_life;
DROP INDEX IF EXISTS idx_cointegration_results_created_at;

DROP TABLE IF EXISTS cointegration_results;

