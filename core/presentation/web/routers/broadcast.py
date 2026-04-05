import logging

from fastapi import APIRouter, Depends, Request, Form, Query, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from core.infrastructure.database.models import (
    UserModel,
    InstanceModel,
    WhatsAppTargetModel,
)
from core.infrastructure.database.session import get_db
from core.infrastructure.database.repositories import (
    SQLTargetRepository,
    SQLInstanceRepository,
    SQLBroadcastListRepository,
    SQLBroadcastCampaignRepository,
    SQLActivityRepository,
)
from core.domain.entities import BroadcastList, BroadcastCampaign, ActivityLog
from core.presentation.web.dependencies import login_required, templates
from core.infrastructure.notifications.evolution_whatsapp import (
    EvolutionWhatsAppService,
)
from core.infrastructure.ai.openai_service import OpenAIService
from core.infrastructure.utils.timezone import now_sp, to_sp
from core.infrastructure.utils.text_utils import parse_contacts_text

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
    instance_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    valid_instance_id = None
    if instance_id and instance_id.isdigit():
        valid_instance_id = int(instance_id)

    target_repo = SQLTargetRepository(db)
    contacts = target_repo.list_contacts(current_user.id, valid_instance_id)

    instance_repo = SQLInstanceRepository(db)
    instances = instance_repo.list_by_user(current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="broadcast_contacts.html",
        context={
            "user": current_user,
            "title": "Meus Contatos",
            "contacts": contacts,
            "instances": instances,
            "selected_instance_id": valid_instance_id,
        },
    )


