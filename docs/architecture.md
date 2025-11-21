# Architecture

## 1. System Overview

- Unified Flask application for PayCrypt crypto gateway + bank gateway.
- Exposes web UI (admin, client, demo) and JSON APIs for payments and bank flows.
- Designed for betting platforms, casinos, and high-risk operators.

## 2. Main Modules

- `app/models/` – SQLAlchemy models (payments, withdrawals, bank gateway, clients, etc.)
- `app/routes/` – Flask blueprints (main site, tools, client, branch, bank_gateway, demo, webhooks)
- `app/templates/` – Marketing pages, dashboards, bank gateway UIs, tools.
- `app/utils/` – Shared helpers (wallet execution, webhooks, notifications, config helpers).
- `migrations/` – Alembic migrations for the unified schema.
- `tests/` – Regression/integration tests (wallet integration, webhooks, etc.).

## 3. Data Flow (High-Level)

Typical crypto deposit:

1. Client or platform calls a crypto deposit endpoint (or uses the demo gateway).
2. Request is handled by `app.routes.api_v1` / related blueprint.
3. Business logic loads client + wallet configuration and creates a `Payment` record.
4. Wallet provider / address is chosen (manual, custom API, or default platform wallet).
5. Player sends funds on-chain to the generated address.
6. Webhook from wallet provider hits `app.routes.webhooks`.
7. Webhook is validated and reconciled against the `Payment` record.
8. Client-facing systems update balances / tickets.

See `README_UNIFIED.md` for more concrete details on bank gateway components.
