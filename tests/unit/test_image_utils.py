import pytest
import io
import base64
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image
from core.infrastructure.utils.image_utils import get_optimized_base64


@pytest.mark.asyncio
async def test_get_optimized_base64_local_file(tmp_path):
    # Create a dummy image
    img = Image.new("RGB", (100, 100), color="red")
    img_path = tmp_path / "test.jpg"
    img.save(img_path)

    base64_res = await get_optimized_base64(str(img_path))
    assert isinstance(base64_res, str)
    assert len(base64_res) > 0


@pytest.mark.asyncio
async def test_get_optimized_base64_data_uri():
    # Create a dummy image and convert to data URI
    img = Image.new("RGB", (10, 10), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    b64_img = base64.b64encode(buffer.getvalue()).decode()
    data_uri = f"data:image/jpeg;base64,{b64_img}"

    base64_res = await get_optimized_base64(data_uri)
    assert isinstance(base64_res, str)
    assert len(base64_res) > 0


@pytest.mark.asyncio
async def test_get_optimized_base64_http_url():
    img = Image.new("RGB", (10, 10), color="green")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    img_data = buffer.getvalue()

    mock_response = MagicMock()
    mock_response.content = img_data
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        base64_res = await get_optimized_base64("http://example.com/test.jpg")
        assert isinstance(base64_res, str)
        assert len(base64_res) > 0


@pytest.mark.asyncio
async def test_get_optimized_base64_supabase():
    img = Image.new("RGB", (10, 10), color="yellow")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    img_data = buffer.getvalue()

    with patch(
        "core.infrastructure.services.supabase_storage.SupabaseStorageService.download_image"
    ) as mock_download:
        mock_download.return_value = img_data
        base64_res = await get_optimized_base64("supabase://bucket/test.jpg")
        assert isinstance(base64_res, str)
        assert len(base64_res) > 0

    # We can't easily call get_optimized_base64 for bytes directly without hitting the fs or network
    # but we can test the internal logic if we refactor or just use a local file
    pass  # covered by standard use but good to note
