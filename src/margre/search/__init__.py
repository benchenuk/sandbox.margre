"""Search module exports and provider factory."""

from margre.config import get_config
from margre.search.base import SearchProvider, SearchResult
from margre.search.ddgs import DDGSSearchProvider
from margre.search.searxng import SearXNGSearchProvider

def get_search_provider() -> SearchProvider:
    """Return the configured search provider instance."""
    config = get_config()
    provider_type = config.search.provider.lower()
    
    if provider_type == "ddgs":
        return DDGSSearchProvider()
    elif provider_type == "searxng":
        return SearXNGSearchProvider(base_url=config.search.searxng_url)
    else:
        # Fallback to DDGS if unknown
        import logging
        logging.warning(f"Unknown search provider '{provider_type}', falling back to DDGS")
        return DDGSSearchProvider()
