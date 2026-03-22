"""DuckDuckGo Search provider implementation."""

from typing import List
from ddgs import DDGS
from margre.search.base import SearchResult, SearchProvider

class DDGSSearchProvider(SearchProvider):
    """Search provider using the DuckDuckGo Search (DDGS) library."""
    
    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Perform search using DuckDuckGo."""
        results = []
        try:
            with DDGS() as ddgs:
                ddgs_results = ddgs.text(query, max_results=max_results)
                for r in ddgs_results:
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        url=r.get("href", ""),
                        snippet=r.get("body", ""),
                        source="DDGS"
                    ))
        except Exception as e:
            # Re-raise or handle as appropriate for MARGRe's error boundary
            import logging
            logging.error(f"DDGS search failed: {e}")
            
        return results
