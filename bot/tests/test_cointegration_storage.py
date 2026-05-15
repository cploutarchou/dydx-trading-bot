from datetime import datetime, timezone

from src.infrastructure.domain.cointegration_storage import (
    CointegrationResult,
    PairStorage,
)


def _pair(base: str, quote: str) -> CointegrationResult:
    return CointegrationResult(
        base_market=base,
        quote_market=quote,
        hedge_ratio=1.2,
        half_life=6.0,
        zero_crossings=8,
        p_value=0.01,
        z_score_mean=0.0,
        z_score_std=1.0,
        analysis_timestamp=datetime.now(timezone.utc).isoformat(),
        confidence_score=0.82,
    )


def test_save_pairs_uses_db_primary_without_file_write(tmp_path, monkeypatch):
    storage_path = tmp_path / "cointegration_results.json"
    storage = PairStorage(storage_path=str(storage_path))

    monkeypatch.setattr(storage, "_db_save", lambda _payload: True)

    result = storage.save_pairs([_pair("BTC-USD", "ETH-USD")])

    assert result["success"] is True
    assert result["pairs_saved"] == 1
    assert not storage_path.exists()


def test_load_pairs_prefers_db_payload_over_file_cache(tmp_path, monkeypatch):
    storage_path = tmp_path / "cointegration_results.json"
    storage = PairStorage(storage_path=str(storage_path))

    # Seed a stale file payload that should be ignored when DB has data.
    storage_path.write_text(
        '{"pairs": [{"base_market": "STALE-USD", "quote_market": "OLD-USD", '
        '"hedge_ratio": 1.0, "half_life": 5.0, "zero_crossings": 1, '
        '"p_value": 0.05, "z_score_mean": 0.0, "z_score_std": 1.0, '
        '"analysis_timestamp": "2026-01-01T00:00:00+00:00", "confidence_score": 0.2, '
        '"creation_timestamp": "2026-01-01T00:00:00+00:00"}] }',
        encoding="utf-8",
    )

    db_pair = _pair("BTC-USD", "ETH-USD").to_dict()
    monkeypatch.setattr(storage, "_db_load", lambda: {"pairs": [db_pair]})

    loaded = storage.load_pairs()

    assert len(loaded) == 1
    assert loaded[0].base_market == "BTC-USD"
    assert loaded[0].quote_market == "ETH-USD"
