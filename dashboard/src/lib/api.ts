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

export const api = {
  getState: () => get<PortfolioState>("/state"),
  refreshState: () => get<PortfolioState>("/state/refresh"),
  getRisk: () => get<RiskScoreboard>("/risk"),
  getWarnings: () => get<Warning[]>("/warnings"),
  getMommyInsight: () => get<MommyInsight>("/mommy/insight"),
  getPerformance: () => get<PerformanceData>("/performance"),
  getLearning: () => get<LearningData>("/learning"),
  getMarketIndices: () => get<MarketIndices>("/market/indices"),
  getChartData: (ticker: string, range: string = "1M") =>
    get<ChartData>(`/market/chart/${ticker}?range=${range}`),
  analyze: () => post<AnalysisResult>("/analyze"),
  execute: () => post<Record<string, unknown>>("/execute"),
  chat: (message: string) => post<{ message: string; success: boolean; error: string | null }>("/chat", { message }),
  updatePrices: () => get<PortfolioState>("/state/refresh"),
  toggleMode: () => post<{ paper_mode: boolean; message: string }>("/mode/toggle"),
  closeAll: () => post<{
    closed: number;
    positions: Array<{ ticker: string; shares: number; price: number; total_value: number; unrealized_pnl: number; unrealized_pnl_pct: number }>;
    total_value: number;
    total_pnl: number;
    message: string;
  }>("/close-all"),
};
