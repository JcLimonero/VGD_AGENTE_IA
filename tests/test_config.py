"""Tests for agente_dwh.config module."""

import pytest

from agente_dwh.config import Config, ConfigError


class TestConfig:
    def test_missing_dwh_url_raises(self, monkeypatch):
        monkeypatch.delenv("DWH_URL", raising=False)
        with pytest.raises(ConfigError, match="DWH_URL"):
            Config.from_env()

    def test_valid_config(self, monkeypatch):
        monkeypatch.setenv("DWH_URL", "sqlite:///test.db")
        monkeypatch.setenv("LLM_ENDPOINT", "http://localhost:11434")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        monkeypatch.setenv("MAX_ROWS", "100")
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "30")

        cfg = Config.from_env()
        assert cfg.dwh_url == "sqlite:///test.db"
        assert cfg.llm_model == "test-model"
        assert cfg.max_rows == 100
        assert cfg.llm_timeout_seconds == 30

    def test_invalid_max_rows(self, monkeypatch):
        monkeypatch.setenv("DWH_URL", "sqlite:///test.db")
        monkeypatch.setenv("MAX_ROWS", "abc")
        with pytest.raises(ConfigError, match="MAX_ROWS"):
            Config.from_env()

    def test_negative_max_rows(self, monkeypatch):
        monkeypatch.setenv("DWH_URL", "sqlite:///test.db")
        monkeypatch.setenv("MAX_ROWS", "-5")
        with pytest.raises(ConfigError, match="MAX_ROWS"):
            Config.from_env()

    def test_defaults(self, monkeypatch):
        monkeypatch.setenv("DWH_URL", "sqlite:///test.db")
        monkeypatch.delenv("LLM_ENDPOINT", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("MAX_ROWS", raising=False)
        monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)

        cfg = Config.from_env()
        assert cfg.llm_endpoint == "http://127.0.0.1:11434"
        assert cfg.llm_model == "llama3.1"
        assert cfg.max_rows == 200
        assert cfg.llm_timeout_seconds == 60
