# API Backend

FastAPI backend serving the trading platform. Provides REST endpoints for the operator console, orchestrates service calls, and manages platform state.

## Quick Start

```bash
uvicorn apps.api.src.main:app --reload
```

## Endpoints

- `GET /health` — Health check

See [PROJECT_CHARTER_V2.md](../../docs/PROJECT_CHARTER_V2.md) §8 for architecture details.
