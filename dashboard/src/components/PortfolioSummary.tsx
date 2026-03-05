/** Horizontal summary strip at the top of the main column. */

import { useMemo, useEffect, useRef, useState, useCallback } from "react";
import { usePortfolioState } from "../hooks/usePortfolioState";
import { useRisk } from "../hooks/useRisk";
import { useCountUp } from "../hooks/useCountUp";
import type { Snapshot } from "../lib/types";
import { UpdateButton, ScanButton, AnalyzeExecute } from "./CommandBar";

// ── helpers ──────────────────────────────────────────────────────────────────

function rrect(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number, r: number,
) {
  if (typeof ctx.roundRect === "function") {
    ctx.roundRect(x, y, w, h, r);
  } else {
    const rx = Math.min(r, w / 2, h / 2);
    ctx.moveTo(x + rx, y);
    ctx.lineTo(x + w - rx, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + rx);
    ctx.lineTo(x + w, y + h - rx);
    ctx.quadraticCurveTo(x + w, y + h, x + w - rx, y + h);
    ctx.lineTo(x + rx, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - rx);
    ctx.lineTo(x, y + rx);
    ctx.quadraticCurveTo(x, y, x + rx, y);
    ctx.closePath();
  }
}

// ── EquityWaveform ────────────────────────────────────────────────────────────

