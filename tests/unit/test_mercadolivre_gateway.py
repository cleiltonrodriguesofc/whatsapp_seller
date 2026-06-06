import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from core.infrastructure.gateways.mercadolivre_gateway import MercadoLivreGateway
from core.domain.entities import AffiliateOffer


@pytest.fixture(autouse=True)
def clear_cache():
    from core.infrastructure.gateways.mercadolivre_gateway import _ml_cache
    _ml_cache.clear()

@pytest.fixture
def gateway():
    return MercadoLivreGateway(client_id="test_token")


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
    mock_search_resp.json.return_value = {"results": [{
        "title": "Test Product",
        "original_price": 100.0,
        "price": 70.0,  # 30% discount
        "permalink": "http://ml.com/item1",
        "thumbnail": "http://img.com/item1.jpg"
    }]}
    mock_search_resp.raise_for_status = MagicMock()

    async def mock_get(url, **kwargs):
        if "search" in url:
            return mock_search_resp
        raise ValueError(f"Unexpected GET url: {url}")

    mock_client.get.side_effect = mock_get

    offers = await gateway.get_offers(categories=["notebook"], min_discount_percent=20.0)

    assert len(offers) == 1
    assert offers[0].title == "Test Product"
    assert offers[0].discount_percent == 30.0
    assert "matt_tool=test_token" in offers[0].affiliate_link


@pytest.mark.asyncio
async def test_get_offers_filters_by_discount(gateway, mock_client):
    # Mock search items
    mock_search_resp = MagicMock()
    mock_search_resp.json.return_value = {"results": [{
        "title": "Test Product",
        "original_price": 100.0,
        "price": 90.0,  # 10% discount
        "permalink": "http://ml.com/item1",
    }]}
    mock_search_resp.raise_for_status = MagicMock()

    async def mock_get(url, **kwargs):
        if "search" in url:
            return mock_search_resp
        raise ValueError(f"Unexpected GET url: {url}")

    mock_client.get.side_effect = mock_get

    offers = await gateway.get_offers(categories=["notebook"], min_discount_percent=20.0)

    # Should be empty since discount < 20%
    assert len(offers) == 0


@pytest.mark.asyncio
async def test_get_offers_search_error(gateway, mock_client):
    mock_client.get.side_effect = Exception("Search failed")
    offers = await gateway.get_offers(categories=["notebook"])
    assert len(offers) == 0
