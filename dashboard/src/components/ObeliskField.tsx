/** Performance Obelisk Field — sculpted portfolio monuments. */

import { useMemo, useState, useEffect, useRef } from "react";
import type { PortfolioSummary } from "../lib/types";

// ── Constants ────────────────────────────────────────────────────────────────

export const CONTAINER_W = 800;
export const CONTAINER_H = 340;
export const BASELINE_Y = 295;     // y of 0% return ground plane
export const OBELISK_HEIGHT = 245; // max column height in px
const COL_BASE_WIDTH = 36;
const FLARE_K = 4.0;
const SCAR_K = 1.8;
const MIN_WIDTH = 8;
const DEPTH_X = 14;
const DEPTH_Y = -7;

// ── Types ────────────────────────────────────────────────────────────────────

export interface ObeliskGeometry {
  cum: number[];        // cumulative return % at each step
  vel: number[];        // smoothed velocity (first derivative)
  dd: number[];         // drawdown from prior high (≤ 0)
  widths: number[];     // column width at each step
  finalReturn: number;  // cum[last]
  isNewHigh: boolean;   // ended at all-time high
  colTopY: number;      // y of crown
}

// ── Geometry ─────────────────────────────────────────────────────────────────

export function computeObeliskGeometry(
  sparkline: number[],
  scale: number
): ObeliskGeometry | null {
  if (!sparkline || sparkline.length < 2) return null;
  const base = sparkline[0];
  if (base === 0) return null;

  // cumulative return %
  const cum = sparkline.map((v) => ((v - base) / base) * 100);

  // raw velocity
  const velRaw = cum.map((v, i) => (i === 0 ? 0 : v - cum[i - 1]));

  // smoothed velocity: 5-point moving average
  const vel = velRaw.map((_, i) => {
    const slice = velRaw.slice(Math.max(0, i - 2), Math.min(velRaw.length, i + 3));
    return slice.reduce((a, b) => a + b, 0) / slice.length;
  });

  // drawdown from prior high
  let runMax = cum[0];
  const dd = cum.map((v) => {
    runMax = Math.max(runMax, v);
    return v - runMax;
  });

  // width at each step
  const widths = vel.map((v, i) =>
    Math.max(MIN_WIDTH, COL_BASE_WIDTH + v * FLARE_K + dd[i] * SCAR_K)
  );

  const finalReturn = cum[cum.length - 1];
  const clampedReturn = Math.max(finalReturn, 0.5);
  const colTopY = BASELINE_Y - clampedReturn * scale;

  const maxCum = Math.max(...cum);
  const isNewHigh = finalReturn >= maxCum - 0.01;

  return { cum, vel, dd, widths, finalReturn, isNewHigh, colTopY };
}

// ── Path builders ─────────────────────────────────────────────────────────────

/** Build a smooth path segment through a list of points using quadratic beziers. */
function smoothThrough(pts: [number, number][]): string {
  if (pts.length === 0) return "";
  let d = `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
  for (let i = 1; i < pts.length; i++) {
    const [cx, cy] = pts[i - 1];
    const [nx, ny] = pts[i];
    const mx = ((cx + nx) / 2).toFixed(1);
    const my = ((cy + ny) / 2).toFixed(1);
    d += ` Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${mx} ${my}`;
  }
  const last = pts[pts.length - 1];
  d += ` Q ${last[0].toFixed(1)} ${last[1].toFixed(1)} ${last[0].toFixed(1)} ${last[1].toFixed(1)}`;
  return d;
}

/** Closed polygon for the front face. */
export function buildFrontFace(
  colX: number,
  colTopY: number,
  widths: number[]
): string {
  const N = widths.length;
  const colH = BASELINE_Y - colTopY;
  const ys = widths.map((_, i) => BASELINE_Y - (i / (N - 1)) * colH);

  const L: [number, number][] = ys.map((y, i) => [colX - widths[i] / 2, y]);
  const R: [number, number][] = ys.map((y, i) => [colX + widths[i] / 2, y]);

  const leftPath = smoothThrough(L);
  const rightPathRev = smoothThrough([...R].reverse());

  // Strip the leading "M x y" from rightPathRev and replace with explicit L
  const rightContinuation = rightPathRev.replace(/^M\s+[\d.+-]+\s+[\d.+-]+/, "").trimStart();

  return (
    leftPath +
    ` L ${R[N - 1][0].toFixed(1)} ${R[N - 1][1].toFixed(1)}` +
    " " + rightContinuation +
    " Z"
  );
}

/** Parallelogram for the right (shadow) face. */
export function buildRightFace(
  colX: number,
  colTopY: number,
  widths: number[]
): string {
  const N = widths.length;
  const colH = BASELINE_Y - colTopY;
  const ys = widths.map((_, i) => BASELINE_Y - (i / (N - 1)) * colH);

  const fr: [number, number][] = ys.map((y, i) => [colX + widths[i] / 2, y]);
  const br: [number, number][] = fr.map(([x, y]) => [x + DEPTH_X, y + DEPTH_Y]);

  const frontEdge = smoothThrough(fr);
  const backEdgePart = (() => {
    let s = ` L ${br[N - 1][0].toFixed(1)} ${br[N - 1][1].toFixed(1)}`;
    for (let i = N - 2; i >= 0; i--) s += ` L ${br[i][0].toFixed(1)} ${br[i][1].toFixed(1)}`;
    return s;
  })();
  return frontEdge + backEdgePart + " Z";
}

/** Small parallelogram cap at the crown. */
export function buildTopCap(
  colX: number,
  colTopY: number,
  topWidth: number
): string {
  const tl: [number, number] = [colX - topWidth / 2, colTopY];
  const tr: [number, number] = [colX + topWidth / 2, colTopY];
  const trb: [number, number] = [tr[0] + DEPTH_X, tr[1] + DEPTH_Y];
  const tlb: [number, number] = [tl[0] + DEPTH_X, tl[1] + DEPTH_Y];
  return `M ${tl[0].toFixed(1)} ${tl[1].toFixed(1)} L ${tr[0].toFixed(1)} ${tr[1].toFixed(1)} L ${trb[0].toFixed(1)} ${trb[1].toFixed(1)} L ${tlb[0].toFixed(1)} ${tlb[1].toFixed(1)} Z`;
}

/** Open path for rim light — right edge of front face. */
export function buildRimPath(
  colX: number,
  colTopY: number,
  widths: number[]
): string {
  const N = widths.length;
  const colH = BASELINE_Y - colTopY;
  const ys = widths.map((_, i) => BASELINE_Y - (i / (N - 1)) * colH);
  const R: [number, number][] = ys.map((y, i) => [colX + widths[i] / 2, y]);
  return smoothThrough(R);
}
