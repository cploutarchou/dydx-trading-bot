"""Regression tests for the extracted arbitrage router (monolith Phase 4)."""

from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

import src.api.server as server
import src.api.v1.arbitrage as arbitrage_module
from src.api.v1.arbitrage import router as arbitrage_router
from src.middleware.auth_middleware import get_current_active_user


@pytest.fixture
def authed_app(monkeypatch):
    async def _active_user():
        return SimpleNamespace(is_active=True)

    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        _active_user,
    )
    return server.app


async def _request(method: str, path: str, **kwargs):
    """Exercise ASGI directly; the installed legacy TestClient adapter deadlocks."""

    transport = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, path, **kwargs)


def test_arbitrage_request_model_reexport_identity():
    """Keep the prior ``server.ArbitrageRuntimeSettingsRequest`` import path."""

    assert (
        server.ArbitrageRuntimeSettingsRequest
        is arbitrage_module.ArbitrageRuntimeSettingsRequest
    )


def test_arbitrage_router_has_five_authenticated_routes():
    routes = [route for route in arbitrage_router.routes if isinstance(route, APIRoute)]
    operations = {
        (method, route.path)
        for route in routes
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    assert operations == {
        ("GET", "/api/v1/arbitrage/improvement-metrics"),
        ("GET", "/api/v1/arbitrage/runtime-settings"),
        ("PUT", "/api/v1/arbitrage/runtime-settings"),
        ("GET", "/api/v1/arbitrage/pair-priority"),
        ("GET", "/api/v1/arbitrage/opportunity/{opportunity_id}/explain"),
    }
    for route in routes:
        dependencies = [dependency.call for dependency in route.dependant.dependencies]
        assert get_current_active_user in dependencies
        assert route.endpoint.__module__ == "src.api.v1.arbitrage"

    direct_duplicates = [
        route
        for route in server.app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/arbitrage/")
    ]
    mounts = [
        route
        for route in server.app.routes
        if getattr(route, "original_router", None) is arbitrage_router
    ]
    assert direct_duplicates == []
    assert len(mounts) == 1


@pytest.mark.asyncio
async def test_arbitrage_routes_require_auth(monkeypatch):
    async def _reject_credentials():
        raise HTTPException(status_code=401, detail="Missing credentials")

    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    monkeypatch.setitem(
        server.app.dependency_overrides,
        get_current_active_user,
        _reject_credentials,
    )
    requests = [
        await _request("GET", "/api/v1/arbitrage/improvement-metrics"),
        await _request("GET", "/api/v1/arbitrage/runtime-settings"),
        await _request("PUT", "/api/v1/arbitrage/runtime-settings", json={}),
        await _request("GET", "/api/v1/arbitrage/pair-priority"),
        await _request("GET", "/api/v1/arbitrage/opportunity/sample/explain"),
    ]

    assert [response.status_code for response in requests] == [401] * 5


@pytest.mark.asyncio
async def test_runtime_settings_get_and_put_preserve_envelope(authed_app, monkeypatch):
    _ = authed_app
    captured = {}
    monkeypatch.setattr(
        arbitrage_module,
        "get_runtime_settings",
        lambda: {"PAIR_PRIORITY_MAX_PAIRS": 25},
    )
    monkeypatch.setattr(
        arbitrage_module,
        "get_feature_flags",
        lambda: {"pair_priority_engine": True},
    )

    response = await _request("GET", "/api/v1/arbitrage/runtime-settings")
    assert response.status_code == 200
    assert response.json()["data"] == {
        "settings": {"PAIR_PRIORITY_MAX_PAIRS": 25},
        "feature_flags": {"pair_priority_engine": True},
    }
    assert response.json()["trace_id"]

    def _update(payload):
        captured.update(payload)
        return {"PAIR_PRIORITY_MAX_PAIRS": payload["PAIR_PRIORITY_MAX_PAIRS"]}

    monkeypatch.setattr(arbitrage_module, "update_runtime_settings", _update)
    response = await _request(
        "PUT",
        "/api/v1/arbitrage/runtime-settings",
        json={
            "ARBITRAGE_IMPROVEMENTS_ENABLED": False,
            "PAIR_PRIORITY_MAX_PAIRS": 40,
            "PAIR_PRIORITY_STALE_SECONDS": 0,
            "unknown_legacy_field": "ignored",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "ARBITRAGE_IMPROVEMENTS_ENABLED": False,
        "PAIR_PRIORITY_MAX_PAIRS": 40,
        "PAIR_PRIORITY_STALE_SECONDS": 0.0,
    }
    assert response.json()["data"]["settings"] == {"PAIR_PRIORITY_MAX_PAIRS": 40}
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_improvement_metrics_preserve_runtime_context(authed_app, monkeypatch):
    _ = authed_app
    captured = {}
    monkeypatch.setattr(arbitrage_module, "get_feature_flags", lambda: {"flag": True})
    monkeypatch.setattr(arbitrage_module, "get_runtime_settings", lambda: {"limit": 7})

    def _snapshot(context):
        captured.update(context)
        return {"counters": {"evaluated": 3}, **context}

    monkeypatch.setattr(arbitrage_module, "snapshot_metrics", _snapshot)

    response = await _request("GET", "/api/v1/arbitrage/improvement-metrics")

    assert response.status_code == 200
    assert captured == {
        "feature_flags": {"flag": True},
        "runtime_settings": {"limit": 7},
    }
    assert response.json()["data"]["counters"] == {"evaluated": 3}
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_runtime_settings_validation_uses_standard_envelope(authed_app):
    _ = authed_app
    response = await _request(
        "PUT",
        "/api/v1/arbitrage/runtime-settings",
        json={"PAIR_PRIORITY_MAX_PAIRS": -1},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["data"]["errors"]
    assert response.json()["trace_id"]


@pytest.mark.asyncio
async def test_cost_gate_settings_round_trip_and_clamp(authed_app, monkeypatch):
    """The new keys pass the request model, clamp, and read back via GET."""
    _ = authed_app
    from src.trading import arbitrage_runtime_config

    monkeypatch.setattr(arbitrage_runtime_config, "_overrides", {})

    response = await _request(
        "PUT",
        "/api/v1/arbitrage/runtime-settings",
        json={
            "COST_GATE_ENABLED": True,
            "COST_GATE_EDGE_MULTIPLE": 50,
            "COST_GATE_TAKER_FEE": 0.0007,
            "COST_GATE_SLIPPAGE_BPS": 5000,
            "FUNDING_SAME_SIDE_THRESHOLD": 0.00002,
        },
    )
    assert response.status_code == 200
    settings = response.json()["data"]["settings"]
    assert settings["COST_GATE_ENABLED"] is True
    assert settings["COST_GATE_EDGE_MULTIPLE"] == 20.0
    assert settings["COST_GATE_TAKER_FEE"] == 0.0007
    assert settings["COST_GATE_SLIPPAGE_BPS"] == 1000.0
    assert settings["FUNDING_SAME_SIDE_THRESHOLD"] == 0.00002
    assert response.json()["data"]["feature_flags"]["COST_GATE_ENABLED"] is True

    response = await _request(
        "PUT",
        "/api/v1/arbitrage/runtime-settings",
        json={"COST_GATE_EDGE_MULTIPLE": 0.5, "COST_GATE_ENABLED": False},
    )
    assert response.status_code == 200

    response = await _request("GET", "/api/v1/arbitrage/runtime-settings")
    assert response.status_code == 200
    settings = response.json()["data"]["settings"]
    assert settings["COST_GATE_EDGE_MULTIPLE"] == 1.0
    assert settings["COST_GATE_ENABLED"] is False
    # Keys not sent in the second PUT keep their earlier values.
    assert settings["COST_GATE_SLIPPAGE_BPS"] == 1000.0


@pytest.mark.asyncio
async def test_cost_gate_settings_reject_negative_values(authed_app, monkeypatch):
    _ = authed_app
    from src.trading import arbitrage_runtime_config

    monkeypatch.setattr(arbitrage_runtime_config, "_overrides", {})
    response = await _request(
        "PUT",
        "/api/v1/arbitrage/runtime-settings",
        json={"COST_GATE_SLIPPAGE_BPS": -1},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert arbitrage_runtime_config._overrides == {}


def test_cost_gate_runtime_defaults_are_off_and_clamped():
    from src.trading import arbitrage_runtime_config

    defaults = arbitrage_runtime_config._DEFAULTS
    assert "COST_GATE_ENABLED" in arbitrage_runtime_config.FEATURE_FLAG_KEYS
    for key in (
        "COST_GATE_EDGE_MULTIPLE",
        "COST_GATE_TAKER_FEE",
        "COST_GATE_SLIPPAGE_BPS",
        "FUNDING_SAME_SIDE_THRESHOLD",
    ):
        assert key in arbitrage_runtime_config.FLOAT_SETTING_KEYS
        (lower, upper), _fallback = arbitrage_runtime_config._FLOAT_SETTING_CLAMPS[key]
        assert lower <= defaults[key] <= upper


def test_cost_gate_non_finite_override_falls_back_to_startup_default(monkeypatch):
    from src.trading import arbitrage_runtime_config

    monkeypatch.setattr(arbitrage_runtime_config, "_overrides", {})
    monkeypatch.setitem(
        arbitrage_runtime_config._DEFAULTS, "COST_GATE_SLIPPAGE_BPS", 7.0
    )

    settings = arbitrage_runtime_config.update_runtime_settings(
        {"COST_GATE_SLIPPAGE_BPS": "nan", "COST_GATE_EDGE_MULTIPLE": "inf"}
    )

    assert settings["COST_GATE_SLIPPAGE_BPS"] == 7.0
    assert (
        settings["COST_GATE_EDGE_MULTIPLE"]
        == arbitrage_runtime_config._DEFAULTS["COST_GATE_EDGE_MULTIPLE"]
    )


@pytest.mark.asyncio
async def test_pair_priority_clamps_limit_and_formats_scores(authed_app, monkeypatch):
    _ = authed_app
    pair = SimpleNamespace(base_market="BTC-USD", quote_market="ETH-USD")
    score = SimpleNamespace(
        pair="BTC-USD/ETH-USD",
        score=0.75,
        components={"liquidity": 0.8},
        explanation=["liquid pair"],
    )
    captured = {}

    monkeypatch.setattr(arbitrage_module.pair_storage, "load_pairs", lambda: [pair])
    monkeypatch.setattr(
        arbitrage_module, "is_pair_priority_engine_enabled", lambda: True
    )

    def _prioritize(pairs, max_pairs):
        captured["pairs"] = pairs
        captured["max_pairs"] = max_pairs
        return pairs, [score]

    monkeypatch.setattr(arbitrage_module, "prioritize_pairs", _prioritize)

    response = await _request(
        "GET", "/api/v1/arbitrage/pair-priority", params={"limit": 9999}
    )

    assert response.status_code == 200
    assert captured == {"pairs": [pair], "max_pairs": 100}
    assert response.json()["data"] == {
        "pairs": [
            {
                "pair": "BTC-USD/ETH-USD",
                "base_market": "BTC-USD",
                "quote_market": "ETH-USD",
                "score": 0.75,
                "components": {"liquidity": 0.8},
                "explanation": ["liquid pair"],
                "enabled": True,
            }
        ],
        "count": 1,
        "enabled": True,
    }


@pytest.mark.asyncio
async def test_pair_priority_disabled_preserves_storage_order(authed_app, monkeypatch):
    _ = authed_app
    pairs = [
        SimpleNamespace(base_market="BTC-USD", quote_market="ETH-USD"),
        SimpleNamespace(base_market="SOL-USD", quote_market="ADA-USD"),
    ]
    monkeypatch.setattr(arbitrage_module.pair_storage, "load_pairs", lambda: pairs)
    monkeypatch.setattr(
        arbitrage_module, "is_pair_priority_engine_enabled", lambda: False
    )
    monkeypatch.setattr(
        arbitrage_module,
        "prioritize_pairs",
        lambda *_args, **_kwargs: pytest.fail("disabled engine must not rank pairs"),
    )
    monkeypatch.setattr(
        arbitrage_module,
        "score_pair",
        lambda pair: SimpleNamespace(
            pair=f"{pair.base_market}/{pair.quote_market}",
            score=0.25,
            components={},
            explanation=[],
        ),
    )

    response = await _request(
        "GET", "/api/v1/arbitrage/pair-priority", params={"limit": 1}
    )

    assert response.status_code == 200
    assert response.json()["data"]["count"] == 1
    assert response.json()["data"]["pairs"][0]["pair"] == "BTC-USD/ETH-USD"
    assert response.json()["data"]["pairs"][0]["enabled"] is False


@pytest.mark.asyncio
async def test_pair_priority_rejects_non_integer_limit(authed_app):
    _ = authed_app
    response = await _request(
        "GET",
        "/api/v1/arbitrage/pair-priority",
        params={"limit": "not-an-int"},
    )

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["data"]["errors"]


@pytest.mark.asyncio
async def test_opportunity_explain_matches_and_sorts_rejections(
    authed_app, monkeypatch
):
    _ = authed_app
    monkeypatch.setattr(
        arbitrage_module,
        "snapshot_metrics",
        lambda _context: {
            "rejection_reasons": {"spread_too_narrow": 3, "low_liquidity": 5},
            "counters": {"evaluated": 8},
            "feature_flags": {"enabled": True},
            "runtime_settings": {"max_pairs": 25},
        },
    )
    monkeypatch.setattr(arbitrage_module, "get_feature_flags", lambda: {})
    monkeypatch.setattr(arbitrage_module, "get_runtime_settings", lambda: {})

    response = await _request(
        "GET", "/api/v1/arbitrage/opportunity/spread%20too%20narrow/explain"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["matched_rejection_reason"] == {
        "reason": "spread_too_narrow",
        "count": 3,
    }
    assert data["top_rejection_reasons"][0] == {
        "reason": "low_liquidity",
        "count": 5.0,
    }


@pytest.mark.asyncio
async def test_capabilities_and_openapi_include_extracted_arbitrage_routes(authed_app):
    _ = authed_app
    response = await _request("GET", "/api/v1/capabilities")
    assert response.status_code == 200
    capabilities = response.json()["data"]

    expected_operations = {
        "GET /api/v1/arbitrage/improvement-metrics",
        "GET /api/v1/arbitrage/runtime-settings",
        "PUT /api/v1/arbitrage/runtime-settings",
        "GET /api/v1/arbitrage/pair-priority",
        "GET /api/v1/arbitrage/opportunity/{opportunity_id}/explain",
    }
    arbitrage_operations = [
        operation
        for operation in capabilities["http_endpoints"]
        if "/api/v1/arbitrage/" in operation
    ]
    assert set(arbitrage_operations) == expected_operations
    assert len(arbitrage_operations) == len(expected_operations)
    assert "PUT /api/v1/arbitrage/runtime-settings" in capabilities["command_endpoints"]
    assert (
        len(
            [
                operation
                for operation in capabilities["query_endpoints"]
                if "/api/v1/arbitrage/" in operation
            ]
        )
        == 4
    )

    schema = server.app.openapi()
    assert set(schema["paths"]["/api/v1/arbitrage/runtime-settings"]) == {
        "get",
        "put",
    }
    request_schema = schema["components"]["schemas"]["ArbitrageRuntimeSettingsRequest"]
    assert (
        request_schema["properties"]["PAIR_PRIORITY_MAX_PAIRS"]["anyOf"][0]["minimum"]
        == 0
    )

    for path, path_item in schema["paths"].items():
        if not path.startswith("/api/v1/arbitrage/"):
            continue
        for operation in path_item.values():
            assert operation["security"] == [{"BearerAuth": []}]
            assert operation["x-response-envelope"] == "StandardApiResponse"
            assert "tags" not in operation
