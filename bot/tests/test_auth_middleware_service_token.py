import pytest

from src.middleware.auth_middleware import authenticate_bearer_token


class _FailingSession:
    """Session stub that fails if DB lookup is attempted for service-token auth."""

    def query(self, *_args, **_kwargs):  # pragma: no cover - safety assertion
        raise AssertionError("DB query should not be used for service-token authentication")


@pytest.mark.parametrize("token", ["token-current", "token-previous"])
def test_authenticate_bearer_token_accepts_rotation_overlap_tokens(monkeypatch, token):
    """Both current and previous service tokens are accepted during rotation overlap."""
    monkeypatch.setenv("BOT_API_TOKEN", "token-current")
    monkeypatch.setenv("BOT_API_TOKEN_PREVIOUS", "token-previous")
    monkeypatch.delenv("BOT_API_TOKENS", raising=False)

    user = authenticate_bearer_token(f"Bearer {token}", _FailingSession())

    assert user.username == "backend-service-token"
    assert user.is_active is True
    assert user.is_superuser is True
