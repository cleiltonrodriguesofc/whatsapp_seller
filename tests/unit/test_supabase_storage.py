import pytest
from unittest.mock import MagicMock, patch
from core.infrastructure.services.supabase_storage import SupabaseStorageService

@pytest.fixture
def mock_env():
    with patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"}):
        yield

@patch("core.infrastructure.services.supabase_storage.create_client")
def test_supabase_init(mock_create_client, mock_env):
    service = SupabaseStorageService()
    assert service.url == "https://test.supabase.co"
    assert service.key == "test-key"
    mock_create_client.assert_called_with("https://test.supabase.co", "test-key")

# Since upload_image is async, let's use a proper async test container
@pytest.mark.asyncio
@patch("core.infrastructure.services.supabase_storage.create_client")
async def test_supabase_upload_image_async(mock_create_client, mock_env):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    service = SupabaseStorageService()
    
    mock_bucket = mock_client.storage.from_.return_value
    mock_bucket.upload.return_value = {"path": "test.jpg"}
    
    path = await service.upload_image(b"fake-content", "test.jpg")
    assert path is not None
    assert path.startswith("supabase://")
    mock_client.storage.from_.assert_called_with("produtos")

@patch("core.infrastructure.services.supabase_storage.create_client")
def test_supabase_download_image(mock_create_client, mock_env):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    service = SupabaseStorageService()
    
    mock_bucket = mock_client.storage.from_.return_value
    mock_bucket.download.return_value = b"image-data"
    
    data = service.download_image("supabase://test.jpg")
    assert data == b"image-data"
    mock_bucket.download.assert_called_with("test.jpg")

@patch("core.infrastructure.services.supabase_storage.create_client")
def test_supabase_get_signed_url(mock_create_client, mock_env):
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    service = SupabaseStorageService()
    
    mock_bucket = mock_client.storage.from_.return_value
    mock_bucket.create_signed_url.return_value = {"signedURL": "https://signed.url"}
    
    url = service.get_signed_url("test.jpg")
    assert url == "https://signed.url"
