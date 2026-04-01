# Indian Equities AI Trading Platform

An institutional-style solo trading control system for Indian cash equities where deterministic logic owns risk and execution, LLMs supply structured reasoning and skeptical review, the operator retains controlled authority, and the entire platform is testable before any real capital is exposed.

> **Operating principle:** AI proposes. AI critiques. Rules decide. Execution executes. Operator supervises.

## Development Setup

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --all-extras

# Start local PostgreSQL
docker compose up -d

# Set up the development database
./scripts/setup_local_db.sh

# Install pre-commit hooks
uv run pre-commit install

# Run all checks
make check
```

## Phase Roadmap

| Phase | Goal |
|-------|------|
| 0 | Foundations — repo, tooling, CI, local DB |
| 1 | Contracts first — Pydantic schemas for all inter-service messages |
| 2 | Core engines — data ingest, feature engine, candidate engine, rule engine |
| 3 | Paper system — paper broker, EOD run, ledger, intraday monitor |
| 4 | Operator console — dashboard, risk center, command center |
| 5 | Model routing — provider adapters, structured outputs, telemetry |
| 6 | Shadow live — broker auth, static IP, compliance gate |
| 7 | Tiny live — small capital, tight limits, manual review every run |

## Architecture

All architecture decisions follow [`docs/PROJECT_CHARTER_V2.md`](docs/PROJECT_CHARTER_V2.md).
