/** TypeScript interfaces for API responses. */

export interface TickerInfo {
  ticker: string;
  name: string;
  description: string | null;
  sector: string | null;
  industry: string | null;
  website: string | null;
  employees: number | null;
  market_cap: number | null;
  trailing_pe: number | null;
  forward_pe: number | null;
  week_52_high: number | null;
  week_52_low: number | null;
  analyst_target: number | null;
  analyst_rating: string | null;
  analyst_count: number | null;
  dividend_yield: number | null;
  beta: number | null;
}

// --- Portfolio types ---

export interface PortfolioMeta {
  id: string;
  name: string;
  universe: string;
  created: string;
  starting_capital: number;
  active: boolean;
}

export interface PortfolioList {
  portfolios: PortfolioMeta[];
  default_portfolio: string;
}

export interface PortfolioSummary {
  id: string;
  name: string;
  universe: string;
  equity: number;
  cash: number;
  positions_value: number;
  num_positions: number;
  regime: string | null;
  paper_mode: boolean;
  unrealized_pnl: number;
  day_pnl: number;
  all_time_pnl: number;
  total_return_pct: number;
  deployed_pct: number;
  sparkline?: number[];
  equity_curve?: number[];
  error?: string;
}

export interface CrossPortfolioMover {
  portfolio_id: string;
  portfolio_name: string;
  ticker: string;
  pnl: number;
  pnl_pct: number;
  market_value?: number;
  day_change_pct?: number;
}

export interface OverviewData {
  total_equity: number;
  total_cash: number;
  total_day_pnl: number;
  total_unrealized_pnl: number;
  total_all_time_pnl: number;
  total_return_pct: number;
  total_positions: number;
  top_movers: CrossPortfolioMover[];
  bottom_movers: CrossPortfolioMover[];
  all_positions: CrossPortfolioMover[];
  portfolios: PortfolioSummary[];
}

export interface CreatePortfolioRequest {
  id: string;
  name: string;
  universe: string;
  starting_capital: number;
  sectors?: string[];
  sector_weights?: Record<string, number>;
  trading_style?: string;
  ai_config?: AiConfig;
  ai_driven?: boolean;
  strategy_dna?: string;
}

// --- Existing types ---

export interface Position {
  ticker: string;
  shares: number;
  avg_cost_basis: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  stop_loss: number;
  take_profit: number;
  entry_date: string;
  day_change?: number;
  day_change_pct?: number;
  alpha?: number;
}

export interface TradeRationale {
  ai_decision: "APPROVE" | "MODIFY" | "VETO" | string;
  ai_confidence: number;
  ai_reasoning: string;
  quant_reason: string;
  regime: string;
  top_factors: Array<{ name: string; score: number }>;
}

export interface Transaction {
  transaction_id: string;
  date: string;
  ticker: string;
  action: "BUY" | "SELL";
  shares: number;
  price: number;
  total_value: number;
  stop_loss: number | null;
  take_profit: number | null;
  reason: string;
  factor_scores?: string | null;
  composite_score?: number | null;
  regime_at_entry?: string | null;
  signal_rank?: number | null;
  realized_pnl?: number | null;
  realized_pnl_pct?: number | null;
  entry_price?: number | null;
  trade_rationale?: string | null;
}

export interface Snapshot {
  date: string;
  cash: number;
  positions_value: number;
  total_equity: number;
  day_pnl: number;
  day_pnl_pct: number;
  benchmark_value: number | null;
}

export interface RegimeAnalysis {
  regime: string;
  sma_50: number;
  sma_200: number;
  benchmark_price: number;
  position_size_factor: number;
}

export interface PortfolioState {
  cash: number;
  positions: Position[];
  transactions: Transaction[];
  snapshots: Snapshot[];
  regime: string;
  regime_analysis: RegimeAnalysis | null;
  positions_value: number;
  total_equity: number;
  num_positions: number;
  config: Record<string, unknown>;
  stale_alerts: string[];
  paper_mode: boolean;
  price_failures: string[];
  day_pnl: number;
  day_pnl_pct: number;
  total_return_pct: number;
  all_time_pnl: number;
  realized_pnl: number;
  cagr_pct: number;
  spx_return_pct?: number | null;
  ndx_return_pct?: number | null;
  rut_return_pct?: number | null;
  spx_alpha?: number | null;
  ndx_alpha?: number | null;
  rut_alpha?: number | null;
  starting_capital: number;
  timestamp: string;
  position_rationales?: Record<string, TradeRationale>;
}

export interface RiskComponent {
  name: string;
  score: number;
  weight: number;
  value: number;
  threshold_warning: number;
  threshold_danger: number;
  status: "OK" | "WARNING" | "DANGER";
  narrative: string;
}

export interface RiskScoreboard {
  overall_score: number;
  risk_level: string;
  risk_color: string;
  components: RiskComponent[];
  narrative: string;
  recommended_actions: string[];
}

