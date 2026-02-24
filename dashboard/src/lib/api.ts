/** Typed fetch wrappers for the FastAPI backend. */

import type {
  PortfolioState,
  RiskScoreboard,
  Warning,
  MommyInsight,
  AnalysisResult,
  PerformanceData,
  LearningData,
  MarketIndices,
  ChartData,
  ScanResult,
  PortfolioList,
  OverviewData,
  CreatePortfolioRequest,
  PortfolioMeta,
  GenerateStrategyRequest,
  GeneratedStrategy,
  TradingStyle,
} from "./types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  // --- Portfolio management (no portfolio_id prefix) ---
  getPortfolios: () => get<PortfolioList>("/portfolios"),
  getOverview: () => get<OverviewData>("/portfolios/overview"),
  getUniverses: () => get<Record<string, { label: string }>>("/portfolios/universes"),
  createPortfolio: (req: CreatePortfolioRequest) =>
    post<{ portfolio: PortfolioMeta; message: string }>("/portfolios", req),
  deletePortfolio: (id: string) =>
    del<{ message: string }>(`/portfolios/${id}`),
  generateStrategy: (req: GenerateStrategyRequest) =>
    post<GeneratedStrategy>("/portfolios/generate-strategy", req),
  getTradingStyles: () => get<Record<string, TradingStyle>>("/portfolios/trading-styles"),
  getSectors: () => get<{ sectors: string[] }>("/portfolios/sectors"),

  // --- Portfolio-scoped endpoints ---
  getState: (pid: string) => get<PortfolioState>(`/${pid}/state`),
  refreshState: (pid: string) => get<PortfolioState>(`/${pid}/state/refresh`),
  getRisk: (pid: string) => get<RiskScoreboard>(`/${pid}/risk`),
  getWarnings: (pid: string) => get<Warning[]>(`/${pid}/warnings`),
  getMommyInsight: (pid: string) => get<MommyInsight>(`/${pid}/mommy/insight`),
  getPerformance: (pid: string) => get<PerformanceData>(`/${pid}/performance`),
  getLearning: (pid: string) => get<LearningData>(`/${pid}/learning`),
  analyze: (pid: string) => post<AnalysisResult>(`/${pid}/analyze`),
  execute: (pid: string) => post<Record<string, unknown>>(`/${pid}/execute`),
  chat: (pid: string, message: string) =>
    post<{ message: string; success: boolean; error: string | null }>(`/${pid}/chat`, { message }),
  updatePrices: (pid: string) => get<PortfolioState>(`/${pid}/state/refresh`),
  scan: (pid: string) => post<ScanResult>(`/${pid}/scan`),
  sellPosition: (pid: string, ticker: string) =>
    post<{
      ticker: string;
      shares: number;
      price: number;
      total_value: number;
      unrealized_pnl: number;
      unrealized_pnl_pct: number;
      message: string;
    }>(`/${pid}/sell/${ticker}`),
  toggleMode: (pid: string) => post<{ paper_mode: boolean; message: string }>(`/${pid}/mode/toggle`),
  closeAll: (pid: string) =>
    post<{
      closed: number;
      positions: Array<{ ticker: string; shares: number; price: number; total_value: number; unrealized_pnl: number; unrealized_pnl_pct: number }>;
      total_value: number;
      total_pnl: number;
      message: string;
    }>(`/${pid}/close-all`),

  // --- Market endpoints (global, not portfolio-scoped) ---
  getMarketIndices: () => get<MarketIndices>("/market/indices"),
  getChartData: (ticker: string, range: string = "1M") =>
    get<ChartData>(`/market/chart/${ticker}?range=${range}`),
};
