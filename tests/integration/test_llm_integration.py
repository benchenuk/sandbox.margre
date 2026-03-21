import pytest
from langchain_openai import ChatOpenAI
from margre.llm.client import create_completion

# Constants for integration testing with local provider
BASE_URL = "http://localhost:1234/v1"
MODEL = "qwen3.5-4b-mlx-lm-nvfp4"
# LangChain ChatOpenAI expects an API key even if it is dummy for local models
API_KEY = "dummy-key-for-local"

def test_llm_direct_langchain_integration():
    """
    Test direct ChatOpenAI connection to local provider.
    This confirms the LangChain-OpenAI library can communicate with the local endpoint.
    """
    model = ChatOpenAI(
        openai_api_base=BASE_URL,
        openai_api_key=API_KEY,
        model_name=MODEL,
        temperature=0
    )
    
    try:
        response = model.invoke("You are a helpful assistant. Reply with only the word: SUCCESS")
        content = str(response.content)
        print(f"\nDirect LangChain LLM Response: {content}")
        assert content is not None
        assert "SUCCESS" in content.upper()
    except Exception as e:
        pytest.fail(f"Direct LangChain integration test failed: {e}")

def test_llm_wrapper_langchain_integration(monkeypatch):
    """
    Test the application's LLM wrapper (which now uses LangChain).
    """
    monkeypatch.setenv("MARGRE_LLM_API_KEY", API_KEY)
    
    try:
        # Wrapper now uses ChatOpenAI underneath
        response = create_completion(
            messages=[{"role": "user", "content": "Say hello!"}],
            config={"max_tokens": 5}  # LangChain 'invoke' takes kwargs like config/callbacks but for params use .bind() or pass directly if supported
        )
        print(f"\nWrapper LangChain LLM Response: {response}")
        assert isinstance(response, str)
        assert len(response) > 0
    except Exception as e:
        pytest.fail(f"Wrapper LangChain integration test failed: {e}")
