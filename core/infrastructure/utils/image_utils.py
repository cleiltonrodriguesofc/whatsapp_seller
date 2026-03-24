import io
import httpx
import base64
import os
from PIL import Image
from core.infrastructure.services.supabase_storage import SupabaseStorageService


async def get_optimized_base64(
    path_or_url: str, max_size: tuple = (400, 400), quality: int = 70
) -> str:
    """
    Downloads or reads an image, resizes it, compresses it and returns a Base64 string.
    """
    if path_or_url.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            # Mask user-agent to bypass basic CDN hotlink protections
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = await client.get(path_or_url, headers=headers)
            response.raise_for_status()
            img_data = response.content
    elif path_or_url.startswith("supabase://"):
        # Authenticated download from private Supabase bucket
        storage_svc = SupabaseStorageService()
        img_data = storage_svc.download_image(path_or_url)
        if not img_data:
            raise ValueError(f"Failed to download private image from Supabase: {path_or_url}")
    elif path_or_url.startswith("data:"):
        # It's a Base64 Data URI stored in the DB
        base64_str = path_or_url.split(",", 1)[-1]
        img_data = base64.b64decode(base64_str)
    else:
        # Resolve /static/ paths to local filesystem if necessary
        local_path = path_or_url
        if path_or_url.startswith("/static/"):
            # Map /static/ to core/presentation/web/static/
            local_path = os.path.join("core", "presentation", "web", "static", path_or_url.lstrip("/"))
        
        with open(local_path, "rb") as f:
            img_data = f.read()

    # Open image with Pillow
    img = Image.open(io.BytesIO(img_data))

    # Convert to RGB unconditionally if not already RGB to support WebP/alpha safely
    if img.mode != "RGB":
        # Create a white background first to avoid black artifacts on transparent areas
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode in ("RGBA", "LA", "P"):
            try:
                # If it has alpha, composite it
                background.paste(img, mask=img.convert("RGBA").split()[3])
            except Exception:
                pass # fallback
            img = background
        else:
            img = img.convert("RGB")

    # Resize keeping aspect ratio
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Compress and save to buffer
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)

    # Encode to Base64 (Raw for Evolution v2)
    base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return base64_data
