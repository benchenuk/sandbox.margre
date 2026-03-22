"""Configuration loading from config.toml settings."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float

@dataclass
class Neo4jConfig:
    uri: str
    username: str
    password: str
    database: str

@dataclass
class SearchConfig:
    provider: str
    max_results: int
    searxng_url: str

@dataclass
class Config:
    llm: LLMConfig
    neo4j: Neo4jConfig
    search: SearchConfig

def load_config(path: str = "config.toml") -> Config:
    """Load configuration from TOML file, overriding secrets with env vars."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    
    # LLM config
    llm_data = data.get("llm", {})
    llm_api_key = os.getenv("MARGRE_LLM_API_KEY", llm_data.get("api_key", ""))
    llm_config = LLMConfig(
        base_url=llm_data.get("base_url", "http://localhost:1234/v1"),
        api_key=llm_api_key,
        model=llm_data.get("model", "default"),
        temperature=llm_data.get("temperature", 0.7),
    )
    
    # Neo4j config 
    neo4j_data = data.get("neo4j", {})
    neo4j_password = os.getenv("MARGRE_NEO4J_PASSWORD", neo4j_data.get("password", ""))
    neo4j_config = Neo4jConfig(
        uri=neo4j_data.get("uri", "bolt://localhost:7687"),
        username=neo4j_data.get("username", "neo4j"),
        password=neo4j_password,
        database=neo4j_data.get("database", "neo4j"),
    )
    
    # Search config
    search_data = data.get("search", {})
    searxng_data = search_data.get("searxng", {})
    search_config = SearchConfig(
        provider=search_data.get("provider", "ddgs"),
        max_results=search_data.get("max_results", 10),
        searxng_url=searxng_data.get("base_url", "http://localhost:8080"),
    )
    
    return Config(llm=llm_config, neo4j=neo4j_config, search=search_config)

# Global configured instance (lazy-loaded or manually initialized if needed)
_config: Config | None = None

def get_config() -> Config:
    """Return the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