export interface Warning {
  id: string;
  severity: "info" | "medium" | "high" | "critical";
  title: string;
  description: string;
  category: string;
  metric_name: string | null;
  metric_value: number | null;
  threshold: number | null;
  action_suggestion: string;
  timestamp: string;
}

// --- Performance types ---

export interface HealthComponent {
  name: string;
  score: number;
  weight: number;
  grade: string;
  details: Record<string, unknown>;
  issues: string[];
  strengths: string[];
}

export interface StrategyHealth {
  score: number;
  grade: string;
  grade_description: string;
  components: HealthComponent[];
  diagnosis: string;
  what_working: string[];
  what_struggling: string[];
  recommendations: string[];
  pivot_recommended: boolean;
  pivot_urgency: string;
}

export interface FactorAttribution {
  factor: string;
  contribution: number;
  contribution_pct: number;
  narrative: string;
}

export interface TradeContribution {
  ticker: string;
  pnl: number;
  pnl_pct: number;
  entry_date: string;
  factor_scores: Record<string, number>;
  regime_at_entry: string;
  is_realized: boolean;
}

export interface PerformanceAttribution {
  period: string;
  start_date: string;
  end_date: string;
  total_return: number;
  total_return_pct: number;
  attribution_by_factor: Record<string, number>;
  factor_details: FactorAttribution[];
  attribution_by_regime: Record<string, number>;
  top_contributors: TradeContribution[];
  bottom_contributors: TradeContribution[];
  narrative: string;
}

export interface RiskMetrics {
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  calmar_ratio: number;
  volatility_annual: number;
  total_return_pct: number;
  cagr_pct: number;
  current_drawdown_pct: number;
  exposure_pct: number;
  days_tracked: number;
  benchmark_return_pct: number;
  alpha_pct: number;
}

export interface PerformanceData {
  health: StrategyHealth;
  attribution: PerformanceAttribution | null;
  metrics: RiskMetrics | null;
}

export interface FactorSummaryEntry {
  factor: string;
  win_rate: number;
  total_trades: number;
  total_contribution: number;
  trend: string;
  best_regime: string;
}

export interface WeightSuggestion {
  factor: string;
  current_weight: number;
  suggested_weight: number;
  change_pct: number;
  reason: string;
  confidence: string;
}

export interface LearningData {
  factor_summary: {
    status: string;
    factors: FactorSummaryEntry[];
    total_analyzed_trades: number;
    last_updated: string;
  };
  weight_suggestions: WeightSuggestion[];
}

export interface MarketIndex {
  value: number;
  change_pct: number;
  sparkline: number[];
}

export interface MarketIndices {
  sp500: MarketIndex;
  russell2000: MarketIndex;
  vix: MarketIndex;
}

// --- Chart data types ---

export interface ChartDataPoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChartIndicators {
  rsi: (number | null)[];
  sma_20: (number | null)[];
  sma_50: (number | null)[];
}

export interface ChartData {
  ticker: string;
  range: string;
  data: ChartDataPoint[];
  indicators: ChartIndicators;
}

// --- Scan/Discovery types ---

export interface ScanResult {
  discovered: number;
  added: number;
  marked_stale: number;
  removed: number;
  poor_performers_removed: number;
  sector_balanced: Record<string, number>;
  total_active: number;
  elapsed_seconds?: number;
}

export interface WatchlistCandidate {
  ticker: string;
  score: number;
  sector: string;
  source: string;
  notes: string;
  added_date: string;
  social_heat?: string        // "COLD" | "WARM" | "HOT" | "SPIKING"
  social_rank?: number | null
  social_bullish_pct?: number | null
}

export interface WatchlistData {
  candidates: WatchlistCandidate[];
  total: number;
}

export interface ScanJobStatus {
  status: "idle" | "running" | "complete" | "error";
  started_at?: string;
  finished_at?: string;
  result?: ScanResult | null;
  error?: string | null;
  message?: string;
}

// --- Analysis types ---

export interface FactorScores {
  price_momentum: number;
  earnings_growth: number;
  quality: number;
  volume: number;
  volatility: number;
  value_timing: number;
}

export interface ProposedAction {
  action_type: "BUY" | "SELL";
  ticker: string;
  shares: number;
  price: number;
  stop_loss: number;
  take_profit: number;
  quant_score: number;
  factor_scores: FactorScores;
  regime: string;
  reason: string;
}

export interface ReviewedAction {
  original: ProposedAction;
  decision: "APPROVE" | "MODIFY" | "VETO";
  ai_reasoning: string;
  confidence: number;
  modified_shares: number | null;
  modified_stop: number | null;
  modified_target: number | null;
}

export interface AnalysisSummary {
  total_proposed: number;
  approved: number;
  modified: number;
  vetoed: number;
  can_execute: boolean;
}

