"""Search provider base protocol and data models."""

from typing import List, Protocol, runtime_checkable
from pydantic import BaseModel, Field

class SearchResult(BaseModel):
    """Refined search result structure."""
    title: str = Field(..., description="Title of the search result")
    url: str = Field(..., description="URL source link")
    snippet: str = Field(default="", description="Key text snippet from the result")
    source: str = Field(..., description="Name of the search provider")

@runtime_checkable
class SearchProvider(Protocol):
    """Protocol defining the standard interface for search providers."""
    
    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Perform a web search and return a list of SearchResult objects."""
        ...
