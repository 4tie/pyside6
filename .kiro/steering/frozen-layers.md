---
inclusion: always
---

# Frozen Layers

## DO NOT MODIFY

The following directories are **frozen** — no new features, bug fixes, or refactors should be made here:

- `app/ui/` — legacy PySide6 desktop UI (frozen)
- `app/web/` — legacy static/HTML web layer (frozen)

## Active Development Targets

All work must go to:

- `app/core/` — backend business logic, services, models, APIs
- `app/re_web/` — React frontend (TypeScript/Vite)

