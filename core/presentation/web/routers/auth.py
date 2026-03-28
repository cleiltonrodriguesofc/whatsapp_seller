"""
Authentication routes: login, register, logout.
"""
import logging
import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from core.infrastructure.database.models import InstanceModel, UserModel
from core.infrastructure.database.session import get_db
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService
from core.presentation.web.dependencies import auth_service, templates

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="login.html", context={"title": "Login"}
    )


@router.post("/login")
@limiter.limit("10/minute")
async def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.email == username).first()
    if not user or not auth_service.verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid email or password", "title": "Login"},
        )

    access_token = auth_service.create_access_token(data={"sub": user.email})
    response = RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)
    is_prod = os.environ.get("RENDER") == "true"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
    )
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="register.html", context={"title": "Register"}
    )


@router.post("/register")
@limiter.limit("5/minute")
async def register_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    business_name: str = Form(...),
    db: Session = Depends(get_db),
):
    existing_user = db.query(UserModel).filter(UserModel.email == email).first()
    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Email already registered", "title": "Register"},
        )

    new_user = UserModel(
        email=email, hashed_password=auth_service.hash_password(password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # provision whitatsapp instance
    try:
        instance_name = (
            business_name.lower().replace(" ", "_") + "_" + str(new_user.id)
        )
        whatsapp_service = EvolutionWhatsAppService()
        instance_data = await whatsapp_service.create_instance(
            instance_name, display_name=business_name
        )

        if instance_data and isinstance(instance_data, dict):
            hash_data = instance_data.get("hash")
            if isinstance(hash_data, dict):
                apikey = hash_data.get("apikey")
            elif isinstance(hash_data, str):
                apikey = hash_data
            else:
                apikey = instance_data.get("apikey")

            new_instance = InstanceModel(
                user_id=new_user.id,
                name=instance_name,
                display_name=business_name,
                apikey=apikey,
            )
            db.add(new_instance)
            db.commit()
        else:
            logger.warning(
                "evolution api returned non-dict response for %s: %s",
                instance_name,
                type(instance_data),
            )
    except Exception as e:
        logger.error(
            "post-registration instance provisioning failed: %s", e, exc_info=True
        )

    access_token = auth_service.create_access_token(data={"sub": new_user.email})
    response = RedirectResponse(url="/whatsapp/connect", status_code=HTTP_303_SEE_OTHER)
    is_prod = os.environ.get("RENDER") == "true"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response
