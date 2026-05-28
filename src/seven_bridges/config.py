"""Configuration and model routing."""

import os
import re
from dataclasses import dataclass, replace

# ── Pricing ─────────────────────────────────────────────────────────────
# Per-backend and per-model pricing overrides.  Prices are USD per 1M tokens.
# Resolution order: (backend, model) → (backend, *) → (*> *)
PRICING: dict[str, dict[str, dict[str, float]]] = {
    "deepseek": {
        "*": {"input": 0.14, "output": 1.10, "cache_read": 0.014},
    },
    "ollama": {
        "*": {"input": 0.0, "output": 0.0, "cache_read": 0.0},
    },
    "*": {
        "*": {"input": 0.40, "output": 4.00, "cache_read": 0.15},
    },
}


def get_pricing(backend: str | None = None, model_alias: str | None = None) -> dict[str, float]:
    """Resolve pricing for a given backend and optional model alias.

    Fallback chain:
      1. Exact (backend, model_alias) match
      2. Backend-level wildcard  ``(backend, "*")``
      3. Global wildcard          ``("*", "*")``
    """
    if backend and backend in PRICING:
        backend_pricing = PRICING[backend]
        if model_alias and model_alias in backend_pricing:
            return backend_pricing[model_alias]
        if "*" in backend_pricing:
            return backend_pricing["*"]
    return PRICING["*"]["*"]


@dataclass(frozen=True)
class ModelRoute:
    """Maps an Anthropic model alias to a backend bridge."""

    alias: str
    bridge: str  # e.g. "deepseek", "kimi"
    backend_model: str
    display_name: str
    context_window: int = 200_000
    max_output_tokens: int = 8192


def _version_display(suffix: str) -> str:
    """Convert a version suffix like '4-6' or '4-5-20251001' to display form.

    >>> _version_display('4-6')
    '4.6'
    >>> _version_display('4-5-20251001')
    '4.5-20251001'
    """
    parts = suffix.split("-", 1)
    return parts[0] + "." + parts[1] if len(parts) == 2 else parts[0]


