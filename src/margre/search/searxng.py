"""SearXNG Search provider implementation."""

import httpx
from typing import List
from margre.search.base import SearchResult, SearchProvider

class SearXNGSearchProvider(SearchProvider):
    """Search provider using a SearXNG instance."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        
    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Perform search using SearXNG API."""
        results = []
        try:
            params = {
                "q": query,
                "format": "json",
                "pageno": 1
            }
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
        except Exception as e:
            import logging
            logging.error(f"SearXNG search failed: {e}")
            
        return results
