# Model Router Service

Routes LLM requests to appropriate providers based on capability roles: thesis extraction, blocker classification, deep reasoning, and operator explanation.

Implements tiered routing (Tier 0-3), structured output validation, retry/fallback logic, and cost/latency telemetry. Provider-agnostic with Bedrock-first production posture.

See [PROJECT_CHARTER_V2.md](../../docs/PROJECT_CHARTER_V2.md) §7 for AI architecture details.
