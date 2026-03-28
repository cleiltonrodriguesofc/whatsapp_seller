"""
Campaign routes: dashboard, new/edit/delete campaigns, AI rewrite.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from core.application.use_cases.schedule_campaign import ScheduleCampaign
from core.infrastructure.ai.openai_service import OpenAIService
from core.infrastructure.database.models import (
    CampaignStatus as ModelCampaignStatus,
    InstanceModel,
    UserModel,
    StatusCampaignModel,
)
from core.infrastructure.database.repositories import (
    SQLCampaignRepository,
    SQLProductRepository,
)
from core.infrastructure.database.session import get_db
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService
from core.presentation.web.dependencies import (
    get_current_user,
    login_required,
    templates,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["campaigns"])


@router.head("/", include_in_schema=False)
async def home_head():
    return {}


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_current_user),
):
    if not current_user:
        return templates.TemplateResponse(request=request, name="landing.html", context={"title": "Welcome"})

    # Estatísticas focadas em Status
    status_campaigns = db.query(StatusCampaignModel).filter(StatusCampaignModel.user_id == current_user.id).all()
    sent_count = (
        db.query(StatusCampaignModel)
        .filter(StatusCampaignModel.user_id == current_user.id, StatusCampaignModel.status == ModelCampaignStatus.SENT)
        .count()
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "campaigns": status_campaigns,
            "sent_count": sent_count,
            "ai_count": 0,
            "total_clicks": 0,
            "user": current_user,
        },
    )


@router.post("/campaign/delete/{campaign_id}")
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


@router.get("/campaigns/new", response_class=HTMLResponse)
async def new_campaign_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    product_repo = SQLProductRepository(db)
    instances = db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).all()
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


@router.post("/campaigns/new")
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
    instance_model = db.query(InstanceModel).filter(InstanceModel.id == instance_id).first()
    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name if instance_model else None,
        apikey=instance_model.apikey if instance_model else None,
    )
    ai_service = OpenAIService()

    scheduler = ScheduleCampaign(campaign_repo, product_repo, whatsapp_service, ai_service)

    dt_scheduled = None
    if scheduled_at:
        try:
            dt_scheduled = datetime.fromisoformat(scheduled_at)
        except ValueError as exc:
            logger.warning(
                "invalid scheduled_at value '%s': %s — defaulting to now",
                scheduled_at,
                exc,
            )
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


@router.get("/campaigns/edit/{campaign_id}", response_class=HTMLResponse)
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
    instances = db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).all()

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


@router.post("/campaigns/edit/{campaign_id}")
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
            campaign.scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", ""))
        except ValueError as exc:
            logger.warning(
                "invalid scheduled_at value '%s': %s — keeping existing value",
                scheduled_at,
                exc,
            )

    campaign_repo.save(campaign)
    return RedirectResponse(url="/", status_code=303)


@router.post("/campaign/rewrite")
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
        prompt = "Melhore esta mensagem de venda para WhatsApp, tornando-a mais persuasiva e profissional. "
    else:
        prompt = "Crie uma mensagem persuasiva de vendas para o WhatsApp do zero. "

    if product:
        prompt += f"Foque nos benefícios práticos do produto: {product.name}. "
        prompt += f"Descrição: {product.description}. Preço: R$ {product.price}. "

    if is_status:
        prompt += "ESTA MENSAGEM É PARA O STATUS DO WHATSAPP. Seja extremamente conciso (máximo 700 caracteres). "
    else:
        prompt += "Mantenha um tom amigável e focado em converter o cliente. "

    prompt += "MANTENHA O LINK ABAIXO EXATAMENTE COMO ESTÁ NO FINAL DA MENSAGEM. "
    prompt += "Use emojis, bullet points e uma chamada para ação clara. "
    prompt += "Não use markdown links (como [texto](url)).\n\n"

    link = product.affiliate_link if product else (text if "http" in (text or "") else "")
    prompt += f"Link que DEVE estar na mensagem: {link}\n\n"

    if text:
        prompt += f"Texto original: {text}"

    improved_text = await ai_service.chat(prompt)

    if link and link not in improved_text:
        improved_text += f"\n\n👉 Compre aqui: {link}"

    return {"improved_text": improved_text}
