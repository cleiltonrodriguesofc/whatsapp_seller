from fastapi import (
    FastAPI,
    Request,
    Form,
    Depends,
    HTTPException,
    File,
    UploadFile,
    Query,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from dotenv import load_dotenv
import os
import asyncio
import shutil
import uuid
import json
from typing import List, Optional

# Load environment variables
load_dotenv()

from core.infrastructure.database.session import get_db, engine, SessionLocal
from core.infrastructure.database.models import (
    Base,
    CampaignStatus as ModelCampaignStatus,
    CampaignModel,
    UserModel,
    InstanceModel,
)
from core.infrastructure.database.repositories import (
    SQLProductRepository,
    SQLCampaignRepository,
    SQLTargetRepository,
)
from core.application.use_cases.schedule_campaign import ScheduleCampaign
from core.infrastructure.notifications.evolution_whatsapp import (
    EvolutionWhatsAppService,
)
from core.domain.entities import (
    Campaign,
    Product,
    CampaignStatus as DomainCampaignStatus,
)
from core.infrastructure.ai.openai_service import OpenAIService
from core.application.use_cases.sales_agent_campaign import SalesAgentCampaignUseCase
from core.application.use_cases.send_daily_greeting import SendDailyGreeting
from core.application.services.auth_service import AuthService
from fastapi.security import OAuth2PasswordBearer
from starlette.status import HTTP_303_SEE_OTHER

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="WhatsApp Sales Agent Dashboard")

# Security
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
auth_service = AuthService()

# Mount static files and templates
app.mount(
    "/static", StaticFiles(directory="core/presentation/web/static"), name="static"
)
templates = Jinja2Templates(directory="core/presentation/web/templates")


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
    # Start the background scheduler
    asyncio.create_task(campaign_scheduler_loop())


async def campaign_scheduler_loop():
    """
    Background task to check and send scheduled/recurring campaigns.
    """
    while True:
        db = SessionLocal()
        try:
            now = datetime.utcnow()  # Use utcnow for consistency
            current_time_str = now.strftime("%H:%M")
            current_day_str = now.strftime("%a").lower()  # "mon", "tue", etc.

            campaign_repo = SQLCampaignRepository(db)

            # 1. Handle One-off Campaigns
            pending_one_off = (
                db.query(CampaignModel)
                .filter(
                    CampaignModel.status == ModelCampaignStatus.SCHEDULED,
                    CampaignModel.is_recurring == False,
                    CampaignModel.scheduled_at <= now,
                )
                .all()
            )

            for campaign_model in pending_one_off:
                print(f"Executing One-off Campaign: {campaign_model.title}")
                # Convert Model to Domain entity
                domain_campaign = campaign_repo._to_entity(campaign_model)
                await send_campaign(domain_campaign, db)

            # Iterate through all recurring campaigns
            recurring_campaigns = (
                db.query(CampaignModel)
                .filter(
                    CampaignModel.is_recurring == True,
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
                    except:
                        pass

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
                        print(
                            f"Executing Multi-Time Campaign: {campaign_model.title} at {current_time_str}"
                        )
                        campaign_model.last_run_at = now
                        db.add(campaign_model)
                        db.commit()
                        domain_campaign = campaign_repo._to_entity(campaign_model)
                        await send_campaign(domain_campaign, db)

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
                            print(
                                f"Executing Granular Campaign ({target_type}): {campaign_model.title} at {current_time_str}"
                            )
                            campaign_model.last_run_at = now
                            db.add(campaign_model)
                            db.commit()
                            domain_campaign = campaign_repo._to_entity(campaign_model)
                            # Here we should optionally filter domain_campaign.target_groups by type
                            await send_campaign(domain_campaign, db)

        except Exception as e:
            print(f"Error in scheduler loop: {e}")
        finally:
            db.close()

        await asyncio.sleep(60)  # Check every minute


async def send_campaign(campaign: Campaign, db: Session):
    """
    Sends the campaign messages via WhatsApp with humanized behavior and user-specific instance.
    """
    from core.application.services.humanized_sender import HumanizedSender
    from core.infrastructure.database.models import InstanceModel

    print(f"Sending campaign: {campaign.title}")
    campaign_repo = SQLCampaignRepository(db)

    # 1. Resolve User Instance
    instance_model = (
        db.query(InstanceModel)
        .filter(InstanceModel.user_id == campaign.user_id)
        .first()
    )
    instance_name = instance_model.name if instance_model else None

    # Fallback to default if no user instance found (or if testing)
    whatsapp_service = EvolutionWhatsAppService(instance=instance_name)
    humanized_sender = HumanizedSender(whatsapp_service)

    # Update status to SENDING
    campaign.status = DomainCampaignStatus.SENDING
    campaign_repo.save(campaign)

    # 2. Prepare Content
    message = campaign.custom_message
    if not message:
        message = f"Confira nosso produto: {campaign.product.name} - {campaign.product.affiliate_link}"

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
        print(f"Error during humanized campaign send: {e}")
        campaign.status = DomainCampaignStatus.FAILED

    campaign.sent_at = datetime.utcnow()
    campaign_repo.save(campaign)
    print(f"Campaign {campaign.title} finished. Status: {campaign.status.name}")


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/login")

    campaign_repo = SQLCampaignRepository(db)
    campaigns = campaign_repo.list_all(user_id=current_user.id)

    # Get user's instance
    instance_model = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).first()
    )
    instance_name = instance_model.name if instance_model else None

    whatsapp_service = EvolutionWhatsAppService(instance=instance_name)
    wa_status = await whatsapp_service.get_status()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "campaigns": campaigns,
            "user": current_user,
            "wa_connected": wa_status.get("connected", False),
            "wa_status": wa_status.get("status", "unknown"),
        },
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(UserModel).filter(UserModel.email == username).first()
    if not user or not auth_service.verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid email or password"}
        )

    access_token = auth_service.create_access_token(data={"sub": user.email})
    response = RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
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
            "register.html", {"request": request, "error": "Email already registered"}
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
        instance_data = await whatsapp_service.create_instance(instance_name)

        if instance_data:
            # The structure might vary depending on Evolution API version
            # v1 often has instance.hash.apikey, v2 might be different
            apikey = (instance_data.get("hash", {}) or {}).get(
                "apikey"
            ) or instance_data.get("apikey")

            new_instance = InstanceModel(
                user_id=new_user.id,
                name=instance_name,
                apikey=apikey,
            )
            db.add(new_instance)
            db.commit()
    except Exception as e:
        print(f"Post-registration instance provisioning failed: {e}")
        # We don't fail the whole registration if WhatsApp provisioning fails
        # The user can retry connecting later in the dashboard

    # 4. Login and Redirect
    access_token = auth_service.create_access_token(data={"sub": new_user.email})
    response = RedirectResponse(url="/whatsapp/connect", status_code=HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response


@app.get("/whatsapp/connect", response_class=HTMLResponse)
async def connect_whatsapp_page(
    request: Request, current_user: UserModel = Depends(login_required)
):
    return templates.TemplateResponse(
        "connect_whatsapp.html", {"request": request, "user": current_user}
    )


@app.post("/whatsapp/connect")
async def get_whatsapp_qr(
    current_user: UserModel = Depends(login_required), db: Session = Depends(get_db)
):
    instance_model = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).first()
    )
    if not instance_model:
        return {"success": False, "error": "No instance provisioned"}

    whatsapp_service = EvolutionWhatsAppService(instance=instance_model.name)
    qrcode_base64 = await whatsapp_service.get_qrcode()
    if qrcode_base64:
        return {"success": True, "qrcode": qrcode_base64}
    return {"success": False, "error": "Failed to generate QR code"}


