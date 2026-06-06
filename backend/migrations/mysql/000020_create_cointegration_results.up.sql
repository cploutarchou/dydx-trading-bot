-- Migration 000020: Create cointegration_results table for pair storage

CREATE TABLE IF NOT EXISTS cointegration_results
(
  id                 INT AUTO_INCREMENT PRIMARY KEY,
  base_market        VARCHAR(50) NOT NULL,
  quote_market       VARCHAR(50) NOT NULL,
  hedge_ratio        FLOAT        NOT NULL,
  half_life          FLOAT        NOT NULL,
  zero_crossings     INTEGER      DEFAULT 0,
  p_value            FLOAT         DEFAULT NULL,
  z_score_mean       FLOAT         DEFAULT 0.0,
  z_score_std        FLOAT         DEFAULT 1.0,
  analysis_timestamp VARCHAR(255) DEFAULT NULL,
  confidence_score   FLOAT         DEFAULT 0.5,
  created_at         TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  updated_at         TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (base_market, quote_market)
);

-- Create indexes for performance
CREATE INDEX idx_cointegration_results_base_market ON cointegration_results (base_market);
CREATE INDEX idx_cointegration_results_quote_market ON cointegration_results (quote_market);
CREATE INDEX idx_cointegration_results_confidence_score ON cointegration_results (confidence_score);
CREATE INDEX idx_cointegration_results_half_life ON cointegration_results (half_life);
CREATE INDEX idx_cointegration_results_created_at ON cointegration_results (created_at);

