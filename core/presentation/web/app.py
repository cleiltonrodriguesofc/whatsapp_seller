from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import os
import asyncio

from core.infrastructure.database.session import get_db, engine, SessionLocal
from core.infrastructure.database.models import Base, CampaignStatus as ModelCampaignStatus
from core.infrastructure.database.repositories import SQLProductRepository, SQLCampaignRepository
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
    return templates.TemplateResponse("dashboard.html", {"request": request, "campaigns": campaigns})

@app.get("/products", response_class=HTMLResponse)
async def list_products(request: Request, db: Session = Depends(get_db)):
    product_repo = SQLProductRepository(db)
    products = product_repo.list_all()
    return templates.TemplateResponse("products.html", {"request": request, "products": products})

@app.get("/campaigns/new", response_class=HTMLResponse)
async def new_campaign_form(request: Request, db: Session = Depends(get_db)):
    product_repo = SQLProductRepository(db)
    products = product_repo.list_all()
    
    whatsapp_service = EvolutionWhatsAppService()
    groups = whatsapp_service.get_groups()
    
    return templates.TemplateResponse("new_campaign.html", {
        "request": request, 
        "products": products,
        "groups": groups
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
    db: Session = Depends(get_db)
):
    product_repo = SQLProductRepository(db)
    product = Product(
        name=name,
        description=description,
        price=price,
        affiliate_link=affiliate_link,
        image_url=image_url
    )
    product_repo.save(product)
    return RedirectResponse(url="/products", status_code=303)
