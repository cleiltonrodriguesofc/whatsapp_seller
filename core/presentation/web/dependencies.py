"""
Shared FastAPI dependencies for all routers.
"""

import logging

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.application.services.auth_service import AuthService
from core.infrastructure.database.models import UserModel
from core.infrastructure.database.session import get_db
from core.infrastructure.database.repositories import SQLActivityRepository

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
auth_service = AuthService()

templates = Jinja2Templates(directory="core/presentation/web/templates")


def get_proxy_url(url: str) -> str:
    """
    Helper for Jinja2 templates: converts supabase:// identifiers
    to the authenticated proxy route.
    """
    if not url:
        return "/static/img/no-image.png"
    if url.startswith("supabase://"):
        return f"/storage/view/{url.replace('supabase://', '')}"
    return url


# register template helper globally
templates.env.globals["get_proxy_url"] = get_proxy_url


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> UserModel | None:
    token = request.cookies.get("access_token")
    if not token:
        return None

    payload = auth_service.decode_access_token(token)
    if not payload:
        return None

    email = payload.get("sub")
    if not email:
        return None

    return db.query(UserModel).filter(UserModel.email == email).first()


def login_required(user: UserModel = Depends(get_current_user)) -> UserModel:
    if not user:
        raise HTTPException(
            status_code=303,
            detail="Not authenticated",
            headers={"Location": "/login"},
        )
    return user


def admin_required(user: UserModel = Depends(login_required)) -> UserModel:
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required",
        )
    return user


def get_activity_repo(db: Session = Depends(get_db)) -> SQLActivityRepository:
    return SQLActivityRepository(db)