export function EquityCurve({ snapshots }: { snapshots: Snapshot[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const [dims, setDims] = useState({ width: 600, height: 200 });
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const animRef      = useRef<number | null>(null);
  const startRef     = useRef<number | null>(null);
  const [animProg, setAnimProg] = useState(0);

  // Last 30 snapshots; compute day_pnl from equity delta if missing
  const bars = useMemo(() => {
    const recent = snapshots.slice(-30);
    return recent.map((s, i) => {
      const equity = s.total_equity ?? s.cash + s.positions_value;
      let pnl = s.day_pnl ?? 0;
      if (pnl === 0 && i > 0) {
        const prev = recent[i - 1];
        pnl = equity - (prev.total_equity ?? prev.cash + prev.positions_value);
      }
      return { date: s.date, equity, pnl };
    });
  }, [snapshots]);

  const maxAmp = useMemo(
    () => Math.max(...bars.map((b) => Math.abs(b.pnl)), 1),
    [bars],
  );

  // Mount animation
  useEffect(() => {
    setAnimProg(0);
    startRef.current = null;
    if (animRef.current) cancelAnimationFrame(animRef.current);

    function tick(now: number) {
      if (!startRef.current) startRef.current = now;
      const t = Math.min((now - startRef.current) / 900, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setAnimProg(eased);
      if (t < 1) animRef.current = requestAnimationFrame(tick);
    }
    animRef.current = requestAnimationFrame(tick);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [bars.length]);

  // ResizeObserver
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDims({ width, height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // DPR scaling
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width  = dims.width  * dpr;
    canvas.height = dims.height * dpr;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);
  }, [dims]);

  // Draw
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || bars.length === 0) return;
    const ctx = canvas.getContext("2d")!;
    const { width: W, height: H } = dims;

    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = "#010107";
    ctx.fillRect(0, 0, W, H);

    const PAD_X   = 20;
    const PAD_Y   = 14;
    const chartW  = W - PAD_X * 2;
    const chartH  = H - PAD_Y * 2;
    const baseline = PAD_Y + chartH / 2;
    const maxBarH  = chartH / 2 - 6;
    const n        = bars.length;
    const barSlot  = chartW / n;
    const barW     = Math.max(3, barSlot * 0.60);
    const gap      = (barSlot - barW) / 2;

    // Baseline — subtle glow then hard line
    ctx.save();
    ctx.globalAlpha = 0.25;
    ctx.filter = "blur(3px)";
    ctx.strokeStyle = "rgba(255,255,255,0.4)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(PAD_X, baseline);
    ctx.lineTo(W - PAD_X, baseline);
    ctx.stroke();
    ctx.filter = "none";
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = "rgba(255,255,255,0.12)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(PAD_X, baseline);
    ctx.lineTo(W - PAD_X, baseline);
    ctx.stroke();
    ctx.restore();

    // Bars
    bars.forEach((bar, i) => {
      const isPos  = bar.pnl >= 0;
      const color  = isPos ? "#34d399" : "#f87171";
      const colorDim = isPos ? "rgba(52,211,153,0.25)" : "rgba(248,113,113,0.25)";

      // Power scale: compresses outliers so small moves still register
      const rawH = Math.pow(Math.abs(bar.pnl) / maxAmp, 0.55) * maxBarH;
      const barH = rawH * animProg;
      if (barH < 0.5) return;

      const x        = PAD_X + i * barSlot + gap;
      const isHovered = hoverIdx === i;
      const alpha     = hoverIdx !== null && !isHovered ? 0.45 : 1.0;

      // ── Glow pass (blurred) ──────────────────────────────────────────────
      ctx.save();
      ctx.globalAlpha = alpha * 0.35;
      ctx.filter = "blur(5px)";
      ctx.fillStyle = color;
      // top spike
      ctx.beginPath();
      rrect(ctx, x - 2, baseline - barH - 2, barW + 4, barH + 2, 3);
      ctx.fill();
      // bottom mirror
      ctx.beginPath();
      rrect(ctx, x - 2, baseline, barW + 4, barH + 2, 3);
      ctx.fill();
      ctx.filter = "none";
      ctx.restore();

      // ── Crisp bars with gradient ─────────────────────────────────────────
      ctx.save();
      ctx.globalAlpha = alpha;

      // Top spike: bright tip → dim base
      const gradUp = ctx.createLinearGradient(0, baseline - barH, 0, baseline);
      gradUp.addColorStop(0, color);
      gradUp.addColorStop(1, colorDim);
      ctx.fillStyle = gradUp;
      ctx.beginPath();
      rrect(ctx, x, baseline - barH, barW, barH, 2);
      ctx.fill();

      // Bottom mirror: dim base → bright tip
      const gradDown = ctx.createLinearGradient(0, baseline, 0, baseline + barH);
      gradDown.addColorStop(0, colorDim);
      gradDown.addColorStop(1, color);
      ctx.fillStyle = gradDown;
      ctx.beginPath();
      rrect(ctx, x, baseline, barW, barH, 2);
      ctx.fill();

      ctx.restore();

      // ── Hover scan line ──────────────────────────────────────────────────
      if (isHovered) {
        ctx.save();
        ctx.strokeStyle = "rgba(255,255,255,0.18)";
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(x + barW / 2, PAD_Y);
        ctx.lineTo(x + barW / 2, H - PAD_Y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();
      }
    });

    // ── Tooltip ────────────────────────────────────────────────────────────
    if (hoverIdx !== null && hoverIdx >= 0 && hoverIdx < bars.length) {
      const bar     = bars[hoverIdx];
      const barSlotX = PAD_X + hoverIdx * barSlot + gap;
      const cx      = barSlotX + barW / 2;

      const dateStr  = String(bar.date).slice(0, 10);
      const equityStr = "$" + bar.equity.toLocaleString(undefined, { maximumFractionDigits: 0 });
      const pnlStr   = (bar.pnl >= 0 ? "+" : "") + "$" + Math.abs(bar.pnl).toLocaleString(undefined, { maximumFractionDigits: 0 });
      const pnlColor = bar.pnl >= 0 ? "#34d399" : "#f87171";

      const CW = 148, CH = 54;
      let tx = cx + 10;
      if (tx + CW > W - PAD_X) tx = cx - CW - 10;
      tx = Math.max(PAD_X, tx);
      const ty = PAD_Y + 6;

      ctx.save();
      ctx.fillStyle   = "rgba(4,4,12,0.94)";
      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      ctx.lineWidth   = 1;
      ctx.beginPath();
      rrect(ctx, tx, ty, CW, CH, 4);
      ctx.fill();
      ctx.stroke();

      ctx.font         = "600 8px/1 monospace";
      ctx.textBaseline = "middle";

      ctx.fillStyle = "rgba(255,255,255,0.35)";
      ctx.textAlign = "left";
      ctx.fillText(dateStr, tx + 10, ty + 14);

      ctx.fillStyle = "rgba(255,255,255,0.88)";
      ctx.fillText(equityStr, tx + 10, ty + 32);

      ctx.fillStyle = pnlColor;
      ctx.textAlign = "right";
      ctx.fillText(pnlStr, tx + CW - 10, ty + 32);

      ctx.restore();
    }

    // ── Return label (top-left) ────────────────────────────────────────────
    if (bars.length >= 2 && animProg >= 1) {
      const first  = bars[0].equity;
      const last   = bars[bars.length - 1].equity;
      const retPct = ((last - first) / first) * 100;
      const sign   = retPct >= 0 ? "+" : "";
      const retColor = retPct >= 0 ? "#34d399" : "#f87171";

      ctx.save();
      ctx.font         = "700 9px/1 monospace";
      ctx.textAlign    = "right";
      ctx.textBaseline = "top";
      ctx.fillStyle    = retColor;
      ctx.globalAlpha  = 0.75;
      ctx.fillText(`${sign}${retPct.toFixed(1)}%`, W - PAD_X - 4, PAD_Y + 4);
      ctx.restore();
    }
  }, [bars, dims, animProg, hoverIdx, maxAmp]);

  // Mouse
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x   = e.clientX - rect.left;
      const PAD_X  = 20;
      const chartW = dims.width - PAD_X * 2;
      const slot   = chartW / bars.length;
      const idx    = Math.floor((x - PAD_X) / slot);
      setHoverIdx(idx >= 0 && idx < bars.length ? idx : null);
    },
    [bars.length, dims.width],
  );

  const handleMouseLeave = useCallback(() => setHoverIdx(null), []);

  if (snapshots.length < 2) return null;

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", position: "relative" }}>
      <canvas
        ref={canvasRef}
        style={{ display: "block", width: "100%", height: "100%" }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />
    </div>
  );
}

