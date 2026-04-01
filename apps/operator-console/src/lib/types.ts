// TypeScript types mirroring Phase 4A Pydantic models exactly.

// --- Enums ---
export type PortfolioLayer = 'core' | 'swing';
export type OrderSide = 'buy' | 'sell';
export type OrderType = 'market' | 'limit';
export type OrderStatus =
  | 'pending'
  | 'submitted'
  | 'filled'
  | 'partially_filled'
  | 'cancelled'
  | 'rejected'
  | 'expired';
export type RegimeClass = 'green' | 'mixed' | 'stressed';
export type Mode = 'paper' | 'shadow-live' | 'live';
export type OverrideAction =
  | 'cancel_entry'
  | 'reduce_size'
  | 'tighten_stop'
  | 'close_position'
  | 'freeze_symbol';
export type BlockerCategory =
  | 'earnings_window'
  | 'corporate_action'
  | 'credibility_risk'
  | 'overnight_gap'
  | 'sector_shock'
  | 'aggregate_risk'
  | 'time_stop'
  | 'regime_block';
export type SignalDirection = 'long' | 'flat';
export type ExecutionTiming = 'next_open';
export type ComplianceCheckStatus = 'pass' | 'fail' | 'skipped' | 'warning';
export type CommandStatus = 'executed' | 'rejected' | 'error';

// --- Response Envelopes ---
export interface APIResponse<T> {
  success: boolean;
  data: T | null;
  error: string | null;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  total: number;
  page: number;
  page_size: number;
  timestamp: string;
}

// --- Regime ---
export interface RegimeState {
  assessed_at: string;
  regime_class: RegimeClass;
  nifty50_trend: 'bullish' | 'bearish' | 'neutral';
  breadth_above_50dma_pct: string;
  breadth_above_200dma_pct: string;
  vix_level: string | null;
  vix_state: 'low' | 'normal' | 'elevated' | 'extreme';
  gap_frequency_5d: string;
  sector_concentration_score: string;
  correlation_state: 'compressed' | 'normal' | 'expanded';
  sizing_multiplier: string;
  rationale: string;
}

// --- Risk ---
export interface PortfolioRisk {
  open_risk_pct: string;
  position_count: number;
  sector_exposure: Record<string, string>;
  largest_position_pct: string;
  breaches: string[];
}

export interface RiskLimits {
  swing_risk_per_trade_pct: string;
  core_add_risk_pct: string;
  core_position_cap_pct: string;
  swing_position_cap_pct: string;
  sector_cap_pct: string;
  aggregate_open_risk_pct: string;
  max_new_swing_entries_per_day: number;
}

export interface SectorUtilization {
  sector: string;
  exposure_pct: string;
  limit_pct: string;
  utilization_pct: string;
}

export interface LimitUtilization {
  aggregate_risk_used_pct: string;
  aggregate_risk_limit_pct: string;
  aggregate_risk_utilization_pct: string;
  sector_utilization: Record<string, SectorUtilization>;
  worst_sector: string | null;
}

export interface PositionRiskDetail {
  symbol: string;
  layer: PortfolioLayer;
  risk_amount: string;
  risk_pct: string;
  position_pct: string;
  sector: string;
}

export interface RiskCenterData {
  portfolio_risk: PortfolioRisk;
  risk_limits: RiskLimits;
  limit_utilization: LimitUtilization;
  position_risk_breakdown: PositionRiskDetail[];
}

// --- Config ---
export interface ConfigSnapshot {
  snapshot_id: string;
  captured_at: string;
  mode: Mode;
  armed_live: boolean;
  risk_limits: RiskLimits;
  regime_state: RegimeClass;
  universe_size: number;
  active_blockers_count: number;
  config_checksum: string;
}

export interface ConfigChange {
  field: string;
  old_value: string;
  new_value: string;
}

export interface ConfigDiff {
  snapshot_a_id: string;
  snapshot_b_id: string;
  snapshot_a_time: string;
  snapshot_b_time: string;
  changes: ConfigChange[];
}

// --- Reconciliation ---
export interface ReconciliationReport {
  is_clean: boolean;
  position_mismatches: number;
  order_mismatches: number;
  details: string[];
}

// --- EOD Report ---
export interface EODRunReport {
  run_id: string;
  trading_date: string;
  mode: Mode;
  started_at: string;
  completed_at: string;
  regime: RegimeState;
  candidates_scanned: number;
  swing_candidates_passing: number;
  core_candidates_passing: number;
  entries_approved: number;
  entries_rejected: number;
  exits_triggered: number;
  orders_filled: number;
  portfolio_risk: PortfolioRisk;
  reconciliation: ReconciliationReport;
  errors: string[];
  is_successful: boolean;
}

// --- Dashboard ---
export interface SystemHealth {
  data_feed_fresh: boolean;
  broker_healthy: boolean;
  ledger_healthy: boolean;
  last_run_successful: boolean;
  last_run_time: string | null;
}

export interface DashboardData {
  mode: Mode;
  armed_live: boolean;
  portfolio_equity: string;
  portfolio_cash: string;
  total_positions: number;
  open_risk_pct: string;
  regime: RegimeState;
  todays_pnl: string;
  total_unrealized_pnl: string;
  total_realized_pnl: string;
  pending_orders: number;
  last_eod_run: EODRunReport | null;
  alerts_count_today: number;
  system_health: SystemHealth;
}

