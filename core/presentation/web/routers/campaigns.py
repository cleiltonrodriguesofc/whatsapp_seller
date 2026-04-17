"""
Campaign routes: dashboard, new/edit/delete campaigns, AI rewrite.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.application.use_cases.schedule_campaign import ScheduleCampaign
from core.infrastructure.ai.openai_service import OpenAIService
from core.infrastructure.database.models import (
    InstanceModel,
    StatusCampaignModel,
    SubscriptionModel,
    UserModel,
    CampaignModel,
    BroadcastCampaignModel,
    ProductModel,
    ActivityLogModel,
    WhatsAppTargetModel,
    campaign_groups,
)
from core.infrastructure.database.repositories import (
    SQLCampaignRepository,
    SQLProductRepository,
    SQLActivityRepository,
)
from core.infrastructure.database.session import get_db
from core.infrastructure.notifications.evolution_whatsapp import (
    EvolutionWhatsAppService,
)
from core.presentation.web.dependencies import (
    get_current_user,
    login_required,
    templates,
)
from core.domain.entities import ActivityLog

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
        return templates.TemplateResponse(
            request=request, name="landing.html", context={"title": "Welcome"}
        )

    uid = current_user.id

    # --- Statistics Aggregation ---

    # 1. Total Campaigns (all types)
    c_count = db.query(CampaignModel).filter(CampaignModel.user_id == uid).count()
    s_count = (
        db.query(StatusCampaignModel).filter(StatusCampaignModel.user_id == uid).count()
    )
    b_count = (
        db.query(BroadcastCampaignModel)
        .filter(BroadcastCampaignModel.user_id == uid)
        .count()
    )
    total_campaigns = c_count + s_count + b_count

    # 2. Total Messages Sent (actual recipients, not campaign count)
    # - CampaignModel: count rows in campaign_groups for all sent campaigns of this user
    c_sent_messages = (
        db.query(func.count(campaign_groups.c.group_jid))
        .join(CampaignModel, campaign_groups.c.campaign_id == CampaignModel.id)
        .filter(CampaignModel.user_id == uid, CampaignModel.status == "sent")
        .scalar()
        or 0
    )
    # - StatusCampaignModel: target_contacts is a JSON list stored as text; we must
    #   fetch each sent campaign and count items in its list in Python
    sent_status_campaigns = (
        db.query(StatusCampaignModel)
        .filter(
            StatusCampaignModel.user_id == uid, StatusCampaignModel.status == "sent"
        )
        .all()
    )
    s_sent_messages = 0
    for sc in sent_status_campaigns:
        if sc.target_contacts:
            try:
                contacts = json.loads(sc.target_contacts)
                s_sent_messages += len(contacts) if isinstance(contacts, list) else 1
            except (json.JSONDecodeError, TypeError):
                s_sent_messages += 1
    # - BroadcastCampaignModel: uses its own sent_count field (accurate)
    b_sent_messages = (
        db.query(func.sum(BroadcastCampaignModel.sent_count))
        .filter(BroadcastCampaignModel.user_id == uid)
        .scalar()
        or 0
    )
    total_sent = c_sent_messages + s_sent_messages + b_sent_messages

    # 3. AI Generated campaigns count
    ai_count = (
        db.query(CampaignModel)
        .filter(
            CampaignModel.user_id == uid,
            CampaignModel.is_ai_generated == True,  # noqa: E712
        )
        .count()
    )

    # 4. Total Clicks across all products
    total_clicks = (
        db.query(func.sum(ProductModel.click_count))
        .filter(ProductModel.user_id == uid)
        .scalar()
        or 0
    )

    # 5. Unique Contacts and Groups (deduplicated by JID, active only)
    contact_count = (
        db.query(func.count(func.distinct(WhatsAppTargetModel.jid)))
        .filter(
            WhatsAppTargetModel.user_id == uid,
            WhatsAppTargetModel.type == "chat",
            WhatsAppTargetModel.is_active == True,  # noqa: E712
        )
        .scalar()
        or 0
    )
    group_count = (
        db.query(func.count(func.distinct(WhatsAppTargetModel.jid)))
        .filter(
            WhatsAppTargetModel.user_id == uid,
            WhatsAppTargetModel.type == "group",
            WhatsAppTargetModel.is_active == True,  # noqa: E712
        )
        .scalar()
        or 0
    )

    # --- Chart Data Generation (Last 7 Days) ---
    today = datetime.utcnow().date()
    # Generate labels backwards from today
    labels = []
    clicks_data = []
    mensagens_data = []

    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        start_dt = datetime(target_date.year, target_date.month, target_date.day)
        end_dt = start_dt + timedelta(days=1)

        # Abbreviated weekday label (e.g., Seg, Ter)
        # Using a simple mapping since strftime("%a") uses locale in some envs
        pt_br_weekdays = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        labels.append(pt_br_weekdays[target_date.weekday()])

        # Count Clicks for target_date
        day_clicks = (
            db.query(ActivityLogModel)
            .filter(
                ActivityLogModel.user_id == uid,
                ActivityLogModel.event_type == "link_click",
                ActivityLogModel.timestamp >= start_dt,
                ActivityLogModel.timestamp < end_dt,
            )
            .count()
        )
        clicks_data.append(day_clicks)

        # Count Sent Messages for target_date
        # (Status, Regular)
        c_day_sent = (
            db.query(CampaignModel)
            .filter(
                CampaignModel.user_id == uid,
                CampaignModel.status == "sent",
                CampaignModel.sent_at >= start_dt,
                CampaignModel.sent_at < end_dt,
            )
            .count()
        )
        s_day_sent = (
            db.query(StatusCampaignModel)
            .filter(
                StatusCampaignModel.user_id == uid,
                StatusCampaignModel.status == "sent",
                StatusCampaignModel.sent_at >= start_dt,
                StatusCampaignModel.sent_at < end_dt,
            )
            .count()
        )
        b_day_sent = (
            db.query(func.sum(BroadcastCampaignModel.sent_count))
            .filter(
                BroadcastCampaignModel.user_id == uid,
                BroadcastCampaignModel.sent_at >= start_dt,
                BroadcastCampaignModel.sent_at < end_dt,
            )
            .scalar()
            or 0
        )

        mensagens_data.append(c_day_sent + s_day_sent + b_day_sent)

    chart_data = {
        "labels": labels,
        "cliques": clicks_data,
        "mensagens": mensagens_data,
        "distribution": {"regular": c_count, "status": s_count, "broadcast": b_count},
    }

    # Buscar assinatura e dados de referral
    subscription = (
        db.query(SubscriptionModel).filter(SubscriptionModel.user_id == uid).first()
    )

    # Calcular dias restantes se for trial
    days_left = 0
    if (
        subscription
        and subscription.status == "trialing"
        and subscription.trial_ends_at
    ):
        delta = subscription.trial_ends_at - datetime.utcnow()
        days_left = max(0, delta.days)

    recent_campaigns = (
        db.query(CampaignModel)
        .filter(CampaignModel.user_id == uid)
        .order_by(CampaignModel.created_at.desc())
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "campaigns": recent_campaigns,
            "total_campaigns": total_campaigns,
            "total_sent": total_sent,
            "ai_count": ai_count,
            "total_clicks": total_clicks,
            "contact_count": contact_count,
            "group_count": group_count,
            "user": current_user,
            "subscription": subscription,
            "days_left": days_left,
            "chart_data": chart_data,
        },
    )


@router.post("/campaign/delete/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLCampaignRepository(db)
    campaign = campaign_repo.get_by_id(campaign_id, user_id=current_user.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    title = campaign.title
    success = campaign_repo.delete(campaign_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="campaign_delete",
            description=f"Deleted campaign: {title}",
        )
    )

    return RedirectResponse(url="/", status_code=303)


@router.post("/campaign/pause/{campaign_id}")
async def pause_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign = db.query(CampaignModel).filter(CampaignModel.id == campaign_id, CampaignModel.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "paused"
    db.commit()
    return {"success": True, "status": "paused"}


@router.post("/campaign/resume/{campaign_id}")
async def resume_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign = db.query(CampaignModel).filter(CampaignModel.id == campaign_id, CampaignModel.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # If it's recurring, picking it up again is automatic.
    # If it's one-off, set back to scheduled.
    campaign.status = "scheduled"
    db.commit()
    return {"success": True, "status": "scheduled"}


@router.post("/campaign/cancel/{campaign_id}")
async def cancel_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign = db.query(CampaignModel).filter(CampaignModel.id == campaign_id, CampaignModel.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "canceled"
    db.commit()
    return {"success": True, "status": "canceled"}


@router.post("/campaign/resend/{campaign_id}")
async def resend_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign = db.query(CampaignModel).filter(CampaignModel.id == campaign_id, CampaignModel.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "scheduled"
    campaign.sent_at = None
    if not campaign.is_recurring:
        from core.infrastructure.utils.timezone import now_sp
        campaign.scheduled_at = now_sp()
        
    db.commit()
    return {"success": True, "status": "scheduled"}


@router.get("/campaigns/new", response_class=HTMLResponse)
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
    instance_model = (
        db.query(InstanceModel).filter(InstanceModel.id == instance_id).first()
    )
    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name if instance_model else None,
        apikey=instance_model.apikey if instance_model else None,
    )
    ai_service = OpenAIService()

    scheduler = ScheduleCampaign(
        campaign_repo, product_repo, whatsapp_service, ai_service
    )

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

    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="campaign_create",
            description=f"Created campaign: {title} (Draft: {save_as_draft})",
        )
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
            campaign.scheduled_at = datetime.fromisoformat(
                scheduled_at.replace("Z", "")
            )
        except ValueError as exc:
            logger.warning(
                "invalid scheduled_at value '%s': %s — keeping existing value",
                scheduled_at,
                exc,
            )

    campaign_repo.save(campaign)

    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="campaign_edit",
            description=f"Updated campaign: {title}",
        )
    )

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

    link = (
        product.affiliate_link if product else (text if "http" in (text or "") else "")
    )
    prompt += f"Link que DEVE estar na mensagem: {link}\n\n"

    if text:
        prompt += f"Texto original: {text}"

    improved_text = await ai_service.chat(prompt)

    if link and link not in improved_text:
        improved_text += f"\n\n👉 Compre aqui: {link}"

    return {"improved_text": improved_text}
