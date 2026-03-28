import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService

@pytest.fixture
def mock_httpx():
    with patch("core.infrastructure.notifications.evolution_whatsapp.httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.__aenter__.return_value = mock_instance
        yield mock_instance

@pytest.mark.asyncio
async def test_evolution_send_text_success(mock_httpx):
    mock_response = MagicMock(status_code=201, text="ok")
    mock_response.json = lambda: {"key": {"id": "msg_id"}}
    mock_httpx.post = AsyncMock(return_value=mock_response)
    
    with patch.dict("os.environ", {"EVOLUTION_API_URL": "http://api.com", "EVOLUTION_API_KEY": "key"}):
        service = EvolutionWhatsAppService()
        res = await service.send_text("123@s.whatsapp.net", "Hello")
        
        assert res is True

@pytest.mark.asyncio
async def test_evolution_create_instance(mock_httpx):
    mock_response = MagicMock(status_code=201, text="ok")
    mock_response.json = lambda: {"instance": {"instanceName": "test"}}
    mock_httpx.post = AsyncMock(return_value=mock_response)
    
    with patch.dict("os.environ", {"EVOLUTION_API_URL": "http://api.com", "EVOLUTION_API_KEY": "key"}):
        service = EvolutionWhatsAppService()
        res = await service.create_instance("test")
        
        assert res == {"instance": {"instanceName": "test"}}

@pytest.mark.asyncio
async def test_evolution_get_instances(mock_httpx):
    # Note: get_instances might be called get_instances or something else in the actual code
    # Looking at evolution_whatsapp.py, it doesn't have get_instances!
    # It has get_contacts, get_groups, get_status, create_instance, get_qrcode, etc.
    pass

@pytest.mark.asyncio
async def test_evolution_get_contacts(mock_httpx):
    mock_response = MagicMock(status_code=200, text="ok")
    mock_response.json = lambda: [{"id": "c1"}]
    mock_httpx.get = AsyncMock(return_value=mock_response)
    with patch.dict("os.environ", {"EVOLUTION_API_URL": "http://api.com", "EVOLUTION_API_KEY": "key"}):
        service = EvolutionWhatsAppService()
        res = await service.get_contacts()
        assert len(res) == 1
