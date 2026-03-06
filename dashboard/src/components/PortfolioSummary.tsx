/** Horizontal summary strip at the top of the main column. */

import { useMemo, useEffect, useRef, useState, useCallback } from "react";
import { usePortfolioState } from "../hooks/usePortfolioState";
import { useRisk } from "../hooks/useRisk";
import { useCountUp } from "../hooks/useCountUp";
import type { Snapshot } from "../lib/types";
import { UpdateButton, ScanButton, AnalyzeExecute } from "./CommandBar";

// ── Fourier Ghost Stack ────────────────────────────────────────────────────

const HARMONIC_PALETTE = [
  "#7c3aed", // violet   (k=1, fundamental — slowest drift)
  "#2563eb", // indigo
  "#06b6d4", // cyan
  "#10b981", // emerald
  "#eab308", // yellow
  "#f97316", // orange
  "#ef4444", // red      (k=7, fastest drift)
];

const ω_BASE = 0.35; // rad/s per harmonic number

interface Harmonic {
  k: number;
  amp: number;
  phase: number;
  colorIdx: number;
  energyFrac: number; // fraction of total signal energy
}

/**
 * Discrete Fourier Transform — returns top maxH harmonics sorted by frequency.
 * Input signal should be normalized (e.g. zero-mean, unit-max-amplitude).
 */
function dft(signal: number[], maxH = 7): Harmonic[] {
  const N = signal.length;
  if (N < 4) return [];

  const all: Array<{ k: number; amp: number; phase: number }> = [];

  for (let k = 1; k <= Math.floor(N / 2); k++) {
    let re = 0, im = 0;
    for (let n = 0; n < N; n++) {
      const θ = (2 * Math.PI * k * n) / N;
      re += signal[n] * Math.cos(θ);
      im -= signal[n] * Math.sin(θ); // negated so phase = atan2(im, re) gives correct reconstruction
    }
    const amp = (2 / N) * Math.sqrt(re * re + im * im);
    all.push({ k, amp, phase: Math.atan2(im, re) });
  }

  const totalE = all.reduce((s, h) => s + h.amp * h.amp, 0) || 1;

  // Top N by amplitude
  const top = [...all].sort((a, b) => b.amp - a.amp).slice(0, maxH);
  // Re-sort by k so color assignment follows frequency order (low→violet, high→red)
  top.sort((a, b) => a.k - b.k);

  return top.map((h, i) => ({
    ...h,
    colorIdx: i % HARMONIC_PALETTE.length,
    energyFrac: (h.amp * h.amp) / totalE,
  }));
}

// ── EquityCurve ────────────────────────────────────────────────────────────

