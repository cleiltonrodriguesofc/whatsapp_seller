from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from core.infrastructure.database.session import get_db
from core.infrastructure.database.models import AffiliateConfigModel, AffiliateLogModel
from core.presentation.web.dependencies import templates

router = APIRouter(prefix="/vitrine", tags=["vitrine"])

@router.get("/{store_slug}", response_class=HTMLResponse)
async def public_vitrine(request: Request, store_slug: str, db: Session = Depends(get_db)):
    """Public storefront displaying the user's latest automated offers."""
    
    # Try finding the config by Magalu slug or ML slug
    config = db.query(AffiliateConfigModel).filter(
        (AffiliateConfigModel.storefront_slug == store_slug) | 
        (AffiliateConfigModel.ml_profile_slug == store_slug)
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Vitrine não encontrada.")

    # Fetch recent sent offers
    recent_offers = (
        db.query(AffiliateLogModel)
        .filter(AffiliateLogModel.user_id == config.user_id)
        .filter(AffiliateLogModel.status == "sent")
        .filter(AffiliateLogModel.short_url != None)  # noqa: E711 — SQLAlchemy requires != None for IS NOT NULL
        .order_by(desc(AffiliateLogModel.created_at))
        .limit(50)
        .all()
    )

    # Deduplicate by original_url
    seen = set()
    unique_offers = []
    for offer in recent_offers:
        key = offer.original_url
        if key not in seen:
            seen.add(key)
            unique_offers.append(offer)

    # Limit to top 24 unique offers
    unique_offers = unique_offers[:24]

    return templates.TemplateResponse(
        request=request,
        name="vitrine.html",
        context={
            "request": request,
            "store_slug": store_slug,
            "config": config,
            "offers": unique_offers,
            "theme_color": config.theme_color or "#0088ff",
            "tagline": config.tagline or "As melhores promoções reunidas aqui!",
            "owner_avatar": config.owner_avatar_b64
        }
    )
