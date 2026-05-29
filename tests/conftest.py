"""Shared test fixtures."""

import pytest

from seven_bridges.config import settings


@pytest.fixture(autouse=True)
def _patch_api_keys(monkeypatch):
    """Ensure all backend API keys are set so _get_bridge doesn't 503.

    Real HTTP is mocked per-test by respx; these keys just let the bridge
    instantiation succeed.
    """
    if not settings.deepseek_api_key:
        monkeypatch.setattr(settings, "deepseek_api_key", "test-ds-key")
    if not settings.kimi_api_key:
        monkeypatch.setattr(settings, "kimi_api_key", "test-kimi-key")
    if not settings.siliconflow_api_key:
        monkeypatch.setattr(settings, "siliconflow_api_key", "test-sf-key")
    if not settings.fireworks_api_key:
        monkeypatch.setattr(settings, "fireworks_api_key", "test-fw-key")
    if not settings.mimo_api_key:
        monkeypatch.setattr(settings, "mimo_api_key", "test-mimo-key")
