import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from core.infrastructure.gateways.mercadolivre_gateway import MercadoLivreGateway
from core.domain.entities import AffiliateOffer


@pytest.fixture
def gateway():
    return MercadoLivreGateway("test_token")


@pytest.fixture
def mock_client():
    with patch("core.infrastructure.gateways.mercadolivre_gateway.httpx.AsyncClient") as c:
        instance = c.return_value
        instance.__aenter__.return_value = instance
        instance.__aexit__ = AsyncMock(return_value=False)
        yield instance


@pytest.mark.asyncio
async def test_get_offers_success(gateway, mock_client):
    # Mock search items
    mock_search_resp = MagicMock()
    mock_search_resp.json.return_value = {"results": ["item1"]}
    mock_search_resp.raise_for_status = MagicMock()

    # Mock item details
    mock_item_resp = MagicMock()
    mock_item_resp.json.return_value = {
        "title": "Test Product",
        "original_price": 100.0,
        "price": 70.0,  # 30% discount
        "permalink": "http://ml.com/item1",
        "thumbnail": "http://img.com/item1.jpg"
    }

    # Mock affiliate link
    mock_link_resp = MagicMock()
    mock_link_resp.json.return_value = {"url": "http://affiliate.ml.com/item1"}

    # Setup mock get/post
    async def mock_get(url, **kwargs):
        if "search" in url:
            return mock_search_resp
        elif "items/" in url:
            return mock_item_resp
        raise ValueError(f"Unexpected GET url: {url}")

    async def mock_post(url, **kwargs):
        if "links" in url:
            return mock_link_resp
        raise ValueError(f"Unexpected POST url: {url}")

    mock_client.get.side_effect = mock_get
    mock_client.post.side_effect = mock_post

    offers = await gateway.get_offers(min_discount_percent=20.0)

    assert len(offers) == 1
    assert offers[0].title == "Test Product"
    assert offers[0].discount_percent == 30.0
    assert offers[0].affiliate_link == "http://affiliate.ml.com/item1"
    assert offers[0].source == "mercadolivre"


@pytest.mark.asyncio
async def test_get_offers_filters_by_discount(gateway, mock_client):
    # Mock search items
    mock_search_resp = MagicMock()
    mock_search_resp.json.return_value = {"results": ["item1"]}
    
    # Mock item details (only 10% discount)
    mock_item_resp = MagicMock()
    mock_item_resp.json.return_value = {
        "title": "Test Product",
        "original_price": 100.0,
        "price": 90.0,  # 10% discount
        "permalink": "http://ml.com/item1",
    }

    async def mock_get(url, **kwargs):
        if "search" in url:
            return mock_search_resp
        elif "items/" in url:
            return mock_item_resp
        raise ValueError(f"Unexpected GET url: {url}")

    mock_client.get.side_effect = mock_get

    offers = await gateway.get_offers(min_discount_percent=20.0)

    # Should be empty since discount < 20%
    assert len(offers) == 0


@pytest.mark.asyncio
async def test_get_offers_search_error(gateway, mock_client):
    mock_client.get.side_effect = Exception("Search failed")
    offers = await gateway.get_offers()
    assert len(offers) == 0