export interface AnalysisResult {
  proposed_actions: ProposedAction[];
  reviewed_actions: ReviewedAction[];
  approved: ReviewedAction[];
  modified: ReviewedAction[];
  vetoed: ReviewedAction[];
  summary: AnalysisSummary;
  portfolio_context: Record<string, unknown>;
  regime: string;
  timestamp: string;
  ai_mode?: "claude" | "mechanical" | "mechanical_fallback";
}

export interface ExecutionSummary {
  proposed: { buys: number; sells: number };
  executed: { buys: number; sells: number };
  dropped: Array<{ ticker: string; reason: string }>;
  ai_mode: string;
}

// --- Strategy generation types ---

export interface AiConfig {
  sectors?: string[];
  sector_weights?: Record<string, number>;
  trading_style?: string;
  scoring_weights?: Record<string, number>;
  stop_loss_pct?: number;
  risk_per_trade_pct?: number;
  max_position_pct?: number;
  scan_types?: Record<string, boolean>;
  etf_sources?: string[];
  strategy_name?: string;
  rationale?: string;
  prompt?: string;
}

export interface SuggestConfigRequest {
  strategy_dna: string;
  starting_capital: number;
}

export interface ScreenerConfig {
  enabled: boolean;
  sectors: string[];
  industries: string[];
  market_cap_min: number;
  market_cap_max: number;
  region: string;
}

export interface AiRefinementConfig {
  enabled: boolean;
  prompt: string;
}

export interface SuggestConfigResponse {
  name: string;
  universe: string;
  etfs: string[];
  stop_loss_pct: number;
  take_profit_pct: number;
  risk_per_trade_pct: number;
  max_position_pct: number;
  max_positions: number;
  screener?: ScreenerConfig;
  ai_refinement?: AiRefinementConfig;
}

// ── System Logs ──────────────────────────────────────────────────────────────

export interface PipelineJob {
  status: "ok" | "failed" | "missing";
  ok: number;
  failed: number;
  ran_at: string | null;   // "HH:MM" or null if missing
  trades?: number;         // execute job only
}

export interface LogEvent {
  time: string;            // "HH:MM"
  type: "scan" | "execute" | "update" | "api_restart" | "failed";
  detail: string;
}

export interface DayLog {
  date: string;            // "YYYY-MM-DD"
  pipeline: {
    scan: PipelineJob;
    execute: PipelineJob;
    update_midday: PipelineJob;
    update_close: PipelineJob;
  };
  watchdog_restarts: number;
  events: LogEvent[];
}

export interface SystemLogsResponse {
  days: DayLog[];
}

export interface NarrativeResponse {
  date: string;
  narrative: string | null;
  generated_at: string;
  cached: boolean;
  error?: string;
}

// --- Intelligence Brief types ---

export interface SectorBreakdownEntry {
  count: number;
  value: number;
  pct: number;
}

export interface IntelligenceBriefData {
  health: StrategyHealth;
  metrics: RiskMetrics | null;
  factor_summary: LearningData["factor_summary"];
  weight_suggestions: WeightSuggestion[];
  factor_deltas: Record<string, number>;
  risk: RiskScoreboard;
  warnings: Warning[];
  sector_breakdown: Record<string, SectorBreakdownEntry>;
  top3_concentration_pct: number;
  positions_near_stop: string[];
  avg_position_age_days: number;
  avg_hold_days: number;
  most_traded_tickers: Array<{ ticker: string; count: number }>;
  config: Record<string, unknown>;
  total_return_pct: number;
  regime: string | null;
  regime_analysis: RegimeAnalysis | null;
  cash_pct: number;
  deployed_pct: number;
  num_positions: number;
  snapshots: Array<{ date: string; total_equity: number; day_pnl_pct: number }>;
  error?: string;
}

export interface AuditBriefResponse {
  brief: string | null;
  generated_at: string;
  cached: boolean;
  error?: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  reply: string;
  error?: string | null;
}

// ── Trade Reviews ─────────────────────────────────────────────────────────

export interface ClosedTradeFactorScores {
  momentum?: number;
  quality?: number;
  earnings?: number;
  volume?: number;
  volatility?: number;
  value_timing?: number;
  [key: string]: number | undefined;
}

export interface ClosedTrade {
  trade_id: string;
  ticker: string;
  entry_date: string;
  exit_date: string;
  holding_days: number;
  entry_price: number | null;
  exit_price: number | null;
  shares: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  exit_reason: string;
  regime_at_entry: string;
  regime_at_exit: string;
  entry_ai_reasoning: string;
  exit_ai_reasoning: string;
  factor_scores: ClosedTradeFactorScores;
  what_worked: string;
  what_failed: string;
  recommendation: string;
  summary: string;
}

export interface TradeReviewsResponse {
  trades: ClosedTrade[];
}

export interface TradeAnalyzeResponse {
  narrative: string;
}
