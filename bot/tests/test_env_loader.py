import os
from pathlib import Path

from src.shared.env_loader import load_file_env_values


def test_load_file_env_values_loads_mounted_secret(monkeypatch, tmp_path: Path) -> None:
    secret_path = tmp_path / "bot-api-token"
    secret_path.write_text("service-token\n", encoding="utf-8")

    monkeypatch.setenv("BOT_API_TOKEN_FILE", str(secret_path))
    monkeypatch.delenv("BOT_API_TOKEN", raising=False)

    load_file_env_values(override=True)

    assert os.getenv("BOT_API_TOKEN") == "service-token"
