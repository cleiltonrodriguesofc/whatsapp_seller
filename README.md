# 🚀 WhatsApp Seller Pro

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-05998b.svg)](https://fastapi.tiangolo.com/)
[![Render](https://img.shields.io/badge/Deploy-Render-43a047)](https://render.com)
[![Built with Clean Architecture](https://img.shields.io/badge/Architecture-Clean-blue)](# architecture)

A high-performance, **Production-Ready** WhatsApp marketing SaaS. Built with **Clean Architecture** and **Asynchronous I/O**, it leverages the [Evolution API](https://doc.evolution-api.com) for professional-grade automation.

---

## ✨ Key Features

-   **💎 Premium UI/UX**: Modern SaaS dashboard with a sleek dark theme, responsive sidebar, and smooth transitions.
-   **🛡️ Anti-Ban Engine**: Built-in **Spintax** support (`{hi|hello}`), randomized humanized delays, and "Typing..." presence simulation to protect your account.
-   **🔒 SaaS Hardened Security**: Implementation of **Content-Security-Policy**, **HSTS**, **Secure Cookies** (Lax/HttpOnly), and CSRF hardening for safe web access.
-   **🚀 Render-Ready Infrastructure**: Multi-stage Docker optimization and `render.yaml` blueprint for one-click deployment with PostgreSQL.
-   **🤖 AI Message Copilot**: Integrated OpenAI support to generate and rewrite persuasive, high-conversion sales copy.
-   **⏰ Granular Scheduler**: "Alarm-style" recurring campaigns. Set exact times and days (e.g., Mon, Wed, Fri at 08:00).
-   **🔌 Multi-Instance Management**: Support for multiple WhatsApp accounts per user with real-time QR code pairing.

---

## 🏗️ Technical Stack

-   **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
-   **Database**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with PostgreSQL (Production) / SQLite (Dev)
-   **Security**: [bcrypt](https://pypi.org/project/bcrypt/) & [PyJWT](https://pyjwt.readthedocs.io/)
-   **Deployment**: [Render](https://render.com) + [Docker](https://www.docker.com/) (Multi-stage)

---

## 🚀 Getting Started

### Prerequisites
- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- An active [Evolution API](https://github.com/EvolutionAPI/evolution-api) instance.

### Setup & Launch
1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourserver/whatsapp_sales_agent.git
   cd whatsapp_sales_agent
   ```

2. **Configure Environment Variables**:
   Copy the example file and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   *Required variables: `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, and `OPENAI_API_KEY`.*

3. **Run with Docker (Recommended)**:
   ```bash
   docker compose up --build
   ```
   *The app will be available at `http://localhost:8000`.*

---

## 📁 Project Structure

Following **Clean Architecture** principles:

```text
├── core/
│   ├── domain/           # Core Entities (Business Rules)
│   ├── application/      # Use Cases & Service Interfaces
│   ├── infrastructure/   # DB Repositories, API Clients (Evolution, OpenAI)
│   └── presentation/     # Web Dashboard (FastAPI, Templates, Static)
├── venv/                 # Local Virtual Environment
└── docker-compose.yml    # Container Orchestration
```

---

## 🔒 Security & Standards

-   **Hardened Security**: Headers (CSP, HSTS) and secure session cookies prevent common web attacks.
-   **Non-Root Execution**: Docker containers run under restricted user permissions.
-   **Environment Discipline**: Sensitive database files and `.env` are strictly excluded from Git; production secrets are generated on deployment.

---

## 📄 License
Internal use only. Build for professional sales teams.
