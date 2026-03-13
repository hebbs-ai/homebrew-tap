"""Tests for demo config loading and validation."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from demo.config import DemoConfig


def test_default_config_has_gemini():
    cfg = DemoConfig.default()
    assert cfg.llm.conversation_provider == "gemini"
    assert cfg.llm.conversation_model == "gemini-2.0-flash"
    assert cfg.llm.extraction_provider == "gemini"
    assert cfg.llm.extraction_model == "gemini-2.0-flash"


def test_default_config_hebbs_address():
    cfg = DemoConfig.default()
    assert cfg.hebbs.address == "localhost:6380"


def test_load_toml_config(tmp_path):
    toml = b"""
[llm]
conversation_provider = "openai"
conversation_model = "gpt-4o"
extraction_provider = "openai"
extraction_model = "gpt-4o-mini"

[llm.openai]
api_key_env = "OPENAI_API_KEY"

[hebbs]
address = "my-server:6380"
"""
    p = tmp_path / "test.toml"
    p.write_bytes(toml)
    cfg = DemoConfig.from_toml(p)
    assert cfg.llm.conversation_provider == "openai"
    assert cfg.llm.conversation_model == "gpt-4o"
    assert cfg.hebbs.address == "my-server:6380"


def test_config_not_found():
    with pytest.raises(FileNotFoundError):
        DemoConfig.from_toml("/nonexistent/path.toml")


def test_validate_warns_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg = DemoConfig.default()
    warnings = cfg.validate()
    assert len(warnings) >= 1
    assert "GEMINI_API_KEY" in warnings[0]


def test_validate_passes_with_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    cfg = DemoConfig.default()
    warnings = cfg.validate()
    assert len(warnings) == 0


def test_gemini_provider_config():
    cfg = DemoConfig.default()
    prov = cfg.get_llm_provider_config("gemini")
    assert prov.api_key_env == "GEMINI_API_KEY"
    assert prov.model == "gemini-2.0-flash"
