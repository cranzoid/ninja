# Indian Equities AI Trading Platform — Project Charter V2

> **Operating principle:** AI proposes. AI critiques. Rules decide. Execution executes. Operator supervises.

**Prepared for:** Vishesh Vaibhav
**Date:** 23 March 2026
**Document type:** Master build charter

---

## 1. Executive Summary

Build an institutional-style solo trading control system for Indian cash equities where:
- Deterministic logic owns risk and execution
- LLMs supply structured reasoning and skeptical review
- The operator retains controlled authority
- The entire platform is testable before any real capital is exposed

**V2 in one line:** Build a serious solo trading OS where rules own decisions, AI advises, and the operator supervises.

---

## 2. Locked Decisions from V1

| Area | Decision | Status |
|------|----------|--------|
| Market | Indian cash equities (NSE) | Keep |
| Style | Swing + long-term core | Keep |
| Authority | LLMs advise, rules decide | Keep |
| Deployment | Paper first, live later | Keep |
| Cloud stack | AWS + Python + Terraform | Keep |
| Control model | Operator console with overrides | Keep |
| Kill switch | Pause entries, allow exits/stops | Keep |
| Mode safety | MODE and ARMED_LIVE flags | Keep |
| Non-goals | No intraday, options, leverage, HFT | Keep |

---

## 3. V2 Changes

| V1 Assumption | V2 Refinement |
|---------------|---------------|
| Fixed model names | Capability roles with swappable providers |
| Compliance-aware design | Explicit pre-live compliance gate |
| Single regime proxy | Regime stack with sizing multipliers |
| Position counts for future capital | Lower live-v1 counts for ₹50k |
| LLM outputs as concepts | Strict JSON-schema contracts everywhere |
| Paper then live | Backtest → paper → shadow-live → tiny-live |
| Tooling implied | Tool matrix for build, review, infra, runtime |

---

## 4. Design Principles

1. **Institutional behavior over retail excitement** — fewer, cleaner decisions over frequent activity
2. **White-box control over black-box confidence** — every trade explainable and audit-ready
3. **Deterministic authority over model authority** — no model output can place/resize/loosen risk alone
4. **Same engine in paper and live** — only the broker adapter differs
5. **Operator visibility by default** — always know what was considered, blocked, scheduled, executed, changed, or failed
6. **Small-capital realism** — V1 live respects friction and slippage at ~₹50,000 capital
7. **Prompt-driven engineering** — every module buildable with prompts, verifiable with AI-generated checks

### Success Definition (Year 1)
Not raw return. Success = system can ingest data reliably, generate and reject trades consistently, simulate realistically, survive restarts, explain itself, enforce controls, and move toward live without hidden fragility.

---

## 5. Scope

### Included
- NSE cash-equity trading only
- Dual portfolio: long-term core (60%) + swing satellite (40%)
- Paper trading with realistic execution assumptions
- Operator console with structured override commands
- Model-assisted research, blocker scanning, explanation generation
- Deterministic rule engine, risk engine, execution gate
- Data normalization, feature engine, audit ledger
- Build-time and run-time test harnesses
- Live scaffolding with explicit compliance gating

### Explicit Non-Goals
- No HFT, co-location, microsecond execution, tick-driven market-making
- No futures, options, leverage, margin-driven strategies in V1
- No multi-user productization in V1
- No black-box RL execution engine
- No AI-owned capital allocation outside rule-bounded limits
- No live broker onboarding before paper stack is stable for weeks

---

## 6. Trading Architecture & Rulebook

### 6.1 Portfolio Structure

| Layer | Strategic Target | Live-V1 Target | Notes |
|-------|-----------------|----------------|-------|
| Core | 60%, 6-10 holdings | 60%, 3-5 holdings | Strongest names only |
| Swing | 40%, 4-8 holdings | 40%, 2-4 holdings | Strict stop/entry discipline |

### 6.2 Universe
- Start with NIFTY 100 or similar liquid, well-covered universe
- Require price floor, liquidity floor, sane corporate-action data
- Exclude: unresolved splits, rights, mergers, demergers, delisting risk, data contradictions

### 6.3 Risk Rules

| Control | V2 Live-V1 Recommendation |
|---------|--------------------------|
| Swing risk per trade | 0.35% to 0.50% of equity |
| Core add risk | 0.25% |
| Core position cap | 12% hard cap |
| Swing position cap | 8% hard cap |
| Sector cap | 25% preferred |
| Aggregate open risk | 4% preferred |

### 6.4 Core Rules
- Price above 200-DMA
- Price not excessively extended (within ~+12% of 50-DMA)
- Fundamental quality acceptable (positive/improving revenue, acceptable profitability, no sharp debt deterioration)
- Exit if price closes below 200-DMA for 3 consecutive sessions or fundamentals deteriorate meaningfully
- Rebalance monthly after data and blocker review

### 6.5 Swing Rules
- Entry: price > 50-DMA, 50-DMA > 200-DMA, close > 20-day high, volume ≥ 1.2× 20-day avg
- Execution: next-day open only
- Stop: 2× ATR(14) below entry (fallback fixed % if ATR unavailable)
- Exit: partial at +2R, trail remainder using 10-DMA, exit next open when close breaks below
- No averaging down, no pyramiding, no second entry below original entry in V1

