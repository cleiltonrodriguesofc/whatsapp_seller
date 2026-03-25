import pytest
import io
import base64
from PIL import Image
from unittest.mock import MagicMock, patch
from core.infrastructure.utils.image_utils import get_optimized_base64

@pytest.fixture
def sample_image_bytes():
    img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

@pytest.mark.asyncio
async def test_get_optimized_base64_data_uri(sample_image_bytes):
    # Test data:URI handling
    b64_data = base64.b64encode(sample_image_bytes).decode()
    data_uri = f"data:image/png;base64,{b64_data}"
    
    result = await get_optimized_base64(data_uri)
    assert isinstance(result, str)
    # Result should be a valid base64 (decodable)
    decoded = base64.b64decode(result)
    assert len(decoded) > 0
    
    # Verify it's a valid JPEG by opening it
    img = Image.open(io.BytesIO(decoded))
    assert img.format == "JPEG"
    assert img.mode == "RGB"

@pytest.mark.asyncio
async def test_get_optimized_base64_local_file(tmp_path, sample_image_bytes):
    # Test local file reading
    img_file = tmp_path / "test.png"
    img_file.write_bytes(sample_image_bytes)
    
    result = await get_optimized_base64(str(img_file))
    assert isinstance(result, str)
    decoded = base64.b64decode(result)
    img = Image.open(io.BytesIO(decoded))
    assert img.mode == "RGB"

@pytest.mark.asyncio
@patch("core.infrastructure.utils.image_utils.SupabaseStorageService")
async def test_get_optimized_base64_supabase(mock_storage_svc_class, sample_image_bytes):
    # Test supabase:// path
    mock_svc = mock_storage_svc_class.return_value
    mock_svc.download_image.return_value = sample_image_bytes
    
    result = await get_optimized_base64("supabase://test-img.png")
    mock_svc.download_image.assert_called_with("supabase://test-img.png")
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_get_optimized_base64_http_mock(sample_image_bytes):
    # Test http:// path with mocked httpx
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.content = sample_image_bytes
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        result = await get_optimized_base64("https://example.com/image.jpg")
        assert isinstance(result, str)
        mock_get.assert_called()
