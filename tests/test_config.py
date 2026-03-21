import os
from margre.config import load_config

def test_config_loads_defaults_and_env(monkeypatch):
    monkeypatch.setenv("MARGRE_LLM_API_KEY", "custom-api-key")
    monkeypatch.setenv("MARGRE_NEO4J_PASSWORD", "custom-neo4j-pass")
    
    config = load_config("config.toml.example")
    
    assert config.llm.base_url == "http://localhost:1234/v1"
    assert config.llm.api_key == "custom-api-key"
    assert config.neo4j.uri == "bolt://localhost:7687"
    assert config.neo4j.password == "custom-neo4j-pass"
