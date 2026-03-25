import type { CrossPortfolioMover, Position, MatrixPosition, MatrixPortfolio } from "./types";

export const PORTFOLIO_COLORS: Array<{ color: string; hex: [number, number, number] }> = [
  { color: "#22d3ee", hex: [34, 211, 238] },
  { color: "#f59e0b", hex: [245, 158, 11] },
  { color: "#a78bfa", hex: [167, 139, 250] },
  { color: "#34d399", hex: [52, 211, 153] },
  { color: "#f87171", hex: [248, 113, 113] },
  { color: "#fb923c", hex: [251, 146, 60] },
  { color: "#f472b6", hex: [244, 114, 182] },
  { color: "#bef264", hex: [190, 242, 100] },
];

export const BG_COLOR = "#040608";
export const ACCENT_GREEN = "#4ade80";
export const DANGER_RED = "#f87171";
export const MATRIX_FONT = "'Azeret Mono','JetBrains Mono','Fira Code',monospace";

export function portfolioAbbr(id: string): string {
  const map: Record<string, string> = {
    microcap: "MC", ai: "AI", sph: "SP", new: "NW",
    largeboi: "LB", "10k": "TK", klop: "KL",
  };
  return map[id] ?? id.slice(0, 2).toUpperCase();
}

export function genSparkline(perf: number): number[] {
  const pts: number[] = [];
  let v = 50;
  const seed = Math.abs(perf * 13.7);
  for (let i = 0; i < 28; i++) {
    const r = ((seed + i * 7.3) % 100) / 100;
    v += (r - 0.47 + perf * 0.008) * 5;
    v = Math.max(5, Math.min(95, v));
    pts.push(v);
  }
  return pts;
}

export function buildPortfolioMap(
  portfolioIds: Array<{ id: string; name: string }>
): Map<string, MatrixPortfolio> {
  const sorted = [...portfolioIds].sort((a, b) => a.id.localeCompare(b.id));
  const map = new Map<string, MatrixPortfolio>();
  sorted.forEach((p, i) => {
    const palette = PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length];
    map.set(p.id, {
      id: p.id,
      name: p.name,
      abbr: portfolioAbbr(p.id),
      color: palette.color,
      hex: palette.hex,
    });
  });
  return map;
}

export function crossMoverToMatrix(
  mover: CrossPortfolioMover,
  portfolioMap: Map<string, MatrixPortfolio>
): MatrixPosition {
  const port = portfolioMap.get(mover.portfolio_id) ?? {
    id: mover.portfolio_id,
    name: mover.portfolio_name,
    abbr: portfolioAbbr(mover.portfolio_id),
    color: ACCENT_GREEN,
    hex: [74, 222, 128] as [number, number, number],
  };
  return {
    ticker: mover.ticker,
    portfolioId: port.id,
    portfolioName: port.name,
    portfolioAbbr: port.abbr,
    portfolioColor: port.color,
    portfolioHex: port.hex,
    value: mover.market_value ?? 0,
    perf: mover.pnl_pct,
    day: mover.day_change_pct ?? 0,
    sparkline: genSparkline(mover.pnl_pct),
    sector: "N/A",
    vol: null,
    beta: null,
    mktCap: "N/A",
  };
}

export function positionToMatrix(pos: Position, port: MatrixPortfolio): MatrixPosition {
  return {
    ticker: pos.ticker,
    portfolioId: port.id,
    portfolioName: port.name,
    portfolioAbbr: port.abbr,
    portfolioColor: port.color,
    portfolioHex: port.hex,
    value: pos.market_value,
    perf: pos.unrealized_pnl_pct,
    day: pos.day_change_pct ?? 0,
    sparkline: genSparkline(pos.unrealized_pnl_pct),
    sector: "N/A",
    vol: null,
    beta: null,
    mktCap: "N/A",
    shares: pos.shares,
    avgCost: pos.avg_cost_basis,
    currentPrice: pos.current_price,
    unrealizedPnl: pos.unrealized_pnl,
    stopLoss: pos.stop_loss,
    takeProfit: pos.take_profit,
    entryDate: pos.entry_date,
    dayChangeDollar: pos.day_change,
    alpha: pos.alpha,
  };
}

export const pc = (p: number): string =>
  p > 5 ? "#4ade80" : p > 0 ? "#86c98e" : p > -5 ? "#c98e86" : "#f87171";

export const pbg = (p: number): string => {
  if (p > 15) return "#163826";
  if (p > 5)  return "#0f2a1a";
  if (p > 0)  return "#0a1c10";
  if (p > -5) return "#1c0a0a";
  if (p > -10) return "#2a0f0f";
  return "#381616";
};

export const fv = (v: number): string =>
  v >= 1000 ? `${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k` : String(Math.round(v));
