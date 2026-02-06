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
  chat: (message: string) => post<{ response: string }>("/chat", { message }),
  updatePrices: () => post<{ updated: number; total_equity: number; unrealized_pnl: number }>("/state/update"),
};
