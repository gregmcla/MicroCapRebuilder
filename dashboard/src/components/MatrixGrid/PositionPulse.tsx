/**
 * Position Pulse — a 36px kinetic strip between the topbar and the matrix.
 *
 * Three zones, left to right:
 *   Zone 1 (180px): Portfolio health spine — weighted P&L, vol σ, beat ratio
 *   Zone 2 (flex):  Position glyph lane — one cell per position, sorted by perf,
 *                   each showing ticker + day% + real sparkline
 *   Zone 3 (130px): Session clock (ET) + ΔDAY total dollar change
 */

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import type { MatrixPosition } from "./types";
import { pc, MATRIX_FONT } from "./constants";

// ── Helpers ───────────────────────────────────────────────────────────────────

function getETTime(): Date {
  return new Date(new Date().toLocaleString("en-US", { timeZone: "America/New_York" }));
}

function marketState(): { label: string; color: string } {
  const et  = getETTime();
  const day  = et.getDay();
  const mins = et.getHours() * 60 + et.getMinutes();
  if (day === 0 || day === 6)                       return { label: "closed",    color: "#444" };
  if (mins >= 4 * 60 && mins < 9 * 60 + 30)        return { label: "pre-mkt",   color: "#fbbf24" };
  if (mins >= 9 * 60 + 30 && mins < 16 * 60)       return { label: "open",      color: "#22C55E" };
  if (mins >= 16 * 60 && mins < 20 * 60)            return { label: "after-hrs", color: "#fbbf24" };
  return { label: "closed", color: "#444" };
}

// ── Mini sparkline (SVG, 1px line, no fill) ───────────────────────────────────

