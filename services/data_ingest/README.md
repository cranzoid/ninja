# Data Ingest Service

Ingests market data across four lanes: Signal (OHLCV, indicators), Execution (broker positions/orders/fills), Corporate-action (splits, bonuses, rights, mergers), and Context (earnings, news, flags, pledge data).

Starts with NIFTY 100 universe. Handles normalization, versioning, and reconciliation.

See [PROJECT_CHARTER_V2.md](../../docs/PROJECT_CHARTER_V2.md) §9 for data architecture details.
