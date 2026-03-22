"""DuckDuckGo Search provider implementation."""

from typing import List
from ddgs import DDGS
from margre.search.base import SearchResult, SearchProvider

import logging

logger = logging.getLogger(__name__)

class DDGSSearchProvider(SearchProvider):
    """Search provider using the DuckDuckGo Search (DDGS) library."""
    
    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Perform search using DuckDuckGo."""
        logger.info(f"SEARCH [DDGS]: Executing search for: '{query}'")
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
            logger.info(f"SEARCH [DDGS]: Found {len(results)} results.")
            for idx, res in enumerate(results):
                logger.debug(f"SEARCH [DDGS]: Result {idx+1}: {res.title} ({res.url})")
        except Exception as e:
            logger.error(f"SEARCH [DDGS]: Search failed: {e}")
            
        return results
