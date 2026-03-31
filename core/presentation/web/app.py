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
        migrations = [
            ("products", "click_count", "ALTER TABLE products ADD COLUMN click_count INTEGER DEFAULT 0;"),
            ("status_campaigns", "link", "ALTER TABLE status_campaigns ADD COLUMN link TEXT;"),
            ("status_campaigns", "price", "ALTER TABLE status_campaigns ADD COLUMN price FLOAT;"),
            ("status_campaigns", "target_contacts", "ALTER TABLE status_campaigns ADD COLUMN target_contacts TEXT;"),
            ("whatsapp_targets", "phone", "ALTER TABLE whatsapp_targets ADD COLUMN phone TEXT;"),
            ("broadcast_campaigns", "target_type", "ALTER TABLE broadcast_campaigns ADD COLUMN target_type TEXT DEFAULT 'contacts';"),
            ("broadcast_campaigns", "target_jids", "ALTER TABLE broadcast_campaigns ADD COLUMN target_jids TEXT;"),
            ("broadcast_campaigns", "list_id", "ALTER TABLE broadcast_campaigns ADD COLUMN list_id INTEGER;"),
            ("whatsapp_targets", "instance_id", "ALTER TABLE whatsapp_targets ADD COLUMN instance_id INTEGER REFERENCES instances(id) ON DELETE SET NULL;"),
            ("broadcast_lists", "instance_id", "ALTER TABLE broadcast_lists ADD COLUMN instance_id INTEGER REFERENCES instances(id) ON DELETE SET NULL;"),
        ]

        for table, column, stmt in migrations:
            try:
                res = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = :table_name AND column_name = :column_name;"
                    ),
                    {"table_name": table, "column_name": column}
                )
                if not res.fetchone():
                    conn.execute(text(stmt))
                    conn.commit()
                    logger.info(f"auto-migration: added '{column}' to {table} table")
            except Exception as e:
                logger.warning(f"auto-migration failed for {table}.{column}: {e}")

        # postgres-only enum-to-varchar casts
        postgres_casts = [
            "ALTER TABLE campaigns ALTER COLUMN status TYPE VARCHAR(50) USING status::varchar;",
            "ALTER TABLE status_campaigns ALTER COLUMN status TYPE VARCHAR(50) USING status::varchar;",
            "ALTER TABLE broadcast_campaigns ALTER COLUMN status TYPE VARCHAR(50) USING status::varchar;",
        ]
        for cast_stmt in postgres_casts:
            try:
                conn.execute(text(cast_stmt))
                conn.commit()
                logger.debug("auto-migration: executed postgres type cast successfully")
            except Exception:
                # Expected to fail silently on SQLite or if already casted in Postgres
                pass

except Exception as e:
    logger.warning("auto-migration base loop failed: %s", e)

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
