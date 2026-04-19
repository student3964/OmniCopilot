"""
LLM Service — unified interface that wraps Groq, OpenAI, and Gemini.
Provides a consistent ChatModel regardless of backend provider.
Falls back automatically if the primary provider fails.
"""

from typing import Optional
from langchain_core.language_models import BaseChatModel
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Cache instantiated model to avoid re-creating on every request
_model_cache: dict[str, BaseChatModel] = {}


def get_llm(
    temperature: float = 0.1,
    streaming: bool = False,
) -> BaseChatModel:
    """
    Return a robust LangChain chat model with automatic fallbacks.
    Chain: Primary → OpenAI (gpt-4o) → Gemini (1.5-flash) → Groq (70b)
    """
    primary_provider = settings.llm_provider
    primary_model = settings.llm_model
    
    # Create the primary model
    primary_llm = _create_model(
        primary_provider, 
        primary_model, 
        temperature, 
        streaming
    )

    # Define the fallback chain candidates
    candidates = []
    
    # OpenAI (gpt-4o) - DISABLED TEMPORARILY DUE TO QUOTA
    # if settings.openai_api_key and primary_provider != "openai":
    #     candidates.append(_create_model("openai", "gpt-4o", temperature, streaming))
    
    # Gemini (1.5-flash) for balance
    if settings.gemini_api_key and primary_provider != "gemini":
        candidates.append(_create_model("gemini", "gemini-1.5-flash", temperature, streaming))
    
    # Groq (llama-3.3-70b) for speed/reasoning
    if settings.groq_api_key and primary_provider != "groq":
        candidates.append(_create_model("groq", "llama-3.3-70b-versatile", temperature, streaming))

    # Gemini (1.5-pro) if available as a desperate fallback
    if settings.gemini_api_key:
        candidates.append(_create_model("gemini", "gemini-1.5-pro", temperature, streaming))

    # Groq (llama-3.1-8b) as the ultimate high-availability safety net
    if settings.groq_api_key:
        candidates.append(_create_model("groq", "llama-3.1-8b-instant", temperature, streaming))

    # Combine into a single chain if candidates exist
    if candidates:
        # We handle any exception to ensure silent fallback across providers.
        return primary_llm.with_fallbacks(
            candidates,
            exceptions_to_handle=(Exception,) # Broad catch to ensure silent fallback
        )
    
    return primary_llm


def _create_model(
    provider: str, model: str, temperature: float, streaming: bool
) -> BaseChatModel:
    """Instantiate the correct LangChain model."""
    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=settings.groq_api_key,
            model=model,
            temperature=temperature,
            streaming=streaming,
            max_retries=1,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=model,
            temperature=temperature,
            streaming=streaming,
            max_retries=1,
        )

    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            google_api_key=settings.gemini_api_key,
            model=model,
            temperature=temperature,
            streaming=streaming,
            max_retries=1,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


# Deprecated: use get_llm() which now has fallbacks built-in
async def get_llm_with_fallback(
    temperature: float = 0.1,
    streaming: bool = False,
) -> BaseChatModel:
    return get_llm(temperature=temperature, streaming=streaming)
