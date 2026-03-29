import logging

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from core.infrastructure.database.models import UserModel, InstanceModel, WhatsAppTargetModel
from core.infrastructure.database.session import get_db
from core.infrastructure.database.repositories import (
    SQLTargetRepository,
    SQLInstanceRepository,
    SQLBroadcastListRepository,
    SQLBroadcastCampaignRepository,
)
from core.domain.entities import BroadcastList, BroadcastCampaign
from core.presentation.web.dependencies import login_required, templates
from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService
from core.infrastructure.ai.openai_service import OpenAIService
from core.infrastructure.utils.timezone import now_sp, to_sp

router = APIRouter(prefix="/broadcast", tags=["broadcast"])

@router.get("/", response_class=HTMLResponse)
async def broadcast_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    list_repo = SQLBroadcastListRepository(db)
    campaign_repo = SQLBroadcastCampaignRepository(db)
    target_repo = SQLTargetRepository(db)
    
    contacts = target_repo.list_contacts(current_user.id)
    groups = target_repo.list_groups(current_user.id)
    lists = list_repo.list_all(current_user.id)
    campaigns = campaign_repo.list_all(current_user.id)
    
    return templates.TemplateResponse(
        request=request,
        name="broadcast_dashboard.html",
        context={
            "user": current_user,
            "title": "Broadcast",
            "contact_count": len(contacts),
            "group_count": len(groups),
            "list_count": len(lists),
            "campaign_count": len(campaigns),
            "latest_campaigns": campaigns[:5],
        },
    )

@router.get("/contacts", response_class=HTMLResponse)
async def broadcast_contacts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    target_repo = SQLTargetRepository(db)
    contacts = target_repo.list_contacts(current_user.id)
    
    return templates.TemplateResponse(
        request=request,
        name="broadcast_contacts.html",
        context={
            "user": current_user,
            "title": "Meus Contatos",
            "contacts": contacts,
        },
    )

