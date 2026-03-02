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

/** Y position for each time step: linear interpolation bottom→top. */
function computeYs(widths: number[], colTopY: number): number[] {
  const N = widths.length;
  const colH = BASELINE_Y - colTopY;
  return widths.map((_, i) => BASELINE_Y - (i / (N - 1)) * colH);
}

/** Build a smooth path segment through a list of points using quadratic beziers. */
function smoothThrough(pts: [number, number][]): string {
  if (pts.length === 0) return "";
  if (pts.length === 1) return `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
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
  if (N < 2) return "";
  const ys = computeYs(widths, colTopY);

  const L: [number, number][] = ys.map((y, i) => [colX - widths[i] / 2, y]);
  const R: [number, number][] = ys.map((y, i) => [colX + widths[i] / 2, y]);

  const leftPath = smoothThrough(L);
  const rightPathRev = smoothThrough([...R].reverse());

  // Strip the leading "M x y" from rightPathRev and replace with explicit L
  const rightContinuation = rightPathRev.replace(/^M\s+[-\d.+]+\s+[-\d.+]+/, "").trimStart();

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
  if (N < 2) return "";
  const ys = computeYs(widths, colTopY);

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
  if (N < 2) return "";
  const ys = computeYs(widths, colTopY);
  const R: [number, number][] = ys.map((y, i) => [colX + widths[i] / 2, y]);
  return smoothThrough(R);
}

// ── SVG Defs ─────────────────────────────────────────────────────────────────

export function ObeliskDefs() {
  return (
    <defs>
      <filter id="ob-rim-blur" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="0.8" />
      </filter>
      <filter id="ob-crown-blur" x="-100%" y="-100%" width="300%" height="300%">
        <feGaussianBlur stdDeviation="4" />
      </filter>
      <filter id="ob-beam-blur" x="-200%" y="-200%" width="500%" height="500%">
        <feGaussianBlur stdDeviation="2" />
      </filter>
      <filter id="ob-reflect-blur">
        <feGaussianBlur stdDeviation="1.2" />
      </filter>
    </defs>
  );
}

// ── Crown components ──────────────────────────────────────────────────────────

function PositiveCrown({
  colX, colTopY, topWidth, color, isNewHigh, crownVisible,
}: {
  colX: number; colTopY: number; topWidth: number;
  color: string; isNewHigh: boolean; crownVisible: boolean;
}) {
  if (!crownVisible) return null;
  const cy = colTopY - 4;
  const rx = topWidth * 0.55;
  return (
    <g>
      <ellipse cx={colX} cy={cy} rx={rx} ry={5}
        fill={color} opacity={0.32} filter="url(#ob-crown-blur)" />
      <ellipse cx={colX} cy={cy} rx={rx * 0.6} ry={3}
        fill={color} opacity={0.18} />
      {isNewHigh && (
        <line
          x1={colX} y1={colTopY - 4}
          x2={colX} y2={colTopY - 22}
          stroke={color} strokeWidth={1.5} strokeOpacity={0.55}
          filter="url(#ob-beam-blur)"
        />
      )}
    </g>
  );
}

function NegativeCrown({
  colX, colTopY, topWidth, color, crownVisible,
}: {
  colX: number; colTopY: number; topWidth: number;
  color: string; crownVisible: boolean;
}) {
  if (!crownVisible) return null;
  const shards: [number, number, number, number][] = [
    [colX - topWidth * 0.3, colTopY,     colX - topWidth * 0.05, colTopY - 4],
    [colX - topWidth * 0.05, colTopY - 1, colX + topWidth * 0.25, colTopY - 5],
    [colX + topWidth * 0.18, colTopY,     colX + topWidth * 0.38, colTopY - 3],
  ];
  return (
    <g opacity={0.6}>
      {shards.map(([x1, y1, x2, y2], i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
          stroke={color} strokeWidth={1} opacity={0.5} />
      ))}
      <ellipse cx={colX} cy={colTopY} rx={topWidth * 0.4} ry={2.5}
        fill={color} opacity={0.12} filter="url(#ob-crown-blur)" />
    </g>
  );
}

// ── ObeliskColumn ─────────────────────────────────────────────────────────────

export interface ObeliskColumnProps {
  geo: ObeliskGeometry;
  colX: number;
  color: string;
  id: string;
  animProgress: number;
  crownVisible: boolean;
  isHovered?: boolean;
}

export function ObeliskColumn({
  geo, colX, color, id, animProgress, crownVisible, isHovered = false,
}: ObeliskColumnProps) {
  const { widths, colTopY, finalReturn, isNewHigh } = geo;
  const progress = Math.max(0, Math.min(1, animProgress));
  const topWidth = widths[widths.length - 1];

  const frontPath = useMemo(() => buildFrontFace(colX, colTopY, widths), [colX, colTopY, widths]);
  const rightPath = useMemo(() => buildRightFace(colX, colTopY, widths), [colX, colTopY, widths]);
  const capPath   = useMemo(() => buildTopCap(colX, colTopY, topWidth), [colX, colTopY, topWidth]);
  const rimPath   = useMemo(() => buildRimPath(colX, colTopY, widths), [colX, colTopY, widths]);

  const colH  = BASELINE_Y - colTopY;
  const clipY = BASELINE_Y - colH * progress;
  const clipH = colH * progress + 40;

  const bodyGradId = `ob-body-${id}`;
  const rimGradId  = `ob-rim-${id}`;
  const reflMaskId = `ob-rm-${id}`;
  const clipId     = `ob-clip-${id}`;

  return (
    <g>
      <defs>
        {/* Body: near-black base, portfolio color bleeds into top 10% */}
        <linearGradient id={bodyGradId} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%"   stopColor="#07070f" stopOpacity={1} />
          <stop offset="88%"  stopColor="#0d0d1a" stopOpacity={1} />
          <stop offset="100%" stopColor={color}   stopOpacity={0.18} />
        </linearGradient>

        {/* Rim: portfolio color, bright at crown, dim at base; brightens on hover */}
        <linearGradient id={rimGradId} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%"   stopColor={color} stopOpacity={isHovered ? 0.5 : 0.15} />
          <stop offset="100%" stopColor={color} stopOpacity={isHovered ? 1.0 : 0.85} />
        </linearGradient>

        {/* Reflection mask: opaque at top (baseline), fades downward */}
        <linearGradient id={`${reflMaskId}-g`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="white" stopOpacity={1} />
          <stop offset="100%" stopColor="white" stopOpacity={0} />
        </linearGradient>
        <mask id={reflMaskId}>
          <rect x={colX - 120} y={BASELINE_Y} width={240} height={50}
            fill={`url(#${reflMaskId}-g)`} />
        </mask>

        {/* Animation clip: reveals from bottom upward as animProgress → 1 */}
        <clipPath id={clipId}>
          <rect x={colX - 120} y={clipY} width={240} height={clipH} />
        </clipPath>
      </defs>

      {/* Floor reflection */}
      <g
        transform={`translate(0, ${BASELINE_Y * 2}) scale(1, -1)`}
        opacity={0.14}
        filter="url(#ob-reflect-blur)"
        mask={`url(#${reflMaskId})`}
      >
        <path d={frontPath} fill={`url(#${bodyGradId})`} />
        <path d={rightPath} fill="#030306" />
      </g>

      {/* Column body — clipped to animate reveal bottom→top */}
      <g clipPath={`url(#${clipId})`}>
        <path d={rightPath} fill="#030306" />
        <path d={capPath}   fill="#09090f" />
        <path d={frontPath} fill={`url(#${bodyGradId})`} />
        <path
          d={rimPath}
          fill="none"
          stroke={`url(#${rimGradId})`}
          strokeWidth={isHovered ? 1.8 : 1}
          filter="url(#ob-rim-blur)"
        />
      </g>

      {/* Crown — outside clip so it always glows at the current top */}
      {finalReturn >= 0 ? (
        <PositiveCrown
          colX={colX} colTopY={colTopY} topWidth={topWidth}
          color={color} isNewHigh={isNewHigh} crownVisible={crownVisible}
        />
      ) : (
        <NegativeCrown
          colX={colX} colTopY={colTopY} topWidth={topWidth}
          color={color} crownVisible={crownVisible}
        />
      )}
    </g>
  );
}

