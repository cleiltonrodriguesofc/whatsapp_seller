"""
WhatsApp instance management routes.
"""

import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from core.application.use_cases.sales_agent_campaign import SalesAgentCampaignUseCase
from core.infrastructure.database.repositories import SQLTargetRepository, SQLActivityRepository
from core.infrastructure.database.models import UserModel, InstanceModel
from core.domain.entities import ActivityLog
from core.infrastructure.database.session import get_db
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService
from core.presentation.web.dependencies import login_required, templates

logger = logging.getLogger(__name__)

router = APIRouter(tags=["whatsapp"])


@router.get("/whatsapp/connect", response_class=HTMLResponse)
async def connect_whatsapp_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    instances = db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).all()
    return templates.TemplateResponse(
        name="connect_whatsapp.html", 
        context={
            "request": request, 
            "instances": instances, 
            "user": current_user,
            "title": "Configuração WhatsApp"
        }
    )


@router.post("/whatsapp/instance/new")
async def create_new_instance(
    name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    safe_name = name.lower().replace(" ", "_").strip()
    full_name = f"{safe_name}_{current_user.id}_{uuid.uuid4().hex[:4]}"

    whatsapp_service = EvolutionWhatsAppService()
    instance_data = await whatsapp_service.create_instance(full_name, display_name=name)

    if instance_data and isinstance(instance_data, dict):
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
        
        # Log activity
        activity_repo = SQLActivityRepository(db)
        activity_repo.save(ActivityLog(
            user_id=current_user.id, 
            event_type="instance_create", 
            description=f"Created new WhatsApp instance: {name} ({full_name})"
        ))
        
        return {"success": True, "instance_id": new_instance.id}

    logger.error("failed to create instance. response type: %s", type(instance_data))
    return {
        "success": False,
        "error": "Failed to create instance or invalid response from Evolution API",
    }


@router.post("/whatsapp/connect/{instance_id}")
async def get_whatsapp_qr(
    instance_id: int,
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id)
        .first()
    )
    if not instance_model:
        return {"success": False, "error": "Instance not found"}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey,
    )
    qrcode_base64 = await whatsapp_service.get_qrcode()
    if qrcode_base64:
        return {"success": True, "qrcode": qrcode_base64}
    return {"success": False, "error": "Failed to generate QR code"}


@router.get("/whatsapp/status")
async def get_global_whatsapp_status(
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instances = db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).all()
    if not instances:
        return {"connected": False}

    for instance in instances:
        whatsapp_service = EvolutionWhatsAppService(
            instance=instance.name,
            apikey=instance.apikey,
        )
        status = await whatsapp_service.get_status()
        if status.get("connected"):
            return {"connected": True}

    return {"connected": False}


@router.get("/whatsapp/status/{instance_id}")
async def get_whatsapp_status(
    instance_id: int,
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id)
        .first()
    )
    if not instance_model:
        return {"status": "not_found", "connected": False}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey,
    )
    status = await whatsapp_service.get_status()
    status["instance_name"] = instance_model.name
    status["instance_id"] = instance_model.id
    return status


@router.post("/whatsapp/delete/{instance_id}")
async def delete_whatsapp(
    instance_id: int,
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id)
        .first()
    )
    if not instance_model:
        return {"success": False}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey,
    )
    await whatsapp_service.delete_instance()
    db.delete(instance_model)
    db.commit()
    
    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(ActivityLog(
        user_id=current_user.id, 
        event_type="instance_delete", 
        description=f"Deleted WhatsApp instance: {instance_model.display_name}"
    ))
    
    return {"success": True}


@router.post("/whatsapp/rename/{instance_id}")
async def rename_whatsapp(
    instance_id: int,
    new_name: str = Form(...),
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id)
        .first()
    )
    if not instance_model:
        return {"success": False, "error": "Instance not found"}

    instance_model.display_name = new_name
    db.commit()
    
    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(ActivityLog(
        user_id=current_user.id, 
        event_type="instance_rename", 
        description=f"Renamed WhatsApp instance to: {new_name}"
    ))
    
    return {"success": True}


