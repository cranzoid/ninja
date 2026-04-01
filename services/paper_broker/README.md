# Paper Broker Service

Simulates broker execution for paper trading mode. Implements the same broker adapter contract as the live broker (authenticate, get_quotes, place_order, modify_order, cancel_order, get_positions, get_orders, healthcheck) with realistic execution assumptions.

The same engine runs in paper and live — only the broker adapter differs.

See [PROJECT_CHARTER_V2.md](../../docs/PROJECT_CHARTER_V2.md) §11 for the broker adapter contract.
