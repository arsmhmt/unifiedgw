# Decisions

Track important architectural / product decisions here.

Example format:

## 2025-11-21 – Unified Flask instead of separate apps

- **Context:** Previously had separate PayCrypt CCA (Flask) and bank gateway (Django).
- **Decision:** Merge into a unified Flask application with shared models and routes.
- **Consequences:**
  - Simpler deployment & hosting.
  - Shared authentication and admin surfaces.
  - Migration work required for bank gateway data.

Add new entries as you make significant changes.
