/** TypeScript interfaces for API responses. */

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
  timestamp: string;
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

export interface MommyInsight {
  insight: string;
  category: "alert" | "warning" | "performance" | "idle";
  warnings_count: number;
  critical_count: number;
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

// --- Analysis types ---

export interface FactorScores {
  momentum: number;
  volatility: number;
  volume: number;
  relative_strength: number;
  mean_reversion: number;
  rsi: number;
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
}
