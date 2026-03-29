/**
 * Portfolio Waveform Reader — each portfolio is a horizontal lane.
 * Positions within each lane are rendered as vertical bars sorted by pnl_pct
 * (worst → best, left to right), creating a "waveform" silhouette per portfolio.
 *
 * Bar height = |pnl_pct|, color = direction (green up / red down).
 * A thin purple tick mark on each bar encodes day_change_pct independently.
 * The gestalt of each lane's shape is readable before any label is read.
 *
 * Expand-on-click: clicking a portfolio's gutter expands it to fill the canvas;
 * all other portfolios collapse to 40px header rows.
 */

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import type { CrossPortfolioMover, PortfolioSummary } from "../lib/types";

// ── Prop types ─────────────────────────────────────────────────────────────────
export interface ConstellationMapProps {
  positions: CrossPortfolioMover[];
  portfolios: PortfolioSummary[];
  onPositionClick?: (ticker: string, portfolioId: string) => void;
}

// ── Constants ──────────────────────────────────────────────────────────────────
const GUTTER_W        = 164;   // left label column width
const LANE_PAD_T      = 10;    // padding above baseline within lane
const LANE_PAD_B      = 10;    // padding below baseline
const LANE_GAP        = 1;     // px between lanes (the separator line)
const BAR_GAP         = 2;     // gap between bars
const MIN_BAR_H       = 6;     // minimum bar height (so every position is visible)
const RIGHT_PAD       = 16;    // right margin
const COLLAPSED_H     = 40;    // height of a collapsed lane
const MIN_EXPANDED_H  = 300;   // minimum height for the expanded lane
const LABEL_FONT      = "500 10px 'JetBrains Mono', monospace";
const LABEL_FONT_S    = "400 9px 'JetBrains Mono', monospace";

// Theme colors
const C_BG         = "#08090d";
const C_GREEN      = "#34d399";
const C_RED        = "#f87171";
const C_ACCENT     = "#7c5cfc";
const C_BASELINE   = "rgba(255,255,255,0.08)";
const C_SEPARATOR  = "rgba(255,255,255,0.05)";
const C_TEXT       = "rgba(255,255,255,0.70)";
const C_TEXT_DIM   = "rgba(255,255,255,0.35)";
const C_HOVER_FILL = "rgba(255,255,255,0.06)";

// ── Internal types ─────────────────────────────────────────────────────────────
interface Bar {
  x: number;          // canvas x of bar left edge (within lane's bar region)
  barW: number;       // computed bar width for this lane
  pnlPct: number;
  dayPct: number;
  marketValue: number;
  pnl: number;
  ticker: string;
  portfolioId: string;
  portfolioName: string;
  nodeKey: string;
}

interface Lane {
  portfolioId: string;
  portfolioName: string;
  totalReturn: number;
  equity: number;
  laneY: number;       // top of this lane in canvas coords
  laneH: number;       // total height of lane
  baselineY: number;   // absolute canvas Y of baseline
  bars: Bar[];
  maxAbsPnl: number;   // for scaling
  clipped: number;     // how many bars didn't fit
  isCollapsed: boolean;
  isExpanded: boolean;
  barW: number;        // computed bar width for this lane
}

interface HoveredBar {
  bar: Bar;
  canvasX: number;  // center of bar in canvas coords
  canvasY: number;  // mouse Y for tooltip placement
  laneBaselineY: number;
}