// --- Order ---
export interface OrderIntent {
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  quantity: number;
  limit_price: string | null;
  stop_price: string;
  layer: PortfolioLayer;
  execution_timing: ExecutionTiming;
  max_slippage_pct: string;
}

export interface OrderStateTransition {
  order_id: string;
  from_status: OrderStatus;
  to_status: OrderStatus;
  timestamp: string;
  reason: string | null;
  fill_price: string | null;
  filled_qty: number | null;
}

export interface OrderRecord {
  order_id: string;
  intent: OrderIntent;
  current_status: OrderStatus;
  submitted_at: string | null;
  filled_at: string | null;
  fill_price: string | null;
  filled_qty: number;
  remaining_qty: number;
  transitions: OrderStateTransition[];
  created_at: string;
}

// --- Positions ---
export interface PositionDetail {
  symbol: string;
  layer: PortfolioLayer;
  quantity: number;
  entry_price: string;
  current_price: string;
  stop_price: string;
  risk_amount: string;
  sector: string;
  entry_date: string;
  unrealized_pnl: string;
  unrealized_pnl_pct: string;
  risk_pct_of_equity: string;
  days_held: number;
  distance_to_stop_pct: string;
  distance_to_2r_pct: string | null;
}

// --- Plan ---
export interface ExitWatchItem {
  symbol: string;
  layer: PortfolioLayer;
  current_price: string;
  stop_price: string;
  distance_to_stop_pct: string;
  distance_to_2r_pct: string | null;
  days_below_200dma: number;
}

export interface BlockedSymbolSummary {
  symbol: string;
  blocker_categories: BlockerCategory[];
  expires_at: string | null;
}

export interface SwingCandidate {
  symbol: string;
  close: string;
  entry_price: string;
  stop_price: string;
  volume_ratio: string;
  atr: string;
  passes_all: boolean;
}

export interface TodaysPlan {
  trading_date: string;
  regime: RegimeState;
  pending_entries: OrderRecord[];
  pending_exits: OrderRecord[];
  exit_watchlist: ExitWatchItem[];
  candidate_preview: SwingCandidate[];
  blocked_symbols: BlockedSymbolSummary[];
}

// --- Audit / Alerts ---
export interface AuditEvent {
  event_id: string;
  timestamp: string;
  event_type: string;
  source_service: string;
  mode: Mode;
  payload: Record<string, unknown>;
  related_symbol: string | null;
  operator_visible: boolean;
}

// --- Compliance ---
export interface ComplianceCheck {
  check_name: string;
  status: ComplianceCheckStatus;
  message: string;
  checked_at: string;
}

export interface ComplianceStatus {
  mode: Mode;
  armed_live: boolean;
  checks: ComplianceCheck[];
  all_passed: boolean;
  eligible_for_live: boolean;
}

// Phase 6: ComplianceReport from real gate
export interface ComplianceResult {
  check_name: string;
  status: ComplianceCheckStatus;
  message: string;
  checked_at: string;
}

export interface ComplianceReport {
  results: ComplianceResult[];
  all_blocking_passed: boolean;
  generated_at: string;
  mode: Mode;
}

// --- Broker ---
export interface BrokerSession {
  session_id: string;
  expires_at: string;
  broker_name: string;
  is_live: boolean;
}

export interface BrokerHealth {
  is_healthy: boolean;
  latency_ms: number;
  last_checked: string;
  session_valid: boolean;
  error_message: string | null;
}

// --- Shadow Run ---
export interface ShadowRunReport {
  trading_date: string;
  regime_state: string;
  candidates_scanned: number;
  intents_generated: OrderIntent[];
  orders_dry_run: OrderRecord[];
  blockers_triggered: unknown[];
  audit_events_count: number;
  completed_at: string;
  errors: string[];
}

// --- Live Run ---
export interface LiveRunReport {
  trading_date: string;
  mode: Mode;
  orders_submitted: OrderRecord[];
  orders_filled: OrderRecord[];
  orders_cancelled: OrderRecord[];
  positions_before: unknown[];
  positions_after: unknown[];
  reconciliation_result: ReconciliationReport;
  risk_utilization: PortfolioRisk;
  anomalies: string[];
  reviewed_by_operator: boolean;
  review_notes: string | null;
  generated_at: string;
}

export interface ComplianceStatusResponse {
  report: ComplianceReport;
  live_ready: boolean;
}

// --- Commands ---
export interface OperatorCommand {
  command_type: OverrideAction;
  symbol: string;
  parameters: Record<string, unknown>;
  reason: string;
}

export interface CommandResult {
  command_id: string;
  command_type: OverrideAction;
  symbol: string;
  status: CommandStatus;
  message: string;
  audit_event_id: string;
  resulting_order: OrderRecord | null;
}

// --- Simulation ---
export interface SimulationSummary {
  simulation_id: string;
  start_date: string;
  end_date: string;
  trading_days_run: number;
  initial_equity: string;
  final_equity: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  total_return_pct: string;
  max_drawdown_pct: string;
  daily_reports: EODRunReport[];
  all_reconciliations_clean: boolean;
  errors_encountered: string[];
}

