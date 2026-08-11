"""Shared TOTP (2FA) database-state helpers.

Both the login flow (``src/api/v1/auth/__init__.py``) and the setup/verify flow
(``src/api/v1/auth/password_2fa.py``) need to look up a user's TOTP secret and
enabled flag from the ``user_tokens`` table. Centralizing those queries here keeps
a single source of truth for the 2FA state model:

* ``token_type="totp_secret"``  — the user's TOTP shared secret (pyotp base32).
* ``token_type="totp_enabled"`` — presence of a non-revoked row means 2FA is on.

The login enforcement (``verify_totp_for_user``) is also rooted here so the
normalization + defense-in-depth format check is identical to the setup ``verify``
handler.
"""

from typing import cast

from sqlalchemy.orm import Session

from src.api.auth_utils import TwoFactorUtils
from src.infrastructure.domain.models.auth_models import UserToken


def _token_value(record: UserToken) -> str:
    return str(cast(object, record.token))


def get_totp_secret_record(session: Session, user_id: int):
    """Most recent non-revoked ``totp_secret`` row for the user, or ``None``."""
    return (
        session.query(UserToken)
        .filter(
            UserToken.user_id == user_id,
            UserToken.token_type == "totp_secret",
            UserToken.is_revoked.is_(False),
        )
        .order_by(UserToken.created_at.desc())
        .first()
    )


def get_totp_enabled_record(session: Session, user_id: int):
    """Most recent non-revoked ``totp_enabled`` row for the user, or ``None``."""
    return (
        session.query(UserToken)
        .filter(
            UserToken.user_id == user_id,
            UserToken.token_type == "totp_enabled",
            UserToken.is_revoked.is_(False),
        )
        .order_by(UserToken.created_at.desc())
        .first()
    )


def is_two_factor_enabled(session: Session, user_id: int) -> bool:
    """True if the user has a non-revoked ``totp_enabled`` row."""
    return get_totp_enabled_record(session, user_id) is not None


def verify_totp_for_user(session: Session, user_id: int, raw_code: str) -> bool:
    """Validate a TOTP code for the user.

    Returns ``False`` on any failure (no secret configured, malformed code, or a
    wrong code) — never raises. The caller decides the HTTP response, so this is
    safe to call from the unauthenticated login path. Normalization and the
    ``{6, 8}``-digit length check mirror the setup ``verify`` handler exactly.
    """
    secret_record = get_totp_secret_record(session, user_id)
    if not secret_record:
        return False

    code = (raw_code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) not in {6, 8}:
        return False

    return bool(TwoFactorUtils.verify_totp_token(_token_value(secret_record), code))
