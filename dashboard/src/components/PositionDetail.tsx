/** Position detail view — shown in right panel when a position is clicked. */

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Position } from "../lib/types";
import { useUIStore, usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import CandlestickChart from "./CandlestickChart";

function DetailRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/30">
      <span className="text-xs text-text-muted">{label}</span>
      <span className={`font-mono text-sm ${color ?? "text-text-primary"}`}>{value}</span>
    </div>
  );
}

function ProgressVisualization({ pos }: { pos: Position }) {
  const range = pos.take_profit - pos.stop_loss;
  const progress = range > 0 ? ((pos.current_price - pos.stop_loss) / range) * 100 : 50;
  const clamped = Math.max(0, Math.min(100, progress));

  return (
    <div className="mt-3 mb-2">
      <div className="flex justify-between text-[10px] text-text-muted mb-1">
        <span>Stop ${pos.stop_loss.toFixed(2)}</span>
        <span>Target ${pos.take_profit.toFixed(2)}</span>
      </div>
      <div className="relative h-3 bg-bg-primary rounded-full overflow-hidden">
        {/* Danger zone (0-20%) */}
        <div className="absolute left-0 top-0 h-full w-[20%] bg-loss/10 rounded-l-full" />
        {/* Target zone (80-100%) */}
        <div className="absolute right-0 top-0 h-full w-[20%] bg-profit/10 rounded-r-full" />
        {/* Current price marker */}
        <div
          className="absolute top-0 h-full w-1.5 rounded-full bg-accent shadow-[0_0_6px_rgba(34,211,238,0.5)]"
          style={{ left: `calc(${clamped}% - 3px)` }}
        />
      </div>
      <div className="flex justify-between text-[10px] mt-1">
        <span className="text-loss">
          {((pos.stop_loss / pos.current_price - 1) * 100).toFixed(1)}%
        </span>
        <span className="font-mono text-accent">
          ${pos.current_price.toFixed(2)}
        </span>
        <span className="text-profit">
          +{((pos.take_profit / pos.current_price - 1) * 100).toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

function SellButton({ pos }: { pos: Position }) {
  const queryClient = useQueryClient();
  const selectPosition = useUIStore((s) => s.selectPosition);
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const [showConfirm, setShowConfirm] = useState(false);
  const [selling, setSelling] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleSell = async () => {
    setSelling(true);
    setShowConfirm(false);
    try {
      const res = await api.sellPosition(portfolioId, pos.ticker);
      setResult(res.message);
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
      queryClient.invalidateQueries({ queryKey: ["chartData"] });
      setTimeout(() => {
        setResult(null);
        selectPosition(null);
      }, 3000);
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Sell failed");
      setTimeout(() => setResult(null), 5000);
    } finally {
      setSelling(false);
    }
  };

  const pnlColor = pos.unrealized_pnl >= 0 ? "text-profit" : "text-loss";

  return (
    <div className="relative">
      <button
        onClick={() => setShowConfirm(true)}
        disabled={selling}
        className="px-3 py-1 text-xs font-semibold rounded bg-loss/15 text-loss hover:bg-loss/25 transition-colors disabled:opacity-50"
      >
        {selling ? "Selling..." : "SELL"}
      </button>

      {result && (
        <span className="ml-2 text-xs text-text-muted">{result}</span>
      )}

      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-bg-elevated border border-border rounded-lg p-4 max-w-sm">
            <h3 className="text-sm font-semibold text-text-primary mb-2">
              Sell {pos.ticker}?
            </h3>
            <div className="bg-bg-surface rounded p-3 mb-3 space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-text-muted">Shares</span>
                <span className="font-mono">{pos.shares}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Price</span>
                <span className="font-mono">${pos.current_price.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Value</span>
                <span className="font-mono">${pos.market_value.toFixed(2)}</span>
              </div>
              <div className="flex justify-between border-t border-border pt-1 mt-1">
                <span className="text-text-muted">P&L</span>
                <span className={`font-mono font-semibold ${pnlColor}`}>
                  {pos.unrealized_pnl >= 0 ? "+" : ""}${pos.unrealized_pnl.toFixed(2)} ({pos.unrealized_pnl_pct >= 0 ? "+" : ""}{pos.unrealized_pnl_pct.toFixed(1)}%)
                </span>
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-3 py-1 text-xs font-semibold bg-bg-surface text-text-primary rounded hover:bg-border transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSell}
                className="px-3 py-1 text-xs font-semibold bg-loss/15 text-loss rounded hover:bg-loss/25 transition-colors"
              >
                Confirm Sell
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PositionDetail({ pos }: { pos: Position }) {
  const clearSelection = useUIStore((s) => s.selectPosition);
  const [range, setRange] = useState("1M");

  const pnlColor =
    pos.unrealized_pnl_pct > 0
      ? "text-profit"
      : pos.unrealized_pnl_pct < 0
        ? "text-loss"
        : "text-text-primary";

  const daysHeld = Math.floor(
    (Date.now() - new Date(pos.entry_date).getTime()) / (1000 * 60 * 60 * 24)
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold text-text-primary">{pos.ticker}</h2>
          <span className={`font-mono text-sm font-semibold ${pnlColor}`}>
            {pos.unrealized_pnl_pct >= 0 ? "+" : ""}
            {pos.unrealized_pnl_pct.toFixed(2)}%
          </span>
        </div>
        <div className="flex items-center gap-2">
          <SellButton pos={pos} />
          <button
            onClick={() => clearSelection(null)}
            className="text-xs text-text-muted hover:text-text-secondary transition-colors px-2 py-1 rounded border border-border hover:border-accent"
          >
            Back
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* P&L summary */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-bg-elevated/50 rounded-lg p-3 border border-border/50">
            <p className="text-[10px] text-text-muted uppercase tracking-wider mb-0.5">
              Unrealized P&L
            </p>
            <p className={`font-mono text-lg font-bold ${pnlColor}`}>
              {pos.unrealized_pnl >= 0 ? "+" : ""}${pos.unrealized_pnl.toFixed(2)}
            </p>
          </div>
          <div className="bg-bg-elevated/50 rounded-lg p-3 border border-border/50">
            <p className="text-[10px] text-text-muted uppercase tracking-wider mb-0.5">
              Market Value
            </p>
            <p className="font-mono text-lg font-bold text-text-primary">
              ${pos.market_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </p>
          </div>
        </div>

        {/* Time Range Selector */}
        <div className="flex gap-1 mb-3">
          {['1D', '5D', '1M', '3M', 'YTD', 'ALL'].map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                range === r
                  ? 'bg-cyber-cyan text-black font-semibold'
                  : 'text-text-muted border border-border hover:border-cyber-cyan'
              }`}
            >
              {r}
            </button>
          ))}
        </div>

        {/* Candlestick Chart */}
        <CandlestickChart ticker={pos.ticker} range={range} position={pos} />

        {/* Stop/Target progress */}
        <div className="mt-3">
          <ProgressVisualization pos={pos} />
        </div>

        {/* Details */}
        <div>
          <DetailRow label="Shares" value={`${pos.shares}`} />
          <DetailRow label="Avg Cost" value={`$${pos.avg_cost_basis.toFixed(2)}`} />
          <DetailRow label="Current Price" value={`$${pos.current_price.toFixed(2)}`} color="text-accent" />
          <DetailRow label="Stop Loss" value={`$${pos.stop_loss.toFixed(2)}`} color="text-loss" />
          <DetailRow label="Take Profit" value={`$${pos.take_profit.toFixed(2)}`} color="text-profit" />
          <DetailRow label="Entry Date" value={pos.entry_date.slice(0, 10)} />
          <DetailRow label="Days Held" value={`${daysHeld}`} />
        </div>
      </div>
    </div>
  );
}