// ── Layout builder ─────────────────────────────────────────────────────────────
function buildLanes(
  positions: CrossPortfolioMover[],
  portfolios: PortfolioSummary[],
  canvasW: number,
  canvasH: number,
  selectedPortfolioId: string | null,
): Lane[] {
  if (positions.length === 0 || canvasW <= 0 || canvasH <= 0) return [];

  const portMap = new Map<string, PortfolioSummary>(portfolios.map(p => [p.id, p]));

  // Group by portfolio
  const byPort = new Map<string, CrossPortfolioMover[]>();
  for (const pos of positions) {
    const arr = byPort.get(pos.portfolio_id) ?? [];
    arr.push(pos);
    byPort.set(pos.portfolio_id, arr);
  }

  // Sort portfolios by equity descending
  const portIds = [...byPort.keys()].sort((a, b) => {
    const ea = portMap.get(a)?.equity ?? 0;
    const eb = portMap.get(b)?.equity ?? 0;
    return eb - ea;
  });

  const numPorts = portIds.length;
  if (numPorts === 0) return [];

  // Bar region width
  const barRegionW = canvasW - GUTTER_W - RIGHT_PAD;

  // ── Determine lane heights ──────────────────────────────────────────────────
  const hasSelection = selectedPortfolioId !== null && portIds.includes(selectedPortfolioId);
  const totalSepH = (numPorts - 1) * LANE_GAP;

  let laneHMap: Map<string, number>;

  if (!hasSelection) {
    // Equal height mode — all lanes show bars
    const MIN_LANE_H = 80;
    const available  = canvasH - totalSepH;
    const equalH     = Math.max(MIN_LANE_H, Math.floor(available / numPorts));
    laneHMap = new Map(portIds.map(pid => [pid, equalH]));
  } else {
    // Accordion mode: collapsed lanes = COLLAPSED_H, expanded fills remainder
    const collapsedCount = numPorts - 1;
    const collapsedTotal = collapsedCount * COLLAPSED_H;
    const expandedH = Math.max(MIN_EXPANDED_H, canvasH - totalSepH - collapsedTotal);
    laneHMap = new Map<string, number>();
    for (const pid of portIds) {
      laneHMap.set(pid, pid === selectedPortfolioId ? expandedH : COLLAPSED_H);
    }
  }

  const lanes: Lane[] = [];
  let curY = 0;

  for (let i = 0; i < portIds.length; i++) {
    const pid    = portIds[i];
    const port   = portMap.get(pid);
    const laneH  = laneHMap.get(pid) ?? COLLAPSED_H;
    const posArr = byPort.get(pid) ?? [];

    const isCollapsed = hasSelection && pid !== selectedPortfolioId;
    const isExpanded  = hasSelection && pid === selectedPortfolioId;

    // Sort by pnl_pct ascending → worst left, best right
    const sorted = [...posArr].sort((a, b) => (a.pnl_pct ?? 0) - (b.pnl_pct ?? 0));

    // Compute global max |pnl_pct| for this lane (for scaling)
    const maxAbsPnl = sorted.reduce((m, p) => Math.max(m, Math.abs(p.pnl_pct ?? 0)), 0.01);

    // Maximum bar height = available drawing area above/below baseline
    const drawableH  = laneH - LANE_PAD_T - LANE_PAD_B;
    const halfH      = drawableH / 2;
    const baselineY  = curY + LANE_PAD_T + halfH;

    // ── Dynamic bar width: stretch bars to fill the bar region ──────────────
    const numPositions = sorted.length;
    let barW: number;
    if (numPositions <= 0) {
      barW = 8;
    } else {
      const rawBarW = Math.floor(barRegionW / numPositions) - BAR_GAP;
      barW = Math.max(4, Math.min(32, rawBarW));
    }
    const unitW = barW + BAR_GAP;

    // Collapsed lanes show no bars
    const maxBars = isCollapsed ? 0 : Math.max(1, Math.floor(barRegionW / unitW));
    const visible  = sorted.slice(0, maxBars);
    const clipped  = Math.max(0, sorted.length - maxBars);

    // Layout bars
    const bars: Bar[] = visible.map((pos, idx) => ({
      x:            GUTTER_W + idx * unitW,
      barW,
      pnlPct:       pos.pnl_pct ?? 0,
      dayPct:       pos.day_change_pct ?? 0,
      marketValue:  pos.market_value ?? 0,
      pnl:          pos.pnl ?? 0,
      ticker:       pos.ticker,
      portfolioId:  pos.portfolio_id,
      portfolioName: pos.portfolio_name,
      nodeKey:      `${pos.ticker}:${pos.portfolio_id}`,
    }));

    lanes.push({
      portfolioId:   pid,
      portfolioName: port?.name ?? pid,
      totalReturn:   port?.total_return_pct ?? 0,
      equity:        port?.equity ?? 0,
      laneY:         curY,
      laneH,
      baselineY,
      bars,
      maxAbsPnl,
      clipped,
      isCollapsed,
      isExpanded,
      barW,
    });

    curY += laneH + LANE_GAP;
  }

  return lanes;
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function fmtPct(v: number, decimals = 1): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}%`;
}

function fmtDollar(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000)     return `$${(v / 1_000).toFixed(1)}K`;
  return `$${Math.round(v).toLocaleString()}`;
}

// Safer gradient: takes hex color, returns gradient
function barGradient(
  ctx: CanvasRenderingContext2D,
  tipY: number,
  baseY: number,
  isGreen: boolean,
): CanvasGradient {
  const grad = ctx.createLinearGradient(0, tipY, 0, baseY);
  if (isGreen) {
    grad.addColorStop(0, "rgba(52, 211, 153, 1.0)");
    grad.addColorStop(1, "rgba(52, 211, 153, 0.28)");
  } else {
    grad.addColorStop(0, "rgba(248, 113, 113, 1.0)");
    grad.addColorStop(1, "rgba(248, 113, 113, 0.28)");
  }
  return grad;
}

// ── Canvas draw ────────────────────────────────────────────────────────────────
function drawWaveform(
  ctx: CanvasRenderingContext2D,
  lanes: Lane[],
  canvasW: number,
  canvasH: number,
  hoveredKey: string | null,
  selectedKey: string | null,
  selectedPortfolioId: string | null,
): void {
  // Background
  ctx.fillStyle = C_BG;
  ctx.fillRect(0, 0, canvasW, canvasH);

  for (const lane of lanes) {
    const { laneY, laneH, baselineY, bars, maxAbsPnl, clipped, isCollapsed, isExpanded, barW } = lane;

    // ── Collapsed lane: just a header row ─────────────────────────────────
    if (isCollapsed) {
      // Subtle background
      ctx.fillStyle = "rgba(0,0,0,0.10)";
      ctx.fillRect(0, laneY, canvasW, laneH);

      // Gutter background
      ctx.fillStyle = "rgba(0,0,0,0.18)";
      ctx.fillRect(0, laneY, GUTTER_W, laneH);

      // Portfolio name
      const nameStr = lane.portfolioName.length > 18
        ? lane.portfolioName.slice(0, 17) + "…"
        : lane.portfolioName;
      ctx.font         = LABEL_FONT;
      ctx.fillStyle    = C_TEXT_DIM;
      ctx.textAlign    = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(nameStr, 10, laneY + laneH * 0.38);

      // Return %
      const retStr   = fmtPct(lane.totalReturn);
      const retColor = lane.totalReturn >= 0 ? C_GREEN : C_RED;
      ctx.font      = "700 10px 'JetBrains Mono', monospace";
      ctx.fillStyle = retColor;
      ctx.fillText(retStr, 10, laneY + laneH * 0.72);

      // Equity (right side of gutter)
      const eqStr = fmtDollar(lane.equity);
      ctx.font      = LABEL_FONT_S;
      ctx.fillStyle = "rgba(255,255,255,0.20)";
      ctx.textAlign = "right";
      ctx.fillText(eqStr, GUTTER_W - 8, laneY + laneH * 0.5);
      ctx.textAlign = "left";

      // Gutter right border
      ctx.strokeStyle = "rgba(255,255,255,0.04)";
      ctx.lineWidth   = 1;
      ctx.beginPath();
      ctx.moveTo(GUTTER_W, laneY);
      ctx.lineTo(GUTTER_W, laneY + laneH);
      ctx.stroke();

      // Lane separator
      ctx.strokeStyle = C_SEPARATOR;
      ctx.lineWidth   = 1;
      ctx.beginPath();
      ctx.moveTo(0, laneY + laneH);
      ctx.lineTo(canvasW, laneY + laneH);
      ctx.stroke();

      continue;
    }

    // ── Lane hover highlight ───────────────────────────────────────────────
    const laneHovered = hoveredKey && bars.some(b => b.nodeKey === hoveredKey);
    if (laneHovered) {
      ctx.fillStyle = C_HOVER_FILL;
      ctx.fillRect(0, laneY, canvasW, laneH);
    }

    // ── Baseline ──────────────────────────────────────────────────────────
    ctx.strokeStyle = C_BASELINE;
    ctx.lineWidth   = 1;
    ctx.beginPath();
    ctx.moveTo(GUTTER_W, baselineY);
    ctx.lineTo(canvasW - RIGHT_PAD, baselineY);
    ctx.stroke();

    // ── Gutter background ─────────────────────────────────────────────────
    ctx.fillStyle = "rgba(0,0,0,0.18)";
    ctx.fillRect(0, laneY, GUTTER_W, laneH);

    if (isExpanded) {
      // ── Expanded gutter: full name, return, equity, collapse hint ────────
      // Full name (may wrap — use clipping)
      ctx.save();
      ctx.beginPath();
      ctx.rect(4, laneY, GUTTER_W - 8, laneH);
      ctx.clip();

      ctx.font         = "500 10px 'JetBrains Mono', monospace";
      ctx.fillStyle    = C_TEXT;
      ctx.textAlign    = "left";
      ctx.textBaseline = "top";
      ctx.fillText(lane.portfolioName, 10, laneY + 10);

      ctx.restore();

      // Return
      const retStr   = fmtPct(lane.totalReturn);
      const retColor = lane.totalReturn >= 0 ? C_GREEN : C_RED;
      ctx.font      = "700 13px 'JetBrains Mono', monospace";
      ctx.fillStyle = retColor;
      ctx.textAlign = "left";
      ctx.textBaseline = "top";
      ctx.fillText(retStr, 10, laneY + 28);

      // Equity
      const eqStr = fmtDollar(lane.equity);
      ctx.font      = LABEL_FONT_S;
      ctx.fillStyle = C_TEXT_DIM;
      ctx.fillText(eqStr, 10, laneY + 48);

      // Position count
      const totalBars = bars.length + clipped;
      ctx.fillStyle = "rgba(255,255,255,0.20)";
      ctx.font      = "400 8px 'JetBrains Mono', monospace";
      ctx.fillText(`${totalBars} pos`, 10, laneY + 64);

      // Collapse hint at bottom of gutter
      ctx.font      = "400 8px 'JetBrains Mono', monospace";
      ctx.fillStyle = "rgba(124,92,252,0.55)";
      ctx.textBaseline = "bottom";
      ctx.fillText("▼ collapse", 10, laneY + laneH - 8);
      ctx.textBaseline = "alphabetic";

    } else {
      // ── Normal (equal-height) gutter ─────────────────────────────────────
      const nameStr = lane.portfolioName.length > 18
        ? lane.portfolioName.slice(0, 17) + "…"
        : lane.portfolioName;

      ctx.font         = LABEL_FONT;
      ctx.fillStyle    = C_TEXT;
      ctx.textAlign    = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(nameStr, 10, laneY + 14);

      // Total return pct
      const retStr   = fmtPct(lane.totalReturn);
      const retColor = lane.totalReturn >= 0 ? C_GREEN : C_RED;
      ctx.font      = "700 11px 'JetBrains Mono', monospace";
      ctx.fillStyle = retColor;
      ctx.fillText(retStr, 10, laneY + 30);

      // Equity
      const eqStr = fmtDollar(lane.equity);
      ctx.font      = LABEL_FONT_S;
      ctx.fillStyle = C_TEXT_DIM;
      ctx.fillText(eqStr, 10, laneY + 44);

      // Position count
      const totalBars = bars.length + clipped;
      ctx.fillStyle = "rgba(255,255,255,0.20)";
      ctx.font      = "400 8px 'JetBrains Mono', monospace";
      ctx.fillText(`${totalBars} pos`, 10, laneY + laneH - 10);
    }

    // ── Bars ──────────────────────────────────────────────────────────────
    const drawableH = laneH - LANE_PAD_T - LANE_PAD_B;
    const halfH     = drawableH / 2;

    for (const bar of bars) {
      const { x, pnlPct, dayPct, nodeKey, ticker } = bar;
      const bw         = bar.barW;
      const isHovered  = nodeKey === hoveredKey;
      const isSelected = nodeKey === selectedKey;
      const isDimmed   = hoveredKey !== null && !isHovered;

      // Bar height proportional to |pnl_pct|, clamped
      const barH = Math.max(MIN_BAR_H, (Math.abs(pnlPct) / maxAbsPnl) * halfH * 0.92);
      const isGreen = pnlPct >= 0;

      // Bar geometry: positive bars rise above baseline, negative below
      const tipY  = isGreen ? baselineY - barH : baselineY;
      const baseY = isGreen ? baselineY         : baselineY + barH;

      ctx.save();
      ctx.globalAlpha = isDimmed ? 0.38 : 1.0;

      // Bar fill gradient
      const grad = barGradient(ctx, tipY, baseY, isGreen);
      ctx.fillStyle = grad;
      ctx.fillRect(x, tipY, bw, barH);

      // Hover: brighter fill + thin white border
      if (isHovered || isSelected) {
        ctx.fillStyle   = "rgba(255,255,255,0.12)";
        ctx.fillRect(x - 1, tipY - 1, bw + 2, barH + 2);
        ctx.strokeStyle = isSelected ? C_ACCENT : "rgba(255,255,255,0.6)";
        ctx.lineWidth   = 1;
        ctx.strokeRect(x - 0.5, tipY - 0.5, bw + 1, barH + 1);
      }

      // Selected: accent cap at tip
      if (isSelected) {
        ctx.fillStyle = C_ACCENT;
        const capY = isGreen ? tipY : tipY + barH - 2;
        ctx.fillRect(x - 1, capY, bw + 2, 2);
      }

      // Day change tick — purple horizontal mark within bar
      if (Math.abs(dayPct) > 0.05) {
        const dayH    = Math.max(MIN_BAR_H * 0.6, (Math.abs(dayPct) / maxAbsPnl) * halfH * 0.92);
        const dayIsGreen = dayPct >= 0;

        let tickY: number;
        if (isGreen) {
          tickY = dayIsGreen
            ? baselineY - Math.min(dayH, barH)
            : baselineY - barH * 0.35;
        } else {
          tickY = dayIsGreen
            ? baselineY + barH * 0.35
            : baselineY + Math.min(dayH, barH);
        }

        ctx.strokeStyle = C_ACCENT;
        ctx.lineWidth   = 1.5;
        ctx.beginPath();
        ctx.moveTo(x - 1,       tickY);
        ctx.lineTo(x + bw + 1,  tickY);
        ctx.stroke();
      }

      // ── Expanded-mode extras ─────────────────────────────────────────────
      if (isExpanded) {
        // % label at tip of bar (if bar is tall enough)
        if (barH > 20) {
          const pctLabel = fmtPct(pnlPct);
          ctx.font         = "400 9px 'JetBrains Mono', monospace";
          ctx.fillStyle    = isGreen ? C_GREEN : C_RED;
          ctx.textAlign    = "center";
          ctx.textBaseline = isGreen ? "bottom" : "top";
          const labelY = isGreen ? tipY - 2 : tipY + barH + 2;
          ctx.fillText(pctLabel, x + bw / 2, labelY);
          ctx.textBaseline = "alphabetic";
        }

        // Ticker label (vertical / below baseline) if bar is wide enough
        if (bw >= 14) {
          ctx.save();
          ctx.font      = "400 8px 'JetBrains Mono', monospace";
          ctx.fillStyle = "rgba(255,255,255,0.45)";
          ctx.textAlign = "center";
          ctx.textBaseline = "top";

          const labelX = x + bw / 2;
          const belowY = baselineY + (isGreen ? 4 : barH + 6);

          // Rotate for angled label
          ctx.translate(labelX, belowY);
          ctx.rotate(-Math.PI / 4);
          ctx.fillText(ticker, 0, 0);
          ctx.restore();
        }
      }

      ctx.restore();
    }

    // ── Clipped overflow label ─────────────────────────────────────────────
    if (clipped > 0) {
      const lastBar = bars[bars.length - 1];
      const overflowX = lastBar
        ? lastBar.x + lastBar.barW + 4
        : GUTTER_W + 4;
      ctx.font      = "400 8px 'JetBrains Mono', monospace";
      ctx.fillStyle = "rgba(255,255,255,0.22)";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(`+${clipped}`, overflowX, baselineY);
    }

    // ── Lane separator ─────────────────────────────────────────────────────
    ctx.strokeStyle = C_SEPARATOR;
    ctx.lineWidth   = 1;
    ctx.beginPath();
    ctx.moveTo(0, laneY + laneH);
    ctx.lineTo(canvasW, laneY + laneH);
    ctx.stroke();

    // ── Gutter right border ────────────────────────────────────────────────
    ctx.strokeStyle = "rgba(255,255,255,0.04)";
    ctx.lineWidth   = 1;
    ctx.beginPath();
    ctx.moveTo(GUTTER_W, laneY);
    ctx.lineTo(GUTTER_W, laneY + laneH);
    ctx.stroke();
  }
}

// ── Hit test ───────────────────────────────────────────────────────────────────
function hitTest(
  lanes: Lane[],
  cx: number,
  cy: number,
): { bar: Bar; lane: Lane } | null {
  for (const lane of lanes) {
    if (cy < lane.laneY || cy > lane.laneY + lane.laneH) continue;
    for (const bar of lane.bars) {
      if (cx >= bar.x && cx <= bar.x + bar.barW) {
        return { bar, lane };
      }
    }
  }
  return null;
}

// ── Gutter hit test: returns the lane whose gutter was clicked ─────────────────
function gutterHitTest(
  lanes: Lane[],
  cx: number,
  cy: number,
): Lane | null {
  if (cx > GUTTER_W) return null;
  for (const lane of lanes) {
    if (cy >= lane.laneY && cy <= lane.laneY + lane.laneH) {
      return lane;
    }
  }
  return null;
}

// ── Tooltip ────────────────────────────────────────────────────────────────────
function Tooltip({
  hovered,
  canvasW,
  canvasH,
}: {
  hovered: HoveredBar;
  canvasW: number;
  canvasH: number;
}) {
  const { bar, canvasX, canvasY } = hovered;
  const bw = bar.barW;
  const TW = 196;
  const TH = 138;

  // Prefer right of bar; flip left if near right edge
  let left = canvasX + bw + 10;
  if (left + TW > canvasW - 8) left = canvasX - TW - 10;
  if (left < 4) left = 4;

  // Prefer above mouse; flip below if near top
  let top = canvasY - TH / 2;
  if (top < 4) top = 4;
  if (top + TH > canvasH - 4) top = canvasH - TH - 4;

  const pColor = bar.pnlPct >= 0 ? C_GREEN : C_RED;
  const dColor = bar.dayPct >= 0 ? C_GREEN : C_RED;

  return (
    <div
      style={{
        position:      "absolute",
        left,
        top,
        width:         TW,
        background:    "#0e0f17",
        border:        `1px solid ${C_ACCENT}`,
        borderRadius:  4,
        padding:       "10px 13px",
        fontFamily:    "'JetBrains Mono', monospace",
        fontSize:      11,
        color:         "#e2e8f0",
        pointerEvents: "none",
        zIndex:        20,
        boxShadow:     `0 6px 28px rgba(0,0,0,0.72), 0 0 0 1px rgba(124,92,252,0.12)`,
      }}
    >
      {/* Ticker */}
      <div style={{ fontSize: 17, fontWeight: 800, color: "#ffffff", letterSpacing: "0.04em", marginBottom: 2 }}>
        {bar.ticker}
      </div>

      {/* Portfolio */}
      <div style={{ fontSize: 8, color: "rgba(255,255,255,0.38)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>
        {bar.portfolioName.length > 28 ? bar.portfolioName.slice(0, 27) + "…" : bar.portfolioName}
      </div>

      {/* P&L total */}
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ color: "rgba(255,255,255,0.40)", fontSize: 9 }}>TOTAL P&L</span>
        <span style={{ color: pColor, fontWeight: 700 }}>
          {bar.pnl >= 0 ? "+" : ""}{fmtDollar(bar.pnl)}{" "}
          <span style={{ fontSize: 9, opacity: 0.85 }}>({fmtPct(bar.pnlPct)})</span>
        </span>
      </div>

      {/* Day change */}
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ color: "rgba(255,255,255,0.40)", fontSize: 9 }}>TODAY</span>
        <span style={{ color: dColor }}>
          {fmtPct(bar.dayPct, 2)}
        </span>
      </div>

      {/* Market value */}
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, paddingTop: 6, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <span style={{ color: "rgba(255,255,255,0.40)", fontSize: 9 }}>MKT VALUE</span>
        <span style={{ color: "rgba(255,255,255,0.55)" }}>
          {fmtDollar(bar.marketValue)}
        </span>
      </div>

      {/* Day tick legend */}
      <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 5, fontSize: 8, color: "rgba(255,255,255,0.28)" }}>
        <span style={{ display: "inline-block", width: 14, height: 1.5, background: C_ACCENT, borderRadius: 1 }} />
        day change marker
      </div>
    </div>
  );
}

// ── Compute canvas height ──────────────────────────────────────────────────────
// In accordion mode we fix canvas to container height.
// In equal mode we use the larger of container height or min-required height.
function computeCanvasH(
  numPorts: number,
  containerH: number,
  selectedPortfolioId: string | null,
  hasMatchingSelection: boolean,
): number {
  if (numPorts <= 0) return Math.max(containerH, 400);

  if (hasMatchingSelection) {
    // Accordion: fill the container exactly (expanded lane fills remaining space)
    return Math.max(containerH, 400);
  }

  // Equal mode: ensure enough room for all lanes
  const MIN_LANE_H = 80;
  const minRequired = numPorts * MIN_LANE_H + (numPorts - 1) * LANE_GAP;
  return Math.max(containerH, minRequired);
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function ConstellationMap({ positions, portfolios, onPositionClick }: ConstellationMapProps) {
  const canvasRef      = useRef<HTMLCanvasElement>(null);
  const containerRef   = useRef<HTMLDivElement>(null);
  const lanesRef       = useRef<Lane[]>([]);
  const dimsRef        = useRef({ w: 0, h: 0 });
  const rafRef         = useRef<number>(0);

  const [hoveredBar, setHoveredBar]               = useState<HoveredBar | null>(null);
  const [selectedKey, setSelectedKey]             = useState<string | null>(null);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);

  const hoveredKeyRef         = useRef<string | null>(null);
  const selectedKeyRef        = useRef<string | null>(null);
  const selectedPortfolioRef  = useRef<string | null>(null);

  // Determine how many distinct portfolios are represented.
  // Memoized so the array reference stays stable between renders —
  // prevents rebuildLayout from being recreated on every hover state update,
  // which was causing canvas.width to reset (clearing the canvas) on every hover.
  const portIds = useMemo(
    () => portfolios.length > 0
      ? portfolios.map(p => p.id)
      : [...new Set(positions.map(p => p.portfolio_id))],
    [portfolios, positions],
  );
  const numActivePortfolios = portIds.length;

  // Build layout
  const rebuildLayout = useCallback((containerW: number, containerH: number) => {
    if (containerW <= 0) return;

    const selPid = selectedPortfolioRef.current;
    const hasMatchingSelection = selPid !== null && portIds.includes(selPid);

    const h = computeCanvasH(numActivePortfolios, containerH, selPid, hasMatchingSelection);
    const dpr = window.devicePixelRatio || 1;
    const canvas = canvasRef.current;
    if (canvas) {
      canvas.width  = containerW * dpr;
      canvas.height = h * dpr;
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      canvas.style.height = `${h}px`;
    }
    dimsRef.current = { w: containerW, h };
    lanesRef.current = buildLanes(positions, portfolios, containerW, h, selPid);
  }, [positions, portfolios, numActivePortfolios, portIds]);

  // RAF render loop — draws every frame unconditionally.
  // The dirty-flag guard was causing a 1-frame black flash when the mouse
  // crossed the gap between bars: hoveredKey briefly became null, triggering
  // a redraw with no hover state before the next bar was entered.
  // drawWaveform is cheap (background + lane draw, no layout recalculation),
  // so running it every frame is fine and eliminates the flash entirely.
  useEffect(() => {
    function frame() {
      const canvas = canvasRef.current;
      if (canvas && dimsRef.current.w > 0 && dimsRef.current.h > 0) {
        const ctx = canvas.getContext("2d");
        if (ctx) {
          drawWaveform(
            ctx,
            lanesRef.current,
            dimsRef.current.w,
            dimsRef.current.h,
            hoveredKeyRef.current,
            selectedKeyRef.current,
            selectedPortfolioRef.current,
          );
        }
      }
      rafRef.current = requestAnimationFrame(frame);
    }
    rafRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  // ResizeObserver — tracks both WIDTH and HEIGHT of container
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const ro = new ResizeObserver(entries => {
      const rect = entries[0].contentRect;
      const w    = Math.floor(rect.width);
      const h    = Math.floor(rect.height);
      rebuildLayout(w, h);
    });
    ro.observe(container);
    return () => ro.disconnect();
  }, [rebuildLayout]);

  // Rebuild on data change
  useEffect(() => {
    const container = containerRef.current;
    if (container) {
      const rect = container.getBoundingClientRect();
      rebuildLayout(Math.floor(rect.width), Math.floor(rect.height));
    }
  }, [rebuildLayout]);

  // Mouse move — only update state when hitting a bar.
  // Never clear hover state mid-canvas (gaps between bars).
  // Clearing only happens in handleMouseLeave when mouse exits the canvas.
  // This eliminates the flash/blank between adjacent bars.
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const cx   = e.clientX - rect.left;
    const cy   = e.clientY - rect.top;

    const hit = hitTest(lanesRef.current, cx, cy);
    if (!hit) return; // in a gap — keep last hover state, no flash

    const key = hit.bar.nodeKey;
    hoveredKeyRef.current = key;
    setHoveredBar({
      bar:           hit.bar,
      canvasX:       hit.bar.x,
      canvasY:       cy,
      laneBaselineY: hit.lane.baselineY,
    });
  }, []);

  const handleMouseLeave = useCallback(() => {
    hoveredKeyRef.current = null;
    setHoveredBar(null);
  }, []);

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const cx   = e.clientX - rect.left;
    const cy   = e.clientY - rect.top;

    // Check gutter click first (portfolio expand/collapse)
    const gutterLane = gutterHitTest(lanesRef.current, cx, cy);
    if (gutterLane) {
      const pid = gutterLane.portfolioId;
      const isDeselect = pid === selectedPortfolioRef.current;
      const newPid = isDeselect ? null : pid;
      selectedPortfolioRef.current = newPid;
      setSelectedPortfolioId(newPid);

      // Rebuild layout with new accordion state
      const container = containerRef.current;
      if (container) {
        const r = container.getBoundingClientRect();
        rebuildLayout(Math.floor(r.width), Math.floor(r.height));
      }
      return;
    }

    // Bar click → onPositionClick
    const hit = hitTest(lanesRef.current, cx, cy);
    if (hit) {
      const newKey = hit.bar.nodeKey;
      const isDeselect = newKey === selectedKeyRef.current;
      selectedKeyRef.current = isDeselect ? null : newKey;
      setSelectedKey(isDeselect ? null : newKey);
      if (!isDeselect && onPositionClick) {
        onPositionClick(hit.bar.ticker, hit.bar.portfolioId);
      }
    }
  }, [onPositionClick, rebuildLayout]);

  const hasPositions = positions.length > 0;

  // Cursor: pointer over gutter (portfolio select) or bars
  const getCursor = useCallback(() => {
    return "pointer";
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        position:   "relative",
        borderRadius: 8,
        overflowY:  "auto",
        overflowX:  "hidden",
        background: C_BG,
        border:     "1px solid var(--border-0)",
        width:      "100%",
        height:     "100%",
        minHeight:  400,
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          display: "block",
          width:   "100%",
          cursor:  getCursor(),
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onClick={handleClick}
      />

      {!hasPositions && (
        <div style={{
          position:       "absolute",
          inset:          0,
          display:        "flex",
          alignItems:     "center",
          justifyContent: "center",
          fontFamily:     "'JetBrains Mono', monospace",
          fontSize:       12,
          color:          "#444",
          letterSpacing:  "0.08em",
          pointerEvents:  "none",
        }}>
          NO POSITIONS — RUN SCAN TO POPULATE
        </div>
      )}

      {hoveredBar && (
        <Tooltip
          hovered={hoveredBar}
          canvasW={dimsRef.current.w}
          canvasH={dimsRef.current.h}
        />
      )}
    </div>
  );
}
