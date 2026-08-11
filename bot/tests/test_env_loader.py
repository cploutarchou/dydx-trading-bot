import os
from pathlib import Path

from src.shared.env_loader import load_file_env_values, load_repo_env


def test_load_file_env_values_loads_mounted_secret(monkeypatch, tmp_path: Path) -> None:
    secret_path = tmp_path / "bot-api-token"
    secret_path.write_text("service-token\n", encoding="utf-8")

    monkeypatch.setenv("BOT_API_TOKEN_FILE", str(secret_path))
    monkeypatch.delenv("BOT_API_TOKEN", raising=False)

    load_file_env_values(override=True)

    assert os.getenv("BOT_API_TOKEN") == "service-token"


def _write_test_runtime_config(tmp_path: Path) -> Path:
    (tmp_path / ".github").mkdir()
    (tmp_path / "AGENTS.md").write_text("test\n", encoding="utf-8")
    (tmp_path / "run.json").write_text(
        '{"runtime":{"BOT_DATABASE_URL":"profile-db","PROFILE_ONLY":"loaded"}}',
        encoding="utf-8",
    )
    anchor = tmp_path / "bot" / "src" / "entrypoint.py"
    anchor.parent.mkdir(parents=True)
    anchor.write_text("# test\n", encoding="utf-8")
    return anchor


def test_load_repo_env_overrides_process_env_by_default(
    monkeypatch, tmp_path: Path
) -> None:
    anchor = _write_test_runtime_config(tmp_path)
    monkeypatch.setenv("BOT_DATABASE_URL", "process-db")
    monkeypatch.delenv("APP_CONFIG_PRESERVE_PROCESS_ENV", raising=False)

    load_repo_env(anchor)

    assert os.getenv("BOT_DATABASE_URL") == "profile-db"
    assert os.getenv("PROFILE_ONLY") == "loaded"


def test_load_repo_env_can_preserve_devcontainer_process_env(
    monkeypatch, tmp_path: Path
) -> None:
    anchor = _write_test_runtime_config(tmp_path)
    monkeypatch.setenv("APP_CONFIG_PRESERVE_PROCESS_ENV", "true")
    monkeypatch.setenv("BOT_DATABASE_URL", "process-db")

    load_repo_env(anchor)

    assert os.getenv("BOT_DATABASE_URL") == "process-db"
    assert os.getenv("PROFILE_ONLY") == "loaded"
