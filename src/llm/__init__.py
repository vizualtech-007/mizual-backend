"""
LLM Provider Factory Module
Provides a factory pattern for selecting and configuring LLM providers
"""

import os
from ..logger import logger

# Import providers
try:
    from .gemini_provider import GeminiProvider
except ImportError as e:
    logger.info(f"Warning: Gemini provider not available - import error: {e}")
    GeminiProvider = None

try:
    from .openai_provider import OpenAIProvider
except ImportError:
    logger.info("Warning: OpenAI provider not available - missing dependencies")
    OpenAIProvider = None

def get_provider():
    """
    Factory function to get the configured LLM provider based on environment variables
    
    Returns:
        BaseLLMProvider: An instance of the configured provider
    
    Raises:
        ValueError: If the configured provider is not supported or dependencies are missing
        ImportError: If required dependencies are not installed
    """
    # Check if prompt enhancement is enabled
    if not os.environ.get("ENABLE_PROMPT_ENHANCEMENT", "true").lower() in ["true", "1", "yes"]:
        logger.info("Prompt enhancement is disabled")
        return None
    
    # Get provider from environment
    provider_name = os.environ.get("LLM_PROVIDER", "gemini").lower()
    logger.info(f"Initializing LLM provider: {provider_name}")
    
    # Select provider based on configuration
    if provider_name == "gemini":
        if GeminiProvider is None:
            logger.info("Error: Gemini provider requested but dependencies not available")
            raise ImportError("Gemini dependencies not installed. Run: pip install google-generativeai")
        return GeminiProvider()
    
    elif provider_name == "openai":
        if OpenAIProvider is None:
            logger.info("Error: OpenAI provider requested but dependencies not available")
            raise ImportError("OpenAI dependencies not installed. Run: pip install openai>=1.0.0")
        return OpenAIProvider()
    
    else:
        logger.error(f"Error: Unsupported LLM provider: {provider_name}")
        raise ValueError(f"Unsupported LLM provider: {provider_name}. " 
                         f"Supported providers: gemini, openai")