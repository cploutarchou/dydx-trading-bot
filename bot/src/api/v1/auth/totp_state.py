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

from datetime import timedelta
from typing import cast

from sqlalchemy.orm import Session

from src.api.auth_utils import PasswordUtils, SecurityUtils, TwoFactorUtils
from src.infrastructure.domain.models.auth_models import UserToken
from src.shared.time_utils import utc_now


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


# --------------------------------------------------------------------------- #
# Backup codes (single-use recovery factors)
# --------------------------------------------------------------------------- #
def _hash_backup_code(code: str) -> str:
    """SHA-256 of the normalized (lowercased, trimmed) code. Case-insensitive."""
    return SecurityUtils.hash_string((code or "").strip().lower())


def issue_backup_codes(session: Session, user_id: int, count: int = 10) -> list[str]:
    """Generate a fresh set of backup codes, invalidating all prior ones.

    Revokes every still-usable ``totp_backup`` row for the user, then stores a new
    set (hashed). Returns the **plain** codes — the only time they are available.
    """
    session.query(UserToken).filter(
        UserToken.user_id == user_id,
        UserToken.token_type == "totp_backup",
        UserToken.is_revoked.is_(False),
    ).update({UserToken.is_revoked: True})

    plain_codes = PasswordUtils.generate_backup_codes(count=count)
    expires_at = utc_now() + timedelta(days=3650)
    for code in plain_codes:
        session.add(
            UserToken(
                user_id=user_id,
                token=_hash_backup_code(code),
                token_type="totp_backup",
                expires_at=expires_at,
                is_revoked=False,
            )
        )
    session.commit()
    return plain_codes


def consume_backup_code(session: Session, user_id: int, raw_code: str) -> bool:
    """Match and consume a single-use backup code. Returns True on success."""
    record = (
        session.query(UserToken)
        .filter(
            UserToken.user_id == user_id,
            UserToken.token_type == "totp_backup",
            UserToken.token == _hash_backup_code(raw_code),
            UserToken.is_revoked.is_(False),
        )
        .first()
    )
    if not record:
        return False
    setattr(record, "is_revoked", True)
    session.commit()
    return True


def verify_login_second_factor(session: Session, user_id: int, raw_code: str) -> bool:
    """Accept a TOTP code OR a single-use backup code (consumed on success)."""
    if verify_totp_for_user(session, user_id, raw_code):
        return True
    return consume_backup_code(session, user_id, raw_code)


def disable_two_factor(session: Session, user_id: int) -> int:
    """Revoke every 2FA row (enabled flag, secret, backup codes).

    Returns the number of rows revoked. Setup/verify filter on ``is_revoked=False``
    so re-enabling after a disable creates fresh rows.
    """
    count = (
        session.query(UserToken)
        .filter(
            UserToken.user_id == user_id,
            UserToken.token_type.in_(("totp_enabled", "totp_secret", "totp_backup")),
        )
        .update({UserToken.is_revoked: True})
    )
    session.commit()
    return int(count or 0)
