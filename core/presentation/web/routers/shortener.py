from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from core.infrastructure.database.session import get_db
from core.infrastructure.database.models import ShortLinkModel, AffiliateLogModel, AffiliateConfigModel
from core.presentation.web.dependencies import templates

router = APIRouter(tags=["Shortener"])

from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

@router.get("/oferta/{store_name}/{hash_id}", response_class=HTMLResponse)
async def redirect_shortlink(store_name: str, hash_id: str, request: Request, db: Session = Depends(get_db)):
    """Redirects a shortlink to the original affiliate url via an interstitial page."""
    link_record = db.query(ShortLinkModel).filter(
        ShortLinkModel.hash_id == hash_id,
        ShortLinkModel.store_name == store_name
    ).first()

    if not link_record:
        raise HTTPException(status_code=404, detail="Oferta não encontrada ou expirada.")

    # increment click count
    link_record.clicks += 1
    db.commit()

    # Log request details (IP, user-agent)
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    logger.info(f"Shortlink click: {hash_id} by IP {client_ip} (User-Agent: {user_agent})")

    # Security: Prevent Open Redirect
    allowed_domains = [
        "magazinevoce.com.br", "magazineluiza.com.br",
        "mercadolivre.com.br", "mercadolibre.com",
        "magalu.com",
    ]
    parsed_url = urlparse(link_record.original_url)
    if not any(parsed_url.netloc.endswith(domain) for domain in allowed_domains):
        logger.warning(f"Blocked open redirect attempt to: {link_record.original_url}")
        raise HTTPException(status_code=400, detail="URL de destino não autorizada.")

    # Try to find the user to show their avatar
    owner_avatar = ""
    log_record = db.query(AffiliateLogModel).filter(AffiliateLogModel.original_url == link_record.original_url).first()
    if log_record:
        config = db.query(AffiliateConfigModel).filter(AffiliateConfigModel.user_id == log_record.user_id).first()
        if config and config.owner_avatar_b64:
            owner_avatar = config.owner_avatar_b64

    store_label = "Mercado Livre" if "mercadolivre" in store_name.lower() or "ml" in store_name.lower() else "Magalu"

    return templates.TemplateResponse(
        "interstitial.html",
        {
            "request": request,
            "destination_url": link_record.original_url,
            "owner_avatar": owner_avatar,
            "store_label": store_label
        }
    )
