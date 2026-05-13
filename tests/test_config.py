"""Tests for model routing and configuration."""

from seven_bridges.config import Settings, _version_display


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

    def test_unknown_model_returns_none(self) -> None:
        settings = Settings()
        assert settings.resolve_model("claude-unknown-9-9") is None
        assert settings.resolve_model("not-a-model") is None
        assert settings.resolve_model("") is None
