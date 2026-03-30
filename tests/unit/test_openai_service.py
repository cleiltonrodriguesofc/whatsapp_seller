import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.infrastructure.ai.openai_service import OpenAIService


@pytest.mark.asyncio
async def test_openai_service_chat_success():
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("openai.resources.chat.completions.AsyncCompletions.create", new_callable=AsyncMock) as mock_create:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "AI Response"
            mock_create.return_value = mock_response

            service = OpenAIService()
            res = await service.chat("Hello")
            assert res == "AI Response"


@pytest.mark.asyncio
async def test_openai_service_chat_failure():
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("openai.resources.chat.completions.AsyncCompletions.create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("OpenAI Error")

            service = OpenAIService()
            with pytest.raises(Exception, match="OpenAI Error"):
                await service.chat("Hello")
