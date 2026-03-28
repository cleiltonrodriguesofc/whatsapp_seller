"""
Product routes: list, create, edit, delete products.
"""
import io
import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from PIL import Image
from sqlalchemy.orm import Session

from core.domain.entities import Product
from core.infrastructure.database.models import UserModel
from core.infrastructure.database.repositories import SQLProductRepository
from core.infrastructure.database.session import get_db
from core.infrastructure.services.supabase_storage import SupabaseStorageService
from core.presentation.web.dependencies import login_required, templates

logger = logging.getLogger(__name__)

router = APIRouter(tags=["products"])

_ALLOWED_IMAGE_TYPES = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


async def _save_uploaded_image(
    image_file: UploadFile,
    quality: int = 85,
    max_size: tuple = (1080, 1920),
    bucket: str = "produtos"
) -> str:
    """
    Validates, resizes and uploads an image to Supabase Storage.
    Returns the internal supabase:// path, or a local fallback path.
    """
    raw = await image_file.read()

    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large. Maximum allowed size is {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
    except Exception:
        raise HTTPException(
            status_code=415,
            detail="Invalid image file. Only JPEG, PNG, WEBP and GIF are accepted.",
        )

    img = Image.open(io.BytesIO(raw))
    fmt = img.format
    if fmt not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image format '{fmt}'. Allowed: {', '.join(_ALLOWED_IMAGE_TYPES)}.",
        )

    unique_filename = f"{uuid.uuid4()}.jpg"

    try:
        img = Image.open(io.BytesIO(raw))
        if img.mode != "RGB":
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode in ("RGBA", "LA", "P"):
                try:
                    background.paste(img, mask=img.convert("RGBA").split()[3])
                except Exception:
                    pass
                img = background
            else:
                img = img.convert("RGB")

        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        optimized_buffer = io.BytesIO()
        img.save(optimized_buffer, format="JPEG", quality=quality, optimize=True)
        raw = optimized_buffer.getvalue()

    except Exception as e:
        logger.warning("image optimization failed, using raw: %s", e)

    try:
        storage_svc = SupabaseStorageService(bucket_name=bucket)
        public_url = await storage_svc.upload_image(
            file_content=raw,
            filename=unique_filename,
            content_type="image/jpeg",
        )
    except Exception as e:
        logger.error("supabase storage service error: %s", e)
        public_url = None

    if not public_url:
        logger.error("supabase upload failed, falling back to local storage (ephemeral)")
        upload_dir = os.path.join("core", "presentation", "web", "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        upload_path = os.path.join(upload_dir, unique_filename)
        img.save(upload_path)
        return f"/static/uploads/{unique_filename}"

    logger.info("image uploaded to supabase: %s", public_url)
    return public_url


@router.get("/products", response_class=HTMLResponse)
async def list_products(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    product_repo = SQLProductRepository(db)
    products = product_repo.list_all(user_id=current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={"products": products, "user": current_user, "title": "Products"},
    )


@router.post("/products/new")
async def create_product(
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    affiliate_link: str = Form(...),
    image_url: str = Form(None),
    category: str = Form(None),
    image_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    product_repo = SQLProductRepository(db)

    final_image_url = image_url
    if image_file and image_file.filename:
        final_image_url = await _save_uploaded_image(image_file)

    product = Product(
        name=name,
        description=description,
        price=price,
        affiliate_link=affiliate_link,
        image_url=final_image_url,
        category=category,
        user_id=current_user.id,
    )
    product_repo.save(product)
    return RedirectResponse(url="/products", status_code=303)


@router.get("/products/edit/{product_id}", response_class=HTMLResponse)
async def edit_product_form(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    product_repo = SQLProductRepository(db)
    product = product_repo.get_by_id(product_id, user_id=current_user.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return templates.TemplateResponse(
        request=request,
        name="edit_product.html",
        context={"product": product, "user": current_user},
    )


@router.post("/products/edit/{product_id}")
async def update_product(
    product_id: int,
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    affiliate_link: str = Form(...),
    image_url: str = Form(None),
    category: str = Form(None),
    image_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    product_repo = SQLProductRepository(db)
    product = product_repo.get_by_id(product_id, user_id=current_user.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    final_image_url = image_url or product.image_url
    if image_file and image_file.filename:
        final_image_url = await _save_uploaded_image(image_file)
    elif final_image_url and final_image_url.startswith("/static/uploads/"):
        # lazy-migrate legacy local images to supabase
        local_path = os.path.join(
            "core", "presentation", "web", "static", "uploads",
            final_image_url.split("/")[-1],
        )
        if os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    content = f.read()
                storage_svc = SupabaseStorageService()
                try:
                    img = Image.open(io.BytesIO(content))
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    img.thumbnail((1080, 1920), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=85, optimize=True)
                    content = buffer.getvalue()
                except Exception:
                    pass

                migrated_url = await storage_svc.upload_image(
                    file_content=content,
                    filename=local_path,
                    content_type="image/jpeg",
                )
                if migrated_url:
                    final_image_url = migrated_url
                    logger.info("lazy-migrated legacy image to supabase: %s", migrated_url)
            except Exception as e:
                logger.error("lazy migration failed: %s", e)

    product.name = name
    product.description = description
    product.price = price
    product.affiliate_link = affiliate_link
    product.category = category
    product.image_url = final_image_url

    product_repo.save(product)
    return RedirectResponse(url="/products", status_code=303)


@router.post("/products/delete/{product_id}")
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    product_repo = SQLProductRepository(db)
    success = product_repo.delete(product_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Product not found or not owned by user"
        )
    return RedirectResponse(url="/products", status_code=303)
