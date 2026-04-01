# Live Broker Service

Production broker adapter for real order execution. Implements the standard broker adapter contract with live session management, static IP requirements, and order-rate governance.

Cannot arm without passing the full pre-live compliance gate. Requires explicit MODE=live and ARMED_LIVE=true configuration.

See [PROJECT_CHARTER_V2.md](../../docs/PROJECT_CHARTER_V2.md) §10 and §11 for compliance gate and broker contract.
