import logging
from datetime import datetime
from core.infrastructure.utils.timezone import now_sp, to_sp
from typing import Optional
import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from core.domain.entities import StatusCampaign, CampaignStatus, ActivityLog
from core.infrastructure.database.models import (
    UserModel,
    InstanceModel,
    WhatsAppTargetModel,
)
from core.infrastructure.database.repositories import (
    SQLStatusCampaignRepository,
    SQLInstanceRepository,
    SQLTargetRepository,
    SQLActivityRepository,
)
from core.infrastructure.database.session import get_db
from core.presentation.web.dependencies import login_required, templates
from core.presentation.web.routers.products import _save_uploaded_image
from core.infrastructure.services.supabase_storage import SupabaseStorageService
from core.infrastructure.ai.openai_service import OpenAIService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["status_campaigns"])


@router.get("/status_campaigns", response_class=HTMLResponse)
async def list_status_campaigns(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    repo = SQLStatusCampaignRepository(db)
    campaigns = repo.list_all(user_id=current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="status_list.html",
        context={
            "campaigns": campaigns,
            "user": current_user,
            "title": "Status Automático",
        },
    )


@router.get("/status_campaigns/new", response_class=HTMLResponse)
async def new_status_campaign_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    instance_repo = SQLInstanceRepository(db)
    instances = instance_repo.list_by_user(current_user.id)

    target_repo = SQLTargetRepository(db)
    targets = target_repo.list_all(current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="status_editor.html",
        context={
            "user": current_user,
            "campaign": None,
            "instances": instances,
            "targets": targets,
            "title": "Novo Status Automático",
        },
    )


@router.post("/status_campaigns/new")
async def create_status_campaign(
    title: str = Form(...),
    image_file: Optional[UploadFile] = File(None),
    caption: Optional[str] = Form(None),
    link: Optional[str] = Form(None),
    price: Optional[str] = Form(None),
    background_color: Optional[str] = Form("#128C7E"),
    scheduled_at: Optional[str] = Form(None),
    instance_id: Optional[int] = Form(None),
    target_groups: str = Form("[]"),
    is_recurring: bool = Form(False),
    recurrence_days: Optional[list[str]] = Form(None),
    send_time: Optional[str] = Form(None),
    existing_image_url: Optional[str] = Form(None),
    save_mode: str = Form("schedule"),  # "schedule" or "draft"
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    repo = SQLStatusCampaignRepository(db)

    try:
        if scheduled_at:
            # Assume naive input from browser is local (SP) time or convert if Z present
            dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
            scheduled_dt = to_sp(dt)
        else:
            scheduled_dt = now_sp()
    except ValueError:
        scheduled_dt = now_sp()

    try:
        targets = json.loads(target_groups)
    except Exception:
        targets = []

    image_url = None
    if image_file and image_file.filename:
        image_url = await _save_uploaded_image(
            image_file, user=current_user, quality=90, max_size=(1080, 1920)
        )
    elif existing_image_url:
        image_url = existing_image_url

    status = CampaignStatus.DRAFT if save_mode == "draft" else CampaignStatus.SCHEDULED

    campaign = StatusCampaign(
        title=title,
        image_url=image_url,
        background_color=background_color,
        caption=caption,
        link=link,
        price=float(price.replace(".", "").replace(",", ".")) if price else None,
        scheduled_at=scheduled_dt,
        instance_id=instance_id,
        user_id=current_user.id,
        status=status,
        target_contacts=targets,
        is_recurring=is_recurring,
        recurrence_days=(
            ",".join(recurrence_days) if is_recurring and recurrence_days else None
        ),
        send_time=send_time if is_recurring else None,
    )
    repo.save(campaign)

    # Log activity
    from core.infrastructure.database.repositories import SQLActivityRepository
    from core.domain.entities import ActivityLog

    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="status_campaign_create",
            description=f"Created status campaign: {title}",
        )
    )

    return RedirectResponse(url="/status_campaigns", status_code=303)


