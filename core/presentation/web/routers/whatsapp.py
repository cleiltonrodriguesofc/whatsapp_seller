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
from core.infrastructure.database.repositories import (
    SQLTargetRepository,
    SQLActivityRepository,
)
from core.infrastructure.database.models import UserModel, InstanceModel
from core.domain.entities import ActivityLog
from core.infrastructure.database.session import get_db
from core.infrastructure.notifications.evolution_whatsapp import (
    EvolutionWhatsAppService,
)
from core.presentation.web.dependencies import login_required, templates

logger = logging.getLogger(__name__)

router = APIRouter(tags=["whatsapp"])


@router.get("/whatsapp/connect", response_class=HTMLResponse)
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
        context={
            "request": request,
            "instances": instances,
            "user": current_user,
            "title": "Configuração WhatsApp",
        },
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
        activity_repo.save(
            ActivityLog(
                user_id=current_user.id,
                event_type="instance_create",
                description=f"Created new WhatsApp instance: {name} ({full_name})",
            )
        )

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
        .filter(
            InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id
        )
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


@router.post("/whatsapp/connect-phone/{instance_id}")
async def request_pairing_code_api(
    instance_id: int,
    phone: str = Form(...),
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
        apikey=instance_model.apikey,
    )
    code = await whatsapp_service.request_pairing_code(phone)
    if code:
        return {"success": True, "code": code}
    return {"success": False, "error": "Failed to generate pairing code"}
    return {"success": False, "error": "Failed to generate QR code"}


@router.get("/whatsapp/status")
async def get_global_whatsapp_status(
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instances = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).all()
    )
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
        .filter(
            InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id
        )
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
    from core.infrastructure.database.models import (
        StatusCampaignModel,
        CampaignModel,
        BroadcastCampaignModel,
        WhatsAppTargetModel,
        BroadcastListModel,
    )

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
        apikey=instance_model.apikey,
    )
    await whatsapp_service.delete_instance()

    # nullify all fk references before deleting to avoid IntegrityError
    db.query(StatusCampaignModel).filter(
        StatusCampaignModel.instance_id == instance_id
    ).update({"instance_id": None})
    db.query(CampaignModel).filter(
        CampaignModel.instance_id == instance_id
    ).update({"instance_id": None})
    db.query(WhatsAppTargetModel).filter(
        WhatsAppTargetModel.instance_id == instance_id
    ).update({"instance_id": None})
    db.query(BroadcastListModel).filter(
        BroadcastListModel.instance_id == instance_id
    ).update({"instance_id": None})
    # broadcast_campaigns has NOT NULL fk — delete orphaned campaigns
    db.query(BroadcastCampaignModel).filter(
        BroadcastCampaignModel.instance_id == instance_id
    ).delete()

    db.delete(instance_model)
    db.commit()

    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="instance_delete",
            description=f"Deleted WhatsApp instance: {instance_model.display_name}",
        )
    )

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
        .filter(
            InstanceModel.id == instance_id, InstanceModel.user_id == current_user.id
        )
        .first()
    )
    if not instance_model:
        return {"success": False, "error": "Instance not found"}

    instance_model.display_name = new_name
    db.commit()

    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="instance_rename",
            description=f"Renamed WhatsApp instance to: {new_name}",
        )
    )

    return {"success": True}


@router.post("/whatsapp/logout/{instance_id}")
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
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="instance_logout",
            description=f"Logged out from WhatsApp instance: {instance_model.display_name}",
        )
    )

    return {"success": True}


@router.get("/whatsapp/groups/{instance_id}")
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
        apikey=instance_model.apikey,
    )

    groups = await whatsapp_service.get_groups()
    chats = await whatsapp_service.get_contacts()
    phonebook = await whatsapp_service.get_phonebook_contacts()

    target_map = {}
    for g in groups:
        gid = g.get("id")
        if gid:
            subject = g.get("subject") or g.get("name")
            target_map[gid] = {
                "id": gid,
                "subject": subject if subject else gid.split("@")[0],
            }

    for c in chats:
        jid = c.get("remoteJid") or c.get("id")
        if jid and jid not in target_map:
            name = c.get("name") or c.get("pushName")
            target_map[jid] = {
                "id": jid,
                "subject": name if name else jid.split("@")[0],
            }

    for p in phonebook:
        jid = p.get("remoteJid") or p.get("id")
        if not jid:
            continue
        name = p.get("name") or p.get("pushName") or p.get("notify") or jid
        if jid not in target_map or target_map[jid]["subject"] == jid:
            target_map[jid] = {"id": jid, "subject": name}

    targets = list(target_map.values())

    return {"success": True, "groups": targets}


@router.get("/whatsapp/sync")
async def sync_whatsapp_targets(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    """Force a sync from Evolution API to the local database."""
    instance_model = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).first()
    )
    if not instance_model:
        return {"success": False, "error": "No instance provisioned"}

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name,
        apikey=instance_model.apikey,
    )
    target_repo = SQLTargetRepository(db)

    groups = await whatsapp_service.get_groups()
    chats = await whatsapp_service.get_contacts()

    # normalize lists (api may return {"data": [...]})
    g_list = groups.get("data", groups) if isinstance(groups, dict) else groups
    c_list = chats.get("data", chats) if isinstance(chats, dict) else chats

    if not isinstance(g_list, list):
        g_list = []
    if not isinstance(c_list, list):
        c_list = []

    targets = g_list + c_list

    if targets:
        target_repo.upsert_sync(
            targets, user_id=current_user.id, instance_id=instance_model.id
        )

    return {"success": True, "count": len(targets)}