@router.get("/groups", response_class=HTMLResponse)
async def broadcast_groups(
    request: Request,
    instance_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    valid_instance_id = None
    if instance_id and instance_id.isdigit():
        valid_instance_id = int(instance_id)

    target_repo = SQLTargetRepository(db)
    groups = target_repo.list_groups(current_user.id, valid_instance_id)

    instance_repo = SQLInstanceRepository(db)
    instances = instance_repo.list_by_user(current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="broadcast_groups.html",
        context={
            "user": current_user,
            "title": "Meus Grupos",
            "groups": groups,
            "instances": instances,
            "selected_instance_id": valid_instance_id,
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
            sync_logger.warning(
                "skipping instance with missing name/apikey: id=%s", inst.id
            )
            continue

        whatsapp_service = EvolutionWhatsAppService(
            instance=inst.name, apikey=inst.apikey
        )

        # Sync groups
        try:
            groups = await whatsapp_service.get_groups()
            sync_logger.info(
                "fetched %d groups from instance %s", len(groups or []), inst.name
            )
            if groups:
                target_repo.upsert_sync(groups, current_user.id, instance_id=inst.id)
                total_groups += len(groups)
        except Exception as e:
            msg = f"groups sync error for {inst.name}: {e}"
            sync_logger.error(msg)
            errors.append(msg)

        # Sync contacts
        try:
            contacts = await whatsapp_service.get_contacts()
            sync_logger.info(
                "fetched %d contacts from instance %s", len(contacts or []), inst.name
            )
            if contacts:
                target_repo.upsert_sync(contacts, current_user.id, instance_id=inst.id)
                total_contacts += len(contacts)
        except Exception as e:
            msg = f"contacts sync error for {inst.name}: {e}"
            sync_logger.error(msg)
            errors.append(msg)

    sync_logger.info(
        "sync complete: %d groups, %d contacts synced for user %s",
        total_groups,
        total_contacts,
        current_user.id,
    )

    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="broadcast_sync",
            description=f"Synced targets from active instances: {total_contacts} contacts and {total_groups} groups found",
        )
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
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    instance_repo = SQLInstanceRepository(db)
    instances = instance_repo.list_by_user(current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="broadcast_list_editor.html",
        context={
            "user": current_user,
            "title": "Nova Lista",
            "broadcast_list": None,
            "instances": instances,
        },
    )


@router.get("/api/targets")
async def api_targets(
    instance_id: int,
    target_type: str = Query("chat", pattern="^(chat|group)$"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    target_repo = SQLTargetRepository(db)
    if target_type == "chat":
        items = target_repo.list_contacts(current_user.id, instance_id)
    else:
        items = target_repo.list_groups(current_user.id, instance_id)
    return JSONResponse(
        [{"jid": item.jid, "name": item.name or "Sem Nome"} for item in items]
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

    # resolve target info from JIDs
    members = []
    instance_ids_found = set()
    for jid in jids:
        model = (
            db.query(WhatsAppTargetModel)
            .filter_by(user_id=current_user.id, jid=jid)
            .first()
        )
        if model:
            if model.instance_id:
                instance_ids_found.add(model.instance_id)
            members.append({"jid": jid, "name": model.name, "type": model.type})

    if len(instance_ids_found) > 1:
        from fastapi.responses import HTMLResponse

        return HTMLResponse(
            "<b>Erro de Segurança Anti-Ban:</b> Você selecionou contatos pertencentes a instâncias (números) diferentes. "
            "Uma Lista de Transmissão só pode conter clientes de uma única Instância de origem. <a href='javascript:history.back()'>Voltar</a>",
            status_code=400,
        )

    inferred_instance_id = list(instance_ids_found)[0] if instance_ids_found else None

    list_repo = SQLBroadcastListRepository(db)
    new_list = BroadcastList(
        user_id=current_user.id,
        instance_id=inferred_instance_id,
        name=name,
        description=description,
    )
    new_list = list_repo.save(new_list)
    list_repo.set_members(new_list.id, members)

    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="broadcast_list_create",
            description=f"Created broadcast list: {name}",
        )
    )

    return RedirectResponse(url="/broadcast/lists", status_code=303)


@router.post("/lists/{list_id}/delete")
async def delete_broadcast_list(
    list_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    list_repo = SQLBroadcastListRepository(db)
    list_repo.delete(list_id, current_user.id)

    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="broadcast_list_delete",
            description=f"Deleted broadcast list ID: {list_id}",
        )
    )

    return RedirectResponse(url="/broadcast/lists", status_code=303)

@router.post("/lists/{list_id}/import")
async def import_broadcast_contacts(
    list_id: int,
    request: Request,
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    list_repo = SQLBroadcastListRepository(db)
    b_list = list_repo.get_by_id(list_id, current_user.id)
    if not b_list:
        return RedirectResponse(url="/broadcast/lists", status_code=303)

    content = ""
    if file and file.filename:
        content_bytes = await file.read()
        content = content_bytes.decode("utf-8", errors="ignore")
    elif raw_text:
        content = raw_text

    if content:
        parsed_contacts = parse_contacts_text(content)
        if parsed_contacts:
            target_repo = SQLTargetRepository(db)
            instance_repo = SQLInstanceRepository(db)
            
            # Upsert them to global targets too, assigning to first instance if any
            default_inst = instance_repo.list_by_user(current_user.id)
            inst_id = default_inst[0].id if default_inst else None
            import_payload = [{"id": f"{c['phone']}@s.whatsapp.net", "subject": c["name"]} for c in parsed_contacts]
            if inst_id:
                target_repo.upsert_sync(import_payload, current_user.id, instance_id=inst_id)

            existing_jids = set(list_repo.get_member_jids(list_id))
            added_count = 0
            
            for c in parsed_contacts:
                jid = f"{c['phone']}@s.whatsapp.net"
                if jid not in existing_jids:
                    new_member = BroadcastListMemberModel(
                        list_id=list_id,
                        target_jid=jid,
                        target_name=c["name"],
                        target_type="chat",
                    )
                    db.add(new_member)
                    added_count += 1
            
            db.commit()
            
            # Log activity
            activity_repo = SQLActivityRepository(db)
            activity_repo.save(ActivityLog(
                user_id=current_user.id, 
                event_type="broadcast_list_import", 
                description=f"Imported {added_count} new contacts to list ID: {list_id}"
            ))

    return RedirectResponse(url=f"/broadcast/lists/{list_id}", status_code=303)



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

        members = (
            target_repo.db.query(BroadcastListMemberModel)
            .filter_by(list_id=campaign.list_id)
            .all()
        )
        target_names = [m.target_name for m in members]
    else:
        jids = campaign.target_jids or []

        from core.infrastructure.database.models import WhatsAppTargetModel

        for jid in jids:
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
        name="broadcast_campaign_detail.html",
        context={
            "user": current_user,
            "title": f"Detalhes: {campaign.title}",
            "campaign": campaign,
            "instance_name": instance_name,
            "target_names": target_names,
        },
    )


@router.get("/campaigns/duplicate/{campaign_id}", response_class=HTMLResponse)
async def duplicate_broadcast_campaign(
    campaign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLBroadcastCampaignRepository(db)
    original = campaign_repo.get_by_id(campaign_id, current_user.id)
    if not original:
        return RedirectResponse(url="/broadcast/campaigns", status_code=303)

    # Clear ID and reset status/date for a new entry
    original.id = None
    original.status = "draft"
    original.scheduled_at = now_sp()

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
            "title": "Duplicar Campanha",
            "campaign": original,
            "instances": instances,
            "lists": broadcast_lists,
            "contacts": contacts,
            "groups": groups,
            "selected_list_id": original.list_id,
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
        f"Ideia do que enviar: {description}\n\n"
        f"Instruções:\n"
        f"1. {context_instr}\n"
        f"2. Use emojis de forma estratégica.\n"
        f"3. Responda APENAS E DIRETAMENTE com o CONTEÚDO da mensagem gerada.\n"
        f"4. NUNCA escreva PREFIXOS, nem repita Assunto/Título (exemplo: NÃO comece com 'Assunto:', nem 'Título:', etc).\n"
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

    product_link = form_data.get("product_link", "").strip()
    product_price = form_data.get("product_price", "").strip()

    # Se o usuário preencheu link e/ou preço, não permitimos duplicar se já existirem
    # Mas anexamos ao final caso não existam no texto.
    if product_price and product_price not in message:
        message += f"\n\n💰 *Valor:* {product_price}"
    if product_link and product_link not in message:
        message += f"\n🔗 *Acesse:* {product_link}"

    # Save mode (draft vs schedule)
    save_mode = form_data.get("save_mode", "schedule")
    orig_status = form_data.get("status", "scheduled")
    is_now = orig_status == "sending"

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
            scheduled_at=scheduled_at or (now_sp() if status == "sending" else None),
            is_recurring=is_recurring,
            recurrence_days=recurrence_days,
            send_time=send_time,
            status=status,
        )

    campaign_repo.save(campaign)

    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="broadcast_campaign_save",
            description=f"Saved broadcast campaign: {campaign.title} (Status: {campaign.status})",
        )
    )

    return RedirectResponse(url="/broadcast/campaigns", status_code=303)


@router.post("/campaigns/{campaign_id}/delete")
async def delete_broadcast_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(login_required),
):
    campaign_repo = SQLBroadcastCampaignRepository(db)
    campaign_repo.delete(campaign_id, current_user.id)

    # Log activity
    activity_repo = SQLActivityRepository(db)
    activity_repo.save(
        ActivityLog(
            user_id=current_user.id,
            event_type="broadcast_campaign_delete",
            description=f"Deleted broadcast campaign ID: {campaign_id}",
        )
    )

    return RedirectResponse(url="/broadcast/campaigns", status_code=303)
