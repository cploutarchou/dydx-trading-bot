import logging
import time
from typing import Tuple, cast

import numpy as np
import pandas as pd
from constants import MAX_HALF_LIFE, WINDOW
from func_messaging import TelegramMessenger

logger = logging.getLogger(__name__)


class SmartError(Exception):
    pass


def half_life_mean_reversion(series):
    if len(series) <= 1:
        raise SmartError("Series length must be greater than 1.")
    # Import locally to avoid pulling heavy dependencies at module import time
    from scipy.stats import linregress

    # Ensure we operate on a numpy float64 array (helps typing and numeric stability)
    series = np.asarray(series, dtype=np.float64)
    difference = np.diff(series)
    lagged_series = series[:-1]

    # Ensure both arrays are 1D
    lagged_series = np.asarray(lagged_series).flatten()
    difference = np.asarray(difference).flatten()

    # linregress returns (slope, intercept, rvalue, pvalue, stderr) for backward compatibility
    # Guard against degenerate regression inputs before calling linregress
    if np.nanstd(lagged_series) < np.finfo(np.float64).eps:
        raise SmartError(
            "Cannot calculate half life. Lagged series variance is too small for regression."
        )
    if np.nanstd(difference) < np.finfo(np.float64).eps:
        raise SmartError(
            "Cannot calculate half life. Difference series variance is too small for regression."
        )

    result_tuple = linregress(lagged_series, difference)
    slope_val, _, _, _, _ = cast(Tuple[float, float, float, float, float], result_tuple)
    slope: float = float(slope_val)

    # Guard against near-zero slope
    if abs(slope) < np.finfo(np.float64).eps:
        raise SmartError(
            "Cannot calculate half life. Slope value is too close to zero."
        )

    half_life = -np.log(2) / slope
    return float(half_life)


# Calculate ZScore
def calculate_zscore(spread):
    spread_series = pd.Series(spread)
    mean = spread_series.rolling(center=False, window=WINDOW).mean()
    std = spread_series.rolling(center=False, window=WINDOW).std()
    x = spread_series.rolling(center=False, window=1).mean()
    zscore = (x - mean) / std
    return zscore


# Calculate Cointegration
def calculate_cointegration(series_1, series_2):
    # Local imports to avoid heavy startup time when main merely loads modules
    import statsmodels.api as sm
    from statsmodels.tsa.stattools import coint

    series_1 = np.array(series_1).astype(np.float64)
    series_2 = np.array(series_2).astype(np.float64)
    coint_flag = 0
    # Basic guards: skip if either series has (near-)zero variance or contains NaNs
    if np.isnan(series_1).any() or np.isnan(series_2).any():
        raise SmartError("Series contains NaN values")
    if (
        np.nanstd(series_1) < np.finfo(np.float64).eps
        or np.nanstd(series_2) < np.finfo(np.float64).eps
    ):
        raise SmartError("Series variance is too small for reliable cointegration test")
    # Quick check for nearly identical series which make the test ill-conditioned
    if np.allclose(series_1, series_2, rtol=1e-6, atol=1e-8):
        raise SmartError(
            "Series are nearly identical; cointegration test is unreliable"
        )
    # Check for spread with too little movement prior to regression/half-life
    if np.nanstd(series_1 - series_2) < np.finfo(np.float64).eps:
        raise SmartError(
            "Series spread variance is too small for reliable cointegration test"
        )
    coint_res = coint(series_1, series_2)
    coint_t = coint_res[0]
    p_value = coint_res[1]
    critical_value = coint_res[2][1]

    # Better way to fit data vs older version
    series_2_with_constant = sm.add_constant(series_2)
    model = sm.OLS(series_1, series_2_with_constant).fit()
    hedge_ratio = model.params[1]
    intercept = model.params[0]

    spread = series_1 - (series_2 * hedge_ratio) - intercept
    half_life = half_life_mean_reversion(spread)
    t_check = coint_t < critical_value
    coint_flag = 1 if p_value < 0.05 and t_check else 0
    return coint_flag, hedge_ratio, half_life


# Store Cointegration Results
def store_cointegration_results(df_market_prices):

    # Initialize
    start_time = time.time()
    messenger = TelegramMessenger()
    markets = df_market_prices.columns.to_list()
    criteria_met_pairs = []

    # Find cointegrated pairs
    # Start with our base pair
    # Minimum return std (percent change) to consider a market tradeable for cointegration
    MIN_RETURN_STD = 1e-4
    for index, base_market in enumerate(markets[:-1]):
        series_1 = df_market_prices[base_market].values.astype(np.float64).tolist()

        # Quick filter: skip base markets with almost-zero return volatility
        try:
            import pandas as _pd

            returns_1 = _pd.Series(series_1).pct_change().dropna()
            if returns_1.empty or returns_1.std() < MIN_RETURN_STD:
                # Too little movement in base market — skip all pairs with this base
                # This avoids a flood of 'Series variance is too small' messages
                # and speeds up the scan.
                # Print once per base market for visibility.
                logger.debug(
                    "Skipping market %s: return volatility below threshold", base_market
                )
                continue
        except Exception:
            # If any error computing returns, skip this market
            logger.warning("Skipping market %s: error computing returns", base_market)
            continue

        # Get Quote Pair
        for quote_market in markets[index + 1 :]:
            series_2 = df_market_prices[quote_market].values.astype(np.float64).tolist()

            # Quick filter: skip quote markets with near-zero return volatility
            try:
                returns_2 = _pd.Series(series_2).pct_change().dropna()
                if returns_2.empty or returns_2.std() < MIN_RETURN_STD:
                    # Skip this pair silently to avoid noise
                    continue
            except Exception:
                continue

            # Check cointegration (guard errors per-pair so one bad pair doesn't abort the whole run)
            try:
                coint_flag, hedge_ratio, half_life = calculate_cointegration(
                    series_1, series_2
                )
            except SmartError as e:
                # Skip problematic pairs (constant series, NaNs, near-zero variance, etc.)
                logger.debug("Skipping pair %s / %s: %s", base_market, quote_market, e)
                continue
            except Exception:
                # Catch-all: skip pair but log for debugging
                logger.exception(
                    "Error testing pair %s / %s", base_market, quote_market
                )
                continue

            # Log pair
            if coint_flag == 1 and half_life <= MAX_HALF_LIFE and half_life > 0:
                criteria_met_pairs.append(
                    {
                        "base_market": base_market,
                        "quote_market": quote_market,
                        "hedge_ratio": hedge_ratio,
                        "half_life": half_life,
                    }
                )

    # Create and save DataFrame
    df_criteria_met = pd.DataFrame(criteria_met_pairs)
    df_criteria_met.to_csv("cointegrated_pairs.csv")
    
    # Calculate analysis time and send notification
    analysis_time = time.time() - start_time
    pairs_found = len(criteria_met_pairs)
    messenger.send_cointegration_results(pairs_found, analysis_time)
    
    del df_criteria_met

    # Return result
    logger.info("Cointegrated pairs successfully saved")
    return "saved"
