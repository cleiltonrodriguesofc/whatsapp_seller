import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import (
    Depends,
    File,
    FastAPI,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    Response,
    FileResponse
)
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image
import io
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from core.application.services.auth_service import AuthService
from core.application.use_cases.sales_agent_campaign import SalesAgentCampaignUseCase
from core.application.use_cases.schedule_campaign import ScheduleCampaign
from core.application.use_cases.save_status_draft import SaveStatusCampaignDraft
from core.application.use_cases.schedule_status_campaign import ScheduleStatusCampaign

from core.domain.entities import (
    Campaign,
    CampaignStatus as DomainCampaignStatus,
    Product,
    StatusCampaign,
    StatusCampaignStatus as DomainStatusCampaignStatus,
)
from core.infrastructure.ai.openai_service import OpenAIService
from core.infrastructure.database.models import (
    Base,
    CampaignModel,
    CampaignStatus as ModelCampaignStatus,
    StatusCampaignModel,
    StatusCampaignStatus as ModelStatusCampaignStatus,
    InstanceModel,
    ProductModel,
    UserModel,
    campaign_groups,
)
from core.infrastructure.database.repositories import (
    SQLCampaignRepository,
    SQLProductRepository,
    SQLTargetRepository,
    SQLStatusCampaignRepository,
)
from core.infrastructure.database.session import SessionLocal, engine, get_db
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService
from core.infrastructure.services.supabase_storage import SupabaseStorageService

# Load environment variables
load_dotenv()

# configure module-level logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# rate limiter setup
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="WhatSeller Pro", debug=True)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security Middlewares
# Run auto-migrations on startup
try:
    with engine.connect() as conn:
        from sqlalchemy import text
        # check if click_count exists
        res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'products' AND column_name = 'click_count';"))
        if not res.fetchone():
            conn.execute(text("ALTER TABLE products ADD COLUMN click_count INTEGER DEFAULT 0;"))
            conn.commit()
            print("Auto-migration: Added 'click_count' to products table.")
