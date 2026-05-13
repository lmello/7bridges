"""Configuration and model routing."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRoute:
    """Maps an Anthropic model alias to a backend bridge."""

    alias: str
    bridge: str  # e.g. "deepseek", "kimi"
    backend_model: str
    display_name: str
    context_window: int = 200_000
    max_output_tokens: int = 8192


class Settings:
    """Application settings."""

    deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "")
    kimi_api_key: str = os.environ.get("KIMI_CODE_API_KEY", "")
    api_key: str = os.environ.get("BRIDGE_API_KEY", "ollama")

    model_routes: dict[str, ModelRoute] = {
        "claude-sonnet-4-6": ModelRoute(
            alias="claude-sonnet-4-6",
            bridge="deepseek",
            backend_model="deepseek-v4-pro",
            display_name="Claude Sonnet 4.6 (DeepSeek V4 Pro)",
            context_window=1_048_576,
            max_output_tokens=393_216,
        ),
        "claude-haiku-4-5": ModelRoute(
            alias="claude-haiku-4-5",
            bridge="deepseek",
            backend_model="deepseek-v4-flash",
            display_name="Claude Haiku 4.5 (DeepSeek V4 Flash)",
            context_window=1_048_576,
            max_output_tokens=393_216,
        ),
        "claude-opus-4-6": ModelRoute(
            alias="claude-opus-4-6",
            bridge="kimi",
            backend_model="kimi-for-coding",
            display_name="Claude Opus 4.6 (Kimi K2.6)",
            context_window=262_144,
            max_output_tokens=32_768,
        ),
        "claude-opus-4-7": ModelRoute(
            alias="claude-opus-4-7",
            bridge="kimi",
            backend_model="kimi-for-coding",
            display_name="Claude Opus 4.7 (Kimi K2.6)",
            context_window=262_144,
            max_output_tokens=32_768,
        ),
        # Claude Code internal fallback aliases (used for background tasks
        # like session title generation when ANTHROPIC_DEFAULT_HAIKU_MODEL
        # is set in another shell)
        "claude-haiku-4-5-20251001": ModelRoute(
            alias="claude-haiku-4-5-20251001",
            bridge="deepseek",
            backend_model="deepseek-v4-flash",
            display_name="Claude Haiku 4.5-20251001 (DeepSeek V4 Flash)",
            context_window=1_048_576,
            max_output_tokens=393_216,
        ),
    }

    # Bedrock-style variants map to the same routes
    _aliases = list(model_routes.keys())
    for alias in _aliases:
        route = model_routes[alias]
        model_routes[f"{alias}:0"] = route
        bedrock_alias = f"us.anthropic.{alias.replace('-', '_')}-v1"
        model_routes[bedrock_alias] = route
        model_routes[f"{bedrock_alias}:0"] = route


settings = Settings()
