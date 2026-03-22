# 🚀 WhatsApp Seller

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-05998b.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ed.svg)](https://www.docker.com/)
[![Render](https://img.shields.io/badge/Deploy-Render-43a047)](https://render.com)
[![Architecture](https://img.shields.io/badge/Architecture-Clean-blue)](#architecture)

**WhatsApp Seller** is a production-ready WhatsApp marketing SaaS built with **Clean Architecture** and **Async I/O**. It integrates the [Evolution API](https://doc.evolution-api.com) to automate campaign dispatch, manage multiple WhatsApp instances, and generate messages with OpenAI.

---

## ✨ Features

- **Multi-Instance Management** — connect multiple WhatsApp numbers via QR Code and manage them from a single dashboard
- **Campaign Scheduling** — one-shot or recurring campaigns with day/time granularity
- **AI Copywriting** — generate sales messages via OpenAI GPT based on your product catalogue
- **Spintax + Humanized Delays** — randomize message wording and dispatch timing to reduce detection risk
- **Product Catalogue** — register products (name, description, price, image, affiliate link) and attach them to campaigns
- **Group & Contact Targeting** — send to WhatsApp groups or individual contacts, selected per campaign
- **Secure Auth** — bcrypt password hashing, JWT session tokens, secure cookie flags (HttpOnly / SameSite)
- **Rate Limiting** — request throttling via SlowAPI to protect endpoints under load
- **Hardened HTTP Headers** — CSP, HSTS, and X-Frame-Options enforced on every response

---

## 🏗️ Architecture

The project follows **Clean Architecture** with strict dependency inversion:

```
core/
├── domain/           # entities, enums, domain exceptions (no external deps)
├── application/      # use cases, service interfaces, repository contracts
├── infrastructure/   # SQLAlchemy models/repos, Evolution API & OpenAI clients
└── presentation/     # FastAPI app, Jinja2 templates, static assets
```

```
tests/                # unit + integration test suite
.github/workflows/    # CI pipeline (lint, test, build)
Dockerfile            # multi-stage production image
docker-compose.yml    # local dev orchestration
render.yaml           # one-click Render deployment blueprint
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI 0.109 |
| ORM | SQLAlchemy 2.0 |
| Database (prod) | PostgreSQL via psycopg2 |
| Database (dev) | SQLite |
| Auth | bcrypt + PyJWT |
| Templates | Jinja2 |
| HTTP client | httpx |
| AI | OpenAI Python SDK |
| Rate limiting | SlowAPI |
| Container | Docker (multi-stage) |
| Deployment | Render |

---

## 🚀 Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- An active [Evolution API](https://github.com/EvolutionAPI/evolution-api) instance
- An [OpenAI API Key](https://platform.openai.com/api-keys) (optional — required for AI copywriting)

### Setup

```bash
# 1. clone the repository
git clone https://github.com/cleiltonrodriguesofc/whatsapp_seller.git
cd whatsapp_seller

# 2. configure environment variables
cp .env.example .env
# edit .env and fill in your keys

# 3. start with docker compose
docker compose up --build
```

The app will be available at **http://localhost:8000**.

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `EVOLUTION_API_URL` | ✅ | Base URL of your Evolution API instance |
| `EVOLUTION_API_KEY` | ✅ | Global API key for the Evolution API |
| `EVOLUTION_DB_URL` | ✅ | PostgreSQL connection string (production) |
| `OPENAI_API_KEY` | ⬜ | Required only for AI copywriting |

---

## 🧪 Running Tests

```bash
# inside the container or local venv
pytest tests/ -v
```

The CI pipeline runs the full test suite on every pull request via GitHub Actions.

---

## 🔒 Security

- Passwords hashed with **bcrypt**
- Sessions managed via **JWT** stored in HttpOnly, SameSite=Lax cookies
- HTTP security headers: CSP, HSTS, X-Content-Type-Options, X-Frame-Options
- `.env` and database files are excluded from Git via `.gitignore`
- Docker container runs as a **non-root user**
- Base image pinned to a stable version (no `latest`)

---

## 📄 License

Internal use only. Built for professional sales teams.