function MiniSparkline({
  data,
  color,
  w = 52,
  h = 7,
}: {
  data: number[];
  color: string;
  w?: number;
  h?: number;
}) {
  const pts = data.slice(-30);
  if (pts.length < 2) return <div style={{ width: w, height: h }} />;
  const min   = Math.min(...pts);
  const max   = Math.max(...pts);
  const range = max - min || 1;
  const points = pts
    .map((v, i) => {
      const x = (i / (pts.length - 1)) * w;
      const y = (h - 1) - ((v - min) / range) * (h - 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      width={w}
      height={h}
      style={{ display: "block", overflow: "visible", flexShrink: 0 }}
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.85"
      />
    </svg>
  );
}

// ── Tooltip rendered at fixed screen position ─────────────────────────────────

function GlyphTooltip({
  pos,
  anchorRect,
}: {
  pos: MatrixPosition;
  anchorRect: DOMRect;
}) {
  const col   = pos.portfolioColor;
  const days  = pos.entryDate
    ? Math.floor((Date.now() - new Date(pos.entryDate).getTime()) / 864e5)
    : null;
  const slDist =
    pos.stopLoss != null && pos.currentPrice != null && pos.currentPrice > 0
      ? ((pos.currentPrice - pos.stopLoss) / pos.currentPrice) * 100
      : null;
  const tpDist =
    pos.takeProfit != null && pos.currentPrice != null && pos.currentPrice > 0
      ? ((pos.takeProfit - pos.currentPrice) / pos.currentPrice) * 100
      : null;

  const TW = 200;
  let left = anchorRect.left + anchorRect.width / 2 - TW / 2;
  left = Math.max(8, Math.min(left, window.innerWidth - TW - 8));
  const bottom = window.innerHeight - anchorRect.top + 6;

  const sparkH = 40;
  const sparkPts = pos.sparkline.slice(-60);
  const sMin   = Math.min(...sparkPts);
  const sMax   = Math.max(...sparkPts);
  const sRange = sMax - sMin || 1;
  const sparkPoints = sparkPts
    .map((v, i) => {
      const x = (i / (sparkPts.length - 1)) * (TW - 24);
      const y = (sparkH - 2) - ((v - sMin) / sRange) * (sparkH - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div
      style={{
        position:   "fixed",
        bottom,
        left,
        width:      TW,
        background: "rgba(2,6,23,0.97)",
        border:     `1px solid ${col}55`,
        padding:    "10px 12px",
        zIndex:     9999,
        fontFamily: MATRIX_FONT,
        pointerEvents: "none",
        boxShadow:  `0 -8px 32px rgba(0,0,0,0.6), 0 0 0 1px ${col}22`,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: "#F8FAFC", letterSpacing: "0.05em" }}>
          {pos.ticker}
        </span>
        <span style={{ fontSize: 9, color: col, letterSpacing: "0.06em" }}>
          {pos.portfolioName}
        </span>
      </div>

      {/* Sparkline */}
      {sparkPts.length >= 2 && (
        <svg
          width={TW - 24}
          height={sparkH}
          style={{ display: "block", marginBottom: 8, overflow: "visible" }}
        >
          <polyline
            points={sparkPoints}
            fill="none"
            stroke={pos.perf >= 0 ? "#22C55E" : "#EF4444"}
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
            opacity="0.9"
          />
        </svg>
      )}

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 8px" }}>
        {[
          pos.currentPrice != null
            ? { l: "PRICE", v: `$${pos.currentPrice.toFixed(2)}`, c: "#ccc" }
            : null,
          { l: "TODAY", v: `${pos.day >= 0 ? "+" : ""}${pos.day.toFixed(2)}%`, c: pc(pos.day) },
          { l: "ALL-TIME", v: `${pos.perf >= 0 ? "+" : ""}${pos.perf.toFixed(1)}%`, c: pc(pos.perf) },
          days !== null
            ? { l: "HELD", v: `${days}d`, c: days >= 35 ? "#F59E0B" : "#64748B" }
            : null,
          slDist !== null
            ? { l: "SL DIST", v: `-${slDist.toFixed(1)}%`, c: slDist < 8 ? "#EF4444" : slDist < 15 ? "#F59E0B" : "#64748B" }
            : null,
          tpDist !== null
            ? { l: "TP DIST", v: `+${tpDist.toFixed(1)}%`, c: "#22C55E" }
            : null,
        ]
          .filter(Boolean)
          .map((s) => (
            <div key={s!.l}>
              <div style={{ fontSize: 7, color: "#475569", letterSpacing: "0.1em", marginBottom: 1 }}>{s!.l}</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: s!.c }}>{s!.v}</div>
            </div>
          ))}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function PositionPulse({
  positions,
}: {
  positions: MatrixPosition[];
}) {
  const [clock,  setClock]  = useState("");
  const [mkt,    setMkt]    = useState(marketState);
  const [hovKey, setHovKey] = useState<string | null>(null);
  const [tipRect,setTipRect]= useState<DOMRect | null>(null);
  const cellRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // Clock — 1s interval, ET timezone
  useEffect(() => {
    const tick = () => {
      setClock(getETTime().toLocaleTimeString("en-US", { hour12: false }));
      setMkt(marketState());
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  // Zone 1: weighted P&L, vol sigma, beat ratio
  const totalV    = positions.reduce((s, p) => s + Math.max(p.value, 0), 0);
  const wPnl      = totalV > 0
    ? positions.reduce((s, p) => s + p.perf * (p.value / totalV), 0)
    : 0;
  const betas     = positions.filter(p => p.beta != null).map(p => p.beta!);
  const avgBeta   = betas.length > 0 ? betas.reduce((a, b) => a + b, 0) / betas.length : null;
  const beats     = positions.filter(p => p.perf > 0).length;

  // ΔDAY total dollar change
  const deltaDay  = positions.reduce((s, p) => {
    if (p.dayChangeDollar != null) return s + p.dayChangeDollar;
    return s + (p.value * p.day / 100);
  }, 0);

  // Glyph lane: sorted by perf desc
  const glyphs    = useMemo(() => [...positions].sort((a, b) => b.perf - a.perf), [positions]);
  const cellW     = glyphs.length > 15 ? 40 : 52;
  const hovPos    = hovKey ? glyphs.find(p => `${p.ticker}:${p.portfolioId}` === hovKey) ?? null : null;

  const handleEnter = useCallback((key: string, el: HTMLDivElement) => {
    setHovKey(key);
    setTipRect(el.getBoundingClientRect());
  }, []);

  const handleLeave = useCallback(() => {
    setHovKey(null);
    setTipRect(null);
  }, []);

  // Beta color
  const betaColor = avgBeta == null ? "#475569"
    : avgBeta > 2.0 ? "#EF4444"
    : avgBeta > 1.5 ? "#F59E0B"
    : "#22C55E";

  const beatColor = beats / Math.max(positions.length, 1) > 0.6 ? "#22C55E"
    : beats / Math.max(positions.length, 1) > 0.4 ? "#F59E0B"
    : "#EF4444";

  return (
    <>
      <div
        style={{
          height:       36,
          flexShrink:   0,
          background:   "rgba(2,6,23,0.8)",
          borderBottom: "1px solid rgba(34,197,94,0.04)",
          display:      "flex",
          alignItems:   "stretch",
          fontFamily:   MATRIX_FONT,
          overflow:     "hidden",
          userSelect:   "none",
        }}
      >
        {/* ── Zone 1: Portfolio Health Spine ─────────────────────────────── */}
        <div
          style={{
            width:        180,
            flexShrink:   0,
            borderRight:  "1px solid rgba(34,197,94,0.04)",
            display:      "flex",
            alignItems:   "center",
            gap:          0,
            paddingLeft:  16,
            paddingRight: 8,
          }}
        >
          {/* P&L */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 7, color: "#475569", letterSpacing: "0.1em", marginBottom: 1 }}>P&L</div>
            <div style={{ fontSize: 11, fontWeight: 700, color: pc(wPnl), letterSpacing: "0.02em" }}>
              {wPnl >= 0 ? "▲" : "▼"} {wPnl >= 0 ? "+" : ""}{wPnl.toFixed(1)}%
            </div>
          </div>

          <div style={{ width: 1, height: 18, background: "rgba(255,255,255,0.07)", flexShrink: 0, margin: "0 8px" }} />

          {/* VOL σ */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 7, color: "#475569", letterSpacing: "0.1em", marginBottom: 1 }}>VOL</div>
            <div style={{ fontSize: 11, fontWeight: 600, color: betaColor }}>
              {avgBeta != null ? `${avgBeta.toFixed(1)}β` : "—"}
            </div>
          </div>

          <div style={{ width: 1, height: 18, background: "rgba(255,255,255,0.07)", flexShrink: 0, margin: "0 8px" }} />

          {/* BEAT */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 7, color: "#475569", letterSpacing: "0.1em", marginBottom: 1 }}>BEAT</div>
            <div style={{ fontSize: 11, fontWeight: 600 }}>
              <span style={{ color: beatColor }}>{beats}</span>
              <span style={{ color: "#475569" }}>/{positions.length}</span>
            </div>
          </div>
        </div>

        {/* ── Zone 2: Position Glyph Lane ────────────────────────────────── */}
        <div
          style={{
            flex:       1,
            minWidth:   0,
            display:    "flex",
            alignItems: "stretch",
            overflow:   "hidden",
            gap:        2,
            padding:    "0 8px",
          }}
        >
          {glyphs.map((pos) => {
            const key      = `${pos.ticker}:${pos.portfolioId}`;
            const isHov    = hovKey === key;
            const dayColor = pos.perf >= 0 ? "#22C55E" : "#EF4444";
            const label    = pos.ticker.length > 4
              ? pos.ticker.slice(0, 4)
              : pos.ticker;

            return (
              <div
                key={key}
                ref={el => {
                  if (el) cellRefs.current.set(key, el);
                  else cellRefs.current.delete(key);
                }}
                onMouseEnter={() => {
                  const el = cellRefs.current.get(key);
                  if (el) handleEnter(key, el);
                }}
                onMouseLeave={handleLeave}
                style={{
                  width:        cellW,
                  flexShrink:   0,
                  display:      "flex",
                  flexDirection:"column",
                  justifyContent:"center",
                  gap:          1,
                  padding:      "0 4px",
                  cursor:       "default",
                  borderLeft:   `2px solid ${pos.portfolioColor}${isHov ? "cc" : "33"}`,
                  background:   isHov ? "rgba(255,255,255,0.03)" : "transparent",
                  transition:   "background 0.1s, border-color 0.1s",
                }}
              >
                {/* Ticker + day% */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{
                    fontSize:   8,
                    fontWeight: 700,
                    color:      isHov ? "#F8FAFC" : "#94A3B8",
                    letterSpacing: "0.04em",
                    transition: "color 0.1s",
                    overflow:   "hidden",
                    whiteSpace: "nowrap",
                  }}>
                    {label}
                  </span>
                  <span style={{ fontSize: 7, color: dayColor, flexShrink: 0, marginLeft: 1 }}>
                    {pos.perf >= 0 ? "+" : ""}{pos.perf.toFixed(1)}
                  </span>
                </div>

                {/* Sparkline */}
                <MiniSparkline
                  data={pos.sparkline}
                  color={pos.perf >= 0 ? "#22C55E" : "#EF4444"}
                  w={cellW - 8}
                  h={7}
                />
              </div>
            );
          })}
        </div>

        {/* ── Zone 3: Session Clock + ΔDAY ───────────────────────────────── */}
        <div
          style={{
            width:       130,
            flexShrink:  0,
            borderLeft:  "1px solid rgba(34,197,94,0.04)",
            display:     "flex",
            flexDirection:"column",
            justifyContent:"center",
            alignItems:  "flex-end",
            paddingRight: 16,
            gap:         2,
          }}
        >
          {/* Clock + market state */}
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontSize: 10, color: "#475569", letterSpacing: "0.06em", fontVariantNumeric: "tabular-nums" }}>
              {clock}
            </span>
            <span style={{ fontSize: 7, color: mkt.color, letterSpacing: "0.08em" }}>
              {mkt.label}
            </span>
          </div>

          {/* ΔDAY */}
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            <span style={{ fontSize: 7, color: "#475569", letterSpacing: "0.1em" }}>ΔDAY</span>
            <span style={{
              fontSize:   10,
              fontWeight: 700,
              color:      deltaDay >= 0 ? "#22C55E" : "#EF4444",
              letterSpacing: "0.02em",
            }}>
              {deltaDay >= 0 ? "▲" : "▼"} {deltaDay >= 0 ? "+" : ""}${Math.abs(deltaDay).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </span>
          </div>
        </div>
      </div>

      {/* Tooltip — rendered at fixed screen position, escapes overflow:hidden */}
      {hovPos && tipRect && (
        <GlyphTooltip pos={hovPos} anchorRect={tipRect} />
      )}
    </>
  );
}