class Settings:
    """Application settings."""

    deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "")
    kimi_api_key: str = os.environ.get("KIMI_CODE_API_KEY", "")
    ollama_host: str = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    ollama_keep_alive: str = os.environ.get("OLLAMA_KEEP_ALIVE", "300s")
    ollama_timeout: float = float(os.environ.get("OLLAMA_TIMEOUT", "120"))
    ollama_sonnet_model: str = os.environ.get("OLLAMA_SONNET_MODEL", "qwen3.6:35b-a3b-coding-nvfp4")
    ollama_sonnet_ctx: int = int(os.environ.get("OLLAMA_SONNET_CONTEXT_WINDOW", "32768"))
    ollama_haiku_model: str = os.environ.get("OLLAMA_HAIKU_MODEL", "qwen3.5:9b")
    ollama_haiku_ctx: int = int(os.environ.get("OLLAMA_HAIKU_CONTEXT_WINDOW", "65536"))
    ollama_gptoss_model: str = os.environ.get("OLLAMA_GPTOSS_MODEL", "gpt-oss:20b")
    ollama_gptoss_ctx: int = int(os.environ.get("OLLAMA_GPTOSS_CONTEXT_WINDOW", "65536"))
    ollama_gemma_model: str = os.environ.get("OLLAMA_GEMMA_MODEL", "gemma4:26b")
    ollama_gemma_ctx: int = int(os.environ.get("OLLAMA_GEMMA_CONTEXT_WINDOW", "65536"))
    siliconflow_api_key: str = os.environ.get("SILICONFLOW_API_KEY", "")
    fireworks_api_key: str = os.environ.get("FIREWORKSAI_API_KEY", "")
    api_key: str = os.environ.get("BRIDGE_API_KEY", "ollama")

    # Vision fallback — experimental "See No Evil, Hear No Evil" feature
    vision_fallback_enabled: bool = (
        os.environ.get("SEVEN_BRIDGES_VISION_FALLBACK_ENABLED", "").lower() == "true"
    )
    vision_fallback_backend: str = os.environ.get("SEVEN_BRIDGES_VISION_FALLBACK_BACKEND", "")
    vision_fallback_timeout: float = float(
        os.environ.get("SEVEN_BRIDGES_VISION_FALLBACK_TIMEOUT", "120")
    )

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
        # Ollama routes — configurable via OLLAMA_SONNET_MODEL / OLLAMA_HAIKU_MODEL env vars
        "claude-sonnet-4-0": ModelRoute(
            alias="claude-sonnet-4-0",
            bridge="ollama",
            backend_model=ollama_sonnet_model,
            display_name=f"Claude Sonnet 4.0 (Ollama {ollama_sonnet_model})",
            context_window=ollama_sonnet_ctx,
            max_output_tokens=8192,
        ),
        "claude-haiku-4-0": ModelRoute(
            alias="claude-haiku-4-0",
            bridge="ollama",
            backend_model=ollama_haiku_model,
            display_name=f"Claude Haiku 4.0 (Ollama {ollama_haiku_model})",
            context_window=ollama_haiku_ctx,
            max_output_tokens=8192,
        ),
        # Clean aliases that avoid Anthropic retirement warnings
        "ollama-sonnet": ModelRoute(
            alias="ollama-sonnet",
            bridge="ollama",
            backend_model=ollama_sonnet_model,
            display_name=f"Ollama Sonnet ({ollama_sonnet_model})",
            context_window=ollama_sonnet_ctx,
            max_output_tokens=8192,
        ),
        "ollama-haiku": ModelRoute(
            alias="ollama-haiku",
            bridge="ollama",
            backend_model=ollama_haiku_model,
            display_name=f"Ollama Haiku ({ollama_haiku_model})",
            context_window=ollama_haiku_ctx,
            max_output_tokens=8192,
        ),
        "ollama-gpt-oss": ModelRoute(
            alias="ollama-gpt-oss",
            bridge="ollama",
            backend_model=ollama_gptoss_model,
            display_name=f"Ollama GPT-OSS ({ollama_gptoss_model})",
            context_window=ollama_gptoss_ctx,
            max_output_tokens=8192,
        ),
        "ollama-gemma": ModelRoute(
            alias="ollama-gemma",
            bridge="ollama",
            backend_model=ollama_gemma_model,
            display_name=f"Ollama Gemma ({ollama_gemma_model})",
            context_window=ollama_gemma_ctx,
            max_output_tokens=8192,
        ),
        "siliconflow-minimax-m2.5": ModelRoute(
            alias="siliconflow-minimax-m2.5",
            bridge="siliconflow",
            backend_model="MiniMaxAI/MiniMax-M2.5",
            display_name="MiniMax M2.5 (SiliconFlow)",
            context_window=196_608,
            max_output_tokens=196_608,
        ),
        "siliconflow-kimi-k2.6": ModelRoute(
            alias="siliconflow-kimi-k2.6",
            bridge="siliconflow",
            backend_model="moonshotai/Kimi-K2.6",
            display_name="Kimi K2.6 (SiliconFlow)",
            context_window=262_144,
            max_output_tokens=262_144,
        ),
        "siliconflow-glm-5.1": ModelRoute(
            alias="siliconflow-glm-5.1",
            bridge="siliconflow",
            backend_model="zai-org/GLM-5.1",
            display_name="GLM 5.1 (SiliconFlow)",
            context_window=200_000,
            max_output_tokens=131_072,
        ),
        "fireworks-kimi-k2p6": ModelRoute(
            alias="fireworks-kimi-k2p6",
            bridge="fireworks",
            backend_model="accounts/fireworks/models/kimi-k2p6",
            display_name="Kimi K2.6 (Fireworks AI)",
            context_window=262_144,
            max_output_tokens=262_144,
        ),
        "fireworks-minimax-m2p7": ModelRoute(
            alias="fireworks-minimax-m2p7",
            bridge="fireworks",
            backend_model="accounts/fireworks/models/minimax-m2p7",
            display_name="MiniMax M2.7 (Fireworks AI)",
            context_window=204_800,
            max_output_tokens=131_072,
        ),
    }

    # When Claude Code updates and introduces brand-new model aliases (e.g.
    # claude-opus-4-8) we route them automatically via prefix matching
    # instead of requiring a manual config entry every time.
    _fallback_patterns: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"^claude-opus-4-"), "claude-opus-4-6"),
        (re.compile(r"^claude-sonnet-4-"), "claude-sonnet-4-6"),
        (re.compile(r"^claude-haiku-4-"), "claude-haiku-4-5"),
        # Claude 3.5-era models (e.g. claude-3-5-haiku-20241022 used by
        # Claude Code statusline). Route to haiku — these are tiny requests.
        (re.compile(r"^claude-3-5-"), "claude-haiku-4-5"),
    ]

    def resolve_model(self, alias: str) -> ModelRoute | None:
        """Look up a model route by exact match, then by pattern fallback."""
        if alias in self.model_routes:
            return self.model_routes[alias]

        for pattern, canonical in self._fallback_patterns:
            if not pattern.match(alias):
                continue
            if canonical not in self.model_routes:
                continue
            route = self.model_routes[canonical]
            # Derive a display name with the correct version string.
            # e.g. canonical "claude-opus-4-6" -> suffix "4-6" -> display "4.6"
            #      alias    "claude-opus-4-7" -> suffix "4-7" -> display "4.7"
            canonical_suffix = canonical.split("-", 2)[2]
            alias_suffix = alias.split("-", 2)[2]
            new_display = route.display_name.replace(
                _version_display(canonical_suffix),
                _version_display(alias_suffix),
            )
            return replace(route, alias=alias, display_name=new_display)
        return None

    # Bedrock-style variants map to the same routes
    _aliases = list(model_routes.keys())
    for alias in _aliases:
        route = model_routes[alias]
        model_routes[f"{alias}:0"] = route
        bedrock_alias = f"us.anthropic.{alias.replace('-', '_')}-v1"
        model_routes[bedrock_alias] = route
        model_routes[f"{bedrock_alias}:0"] = route


settings = Settings()
