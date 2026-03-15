# WhatsApp Sales Agent - Evolution API

A professional WhatsApp sales agent built with **Clean Architecture**, integrating with [Evolution API](https://doc.evolution-api.com) for direct, cost-free WhatsApp communication.

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose
- Evolution API instance (self-hosted)

### Setup
1. Clone the repository.
2. `cp .env.example .env` and fill in your Evolution API credentials.
3. Run with Docker:
   ```bash
   docker compose up --build
   ```

## 🏗️ Architecture

This project follows **Domain-Driven Design (DDD)** and **Clean Architecture** principles:

- **`core/domain`**: Contains entities (`Product`, `Contact`) and business rules. No external dependencies.
- **`core/application`**: Defines use cases (`SendDailyGreeting`) and interfaces (`NotificationService`).
- **`core/infrastructure`**: External implementations (API clients, database).
- **`core/presentation`**: Application entry points (CLI, background services).

## 🛠️ Components

- **Evolution API Service**: Handles QR code generation, connection status, and message sending.
- **Notification Service**: Unified interface for various notification types.
- **Use Cases**: Encapsulated business logic for daily tasks and interactions.

## 📈 Roadmap
- [ ] Implement robust message receiver/webhook handler.
- [ ] Integrate AI (Gemini) for automated responses.
- [ ] Add persistence layer (SQLite/PostgreSQL).
- [ ] Develop a monitoring dashboard.