@router.post("/whatsapp/logout/{instance_id}")
async def logout_whatsapp(
    instance_id: int,
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id)
        .first()
    )
    if not instance_model:
        return {"success": False}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey,
    )
    await whatsapp_service.logout_instance()

    for _ in range(10):
        status_data = await whatsapp_service.get_status()
        if status_data and isinstance(status_data, dict):
            inst_data = status_data.get("instance", {})
            if inst_data.get("state") != "open":
                break
        await asyncio.sleep(1)

    instance_model.status = "disconnected"
    db.commit()
    
    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(ActivityLog(
        user_id=current_user.id, 
        event_type="instance_logout", 
        description=f"Logged out from WhatsApp instance: {instance_model.display_name}"
    ))
    
    return {"success": True}


@router.get("/whatsapp/groups/{instance_id}")
async def get_whatsapp_groups(
    instance_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    instance_model = (
        db.query(InstanceModel)
        .filter(InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id)
        .first()
    )
    if not instance_model:
        return {"success": False, "error": "Instance not found"}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey,
    )

    groups = await whatsapp_service.get_groups()
    chats = await whatsapp_service.get_contacts()

    targets = []
    for g in groups:
        targets.append({"id": g.get("id"), "subject": g.get("subject") or g.get("name")})
    for c in chats:
        targets.append({"id": c.get("id"), "subject": c.get("name") or c.get("id")})

    return {"success": True, "groups": targets}


@router.get("/whatsapp/sync")
async def sync_whatsapp_targets(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    """Force a sync from Evolution API to the local database."""
    instance_model = db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).first()
    if not instance_model:
        return {"success": False, "error": "No instance provisioned"}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey,
    )
    target_repo = SQLTargetRepository(db)

    groups = await whatsapp_service.get_groups()
    chats = await whatsapp_service.get_contacts()

    targets = []
    for g in groups:
        targets.append({"id": g.get("id"), "subject": g.get("subject") or g.get("name")})
    for c in chats:
        targets.append({"id": c.get("id"), "subject": c.get("name") or c.get("id")})

    if targets:
        target_repo.upsert_sync(targets, user_id=current_user.id, instance_id=instance_model.id)

    return {"success": True, "count": len(targets)}


@router.post("/whatsapp/test")
async def send_test_message(
    phone: str = Form(...),
    message: str = Form(...),
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).first()
    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name if instance_model else None,
        apikey=instance_model.apikey if instance_model else None,
    )
    success = await whatsapp_service.send_text(phone, message)
    
    if success:
        # Log activity
        activity_repo = SQLActivityRepository(db)
        activity_repo.save(ActivityLog(
            user_id=current_user.id, 
            event_type="whatsapp_test", 
            description=f"Sent test message to: {phone}"
        ))
        
    return {"success": success}


@router.get("/api/v1/whatsapp/trigger")
@router.post("/api/v1/whatsapp/trigger")
async def whatsapp_webhook_trigger(
    request: Request,
    action: str = Query(...),
    jid: Optional[str] = Query(None),
    message: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Secure endpoint to trigger WhatsApp actions from external systems (e.g. GitHub Actions).
    Protected by X-Trigger-Token header.
    """
    import os as _os

    token = _os.environ.get("TRIGGER_TOKEN")
    header_token = request.headers.get("X-Trigger-Token")

    if not token or header_token != token:
        raise HTTPException(status_code=403, detail="Invalid trigger token")

    whatsapp_service = EvolutionWhatsAppService()

    if action == "campaign":
        use_case = SalesAgentCampaignUseCase(whatsapp_service)
        success = await use_case.execute(jid, message or "Olá! Esta é uma mensagem automática.")
        return {"status": "success" if success else "failed", "action": action}

    if action == "pulse":
        return {"status": "alive", "action": action}

    return {"status": "received", "action": action}