@router.get("/status_campaigns/edit/{campaign_id}", response_class=HTMLResponse)
async def edit_status_campaign_form(
    request: Request,
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    repo = SQLStatusCampaignRepository(db)
    campaign = repo.get_by_id(campaign_id, user_id=current_user.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    instance_repo = SQLInstanceRepository(db)
    instances = instance_repo.list_by_user(current_user.id)

    target_repo = SQLTargetRepository(db)
    targets = target_repo.list_all(current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="status_editor.html",
        context={
            "user": current_user,
            "campaign": campaign,
            "instances": instances,
            "targets": targets,
            "title": "Editar Status Automático",
        },
    )


@router.post("/status_campaigns/edit/{campaign_id}")
async def update_status_campaign(
    campaign_id: int,
    title: str = Form(...),
    caption: Optional[str] = Form(None),
    link: Optional[str] = Form(None),
    price: Optional[str] = Form(None),
    background_color: Optional[str] = Form(None),
    scheduled_at: Optional[str] = Form(None),
    instance_id: Optional[int] = Form(None),
    target_groups: str = Form("[]"),
    is_recurring: bool = Form(False),
    recurrence_days: Optional[list[str]] = Form(None),
    send_time: Optional[str] = Form(None),
    image_file: Optional[UploadFile] = File(None),
    save_mode: str = Form("schedule"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    repo = SQLStatusCampaignRepository(db)
    campaign = repo.get_by_id(campaign_id, user_id=current_user.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    try:
        if scheduled_at:
            scheduled_dt = datetime.fromisoformat(scheduled_at.replace("Z", ""))
        else:
            scheduled_dt = campaign.scheduled_at
    except ValueError:
        scheduled_dt = campaign.scheduled_at

    try:
        targets = json.loads(target_groups)
    except Exception:
        targets = []

    if image_file and image_file.filename:
        # If updating image, we should ideally delete the old one from storage
        if campaign.image_url and campaign.image_url.startswith("supabase://"):
            storage_svc = SupabaseStorageService(bucket_name="images")
            storage_svc.delete_image(campaign.image_url)

        image_url = await _save_uploaded_image(
            image_file, user=current_user, quality=90, max_size=(1080, 1920)
        )
        if image_url:
            campaign.image_url = image_url

    campaign.title = title
    campaign.caption = caption
    campaign.link = link
    campaign.price = float(price.replace(".", "").replace(",", ".")) if price else None
    campaign.background_color = background_color or campaign.background_color
    campaign.scheduled_at = scheduled_dt
    campaign.instance_id = instance_id
    campaign.target_contacts = targets
    campaign.is_recurring = is_recurring
    campaign.recurrence_days = (
        ",".join(recurrence_days) if is_recurring and recurrence_days else None
    )
    campaign.send_time = send_time if is_recurring else None

    if save_mode == "draft":
        campaign.status = CampaignStatus.DRAFT
    elif campaign.status in [
        CampaignStatus.SENT,
        CampaignStatus.FAILED,
        CampaignStatus.SENDING,
        CampaignStatus.DRAFT,
    ]:
        campaign.status = CampaignStatus.SCHEDULED

    repo.save(campaign)

    # Log activity
    from core.infrastructure.database.repositories import SQLActivityRepository
    from core.domain.entities import ActivityLog

    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="status_campaign_edit",
            description=f"Updated status campaign: {title}",
        )
    )

    return RedirectResponse(url="/status_campaigns", status_code=303)


@router.get("/status_campaigns/duplicate/{campaign_id}", response_class=HTMLResponse)
async def duplicate_status_campaign(
    campaign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    repo = SQLStatusCampaignRepository(db)
    original = repo.get_by_id(campaign_id, user_id=current_user.id)
    if not original:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Clear ID to treat as NEW and reset status/date
    original.id = None
    original.status = CampaignStatus.DRAFT
    original.scheduled_at = now_sp()

    instance_repo = SQLInstanceRepository(db)
    instances = instance_repo.list_by_user(current_user.id)
    target_repo = SQLTargetRepository(db)
    targets = target_repo.list_all(current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="status_editor.html",
        context={
            "user": current_user,
            "campaign": original,
            "instances": instances,
            "targets": targets,
            "title": "Duplicar Status Automático",
        },
    )





@router.post("/status_campaigns/improve-ai")
async def improve_status_caption(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    link: Optional[str] = Form(None),
    current_user: UserModel = Depends(login_required),
):
    """
    Leverages AI to improve a status caption based on user description and title.
    """
    ai_service = OpenAIService()

    prompt = (
        f"Melhore esta legenda para um Status de WhatsApp.\n\n"
        f"Título do Status: {title}\n"
        f"Descrição/Ideia do usuário: {description}\n\n"
        f"Instruções:\n"
        f"1. Seja persuasivo e profissional.\n"
        f"2. Use emojis de forma estratégica.\n"
        f"3. O texto deve ser conciso (ideais para leitura rápida no Status).\n"
        f"4. Foque em converter o interesse em uma ação (ex: 'Me chama no PV').\n"
        f"5. Responda APENAS com a legenda sugerida, sem comentários extras.\n"
    )

    if link:
        prompt += f"6. MANTENHA ESTE LINK {link} NA MENSAGEM EXATAMENTE COMO ESTÁ.\n"

    improved_text = await ai_service.chat(prompt)
    return {"improved_text": improved_text}


@router.get("/status_campaigns/{campaign_id}", response_class=HTMLResponse)
async def view_status_campaign(
    campaign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    repo = SQLStatusCampaignRepository(db)
    campaign = repo.get_by_id(campaign_id, user_id=current_user.id)
    if not campaign:
        return RedirectResponse(url="/status_campaigns", status_code=303)
    instance = db.query(InstanceModel).filter_by(id=campaign.instance_id).first()
    instance_name = instance.name if instance else "Padrão"

    target_names = []
    if campaign.target_contacts:
        for jid in campaign.target_contacts or []:
            tm = (
                db.query(WhatsAppTargetModel)
                .filter_by(user_id=current_user.id, jid=jid)
                .first()
            )
            if tm and tm.name:
                target_names.append(tm.name)
            else:
                target_names.append(jid)

    return templates.TemplateResponse(
        request=request,
        name="status_campaign_detail.html",
        context={
            "user": current_user,
            "title": f"Detalhes: {campaign.title}",
            "campaign": campaign,
            "instance_name": instance_name,
        },
    )


@router.post("/status_campaigns/delete/{campaign_id}")
async def delete_status_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    repo = SQLStatusCampaignRepository(db)
    campaign = repo.get_by_id(campaign_id, user_id=current_user.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Delete from Supabase Storage first
    if campaign.image_url and campaign.image_url.startswith("supabase://"):
        try:
            storage_svc = SupabaseStorageService(bucket_name="images")
            storage_svc.delete_image(campaign.image_url)
        except Exception as e:
            logger.warning("Failed to delete image from storage: %s", e)

    success = repo.delete(campaign_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="status_campaign_delete",
            description=f"Deleted status campaign: {campaign.title}",
        )
    )

    return RedirectResponse(url="/status_campaigns", status_code=303)
    
@router.post("/status_campaigns/pause/{campaign_id}")
async def pause_status_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    from core.infrastructure.database.models import StatusCampaignModel
    campaign = db.query(StatusCampaignModel).filter(StatusCampaignModel.id == campaign_id, StatusCampaignModel.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "paused"
    db.commit()
    return {"success": True, "status": "paused"}


@router.post("/status_campaigns/resume/{campaign_id}")
async def resume_status_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    from core.infrastructure.database.models import StatusCampaignModel
    campaign = db.query(StatusCampaignModel).filter(StatusCampaignModel.id == campaign_id, StatusCampaignModel.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "scheduled"
    db.commit()
    return {"success": True, "status": "scheduled"}


@router.post("/status_campaigns/cancel/{campaign_id}")
async def cancel_status_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    from core.infrastructure.database.models import StatusCampaignModel
    campaign = db.query(StatusCampaignModel).filter(StatusCampaignModel.id == campaign_id, StatusCampaignModel.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "canceled"
    db.commit()
    return {"success": True, "status": "canceled"}


@router.post("/status_campaigns/resend/{campaign_id}")
async def resend_status_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    from core.infrastructure.database.models import StatusCampaignModel
    campaign = db.query(StatusCampaignModel).filter(StatusCampaignModel.id == campaign_id, StatusCampaignModel.user_id == current_user.id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.status = "scheduled"
    campaign.sent_at = None
    if not campaign.is_recurring:
        from core.infrastructure.utils.timezone import now_sp
        campaign.scheduled_at = now_sp()
        
    db.commit()
    return {"success": True, "status": "scheduled"}
