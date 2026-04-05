UPDATE backtest_strategies
SET runtime_strategy = 'cointegration'
WHERE runtime_strategy IS NULL OR runtime_strategy = '';
