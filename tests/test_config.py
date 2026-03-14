from pathlib import Path

import pytest

from lidl_recipe.config import Config


def test_require_access_token_exits_when_empty():
    config = Config(access_token="")
    with pytest.raises(SystemExit) as exc_info:
        config.require_access_token()
    assert exc_info.value.code == 1


def test_require_access_token_returns_token():
    config = Config(access_token="my-token")
    assert config.require_access_token() == "my-token"


def test_require_gemini_key_exits_when_empty():
    config = Config(gemini_api_key="")
    with pytest.raises(SystemExit) as exc_info:
        config.require_gemini_key()
    assert exc_info.value.code == 1


def test_require_gemini_key_returns_key():
    config = Config(gemini_api_key="my-key")
    assert config.require_gemini_key() == "my-key"


def test_tasks_token_file_relative_to_project_root(tmp_path):
    config = Config(project_root=tmp_path)
    assert config.tasks_token_file == tmp_path / "tasks_token.json"


def test_tasks_credentials_file_relative_to_project_root(tmp_path):
    config = Config(project_root=tmp_path)
    assert config.tasks_credentials_file == tmp_path / "credentials.json"


def test_save_token_creates_env_and_writes(tmp_path):
    config = Config(project_root=tmp_path)
    config.save_token("test-token-123")

    env_file = tmp_path / ".env"
    assert env_file.exists()
    content = env_file.read_text()
    assert "LIDL_ACCESS_TOKEN" in content
    assert "test-token-123" in content


def test_save_token_updates_existing_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LIDL_ACCESS_TOKEN='old-token'\n")

    config = Config(project_root=tmp_path)
    config.save_token("new-token")

    content = env_file.read_text()
    assert "new-token" in content
    assert "old-token" not in content
