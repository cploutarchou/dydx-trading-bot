import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.infrastructure import database
from src.infrastructure.domain.cointegration_storage import (
    CointegrationResult,
    PairStorage,
    load_stored_pair_scan,
)

_DDL = """
CREATE TABLE cointegrated_pairs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  instance_id VARCHAR(64) NOT NULL UNIQUE,
  pairs_json TEXT NOT NULL DEFAULT '[]',
  pairs_count INTEGER NOT NULL DEFAULT 0,
  high_confidence_count INTEGER NOT NULL DEFAULT 0,
  analyzed_at DATETIME NOT NULL
)
"""


@pytest.fixture
def pairs_table(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as connection:
        connection.execute(text(_DDL))
    monkeypatch.setattr(database.db, "get_session", sessionmaker(bind=engine))
    return engine


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


def test_a_workers_scan_is_readable_by_instance_id(pairs_table, tmp_path, monkeypatch):
    """What one worker saves under its BOT_INSTANCE_ID, the API reads by that id."""
    monkeypatch.setenv("BOT_INSTANCE_ID", "strategy-7-3")
    storage = PairStorage(storage_path=str(tmp_path / "pairs.json"))

    assert storage.save_pairs([_pair("BTC-USD", "ETH-USD")])["success"] is True
    assert not (tmp_path / "pairs.json").exists()  # the database took it

    session = database.db.get_session()
    try:
        scan = load_stored_pair_scan(session, "strategy-7-3")
        other = load_stored_pair_scan(session, "strategy-7-4")
    finally:
        session.close()

    assert other is None
    assert scan is not None
    assert scan.instance_id == "strategy-7-3"
    assert scan.analyzed_at is not None
    assert scan.timestamp is not None
    assert [(p["base_market"], p["quote_market"]) for p in scan.pairs] == [
        ("BTC-USD", "ETH-USD")
    ]
    # The raw row is handed over unprojected; the route decides the wire shape.
    assert scan.pairs[0]["intercept"] == 0.0


def test_load_stored_pair_scan_tolerates_malformed_rows(pairs_table):
    with pairs_table.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO cointegrated_pairs (instance_id, pairs_json, analyzed_at) "
                "VALUES (:iid, :pj, :aa)"
            ),
            [
                {"iid": "broken-json", "pj": "{not json", "aa": "2026-09-26 11:30:00"},
                {"iid": "not-an-object", "pj": "[1, 2]", "aa": "2026-09-26 11:30:00"},
                {
                    "iid": "mixed",
                    "pj": json.dumps(
                        {
                            "timestamp": "2026-09-26T11:30:00+00:00",
                            "pairs": [{"base_market": "A-USD"}, "junk", 3],
                        }
                    ),
                    "aa": "2026-09-26 11:30:00",
                },
            ],
        )

    session = database.db.get_session()
    try:
        broken = load_stored_pair_scan(session, "broken-json")
        not_object = load_stored_pair_scan(session, "not-an-object")
        mixed = load_stored_pair_scan(session, "mixed")
    finally:
        session.close()

    assert broken is not None and broken.pairs == [] and broken.timestamp is None
    assert not_object is not None and not_object.pairs == []
    assert mixed is not None
    assert mixed.pairs == [{"base_market": "A-USD"}]
    assert mixed.timestamp == "2026-09-26T11:30:00+00:00"
    assert mixed.analyzed_at == "2026-09-26 11:30:00"
