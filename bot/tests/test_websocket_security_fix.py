"""Test WebSocket security fixes for authentication bypass vulnerabilities."""

import asyncio
import pytest


async def test_websocket_rejects_query_parameter_tokens():
    """Test that WebSocket connections reject tokens passed via query parameters."""
    # This test verifies that the security fix for JWT in query strings is working
    # The WebSocket should only accept tokens via Authorization header

    # Import the authorization function
    from src.api.server import _authorize_websocket_connection

    # Create a mock websocket
    class MockWebSocket:
        def __init__(self):
            self.headers = {}
            self.query_params = {}
            self.closed = False
            self.close_code = None
            self.close_reason = None

        async def close(self, code: int, reason: str):
            self.closed = True
            self.close_code = code
            self.close_reason = reason

    # Test 1: WebSocket should reject query parameter tokens
    websocket = MockWebSocket()
    websocket.headers = {}  # No Authorization header
    websocket.query_params = {"access_token": "fake_token_via_query_params"}

    # This should fail since we're only using query params (no Authorization header)
    # Note: This test will fail if auth bypass is enabled, so we need to ensure it's disabled
    import os
    original_bypass = os.environ.get("API_BYPASS_AUTH")
    try:
        os.environ["API_BYPASS_AUTH"] = "false"
        result = await _authorize_websocket_connection(websocket)
        assert result == False, "WebSocket should reject query parameter tokens"
        assert websocket.closed == True, "WebSocket should be closed"
        assert websocket.close_code == 4401, "Should close with authentication error code"
    finally:
        if original_bypass is not None:
            os.environ["API_BYPASS_AUTH"] = original_bypass
        else:
            os.environ.pop("API_BYPASS_AUTH", None)

    print("✓ WebSocket security fix verified: query parameter tokens are rejected")


async def test_websocket_accepts_authorization_header():
    """Test that WebSocket connections accept tokens via Authorization header."""
    # This test verifies that proper Authorization header authentication still works

    from src.api.server import _authorize_websocket_connection

    class MockWebSocket:
        def __init__(self):
            self.headers = {}
            self.query_params = {}
            self.closed = False
            self.close_code = None
            self.close_reason = None

        async def close(self, code: int, reason: str):
            self.closed = True
            self.close_code = code
            self.close_reason = reason

    # Test 2: WebSocket should accept Authorization header (but token validation will fail in test)
    websocket = MockWebSocket()
    websocket.headers = {"authorization": "Bearer fake_token_for_test"}
    websocket.query_params = {}

    # This should attempt authentication but fail with invalid token
    import os
    original_bypass = os.environ.get("API_BYPASS_AUTH")
    try:
        os.environ["API_BYPASS_AUTH"] = "false"
        result = await _authorize_websocket_connection(websocket)
        assert result == False, "Should fail with invalid token"
        assert websocket.closed == True, "WebSocket should be closed with invalid token"
        assert "Invalid" in websocket.close_reason, "Should indicate invalid token"
    finally:
        if original_bypass is not None:
            os.environ["API_BYPASS_AUTH"] = original_bypass
        else:
            os.environ.pop("API_BYPASS_AUTH", None)

    print("✓ WebSocket still processes Authorization header tokens (validation works as expected)")


async def main():
    """Run all WebSocket security tests."""
    await test_websocket_rejects_query_parameter_tokens()
    await test_websocket_accepts_authorization_header()
    print("\n✅ All WebSocket security tests passed!")


if __name__ == "__main__":
    asyncio.run(main())