"""
birthday messaging router.
manages birthday contacts, templates, logs, and manual dispatch triggers.
"""

import asyncio
import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from core.infrastructure.database.models import (
    BirthdayContactModel,
    BirthdayLogModel,
    BirthdayTemplateModel,
    InstanceModel,
)
from core.infrastructure.database.session import get_db
from core.presentation.web.dependencies import login_required, templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/birthday", tags=["birthday"])


# ── dashboard ──────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
async def birthday_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    contacts = (
        db.query(BirthdayContactModel)
        .filter(BirthdayContactModel.user_id == user.id)
        .order_by(BirthdayContactModel.name)
        .all()
    )
    template = (
        db.query(BirthdayTemplateModel)
        .filter(BirthdayTemplateModel.user_id == user.id)
        .first()
    )
    recent_logs = (
        db.query(BirthdayLogModel)
        .filter(BirthdayLogModel.user_id == user.id)
        .order_by(BirthdayLogModel.sent_at.desc())
        .limit(50)
        .all()
    )
    instance = (
        db.query(InstanceModel)
        .filter(InstanceModel.user_id == user.id)
        .first()
    )

    return templates.TemplateResponse(
        request=request,
        name="birthday_dashboard.html",
        context={
            "request": request,
            "user": user,
            "contacts": contacts,
            "template": template,
            "recent_logs": recent_logs,
            "has_instance": instance is not None,
            "total_contacts": len(contacts),
            "active_contacts": sum(1 for c in contacts if c.is_active),
        },
    )


# ── contact management ────────────────────────────────────────────────────────


@router.post("/contacts/add")
async def add_contact(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    birth_date: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    parsed_date = None
    if birth_date:
        try:
            parsed_date = datetime.strptime(birth_date, "%Y-%m-%d")
        except ValueError:
            pass

    contact = BirthdayContactModel(
        user_id=user.id,
        name=name.strip(),
        phone=phone.strip(),
        birth_date=parsed_date,
        is_active=True,
    )
    db.add(contact)
    db.commit()
    return RedirectResponse(url="/birthday", status_code=303)


@router.post("/contacts/{contact_id}/delete")
async def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    contact = (
        db.query(BirthdayContactModel)
        .filter(
            BirthdayContactModel.id == contact_id,
            BirthdayContactModel.user_id == user.id,
        )
        .first()
    )
    if contact:
        db.delete(contact)
        db.commit()
    return JSONResponse({"success": True})


@router.post("/contacts/{contact_id}/toggle")
async def toggle_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    contact = (
        db.query(BirthdayContactModel)
        .filter(
            BirthdayContactModel.id == contact_id,
            BirthdayContactModel.user_id == user.id,
        )
        .first()
    )
    if contact:
        contact.is_active = not contact.is_active
        db.commit()
    return JSONResponse({"success": True, "is_active": contact.is_active if contact else False})


@router.post("/contacts/import")
async def import_contacts(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    """imports contacts from csv. expected columns: name, phone, birth_date (YYYY-MM-DD)"""
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    for row in reader:
        name = row.get("name", "").strip() or row.get("nome", "").strip()
        phone = row.get("phone", "").strip() or row.get("telefone", "").strip()
        birth_str = row.get("birth_date", "").strip() or row.get("data_nasc", "").strip()

        if not name or not phone:
            continue

        parsed_date = None
        if birth_str:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    parsed_date = datetime.strptime(birth_str, fmt)
                    break
                except ValueError:
                    continue

        contact = BirthdayContactModel(
            user_id=user.id,
            name=name,
            phone=phone,
            birth_date=parsed_date,
            is_active=True,
        )
        db.add(contact)
        imported += 1

    db.commit()
    return JSONResponse({"success": True, "imported": imported})


# ── template management ───────────────────────────────────────────────────────


@router.post("/template/save")
async def save_template(
    name: str = Form("Parabéns Automático"),
    content: str = Form(...),
    media_url: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    # upsert: update existing or create new
    template = (
        db.query(BirthdayTemplateModel)
        .filter(BirthdayTemplateModel.user_id == user.id)
        .first()
    )
    if template:
        template.name = name.strip()
        template.content = content.strip()
        template.media_url = media_url.strip() or None
        template.is_enabled = True
    else:
        template = BirthdayTemplateModel(
            user_id=user.id,
            name=name.strip(),
            content=content.strip(),
            media_url=media_url.strip() or None,
            is_enabled=True,
        )
        db.add(template)

    db.commit()
    return RedirectResponse(url="/birthday", status_code=303)


# ── manual dispatch ───────────────────────────────────────────────────────────


@router.post("/dispatch")
async def dispatch_birthday_messages(
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    """manually triggers birthday message dispatch for the current user."""
    from core.application.use_cases.send_birthday_messages import SendBirthdayMessages

    use_case = SendBirthdayMessages(db=db, user_id=user.id)

    # run in background to avoid timeout
    async def run():
        try:
            await use_case.execute()
        except Exception as e:
            logger.error("[birthday] manual dispatch error: %s", e)

    asyncio.create_task(run())
    return JSONResponse({"success": True, "message": "Disparo iniciado em segundo plano"})


# ── logs ──────────────────────────────────────────────────────────────────────


@router.post("/logs/clear")
async def clear_logs(
    db: Session = Depends(get_db),
    user=Depends(login_required),
):
    db.query(BirthdayLogModel).filter(BirthdayLogModel.user_id == user.id).delete()
    db.commit()
    return JSONResponse({"success": True})
