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
from core.infrastructure.database.models import Base, CampaignStatus as ModelCampaignStatus
from core.infrastructure.database.repositories import SQLProductRepository, SQLCampaignRepository, SQLTargetRepository
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService
from core.infrastructure.ai.openai_service import OpenAIService
from core.application.use_cases.schedule_campaign import ScheduleCampaign
from core.domain.entities import Product, CampaignStatus as DomainCampaignStatus

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
    Background loop that checks for scheduled campaigns every minute.
    """
    while True:
        try:
            db = SessionLocal()
            campaign_repo = SQLCampaignRepository(db)
            pending_campaigns = campaign_repo.list_pending()
            
            now = datetime.utcnow()
            for campaign in pending_campaigns:
                if campaign.scheduled_at <= now:
                    await send_campaign(campaign, db)
            
            db.close()
        except Exception as e:
            print(f"Error in scheduler loop: {e}")
            
        await asyncio.sleep(60) # Check every minute

async def send_campaign(campaign, db: Session):
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
    # (Note: SQLCampaignRepository needs to handle group storage, for now we assume groups are sent)
    for group_jid in campaign.target_groups:
        success = whatsapp_service.send_text(group_jid, message)
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
    wa_status = whatsapp_service.get_status()
    
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
    qrcode_base64 = whatsapp_service.get_qrcode()
    if qrcode_base64:
        return {"success": True, "qrcode": qrcode_base64}
    return {"success": False, "error": "Failed to generate QR code"}

@app.get("/whatsapp/status")
async def get_whatsapp_status():
    whatsapp_service = EvolutionWhatsAppService()
    status = whatsapp_service.get_status()
    return status

@app.post("/whatsapp/disconnect")
async def disconnect_whatsapp():
    whatsapp_service = EvolutionWhatsAppService()
    success = whatsapp_service.disconnect_instance()
    return {"success": success}

@app.get("/whatsapp/groups")
async def get_whatsapp_groups(db: Session = Depends(get_db)):
    whatsapp_service = EvolutionWhatsAppService()
    target_repo = SQLTargetRepository(db)
    
    groups = whatsapp_service.get_groups()
    chats = whatsapp_service.get_contacts()
    
    targets = []
    for g in groups:
        targets.append({"id": g.get("id"), "subject": g.get("subject") or g.get("name")})
    for c in chats:
        targets.append({"id": c.get("id"), "subject": c.get("name") or c.get("id")})
        
    # Sync to Database
    if targets:
        target_repo.upsert_sync(targets)
        
    return {"success": True, "groups": targets}

@app.post("/whatsapp/test")
async def send_test_message(phone: str = Form(...), message: str = Form(...)):
    whatsapp_service = EvolutionWhatsAppService()
    success = whatsapp_service.send_text(phone, message)
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
    groups: list[str] = Form(...),
    scheduled_at: str = Form(...),
    use_ai: bool = Form(False),
    db: Session = Depends(get_db)
):
    campaign_repo = SQLCampaignRepository(db)
    product_repo = SQLProductRepository(db)
    whatsapp_service = EvolutionWhatsAppService()
    ai_service = OpenAIService()
    
    use_case = ScheduleCampaign(campaign_repo, product_repo, whatsapp_service, ai_service)
    
    scheduled_dt = datetime.fromisoformat(scheduled_at)
    
    use_case.execute(title, product_id, groups, scheduled_dt, use_ai)
    
    return RedirectResponse(url="/", status_code=303)

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
