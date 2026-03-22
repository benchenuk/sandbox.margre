"""SearXNG Search provider implementation."""

import httpx
from typing import List
from margre.search.base import SearchResult, SearchProvider

import logging

logger = logging.getLogger(__name__)

class SearXNGSearchProvider(SearchProvider):
    """Search provider using a SearXNG instance."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        logger.info(f"SEARCH [SearXNG]: Initialised with base_url: {self.base_url}")
        
    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Perform search using SearXNG API."""
        logger.info(f"SEARCH [SearXNG]: Executing search for: '{query}'")
        results = []
        try:
            params = {
                "q": query,
                "format": "json",
                "pageno": 1
            }
            logger.debug(f"SEARCH [SearXNG]: GET {self.base_url}/search with params: {params}")
            response = httpx.get(f"{self.base_url}/search", params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            for r in data.get("results", [])[:max_results]:
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("content", ""),
                    source="SearXNG"
                ))
            logger.info(f"SEARCH [SearXNG]: Found {len(results)} results.")
        except Exception as e:
            logger.error(f"SEARCH [SearXNG]: Search failed: {e}")
            
        return results
