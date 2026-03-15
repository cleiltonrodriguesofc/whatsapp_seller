from fastapi import FastAPI, Request, Form, Depends, HTTPException, File, UploadFile
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

# Load environment variables
load_dotenv()

from core.infrastructure.database.session import get_db, engine, SessionLocal
from core.infrastructure.database.models import Base, CampaignStatus as ModelCampaignStatus, Campaign as CampaignModel # Added CampaignModel import
from core.infrastructure.database.repositories import SQLProductRepository, SQLCampaignRepository, SQLTargetRepository
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService
from core.infrastructure.ai.openai_service import OpenAIService
from core.application.use_cases.schedule_campaign import ScheduleCampaign
from core.domain.entities import Campaign, Product, CampaignStatus as DomainCampaignStatus

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="WhatsApp Sales Agent Dashboard")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="core/presentation/web/static"), name="static")
templates = Jinja2Templates(directory="core/presentation/web/templates")

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
            now = datetime.utcnow() # Use utcnow for consistency
            current_time_str = now.strftime("%H:%M")
            current_day_str = now.strftime("%a").lower() # "mon", "tue", etc.
            
            campaign_repo = SQLCampaignRepository(db)
            
            # 1. Handle One-off Campaigns
            pending_one_off = db.query(CampaignModel).filter(
                CampaignModel.status == ModelCampaignStatus.SCHEDULED,
                CampaignModel.is_recurring == False,
                CampaignModel.scheduled_at <= now
            ).all()
            
            for campaign_model in pending_one_off:
                print(f"Executing One-off Campaign: {campaign_model.title}")
                # Convert Model to Domain entity
                domain_campaign = campaign_repo._to_entity(campaign_model)
                await send_campaign(domain_campaign, db)
                
            # 2. Handle Recurring Campaigns
            recurring_campaigns = db.query(CampaignModel).filter(
                CampaignModel.is_recurring == True,
                CampaignModel.status != ModelCampaignStatus.FAILED # Don't try to send failed recurring campaigns
            ).all()
            
            for campaign_model in recurring_campaigns:
                # Check if today is one of the recurrence days
                if campaign_model.recurrence_days and current_day_str in campaign_model.recurrence_days.lower():
                    # Check if it's time to send
                    if campaign_model.send_time == current_time_str:
                        # Ensure we haven't sent it today already
                        if not campaign_model.last_run_at or campaign_model.last_run_at.date() < now.date():
                            print(f"Executing Recurring Campaign: {campaign_model.title}")
                            
                            # Update last run AT THE START to prevent multiple triggers in same minute
                            campaign_model.last_run_at = now
                            campaign_model.status = ModelCampaignStatus.SCHEDULED # Reset status for sending
                            db.add(campaign_model)
                            db.commit()
                            db.refresh(campaign_model) # Refresh to get updated state
                            
                            # Convert Model to Domain entity
                            domain_campaign = campaign_repo._to_entity(campaign_model)
                            await send_campaign(domain_campaign, db)
                            
        except Exception as e:
            print(f"Error in scheduler loop: {e}")
        finally:
            db.close()
        
        await asyncio.sleep(60) # Check every minute

async def send_campaign(campaign: Campaign, db: Session):
    """
    Sends the campaign messages via WhatsApp.
    """
    print(f"Sending campaign: {campaign.title}")
    campaign_repo = SQLCampaignRepository(db)
    whatsapp_service = EvolutionWhatsAppService()
    
    # Update status to SENDING
    campaign.status = DomainCampaignStatus.SENDING
    campaign_repo.save(campaign)
    
    success_count = 0
    message = campaign.custom_message or f"Confira nosso produto: {campaign.product.name} - {campaign.product.affiliate_link}"
    
    # Target groups list from campaign
    for group_jid in campaign.target_groups:
        success = await whatsapp_service.send_text(group_jid, message)
        if success:
            success_count += 1
            
    # Final update
    campaign.status = DomainCampaignStatus.SENT if success_count > 0 else DomainCampaignStatus.FAILED
    campaign.sent_at = datetime.utcnow()
    campaign_repo.save(campaign)
    print(f"Campaign {campaign.title} finished. Success count: {success_count}")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    campaign_repo = SQLCampaignRepository(db)
    campaigns = campaign_repo.list_all()
    
    whatsapp_service = EvolutionWhatsAppService()
    wa_status = await whatsapp_service.get_status()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "campaigns": campaigns,
        "wa_connected": wa_status.get("connected", False),
        "wa_status": wa_status.get("status", "unknown")
    })

@app.get("/whatsapp/connect", response_class=HTMLResponse)
async def connect_whatsapp_page(request: Request):
    return templates.TemplateResponse("connect_whatsapp.html", {
        "request": request
    })

