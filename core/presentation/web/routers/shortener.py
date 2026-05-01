from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from core.infrastructure.database.session import get_db
from core.infrastructure.database.models import ShortLinkModel

router = APIRouter(tags=["Shortener"])

@router.get("/oferta/{store_name}/{hash_id}")
async def redirect_shortlink(store_name: str, hash_id: str, db: Session = Depends(get_db)):
    """Redirects a shortlink to the original affiliate url."""
    link_record = db.query(ShortLinkModel).filter(
        ShortLinkModel.hash_id == hash_id,
        ShortLinkModel.store_name == store_name
    ).first()

    if not link_record:
        raise HTTPException(status_code=404, detail="Oferta não encontrada ou expirada.")

    # increment click count
    link_record.clicks += 1
    db.commit()

    return RedirectResponse(url=link_record.original_url)
