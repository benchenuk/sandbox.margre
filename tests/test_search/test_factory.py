import pytest
from margre.search import get_search_provider
from margre.search.base import SearchProvider
from margre.search.ddgs import DDGSSearchProvider
from margre.search.searxng import SearXNGSearchProvider

def test_search_provider_factory_default(mock_config):
    # Should default to DDGS from config.toml.example
    provider = get_search_provider()
    assert isinstance(provider, DDGSSearchProvider)

def test_search_provider_factory_searxng(mock_config, monkeypatch):
    # Modify mock_config specifically for this test
    mock_config.search.provider = "searxng"
    mock_config.search.searxng_url = "http://test-searxng:8080"
    
    # We patch get_config to return our manually modified mock_config
    import margre.search
    monkeypatch.setattr(margre.search, "get_config", lambda: mock_config)
    
    provider = get_search_provider()
    assert isinstance(provider, SearXNGSearchProvider)
    assert provider.base_url == "http://test-searxng:8080"