except Exception as e:
    print(f"Auto-migration failed: {e}")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https: https://wjgxuhozvbybpojhvqzf.supabase.co; "
        "connect-src 'self' https:;"
    )
    # Strict-Transport-Security (HSTS) - only for production
    if os.environ.get("RENDER"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health")
async def health_check():
    """health check endpoint used by render and other platforms."""
    return {"status": "ok"}

# Security
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
auth_service = AuthService()

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


# Mount static files and templates
app.mount(
    "/static", StaticFiles(directory="core/presentation/web/static"), name="static"
)
templates = Jinja2Templates(directory="core/presentation/web/templates")
templates.env.globals["get_proxy_url"] = get_proxy_url
app.state.templates = templates


async def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None

    payload = auth_service.decode_access_token(token)
    if not payload:
        return None

    email = payload.get("sub")
    if not email:
        return None

    user = db.query(UserModel).filter(UserModel.email == email).first()
    return user


def login_required(user: UserModel = Depends(get_current_user)):
    if not user:
        raise HTTPException(
            status_code=303, detail="Not authenticated", headers={"Location": "/login"}
        )
    return user


@app.on_event("startup")
async def startup_event():
    # start the background campaign scheduler
    asyncio.create_task(campaign_scheduler_loop())


# ── storage proxy ──────────────────────────────────────────────────────────────

# ── storage proxy ──────────────────────────────────────────────────────────────
# (Redundant endpoints removed, consolidated at end of file)


async def execute_campaign_task(campaign_id: int):
    """
    Runs a campaign in the background using its own database session.
    """
    db = SessionLocal()
    try:
        logger.info("Executing background task for campaign ID %s", campaign_id)
        campaign_repo = SQLCampaignRepository(db)
        
        # We must re-fetch the model inside this new thread/task DB session
        model = db.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
        if not model:
            logger.error("Campaign %s not found in background task", campaign_id)
            return

        domain_campaign = campaign_repo._to_entity(model)
        await send_campaign(domain_campaign, db)
    except Exception as e:
        logger.error("Error in background campaign task for %s: %s", campaign_id, e, exc_info=True)
    finally:
        db.close()

async def campaign_scheduler_loop():
    """
    Background task to check and send scheduled/recurring campaigns.
    """
    while True:
        db = SessionLocal()
        try:
            now = datetime.now()  # Fix: use local naive datetime because user inputs are BRT
            current_time_str = now.strftime("%H:%M")
            current_day_str = now.strftime("%a").lower()  # "mon", "tue", etc.

            # 1. Handle One-off Campaigns
            one_off_campaigns = (
                db.query(CampaignModel)
                .filter(
                    CampaignModel.status == ModelCampaignStatus.SCHEDULED,
                    ~CampaignModel.is_recurring,
                    CampaignModel.scheduled_at <= now,
                )
                .all()
            )

            for campaign_model in one_off_campaigns:
                logger.info("scheduling one-off campaign task: %s", campaign_model.title)
                # Mark it as SENDING immediately to prevent duplicate runs
                campaign_model.status = ModelCampaignStatus.SENDING
                campaign_model.last_run_at = now
                db.add(campaign_model)
                db.commit()
                
                asyncio.create_task(execute_campaign_task(campaign_model.id))

            # Iterate through all recurring campaigns
            recurring_campaigns = (
                db.query(CampaignModel)
                .filter(
                    CampaignModel.is_recurring,
                    CampaignModel.status != ModelCampaignStatus.FAILED,
                )
                .all()
            )

            for campaign_model in recurring_campaigns:
                if not campaign_model.recurrence_days:
                    continue
                if current_day_str not in campaign_model.recurrence_days.lower():
                    continue

                # Check for target_config (SaaS) or traditional send_time
                target_config = {}
                if campaign_model.target_config:
                    try:
                        target_config = json.loads(campaign_model.target_config)
                    except Exception as exc:
                        logger.warning("failed to parse target_config for campaign %s: %s", campaign_model.id, exc)

                send_times = [
                    t.strip()
                    for t in (campaign_model.send_time or "").split(",")
                    if t.strip()
                ]

                # 1. Traditional Single-Time Trigger
                if current_time_str in send_times:
                    if (
                        not campaign_model.last_run_at
                        or campaign_model.last_run_at.strftime("%Y-%m-%d %H:%M")
                        != now.strftime("%Y-%m-%d %H:%M")
                    ):
                        logger.info(
                            "executing multi-time campaign: %s at %s",
                            campaign_model.title,
                            current_time_str,
                        )
                        campaign_model.status = ModelCampaignStatus.SENDING
                        campaign_model.last_run_at = now
                        db.add(campaign_model)
                        db.commit()
                        asyncio.create_task(execute_campaign_task(campaign_model.id))

                # 2. Granular Target-Config Triggers (v3)
                for target_type, t_schedule in target_config.items():
                    # For simplicity, if t_schedule is a time "HH:MM", trigger it
                    # If it's a list ["HH:MM", "HH:MM"], trigger any
                    scheduled_times = (
                        [t_schedule] if isinstance(t_schedule, str) else t_schedule
                    )
                    if current_time_str in scheduled_times:
                        # We would need target-specific tracking to avoid duplicates if
                        # different targets have different times. For now, we reuse last_run_at
                        # but ideally we'd tracking per target_type + campaign + day.
                        if (
                            not campaign_model.last_run_at
                            or campaign_model.last_run_at.strftime("%Y-%m-%d %H:%M")
                            != now.strftime("%Y-%m-%d %H:%M")
                        ):
                            logger.info(
                                "executing granular campaign (%s): %s at %s",
                                target_type,
                                campaign_model.title,
                                current_time_str,
                            )
                            campaign_model.status = ModelCampaignStatus.SENDING
                            campaign_model.last_run_at = now
                            db.add(campaign_model)
                            db.commit()
                            # Here we should optionally filter domain_campaign.target_groups by type
                            asyncio.create_task(execute_campaign_task(campaign_model.id))

        except Exception as e:
            logger.error("error in scheduler loop: %s", e, exc_info=True)
        finally:
            db.close()

        await asyncio.sleep(60)  # check every minute


async def send_campaign(campaign: Campaign, db: Session):
    """
    Sends the campaign messages via WhatsApp with humanized behavior and user-specific instance.
    """
    from core.application.services.humanized_sender import HumanizedSender
    from core.infrastructure.database.models import InstanceModel

    logger.info("sending campaign: %s", campaign.title)
    campaign_repo = SQLCampaignRepository(db)

    # 1. Resolve User Instance
    instance_model = (
        db.query(InstanceModel)
        .filter(InstanceModel.user_id == campaign.user_id)
        .first()
    )
    instance_name = instance_model.name if instance_model else None

    # Fallback to default if no user instance found (or if testing)
    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_name,
        apikey=instance_model.apikey if instance_model else None
    )
    humanized_sender = HumanizedSender(whatsapp_service)

    # Update status to SENDING
    campaign.status = DomainCampaignStatus.SENDING
    campaign_repo.save(campaign)

    # 2. Prepare Content
    base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
    cloaked_link = f"{base_url}/l/{campaign.product.id}"
    
    message = campaign.custom_message
    if not message:
        message = f"Confira nosso produto: {campaign.product.name} - {cloaked_link}"
    else:
        # Replacement pattern if user uses placeholders (optional but good)
        message = message.replace("{{link}}", cloaked_link)
        message = message.replace(campaign.product.affiliate_link, cloaked_link)

    # 3. Execute Humanized Send
    # We use target_groups for now, but in the future we might filter by target_config
    try:
        success = await humanized_sender.send_campaign_humanized(
            targets=campaign.target_groups,
            content=message,
            media_url=campaign.product.image_url,
        )

        # Final update
        campaign.status = (
            DomainCampaignStatus.SENT if success else DomainCampaignStatus.FAILED
        )
    except Exception as e:
        logger.error("error during humanized campaign send: %s", e, exc_info=True)
        campaign.status = DomainCampaignStatus.FAILED

    campaign.sent_at = datetime.utcnow()
    campaign_repo.save(campaign)
    logger.info("campaign '%s' finished with status: %s", campaign.title, campaign.status.name)


