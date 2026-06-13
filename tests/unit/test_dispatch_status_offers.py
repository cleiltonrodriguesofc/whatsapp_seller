import pytest
from unittest.mock import AsyncMock
from core.application.use_cases.dispatch_status_offers import DispatchStatusOffers
from core.domain.entities import AffiliateOffer


@pytest.fixture
def mock_gateway():
    gateway = AsyncMock()
    return gateway


@pytest.fixture
def mock_whatsapp():
    wa = AsyncMock()
    wa.send_status.return_value = True
    return wa


@pytest.fixture
def mock_ai():
    ai = AsyncMock()
    ai.chat.return_value = "AI generated copy"
    return ai


@pytest.fixture
def use_case(mock_gateway, mock_whatsapp, mock_ai):
    return DispatchStatusOffers(
        gateway=mock_gateway,
        whatsapp=mock_whatsapp,
        ai_service=mock_ai,
        min_discount=20.0,
    )


@pytest.mark.asyncio
async def test_execute_success_with_image(use_case, mock_gateway, mock_whatsapp, mock_ai):
    offer = AffiliateOffer(
        title="Test",
        original_price=100.0,
        discount_price=50.0,
        discount_percent=50.0,
        affiliate_link="http://link",
        image_url="http://img.jpg",
        source="mercadolivre"
    )
    mock_gateway.get_offers.return_value = [offer]

    result = await use_case.execute()

    assert result["sent"] == 1
    assert result["failed"] == 0
    mock_whatsapp.send_status.assert_called_once_with(
        content="http://img.jpg",
        type="image",
        caption="AI generated copy"
    )


@pytest.mark.asyncio
async def test_execute_success_text_only(use_case, mock_gateway, mock_whatsapp, mock_ai):
    offer = AffiliateOffer(
        title="Test",
        original_price=100.0,
        discount_price=50.0,
        discount_percent=50.0,
        affiliate_link="http://link",
        source="mercadolivre"
        # No image
    )
    mock_gateway.get_offers.return_value = [offer]

    result = await use_case.execute()

    assert result["sent"] == 1
    mock_whatsapp.send_status.assert_called_once_with(
        content="AI generated copy",
        type="text",
        backgroundColor="#000000"
    )


@pytest.mark.asyncio
async def test_execute_no_offers(use_case, mock_gateway, mock_whatsapp):
    mock_gateway.get_offers.return_value = []
    
    result = await use_case.execute()
    
    assert result["sent"] == 0
    assert result["failed"] == 0
    mock_whatsapp.send_status.assert_not_called()


@pytest.mark.asyncio
async def test_execute_gateway_error(use_case, mock_gateway):
    mock_gateway.get_offers.side_effect = Exception("Gateway error")
    
    result = await use_case.execute()
    
    assert result["sent"] == 0
    assert result["failed"] == 0
    assert "error" in result


@pytest.mark.asyncio
async def test_execute_whatsapp_error(use_case, mock_gateway, mock_whatsapp):
    offer = AffiliateOffer(
        title="Test",
        original_price=100.0,
        discount_price=50.0,
        discount_percent=50.0,
        affiliate_link="http://link",
        source="mercadolivre"
    )
    mock_gateway.get_offers.return_value = [offer]
    mock_whatsapp.send_status.return_value = False
    
    result = await use_case.execute()
    
    assert result["sent"] == 0
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_fallback_copy(use_case, mock_gateway, mock_whatsapp, mock_ai):
    use_case.ai_service = None  # Force fallback
    
    offer = AffiliateOffer(
        title="Test Product",
        original_price=100.0,
        discount_price=50.0,
        discount_percent=50.0,
        affiliate_link="http://link",
        source="mercadolivre"
    )
    mock_gateway.get_offers.return_value = [offer]
    
    await use_case.execute()
    
    # Extract the caption/content passed to whatsapp
    args, kwargs = mock_whatsapp.send_status.call_args
    content = kwargs.get("content")
    
    assert "OFERTA IMPERDÍVEL" in content
    assert "Test Product" in content
    assert "R$50.00" in content
    assert "http://link" in content
