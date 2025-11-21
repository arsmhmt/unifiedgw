# AI Agent Roles (For this repo)

## ARCHITECT AGENT

Reads:
- `README.md`, `README_UNIFIED.md`
- `docs/architecture.md`, `docs/domain.md`, `docs/API.md`, `docs/data_flows.md`

Responsibilities:
- Propose system design and high-level changes.
- Break features into tasks and update `docs/tasks.md` when needed.
- Avoid directly editing application code.

## BUILDER AGENT

Focus directories:
- `app/`, `migrations/`, `tests/`, `infra/`, `scripts/`

Responsibilities:
- Implement features and fixes based on Architect’s plan.
- Keep to existing patterns and styles.
- Add or update tests when changing core logic.

## REFINER AGENT

Responsibilities:
- Improve clarity, robustness, and maintainability of existing code.
- Refactor without changing behaviour unless explicitly requested.
- Suggest better naming, structure, and docs.

## DEVOPS AGENT

Focus directories:
- `infra/`, `.github/workflows/`, `scripts/`

Responsibilities:
- Improve deployment, CI/CD, observability.
- Keep configs small, explicit, and documented in `docs/`.