### 6.6 Event & Blocker Rules

| Rule | Description |
|------|-------------|
| S1 | Earnings window block |
| S2 | Corporate-action uncertainty block |
| S3 | Credibility / financial risk block |
| S4 | Overnight news gap block (no auto-reschedule) |
| S5 | Sector shock block |
| R1 | Aggregate open risk limit |
| R2 | Time stop (next-open exit) |
| R3 | No averaging down (non-negotiable) |
| R4 | Gap-through-stop exit (log realized gap loss) |
| R5 | Max new swing entries per day (rank and discard extras) |

### 6.7 Regime Stack

Inputs:
- NIFTY 50 trend state
- Breadth (% of tracked names above 50-DMA and 200-DMA)
- Volatility (India VIX or realized-vol proxy)
- Gap frequency for active universe
- Sector leadership concentration
- Correlation expansion/compression across held names

Output → regime class: **green**, **mixed**, **stressed**

| Regime | Sizing Behavior |
|--------|----------------|
| Green | Normal sizing |
| Mixed | Half-sized swing entries, stricter ranking |
| Stressed | No new swings, core adds only for top names at reduced size |

---

## 7. AI Architecture & Model Routing

### 7.1 Principle
Bind architecture to **capabilities**, not brands. Providers can change.

### 7.2 Capability Roles

| Role | Purpose | Output Contract | When Called |
|------|---------|----------------|------------|
| Thesis extractor | Summarize setup & rationale | TradeCard | Shortlisted names only |
| Blocker classifier | Scan event/risk/contradiction | BlockerReport | Every shortlisted name |
| Deep reasoner | Resolve ambiguous cases | RiskDecision / ReviewMemo | When rules need structured review |
| Operator explainer | Human-facing summaries | UI narrative JSON | Console panels and alerts |

### 7.3 Contract Discipline
- Every model output must conform to strict schema
- No trade decision parsed from prose
- Natural-language explanation allowed only after structured contract passes validation
- Schema failures, retries, fallbacks logged as first-class telemetry

### 7.4 Routing Tiers

| Tier | Work Type | Cost Posture |
|------|-----------|-------------|
| 0 | Screens, filters, scoring | No LLM (free) |
| 1 | Short extraction, blocker classification | Mid-cost model (default path) |
| 2 | Hard reasoning, edge-case review | Frontier model (escalate sparingly) |
| 3 | Console narration, summaries | Low-cost model (cheap, frequent) |

### 7.5 Runtime
- Bedrock-first for production (AWS credits available)
- OpenAI API selectively for build-time experiments and evals
- Provider-agnostic router + capability registry in code

---

## 8. Runtime & Infrastructure

### 8.1 Architecture

| Layer | Choice |
|-------|--------|
| Orchestration | EventBridge + Step Functions |
| Compute | Lambda (light) + ECS (heavy) |
| Primary DB | PostgreSQL |
| Object store | S3 |
| State/locks | DynamoDB (selective) |
| Secrets | Secrets Manager |
| Monitoring | CloudWatch + SNS |
| Network | VPC, private subnets, NAT + Elastic IP |

### 8.2 Environments
1. Local developer environment
2. Paper environment (AWS)
3. Shadow-live (real broker auth, zero live orders)
4. Live (separate secrets, ledgers, explicit arming)

---

## 9. Data Architecture — Four Lanes

| Lane | Purpose | Examples | Rule |
|------|---------|----------|------|
| Signal | Candle & indicator generation | OHLCV, MAs, ATR | Can be recalculated, versioned |
| Execution | Live order & fill truth | Broker positions, orders, fills | Broker is source of truth |
| Corporate-action | Split & action normalization | Splits, bonuses, rights, mergers | Reconcile independently |
| Context | Blocker & background data | Earnings, news, flags, pledge data | Blocker context only |

---

## 10. Pre-Live Compliance Gate

Live mode cannot arm unless ALL checks green:
- Static IP healthy and matches whitelist
- Primary/backup network profile healthy
- Broker dev app credentials valid
- Session and 2FA freshness valid
- Order-rate governor healthy
- Audit sink healthy and writable
- Clock, market calendar, holiday checks valid
- Config checksum matches approved release
- Kill switch off, MODE/ARMED_LIVE transition explicitly approved

---

## 11. Broker Adapter Contract

| Method | Purpose |
|--------|---------|
| `authenticate()` | Create/refresh live session |
| `get_quotes()` | Fetch reference prices |
| `place_order()` | Submit order with tags + idempotency |
| `modify_order()` | Safe modifications |
| `cancel_order()` | Cancel pending entries |
| `get_positions()` | Read current exposure |
| `get_orders()` | Reconcile state |
| `healthcheck()` | Operational readiness signal |

---

## 12. Operator Console

### Core Pages
Dashboard, Today's Plan, Positions, Trades & Ledger, Risk Center, Bot Runs, Configuration, Alerts Feed, Command Center

