"""
AI service factory.

Returns the appropriate AI service based on available environment variables.
Priority: GEMINI_API_KEY → OPENAI_API_KEY → None.
"""

import os
import logging
from typing import Optional
from core.application.interfaces import AIService

logger = logging.getLogger(__name__)


def get_ai_service() -> Optional[AIService]:
    """
    Returns an AI service instance based on available API keys.
    Prefers Gemini if GEMINI_API_KEY is set, falls back to OpenAI.
    Returns None if no API key is configured.
    """
    # Try Gemini first
    if os.environ.get("GEMINI_API_KEY"):
        try:
            from core.infrastructure.ai.gemini_service import GeminiService
            service = GeminiService()
            logger.info("AI service initialized: Gemini (%s)", service.model)
            return service
        except Exception as e:
            logger.warning("Failed to initialize Gemini service: %s", e)

    # Fall back to OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from core.infrastructure.ai.openai_service import OpenAIService
            service = OpenAIService()
            logger.info("AI service initialized: OpenAI (%s)", service.model)
            return service
        except Exception as e:
            logger.warning("Failed to initialize OpenAI service: %s", e)

    logger.warning("No AI service available (set GEMINI_API_KEY or OPENAI_API_KEY)")
    return None
