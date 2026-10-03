"""Environment-label helpers shared by safety gates.

Several gates relax a control only for local development and tests (auth
bypass, plaintext credential storage). They must all fail closed the same way:
an unset environment is NOT development, and a development label in one
variable cannot override a production label in another.
"""

from __future__ import annotations

import os

ENVIRONMENT_VARIABLES = ("APP_CONFIG_ENV", "CONFIG_ENV", "ENVIRONMENT", "APP_ENV")

DEV_OR_TEST_ENVIRONMENTS = frozenset(
    {"development", "dev", "local", "test", "testing", "ci"}
)


def explicit_environment_values() -> list[str]:
    """Normalized values of every environment variable that is set."""
    values = (os.getenv(key, "").strip().lower() for key in ENVIRONMENT_VARIABLES)
    return [value for value in values if value]


def is_explicit_dev_or_test_environment() -> bool:
    """True only when at least one variable is set and all name dev/test."""
    explicit = explicit_environment_values()
    return bool(explicit) and all(
        value in DEV_OR_TEST_ENVIRONMENTS for value in explicit
    )
