"""Tests for model routing and configuration."""

from seven_bridges.config import PRICING, Settings, _version_display, get_pricing


class TestVersionDisplay:
    def test_simple_version(self) -> None:
        assert _version_display("4-6") == "4.6"

    def test_version_with_date_suffix(self) -> None:
        assert _version_display("4-5-20251001") == "4.5-20251001"

    def test_single_segment(self) -> None:
        assert _version_display("5") == "5"


class TestResolveModel:
    """Tests for Settings.resolve_model pattern fallback."""

    def test_exact_match(self) -> None:
        settings = Settings()
        route = settings.resolve_model("claude-sonnet-4-6")
        assert route is not None
        assert route.alias == "claude-sonnet-4-6"
        assert route.bridge == "deepseek"

    def test_opus_fallback(self) -> None:
        settings = Settings()
        route = settings.resolve_model("claude-opus-4-8")
        assert route is not None
        assert route.alias == "claude-opus-4-8"
        assert route.bridge == "kimi"
        assert "4.8" in route.display_name
        assert "Kimi K2.6" in route.display_name

    def test_opus_future_version(self) -> None:
        settings = Settings()
        route = settings.resolve_model("claude-opus-4-99")
        assert route is not None
        assert route.alias == "claude-opus-4-99"
        assert route.bridge == "kimi"

    def test_sonnet_fallback(self) -> None:
        settings = Settings()
        route = settings.resolve_model("claude-sonnet-4-7")
        assert route is not None
        assert route.alias == "claude-sonnet-4-7"
        assert route.bridge == "deepseek"
        assert "4.7" in route.display_name
        assert "DeepSeek V4 Pro" in route.display_name

    def test_haiku_fallback_with_date_suffix(self) -> None:
        settings = Settings()
        route = settings.resolve_model("claude-haiku-4-6-20260101")
        assert route is not None
        assert route.alias == "claude-haiku-4-6-20260101"
        assert route.bridge == "deepseek"
        assert "4.6-20260101" in route.display_name

    def test_plain_claude_haiku(self) -> None:
        """claude-haiku (no version suffix) resolves to deepseek-v4-flash."""
        settings = Settings()
        route = settings.resolve_model("claude-haiku")
        assert route is not None
        assert route.alias == "claude-haiku"
        assert route.bridge == "deepseek"
        assert route.backend_model == "deepseek-v4-flash"
        assert route.context_window == 1_048_576
        assert route.max_output_tokens == 393_216
        assert "DeepSeek V4 Flash" in route.display_name

    def test_native_deepseek_v4_pro(self) -> None:
        """deepseek-v4-pro resolves directly without Anthropic naming."""
        settings = Settings()
        route = settings.resolve_model("deepseek-v4-pro")
        assert route is not None
        assert route.alias == "deepseek-v4-pro"
        assert route.bridge == "deepseek"
        assert route.backend_model == "deepseek-v4-pro"
        assert route.context_window == 1_048_576
        assert route.max_output_tokens == 393_216
        assert route.display_name == "DeepSeek V4 Pro"

    def test_native_deepseek_v4_flash(self) -> None:
        """deepseek-v4-flash resolves directly without Anthropic naming."""
        settings = Settings()
        route = settings.resolve_model("deepseek-v4-flash")
        assert route is not None
        assert route.alias == "deepseek-v4-flash"
        assert route.bridge == "deepseek"
        assert route.backend_model == "deepseek-v4-flash"
        assert route.context_window == 1_048_576
        assert route.max_output_tokens == 393_216
        assert route.display_name == "DeepSeek V4 Flash"

    def test_native_kimi_for_coding(self) -> None:
        """kimi-for-coding resolves directly without Anthropic naming."""
        settings = Settings()
        route = settings.resolve_model("kimi-for-coding")
        assert route is not None
        assert route.alias == "kimi-for-coding"
        assert route.bridge == "kimi"
        assert route.backend_model == "kimi-for-coding"
        assert route.context_window == 262_144
        assert route.max_output_tokens == 32_768
        assert route.display_name == "Kimi K2.7 Code"

    def test_unknown_model_returns_none(self) -> None:
        settings = Settings()
        assert settings.resolve_model("claude-unknown-9-9") is None
        assert settings.resolve_model("not-a-model") is None
        assert settings.resolve_model("") is None


class TestGetPricing:
    """Tests for get_pricing() resolution chain."""

    def test_global_default_when_no_args(self) -> None:
        pricing = get_pricing()
        assert pricing["input"] == 0.40
        assert pricing["output"] == 4.00
        assert pricing["cache_read"] == 0.15

    def test_global_default_when_unknown_backend(self) -> None:
        pricing = get_pricing(backend="nonexistent")
        assert pricing["input"] == 0.40
        assert pricing["output"] == 4.00

    def test_global_default_when_none_backend(self) -> None:
        pricing = get_pricing(backend=None, model_alias=None)
        assert pricing["input"] == 0.40

    def test_backend_wildcard_match(self) -> None:
        pricing = get_pricing(backend="deepseek")
        assert pricing["input"] == 0.14
        assert pricing["output"] == 1.10
        assert pricing["cache_read"] == 0.014

    def test_backend_wildcard_with_unknown_model(self) -> None:
        """When model isn't explicitly listed, fall back to backend wildcard."""
        pricing = get_pricing(backend="deepseek", model_alias="unknown-model")
        assert pricing["input"] == 0.14

    def test_ollama_is_free(self) -> None:
        pricing = get_pricing(backend="ollama")
        assert pricing["input"] == 0.0
        assert pricing["output"] == 0.0
        assert pricing["cache_read"] == 0.0

    def test_model_specific_pricing_exists_in_structure(self) -> None:
        """Verify that the PRICING structure supports per-model entries."""
        # If a model-specific entry exists, it should be found
        assert "deepseek" in PRICING
        assert "*" in PRICING["deepseek"]

    def test_mimo_pricing_pro(self) -> None:
        pricing = get_pricing(backend="mimo", model_alias="mimo-v2.5-pro")
        assert pricing["input"] == 0.40
        assert pricing["output"] == 4.00
        assert pricing["cache_read"] == 0.15

    def test_mimo_pricing_base(self) -> None:
        pricing = get_pricing(backend="mimo", model_alias="mimo-v2.5")
        assert pricing["input"] == 0.14
        assert pricing["output"] == 1.10
        assert pricing["cache_read"] == 0.014