// ── Color palette (matches PORTFOLIO_PALETTE in OverviewPage) ─────────────────

const PALETTE = [
  "#34d399", "#818cf8", "#38bdf8", "#fb923c",
  "#f472b6", "#a78bfa", "#fbbf24", "#4ade80",
];

// ── ObeliskField ──────────────────────────────────────────────────────────────

interface ObeliskFieldProps {
  portfolios: PortfolioSummary[];
}

export default function ObeliskField({ portfolios }: ObeliskFieldProps) {
  const [animProgress, setAnimProgress] = useState(0);
  const [crownsVisible, setCrownsVisible] = useState<boolean[]>([]);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const rafRef = useRef<number>(0);

  // Valid portfolios: have sparkline, no error, sorted worst→best return
  // (sorted so best performer renders last = visually in front)
  const valid = useMemo(
    () =>
      portfolios
        .filter((p) => !p.error && p.sparkline && p.sparkline.length >= 2)
        .sort((a, b) => (a.total_return_pct ?? 0) - (b.total_return_pct ?? 0)),
    [portfolios]
  );

  // Shared scale: pixels per % point, calibrated to highest absolute return
  const scale = useMemo(() => {
    const maxRet = Math.max(
      1,
      ...valid.map((p) => {
        const base = p.sparkline![0];
        if (base === 0) return 0;
        return Math.max(
          ...p.sparkline!.map((v) => Math.abs(((v - base) / base) * 100))
        );
      })
    );
    return OBELISK_HEIGHT / maxRet;
  }, [valid]);

  // Pre-compute geometry for all columns
  const geos = useMemo(
    () => valid.map((p) => computeObeliskGeometry(p.sparkline!, scale)),
    [valid, scale]
  );

  // Load animation: columns grow from base, then crowns ignite ranked by return
  useEffect(() => {
    if (valid.length === 0) return;
    setAnimProgress(0);
    setCrownsVisible([]);

    const start = performance.now();
    const duration = 1400;

    // cubic-bezier(0.16, 1, 0.3, 1) — spring-out easing
    function cubicBezierEase(t: number): number {
      // Newton-Raphson to solve for bezier parameter from t (x-axis)
      const p1x = 0.16, p1y = 1.0, p2x = 0.3, p2y = 1.0;
      const cx = 3 * p1x, bx = 3 * (p2x - p1x) - cx, ax = 1 - cx - bx;
      const cy = 3 * p1y, by = 3 * (p2y - p1y) - cy, ay = 1 - cy - by;
      // Solve for bezier param u where x(u) = t
      let u = t;
      for (let i = 0; i < 8; i++) {
        const xu = ((ax * u + bx) * u + cx) * u;
        const dxu = (3 * ax * u + 2 * bx) * u + cx;
        if (Math.abs(dxu) < 1e-6) break;
        u -= (xu - t) / dxu;
      }
      u = Math.max(0, Math.min(1, u));
      return ((ay * u + by) * u + cy) * u;
    }

    const frame = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      setAnimProgress(cubicBezierEase(t));
      if (t < 1) {
        rafRef.current = requestAnimationFrame(frame);
      } else {
        // Crown ignition: worst performer first, best last (most dramatic finish)
        valid.forEach((_, i) => {
          setTimeout(() => {
            setCrownsVisible((prev) => {
              const next = [...prev];
              next[i] = true;
              return next;
            });
          }, i * 80);
        });
      }
    };

    rafRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafRef.current);
  }, [valid.length]);

  // Column x positions: evenly spaced with margins
  const colXs = useMemo(() => {
    const margin = 90;
    const span = CONTAINER_W - margin * 2;
    return valid.map((_, i) =>
      valid.length === 1
        ? CONTAINER_W / 2
        : margin + (i / (valid.length - 1)) * span
    );
  }, [valid.length]);

  if (valid.length === 0) {
    return (
      <div style={{
        height: `${CONTAINER_H}px`,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: "var(--surface-1)", border: "1px solid var(--border-0)", borderRadius: "7px",
      }}>
        <p style={{ fontSize: "11px", color: "var(--text-0)" }}>
          No portfolio history to display
        </p>
      </div>
    );
  }

  return (
    <div style={{
      position: "relative",
      background: "var(--surface-1)",
      border: "1px solid var(--border-0)",
      borderRadius: "7px",
      overflow: "hidden",
    }}>
      <svg
        width="100%"
        viewBox={`0 0 ${CONTAINER_W} ${CONTAINER_H}`}
        style={{ display: "block" }}
      >
        <ObeliskDefs />

        {/* Environment: near-black void with subtle centered radial warmth */}
        <defs>
          <radialGradient id="ob-env-grad" cx="50%" cy="60%" r="55%">
            <stop offset="0%"   stopColor="#0d0d1f" stopOpacity={1} />
            <stop offset="100%" stopColor="#04040a" stopOpacity={1} />
          </radialGradient>
        </defs>
        <rect width={CONTAINER_W} height={CONTAINER_H} fill="url(#ob-env-grad)" />

        {/* Ground plane */}
        <line
          x1={20} y1={BASELINE_Y}
          x2={CONTAINER_W - 20} y2={BASELINE_Y}
          stroke="rgba(255,255,255,0.05)" strokeWidth={1}
        />

        {/* Columns — worst return renders first (behind), best last (in front) */}
        {valid.map((p, i) => {
          const geo = geos[i];
          if (!geo) return null;
          const color = PALETTE[i % PALETTE.length];
          return (
            <g
              key={p.id}
              onMouseEnter={() => setHoveredIdx(i)}
              onMouseLeave={() => setHoveredIdx(null)}
              style={{ cursor: "default" }}
            >
              <ObeliskColumn
                geo={geo}
                colX={colXs[i]}
                color={color}
                id={p.id}
                animProgress={animProgress}
                crownVisible={crownsVisible[i] ?? false}
                isHovered={hoveredIdx === i}
              />
            </g>
          );
        })}

        {/* Hover tooltip */}
        {hoveredIdx !== null && (() => {
          const p = valid[hoveredIdx];
          const geo = geos[hoveredIdx];
          if (!geo) return null;
          const cx = colXs[hoveredIdx];
          const ty = geo.colTopY - 32;
          const ret = geo.finalReturn;
          const label = `${p.name}  ${ret >= 0 ? "+" : ""}${ret.toFixed(1)}%`;
          const tw = label.length * 6.5 + 16;
          const tx = Math.min(Math.max(cx - tw / 2, 8), CONTAINER_W - tw - 8);
          return (
            <g>
              <rect x={tx} y={ty} width={tw} height={18} rx={3}
                fill="rgba(13,13,26,0.92)"
                stroke="rgba(255,255,255,0.08)" strokeWidth={1}
              />
              <text
                x={tx + tw / 2} y={ty + 12}
                textAnchor="middle"
                fontSize={9.5}
                fontFamily="monospace"
                fontWeight={600}
                fill="rgba(255,255,255,0.75)"
              >
                {label}
              </text>
            </g>
          );
        })()}

        {/* Portfolio labels below ground plane */}
        {valid.map((p, i) => (
          <text
            key={`lbl-${p.id}`}
            x={colXs[i]}
            y={BASELINE_Y + 14}
            textAnchor="middle"
            fontSize={8.5}
            fontFamily="monospace"
            fill="rgba(255,255,255,0.25)"
            letterSpacing="0.06em"
          >
            {p.id.toUpperCase()}
          </text>
        ))}
      </svg>
    </div>
  );
}
