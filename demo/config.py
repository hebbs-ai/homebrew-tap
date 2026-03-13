"""Configuration loader: TOML files, env-var resolution, validated defaults.

Adapted from the embedded hebbs-demo for gRPC client usage.
Key changes:
  - HebbsConfig.address replaces data_dir (server mode)
  - EmbeddingConfig removed (server handles embeddings)
  - Gemini added as an LLM provider
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class LlmProviderConfig:
    api_key_env: str = ""
    model: str = ""
    base_url: str = ""
    project: str = ""
    location: str = ""

    @property
    def api_key(self) -> str | None:
        if self.api_key_env:
            return os.environ.get(self.api_key_env)
        return None


@dataclass
class LlmConfig:
    conversation_provider: str = "gemini"
    conversation_model: str = "gemini-2.0-flash"
    extraction_provider: str = "gemini"
    extraction_model: str = "gemini-2.0-flash"

    gemini: LlmProviderConfig = field(default_factory=lambda: LlmProviderConfig(
        api_key_env="GEMINI_API_KEY", model="gemini-2.0-flash",
    ))
    gemini_vertex: LlmProviderConfig = field(default_factory=lambda: LlmProviderConfig(
        model="gemini-2.0-flash",
        project=os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    ))
    openai: LlmProviderConfig = field(default_factory=lambda: LlmProviderConfig(
        api_key_env="OPENAI_API_KEY", model="gpt-4o",
    ))
    anthropic: LlmProviderConfig = field(default_factory=lambda: LlmProviderConfig(
        api_key_env="ANTHROPIC_API_KEY", model="claude-sonnet-4-20250514",
    ))
    ollama: LlmProviderConfig = field(default_factory=lambda: LlmProviderConfig(
        base_url="http://localhost:11434", model="llama3.2",
    ))


@dataclass
class HebbsConfig:
    address: str = "localhost:6380"


@dataclass
class DemoConfig:
    llm: LlmConfig = field(default_factory=LlmConfig)
    hebbs: HebbsConfig = field(default_factory=HebbsConfig)

    @classmethod
    def from_toml(cls, path: str | Path) -> DemoConfig:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "rb") as f:
            raw = tomllib.load(f)
        return cls._from_dict(raw)

    @classmethod
    def default(cls) -> DemoConfig:
        return cls()

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> DemoConfig:
        cfg = cls()

        llm_raw = d.get("llm", {})
        cfg.llm.conversation_provider = llm_raw.get("conversation_provider", cfg.llm.conversation_provider)
        cfg.llm.conversation_model = llm_raw.get("conversation_model", cfg.llm.conversation_model)
        cfg.llm.extraction_provider = llm_raw.get("extraction_provider", cfg.llm.extraction_provider)
        cfg.llm.extraction_model = llm_raw.get("extraction_model", cfg.llm.extraction_model)

        for provider_name in ("gemini", "gemini_vertex", "openai", "anthropic", "ollama"):
            toml_key = provider_name.replace("_", "-")
            prov_raw = llm_raw.get(toml_key, llm_raw.get(provider_name, {}))
            prov_cfg = getattr(cfg.llm, provider_name)
            if "api_key_env" in prov_raw:
                prov_cfg.api_key_env = prov_raw["api_key_env"]
            if "model" in prov_raw:
                prov_cfg.model = prov_raw["model"]
            if "base_url" in prov_raw:
                prov_cfg.base_url = prov_raw["base_url"]
            if "project" in prov_raw:
                prov_cfg.project = prov_raw["project"]
            if "location" in prov_raw:
                prov_cfg.location = prov_raw["location"]

        hebbs_raw = d.get("hebbs", {})
        cfg.hebbs.address = hebbs_raw.get("address", cfg.hebbs.address)

        return cfg

    def get_llm_provider_config(self, provider_name: str) -> LlmProviderConfig:
        attr = provider_name.replace("-", "_")
        return getattr(self.llm, attr, LlmProviderConfig())

    def validate(self) -> list[str]:
        """Return a list of validation warnings (empty = all good)."""
        warnings: list[str] = []
        for role, prov, model in [
            ("conversation", self.llm.conversation_provider, self.llm.conversation_model),
            ("extraction", self.llm.extraction_provider, self.llm.extraction_model),
        ]:
            if prov in ("openai", "anthropic", "gemini"):
                prov_cfg = self.get_llm_provider_config(prov)
                if not prov_cfg.api_key:
                    env_name = prov_cfg.api_key_env
                    already = any(env_name in w for w in warnings)
                    if not already:
                        warnings.append(
                            f"${env_name} not set -- {role} LLM ({prov}/{model}) will fail"
                        )
            elif prov == "gemini-vertex" or prov == "gemini_vertex":
                prov_cfg = self.get_llm_provider_config("gemini_vertex")
                if not prov_cfg.project:
                    if not any("GOOGLE_CLOUD_PROJECT" in w for w in warnings):
                        warnings.append(
                            f"Vertex AI project not configured -- {role} LLM ({prov}/{model}) will fail. "
                            f"Set GOOGLE_CLOUD_PROJECT or configure project in TOML."
                        )
        return warnings
