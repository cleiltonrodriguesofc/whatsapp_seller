from unittest.mock import MagicMock, patch, AsyncMock
from core.infrastructure.services.supabase_storage import SupabaseStorageService
from core.presentation.web.routers.products import _save_uploaded_image
from core.infrastructure.database.models import UserModel
from fastapi import UploadFile
import io

@pytest.fixture
def mock_supabase_client():
    with patch("core.infrastructure.services.supabase_storage.create_client") as mock_create:
        client = MagicMock()
        mock_create.return_value = client
        yield client

@pytest.mark.asyncio
async def test_save_uploaded_image_with_user_isolation(mock_supabase_client):
    # Mock user
    user = UserModel(id=123, email="test.user+tag@gmail.com")
    
    # Mock file
    file_content = b"fake_image_bytes"
    file = UploadFile(filename="test.jpg", file=io.BytesIO(file_content))
    
    # Run the function with mocked service
    with patch("core.presentation.web.routers.products.SupabaseStorageService") as MockSvc:
        msg_instance = MockSvc.return_value
        msg_instance.upload_image = AsyncMock(return_value="http://supabase.com/user_123_test_user/uuid.jpg")

        result = await _save_uploaded_image(file, user=user)
        
        # Verify folder path generation
        # safe_email = "test_user" (from "test.user+tag".split('@')[0].replace('.','_').replace('+','_'))
        # expected folder = "user_123_test_user"
        args, kwargs = msg_instance.upload_image.call_args
        assert kwargs["folder_path"] == "user_123_test_user"
        assert result == "http://supabase.com/user_123_test_user/uuid.jpg"

@pytest.mark.asyncio
async def test_supabase_storage_upload_with_folder_path(mock_supabase_client):
    service = SupabaseStorageService(bucket_name="images")
    mock_bucket = MagicMock()
    mock_bucket.upload.return_value = {"path": "folder/name.jpg"}
    mock_supabase_client.storage.from_.return_value = mock_bucket
    
    # Test with folder_path
    await service.upload_image(b"content", "name.jpg", folder_path="my_folder")
    
    # Verify the path sent to upload
    # res = self.client.storage.from_(self.bucket_name).upload(path=unique_name, ...)
    args, kwargs = mock_bucket.upload.call_args
    path_arg = kwargs.get("path")
    assert path_arg.startswith("my_folder/")
