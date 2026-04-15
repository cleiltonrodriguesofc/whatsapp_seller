"""
Storage routes: serve private images and affiliate link cloaking.
"""

import logging
import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from core.infrastructure.database.models import UserModel
from core.infrastructure.database.session import get_db
from core.infrastructure.services.supabase_storage import SupabaseStorageService
from core.infrastructure.database.repositories import SQLProductRepository
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from core.presentation.web.dependencies import login_required
from core.presentation.web.routers.products import _save_uploaded_image

logger = logging.getLogger(__name__)

router = APIRouter(tags=["storage"])


@router.get("/storage/view/{filename:path}")
async def serve_private_image(
    filename: str,
    current_user: UserModel = Depends(login_required),
):
    """
    Securely serves images from the private Supabase bucket.
    Requires active dashboard session cookie.
    """
    storage_svc = SupabaseStorageService(bucket_name="images")
    clean_path = filename.replace("supabase://", "")

    image_bytes = storage_svc.download_image(clean_path)
    if not image_bytes:
        raise HTTPException(
            status_code=404, detail="Image not found in private storage"
        )

    ext = os.path.splitext(clean_path)[1].lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = content_types.get(ext, "image/jpeg")

    return Response(content=image_bytes, media_type=media_type)


@router.post("/campaign/upload")
async def upload_campaign_image(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(login_required),
):
    """
    Upload endpoint for campaign images (product-based campaigns).
    Uses standard product quality settings.
    """
    url = await _save_uploaded_image(file, user=current_user, quality=85, max_size=(1080, 1920))
    return {"url": url}


@router.get("/l/{product_id}", response_class=RedirectResponse)
async def redirect_to_affiliate(
    product_id: int,
    db: Session = Depends(get_db),
):
    """
    Cloaks affiliate links by redirecting through a local route.
    Also increments the click counter for analytics.
    """
    from core.infrastructure.database.repositories import SQLActivityRepository
    from core.domain.entities import ActivityLog

    product_repo = SQLProductRepository(db)
    product_repo.increment_clicks(product_id)

    product = product_repo.get_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Link not found")

    # Log click activity
    if product.user_id:
        activity_repo = SQLActivityRepository(db)
        activity_repo.save(
            ActivityLog(
                user_id=product.user_id,
                event_type="link_click",
                description=f"Novo clique no produto: {product.name}",
            )
        )

    return RedirectResponse(url=product.affiliate_link)
