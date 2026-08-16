"""Tests for multi-account portfolio enumeration and exposure reads.

``src/trading/portfolio_accounts.py`` enumerates the deployment's distinct
subaccounts from ``bot_instances`` (best-effort decrypt, deterministic order,
TTL cache) and reads their exposure via public indexer calls (404 = complete
zero exposure; the guard-path loader propagates other errors, the
monitoring-path loader degrades per account). The pure aggregate sums live in
``summarize_exposures``; the aggregate ENTRY decision (limits-aware) is tested
in ``tests/test_portfolio_risk.py``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest

import src.trading.portfolio_accounts as portfolio_accounts
from src.trading.portfolio_accounts import (
    AccountExposure,
    PortfolioAccountRef,
    enumerate_portfolio_accounts,
    extract_account_ref,
    load_account_exposures_http,
    load_account_exposures_via_client,
    normalize_network,
    parse_account_exposure,
    summarize_exposures,
)


def _ref(address: str, network: str = "testnet") -> PortfolioAccountRef:
    return PortfolioAccountRef(address=address, network=network)


def _exposure(
    address: str,
    *,
    equity: float | None,
    free: float | None,
    open_markets: int,
    complete: bool = True,
    network: str = "testnet",
) -> AccountExposure:
    return AccountExposure(
        address=address,
        network=network,
        equity=equity,
        free_collateral=free,
        open_market_count=open_markets,
        complete=complete,
    )


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


def test_normalize_network_maps_non_mainnet_to_testnet():
    assert normalize_network("mainnet") == "mainnet"
    assert normalize_network("MAINNET") == "mainnet"
    assert normalize_network(" testnet ") == "testnet"
    assert normalize_network(None) == "testnet"
    assert normalize_network("") == "testnet"


def test_parse_account_exposure_reads_subaccount_fields():
    payload = {
        "equity": "1234.5",
        "freeCollateral": "1000",
        "openPerpetualPositions": {"BTC-USD": {}, "ETH-USD": {}},
    }
    exposure = parse_account_exposure(_ref("0x1"), payload)
    assert exposure.address == "0x1"
    assert exposure.equity == 1234.5
    assert exposure.free_collateral == 1000.0
    assert exposure.open_market_count == 2
    assert exposure.complete is True
    assert exposure.error is None


def test_parse_account_exposure_malformed_payload_is_incomplete():
    exposure = parse_account_exposure(_ref("0x1"), {"equity": "nonsense"})
    assert exposure.equity is None
    assert exposure.complete is False
    # Non-dict payloads degrade to a fully incomplete exposure.
    assert parse_account_exposure(_ref("0x1"), None).complete is False


def test_summarize_exposures_sums_complete_accounts_only():
    exposures = (
        _exposure("0x1", equity=1000.0, free=800.0, open_markets=3),
        _exposure("0x2", equity=None, free=None, open_markets=2, complete=False),
        _exposure("0x3", equity=500.0, free=100.0, open_markets=1),
    )
    totals = summarize_exposures(exposures)
    assert totals.accounts == 3
    assert totals.incomplete_accounts == 1
    assert totals.total_equity == 1500.0
    assert totals.total_free_collateral == 900.0
    # Open markets count every account (positions are readable even when the
    # equity fields are malformed).
    assert totals.total_open_markets == 6
    # (1500 - 900) / 1500 = 40%
    assert totals.margin_utilization_pct == pytest.approx(40.0)


def test_summarize_exposures_zero_equity_has_no_utilization():
    totals = summarize_exposures(())
    assert totals.accounts == 0
    assert totals.total_equity == 0.0
    assert totals.margin_utilization_pct is None


# --------------------------------------------------------------------------- #
# Enumeration (bot_instances → refs)
# --------------------------------------------------------------------------- #


def _record(config: Any, network: str = "testnet", instance_id: str = "bot-1"):
    return SimpleNamespace(config=config, network=network, instance_id=instance_id)


def test_extract_account_ref_reads_plaintext_config():
    record = _record(
        {"credentials": {"address": " 0xabc ", "mnemonic": "words"}},
        network="mainnet",
    )
    ref = extract_account_ref(record)
    assert ref == PortfolioAccountRef(address="0xabc", network="mainnet")


def test_extract_account_ref_accepts_json_string_config():
    record = _record('{"credentials": {"address": "0xdef"}}')
    assert extract_account_ref(record) == _ref("0xdef")


@pytest.mark.parametrize(
    "config",
    [
        None,
        {},
        {"credentials": {}},
        {"credentials": {"address": "   "}},
        "not-json",
        "[1, 2, 3]",
        42,
    ],
)
def test_extract_account_ref_skips_unresolvable_rows(config):
    assert extract_account_ref(_record(config)) is None


def test_extract_account_ref_undecryptable_row_falls_back_to_raw():
    # A malformed sealed envelope: decryption raises, the raw payload is used,
    # and it carries no plaintext address — so the row is skipped (not fatal).
    sealed = {"credentials_sealed": {"nonce": "AAAA", "ciphertext": "%%%not-base64%%%"}}
    assert extract_account_ref(_record(sealed)) is None


def test_enumerate_dedupes_and_orders_deterministically(monkeypatch):
    records = [
        _record({"credentials": {"address": "0xb"}}, "testnet", "bot-2"),
        _record({"credentials": {"address": "0xa"}}, "mainnet", "bot-3"),
        _record({"credentials": {"address": "0xb"}}, "testnet", "bot-2-dup"),
        _record({"credentials": {"address": "0xc"}}, "testnet", "bot-1"),
    ]

    class _Query:
        def all(self):
            return records

    class _Session:
        def query(self, model):
            return _Query()

        def close(self):
            pass

    import src.infrastructure.database as database
    import src.infrastructure.db_offload as db_offload

    async def _fake_run_db(func):
        return func()

    monkeypatch.setattr(db_offload, "run_db", _fake_run_db)
    monkeypatch.setattr(database.db, "get_session", lambda: _Session())

    refs = asyncio.run(enumerate_portfolio_accounts())
    assert refs == (
        PortfolioAccountRef("0xa", "mainnet"),
        PortfolioAccountRef("0xb", "testnet"),
        PortfolioAccountRef("0xc", "testnet"),
    )


def test_enumerate_caches_within_ttl(monkeypatch):
    calls = []

    async def _fake_run_db(func):  # pragma: no cover - replaced per call
        calls.append(func)
        return ()

    import src.infrastructure.db_offload as db_offload

    monkeypatch.setattr(db_offload, "run_db", _fake_run_db)

    portfolio_accounts.reset_portfolio_account_cache()
    first = asyncio.run(enumerate_portfolio_accounts())
    second = asyncio.run(enumerate_portfolio_accounts())
    assert first == second == ()
    assert len(calls) == 1  # second call served from cache

    forced = asyncio.run(enumerate_portfolio_accounts(force_refresh=True))
    assert len(calls) == 2
    assert forced == ()


# --------------------------------------------------------------------------- #
# Exposure loaders
# --------------------------------------------------------------------------- #


def _http_404() -> Exception:
    request = httpx.Request("GET", "https://indexer/v4/addresses/0x1")
    return httpx.HTTPStatusError(
        "404", request=request, response=httpx.Response(404, request=request)
    )


class _FakeIndexerAccount:
    def __init__(self, payloads: dict[str, Any], errors: dict[str, Exception]):
        self.account = self
        self._payloads = payloads
        self._errors = errors
        self.calls: list[str] = []

    async def get_subaccount(self, address, subaccount_number):
        self.calls.append(address)
        if address in self._errors:
            raise self._errors[address]
        return self._payloads[address]


def test_client_loader_reads_all_refs_concurrently():
    indexer = _FakeIndexerAccount(
        payloads={
            "0x1": {
                "subaccount": {
                    "equity": "100",
                    "freeCollateral": "90",
                    "openPerpetualPositions": {"A-USD": {}},
                }
            },
            "0x2": {
                "subaccount": {
                    "equity": "50",
                    "freeCollateral": "10",
                    "openPerpetualPositions": {},
                }
            },
        },
        errors={},
    )
    client = SimpleNamespace(indexer_account=indexer)
    exposures = asyncio.run(
        load_account_exposures_via_client(cast(Any, client), (_ref("0x1"), _ref("0x2")))
    )
    assert indexer.calls == ["0x1", "0x2"]
    assert [e.equity for e in exposures] == [100.0, 50.0]
    assert exposures[0].open_market_count == 1
    assert all(e.complete for e in exposures)


def test_client_loader_maps_404_to_complete_zero_exposure():
    indexer = _FakeIndexerAccount(payloads={}, errors={"0x1": _http_404()})
    client = SimpleNamespace(indexer_account=indexer)
    exposures = asyncio.run(
        load_account_exposures_via_client(cast(Any, client), (_ref("0x1"),))
    )
    assert exposures[0].complete is True
    assert exposures[0].equity == 0.0
    assert exposures[0].open_market_count == 0


def test_client_loader_propagates_transport_errors():
    indexer = _FakeIndexerAccount(
        payloads={}, errors={"0x1": httpx.ConnectError("boom")}
    )
    client = SimpleNamespace(indexer_account=indexer)
    with pytest.raises(httpx.ConnectError):
        asyncio.run(
            load_account_exposures_via_client(cast(Any, client), (_ref("0x1"),))
        )


def test_client_loader_propagates_http_500():
    request = httpx.Request("GET", "https://indexer/v4/addresses/0x1")
    error_500 = httpx.HTTPStatusError(
        "500",
        request=request,
        response=httpx.Response(500, request=request),
    )
    indexer = _FakeIndexerAccount(payloads={}, errors={"0x1": error_500})
    client = SimpleNamespace(indexer_account=indexer)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(
            load_account_exposures_via_client(cast(Any, client), (_ref("0x1"),))
        )


def test_http_loader_degrades_unreachable_accounts_best_effort(monkeypatch):
    refs = (_ref("0x1"), _ref("0x2", network="mainnet"))

    class _FakeHttp:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            if "/0x2/" in url:
                raise _http_404()
            if "/0x1/" in url:
                raise httpx.ConnectError("unreachable")
            raise AssertionError(url)

    import httpx as httpx_module

    monkeypatch.setattr(httpx_module, "AsyncClient", lambda **kwargs: _FakeHttp())
    exposures = asyncio.run(load_account_exposures_http(refs))
    assert exposures[0].complete is False
    assert exposures[0].error == "ConnectError"
    assert exposures[1].complete is True
    assert exposures[1].equity == 0.0


def test_http_loader_parses_response_bodies(monkeypatch):
    """The loader must call ``.json()`` on the httpx response (regression: a
    live check caught the raw Response being treated as the payload dict)."""
    refs = (_ref("0x1"),)
    subaccount = {
        "equity": "750.5",
        "freeCollateral": "500",
        "openPerpetualPositions": {"ETH-USD": {}},
    }

    class _FakeResponse:
        def __init__(self, payload=None, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                request = httpx.Request("GET", "https://indexer")
                raise httpx.HTTPStatusError(
                    str(self.status_code),
                    request=request,
                    response=httpx.Response(self.status_code, request=request),
                )

    class _FakeHttp:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            from src.constants import SUBACCOUNT_NUMBER

            assert url == (
                f"https://indexer.v4testnet.dydx.exchange/v4/addresses/0x1"
                f"/subaccountNumber/{SUBACCOUNT_NUMBER}"
            ), url
            return _FakeResponse(payload={"subaccount": subaccount})

    import httpx as httpx_module

    monkeypatch.setattr(httpx_module, "AsyncClient", lambda **kwargs: _FakeHttp())
    exposures = asyncio.run(load_account_exposures_http(refs))
    assert exposures == (
        AccountExposure(
            address="0x1",
            network="testnet",
            equity=750.5,
            free_collateral=500.0,
            open_market_count=1,
            complete=True,
            error=None,
        ),
    )


def test_http_loader_with_no_refs_is_empty():
    assert asyncio.run(load_account_exposures_http(())) == ()


def test_http_loader_maps_404_status_to_complete_zero_exposure(monkeypatch):
    """Plain httpx does not raise on 404 — the loader must surface it through
    raise_for_status and map it to a complete zero-exposure account (regression
    found by the live monitoring-endpoint check)."""
    refs = (_ref("0x1"),)

    class _FakeResponse:
        status_code = 404

        def json(self):  # pragma: no cover - must not be reached
            raise AssertionError("404 body must not be parsed")

        def raise_for_status(self):
            request = httpx.Request("GET", "https://indexer")
            raise httpx.HTTPStatusError(
                "404",
                request=request,
                response=httpx.Response(404, request=request),
            )

    class _FakeHttp:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return _FakeResponse()

    import httpx as httpx_module

    monkeypatch.setattr(httpx_module, "AsyncClient", lambda **kwargs: _FakeHttp())
    exposures = asyncio.run(load_account_exposures_http(refs))
    assert exposures[0].complete is True
    assert exposures[0].equity == 0.0
    assert exposures[0].open_market_count == 0
