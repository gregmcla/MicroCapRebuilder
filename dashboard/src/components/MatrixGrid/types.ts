import type { CrossPortfolioMover, Position } from "../../lib/types";

export interface MatrixPortfolio {
  id: string;
  name: string;
  abbr: string;
  color: string;
  hex: [number, number, number];
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
}

export interface MatrixGridProps {
  positions: MatrixPosition[];
  portfolios: MatrixPortfolio[];
  onPositionClick?: (pos: MatrixPosition) => void;
  onBack?: () => void;
  initialFilter?: string;
  showEKG?: boolean;
  showTickerTape?: boolean;
}

// Re-export for convenience in mapping functions
export type { CrossPortfolioMover, Position };