@app.head("/", include_in_schema=False)
async def home_head():
    return {}

@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_current_user),
):
    if not current_user:
        return templates.TemplateResponse(request=request, name="landing.html", context={"title": "Welcome"})

    campaign_repo = SQLCampaignRepository(db)
    campaigns = campaign_repo.list_all(user_id=current_user.id)

    # Calculate real metrics
    total_campaigns = len(campaigns)
    
    # Count individual messages (targets) for sent campaigns
    sent_count = (
        db.query(campaign_groups.c.campaign_id)
        .join(CampaignModel, CampaignModel.id == campaign_groups.c.campaign_id)
        .filter(
            CampaignModel.user_id == current_user.id,
            CampaignModel.status == ModelCampaignStatus.SENT,
        )
        .count()
    )
    
    ai_count = (
        db.query(CampaignModel)
        .filter(
            CampaignModel.user_id == current_user.id,
            CampaignModel.is_ai_generated,
        )
        .count()
    )

    # Click metrics for dashboard
    products = db.query(ProductModel).filter(ProductModel.user_id == current_user.id).all()
    total_clicks = sum(p.click_count or 0 for p in products)

    # Get user's instances
    instances = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).all()
    )

    # For the status indicator, we check the first one or a default one
    wa_connected = False
    wa_status = "not_found"
    if instances:
        whatsapp_service = EvolutionWhatsAppService(
            instance=instances[0].name,
            apikey=instances[0].apikey
        )
        status_data = await whatsapp_service.get_status()
        wa_connected = status_data.get("connected", False)
        wa_status = status_data.get("status", "unknown")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "campaigns": campaigns,
            "user": current_user,
            "total_campaigns": total_campaigns,
            "sent_count": sent_count,
            "ai_count": ai_count,
            "total_clicks": total_clicks,
            "wa_connected": wa_connected,
            "wa_status": wa_status,
            "instances": instances,
            "title": "Dashboard",
        },
    )


@app.post("/campaign/delete/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLCampaignRepository(db)
    success = campaign_repo.delete(campaign_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return RedirectResponse(url="/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"title": "Login"})


@app.post("/login")
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
            request=request, name="login.html", context={"error": "Invalid email or password", "title": "Login"}
        )

    access_token = auth_service.create_access_token(data={"sub": user.email})
    response = RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)
    
    # Secure cookie flags for production
    is_prod = os.environ.get("RENDER") == "true"
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True, 
        secure=is_prod, 
        samesite="lax"
    )
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={"title": "Register"})


