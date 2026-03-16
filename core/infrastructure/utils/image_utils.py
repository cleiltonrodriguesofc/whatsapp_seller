import io
import httpx
import base64
from PIL import Image


async def get_optimized_base64(
    path_or_url: str, max_size: tuple = (400, 400), quality: int = 70
) -> str:
    """
    Downloads or reads an image, resizes it, compresses it and returns a Base64 string.
    """
    if path_or_url.startswith(("http://", "https://")):
        async with httpx.AsyncClient() as client:
            response = await client.get(path_or_url)
            response.raise_for_status()
            img_data = response.content
    else:
        with open(path_or_url, "rb") as f:
            img_data = f.read()

    # Open image with Pillow
    img = Image.open(io.BytesIO(img_data))

    # Convert to RGB if necessary (e.g., RGBA or P)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize keeping aspect ratio
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Compress and save to buffer
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)

    # Encode to Base64 (Raw for Evolution v2)
    base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return base64_data
