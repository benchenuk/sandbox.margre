"""OpenAI-compatible (OpenAILike) LLM client via LangChain."""

from langchain_openai import ChatOpenAI
from margre.config import get_config

_model: ChatOpenAI | None = None

def get_model() -> ChatOpenAI:
    """Get or initialize the LangChain ChatOpenAI model, configured for OpenAI-compatible endpoints."""
    global _model
    if _model is None:
        config = get_config()
        # ChatOpenAI acts as the 'OpenAILike' interface in LangChain
        _model = ChatOpenAI(
            openai_api_base=config.llm.base_url,
            openai_api_key=config.llm.api_key or "dummy-key-for-local",
            model_name=config.llm.model,
            temperature=config.llm.temperature,
            streaming=True
        )
    return _model

def create_completion(messages: list[dict], **kwargs) -> str:
    """Generate a chat completion response using LangChain's ChatOpenAI."""
    model = get_model()
    
    # Standard LangChain invocation
    # and map dict-based messages to BaseMessage if needed, but invoke works with list of messages too
    response = model.invoke(messages, **kwargs)
    return str(response.content)