### V2 Pages
Compliance Center, Model Center (latency/cost/fallback telemetry), Data Health Center, Simulation Drift Center

### Override Policy

| Allowed by Default | Blocked by Default |
|---|---|
| Cancel entry, reduce size, tighten stop, close position, freeze symbol | Increase size, loosen stop, bypass blocker, bypass compliance gate, hot-edit portfolio state |

---

## 13. Prompt-Driven Build Workflow

### Prompt Classes
- **Architecture prompt** → ADR, module contract, open issues
- **Implementation prompt** → Code diff or files
- **Schema prompt** → Pydantic models / JSON schema
- **Test prompt** → Unit tests, integration tests, fixtures
- **Critique prompt** → Failure list and fixes
- **Ops prompt** → Terraform modules, checklists

### Mandatory AI Test Checks Per Module
1. Explain what the module does in plain language
2. List assumptions and hidden dependencies
3. Show exact input/output contracts
4. Generate ≥3 normal cases and ≥3 failure cases
5. Generate 1 adversarial case to break the module
6. Run/simulate tests and summarize failures honestly
7. State what was NOT verified

---

## 14. Implementation Roadmap

| Phase | Goal | Key Outputs |
|-------|------|-------------|
| 0 | Foundations | Repo, Python, package mgmt, linting, local DB, CI |
| 1 | Contracts first | Schemas: TradeCard, BlockerReport, OrderIntent, ConfigSnapshot, AuditEvent |
| 2 | Core engines | Data ingest, feature engine, candidate engine, rule engine |
| 3 | Paper system | Paper broker, EOD run, open gate, intraday monitor, ledger |
| 4 | Operator console | Dashboard, today's plan, risk center, command center |
| 5 | Model routing | Provider adapters, structured outputs, telemetry, fallback |
| 6 | Shadow live | Broker auth, static IP, dry-run live adapter, compliance gate |
| 7 | Tiny live | Small capital, tight limits, manual review every run |

### What NOT to Build Early
- No glossy UI before data/rule engines stable
- No broker onboarding before paper mode reliable for weeks
- No advanced analytics before core audit ledger exists
- No optional features before baseline workflow proven

---

## 15. Acceptance Gates

### Gate A: Paper Stability
- Multi-week paper runs without silent failures
- Consistent schema compliance across all model outputs
- Accurate reconciliation (intents ↔ simulated fills ↔ portfolio state)
- Console reflects real backend state
- Rule/blocker logs readable and trustworthy

### Gate B: Shadow-Live
- Broker auth/session flow proven repeatedly
- Static IP and environment separation verified
- No accidental orders possible
- Execution timing validated
- Compliance gate red/green tested intentionally

### Gate C: Tiny-Live
- Live-v1 risk limits lowered vs paper
- Every live action reviewed after close
- No unresolved reconciliation gaps
- No unexplained model/adapter behavior
- Shadow-live and tiny-live behavior broadly consistent

---

## 16. Open Decisions

| Item | Recommendation | Timing |
|------|---------------|--------|
| Final broker | Choose after shadow-live dry runs | After paper stability |
| Market data vendor | Start simple, keep adapter abstraction | Phase 2 |
| Context/news provider | Blocker-only role, log source categories | Phase 5 |
| Frontend framework | Next.js | Before console build |
| Model router defaults | Finalize after build trials | Phase 5 |
| Advanced features | Delay until baseline stable | Post V1 |

---

## 17. Repository Structure

```
repo/
├── apps/
│   ├── operator-console/        # Next.js frontend
│   └── api/                     # FastAPI backend
├── services/
│   ├── data-ingest/
│   ├── feature-engine/
│   ├── candidate-engine/
│   ├── regime-engine/
│   ├── model-router/
│   ├── rule-engine/
│   ├── paper-broker/
│   ├── live-broker/
│   └── audit-ledger/
├── packages/
│   ├── contracts/               # Pydantic schemas
│   ├── utils/
│   └── observability/
├── infra/
│   └── terraform/
├── evals/
├── tests/
└── docs/
    └── PROJECT_CHARTER_V2.md    # This file
```

---

## 18. Build Ticket Tree (Summary)

**Foundation:** monorepo, Python pinning, uv, pre-commit, ruff/mypy/pytest, GitHub Actions CI

**Contracts:** TradeCard, BlockerReport, OrderIntent, AuditEvent, ConfigSnapshot, validation utilities

**Data:** universe loader, OHLCV ingest, corp-action ingest, earnings/calendar ingest, context signal ingest, normalization

**Engines:** feature, candidate, rule, ranking, risk, regime

**Model Layer:** provider adapters, capability registry, structured output validators, retry/fallback, telemetry

**Execution:** paper broker, ledger, stop/exit manager, order state machine, shadow-live adapter

**Frontend:** dashboard, today's plan, risk center, command center, compliance center, model center

**Ops:** Terraform, secrets/env separation, CloudWatch alarms, SNS, runbooks, release checklist

**Evals:** golden tests, adversarial blocker tests, schema compliance, simulation drift, operator command tests