export function EquityCurve({ snapshots }: { snapshots: Snapshot[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const [dims, setDims] = useState({ width: 600, height: 200 });

  // Refs for the RAF draw loop — avoid stale closures, no re-render on change
  const dimsRef      = useRef(dims);
  const signalRef    = useRef<number[]>([]);
  const equitiesRef  = useRef<number[]>([]);
  const harmonicsRef = useRef<Harmonic[]>([]);
  const hoverRef     = useRef<number | null>(null); // hovered harmonic index
  const timeRef      = useRef(0);
  const lastTsRef    = useRef<number | null>(null);
  const rafRef       = useRef<number | null>(null);

  // ── Compute signal + harmonics ────────────────────────────────────────
  const computed = useMemo(() => {
    const recent = snapshots.slice(-30);
    if (recent.length < 4) return null;
    const equities = recent.map(s => s.total_equity ?? s.cash + s.positions_value);
    const mean = equities.reduce((a, b) => a + b, 0) / equities.length;
    const detrended = equities.map(v => v - mean);
    const maxAmp = Math.max(...detrended.map(Math.abs), 1);
    const signal = detrended.map(v => v / maxAmp);
    return { signal, equities, harmonics: dft(signal, 7) };
  }, [snapshots]);

  // Sync computed data to refs
  useEffect(() => { dimsRef.current = dims; }, [dims]);
  useEffect(() => {
    if (!computed) return;
    signalRef.current    = computed.signal;
    equitiesRef.current  = computed.equities;
    harmonicsRef.current = computed.harmonics;
  }, [computed]);

  // ── ResizeObserver ────────────────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      setDims({ width: Math.max(width, 100), height: Math.max(height, 60) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ── DPR canvas sizing ─────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width  = dims.width  * dpr;
    canvas.height = dims.height * dpr;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);
  }, [dims]);

  // ── RAF draw loop ─────────────────────────────────────────────────────
  useEffect(() => {
    function frame(ts: number) {
      if (lastTsRef.current !== null) {
        timeRef.current += (ts - lastTsRef.current) / 1000;
      }
      lastTsRef.current = ts;
      paint();
      rafRef.current = requestAnimationFrame(frame);
    }

    function paint() {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const { width: W, height: H } = dimsRef.current;
      const signal    = signalRef.current;
      const equities  = equitiesRef.current;
      const harmonics = harmonicsRef.current;
      const hoverH    = hoverRef.current;
      const t         = timeRef.current;

      ctx.clearRect(0, 0, W, H);
      if (signal.length < 2) return;

      const N     = signal.length;
      const PX    = 16, PY = 14;
      const CW    = W - PX * 2;
      const CH    = H - PY * 2;
      const cy    = PY + CH / 2;     // center Y (zero line)
      const halfH = CH * 0.43;       // half-height for amplitude scale
      const DRAW  = 128;             // interpolation resolution for smooth sinusoids

      const xAt  = (i: number)  => PX + (i / (DRAW - 1)) * CW;
      const yAt  = (v: number)  => cy - v * halfH;

      // ── Background ───────────────────────────────────────────────────
      ctx.fillStyle = "#010107";
      ctx.fillRect(0, 0, W, H);

      // ── Zero line ────────────────────────────────────────────────────
      ctx.save();
      ctx.strokeStyle = "rgba(255,255,255,0.05)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);
      ctx.beginPath(); ctx.moveTo(PX, cy); ctx.lineTo(W - PX, cy); ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();

      // ── Pass 1: harmonic glow (screen blend, blurred) ─────────────────
      harmonics.forEach((h, hi) => {
        const color  = HARMONIC_PALETTE[h.colorIdx];
        const baseA  = Math.max(0.18, Math.pow(h.energyFrac, 0.32));
        const isHov  = hoverH === hi;
        const dimmed = hoverH !== null && !isHov;
        const alpha  = dimmed ? 0.06 : (isHov ? 0.9 : baseA);
        const phOff  = h.k * ω_BASE * t;

        ctx.save();
        ctx.globalCompositeOperation = "screen";
        ctx.globalAlpha = alpha * 0.5;
        ctx.filter = `blur(${isHov ? 8 : 4}px)`;
        ctx.strokeStyle = color;
        ctx.lineWidth = isHov ? 3 : 1.8;
        ctx.lineJoin  = "round";
        ctx.beginPath();
        for (let i = 0; i < DRAW; i++) {
          const nFrac = (i / (DRAW - 1)) * (N - 1);
          const x = xAt(i);
          const y = yAt(h.amp * Math.cos(2 * Math.PI * h.k * nFrac / N + h.phase + phOff));
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.filter = "none";
        ctx.restore();
      });

      // ── Pass 2: harmonic crisp lines (screen blend) ───────────────────
      harmonics.forEach((h, hi) => {
        const color  = HARMONIC_PALETTE[h.colorIdx];
        const baseA  = Math.max(0.28, Math.pow(h.energyFrac, 0.32));
        const isHov  = hoverH === hi;
        const dimmed = hoverH !== null && !isHov;
        const alpha  = dimmed ? 0.04 : (isHov ? 1.0 : baseA);
        const phOff  = h.k * ω_BASE * t;

        ctx.save();
        ctx.globalCompositeOperation = "screen";
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = color;
        ctx.lineWidth = isHov ? 1.5 : 0.8;
        ctx.lineJoin  = "round";
        ctx.beginPath();
        for (let i = 0; i < DRAW; i++) {
          const nFrac = (i / (DRAW - 1)) * (N - 1);
          const x = xAt(i);
          const y = yAt(h.amp * Math.cos(2 * Math.PI * h.k * nFrac / N + h.phase + phOff));
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.restore();
      });

      // ── Actual equity curve — static "ground truth" ───────────────────
      const sumAlpha = hoverH !== null ? 0.4 : 0.88;

      // Glow
      ctx.save();
      ctx.globalCompositeOperation = "screen";
      ctx.globalAlpha = sumAlpha * 0.55;
      ctx.filter = "blur(5px)";
      ctx.strokeStyle = "#c4b5fd";
      ctx.lineWidth = 3;
      ctx.lineJoin  = "round";
      ctx.beginPath();
      signal.forEach((v, n) => {
        const x = PX + (n / (N - 1)) * CW;
        const y = yAt(v);
        n === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.filter = "none";
      ctx.restore();

      // Crisp line
      ctx.save();
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = sumAlpha;
      ctx.strokeStyle = "#ddd6fe";
      ctx.lineWidth = 1.5;
      ctx.lineJoin  = "round";
      ctx.beginPath();
      signal.forEach((v, n) => {
        const x = PX + (n / (N - 1)) * CW;
        const y = yAt(v);
        n === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.restore();

      // Endpoint pulse dot
      {
        const lastV = signal[signal.length - 1];
        const ex = PX + CW;
        const ey = yAt(lastV);

        ctx.save();
        ctx.globalCompositeOperation = "screen";
        ctx.globalAlpha = 0.7;
        ctx.filter = "blur(5px)";
        ctx.fillStyle = "#c4b5fd";
        ctx.beginPath(); ctx.arc(ex, ey, 6, 0, Math.PI * 2); ctx.fill();
        ctx.filter = "none";
        ctx.restore();

        ctx.save();
        ctx.fillStyle = "#e9d5ff";
        ctx.beginPath(); ctx.arc(ex, ey, 2, 0, Math.PI * 2); ctx.fill();
        ctx.restore();
      }

      // ── Hover: harmonic label ─────────────────────────────────────────
      if (hoverH !== null && hoverH >= 0 && hoverH < harmonics.length) {
        const h = harmonics[hoverH];
        const color = HARMONIC_PALETTE[h.colorIdx];
        const txt = `H${h.k}  ·  ${(h.energyFrac * 100).toFixed(0)}% signal energy`;

        // Glow behind text
        ctx.save();
        ctx.globalCompositeOperation = "screen";
        ctx.globalAlpha = 0.4;
        ctx.filter = "blur(3px)";
        ctx.font = "600 8px monospace";
        ctx.textBaseline = "top";
        ctx.textAlign    = "left";
        ctx.fillStyle = color;
        ctx.fillText(txt, PX + 4, PY + 4);
        ctx.filter = "none";
        ctx.restore();

        ctx.save();
        ctx.globalCompositeOperation = "source-over";
        ctx.font = "600 8px monospace";
        ctx.textBaseline = "top";
        ctx.textAlign    = "left";
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.92;
        ctx.fillText(txt, PX + 4, PY + 4);
        ctx.restore();
      }

      // ── Return % label (top-right) ────────────────────────────────────
      if (equities.length >= 2 && hoverH === null) {
        const retPct  = ((equities[equities.length - 1] - equities[0]) / equities[0]) * 100;
        const sign    = retPct >= 0 ? "+" : "";
        const retColor = retPct >= 0 ? "#34d399" : "#f87171";

        ctx.save();
        ctx.globalCompositeOperation = "source-over";
        ctx.font = "700 9px monospace";
        ctx.textAlign    = "right";
        ctx.textBaseline = "top";
        ctx.fillStyle    = retColor;
        ctx.globalAlpha  = 0.7;
        ctx.fillText(`${sign}${retPct.toFixed(1)}%`, W - PX - 4, PY + 4);
        ctx.restore();
      }

      // ── Scanlines ─────────────────────────────────────────────────────
      ctx.save();
      ctx.globalAlpha = 0.03;
      ctx.fillStyle   = "#000";
      for (let sy = 0; sy < H; sy += 3) ctx.fillRect(0, sy, W, 1);
      ctx.restore();

      // ── Vignette ──────────────────────────────────────────────────────
      ctx.save();
      const vg = ctx.createRadialGradient(W / 2, H / 2, H * 0.08, W / 2, H / 2, W * 0.62);
      vg.addColorStop(0, "transparent");
      vg.addColorStop(1, "rgba(1,1,10,0.58)");
      ctx.fillStyle = vg;
      ctx.fillRect(0, 0, W, H);
      ctx.restore();
    }

    rafRef.current = requestAnimationFrame(frame);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      lastTsRef.current = null;
    };
  }, []); // runs once — RAF reads from refs

  // ── Mouse: find closest harmonic at cursor ────────────────────────────
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const { width: W, height: H } = dimsRef.current;
    const harmonics = harmonicsRef.current;
    const signal    = signalRef.current;
    const t         = timeRef.current;
    const N         = signal.length;
    if (N < 2) return;

    const PX = 16, PY = 14;
    const CW = W - PX * 2;
    const CH = H - PY * 2;
    const cy    = PY + CH / 2;
    const halfH = CH * 0.43;

    // Interpolated data index at mouse x
    const n0 = ((mx - PX) / CW) * (N - 1);

    let closest: number | null = null;
    let closestDist = 32; // px threshold

    harmonics.forEach((h, hi) => {
      const phOff = h.k * ω_BASE * t;
      const val = h.amp * Math.cos(2 * Math.PI * h.k * n0 / N + h.phase + phOff);
      const y   = cy - val * halfH;
      const d   = Math.abs(my - y);
      if (d < closestDist) { closestDist = d; closest = hi; }
    });

    hoverRef.current = closest;
  }, []);

  const handleMouseLeave = useCallback(() => { hoverRef.current = null; }, []);

  if (!computed || snapshots.length < 2) return null;

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
  const realizedPnl = state?.realized_pnl ?? 0;
  const realizedColor = realizedPnl >= 0 ? "text-profit" : "text-loss";
  const cagrPct = state?.cagr_pct ?? 0;
  const cagrColor = cagrPct >= 0 ? "text-profit" : "text-loss";

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
            {/* Realized P&L */}
            <div>
              <div className={`font-mono text-sm tabular-nums font-semibold ${realizedColor}`}>
                {realizedPnl >= 0 ? "+" : ""}${realizedPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div style={labelStyle}>Realized</div>
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
            {/* CAGR */}
            {cagrPct !== 0 && (
              <div>
                <div className={`font-mono text-sm tabular-nums font-semibold ${cagrColor}`}>
                  {cagrPct >= 0 ? "+" : ""}{cagrPct.toFixed(1)}%
                </div>
                <div style={labelStyle}>CAGR</div>
              </div>
            )}
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
