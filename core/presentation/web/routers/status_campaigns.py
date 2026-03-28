import logging
from datetime import datetime
from typing import Optional
import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from core.domain.entities import StatusCampaign, CampaignStatus
from core.infrastructure.database.models import UserModel
from core.infrastructure.database.repositories import SQLStatusCampaignRepository, SQLInstanceRepository, SQLTargetRepository
from core.infrastructure.database.session import get_db
from core.presentation.web.dependencies import login_required, templates
from core.presentation.web.routers.products import _save_uploaded_image

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
        context={"campaigns": campaigns, "user": current_user, "title": "Status Automático"},
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
            "instances": instances,
            "targets": targets,
            "title": "Novo Status Automático",
        },
    )


@router.post("/status_campaigns/new")
async def create_status_campaign(
    title: str = Form(...),
    image_file: UploadFile = File(...),
    caption: str = Form(""),
    scheduled_at: str = Form(...),
    instance_id: int = Form(...),
    target_groups: str = Form("[]"),
    is_recurring: bool = Form(False),
    recurrence_days: str = Form(None),
    send_time: str = Form(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    repo = SQLStatusCampaignRepository(db)
    
    try:
        scheduled_dt = datetime.fromisoformat(scheduled_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    try:
        targets = json.loads(target_groups)
    except Exception:
        targets = []
        
    image_url = await _save_uploaded_image(image_file, quality=90, max_size=(1080, 1920), bucket="images")
    if not image_url:
        raise HTTPException(status_code=500, detail="Failed to upload image")

    campaign = StatusCampaign(
        title=title,
        image_url=image_url,
        caption=caption,
        scheduled_at=scheduled_dt,
        instance_id=instance_id,
        user_id=current_user.id,
        status=CampaignStatus.SCHEDULED,
        target_contacts=targets,
        is_recurring=is_recurring,
        recurrence_days=recurrence_days if is_recurring else None,
        send_time=send_time if is_recurring else None,
    )
    repo.save(campaign)
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
    caption: str = Form(""),
    scheduled_at: str = Form(...),
    instance_id: int = Form(...),
    target_groups: str = Form("[]"),
    is_recurring: bool = Form(False),
    recurrence_days: str = Form(None),
    send_time: str = Form(None),
    image_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    repo = SQLStatusCampaignRepository(db)
    campaign = repo.get_by_id(campaign_id, user_id=current_user.id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    try:
        scheduled_dt = datetime.fromisoformat(scheduled_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    try:
        targets = json.loads(target_groups)
    except Exception:
        targets = []

    if image_file and image_file.filename:
        image_url = await _save_uploaded_image(image_file, quality=90, max_size=(1080, 1920), bucket="images")
        if image_url:
            campaign.image_url = image_url

    campaign.title = title
    campaign.caption = caption
    campaign.scheduled_at = scheduled_dt
    campaign.instance_id = instance_id
    campaign.target_contacts = targets
    campaign.is_recurring = is_recurring
    campaign.recurrence_days = recurrence_days if is_recurring else None
    campaign.send_time = send_time if is_recurring else None
    
    if campaign.status in [CampaignStatus.SENT, CampaignStatus.FAILED, CampaignStatus.SENDING]:
        campaign.status = CampaignStatus.SCHEDULED

    repo.save(campaign)
    return RedirectResponse(url="/status_campaigns", status_code=303)


@router.post("/status_campaigns/delete/{campaign_id}")
async def delete_status_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    repo = SQLStatusCampaignRepository(db)
    success = repo.delete(campaign_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return RedirectResponse(url="/status_campaigns", status_code=303)
