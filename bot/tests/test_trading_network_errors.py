"""Edge case tests for network failures and API errors in trading modules.

This test suite covers:
- Network connection failures (ConnectionError, asyncio.TimeoutError)
- HTTP API errors (4xx, 5xx status codes via httpx.HTTPStatusError)
- Rate limiting scenarios (429 Too Many Requests)
- Malformed API responses
- Retry and backoff behavior
- Error propagation and metric tracking
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.exceptions import ExchangeError, TradingError
from src.trading import account_manager
from src.trading.arbitrage_observability import increment_metric

# =============================================================================
# Fixtures and Helpers
# =============================================================================


@pytest.fixture
def mock_client(monkeypatch):
    """Create a mock dYdX client for testing with required address."""
    # Mock DYDX_ADDRESS and SUBACCOUNT_NUMBER to avoid RuntimeError
    monkeypatch.setattr("src.trading.account_manager.DYDX_ADDRESS", "0xTestAddress")
    monkeypatch.setattr("src.trading.account_manager.SUBACCOUNT_NUMBER", 0)

    client = SimpleNamespace(
        wallet=None,
        node=SimpleNamespace(
            latest_block_height=AsyncMock(return_value=1000),
            cancel_order=AsyncMock(),
            place_order=AsyncMock(),
        ),
        indexer_account=SimpleNamespace(
            account=SimpleNamespace(
                get_subaccount=AsyncMock(),
                get_order=AsyncMock(),
                get_subaccount_orders=AsyncMock(),
                get_subaccount_fills=AsyncMock(),
            )
        ),
        indexer=SimpleNamespace(
            markets=SimpleNamespace(get_perpetual_markets=AsyncMock())
        ),
    )
    return client


@pytest.fixture
def mock_client_with_wallet(monkeypatch):
    """Create a mock client with a wallet."""
    # Mock constants
    monkeypatch.setattr("src.trading.account_manager.DYDX_ADDRESS", "0xFallbackAddress")
    monkeypatch.setattr("src.trading.account_manager.SUBACCOUNT_NUMBER", 0)

    client = SimpleNamespace(
        wallet=SimpleNamespace(
            address="0xTestAddress",
            node=None,
            mnemonic=None,
        ),
        node=SimpleNamespace(
            latest_block_height=AsyncMock(return_value=1000),
            cancel_order=AsyncMock(),
            place_order=AsyncMock(),
        ),
        indexer_account=SimpleNamespace(
            account=SimpleNamespace(
                get_subaccount=AsyncMock(),
                get_order=AsyncMock(),
                get_subaccount_orders=AsyncMock(),
                get_subaccount_fills=AsyncMock(),
            )
        ),
        indexer=SimpleNamespace(
            markets=SimpleNamespace(get_perpetual_markets=AsyncMock())
        ),
    )
    return client


# =============================================================================
# Account Manager - Network Failure Tests
# =============================================================================


class TestAccountManagerNetworkFailures:
    """Test account_manager functions with network failures."""

    @pytest.mark.asyncio
    async def test_get_account_connection_error(self, mock_client):
        """Test get_account with connection error on both addresses."""
        # Setup: both addresses fail with connection error
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=ConnectionError("Failed to connect to dYdX")
        )

        # Should raise the connection error
        with pytest.raises(ConnectionError, match="Failed to connect"):
            await account_manager.get_account(mock_client)

    @pytest.mark.asyncio
    async def test_get_account_timeout_error(self, mock_client):
        """Test get_account with timeout error."""
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=asyncio.TimeoutError("Request timed out")
        )

        with pytest.raises(asyncio.TimeoutError, match="Request timed out"):
            await account_manager.get_account(mock_client)

    @pytest.mark.asyncio
    async def test_get_account_503_service_unavailable(self, mock_client):
        """Test get_account with 503 Service Unavailable."""
        error_response = httpx.Response(503, json={"error": "Service Unavailable"})
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Service Unavailable", request=MagicMock(), response=error_response
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await account_manager.get_account(mock_client)

    @pytest.mark.asyncio
    async def test_get_account_429_rate_limited(self, mock_client):
        """Test get_account with 429 Too Many Requests."""
        error_response = httpx.Response(429, json={"error": "Rate limited"})
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Rate limited", request=MagicMock(), response=error_response
            )
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await account_manager.get_account(mock_client)

        assert exc_info.value.response.status_code == 429

    @pytest.mark.asyncio
    async def test_get_account_fallback_on_404(self, mock_client):
        """Test get_account falls back to DYDX_ADDRESS on 404 for primary address."""
        # Primary address returns 404, secondary succeeds
        error_response_404 = httpx.Response(404, json={"error": "Not found"})
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "Not found", request=MagicMock(), response=error_response_404
                ),
                {"subaccount": {"address": "0xFallback"}},
            ]
        )

        # Should succeed with fallback
        result = await account_manager.get_account(mock_client)
        assert result["address"] == "0xFallback"

    @pytest.mark.asyncio
    async def test_get_open_positions_connection_error(self, mock_client):
        """Test get_open_positions with connection error."""
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=ConnectionError("Failed to connect")
        )

        with pytest.raises(ConnectionError, match="Failed to connect"):
            await account_manager.get_open_positions(mock_client)

    @pytest.mark.asyncio
    async def test_get_open_positions_404_fresh_account(self, mock_client):
        """Test get_open_positions returns empty dict on 404 for fresh account."""
        error_response = httpx.Response(404, json={"error": "Not found"})
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Not found", request=MagicMock(), response=error_response
            )
        )

        # Should return empty dict, not raise
        result = await account_manager.get_open_positions(mock_client)
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_order_connection_error(self, mock_client):
        """Test get_order with connection error."""
        mock_client.indexer_account.account.get_order = AsyncMock(
            side_effect=ConnectionError("Failed to connect")
        )

        with pytest.raises(ConnectionError, match="Failed to connect"):
            await account_manager.get_order(mock_client, "order-123")

    @pytest.mark.asyncio
    async def test_get_order_404_not_found(self, mock_client):
        """Test get_order with 404 not found."""
        error_response = httpx.Response(404, json={"error": "Order not found"})
        mock_client.indexer_account.account.get_order = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Order not found", request=MagicMock(), response=error_response
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await account_manager.get_order(mock_client, "order-123")

    @pytest.mark.asyncio
    async def test_is_open_positions_404_returns_false(self, mock_client):
        """Test is_open_positions returns False on 404 (fresh account)."""
        error_response = httpx.Response(404, json={"error": "Not found"})
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Not found", request=MagicMock(), response=error_response
            )
        )

        result = await account_manager.is_open_positions(mock_client, "BTC-USD")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_open_positions_connection_error_propagates(self, mock_client):
        """Test is_open_positions propagates connection errors (non-404)."""
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=ConnectionError("Failed to connect")
        )

        with pytest.raises(ConnectionError, match="Failed to connect"):
            await account_manager.is_open_positions(mock_client, "BTC-USD")

    @pytest.mark.asyncio
    async def test_get_order_fills_connection_error(self, mock_client):
        """Test get_order_fills with connection error."""
        mock_client.indexer_account.account.get_subaccount_fills = AsyncMock(
            side_effect=ConnectionError("Failed to connect")
        )

        with pytest.raises(ConnectionError, match="Failed to connect"):
            await account_manager.get_order_fills(mock_client, "order-123")

    @pytest.mark.asyncio
    async def test_get_order_fills_empty_response(self, mock_client):
        """Test get_order_fills with empty/invalid response."""
        mock_client.indexer_account.account.get_subaccount_fills = AsyncMock(
            return_value={"fills": []}
        )

        result = await account_manager.get_order_fills(mock_client, "order-123")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_order_fills_non_dict_response(self, mock_client):
        """Test get_order_fills with non-dict response."""
        mock_client.indexer_account.account.get_subaccount_fills = AsyncMock(
            return_value=[{"orderId": "order-123", "size": "1.0"}]
        )

        result = await account_manager.get_order_fills(mock_client, "order-123")
        assert result == [{"orderId": "order-123", "size": "1.0"}]


# =============================================================================
# Account Manager - Metrics Tracking Tests
# =============================================================================


class TestAccountManagerMetrics:
    """Test that account_manager properly tracks metrics on API failures."""

    @pytest.mark.asyncio
    @patch("src.trading.account_manager.increment_metric")
    async def test_get_subaccount_with_metrics_tracks_api_calls(
        self, mock_increment, mock_client
    ):
        """Test that successful API calls increment exchange_api_calls_total."""
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            return_value={"subaccount": {"address": "0xTest"}}
        )

        await account_manager._get_subaccount_with_metrics(mock_client, "0xTest")

        mock_increment.assert_called_once_with("exchange_api_calls_total")

    @pytest.mark.asyncio
    @patch("src.trading.account_manager.increment_metric")
    async def test_get_subaccount_with_metrics_tracks_provider_errors(
        self, mock_increment, mock_client
    ):
        """Test that provider errors increment provider_errors_total."""
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=ConnectionError("Failed")
        )

        with pytest.raises(ConnectionError):
            await account_manager._get_subaccount_with_metrics(mock_client, "0xTest")

        mock_increment.assert_called_with("provider_errors_total")

    @pytest.mark.asyncio
    @patch("src.trading.account_manager.increment_metric")
    async def test_get_perpetual_markets_tracks_metrics(
        self, mock_increment, mock_client
    ):
        """Test that get_perpetual_markets tracks both API calls and provider errors."""
        error_response = httpx.Response(500, json={"error": "Internal Server Error"})
        mock_client.indexer.markets.get_perpetual_markets = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error", request=MagicMock(), response=error_response
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await account_manager._get_perpetual_markets_with_metrics(
                mock_client, "BTC-USD"
            )

        # Should have tracked both API call and provider error
        assert mock_increment.call_count == 2
        mock_increment.assert_any_call("exchange_api_calls_total")
        mock_increment.assert_any_call("provider_errors_total")

    @pytest.mark.asyncio
    @patch("src.trading.account_manager.increment_metric")
    async def test_get_order_with_metrics_tracks_metrics(
        self, mock_increment, mock_client
    ):
        """Test that get_order tracks metrics correctly."""
        # Use a regular Exception since httpx.HTTPStatusError won't be caught by broad except
        mock_client.indexer_account.account.get_order = AsyncMock(
            side_effect=Exception("Internal Server Error")
        )

        with pytest.raises(Exception):
            await account_manager._get_order_with_metrics(mock_client, "order-123")

        # Should have tracked both API call and provider error
        # Check that both metrics were called
        calls = [str(call) for call in mock_increment.call_args_list]
        assert any("exchange_api_calls_total" in str(call) for call in calls)
        assert any("provider_errors_total" in str(call) for call in calls)


# =============================================================================
# Position Manager - Network Failure Tests
# =============================================================================


class TestPositionManagerNetworkFailures:
    """Test position_manager functions with network failures."""

    @pytest.mark.asyncio
    async def test_get_markets_connection_error(self, mock_client, monkeypatch):
        """Test get_markets with connection error."""
        from src.trading import market_data

        # Mock the indexer call directly
        mock_client.indexer.markets.get_perpetual_markets = AsyncMock(
            side_effect=ConnectionError("Failed to connect")
        )

        with pytest.raises(ConnectionError, match="Failed to connect"):
            await market_data.get_markets(mock_client)

    @pytest.mark.asyncio
    async def test_get_markets_timeout_error(self, mock_client, monkeypatch):
        """Test get_markets with timeout error."""
        from src.trading import market_data

        mock_client.indexer.markets.get_perpetual_markets = AsyncMock(
            side_effect=asyncio.TimeoutError("Request timed out")
        )

        with pytest.raises(asyncio.TimeoutError, match="Request timed out"):
            await market_data.get_markets(mock_client)

    @pytest.mark.asyncio
    async def test_get_candles_recent_network_error(self, mock_client, monkeypatch):
        """Test get_candles_recent with network error."""
        from src.trading import market_data

        # The actual function calls get_perpetual_market_candles
        mock_client.indexer.markets.get_perpetual_market_candles = AsyncMock(
            side_effect=ConnectionError("Failed to connect")
        )

        # Disable caching to ensure we hit the actual API
        with patch.object(market_data, "CANDLES_RECENT_CACHE_TTL_SECONDS", 0):
            with pytest.raises(ConnectionError, match="Failed to connect"):
                await market_data.get_candles_recent(mock_client, "BTC-USD", "1h")


# =============================================================================
# Bot Agent - Network Failure Tests
# =============================================================================


class TestBotAgentNetworkFailures:
    """Test bot_agent functions with network failures."""

    @pytest.mark.asyncio
    async def test_bot_agent_open_trades_connection_error(
        self, mock_client_with_wallet
    ):
        """Test BotAgent.open_trades with connection error - error is caught and stored in order_dict."""
        from src.trading import bot_agent

        # Create a BotAgent instance
        agent = bot_agent.BotAgent(
            client=mock_client_with_wallet,
            market_1="BTC-USD",
            market_2="ETH-USD",
            base_side="BUY",
            base_size=1.0,
            base_price=100.0,
            quote_side="SELL",
            quote_size=1.0,
            quote_price=200.0,
            accept_failsafe_base_price=95.0,
            z_score=2.0,
            half_life=3600.0,
            hedge_ratio=1.0,
        )

        # Mock the place_market_order to fail with connection error
        with patch.object(
            bot_agent,
            "place_market_order",
            AsyncMock(side_effect=ConnectionError("Failed to connect")),
        ):
            result = await agent.open_trades()

            # The exception is caught and stored in order_dict
            assert result["pair_status"] == "ERROR"
            assert "Failed to connect" in result["comments"]

    @pytest.mark.asyncio
    async def test_bot_agent_check_order_status_by_id_connection_error(
        self, mock_client_with_wallet
    ):
        """Test BotAgent.check_order_status_by_id with connection error."""
        from src.trading import bot_agent

        agent = bot_agent.BotAgent(
            client=mock_client_with_wallet,
            market_1="BTC-USD",
            market_2="ETH-USD",
            base_side="BUY",
            base_size=1.0,
            base_price=100.0,
            quote_side="SELL",
            quote_size=1.0,
            quote_price=200.0,
            accept_failsafe_base_price=95.0,
            z_score=2.0,
            half_life=3600.0,
            hedge_ratio=1.0,
        )

        # Mock check_order_status to fail
        with patch.object(
            bot_agent,
            "check_order_status",
            AsyncMock(side_effect=ConnectionError("Failed to connect")),
        ):
            with pytest.raises(ConnectionError, match="Failed to connect"):
                await agent.check_order_status_by_id("order-123")


# =============================================================================
# Edge Case: Malformed Responses
# =============================================================================


class TestMalformedAPIResponses:
    """Test handling of malformed or unexpected API responses."""

    @pytest.mark.asyncio
    async def test_get_order_fills_malformed_response(self, mock_client):
        """Test get_order_fills with malformed response structure."""
        # Response is not a dict and doesn't have 'fills' key
        mock_client.indexer_account.account.get_subaccount_fills = AsyncMock(
            return_value=["not", "a", "valid", "response"]
        )

        result = await account_manager.get_order_fills(mock_client, "order-123")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_order_fills_response_without_fills_key(self, mock_client):
        """Test get_order_fills with response missing 'fills' key."""
        mock_client.indexer_account.account.get_subaccount_fills = AsyncMock(
            return_value={"something_else": "value"}
        )

        result = await account_manager.get_order_fills(mock_client, "order-123")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_order_fills_with_non_dict_items(self, mock_client):
        """Test get_order_fills filters out non-dict items."""
        mock_client.indexer_account.account.get_subaccount_fills = AsyncMock(
            return_value={
                "fills": [
                    {"orderId": "order-123", "size": "1.0"},
                    "not a dict",
                    {"orderId": "order-456", "size": "2.0"},
                    None,
                ]
            }
        )

        result = await account_manager.get_order_fills(mock_client, "order-123")
        # Should only return the first fill (orderId matches)
        assert len(result) == 1
        assert result[0]["orderId"] == "order-123"

    @pytest.mark.asyncio
    async def test_get_open_positions_malformed_subaccount(self, mock_client):
        """Test get_open_positions with malformed subaccount response."""
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            return_value={"subaccount": {"openPerpetualPositions": "not a dict"}}
        )

        # The implementation returns openPerpetualPositions directly
        # which would be the string "not a dict"
        result = await account_manager.get_open_positions(mock_client)
        assert result == "not a dict"

    @pytest.mark.asyncio
    async def test_get_account_missing_subaccount_key(self, mock_client):
        """Test get_account with response missing 'subaccount' key."""
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            return_value={"not_subaccount": {"address": "0xTest"}}
        )

        with pytest.raises(KeyError):
            await account_manager.get_account(mock_client)


# =============================================================================
# Edge Case: Mixed Error Scenarios
# =============================================================================


class TestMixedErrorScenarios:
    """Test complex error scenarios combining multiple failure modes."""

    @pytest.mark.asyncio
    async def test_get_account_primary_timeout_secondary_connection_error(
        self, mock_client
    ):
        """Test get_account with timeout on primary and connection error on secondary."""
        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=[
                asyncio.TimeoutError("Primary timeout"),
                ConnectionError("Secondary connection failed"),
            ]
        )

        with pytest.raises(ConnectionError, match="Secondary connection failed"):
            await account_manager.get_account(mock_client)

    @pytest.mark.asyncio
    async def test_is_open_positions_404_then_500(self, mock_client):
        """Test is_open_positions with 404 on primary and 500 on secondary."""
        error_404 = httpx.Response(404, json={"error": "Not found"})
        error_500 = httpx.Response(500, json={"error": "Internal Server Error"})

        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "Not found", request=MagicMock(), response=error_404
                ),
                httpx.HTTPStatusError(
                    "Internal Server Error", request=MagicMock(), response=error_500
                ),
            ]
        )

        # Should propagate the 500 error since it's not a 404
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await account_manager.is_open_positions(mock_client, "BTC-USD")

        assert exc_info.value.response.status_code == 500

    @pytest.mark.asyncio
    async def test_sequential_api_calls_with_intermittent_failures(self, mock_client):
        """Test sequential API calls where some succeed and some fail."""
        # First call succeeds, second fails
        call_count = 0

        async def side_effect_with_counter(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "subaccount": {"address": "0xTest", "openPerpetualPositions": {}}
                }
            else:
                raise ConnectionError("Second call failed")

        mock_client.indexer_account.account.get_subaccount = AsyncMock(
            side_effect=side_effect_with_counter
        )

        # First call should succeed
        result1 = await account_manager.get_account(mock_client)
        assert result1["address"] == "0xTest"

        # Second call should fail
        with pytest.raises(ConnectionError, match="Second call failed"):
            await account_manager.get_account(mock_client)


# =============================================================================
# Edge Case: Retry and Backoff Behavior
# =============================================================================


class TestRetryAndBackoff:
    """Test retry and exponential backoff behavior for transient failures."""

    @pytest.mark.asyncio
    async def test_entry_backoff_increases_delay(self):
        """Test that entry backoff increases delay with each failure."""
        from src.trading.position_manager import (
            _ENTRY_FAILURE_STATE,
            _entry_backoff_seconds,
            _record_entry_failure,
        )

        # Clear any previous state
        _ENTRY_FAILURE_STATE.clear()

        pair_key = "BTC-USD|ETH-USD"

        # First failure: delay should be base (15 seconds)
        _record_entry_failure(pair_key, "error 1")
        delay1 = _entry_backoff_seconds(1)
        assert delay1 == 15.0

        # Second failure: delay should be base * multiplier (15 * 2 = 30)
        _record_entry_failure(pair_key, "error 2")
        delay2 = _entry_backoff_seconds(2)
        assert delay2 == 30.0

        # Third failure: delay should be base * multiplier^2 (15 * 4 = 60)
        _record_entry_failure(pair_key, "error 3")
        delay3 = _entry_backoff_seconds(3)
        assert delay3 == 60.0

    @pytest.mark.asyncio
    async def test_entry_backoff_capped_at_max(self):
        """Test that entry backoff is capped at maximum."""
        from src.trading.position_manager import (
            _ENTRY_FAILURE_STATE,
            _entry_backoff_seconds,
            _record_entry_failure,
        )

        _ENTRY_FAILURE_STATE.clear()

        pair_key = "BTC-USD|ETH-USD"

        # Record many failures
        for i in range(10):
            _record_entry_failure(pair_key, f"error {i}")

        # Delay should be capped at 180 seconds
        delay = _entry_backoff_seconds(10)
        assert delay == 180.0

    @pytest.mark.asyncio
    async def test_entry_backoff_success_resets_state(self):
        """Test that successful entry resets backoff state."""
        from src.trading.position_manager import (
            _ENTRY_FAILURE_STATE,
            _entry_backoff_seconds,
            _record_entry_failure,
            _record_entry_success,
        )

        _ENTRY_FAILURE_STATE.clear()

        pair_key = "BTC-USD|ETH-USD"

        # Record failures
        _record_entry_failure(pair_key, "error 1")
        _record_entry_failure(pair_key, "error 2")

        assert pair_key in _ENTRY_FAILURE_STATE

        # Record success
        _record_entry_success(pair_key)

        # State should be cleared
        assert pair_key not in _ENTRY_FAILURE_STATE


# =============================================================================
# Edge Case: Concurrent Network Failures
# =============================================================================


class TestConcurrentNetworkFailures:
    """Test concurrent network failure scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_get_account_calls(self, mock_client):
        """Test concurrent get_account calls with network failures on both addresses."""

        # Create a side effect that always fails
        async def always_failing_get_subaccount(*args, **kwargs):
            await asyncio.sleep(0.01)
            raise ConnectionError("All calls fail")

        mock_client.indexer_account.account.get_subaccount = (
            always_failing_get_subaccount
        )

        # Launch multiple concurrent calls
        tasks = [account_manager.get_account(mock_client) for _ in range(3)]

        # All calls should fail since both addresses fail
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that all calls failed
        errors = [r for r in results if isinstance(r, ConnectionError)]

        assert len(errors) == 3

    @pytest.mark.asyncio
    async def test_concurrent_api_calls_with_rate_limiting(self, mock_client):
        """Test concurrent API calls hitting rate limits on both addresses."""
        # Use a list to track calls in a thread-safe way
        rate_limited_calls = []

        async def rate_limited_get_subaccount(*args, **kwargs):
            # All calls rate limited
            rate_limited_calls.append(1)
            await asyncio.sleep(0.01)
            error_response = httpx.Response(429, json={"error": "Rate limited"})
            raise httpx.HTTPStatusError(
                "Rate limited", request=MagicMock(), response=error_response
            )

        mock_client.indexer_account.account.get_subaccount = rate_limited_get_subaccount

        # Launch 10 concurrent calls
        tasks = [account_manager.get_account(mock_client) for _ in range(10)]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should fail with 429 since both addresses get rate limited
        rate_limited = [
            r
            for r in results
            if isinstance(r, httpx.HTTPStatusError) and r.response.status_code == 429
        ]

        # All 10 should be rate limited (5 from first address, 5 from fallback)
        # But due to the fallback, we'll get 20 calls total, but only 10 results
        assert len(rate_limited) == 10
        assert len(results) == 10