@router.get("/groups", response_class=HTMLResponse)
async def broadcast_groups(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    target_repo = SQLTargetRepository(db)
    groups = target_repo.list_groups(current_user.id)
    
    return templates.TemplateResponse(
        request=request,
        name="broadcast_groups.html",
        context={
            "user": current_user,
            "title": "Meus Grupos",
            "groups": groups,
        },
    )

@router.post("/sync")
async def sync_broadcast_targets(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    """
    Syncs contacts and groups from all active instances for the user.
    Accepts optional 'next' form field to control redirect destination.
    """
    form = await request.form()
    redirect_to = form.get("next", "/broadcast/contacts")
    sync_logger = logging.getLogger("broadcast.sync")

    instance_repo = SQLInstanceRepository(db)
    target_repo = SQLTargetRepository(db)
    instances = instance_repo.list_by_user(current_user.id)

    total_groups = 0
    total_contacts = 0
    errors = []

    for inst in instances:
        if not inst.name or not inst.apikey:
            sync_logger.warning("skipping instance with missing name/apikey: id=%s", inst.id)
            continue

        whatsapp_service = EvolutionWhatsAppService(instance=inst.name, apikey=inst.apikey)

        # Sync groups
        try:
            groups = await whatsapp_service.get_groups()
            sync_logger.info("fetched %d groups from instance %s", len(groups or []), inst.name)
            if groups:
                target_repo.upsert_sync(groups, current_user.id)
                total_groups += len(groups)
        except Exception as e:
            msg = f"groups sync error for {inst.name}: {e}"
            sync_logger.error(msg)
            errors.append(msg)

        # Sync contacts
        try:
            contacts = await whatsapp_service.get_contacts()
            sync_logger.info("fetched %d contacts from instance %s", len(contacts or []), inst.name)
            if contacts:
                target_repo.upsert_sync(contacts, current_user.id)
                total_contacts += len(contacts)
        except Exception as e:
            msg = f"contacts sync error for {inst.name}: {e}"
            sync_logger.error(msg)
            errors.append(msg)

    sync_logger.info(
        "sync complete: %d groups, %d contacts synced for user %s",
        total_groups, total_contacts, current_user.id
    )

    return RedirectResponse(url=redirect_to, status_code=303)



# ── Broadcast Lists ───────────────────────────────────────────────────────────


@router.get("/lists", response_class=HTMLResponse)
async def list_broadcast_lists(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    list_repo = SQLBroadcastListRepository(db)
    broadcast_lists = list_repo.list_all(current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="broadcast_lists.html",
        context={
            "user": current_user,
            "title": "Minhas Listas",
            "lists": broadcast_lists,
        },
    )


@router.get("/lists/new", response_class=HTMLResponse)
async def new_broadcast_list(
    request: Request,
    current_user: UserModel = Depends(login_required),
):
    return templates.TemplateResponse(
        request=request,
        name="broadcast_list_editor.html",
        context={
            "user": current_user,
            "title": "Nova Lista",
            "broadcast_list": None,
        },
    )


@router.post("/lists/new")
async def create_broadcast_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    form_data = await request.form()
    name = form_data.get("name")
    description = form_data.get("description")
    jids_raw = form_data.get("jids", "[]")

    import json

    jids = json.loads(jids_raw)  # expected from frontend UI selection

    list_repo = SQLBroadcastListRepository(db)
    new_list = BroadcastList(
        user_id=current_user.id, name=name, description=description
    )
    new_list = list_repo.save(new_list)

    # resolve target info from JIDs
    members = []
    for jid in jids:
        model = db.query(WhatsAppTargetModel).filter_by(user_id=current_user.id, jid=jid).first()
        if model:
            members.append({
                "jid": jid,
                "name": model.name,
                "type": model.type
            })

    list_repo.set_members(new_list.id, members)

    return RedirectResponse(url="/broadcast/lists", status_code=303)


@router.post("/lists/{list_id}/delete")
async def delete_broadcast_list(
    list_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    list_repo = SQLBroadcastListRepository(db)
    list_repo.delete(list_id, current_user.id)
    return RedirectResponse(url="/broadcast/lists", status_code=303)



# ── Broadcast Campaigns ──────────────────────────────────────────────────────


@router.get("/campaigns", response_class=HTMLResponse)
async def list_broadcast_campaigns(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLBroadcastCampaignRepository(db)
    campaigns = campaign_repo.list_all(current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="broadcast_campaign_list.html",
        context={
            "user": current_user,
            "title": "Minhas Campanhas",
            "campaigns": campaigns,
        },
    )


@router.get("/campaigns/new", response_class=HTMLResponse)
async def new_broadcast_campaign(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
    list_id: Optional[int] = None,
):
    instance_repo = SQLInstanceRepository(db)
    instances = instance_repo.list_by_user(current_user.id)
    
    list_repo = SQLBroadcastListRepository(db)
    broadcast_lists = list_repo.list_all(current_user.id)
    
    target_repo = SQLTargetRepository(db)
    contacts = target_repo.list_contacts(current_user.id)
    groups = target_repo.list_groups(current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="broadcast_campaign_editor.html",
        context={
            "user": current_user,
            "title": "Nova Campanha",
            "campaign": None,
            "instances": instances,
            "lists": broadcast_lists,
            "contacts": contacts,
            "groups": groups,
            "selected_list_id": list_id,
        },
    )


@router.get("/campaigns/edit/{campaign_id}", response_class=HTMLResponse)
async def edit_broadcast_campaign(
    campaign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLBroadcastCampaignRepository(db)
    campaign = campaign_repo.get_by_id(campaign_id, current_user.id)
    if not campaign:
        return RedirectResponse(url="/broadcast/campaigns", status_code=303)

    instance_repo = SQLInstanceRepository(db)
    instances = instance_repo.list_by_user(current_user.id)

    list_repo = SQLBroadcastListRepository(db)
    broadcast_lists = list_repo.list_all(current_user.id)

    target_repo = SQLTargetRepository(db)
    contacts = target_repo.list_contacts(current_user.id)
    groups = target_repo.list_groups(current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="broadcast_campaign_editor.html",
        context={
            "user": current_user,
            "title": "Editar Campanha",
            "campaign": campaign,
            "instances": instances,
            "lists": broadcast_lists,
            "contacts": contacts,
            "groups": groups,
            "selected_list_id": campaign.list_id,
        },
    )


@router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
async def view_broadcast_campaign(
    campaign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLBroadcastCampaignRepository(db)
    campaign = campaign_repo.get_by_id(campaign_id, current_user.id)
    if not campaign:
        return RedirectResponse(url="/broadcast/campaigns", status_code=303)

    instance = db.query(InstanceModel).filter_by(id=campaign.instance_id).first()
    instance_name = instance.name if instance else "Desconhecida"

    target_names = []
    target_repo = SQLTargetRepository(db)
    
    if campaign.target_type == "list" and campaign.list_id:
        from core.infrastructure.database.models import BroadcastListMemberModel
        members = target_repo.db.query(BroadcastListMemberModel).filter_by(list_id=campaign.list_id).all()
        target_names = [m.target_name for m in members]
    else:
        jids = campaign.target_jids or []
            
        from core.infrastructure.database.models import WhatsAppTargetModel
        for jid in jids:
            tm = db.query(WhatsAppTargetModel).filter_by(user_id=current_user.id, jid=jid).first()
            if tm and tm.name:
                target_names.append(tm.name)
            else:
                target_names.append(jid)

    return templates.TemplateResponse(
        request=request,
        name="broadcast_campaign_detail.html",
        context={
            "user": current_user,
            "title": f"Detalhes: {campaign.title}",
            "campaign": campaign,
            "instance_name": instance_name,
            "target_names": target_names,
        },
    )


@router.post("/improve-ai")
async def improve_broadcast_caption(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    target_type: Optional[str] = Form("contacts"),
    current_user: UserModel = Depends(login_required),
):
    """
    Leverages AI to improve a broadcast message based on user description and target type.
    """
    ai_service = OpenAIService()

    # Contextual prompt based on target type
    if target_type == "contacts":
        context_instr = (
            "Esta mensagem é para CONTATOS INDIVIDUAIS.\n"
            "Use a variável {nome} no início para uma saudação pessoal (ex: 'Olá {nome}, tudo bem?').\n"
            "O tom deve ser amigável, pessoal e persuasivo."
        )
    else:
        context_instr = (
            "Esta mensagem é para GRUPOS ou LISTAS.\n"
            "O tom deve ser direto, profissional e focado em um anúncio geral (broadcast).\n"
            "NÃO use a variável {nome} aqui."
        )

    prompt = (
        f"Melhore esta mensagem para um Broadcast de WhatsApp.\n\n"
        f"Título/Assunto: {title}\n"
        f"Ideia do que enviar: {description}\n\n"
        f"Instruções:\n"
        f"1. {context_instr}\n"
        f"2. Use emojis de forma estratégica.\n"
        f"3. Responda APENAS com a mensagem sugerida, sem comentários extras.\n"
    )

    improved_text = await ai_service.chat(prompt)
    return {"improved_text": improved_text}


@router.post("/campaigns/new")
async def create_broadcast_campaign(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    return await _save_campaign(request, db, current_user)


@router.post("/campaigns/edit/{campaign_id}")
async def update_broadcast_campaign(
    campaign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    return await _save_campaign(request, db, current_user, campaign_id)


async def _save_campaign(request, db, current_user, campaign_id=None):
    form_data = await request.form()

    title = form_data.get("title")
    instance_id = int(form_data.get("instance_id"))
    target_type = form_data.get("target_type")
    list_id = form_data.get("list_id")
    message = form_data.get("message")
    scheduled_at_str = form_data.get("scheduled_at")
    is_recurring = form_data.get("is_recurring") == "true"
    recurrence_days = ",".join(form_data.getlist("recurrence_days"))
    send_time = form_data.get("send_time")
    
    # Save mode (draft vs schedule)
    save_mode = form_data.get("save_mode", "schedule")
    orig_status = form_data.get("status", "scheduled")
    is_now = (orig_status == "sending")
    
    status = "scheduled" 
    if save_mode == "draft":
        status = "draft"

    image_url = form_data.get("existing_image_url")
    image_file = form_data.get("image")
    if hasattr(image_file, "filename") and image_file.filename:
        from core.presentation.web.routers.products import _save_uploaded_image
        image_url = await _save_uploaded_image(image_file, current_user.id)

    target_jids = []
    if target_type in ["contacts", "groups"]:
        target_jids = form_data.getlist("target_jids")

    scheduled_at = None
    if scheduled_at_str:
        try:
            # Assume browser input is local SP time or convert if Z present
            dt_raw = datetime.fromisoformat(scheduled_at_str.replace("Z", "+00:00"))
            scheduled_at = to_sp(dt_raw)
        except Exception:
            pass
    
    if is_now and not scheduled_at:
        scheduled_at = now_sp()

    campaign_repo = SQLBroadcastCampaignRepository(db)
    
    if campaign_id:
        campaign = campaign_repo.get_by_id(campaign_id, current_user.id)
        if not campaign:
            return RedirectResponse(url="/broadcast/campaigns", status_code=303)
        
        campaign.title = title
        campaign.instance_id = instance_id
        campaign.target_type = target_type
        campaign.target_jids = target_jids
        campaign.list_id = int(list_id) if list_id else None
        campaign.message = message
        campaign.image_url = image_url
        campaign.scheduled_at = scheduled_at
        campaign.is_recurring = is_recurring
        campaign.recurrence_days = recurrence_days
        campaign.send_time = send_time
        # don't reset status if it was already sent/failed unless edited to schedule?
        # for now, follow the UI's suggested status
        campaign.status = status
    else:
        campaign = BroadcastCampaign(
            user_id=current_user.id,
            instance_id=instance_id,
            title=title,
            target_type=target_type,
            target_jids=target_jids,
            list_id=int(list_id) if list_id else None,
            message=message,
            image_url=image_url,
            scheduled_at=scheduled_at or (dt_mod.datetime.now() if status == "sending" else None),
            is_recurring=is_recurring,
            recurrence_days=recurrence_days,
            send_time=send_time,
            status=status,
        )
    
    campaign_repo.save(campaign)
    return RedirectResponse(url="/broadcast/campaigns", status_code=303)


@router.post("/campaigns/{campaign_id}/delete")
async def delete_broadcast_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLBroadcastCampaignRepository(db)
    campaign_repo.delete(campaign_id, current_user.id)
    return RedirectResponse(url="/broadcast/campaigns", status_code=303)
