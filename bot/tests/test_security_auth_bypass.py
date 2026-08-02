"""Dedicated security regression suite for authentication-bypass defenses.

This suite is the single place that systematically pins the authentication
invariants for the bot API, so that a regression of any earlier security fix
(auth-bypass on protected routes, secure WebSocket auth, credential encryption,
token revocation) is caught here rather than in production. It complements the
narrower, feature-specific tests (``test_backtest_route_auth``,
``test_websocket_security_fix``, ``test_token_revocation``,
``test_auth_bypass_environment_guard``, ``test_auth_middleware_service_token``).

Coverage areas:

1. **Route-coverage gate** — every mutating (POST/PUT/PATCH/DELETE) ``/api/v1/*``
   route declares an executable auth dependency; admin-scoped routes declare the
   admin dependency. This is the direct regression test for the original
   auth-bypass class of bug (routes lacking auth deps).
2. **Credential / authorization behavior** — missing credentials, disabled
   users, and non-admin escalation are rejected with the right status codes.
3. **Token defenses** — wrong / near-miss service tokens and signature-tampered
   JWTs are rejected.
4. **Bypass startup guard** — ``API_BYPASS_AUTH=true`` in a production-like
   environment crashes startup (RuntimeError) rather than silently disabling auth.
5. **Runtime enforcement** — representative protected routes return 401 over
   HTTP when no credentials are supplied.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.api import server
from src.api.auth_utils import JWTUtils
from src.middleware import auth_middleware

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

# Both public auth functions count as "an auth dependency is present". Every
# protected route ultimately resolves through ``get_current_user``; at the route
# declaration level that surfaces as ``get_current_active_user`` or
# ``get_admin_user``.
AUTH_DEPENDENCY_CALLS = {
    server.get_current_active_user,
    server.get_admin_user,
}

# Mutating routes that are intentionally public (login/registration/token grant).
# Listed explicitly so the route-coverage gate can distinguish "deliberately
# public" from "forgot to add auth". Includes both the prefixed (mounted) paths
# and the unprefixed paths seen on the auth router before its include prefix is
# applied (FastAPI 0.138+ exposes included-router routes via _IncludedRouter
# with the original, unprefixed paths).
PUBLIC_MUTATING_PATHS = {
    "/auth/token",
    "/auth/login",
    "/auth/register",
    "/api/v1/auth/token",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/token",
    "/login",
    "/register",
}

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _user(*, is_active=True, is_admin=False):
    return SimpleNamespace(
        username="tester",
        email="tester@example.local",
        is_active=is_active,
        is_admin=is_admin,
        is_superuser=is_admin,
        token_version=0,
    )


class _StubSession:
    """Minimal session stand-in; auth rejection paths never reach the DB."""

    def query(self, *_args, **_kwargs):
        return SimpleNamespace(
            filter=lambda *_a, **_k: SimpleNamespace(first=lambda: None)
        )

    def close(self):
        return None


def _mutating_api_routes():
    """All registered mutating APIRoutes (the gate's scope).

    Covers both routes defined directly on ``app`` AND routes brought in via
    ``app.include_router``. FastAPI 0.138+ wraps included routers lazily as
    ``_IncludedRouter``; those routes are reachable through ``original_router``.
    Dedupes because the auth router is mounted under two prefixes.
    """
    seen: set[tuple[frozenset, str]] = set()
    out: list = []

    def _consider(route: APIRoute) -> None:
        if not (route.methods or set()) & MUTATING_METHODS:
            return
        key = (frozenset(route.methods or ()), route.path)
        if key in seen:
            return
        seen.add(key)
        out.append(route)

    for route in server.app.routes:
        if isinstance(route, APIRoute):
            _consider(route)
        elif type(route).__name__ == "_IncludedRouter":
            original = getattr(route, "original_router", None)
            for sub in getattr(original, "routes", []) or []:
                if isinstance(sub, APIRoute):
                    _consider(sub)
    return out


def _route_auth_callables(route: APIRoute):
    return [dependency.call for dependency in route.dependant.dependencies]


# --------------------------------------------------------------------------- #
# 1. Route-coverage gate
# --------------------------------------------------------------------------- #


def test_mutating_api_routes_declare_auth_dependency():
    """Every mutating /api/v1/* route must declare an executable auth dependency.

    This is the regression test for the original auth-bypass vulnerability
    (routes shipping without ``Depends(get_current_active_user)``). Any new
    mutating route must either declare auth or be added to
    ``PUBLIC_MUTATING_PATHS`` deliberately.
    """
    routes = _mutating_api_routes()
    # Guard against a vacuous pass if route discovery ever breaks.
    assert len(routes) >= 20, f"expected >=20 mutating routes, found {len(routes)}"

    unprotected = []
    for route in routes:
        # Auth-router public routes (login/register) are legitimately unauthenticated.
        if route.path in PUBLIC_MUTATING_PATHS:
            continue
        if not (AUTH_DEPENDENCY_CALLS & set(_route_auth_callables(route))):
            unprotected.append(f"{sorted(route.methods)[0]} {route.path}")

    assert not unprotected, (
        "Mutating routes missing an auth dependency (add auth or allowlist): "
        + ", ".join(unprotected)
    )


def test_admin_scoped_routes_declare_admin_dependency():
    """Admin/celery mutating routes must require the admin dependency."""
    admin_routes = [
        route
        for route in _mutating_api_routes()
        if "/admin/" in route.path or "/celery/" in route.path
    ]
    assert admin_routes, "expected at least one admin-scoped mutating route"

    missing = []
    for route in admin_routes:
        if server.get_admin_user not in _route_auth_callables(route):
            missing.append(f"{sorted(route.methods)[0]} {route.path}")

    assert (
        not missing
    ), "Admin-scoped routes missing get_admin_user dependency: " + ", ".join(missing)


# --------------------------------------------------------------------------- #
# 2. Credential / authorization behavior
# --------------------------------------------------------------------------- #


def test_get_current_user_rejects_missing_credentials(monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    with pytest.raises(auth_middleware.AuthenticationError) as exc:
        asyncio.run(
            auth_middleware.get_current_user(credentials=None, session=_StubSession())
        )
    assert exc.value.status_code == 401


def test_disabled_user_is_rejected_by_active_user_dependency():
    with pytest.raises(auth_middleware.AuthorizationError) as exc:
        asyncio.run(
            auth_middleware.get_current_active_user(current_user=_user(is_active=False))
        )
    assert exc.value.status_code == 403


def test_non_admin_user_blocked_from_admin_dependency():
    with pytest.raises(auth_middleware.AuthorizationError) as exc:
        asyncio.run(auth_middleware.get_admin_user(current_user=_user(is_admin=False)))
    assert exc.value.status_code == 403


def test_admin_user_passes_admin_dependency():
    user = asyncio.run(
        auth_middleware.get_admin_user(current_user=_user(is_admin=True))
    )
    assert user.is_admin is True


# --------------------------------------------------------------------------- #
# 3. Token defenses
# --------------------------------------------------------------------------- #


def test_service_token_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("BOT_API_TOKEN", "valid-service-token")
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    with pytest.raises(auth_middleware.AuthenticationError) as exc:
        auth_middleware.authenticate_bearer_token("wrong-token", _StubSession())
    assert exc.value.status_code == 401


@pytest.mark.parametrize(
    "near_miss",
    [
        "valid-service-toke",  # truncated (prefix match attempt)
        "valid-service-tokenX",  # extra char (suffix)
        "valid-service-tokn",  # single char altered
        " VALID-SERVICE-TOKEN ",  # case/whitespace must not match
        "",
    ],
)
def test_service_token_rejects_near_miss_tokens(monkeypatch, near_miss):
    """Timing-safe comparison must not accept prefix/suffix/single-char near misses."""
    monkeypatch.setenv("BOT_API_TOKEN", "valid-service-token")
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    with pytest.raises(auth_middleware.AuthenticationError):
        auth_middleware.authenticate_bearer_token(near_miss, _StubSession())


def test_tampered_jwt_signature_is_rejected(monkeypatch):
    """A JWT whose signature does not verify must not authenticate."""
    from jose import jwt

    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    # Encode with a different secret so the signature will not verify.
    tampered = jwt.encode({"sub": "alice", "stv": 0}, "wrong-secret", algorithm="HS256")
    with pytest.raises(auth_middleware.AuthenticationError) as exc:
        auth_middleware.authenticate_bearer_token(tampered, _StubSession())
    assert exc.value.status_code == 401


# --------------------------------------------------------------------------- #
# 4. Auth-bypass startup guard
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("environment", ["production", "prod", "live", "mainnet"])
def test_auth_bypass_crashes_startup_in_production_environments(
    monkeypatch, environment
):
    """API_BYPASS_AUTH=true in a production-like env must raise at startup."""
    monkeypatch.setenv("API_BYPASS_AUTH", "true")
    # ``current_environment_name`` reads APP_CONFIG_ENV/CONFIG_ENV before ENVIRONMENT,
    # so pin the highest-precedence key to avoid leakage from the loaded dev config.
    monkeypatch.setenv("APP_CONFIG_ENV", environment)
    with pytest.raises(RuntimeError, match="forbidden"):
        auth_middleware.validate_auth_bypass_configuration()


def test_auth_bypass_disabled_by_default(monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    monkeypatch.setenv("APP_CONFIG_ENV", "production")
    assert auth_middleware.is_auth_bypass_enabled() is False


# --------------------------------------------------------------------------- #
# 5. Runtime enforcement over HTTP
# --------------------------------------------------------------------------- #


def test_protected_routes_return_401_without_credentials(monkeypatch):
    """Representative protected routes reject unauthenticated requests over HTTP."""
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    client = TestClient(server.app)

    probes = [
        ("/api/v1/bots", "POST", {}),
        ("/api/v1/backtests/compare", "POST", {"run_ids": ["a", "b"]}),
        ("/api/v1/strategies", "POST", {"name": "x"}),
    ]
    for path, method, body in probes:
        response = client.request(method, path, json=body)
        assert (
            response.status_code == 401
        ), f"{method} {path} without credentials returned {response.status_code}, expected 401"


def test_admin_route_returns_401_without_credentials(monkeypatch):
    monkeypatch.delenv("API_BYPASS_AUTH", raising=False)
    client = TestClient(server.app)
    response = client.post(
        "/api/v1/admin/runtime/strategy-resolution-metrics/reset", json={}
    )
    assert response.status_code == 401
