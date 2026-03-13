"""Shared test fixtures for the HEBBS Python SDK tests."""

from __future__ import annotations

import pytest

from demo.config import DemoConfig


@pytest.fixture
def default_config() -> DemoConfig:
    return DemoConfig.default()


@pytest.fixture
def gemini_config(tmp_path) -> DemoConfig:
    toml_content = b"""
[llm]
conversation_provider = "gemini"
conversation_model = "gemini-2.0-flash"
extraction_provider = "gemini"
extraction_model = "gemini-2.0-flash"

[llm.gemini]
api_key_env = "GEMINI_API_KEY"

[hebbs]
address = "localhost:6380"
"""
    config_file = tmp_path / "gemini.toml"
    config_file.write_bytes(toml_content)
    return DemoConfig.from_toml(config_file)