@router.post("/whatsapp/test")
async def send_test_message(
    phone: str = Form(...),
    message: str = Form(...),
    current_user: UserModel = Depends(login_required),
    db: Session = Depends(get_db),
):
    instance_model = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).first()
    )
    whatsapp_service = EvolutionWhatsAppService(
        instance=instance_model.name if instance_model else None,
        apikey=instance_model.apikey if instance_model else None,
    )
    success = await whatsapp_service.send_text(phone, message)

    if success:
        # Log activity
        activity_repo = SQLActivityRepository(db)
        activity_repo.save(
            ActivityLog(
                user_id=current_user.id,
                event_type="whatsapp_test",
                description=f"Sent test message to: {phone}",
            )
        )

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
        success = await use_case.execute(
            jid, message or "Olá! Esta é uma mensagem automática."
        )
        return {"status": "success" if success else "failed", "action": action}

    if action == "pulse":
        return {"status": "alive", "action": action}

    return {"status": "received", "action": action}


@router.get("/chats", response_class=HTMLResponse)
async def view_whatsapp_chats(
    request: Request,
    instance_id: Optional[int] = Query(None),
    open_jid: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    """
    WhatsApp inbox view - loads active chats from Evolution API.
    """
    instances = (
        db.query(InstanceModel).filter(InstanceModel.user_id == current_user.id).all()
    )

    selected_instance = None
    chats = []

    if instances:
        if instance_id:
            selected_instance = (
                db.query(InstanceModel)
                .filter(
                    InstanceModel.id == instance_id,
                    InstanceModel.user_id == current_user.id,
                )
                .first()
            )
        if not selected_instance:
            selected_instance = instances[0]

        if selected_instance:
            whatsapp_service = EvolutionWhatsAppService(
                instance=selected_instance.name,
                apikey=selected_instance.apikey,
            )
            raw_chats = await whatsapp_service.get_active_chats()
            # normalize chat data for the template
            for c in raw_chats:
                if isinstance(c, dict):
                    chat_id = c.get("remoteJid") or c.get("id") or c.get("jid") or ""
                    chats.append(
                        {
                            "id": chat_id,
                            "name": c.get("name")
                            or c.get("pushName")
                            or c.get("subject")
                            or chat_id.split("@")[0],
                            "profilePicUrl": c.get("profilePicUrl") or "",
                            "unreadCount": c.get("unreadCount") or 0,
                            "lastMsgTimestamp": c.get("lastMsgTimestamp") or 0,
                            "isGroup": "@g.us" in chat_id,
                        }
                    )
            # sort by most recent message
            chats.sort(key=lambda x: x.get("lastMsgTimestamp", 0), reverse=True)

    return templates.TemplateResponse(
        request=request,
        name="chats.html",
        context={
            "user": current_user,
            "title": "Conversas Ativas",
            "chats": chats,
            "instances": instances,
            "selected_instance": selected_instance,
            "open_jid": open_jid or "",
        },
    )


@router.get("/chats/messages")
async def get_chat_messages_api(
    request: Request,
    jid: str = Query(...),
    instance_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    """
    API endpoint to fetch message history for a specific chat.
    """
    instance = (
        db.query(InstanceModel)
        .filter(
            InstanceModel.id == instance_id,
            InstanceModel.user_id == current_user.id,
        )
        .first()
    )

    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    whatsapp_service = EvolutionWhatsAppService(
        instance=instance.name,
        apikey=instance.apikey,
    )
    messages = await whatsapp_service.get_chat_messages(jid, limit=50)

    # normalize message data
    normalized = []
    for msg in messages:
        if isinstance(msg, dict):
            key = msg.get("key", {})
            message_content = msg.get("message", {})
            # extract text from various message types
            text = (
                (
                    message_content.get("conversation")
                    or message_content.get("extendedTextMessage", {}).get("text")
                    or message_content.get("imageMessage", {}).get("caption")
                    or message_content.get("videoMessage", {}).get("caption")
                    or ""
                )
                if isinstance(message_content, dict)
                else str(message_content)
                if message_content
                else ""
            )

            # detect message type
            msg_type = "text"
            if isinstance(message_content, dict):
                if "imageMessage" in message_content:
                    msg_type = "image"
                elif "videoMessage" in message_content:
                    msg_type = "video"
                elif "audioMessage" in message_content:
                    msg_type = "audio"
                elif "documentMessage" in message_content:
                    msg_type = "document"
                elif "stickerMessage" in message_content:
                    msg_type = "sticker"

            normalized.append(
                {
                    "id": key.get("id", ""),
                    "fromMe": key.get("fromMe", False),
                    "remoteJid": key.get("remoteJid", ""),
                    "text": text,
                    "type": msg_type,
                    "timestamp": msg.get("messageTimestamp")
                    or msg.get("messageTimestamp", 0),
                    "pushName": msg.get("pushName", ""),
                }
            )

    # sort by timestamp ascending (oldest first)
    normalized.sort(key=lambda x: x.get("timestamp", 0))

    return {"messages": normalized}
