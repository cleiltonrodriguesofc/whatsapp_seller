from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from core.infrastructure.database.session import get_db
from core.infrastructure.database.repositories import SQLUserRepository, SQLActivityRepository
from core.application.services.admin_service import AdminService
from core.presentation.web.dependencies import admin_required, templates
from core.infrastructure.database.models import UserModel

router = APIRouter(prefix="/admin", tags=["admin"])

def get_admin_service(db: Session = Depends(get_db)) -> AdminService:
    user_repo = SQLUserRepository(db)
    activity_repo = SQLActivityRepository(db)
    return AdminService(user_repo, activity_repo)

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    current_admin: UserModel = Depends(admin_required),
    admin_service: AdminService = Depends(get_admin_service)
):
    users = admin_service.list_users()
    activities = admin_service.list_activities(limit=10)
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": current_admin,
            "users": users,
            "activities": activities,
            "title": "Admin Dashboard"
        }
    )

@router.get("/users", response_class=HTMLResponse)
async def manage_users(
    request: Request,
    current_admin: UserModel = Depends(admin_required),
    admin_service: AdminService = Depends(get_admin_service)
):
    users = admin_service.list_users()
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": current_admin,
            "users": users,
            "title": "Manage Users"
        }
    )

@router.post("/users/{user_id}/toggle")
async def toggle_user(
    user_id: int,
    current_admin: UserModel = Depends(admin_required),
    admin_service: AdminService = Depends(get_admin_service),
    db: Session = Depends(get_db)
):
    user = admin_service.toggle_user_active(user_id)
    if user:
        admin_service.log_activity(
            user_id=current_admin.id,
            event_type="admin_user_toggle",
            description=f"Admin {current_admin.email} toggled status for user {user.email} (Active: {user.is_active})"
        )
    return RedirectResponse(url="/admin/users", status_code=303)

@router.get("/activities", response_class=HTMLResponse)
async def view_activities(
    request: Request,
    user_id: Optional[int] = None,
    current_admin: UserModel = Depends(admin_required),
    admin_service: AdminService = Depends(get_admin_service)
):
    activities = admin_service.list_activities(limit=100, user_id=user_id)
    return templates.TemplateResponse(
        "admin/activities.html",
        {
            "request": request,
            "user": current_admin,
            "activities": activities,
            "filter_user_id": user_id,
            "title": "Platform Activities"
        }
    )
