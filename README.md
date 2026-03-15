# 🚀 WhatsApp Sales Agent Pro

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-05998b.svg)](https://fastapi.tiangolo.com/)
[![Built with Clean Architecture](https://img.shields.io/badge/Architecture-Clean-blue)](# architecture)

A high-performance, professional WhatsApp automation dashboard designed for sales campaigns. Built with **Clean Architecture** and **Asynchronous I/O**, it leverages the [Evolution API](https://doc.evolution-api.com) for cost-free, direct WhatsApp communication.

---

## ✨ Key Features

-   **💎 Premium UI/UX**: Modern SaaS dashboard with a sleek dark theme, responsive sidebar, and micro-animations.
-   **⚡ High-Performance Async Core**: Fully non-blocking architecture using `httpx` and `AsyncOpenAI` for maximum responsiveness.
-   **⏰ Advanced Recurring Scheduler**: "Alarm-style" scheduling. Set campaigns to repeat on specific days of the week at exact times.
-   **🔄 Hybrid Target Fetching**: Smart caching system that prioritizes local DB for instant group/chat loading with an API fallback.
-   **🤖 AI Message Generation**: Integrated OpenAI support to generate persuasive, high-conversion sales copy automatically.
-   **📊 Campaign Management**: Complete lifecycle tracking (Scheduled → Sending → Sent/Failed) with detailed status feedback.
-   **🔌 WhatsApp Management**: Secure QR code pairing, real-time connection status monitoring, and test message functionality.

---

## 🏗️ Technical Stack

-   **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
-   **Database**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with SQLite (local)
-   **Async I/O**: [httpx](https://www.python-httpx.org/)
-   **AI**: [OpenAI SDK](https://github.com/openai/openai-python) (Async)
-   **UI**: Vanilla HTML5/CSS3 with [Jinja2](https://palletsprojects.com/p/jinja/) templates
-   **WhatsApp Integration**: [Evolution API](https://doc.evolution-api.com) (Baileys-based)

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

-   **Non-Root Execution**: Docker containers run under restricted user permissions.
-   **Clean History**: sensitive database files and `.env` are strictly excluded from Git.
-   **Maintainability**: No "God Files"; every component follows the Single Responsibility Principle.

---

## 📄 License
Internal use only. Build for professional sales teams.
