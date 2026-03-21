import pytest
from margre.config import load_config, Config

@pytest.fixture
def mock_config(monkeypatch):
    """Provides a mocked configuration for testing."""
    monkeypatch.setenv("MARGRE_LLM_API_KEY", "test-key")
    monkeypatch.setenv("MARGRE_NEO4J_PASSWORD", "test-pass")
    return load_config("config.toml")
