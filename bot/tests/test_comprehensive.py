"""Comprehensive functionality checks (pytest-compatible)."""

import os

from fastapi.testclient import TestClient

from src.api.server import app
from src.infrastructure.persistence.repository_realtime import (
    AlertRepository,
    MarketDataRepository,
    PositionRepository,
    PositionSnapshotsRepository,
    UnitOfWorkRealtime,
)

os.environ["PYTHONIOENCODING"] = "utf-8"


def test_comprehensive_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    if "data" in data:
        assert "status" in data["data"]
    elif "status" in data:
        assert data["status"] == "healthy"


def test_comprehensive_auth_enforcement():
    client = TestClient(app)
    auth_test_routes = [
        "/api/v1/bots/test/positions/pos-1",
        "/api/v1/bots/test/market-data",
        "/api/v1/bots/test/realtime-stats",
        "/api/v1/bots/test/alerts",
        "/api/v1/bots/test/position-history/pos-1",
    ]

    for route in auth_test_routes:
        response = client.get(route)
        assert response.status_code in [401, 403, 422]


def test_comprehensive_openapi_schema():
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    for field in ["openapi", "info", "paths"]:
        assert field in schema


def test_comprehensive_realtime_repository_contracts():
    repos = {
        PositionRepository: ["get_open_positions", "get_position_by_id"],
        AlertRepository: ["get_unacknowledged_alerts", "get_unnotified_alerts"],
        PositionSnapshotsRepository: ["get_position_history"],
        MarketDataRepository: ["get_all_market_data", "get_market_data"],
        UnitOfWorkRealtime: ["__enter__", "__exit__"],
    }

    for repo_class, methods in repos.items():
        for method in methods:
            assert hasattr(repo_class, method)
