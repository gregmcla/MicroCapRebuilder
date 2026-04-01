/** Typed fetch wrappers for the FastAPI backend. */

import type {
  PortfolioState,
  RiskScoreboard,
  Warning,
  AnalysisResult,
  PerformanceData,
  LearningData,
  MarketIndices,
  ChartData,
  ScanJobStatus,
  WatchlistData,
  PortfolioList,
  OverviewData,
  CreatePortfolioRequest,
  PortfolioMeta,
  SuggestConfigRequest,
  SuggestConfigResponse,
  TickerInfo,
  TradeRationale,
  SystemLogsResponse,
  NarrativeResponse,
  IntelligenceBriefData,
  AuditBriefResponse,
  ChatMessage,
  ChatResponse,
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

async function put<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
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
  renamePortfolio: (id: string, name: string) =>
    put<{ success: boolean; name: string }>(`/portfolios/${id}/rename`, { name }),
  suggestConfig: (req: SuggestConfigRequest) =>
    post<SuggestConfigResponse>("/portfolios/suggest-config", req),

  // --- Portfolio-scoped endpoints ---
  getState: (pid: string) => get<PortfolioState>(`/${pid}/state`),
  refreshState: (pid: string) => get<PortfolioState>(`/${pid}/state/refresh`),
  getRisk: (pid: string) => get<RiskScoreboard>(`/${pid}/risk`),
  getWarnings: (pid: string) => get<Warning[]>(`/${pid}/warnings`),
  getPerformance: (pid: string) => get<PerformanceData>(`/${pid}/performance`),
  getLearning: (pid: string) => get<LearningData>(`/${pid}/learning`),
  analyze: (pid: string) => post<AnalysisResult>(`/${pid}/analyze`),
  execute: (pid: string) => post<Record<string, unknown>>(`/${pid}/execute`),
  updatePrices: (pid: string) => get<PortfolioState>(`/${pid}/state/refresh`),
  scan: (pid: string) => post<ScanJobStatus>(`/${pid}/scan`),
  scanStatus: (pid: string) => get<ScanJobStatus>(`/${pid}/scan/status`),
  getWatchlist: (pid: string) => get<WatchlistData>(`/${pid}/watchlist`),
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

  // --- Portfolio config ---
  getPortfolioConfig: (pid: string) => get<Record<string, unknown>>(`/portfolios/${pid}/config`),
  updatePortfolioConfig: (pid: string, changes: Record<string, unknown>) =>
    put<{ success: boolean; message: string }>(`/portfolios/${pid}/config`, { changes }),

  getDailyReport: (pid: string) => get<{ text: string }>(`/${pid}/report`),

  getTickerInfo: (pid: string, ticker: string) =>
    get<TickerInfo>(`/${pid}/position/${ticker}/info`),
  getPositionRationale: (pid: string, ticker: string) =>
    get<TradeRationale | Record<string, never>>(`/${pid}/position/${ticker}/rationale`),

  // --- Market endpoints (global, not portfolio-scoped) ---
  getMarketIndices: () => get<MarketIndices>("/market/indices"),
  getChartData: (ticker: string, range: string = "1M") =>
    get<ChartData>(`/market/chart/${ticker}?range=${range}`),

  // System logs
  getSystemLogs: (): Promise<SystemLogsResponse> =>
    get<SystemLogsResponse>("/system/logs"),

  generateNarrative: (logDate?: string, regenerate?: boolean): Promise<NarrativeResponse> => {
    const params = new URLSearchParams();
    if (logDate) params.set("date", logDate);
    if (regenerate) params.set("regenerate", "true");
    const qs = params.toString();
    return get<NarrativeResponse>(`/system/narrative${qs ? `?${qs}` : ""}`);
  },

  // Intelligence brief
  getIntelligenceBrief: (pid: string): Promise<IntelligenceBriefData> =>
    get<IntelligenceBriefData>(`/${pid}/intelligence-brief`),

  getAuditBrief: (pid: string, regenerate = false): Promise<AuditBriefResponse> =>
    get<AuditBriefResponse>(`/${pid}/intelligence-brief/audit${regenerate ? "?regenerate=true" : ""}`),

  postIntelligenceChat: (pid: string, messages: ChatMessage[]): Promise<ChatResponse> =>
    post<ChatResponse>(`/${pid}/intelligence-chat`, { messages }),
};
