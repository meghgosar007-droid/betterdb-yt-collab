from __future__ import annotations

from typing import Literal

import redis as redis_lib
from google import genai
from openai import AsyncOpenAI
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _has_secret(value: SecretStr | None) -> bool:
    return bool(value and value.get_secret_value().strip())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    llm_provider: Literal["openai", "gemini"] = "openai"
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    redis_url: str = "redis://localhost:6379"
    openai_model: str = "gpt-4o-mini"
    gemini_model: str = "gemini-3.8-flash"
    embedding_model: str = ""
    chunk_size: int = 500
    chunk_overlap: int = 50
    cache_threshold: float = 0.85
    rate_limit_minute: int = 10
    rate_limit_hour: int = 100

    @model_validator(mode="after")
    def _validate_provider(self) -> Settings:
        if self.llm_provider == "gemini":
            if not _has_secret(self.gemini_api_key):
                raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
            if not self.embedding_model:
                self.embedding_model = "gemini-embedding-001"
        else:
            if not _has_secret(self.openai_api_key):
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
            if not self.embedding_model:
                self.embedding_model = "text-embedding-3-small"
        return self

    @property
    def llm_model(self) -> str:
        return self.gemini_model if self.llm_provider == "gemini" else self.openai_model


_settings: Settings | None = None
_redis: redis_lib.Redis | None = None
_openai: AsyncOpenAI | None = None
_gemini: genai.Client | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        key = get_settings().openai_api_key
        if not _has_secret(key):
            raise RuntimeError("OPENAI_API_KEY is not set")
        _openai = AsyncOpenAI(api_key=key.get_secret_value())
    return _openai


def get_gemini() -> genai.Client:
    global _gemini
    if _gemini is None:
        key = get_settings().gemini_api_key
        if not _has_secret(key):
            raise RuntimeError("GEMINI_API_KEY is not set")
        _gemini = genai.Client(api_key=key.get_secret_value())
    return _gemini
