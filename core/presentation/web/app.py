"""
FastAPI application entry point.
Responsibilities: app init, middleware, startup lifecycle, and router registration.
All route handlers live in core/presentation/web/routers/.
Background tasks live in core/presentation/web/scheduler.py.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text
from core.infrastructure.database.models import (
    Base,
    ProductModel,
    CampaignModel,
    StatusCampaignModel,
    WhatsAppTargetModel,
    BroadcastListModel,
    BroadcastListMemberModel,
    BroadcastCampaignModel,
)
from core.infrastructure.database.session import engine
from core.presentation.web.dependencies import templates  # noqa: F401 — registers template helpers
from core.presentation.web.routers import (
    auth,
    campaigns,
    products,
    status_campaigns,
    storage,
    whatsapp,
    broadcast,
)
from core.presentation.web.scheduler import campaign_scheduler_loop

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# create database tables
Base.metadata.create_all(bind=engine)

# run auto-migrations on startup
try:
    with engine.connect() as conn:
        # products.click_count
        res = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'products' AND column_name = 'click_count';"
            )
        )
        if not res.fetchone():
            conn.execute(text("ALTER TABLE products ADD COLUMN click_count INTEGER DEFAULT 0;"))
            conn.commit()
            logger.info("auto-migration: added 'click_count' to products table")
        
        # status_campaigns.link
        res = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'status_campaigns' AND column_name = 'link';"
            )
        )
        if not res.fetchone():
            conn.execute(text("ALTER TABLE status_campaigns ADD COLUMN link TEXT;"))
            conn.commit()
            logger.info("auto-migration: added 'link' to status_campaigns table")

        # status_campaigns.price
        res = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'status_campaigns' AND column_name = 'price';"
            )
        )
        if not res.fetchone():
            conn.execute(text("ALTER TABLE status_campaigns ADD COLUMN price FLOAT;"))
            conn.commit()
            logger.info("auto-migration: added 'price' to status_campaigns table")
        # whatsapp_targets.phone
        res = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'whatsapp_targets' AND column_name = 'phone';"
            )
        )
        if not res.fetchone():
            conn.execute(text("ALTER TABLE whatsapp_targets ADD COLUMN phone TEXT;"))
            conn.commit()
            logger.info("auto-migration: added 'phone' to whatsapp_targets table")
except Exception as e:
    logger.warning("auto-migration failed: %s", e)

# rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="WhatSeller Pro", debug=os.environ.get("DEBUG", "false") == "true")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── security middleware ────────────────────────────────────────────────────────


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https: "
        "https://wjgxuhozvbybpojhvqzf.supabase.co; "
        "connect-src 'self' https:;"
    )
    if os.environ.get("RENDER"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── static files ───────────────────────────────────────────────────────────────

app.mount(
    "/static",
    StaticFiles(directory="core/presentation/web/static"),
    name="static",
)


# ── startup ────────────────────────────────────────────────────────────────────


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(campaign_scheduler_loop())


# ── health check ───────────────────────────────────────────────────────────────


@app.get("/health")
async def health_check():
    """health check endpoint used by render and other platforms."""
    return {"status": "ok"}


# ── routers ────────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(campaigns.router)
app.include_router(products.router)
app.include_router(status_campaigns.router)
app.include_router(storage.router)
app.include_router(whatsapp.router)
app.include_router(broadcast.router)
