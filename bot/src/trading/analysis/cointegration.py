"""Cointegration analysis module for pairs trading strategy."""

import time
from datetime import datetime, timezone
from typing import Any, Tuple, cast

import numpy as np
import pandas as pd
from loguru import logger

from src.constants import MAX_HALF_LIFE, WINDOW
from src.infrastructure.domain.cointegration_storage import (
    CointegrationResult,
    calculate_confidence_score,
    pair_storage,
)
from src.shared.dataframe_utils import (
    cleanup_dataframe,
    optimize_dataframe_memory,
    register_dataframe,
    unregister_dataframe,
)
from src.shared.notifications import TelegramMessenger


class SmartError(Exception):
    """Custom exception for statistical analysis errors."""

    pass


def half_life_mean_reversion(series: Any) -> float:
    """Calculate half-life of mean reversion for a time series."""
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


def calculate_zscore(spread: Any) -> pd.Series:
    """Calculate Z-score of a spread series."""
    spread_series = pd.Series(spread)
    mean = spread_series.rolling(center=False, window=WINDOW).mean()
    std = spread_series.rolling(center=False, window=WINDOW).std()
    x = spread_series.rolling(center=False, window=1).mean()
    zscore = (x - mean) / std
    return zscore


def calculate_cointegration(
    series_1: Any, series_2: Any
) -> Tuple[int, float, float, float, float]:
    """
    Test cointegration between two price series.

    Returns:
        Tuple of (coint_flag, hedge_ratio, half_life, intercept, p_value)
        where intercept is the OLS constant of series_1 ~ const + hedge_ratio * series_2.
    """
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
    return coint_flag, hedge_ratio, half_life, intercept, p_value


def count_zero_crossings(series: Any) -> int:
    """Count zero crossings in a time series."""
    if len(series) < 2:
        return 0

    # Remove NaN values
    clean_series = series.dropna()
    if len(clean_series) < 2:
        return 0

    # Count sign changes (zero crossings)
    signs = np.sign(clean_series)
    sign_changes = np.diff(signs)
    return int(np.sum(np.abs(sign_changes) == 2))


def store_cointegration_results(df_market_prices: pd.DataFrame) -> dict[str, Any]:
    """
    Find and store cointegrated pairs from market price data.

    Args:
        df_market_prices: DataFrame with market prices by column

    Returns:
        Result of saving pairs to storage
    """
    # Initialize with DataFrame tracking
    start_time = time.time()
    messenger = TelegramMessenger()

    # Register DataFrame for memory tracking
    df_id = register_dataframe(
        df_market_prices,
        "cointegration_analysis",
        {
            "markets_count": len(df_market_prices.columns),
            "analysis_type": "cointegration",
        },
    )

    try:
        markets = df_market_prices.columns.to_list()
        criteria_met_pairs = []

        # Find cointegrated pairs
        # Minimum return std (percent change) to consider a market tradeable for cointegration
        MIN_RETURN_STD = 1e-4
        for index, base_market in enumerate(markets[:-1]):
            series_1 = df_market_prices[base_market].values.astype(np.float64).tolist()

            # Quick filter: skip base markets with almost-zero return volatility
            try:
                import pandas as _pd

                returns_1 = _pd.Series(series_1).pct_change().dropna()
                if returns_1.empty or returns_1.std() < MIN_RETURN_STD:
                    logger.debug(
                        "Skipping market {}: return volatility below threshold",
                        base_market,
                    )
                    continue
            except Exception:
                logger.warning(
                    "Skipping market {}: error computing returns", base_market
                )
                continue

            # Get Quote Pair
            for quote_market in markets[index + 1 :]:
                series_2 = (
                    df_market_prices[quote_market].values.astype(np.float64).tolist()
                )

                # Quick filter: skip quote markets with near-zero return volatility
                try:
                    returns_2 = _pd.Series(series_2).pct_change().dropna()
                    if returns_2.empty or returns_2.std() < MIN_RETURN_STD:
                        continue
                except Exception:
                    continue

                # Check cointegration
                try:
                    (
                        coint_flag,
                        hedge_ratio,
                        half_life,
                        intercept,
                        p_value,
                    ) = calculate_cointegration(series_1, series_2)
                except SmartError as e:
                    logger.debug(
                        "Skipping pair {} / {}: {}", base_market, quote_market, e
                    )
                    continue
                except Exception:
                    logger.exception(
                        "Error testing pair {} / {}", base_market, quote_market
                    )
                    continue

                # Log pair and calculate enhanced metrics
                if coint_flag == 1 and half_life <= MAX_HALF_LIFE and half_life > 0:
                    try:
                        # Create spread for Z-score analysis with cleanup
                        spread_series = None
                        z_scores_series = None

                        spread_series = (
                            pd.Series(series_1)
                            - hedge_ratio * pd.Series(series_2)
                            - intercept
                        )
                        z_scores_series = calculate_zscore(spread_series)

                        # Calculate zero crossings
                        zero_crossings = count_zero_crossings(z_scores_series)

                        # Calculate confidence score
                        confidence = calculate_confidence_score(
                            p_value=p_value,
                            half_life=half_life,
                            zero_crossings=zero_crossings,
                        )

                        # Create enhanced result
                        cointegration_result = CointegrationResult(
                            base_market=base_market,
                            quote_market=quote_market,
                            hedge_ratio=hedge_ratio,
                            half_life=half_life,
                            zero_crossings=zero_crossings,
                            p_value=float(p_value),
                            z_score_mean=float(z_scores_series.mean()),
                            z_score_std=float(z_scores_series.std()),
                            analysis_timestamp=datetime.now(timezone.utc).isoformat(),
                            confidence_score=confidence,
                            intercept=float(intercept),
                        )

                        criteria_met_pairs.append(cointegration_result)

                        # Cleanup intermediate series
                        cleanup_dataframe(spread_series)
                        cleanup_dataframe(z_scores_series)

                    except Exception as e:
                        # If enhanced metrics fail, create basic result
                        logger.warning(
                            f"Enhanced metrics failed for {base_market}/{quote_market}: {e}"
                        )
                        basic_result = CointegrationResult(
                            base_market=base_market,
                            quote_market=quote_market,
                            hedge_ratio=hedge_ratio,
                            half_life=half_life,
                            zero_crossings=0,
                            p_value=float(p_value),
                            z_score_mean=0.0,
                            z_score_std=1.0,
                            analysis_timestamp=datetime.now(timezone.utc).isoformat(),
                            confidence_score=0.5,
                            intercept=float(intercept),
                        )
                        criteria_met_pairs.append(basic_result)

        # Save using enhanced storage system
        result = pair_storage.save_pairs(criteria_met_pairs)

        # Calculate analysis time and send enhanced notification
        analysis_time = time.time() - start_time
        pairs_found = len(criteria_met_pairs)
        high_confidence_pairs = len(
            [p for p in criteria_met_pairs if p.is_high_confidence]
        )

        messenger.send_cointegration_results(
            pairs_found, analysis_time, high_confidence_pairs
        )

        # Log enhanced results
        logger.info(
            f"Cointegrated pairs analysis complete: {pairs_found} total pairs, "
            f"{high_confidence_pairs} high-confidence pairs, {analysis_time:.1f}s"
        )

        return result

    finally:
        # Cleanup DataFrame tracking
        if df_id:
            unregister_dataframe(df_id)
        # Optimize and cleanup the input DataFrame
        if df_market_prices is not None:
            optimize_dataframe_memory(df_market_prices)
