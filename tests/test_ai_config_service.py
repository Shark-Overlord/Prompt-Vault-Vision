import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import database
from services import ai_config_service


def test_ai_config_crud_masks_secret(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "ai.db")
    database.init_db()

    config = ai_config_service.create_ai_config(
        {
            "name": "DeepSeek 测试",
            "provider": "deepseek",
            "api_key": "sk-local-test",
            "model": "deepseek-chat",
            "is_default": True,
        }
    )

    assert config["id"] > 0
    assert config["api_key_set"] is True
    assert "api_key" not in config
    assert config["is_default"] is True

    raw = ai_config_service.get_ai_config(config["id"], include_secret=True)
    assert raw["api_key"] == "sk-local-test"

    updated = ai_config_service.update_ai_config(
        config["id"],
        {
            "provider": "lm_studio",
            "base_url": "http://127.0.0.1:1234/v1",
            "model": "local-model",
            "clear_api_key": True,
        },
    )
    assert updated["provider"] == "lm_studio"
    assert updated["api_key_set"] is False

    assert ai_config_service.delete_ai_config(config["id"]) is True
    assert ai_config_service.delete_ai_config(config["id"]) is False


def test_deepseek_connection_test_fails_without_key(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "ai.db")
    database.init_db()
    config = ai_config_service.create_ai_config(
        {
            "name": "DeepSeek 缺少密钥",
            "provider": "deepseek",
            "model": "deepseek-chat",
        }
    )

    result = asyncio.run(ai_config_service.test_ai_config(config["id"]))

    assert result["status"] == "failed"
    assert "API Key" in result["message"]
    refreshed = ai_config_service.get_ai_config(config["id"])
    assert refreshed["last_test_status"] == "failed"
