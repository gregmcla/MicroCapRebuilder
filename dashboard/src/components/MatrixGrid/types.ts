import type { CrossPortfolioMover, Position, Transaction, WatchlistCandidate, ScanJobStatus, TradeRationale } from "../../lib/types";

export interface MatrixPortfolio {
  id: string;
  name: string;
  abbr: string;
  color: string;
  hex: [number, number, number];
  equityCurve?: number[];
}

export interface MatrixPosition {
  ticker: string;
  portfolioId: string;
  portfolioName: string;
  portfolioAbbr: string;
  portfolioColor: string;
  portfolioHex: [number, number, number];
  value: number;
  perf: number;
  day: number;
  sparkline: number[];
  sector: string;
  vol: number | null;
  beta: number | null;
  mktCap: string;
  // Portfolio-view extras (undefined in overview mode)
  shares?: number;
  avgCost?: number;
  currentPrice?: number;
  unrealizedPnl?: number;
  stopLoss?: number;
  takeProfit?: number;
  entryDate?: string;
  dayChangeDollar?: number;
  alpha?: number;
}

export interface MatrixGridProps {
  positions: MatrixPosition[];
  portfolios: MatrixPortfolio[];
  onPositionClick?: (pos: MatrixPosition) => void;
  onBack?: () => void;
  initialFilter?: string;
  showEKG?: boolean;
  showTickerTape?: boolean;
  transactions?: Transaction[];
  watchlistCandidates?: WatchlistCandidate[];
  scanStatus?: ScanJobStatus;
  showSecondaryTabs?: boolean; // show WATCHLIST/ACTIVITY/LOGS tabs (default true, false for overview)
  filterOverride?: string | null; // when defined, overrides internal filter state and hides filter chips
  positionRationales?: Record<string, TradeRationale>; // trade rationale per ticker (from PortfolioState)
}

// Re-export for convenience in mapping functions
export type { CrossPortfolioMover, Position, Transaction, WatchlistCandidate, ScanJobStatus, TradeRationale };
