# Historical Stress Testing

Phase 3B adds the ability to run the existing `PaperSimulationRunner` against
2 years of real NSE OHLCV data (2023–2024) to validate strategy behaviour
before Gate C is cleared.

All backtest runs use `MODE=paper`. The live compliance gate, `assert_not_live()`,
and Zerodha adapter are completely bypassed.

---

## Setup (one time)

Download 2 years of OHLCV data for all 25 universe symbols from Yahoo Finance:

```bash
python scripts/download_historical.py
```

Saves data to `data/historical/{SYMBOL}/ohlcv.parquet`.

To force re-download of existing files:

```bash
python scripts/download_historical.py --force
```

---

## Run backtest

```bash
python scripts/run_backtest.py --start 2023-01-01 --end 2024-12-31 --equity 50000
```

The script prints a formatted terminal summary and saves a full `BacktestReport`
JSON to `data/backtest_results/{run_id}.json`.

---

## Interpreting results

| Metric | Healthy signal |
|--------|---------------|
| Alpha > 0 | Strategy outperformed buy-and-hold NIFTY 50 |
| Max drawdown < 20% | Position sizing is reasonable |
| STRESSED trades near 0 | Regime engine correctly suppressed trading |
| All reconciliations clean | No silent bugs in the paper broker |
| Days with errors = 0 | Engine stack ran without crashes |

### Alpha

`alpha_pct = total_return_pct - nifty_return_pct`

Positive alpha means the strategy added value beyond simply holding the index.
Negative alpha with controlled drawdown may still be acceptable if the strategy
demonstrated superior risk-adjusted returns.

### Max drawdown

Worst peak-to-trough move as a percentage of equity. Values above 25–30%
suggest position sizing is too aggressive for the live capital of ₹50,000.

### STRESSED trades near 0

The regime engine suppresses new swing entries when the market is STRESSED.
A non-zero STRESSED trade count is a red flag — it means entries slipped
through when the engine should have blocked them.

### Reconciliation

Clean reconciliation across all simulated days means the paper broker state
(orders, positions, cash) stayed consistent with the audit ledger. Any gaps
indicate a silent bug that must be investigated before Gate C.

---

## Gate C relevance

Clean backtest results are supporting evidence for Gate C clearance:

- Positive alpha, controlled drawdown, near-zero STRESSED trades,
  and zero reconciliation gaps across 2 years of data demonstrate that
  the strategy logic and engine stack behave as designed.
- Gate C also requires 2–3 weeks of live shadow runs (MODE=shadow-live)
  to confirm that real-time data ingestion and the Zerodha adapter work
  correctly end-to-end.

Backtest results alone do not clear Gate C — they must be reviewed alongside
the shadow run logs before the operator flips `ARMED_LIVE=true`.

---

## Architecture notes

### HistoricalDataProvider

`services/data_ingest/historical_provider.HistoricalDataProvider` implements
the same `MarketDataProvider` interface used by all other data providers.

Key constraint: `as_of_date` is enforced strictly in both `fetch_ohlcv` and
`fetch_current_quote`. The effective end date is always
`min(requested_end_date, as_of_date)`, which prevents any lookahead bias.

When the `EODOrchestrator` calls `fetch_ohlcv(symbol, lookback_start, trading_date)`,
the provider returns only rows up to `trading_date` — the simulation cannot
see the future.

### BacktestReport

`packages/contracts/backtest_report.BacktestReport` is a frozen Pydantic model
containing the full output of a historical simulation run including the equity
curve, daily reports, regime breakdown, and trade statistics.

Reports are saved as JSON to `data/backtest_results/` and can be loaded by
any downstream tooling (charting, operator console).