@app.get("/whatsapp/status")
async def get_whatsapp_status(
    current_user: UserModel = Depends(login_required), db: Session = Depends(get_db)
):
    instance_model = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).first()
    )
    if not instance_model:
        return {"status": "not_found", "connected": False}

    whatsapp_service = EvolutionWhatsAppService(instance=instance_model.name)
    status = await whatsapp_service.get_status()
    return status


@app.post("/whatsapp/disconnect")
async def disconnect_whatsapp(
    current_user: UserModel = Depends(login_required), db: Session = Depends(get_db)
):
    instance_model = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).first()
    )
    if not instance_model:
        return {"success": False}

    whatsapp_service = EvolutionWhatsAppService(instance=instance_model.name)
    success = await whatsapp_service.disconnect_instance()
    return {"success": success}


@app.get("/whatsapp/groups")
async def get_whatsapp_groups(
    db: Session = Depends(get_db), current_user: UserModel = Depends(login_required)
):
    instance_model = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).first()
    )
    if not instance_model:
        return {"success": False, "error": "No instance provisioned"}

    whatsapp_service = EvolutionWhatsAppService(instance=instance_model.name)
    target_repo = SQLTargetRepository(db)

    # 1. Check database first
    db_targets = target_repo.list_all(user_id=current_user.id)
    if db_targets:
        targets = [{"id": t.jid, "subject": t.name} for t in db_targets]
        return {"success": True, "groups": targets, "source": "database"}

    # 2. Fallback to API if DB is empty
    groups = await whatsapp_service.get_groups()
    chats = await whatsapp_service.get_contacts()

    targets = []
    for g in groups:
        targets.append(
            {"id": g.get("id"), "subject": g.get("subject") or g.get("name")}
        )
    for c in chats:
        targets.append({"id": c.get("id"), "subject": c.get("name") or c.get("id")})

    # Sync to Database for next time
    if targets:
        target_repo.upsert_sync(targets, user_id=current_user.id)

    return {"success": True, "groups": targets, "source": "api"}


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

    whatsapp_service = EvolutionWhatsAppService(instance=instance_model.name)
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

    whatsapp_service = EvolutionWhatsAppService(instance=instance_name)
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
        "products.html",
        {"request": request, "products": products, "user": current_user},
    )


