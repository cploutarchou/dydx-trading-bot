import asyncio
from types import SimpleNamespace

from src.trading import account_manager


class _FakeAccountAPI:
    def __init__(self, *, should_fail: bool = False):
        self.should_fail = should_fail

    async def get_subaccount(self, _address, _subaccount_number):
        if self.should_fail:
            raise RuntimeError("boom")
        return {"subaccount": {"id": "ok"}}

    async def get_order(self, _order_id):
        if self.should_fail:
            raise RuntimeError("boom")
        return {"id": "ord-1", "status": "OPEN"}

    async def get_subaccount_orders(self, *_args, **_kwargs):
        if self.should_fail:
            raise RuntimeError("boom")
        return [{"id": "ord-1"}]


def test_get_subaccount_with_metrics_increments_api_counter(monkeypatch):
    metric_names: list[str] = []

    def _capture_metric(name: str, amount: float = 1.0):
        del amount
        metric_names.append(name)

    fake_client = SimpleNamespace(
        indexer_account=SimpleNamespace(account=_FakeAccountAPI(should_fail=False))
    )

    monkeypatch.setattr(account_manager, "increment_metric", _capture_metric)

    result = asyncio.run(account_manager._get_subaccount_with_metrics(fake_client, "addr1"))

    assert result["subaccount"]["id"] == "ok"
    assert metric_names.count("exchange_api_calls_total") == 1
    assert metric_names.count("provider_errors_total") == 0


def test_get_subaccount_with_metrics_increments_provider_errors_on_failure(monkeypatch):
    metric_names: list[str] = []

    def _capture_metric(name: str, amount: float = 1.0):
        del amount
        metric_names.append(name)

    fake_client = SimpleNamespace(
        indexer_account=SimpleNamespace(account=_FakeAccountAPI(should_fail=True))
    )

    monkeypatch.setattr(account_manager, "increment_metric", _capture_metric)

    try:
        asyncio.run(account_manager._get_subaccount_with_metrics(fake_client, "addr1"))
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

    assert metric_names.count("exchange_api_calls_total") == 1
    assert metric_names.count("provider_errors_total") == 1


def test_get_order_with_metrics_increments_api_counter(monkeypatch):
    metric_names: list[str] = []

    def _capture_metric(name: str, amount: float = 1.0):
        del amount
        metric_names.append(name)

    fake_client = SimpleNamespace(
        indexer_account=SimpleNamespace(account=_FakeAccountAPI(should_fail=False))
    )

    monkeypatch.setattr(account_manager, "increment_metric", _capture_metric)

    result = asyncio.run(account_manager._get_order_with_metrics(fake_client, "ord-1"))

    assert result["id"] == "ord-1"
    assert metric_names.count("exchange_api_calls_total") == 1
    assert metric_names.count("provider_errors_total") == 0


def test_get_subaccount_orders_with_metrics_increments_provider_error(monkeypatch):
    metric_names: list[str] = []

    def _capture_metric(name: str, amount: float = 1.0):
        del amount
        metric_names.append(name)

    fake_client = SimpleNamespace(
        indexer_account=SimpleNamespace(account=_FakeAccountAPI(should_fail=True))
    )

    monkeypatch.setattr(account_manager, "increment_metric", _capture_metric)

    try:
        asyncio.run(
            account_manager._get_subaccount_orders_with_metrics(
                fake_client,
                "addr1",
                0,
                status="OPEN",
            )
        )
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

    assert metric_names.count("exchange_api_calls_total") == 1
    assert metric_names.count("provider_errors_total") == 1
