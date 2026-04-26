"""Industrial-grade configuration: .env + env vars, type-safe via Pydantic.

Multi-provider API key resolution with Kimi Code as first-class citizen:
- Kimi Code API (会员订阅额度) → KIMI_CODE_API_KEY
- Moonshot Open Platform (开放平台按量计费) → MOONSHOT_API_KEY
- OpenAI / DeepSeek / OpenRouter / 任意兼容端点 → OPENAI_API_KEY
- ALTO own naming → LLM_API_KEY

All providers speak OpenAI-compatible protocol.
"""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


# ── Provider defaults ──────────────────────────────────────────────────────
_KIMI_CODE_BASE_URL = "https://api.kimi.com/coding/v1"
_MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1"
_OPENAI_BASE_URL = "https://api.openai.com/v1"

# Default model per provider
_KIMI_CODE_MODEL = "kimi-for-coding"
_MOONSHOT_MODEL = "kimi-latest"
_OPENAI_MODEL = "gpt-4o"


class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_")
    base_url: str = Field(default="")
    api_key: str = Field(default="")
    model_name: str = Field(default="")
    temperature_chat: float = Field(default=0.7, ge=0.0, le=2.0)
    temperature_diagnosis: float = Field(default=0.2, ge=0.0, le=2.0)
    temperature_pedagogy: float = Field(default=0.6, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1)
    timeout: float = Field(default=30.0, ge=1.0)


class MemoryConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEM_")
    storage_path: str = Field(default="./data/memory")
    activation_decay: float = Field(default=0.9, ge=0.0, le=1.0)
    activation_boost: float = Field(default=0.25, ge=0.0, le=1.0)
    stabilization_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    working_memory_capacity: int = Field(default=7, ge=1, le=20)


class DiagnosticConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DIAG_")
    spacy_model: str = Field(default="en_core_web_sm")
    fallback_enabled: bool = Field(default=True)
    systematic_error_threshold: int = Field(default=2, ge=1)


class Config(BaseSettings):
    """Global configuration aggregate."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    app_name: str = "Language Tutor System"
    debug: bool = Field(default=False)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    diagnostic: DiagnosticConfig = Field(default_factory=DiagnosticConfig)

    @field_validator("llm", mode="before")
    @classmethod
    def _validate_llm(cls, v):
        if isinstance(v, dict):
            return LLMConfig(**v)
        return v

    @field_validator("memory", mode="before")
    @classmethod
    def _validate_memory(cls, v):
        if isinstance(v, dict):
            return MemoryConfig(**v)
        return v

    @field_validator("diagnostic", mode="before")
    @classmethod
    def _validate_diagnostic(cls, v):
        if isinstance(v, dict):
            return DiagnosticConfig(**v)
        return v


# ── Multi-provider key resolution ─────────────────────────────────────────

def _resolve_api_key() -> tuple[str, str, str]:
    """Resolve API key, base_url, and model_name from multiple env sources.

    Priority order:
        1. KIMI_CODE_API_KEY  (Kimi Code 会员订阅 — 第一优先)
        2. LLM_API_KEY         (ALTO's own naming — 显式覆盖)
        3. MOONSHOT_API_KEY    (Moonshot Open Platform)
        4. OPENAI_API_KEY      (OpenAI / DeepSeek / OpenRouter — 行业标准)

    For each provider, auto-infers base_url and model_name when not explicitly set.

    Returns:
        (api_key, base_url, model_name)
    """
    # Provider definitions: (env_var_name, prefix, default_base_url, default_model)
    providers = [
        ("KIMI_CODE_API_KEY", "KIMI_CODE_", _KIMI_CODE_BASE_URL, _KIMI_CODE_MODEL),
        ("LLM_API_KEY", "LLM_", "", ""),  # LLM_ prefix requires explicit base_url
        ("MOONSHOT_API_KEY", "MOONSHOT_", _MOONSHOT_BASE_URL, _MOONSHOT_MODEL),
        ("OPENAI_API_KEY", "OPENAI_", _OPENAI_BASE_URL, _OPENAI_MODEL),
    ]

    found_key = ""
    found_prefix = ""
    found_default_url = ""
    found_default_model = ""

    for var_name, prefix, default_url, default_model in providers:
        val = os.getenv(var_name, "").strip()
        if val and not val.lower().startswith(("your", "sk-xxx", "placeholder")):
            found_key = val
            found_prefix = prefix
            found_default_url = default_url
            found_default_model = default_model
            break

    # Resolve base_url: explicit env var > provider default
    base_url = ""
    if found_prefix:
        # Try explicit base_url env var for this provider
        base_url = os.getenv(f"{found_prefix}BASE_URL", "").strip()
        # Also check generic LLM_BASE_URL as fallback
        if not base_url:
            base_url = os.getenv("LLM_BASE_URL", "").strip()
        # Fall back to provider default
        if not base_url:
            base_url = found_default_url

    # Resolve model_name
    model_name = ""
    if found_prefix:
        model_name = os.getenv(f"{found_prefix}MODEL_NAME", "").strip()
        if not model_name:
            model_name = os.getenv("LLM_MODEL_NAME", "").strip()
        if not model_name:
            model_name = found_default_model

    return found_key, base_url, model_name


# ── Singleton with resolution ───────────────────────────────────────────────
_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
        # Post-process: resolve key from multiple env sources
        key, base_url, model_name = _resolve_api_key()
        if key and not _config.llm.api_key:
            _config.llm.api_key = key
        if base_url and not _config.llm.base_url:
            _config.llm.base_url = base_url
        if model_name and not _config.llm.model_name:
            _config.llm.model_name = model_name
    return _config


def reset_config() -> None:
    """Reset singleton (useful in tests)."""
    global _config
    _config = None