@app.post("/whatsapp/connect")
async def get_whatsapp_qr():
    whatsapp_service = EvolutionWhatsAppService()
    qrcode_base64 = await whatsapp_service.get_qrcode()
    if qrcode_base64:
        return {"success": True, "qrcode": qrcode_base64}
    return {"success": False, "error": "Failed to generate QR code"}

@app.get("/whatsapp/status")
async def get_whatsapp_status():
    whatsapp_service = EvolutionWhatsAppService()
    status = await whatsapp_service.get_status()
    return status

@app.post("/whatsapp/disconnect")
async def disconnect_whatsapp():
    whatsapp_service = EvolutionWhatsAppService()
    success = await whatsapp_service.disconnect_instance()
    return {"success": success}

@app.get("/whatsapp/groups")
async def get_whatsapp_groups(db: Session = Depends(get_db)):
    whatsapp_service = EvolutionWhatsAppService()
    target_repo = SQLTargetRepository(db)
    
    # 1. Check database first
    db_targets = target_repo.list_all()
    if db_targets:
        targets = [{"id": t.jid, "subject": t.name} for t in db_targets]
        return {"success": True, "groups": targets, "source": "database"}
    
    # 2. Fallback to API if DB is empty
    groups = await whatsapp_service.get_groups()
    chats = await whatsapp_service.get_contacts()
    
    targets = []
    for g in groups:
        targets.append({"id": g.get("id"), "subject": g.get("subject") or g.get("name")})
    for c in chats:
        targets.append({"id": c.get("id"), "subject": c.get("name") or c.get("id")})
        
    # Sync to Database for next time
    if targets:
        target_repo.upsert_sync(targets)
        
    return {"success": True, "groups": targets, "source": "api"}

@app.get("/whatsapp/sync")
async def sync_whatsapp_targets(db: Session = Depends(get_db)):
    """Force a sync from API to Database"""
    whatsapp_service = EvolutionWhatsAppService()
    target_repo = SQLTargetRepository(db)
    
    groups = await whatsapp_service.get_groups()
    chats = await whatsapp_service.get_contacts()
    
    targets = []
    for g in groups:
        targets.append({"id": g.get("id"), "subject": g.get("subject") or g.get("name")})
    for c in chats:
        targets.append({"id": c.get("id"), "subject": c.get("name") or c.get("id")})
        
    if targets:
        target_repo.upsert_sync(targets)
        
    return {"success": True, "count": len(targets)}

@app.post("/whatsapp/test")
async def send_test_message(phone: str = Form(...), message: str = Form(...)):
    whatsapp_service = EvolutionWhatsAppService()
    success = await whatsapp_service.send_text(phone, message)
    return {"success": success}

@app.get("/products", response_class=HTMLResponse)
async def list_products(request: Request, db: Session = Depends(get_db)):
    product_repo = SQLProductRepository(db)
    products = product_repo.list_all()
    return templates.TemplateResponse("products.html", {"request": request, "products": products})

@app.get("/campaigns/new", response_class=HTMLResponse)
async def new_campaign_form(request: Request, db: Session = Depends(get_db)):
    product_repo = SQLProductRepository(db)
    target_repo = SQLTargetRepository(db)
    
    products = product_repo.list_all()
    db_targets = target_repo.list_all()
    
    # Map DB targets to the UI format
    targets = []
    for t in db_targets:
        targets.append({"id": t.jid, "name": t.name, "type": t.type})
    
    # We still allow dynamic refresh via JS, but now provide cached targets for speed
    return templates.TemplateResponse("new_campaign.html", {
        "request": request, 
        "products": products,
        "targets": targets
    })

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
    db: Session = Depends(get_db)
):
    campaign_repo = SQLCampaignRepository(db)
    product_repo = SQLProductRepository(db)
    whatsapp_service = EvolutionWhatsAppService()
    ai_service = OpenAIService()
    
    scheduler = ScheduleCampaign(
        campaign_repo, 
        product_repo, 
        whatsapp_service, 
        ai_service
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

    await scheduler.execute(
        title=title,
        product_id=product_id,
        target_groups=groups,
        scheduled_at=dt_scheduled,
        custom_message=custom_message,
        is_recurring=is_recurring,
        recurrence_days=days_str,
        send_time=send_time,
        use_ai=not bool(custom_message)
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
    db: Session = Depends(get_db)
):
    product_repo = SQLProductRepository(db)
    
    # Handle image file upload
    final_image_url = image_url
    if image_file and image_file.filename:
        # Create unique filename
        file_ext = os.path.splitext(image_file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        upload_path = os.path.join("core/presentation/web/static/uploads", unique_filename)
        
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
        category=category
    )
    product_repo.save(product)
    return RedirectResponse(url="/products", status_code=303)
