"""Self-registration on the bot API is disabled unless explicitly enabled."""

import httpx
import pytest

import src.api.server as server
from src.api.v1 import auth as auth_module

_PAYLOAD = {
    "username": "newcomer",
    "email": "newcomer@example.com",
    "password": "Str0ng-Password-For-Tests!",
    "full_name": "New Comer",
}


async def _post_register():
    transport = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        return await client.post("/api/v1/auth/register", json=_PAYLOAD)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, "", "false", "0", "no", "maybe"])
async def test_register_is_forbidden_unless_explicitly_enabled(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("BOT_API_ALLOW_SELF_REGISTRATION", raising=False)
    else:
        monkeypatch.setenv("BOT_API_ALLOW_SELF_REGISTRATION", value)

    response = await _post_register()

    assert response.status_code == 403, response.text
    assert "disabled" in response.text.lower()


@pytest.mark.parametrize("value", ["true", "TRUE", " 1 ", "yes"])
def test_flag_enables_registration(monkeypatch, value):
    monkeypatch.setenv("BOT_API_ALLOW_SELF_REGISTRATION", value)

    assert auth_module.self_registration_enabled() is True