@app.post("/register")
@limiter.limit("5/minute")
async def register_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    business_name: str = Form(...),
    db: Session = Depends(get_db),
):
    # 1. Check if user exists
    existing_user = db.query(UserModel).filter(UserModel.email == email).first()
    if existing_user:
        return templates.TemplateResponse(
            request=request, name="register.html", context={"error": "Email already registered", "title": "Register"}
        )

    # 2. Create User
    new_user = UserModel(
        email=email, hashed_password=auth_service.hash_password(password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

        # 3. Provision WhatsApp Instance
    try:
        instance_name = business_name.lower().replace(" ", "_") + "_" + str(new_user.id)
        whatsapp_service = EvolutionWhatsAppService()
        # Pass business_name as display_name for custom linked device name
        instance_data = await whatsapp_service.create_instance(instance_name, display_name=business_name)

        # Robust type check for instance_data response
        if instance_data and isinstance(instance_data, dict):
            # Attempt to get API key from various possible response structures
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
        logger.error("post-registration instance provisioning failed: %s", e, exc_info=True)
        # registration succeeds even if whatsapp provisioning fails;
        # user can connect their number later from the dashboard

    # 4. Login and Redirect
    access_token = auth_service.create_access_token(data={"sub": new_user.email})
    response = RedirectResponse(url="/whatsapp/connect", status_code=HTTP_303_SEE_OTHER)
    
    is_prod = os.environ.get("RENDER") == "true"
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True, 
        secure=is_prod, 
        samesite="lax"
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response


@app.get("/whatsapp/connect", response_class=HTMLResponse)
async def connect_whatsapp_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    instances = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).all()
    )
    return templates.TemplateResponse(
        request=request,
        name="connect_whatsapp.html",
        context={"user": current_user, "instances": instances, "title": "Connect WhatsApp"},
    )


@app.post("/whatsapp/instance/new")
async def create_new_instance(
    name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    # Unique name check/generation
    safe_name = name.lower().replace(" ", "_").strip()
    full_name = f"{safe_name}_{current_user.id}_{uuid.uuid4().hex[:4]}"

    whatsapp_service = EvolutionWhatsAppService()
    # Pass original name as display_name
    instance_data = await whatsapp_service.create_instance(full_name, display_name=name)

    if instance_data and isinstance(instance_data, dict):
        # Attempt to get API key from various possible response structures
        hash_data = instance_data.get("hash")
        if isinstance(hash_data, dict):
            apikey = hash_data.get("apikey")
        elif isinstance(hash_data, str):
            apikey = hash_data
        else:
            apikey = instance_data.get("apikey")

        new_instance = InstanceModel(
            user_id=current_user.id,
            name=full_name,
            display_name=name,
            apikey=apikey,
        )
        db.add(new_instance)
        db.commit()
        return {"success": True, "instance_id": new_instance.id}

    logger.error(
        "failed to create instance. response type: %s",
        type(instance_data),
    )
    return {"success": False, "error": "Failed to create instance or invalid response from Evolution API"}


@app.post("/whatsapp/connect/{instance_id}")
async def get_whatsapp_qr(
    instance_id: int,
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(
            InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id
        )
        .first()
    )
    if not instance_model:
        return {"success": False, "error": "Instance not found"}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey
    )
    qrcode_base64 = await whatsapp_service.get_qrcode()
    if qrcode_base64:
        return {"success": True, "qrcode": qrcode_base64}
    return {"success": False, "error": "Failed to generate QR code"}


@app.get("/whatsapp/status")
async def get_global_whatsapp_status(
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instances = (
        db.query(InstanceModel)
        .filter(InstanceModel.user_id == current_user.id)
        .all()
    )
    if not instances:
        return {"connected": False}

    # Check if ANY instance is connected
    for instance in instances:
        whatsapp_service = EvolutionWhatsAppService(
            instance=instance.name,
            apikey=instance.apikey
        )
        status = await whatsapp_service.get_status()
        if status.get("connected"):
            return {"connected": True}

    return {"connected": False}


@app.get("/whatsapp/status/{instance_id}")
async def get_whatsapp_status(
    instance_id: int,
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(
            InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id
        )
        .first()
    )
    if not instance_model:
        return {"status": "not_found", "connected": False}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey
    )
    status = await whatsapp_service.get_status()
    # Merge label for UI
    status["instance_name"] = instance_model.name
    status["instance_id"] = instance_model.id
    return status


