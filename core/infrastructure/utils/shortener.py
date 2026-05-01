import os
import uuid
from sqlalchemy.orm import Session
from core.infrastructure.database.models import ShortLinkModel

def get_or_create_shortlink(db: Session, original_url: str, store_name: str) -> str:
    """creates or retrieves a short link for the given url and store."""
    BASE_URL = os.environ.get("BASE_URL", "https://whatsellerpro.com.br")
    
    link_record = db.query(ShortLinkModel).filter(
        ShortLinkModel.original_url == original_url,
        ShortLinkModel.store_name == store_name
    ).first()

    if not link_record:
        hash_id = str(uuid.uuid4())[:8]
        link_record = ShortLinkModel(
            hash_id=hash_id,
            original_url=original_url,
            store_name=store_name
        )
        db.add(link_record)
        db.commit()
    
    return f"{BASE_URL}/oferta/{store_name}/{link_record.hash_id}"
