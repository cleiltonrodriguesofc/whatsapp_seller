"""
FastAPI application entry point.
Responsibilities: app init, middleware, startup lifecycle, and router registration.
All route handlers live in core/presentation/web/routers/.
Background tasks live in core/presentation/web/scheduler.py.
"""

import asyncio
import logging
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from core.presentation.web.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from core.infrastructure.database.models import (
    Base,
)
from core.infrastructure.database.session import engine
from core.presentation.web.dependencies import templates  # noqa: F401 - registers template helpers
from core.presentation.web.routers import (
    auth,
    campaigns,
    products,
    status_campaigns,
    storage,
    whatsapp,
    broadcast,
    static_pages,
    billing,
    referral,
    admin,
    birthday,
    affiliate,
    shortener,
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
        migrations = []
        try:
            conn.execute(text("SELECT old_price FROM affiliate_logs LIMIT 1"))
        except Exception:
            conn.rollback()
            migrations.append(
                (
                    "affiliate_logs",
                    "old_price",
                    "ALTER TABLE affiliate_logs ADD COLUMN old_price FLOAT;",
                )
            )

        try:
            conn.execute(text("SELECT installment_text FROM affiliate_logs LIMIT 1"))
        except Exception:
            conn.rollback()
            migrations.append(
                (
                    "affiliate_logs",
                    "installment_text",
                    "ALTER TABLE affiliate_logs ADD COLUMN installment_text VARCHAR;",
                )
            )

        try:
            conn.execute(text("SELECT pix_discount_text FROM affiliate_logs LIMIT 1"))
        except Exception:
            conn.rollback()
            migrations.append(
                (
                    "affiliate_logs",
                    "pix_discount_text",
                    "ALTER TABLE affiliate_logs ADD COLUMN pix_discount_text VARCHAR;",
                )
            )

        migrations.extend([
            (
                "products",
                "click_count",
                "ALTER TABLE products ADD COLUMN click_count INTEGER DEFAULT 0;",
            ),
            (
                "status_campaigns",
                "link",
                "ALTER TABLE status_campaigns ADD COLUMN link TEXT;",
            ),
            (
                "status_campaigns",
                "price",
                "ALTER TABLE status_campaigns ADD COLUMN price FLOAT;",
            ),
            (
                "status_campaigns",
                "target_contacts",
                "ALTER TABLE status_campaigns ADD COLUMN target_contacts TEXT;",
            ),
            (
                "whatsapp_targets",
                "phone",
                "ALTER TABLE whatsapp_targets ADD COLUMN phone TEXT;",
            ),
            (
                "broadcast_campaigns",
                "target_type",
                "ALTER TABLE broadcast_campaigns ADD COLUMN target_type TEXT DEFAULT 'contacts';",
            ),
            (
                "broadcast_campaigns",
                "target_jids",
                "ALTER TABLE broadcast_campaigns ADD COLUMN target_jids TEXT;",
            ),
            (
                "broadcast_campaigns",
                "list_id",
                "ALTER TABLE broadcast_campaigns ADD COLUMN list_id INTEGER;",
            ),
            (
                "whatsapp_targets",
                "instance_id",
                "ALTER TABLE whatsapp_targets ADD COLUMN instance_id"
                " INTEGER REFERENCES instances(id) ON DELETE SET NULL;",
            ),
            (
                "broadcast_lists",
                "instance_id",
                "ALTER TABLE broadcast_lists ADD COLUMN instance_id"
                " INTEGER REFERENCES instances(id) ON DELETE SET NULL;",
            ),
            (
                "users",
                "referral_balance",
                "ALTER TABLE users ADD COLUMN referral_balance FLOAT DEFAULT 0.0;",
            ),
            (
                "users",
                "referral_code_id",
                "ALTER TABLE users ADD COLUMN referral_code_id INTEGER;",
            ),
            (
                "users",
                "agreed_to_terms_at",
                "ALTER TABLE users ADD COLUMN agreed_to_terms_at TIMESTAMP;",
            ),
            (
                "users",
                "is_admin",
                "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;",
            ),
            (
                "users",
                "reset_token",
                "ALTER TABLE users ADD COLUMN reset_token VARCHAR(255) UNIQUE;",
            ),
            (
                "users",
                "reset_token_expiry",
                "ALTER TABLE users ADD COLUMN reset_token_expiry TIMESTAMP;",
            ),
            (
                "affiliate_configs",
                "storefront_slug",
                "ALTER TABLE affiliate_configs ADD COLUMN storefront_slug VARCHAR;",
            ),
            (
                "affiliate_configs",
                "categories",
                "ALTER TABLE affiliate_configs ADD COLUMN categories VARCHAR DEFAULT 'notebook,celular';",
            ),
            (
                "affiliate_configs",
                "min_discount_percent",
                "ALTER TABLE affiliate_configs ADD COLUMN min_discount_percent FLOAT DEFAULT 10.0;",
            ),
            (
                "affiliate_configs",
                "max_offers_per_run",
                "ALTER TABLE affiliate_configs ADD COLUMN max_offers_per_run INTEGER DEFAULT 5;",
            ),
            (
                "affiliate_configs",
                "dispatch_hours",
                "ALTER TABLE affiliate_configs ADD COLUMN dispatch_hours VARCHAR DEFAULT '9,12,18';",
            ),
            (
                "affiliate_configs",
                "store_type",
                "ALTER TABLE affiliate_configs ADD COLUMN store_type VARCHAR DEFAULT 'magalu';",
            ),
            (
                "affiliate_configs",
                "theme_color",
                "ALTER TABLE affiliate_configs ADD COLUMN theme_color VARCHAR DEFAULT '#0088ff';",
            ),
            (
                "affiliate_configs",
                "tagline",
                "ALTER TABLE affiliate_configs ADD COLUMN tagline VARCHAR DEFAULT 'tem na minha loja';",
            ),
            (
                "affiliate_configs",
                "require_approval",
                "ALTER TABLE affiliate_configs ADD COLUMN require_approval BOOLEAN DEFAULT FALSE;",
            ),
            (
                "affiliate_logs",
                "image_url",
                "ALTER TABLE affiliate_logs ADD COLUMN image_url VARCHAR;",
            ),
            (
                "affiliate_configs",
                "preferred_brands",
                "ALTER TABLE affiliate_configs ADD COLUMN preferred_brands VARCHAR;",
            ),
            (
                "affiliate_configs",
                "ml_profile_slug",
                "ALTER TABLE affiliate_configs ADD COLUMN ml_profile_slug VARCHAR;",
            ),
            (
                "affiliate_configs",
                "ml_client_id",
                "ALTER TABLE affiliate_configs ADD COLUMN ml_client_id VARCHAR;",
            ),
            (
                "affiliate_configs",
                "ml_enabled",
                "ALTER TABLE affiliate_configs ADD COLUMN ml_enabled BOOLEAN DEFAULT FALSE;",
            ),
            (
                "affiliate_configs",
                "ml_categories",
                "ALTER TABLE affiliate_configs ADD COLUMN ml_categories VARCHAR DEFAULT 'notebook,celular';",
            ),
            (
                "affiliate_campaigns",
                "custom_search_terms",
                "ALTER TABLE affiliate_campaigns ADD COLUMN custom_search_terms VARCHAR;",
            ),
        ])


        for table, column, stmt in migrations:
            try:
                res = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = :table_name AND column_name = :column_name;"
                    ),
                    {"table_name": table, "column_name": column},
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

# shared limiter

app = FastAPI(
    title="WhatSeller Pro",
    debug=os.environ.get("DEBUG", "false") == "true",
    docs_url="/api-docs" if os.environ.get("RENDER") != "true" else None,
    redoc_url="/api-redoc" if os.environ.get("RENDER") != "true" else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── cors middleware ────────────────────────────────────────────────────────────
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

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
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
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
app.include_router(static_pages.router)
app.include_router(billing.router)
app.include_router(referral.router)
app.include_router(admin.router)
app.include_router(birthday.router)
app.include_router(affiliate.router)
app.include_router(shortener.router)
