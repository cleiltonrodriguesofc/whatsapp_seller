import pytest
from unittest.mock import MagicMock, patch
from core.infrastructure.services.supabase_storage import SupabaseStorageService

@pytest.fixture
def mock_supabase_client():
    with patch("supabase.create_client") as mock_create:
        client = MagicMock()
        mock_create.return_value = client
        yield client

def test_supabase_storage_download_image(mock_supabase_client):
    service = SupabaseStorageService()
    # Explicitly mock the chain
    mock_bucket = MagicMock()
    mock_bucket.download.return_value = b"fake_bytes"
    mock_supabase_client.storage.from_.return_value = mock_bucket
    
    result = service.download_image("test.jpg")
    assert result == b"fake_bytes"

def test_supabase_storage_get_signed_url(mock_supabase_client):
    service = SupabaseStorageService()
    mock_bucket = MagicMock()
    mock_bucket.create_signed_url.return_value = {"signedURL": "http://signed.com"}
    mock_supabase_client.storage.from_.return_value = mock_bucket
    
    result = service.get_signed_url("test.jpg")
    assert result == "http://signed.com"

def test_supabase_storage_get_signed_url_string_fallback(mock_supabase_client):
    service = SupabaseStorageService()
    mock_bucket = MagicMock()
    mock_bucket.create_signed_url.return_value = "http://signed-string.com"
    mock_supabase_client.storage.from_.return_value = mock_bucket
    
    result = service.get_signed_url("test.jpg")
    assert result == "http://signed-string.com"