@app.post("/whatsapp/delete/{instance_id}")
async def delete_whatsapp(
    instance_id: int,
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(
            InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id
        )
        .first()
    )
    if not instance_model:
        return {"success": False}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey
    )
    # We attempt to delete from Evolution API, but ignore the result
    # to guarantee we delete ghost local records if it 404s.
    await whatsapp_service.delete_instance()
    
    # Delete from DB unconditionally
    db.delete(instance_model)
    db.commit()
    
    return {"success": True}


@app.post("/whatsapp/rename/{instance_id}")
async def rename_whatsapp(
    instance_id: int,
    new_name: str = Form(...),
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(
            InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id
        )
        .first()
    )
    if not instance_model:
        return {"success": False, "error": "Instance not found"}

    instance_model.display_name = new_name
    db.commit()
    
    return {"success": True}


@app.post("/whatsapp/logout/{instance_id}")
async def logout_whatsapp(
    instance_id: int,
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(
            InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id
        )
        .first()
    )
    if not instance_model:
        return {"success": False}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey
    )
    await whatsapp_service.logout_instance()
    
    # Evolution API takes a few seconds to drop the websocket and update its internal state
    # We will poll it until it reflects the logout, or timeout after 10 seconds
    for _ in range(10):
        status_data = await whatsapp_service.get_status()
        if status_data and isinstance(status_data, dict):
            # Typical v2 response: {'instance': {'state': 'close'}}
            inst_data = status_data.get("instance", {})
            if inst_data.get("state") != "open":
                break
        await asyncio.sleep(1)
        
    # Update local status
    instance_model.status = "disconnected"
    db.commit()
    
    return {"success": True}


@app.get("/whatsapp/groups/{instance_id}")
async def get_whatsapp_groups(
    instance_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(
            InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id
        )
        .first()
    )
    if not instance_model:
        return {"success": False, "error": "Instance not found"}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey
    )

    # For multi-instance, we might want to sync targets per instance?
    # For now, let's just fetch from API and return.
    groups = await whatsapp_service.get_groups()
    chats = await whatsapp_service.get_contacts()

    targets = []
    for g in groups:
        targets.append(
            {"id": g.get("id"), "subject": g.get("subject") or g.get("name")}
        )
    for c in chats:
        targets.append({"id": c.get("id"), "subject": c.get("name") or c.get("id")})

    # Sync to Database (we should add instance_id to targets too, but let's keep it simple for now)
    # if targets:
    #     target_repo.upsert_sync(targets, user_id=current_user.id)

    return {"success": True, "groups": targets}


@app.get("/whatsapp/sync")
async def sync_whatsapp_targets(
    db: Session = Depends(get_db), current_user: UserModel = Depends(login_required)
):
    """Force a sync from API to Database"""
    instance_model = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).first()
    )
    if not instance_model:
        return {"success": False, "error": "No instance provisioned"}

    # pass apikey so the correct tenant key is used instead of the global env fallback
    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey,
    )
    target_repo = SQLTargetRepository(db)

    groups = await whatsapp_service.get_groups()
    chats = await whatsapp_service.get_contacts()

    targets = []
    for g in groups:
        targets.append(
            {"id": g.get("id"), "subject": g.get("subject") or g.get("name")}
        )
    for c in chats:
        targets.append({"id": c.get("id"), "subject": c.get("name") or c.get("id")})

    if targets:
        target_repo.upsert_sync(targets, user_id=current_user.id)

    return {"success": True, "count": len(targets)}


@app.post("/whatsapp/test")
async def send_test_message(
    phone: str = Form(...),
    message: str = Form(...),
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).first()
    )
    instance_name = instance_model.name if instance_model else None

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_name,
        apikey=instance_model.apikey if instance_model else None
    )
    success = await whatsapp_service.send_text(phone, message)
    return {"success": success}


