from datetime import datetime, timedelta, timezone

from src.infrastructure.domain.cointegration_storage import CointegrationResult
from src.trading.pair_priority import is_pair_analysis_stale, prioritize_pairs, score_pair


def _pair(base: str, quote: str, *, confidence: float, z_std: float, ts: str):
    return CointegrationResult(
        base_market=base,
        quote_market=quote,
        hedge_ratio=1.0,
        half_life=6.0,
        zero_crossings=8,
        p_value=0.01,
        z_score_mean=0.0,
        z_score_std=z_std,
        analysis_timestamp=ts,
        confidence_score=confidence,
    )


def test_pair_priority_scores_internal_cointegration_data(monkeypatch):
    monkeypatch.setenv("PAIR_PRIORITY_STALE_SECONDS", "86400")
    now = datetime.now(timezone.utc)
    strong = _pair(
        "ETH-USD",
        "BTC-USD",
        confidence=0.9,
        z_std=1.1,
        ts=now.isoformat(),
    )
    weak = _pair(
        "DOGE-USD",
        "XRP-USD",
        confidence=0.2,
        z_std=0.2,
        ts=now.isoformat(),
    )

    ranked, scores = prioritize_pairs([weak, strong])

    assert ranked[0].base_market == "ETH-USD"
    assert scores[0].pair == "ETH-USD/BTC-USD"
    assert scores[0].components["historical_opportunity_score"] > scores[1].components[
        "historical_opportunity_score"
    ]


def test_pair_priority_marks_stale_analysis(monkeypatch):
    monkeypatch.setenv("PAIR_PRIORITY_STALE_SECONDS", "60")
    now = datetime.now(timezone.utc)
    stale = _pair(
        "SOL-USD",
        "AVAX-USD",
        confidence=0.9,
        z_std=1.0,
        ts=(now - timedelta(minutes=5)).isoformat(),
    )

    assert is_pair_analysis_stale(stale, now=now)
    score = score_pair(stale)
    assert score.components["stale_data_penalty"] == 1.0
    assert "analysis_stale" in score.explanation
