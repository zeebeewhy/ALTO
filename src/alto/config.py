"""Industrial-grade configuration: .env + env vars, type-safe via Pydantic."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_")
    base_url: str = Field(default="https://api.moonshot.cn/v1")
    api_key: str = Field(default="")
    model_name: str = Field(default="kimi-latest")
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


# Singleton
_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