@app.get("/api/v1/whatsapp/trigger")
@app.post("/api/v1/whatsapp/trigger")
async def whatsapp_webhook_trigger(
    request: Request,
    action: str = Query(...),
    jid: Optional[str] = Query(None),
    message: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Secure endpoint to trigger WhatsApp messages from GitHub Actions.
    Protection: X-Trigger-Token header.
    """
    token = os.environ.get("TRIGGER_TOKEN")
    header_token = request.headers.get("X-Trigger-Token")

    if not token or header_token != token:
        raise HTTPException(status_code=403, detail="Invalid trigger token")

    whatsapp_service = EvolutionWhatsAppService()

    if action == "campaign":
        use_case = SalesAgentCampaignUseCase(whatsapp_service)
        success = await use_case.execute(
            jid, message or "Olá! Esta é uma mensagem automática."
        )
        return {"status": "success" if success else "failed", "action": action}

    elif action == "pulse":
        # The 'pulse' action is used to keep the app awake or trigger internal checks
        # if needed. For now, we just return success.
        return {"status": "alive", "action": action}

    return {"status": "received", "action": action}


@app.get("/products", response_class=HTMLResponse)
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


@app.get("/campaigns/new", response_class=HTMLResponse)
async def new_campaign_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    product_repo = SQLProductRepository(db)
    instances = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).all()
    )

    products = product_repo.list_all(user_id=current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="new_campaign.html",
        context={
            "products": products,
            "instances": instances,
            "user": current_user,
            "title": "New Campaign",
        },
    )


@app.post("/campaigns/new")
async def create_campaign(
    title: str = Form(...),
    product_id: int = Form(...),
    groups: List[str] = Form([]),
    instance_id: int = Form(...),
    custom_message: Optional[str] = Form(None),
    scheduled_at: Optional[str] = Form(None),
    is_recurring: bool = Form(False),
    recurrence_days: List[str] = Form([]),
    send_time: Optional[str] = Form(None),
    use_ai: bool = Form(False),
    save_as_draft: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLCampaignRepository(db)
    product_repo = SQLProductRepository(db)
    instance_model = (
        db.query(InstanceModel).filter(InstanceModel.id == instance_id).first()
    )
    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name if instance_model else None,
        apikey=instance_model.apikey if instance_model else None
    )
    ai_service = OpenAIService()

    scheduler = ScheduleCampaign(
        campaign_repo, product_repo, whatsapp_service, ai_service
    )

    # parse scheduled_at if provided
    dt_scheduled = None
    if scheduled_at:
        try:
            dt_scheduled = datetime.fromisoformat(scheduled_at)
        except ValueError as exc:
            logger.warning("invalid scheduled_at value '%s': %s — defaulting to now", scheduled_at, exc)
            dt_scheduled = datetime.now()

    await scheduler.execute(
        title=title,
        product_id=product_id,
        instance_id=instance_id,
        target_groups=groups,
        scheduled_at=dt_scheduled,
        custom_message=custom_message,
        is_recurring=is_recurring,
        recurrence_days=",".join(recurrence_days),
        send_time=send_time,
        use_ai=use_ai,
        user_id=current_user.id,
        save_as_draft=save_as_draft,
    )

    return RedirectResponse(url="/", status_code=303)



@app.get("/campaigns/edit/{campaign_id}", response_class=HTMLResponse)
async def edit_campaign_form(
    campaign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLCampaignRepository(db)
    product_repo = SQLProductRepository(db)

    campaign = campaign_repo.get_by_id(campaign_id, user_id=current_user.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    products = product_repo.list_all(user_id=current_user.id)
    instances = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).all()
    )

    return templates.TemplateResponse(
        request=request,
        name="edit_campaign.html",
        context={
            "campaign": campaign,
            "products": products,
            "instances": instances,
            "user": current_user,
            "title": "Edit Campaign",
        },
    )


@app.post("/campaigns/edit/{campaign_id}")
async def update_campaign(
    campaign_id: int,
    title: str = Form(...),
    product_id: int = Form(...),
    instance_id: int = Form(...),
    groups: List[str] = Form([]),
    custom_message: Optional[str] = Form(None),
    scheduled_at: Optional[str] = Form(None),
    is_recurring: bool = Form(False),
    recurrence_days: List[str] = Form([]),
    send_time: Optional[str] = Form(None),
    use_ai: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLCampaignRepository(db)
    campaign = campaign_repo.get_by_id(campaign_id, user_id=current_user.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    product_repo = SQLProductRepository(db)
    product = product_repo.get_by_id(product_id, user_id=current_user.id)

    # Update entity
    campaign.title = title
    campaign.product = product
    campaign.instance_id = instance_id
    campaign.target_groups = groups
    campaign.custom_message = custom_message
    campaign.is_recurring = is_recurring
    campaign.recurrence_days = ",".join(recurrence_days)
    campaign.send_time = send_time
    if use_ai:
        campaign.is_ai_generated = True

    if scheduled_at:
        try:
            campaign.scheduled_at = datetime.fromisoformat(
                scheduled_at.replace("Z", "")
            )
        except ValueError as exc:
            logger.warning("invalid scheduled_at value '%s': %s — keeping existing value", scheduled_at, exc)

    campaign_repo.save(campaign)
    return RedirectResponse(url="/", status_code=303)



# ── upload helper ──────────────────────────────────────────────────────────────

_ALLOWED_IMAGE_TYPES = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


async def _save_uploaded_image(image_file: UploadFile) -> str:
    """
    Validates that the uploaded file is a real image (using Pillow, not the
    filename extension), enforces a size limit, and saves it to static/uploads.
    Returns the public URL path or raises HTTPException on failure.
    """
    from PIL import Image
    import io

    raw = await image_file.read()

    # enforce size limit before touching disk
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large. Maximum allowed size is {_MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )

    # validate real mime type via Pillow — this catches disguised files
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()  # raises if not a valid image
    except Exception:
        raise HTTPException(
            status_code=415,
            detail="Invalid image file. Only JPEG, PNG, WEBP and GIF are accepted.",
        )

    # re-open (verify() closes the file pointer) to get the real format
    img = Image.open(io.BytesIO(raw))
    fmt = img.format  # e.g. "JPEG", "PNG"
    if fmt not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image format '{fmt}'. Allowed: {', '.join(_ALLOWED_IMAGE_TYPES)}.",
        )

    ext = ".jpg"  # We'll save as JPEG for best compression/compatibility combo
    unique_filename = f"{uuid.uuid4()}{ext}"

    # OPTIMIZATION: Resize and compress to stay under 50MB limit
    try:
        # Re-open for processing
        img = Image.open(io.BytesIO(raw))
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Max 800px width/height for web display
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        
        # Save to buffer with compression
        optimized_buffer = io.BytesIO()
        img.save(optimized_buffer, format="JPEG", quality=75, optimize=True)
        optimized_raw = optimized_buffer.getvalue()
        
        logger.info("Image optimized for Supabase: %d -> %d bytes", len(raw), len(optimized_raw))
        raw = optimized_raw
    except Exception as e:
        logger.warning("Optimization failed, using raw: %s", e)

    # Use Supabase Storage for persistence across Render deployments
    try:
        storage_svc = SupabaseStorageService()
        public_url = await storage_svc.upload_image(
            file_content=raw,
            filename=unique_filename,
            content_type="image/jpeg"
        )
    except Exception as e:
        logger.error("Supabase storage service error: %s", e)
        public_url = None

    if not public_url:
        logger.error("Supabase upload failed, falling back to local (warning: ephemeral)")
        # Fallback to local if Supabase fails (optional, or just raise error)
        upload_dir = os.path.join("core", "presentation", "web", "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        upload_path = os.path.join(upload_dir, unique_filename)
        img = img.convert("RGB") if fmt == "JPEG" else img
        img.save(upload_path)
        return f"/static/uploads/{unique_filename}"

    logger.info("uploaded image saved to Supabase: %s", public_url)
    return public_url


# ── product endpoints ──────────────────────────────────────────────────────────


@app.post("/products/new")
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

    # handle image file upload with MIME validation
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


@app.get("/products/edit/{product_id}", response_class=HTMLResponse)
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


@app.post("/products/edit/{product_id}")
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

    # handle image file upload with MIME validation
    final_image_url = image_url or product.image_url
    if image_file and image_file.filename:
        # User uploaded a new file: use standard optimized upload
        final_image_url = await _save_uploaded_image(image_file)
    elif final_image_url and final_image_url.startswith("/static/uploads/"):
        # Legacy Migration: if it's still local and we haven't uploaded a new one, try to move it now
        local_path = os.path.join("core", "presentation", "web", "static", "uploads", final_image_url.split("/")[-1])
        if os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    content = f.read()
                storage_svc = SupabaseStorageService()
                # Re-optimize/compress even legacy images to save space
                try:
                    img = Image.open(io.BytesIO(content))
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=75, optimize=True)
                    content = buffer.getvalue()
                except Exception:
                    pass

                migrated_url = await storage_svc.upload_image(
                    file_content=content,
                    filename=local_path,
                    content_type="image/jpeg"
                )
                if migrated_url:
                    final_image_url = migrated_url
                    logger.info("lazy-migrated legacy image to Supabase: %s", migrated_url)
            except Exception as e:
                logger.error("Lazy migration failed: %s", e)

    # Update product entity fields
    product.name = name
    product.description = description
    product.price = price
    product.affiliate_link = affiliate_link
    product.category = category
    product.image_url = final_image_url

    product_repo.save(product)
    return RedirectResponse(url="/products", status_code=303)


@app.post("/products/delete/{product_id}")
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


@app.post("/campaign/rewrite")
async def rewrite_campaign_message(
    text: Optional[str] = Form(None),
    product_id: Optional[int] = Form(None),
    is_status: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    """
    Leverages AI to improve a campaign message or generate one from scratch.
    """
    product_repo = SQLProductRepository(db)
    product = None
    if product_id:
        product = product_repo.get_by_id(product_id, user_id=current_user.id)

    ai_service = OpenAIService()
    
    if text:
        prompt = "Melhore esta mensagem de venda para WHATSAPP STATUS (Story), tornando-a altamente persuasiva e visual. "
    else:
        prompt = "Crie uma mensagem impactante para WHATSAPP STATUS (Story) do zero. "
        
    if product:
        prompt += f"Destaque os benefícios do produto: {product.name}. "
        prompt += f"Descrição: {product.description}. "
        
    # Constant: we are strictly focusing on Status now
    prompt += "ESTA MENSAGEM É PARA O STATUS. Seja EXTREMAMENTE conciso e use uma linguagem de Story (curta, direta, com ganchos). "

    prompt += "3. USE EMOJIS e chame a atenção para o link.\n"
    prompt += "4. Não use markdown links (como [texto](url)).\n\n"
    
    link = product.affiliate_link if product else (text if "http" in (text or "") else "")
    prompt += f"Link que DEVE estar na mensagem: {link}\n\n"
    
    if text:
        prompt += f"Texto original: {text}"

    improved_text = await ai_service.chat(prompt)

    # Safety check: if AI removed the link, append it
    if link and link not in improved_text:
        improved_text += f"\n\n👉 Compre aqui: {link}"

    return {"improved_text": improved_text}


@app.get("/storage/view/{filename}", response_class=FileResponse)
async def serve_private_image(filename: str, current_user: UserModel = Depends(login_required)):
    """
    Securely serves images from the private Supabase bucket.
    Requires active dashboard authentication.
    """
    storage_svc = SupabaseStorageService()
    image_bytes = storage_svc.download_image(filename)
    if not image_bytes:
        raise HTTPException(
            status_code=404, detail="Image not found in private storage"
        )
    return Response(content=image_bytes, media_type="image/jpeg")


@app.get("/l/{product_id}", response_class=RedirectResponse)
async def redirect_to_affiliate(product_id: int, db: Session = Depends(get_db)):
    """
    Cloaks affiliate links by redirecting through a local route.
    """
    from core.infrastructure.database.repositories import SQLProductRepository
    product_repo = SQLProductRepository(db)
    # Increment click count before redirecting
    product_repo.increment_clicks(product_id)
    
    product = product_repo.get_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Link not found")
    return RedirectResponse(url=product.affiliate_link)