export default function PortfolioSummary() {
  const { data: state } = usePortfolioState();
  const { data: risk } = useRisk();

  const overallPnl = state?.positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0) ?? 0;
  const overallColor = overallPnl >= 0 ? "text-profit" : "text-loss";
  const allTimePnl = state?.all_time_pnl ?? 0;
  const allTimeColor = allTimePnl >= 0 ? "text-profit" : "text-loss";
  const dayColor = (state?.day_pnl ?? 0) >= 0 ? "text-profit" : "text-loss";
  const returnColor = (state?.total_return_pct ?? 0) >= 0 ? "text-profit" : "text-loss";

  const animatedEquity = useCountUp(state?.total_equity ?? 0, 1200, 2);

  // Shared label style for metric labels
  const labelStyle: React.CSSProperties = {
    fontSize: "9.5px",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "var(--text-0)",
    fontFamily: "var(--font-sans)",
    marginTop: "2px",
  };

  return (
    <div
      className="flex-shrink-0 border-b"
      style={{ borderColor: "var(--border-0)", background: "var(--surface-0)" }}
    >
      <div className="flex items-stretch" style={{ minHeight: "84px" }}>

        {/* Left: metrics */}
        <div className="flex-1 flex items-center gap-6 px-4 py-3 min-w-0">

          {/* Hero equity */}
          <div className="shrink-0 anim d1">
            <div className="font-mono tabular-nums leading-none" style={{ fontSize: "22px", fontWeight: 300, color: "var(--text-4)" }}>
              ${animatedEquity}
            </div>
            <div style={labelStyle}>Portfolio Equity</div>
          </div>

          {/* Divider */}
          <div style={{ width: "1px", height: "28px", background: "var(--border-1)", flexShrink: 0 }} />

          {/* P&L metrics row */}
          <div className="flex items-center gap-5 flex-wrap anim d2">
            {/* All-Time P&L */}
            <div>
              <div className={`font-mono text-sm tabular-nums font-semibold ${allTimeColor}`}>
                {allTimePnl >= 0 ? "+" : ""}${allTimePnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div style={labelStyle}>All-Time P&L</div>
            </div>
            {/* Open P&L */}
            <div>
              <div className={`font-mono text-sm tabular-nums font-semibold ${overallColor}`}>
                {overallPnl >= 0 ? "+" : ""}${overallPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div style={labelStyle}>Open P&L</div>
            </div>
            {/* Today */}
            <div>
              <div className={`font-mono text-sm tabular-nums font-semibold ${dayColor}`}>
                {(state?.day_pnl ?? 0) >= 0 ? "+" : ""}${(state?.day_pnl ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div style={labelStyle}>Today</div>
            </div>
            {/* Return */}
            <div>
              <div className={`font-mono text-sm tabular-nums font-semibold ${returnColor}`}>
                {(state?.total_return_pct ?? 0) >= 0 ? "+" : ""}{(state?.total_return_pct ?? 0).toFixed(1)}%
              </div>
              <div style={labelStyle}>Return</div>
            </div>
            {/* Cash */}
            <div>
              <div className="font-mono text-sm tabular-nums text-text-primary">
                ${(state?.cash ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div style={labelStyle}>Cash</div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 ml-auto shrink-0">
            <UpdateButton />
            <ScanButton />
            <div style={{ width: "1px", height: "18px", background: "var(--border-1)", flexShrink: 0 }} />
            <AnalyzeExecute />
          </div>

          {/* Divider */}
          <div style={{ width: "1px", height: "28px", background: "var(--border-1)", flexShrink: 0 }} />

          {/* Status chips */}
          <div className="flex items-center gap-2 shrink-0 anim d3" style={{ fontSize: "10px" }}>
            <span className={state?.regime === "BULL" ? "text-profit" : state?.regime === "BEAR" ? "text-loss" : "text-warning"} style={{ fontWeight: 600 }}>
              {state?.regime ?? "—"}
            </span>
            <span style={{ color: "var(--border-2)" }}>·</span>
            <span style={{ color: "var(--text-1)" }}>
              Risk{" "}
              <span className={`font-mono font-semibold ${(risk?.overall_score ?? 0) >= 70 ? "text-profit" : (risk?.overall_score ?? 0) >= 40 ? "text-warning" : "text-loss"}`}>
                {risk?.overall_score != null ? Math.round(risk.overall_score) : "—"}
              </span>
            </span>
            <span style={{ color: "var(--border-2)" }}>·</span>
            <span style={{ color: "var(--text-1)" }}>
              <span className="font-mono text-text-primary">{state?.positions.length ?? 0}</span> pos
            </span>
            {(state?.stale_alerts.length ?? 0) > 0 && (
              <span className="text-warning">&#9888; {state!.stale_alerts.length}</span>
            )}
          </div>

        </div>

      </div>
    </div>
  );
}