@app.get("/campaigns/new", response_class=HTMLResponse)
async def new_campaign_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    product_repo = SQLProductRepository(db)
    target_repo = SQLTargetRepository(db)

    products = product_repo.list_all(user_id=current_user.id)
    db_targets = target_repo.list_all(user_id=current_user.id)

    # Map DB targets to the UI format
    targets = []
    for t in db_targets:
        targets.append({"id": t.jid, "name": t.name, "type": t.type})

    # We still allow dynamic refresh via JS, but now provide cached targets for speed
    return templates.TemplateResponse(
        "new_campaign.html",
        {
            "request": request,
            "products": products,
            "targets": targets,
            "user": current_user,
        },
    )


@app.post("/campaigns/new")
async def create_campaign(
    title: str = Form(...),
    product_id: int = Form(...),
    groups: List[str] = Form(...),
    custom_message: Optional[str] = Form(None),
    scheduled_at: Optional[str] = Form(None),
    is_recurring: bool = Form(False),
    recurrence_days: List[str] = Form([]),
    send_time: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLCampaignRepository(db)
    product_repo = SQLProductRepository(db)
    whatsapp_service = EvolutionWhatsAppService()
    ai_service = OpenAIService()

    scheduler = ScheduleCampaign(
        campaign_repo, product_repo, whatsapp_service, ai_service
    )

    # Parse scheduled_at if provided
    dt_scheduled = None
    if scheduled_at:
        try:
            dt_scheduled = datetime.fromisoformat(scheduled_at)
        except ValueError:
            pass

    # Combine recurrence days into a string
    days_str = ",".join(recurrence_days) if recurrence_days else None

    # Use a copy of custom_message to avoid modifying the original Form value
    message_copy = custom_message

    await scheduler.execute(
        title=title,
        product_id=product_id,
        target_groups=groups,
        scheduled_at=dt_scheduled,
        custom_message=message_copy,
        is_recurring=is_recurring,
        recurrence_days=days_str,
        send_time=send_time,
        use_ai=not bool(custom_message),
        user_id=current_user.id,
    )

    return RedirectResponse(url="/campaigns", status_code=303)


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

    # Handle image file upload
    final_image_url = image_url
    if image_file and image_file.filename:
        # Create unique filename
        file_ext = os.path.splitext(image_file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        upload_path = os.path.join(
            "core/presentation/web/static/uploads", unique_filename
        )

        # Ensure directory exists
        os.makedirs(os.path.dirname(upload_path), exist_ok=True)

        # Save file
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)

        # URL for the saved file
        final_image_url = f"/static/uploads/{unique_filename}"

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
        "edit_product.html",
        {"request": request, "product": product, "user": current_user},
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

    # Handle image file upload
    final_image_url = image_url or product.image_url
    if image_file and image_file.filename:
        file_ext = os.path.splitext(image_file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        upload_path = os.path.join(
            "core/presentation/web/static/uploads", unique_filename
        )
        os.makedirs(os.path.dirname(upload_path), exist_ok=True)
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)
        final_image_url = f"/static/uploads/{unique_filename}"

    product_repo.save(product)
    return RedirectResponse(url="/products", status_code=303)


@app.post("/campaign/rewrite")
async def rewrite_campaign_message(
    text: str = Form(...),
    product_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    """
    Leverages AI to improve a campaign message.
    """
    product_repo = SQLProductRepository(db)
    product = None
    if product_id:
        product = product_repo.get_by_id(product_id, user_id=current_user.id)

    ai_service = OpenAIService()
    prompt = f"Melhore esta mensagem de venda para WhatsApp, tornando-a mais persuasiva e profissional. "
    if product:
        prompt += f"Considerei os detalhes do produto: {product.name} - {product.description}. "
    prompt += f"MANTENHA O LINK ABAIXO EXATAMENTE COMO ESTÁ, NO FINAL DA MENSAGEM. "
    prompt += f"Mantenha emojis e um tom amigável. Não use markdown links (como [texto](url)).\n\n"
    prompt += f"Link que DEVE estar na mensagem: {product.affiliate_link if product else ''}\n\n"
    prompt += f"Texto original: {text}"

    improved_text = await ai_service.chat(prompt)

    # Safety check: if AI removed the link, append it
    if product and product.affiliate_link not in improved_text:
        improved_text += f"\n\n👉 Compre aqui: {product.affiliate_link}"

    return {"improved_text": improved_text}
