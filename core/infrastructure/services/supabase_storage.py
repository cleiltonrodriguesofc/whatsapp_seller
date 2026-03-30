import os
import uuid
import logging
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseStorageService:
    def __init__(self, bucket_name: str = "produtos"):
        self.url: str = os.getenv("SUPABASE_URL", "")
        self.key: str = os.getenv("SUPABASE_KEY", "")
        self.bucket_name: str = bucket_name

        if not self.url or not self.key:
            logger.warning("Supabase credentials not fully configured.")
            self.client: Optional[Client] = None
        else:
            self.client = create_client(self.url, self.key)

    async def upload_image(self, file_content: bytes, filename: str, content_type: str = "image/jpeg") -> Optional[str]:
        """
        Uploads image bytes to Supabase Storage and returns the UNIQUE PATH (filename).
        Uses a private bucket approach where we don't expose public URLs.
        """
        if not self.client:
            logger.error("Supabase client not initialized.")
            return None

        try:
            ext = os.path.splitext(filename)[1] or ".jpg"
            unique_name = f"{uuid.uuid4()}{ext}"

            # Suapbase python client storage is sync
            res = self.client.storage.from_(self.bucket_name).upload(
                path=unique_name, file=file_content, file_options={"content-type": content_type}
            )

            # If storage service returns an error dict/response
            if hasattr(res, "get") and res.get("error"):
                logger.error("Supabase Storage Error: %s", res["error"])
                return None

            logger.info("Image uploaded to Supabase (internal path): %s", unique_name)
            # Prefix with supabase:// to identify it in the DB later
            return f"supabase://{unique_name}"

        except Exception as e:
            logger.error(
                "Exception during Supabase upload: %s. Check if bucket '%s' exists and has RLS policies.",
                e,
                self.bucket_name,
            )
            return None

    def download_image(self, path: str) -> Optional[bytes]:
        """
        Downloads raw bytes from the private bucket.
        'path' should be the internal filename (without supabase:// prefix).
        Tries the current bucket, and falls back to 'images' or 'produtos'.
        """
        if not self.client:
            return None

        clean_path = path.replace("supabase://", "")
        buckets_to_try = [self.bucket_name]
        other_bucket = "images" if self.bucket_name == "produtos" else "produtos"
        buckets_to_try.append(other_bucket)

        for bucket in buckets_to_try:
            try:
                res = self.client.storage.from_(bucket).download(clean_path)
                if res:
                    return res
            except Exception:
                continue

        logger.error("Failed to download image from Supabase path '%s' via multiple buckets", path)
        return None

    def get_signed_url(self, path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generates a temporary signed URL for viewing in the browser.
        """
        if not self.client:
            return None
        try:
            clean_path = path.replace("supabase://", "")
            res = self.client.storage.from_(self.bucket_name).create_signed_url(clean_path, expires_in)
            # res might be a string directly or a dict depending on library version
            if isinstance(res, dict):
                return res.get("signedURL")
            return res
        except Exception as e:
            logger.error("Failed to create signed URL for '%s': %s", path, e)
            return None

    def delete_image(self, path: str) -> bool:
        """
        Deletes an image from the private bucket.
        'path' should be the internal filename (with or without supabase:// prefix).
        """
        if not self.client:
            logger.error("Supabase client not initialized.")
            return False

        try:
            # Clean protocol prefix if present
            clean_path = path.replace("supabase://", "")

            # Remove from the current bucket
            res = self.client.storage.from_(self.bucket_name).remove([clean_path])

            # Supabase remove returns a list of deleted objects
            if res and len(res) > 0:
                logger.info("Image deleted from Supabase: %s", clean_path)
                return True

            logger.warning("Image not found or not deleted: %s", clean_path)
            return False

        except Exception as e:
            logger.error("Exception during Supabase delete: %s", e)
            return False
