import { useEffect, useRef, useMemo } from "react";
import type { CrossPortfolioMover, PortfolioSummary } from "../lib/types";

// ─── Constants ───────────────────────────────────────────────────────────────
const K_SPRING  = 0.012;   // cluster gravity strength
const K_REP     = 1800;    // node-node repulsion
const K_WALL    = 0.3;     // boundary push
const DAMPING   = 0.88;
const WALL_PAD  = 24;
const MIN_R     = 8;
const MAX_R     = 28;

const PALETTE = [
  "#7C5CFC", "#22D3EE", "#F59E0B", "#10B981",
  "#F43F5E", "#A78BFA", "#34D399", "#FBBF24",
];

// ─── Types ───────────────────────────────────────────────────────────────────
interface PhysNode {
  ticker: string;
  portfolioId: string;
  pnlPct: number;
  dayChangePct: number;
  marketValue: number;
  r: number;           // visual radius
  x: number;
  y: number;
  vx: number;
  vy: number;
  anchorX: number;     // cluster anchor
  anchorY: number;
  phase: number;       // breathing phase offset (0–2π)
  rippleT: number;     // ripple timer (counts up, emits at 4s intervals)
}

interface Star {
  x: number;
  y: number;
  r: number;
  speed: number;
  dx: number;
  dy: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function nodeRadius(marketValue: number): number {
  return Math.max(MIN_R, Math.min(MAX_R, Math.sqrt((marketValue ?? 5000) / 500)));
}

function tickerPhase(ticker: string): number {
  let h = 0;
  for (let i = 0; i < ticker.length; i++) h = (h * 31 + ticker.charCodeAt(i)) >>> 0;
  return (h % 1000) / 1000 * Math.PI * 2;
}

function clusterAnchors(
  portfolioIds: string[],
  w: number,
  h: number,
): Record<string, { x: number; y: number }> {
  const ids = [...new Set(portfolioIds)];
  const cx = w / 2, cy = h / 2;
  const spread = Math.min(w, h) * 0.30;
  const result: Record<string, { x: number; y: number }> = {};
  ids.forEach((id, i) => {
    const angle = -Math.PI / 2 + (i / ids.length) * Math.PI * 2;
    result[id] = {
      x: cx + Math.cos(angle) * spread,
      y: cy + Math.sin(angle) * spread,
    };
  });
  return result;
}

function makeStars(count: number, w: number, h: number, speedRange: [number, number]): Star[] {
  const stars: Star[] = [];
  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = speedRange[0] + Math.random() * (speedRange[1] - speedRange[0]);
    stars.push({
      x: Math.random() * w,
      y: Math.random() * h,
      r: 0.5 + Math.random() * 0.9,
      speed,
      dx: Math.cos(angle) * speed,
      dy: Math.sin(angle) * speed,
    });
  }
  return stars;
}

// ─── Component ───────────────────────────────────────────────────────────────
export interface ConstellationMapProps {
  positions: CrossPortfolioMover[];
  portfolios: PortfolioSummary[];
}

export default function ConstellationMap({ positions, portfolios }: ConstellationMapProps) {
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const nodesRef   = useRef<PhysNode[]>([]);
  const starsRef   = useRef<{ slow: Star[]; fast: Star[] }>({ slow: [], fast: [] });
  const rafRef     = useRef<number>(0);
  const dimsRef    = useRef({ w: 0, h: 0 });
  const mouseRef   = useRef({ x: 0, y: 0 });
  const hoverRef   = useRef<string | null>(null);
  const clickRef   = useRef<string | null>(null);

  // Portfolio color palette (hex strings, cycle if more than palette length)
  const paletteRef = useRef<Record<string, string>>({});

  // Build palette map from portfolios prop
  useMemo(() => {
    const map: Record<string, string> = {};
    portfolios.forEach((p, i) => {
      map[p.id] = PALETTE[i % PALETTE.length];
    });
    paletteRef.current = map;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [portfolios]);

  // ── Physics step ───────────────────────────────────────────────────────────
  function stepPhysics(nodes: PhysNode[], w: number, h: number, dt: number) {
    const n = nodes.length;

    // Reset forces
    const fx = new Float32Array(n);
    const fy = new Float32Array(n);

    for (let i = 0; i < n; i++) {
      const a = nodes[i];

      // 1. Spring toward cluster anchor
      fx[i] += K_SPRING * (a.anchorX - a.x);
      fy[i] += K_SPRING * (a.anchorY - a.y);

      // 2. Pairwise repulsion
      for (let j = i + 1; j < n; j++) {
        const b = nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const dist2 = dx * dx + dy * dy;
        const minDist = a.r + b.r + 14;
        if (dist2 < 120 * 120 && dist2 > 0.01) {
          const dist = Math.sqrt(dist2);
          const overlap = Math.max(0, minDist - dist);
          const f = (K_REP / dist2) + (overlap > 0 ? 0.8 * overlap : 0);
          const nx = dx / dist, ny = dy / dist;
          fx[i] += nx * f; fy[i] += ny * f;
          fx[j] -= nx * f; fy[j] -= ny * f;
        }
      }

      // 3. Boundary walls
      const left   = WALL_PAD + a.r, right  = w - WALL_PAD - a.r;
      const top    = WALL_PAD + a.r, bottom = h - WALL_PAD - a.r;
      if (a.x < left)   fx[i] += K_WALL * (left   - a.x);
      if (a.x > right)  fx[i] += K_WALL * (right  - a.x);
      if (a.y < top)    fy[i] += K_WALL * (top    - a.y);
      if (a.y > bottom) fy[i] += K_WALL * (bottom - a.y);
    }

    // Integrate
    for (let i = 0; i < n; i++) {
      const nd = nodes[i];
      nd.vx = (nd.vx + fx[i]) * DAMPING;
      nd.vy = (nd.vy + fy[i]) * DAMPING;
      nd.x += nd.vx * dt;
      nd.y += nd.vy * dt;
      nd.rippleT += dt;
    }
  }

  // ── Init / resize ──────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ro = new ResizeObserver(entries => {
      const { width } = entries[0].contentRect;
      const h = 360;
      canvas.width  = Math.floor(width);
      canvas.height = h;
      dimsRef.current = { w: canvas.width, h };

      // Rebuild stars on resize
      starsRef.current = {
        slow: makeStars(60,  canvas.width, h, [0.03, 0.06]),
        fast: makeStars(120, canvas.width, h, [0.06, 0.12]),
      };

      // Rebuild cluster anchors + scatter nodes
      const { w } = dimsRef.current;
      const anchors = clusterAnchors(positions.map(p => p.portfolio_id), w, h);
      nodesRef.current = positions.map(pos => {
        const anchor = anchors[pos.portfolio_id] ?? { x: w / 2, y: h / 2 };
        const r = nodeRadius(pos.market_value ?? 5000);
        return {
          ticker:       pos.ticker,
          portfolioId:  pos.portfolio_id,
          pnlPct:       pos.pnl_pct,
          dayChangePct: pos.day_change_pct ?? 0,
          marketValue:  pos.market_value ?? 0,
          r,
          x: anchor.x + (Math.random() - 0.5) * 80,
          y: anchor.y + (Math.random() - 0.5) * 80,
          vx: 0, vy: 0,
          anchorX: anchor.x,
          anchorY: anchor.y,
          phase:    tickerPhase(pos.ticker),
          rippleT:  Math.random() * 4,
        };
      });
    });

    ro.observe(canvas);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positions]);

  // ── rAF render loop ────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d") as CanvasRenderingContext2D;
    if (!ctx) return;

    let last = performance.now();

    function frame(now: number) {
      const dt = Math.min((now - last) / 16.67, 2.5); // normalized to 60fps
      last = now;

      const { w, h } = dimsRef.current;
      if (w === 0 || h === 0) { rafRef.current = requestAnimationFrame(frame); return; }

      const nodes   = nodesRef.current;
      const stars   = starsRef.current;
      const mouse   = mouseRef.current;
      const hover   = hoverRef.current;
      const palette = paletteRef.current;

      stepPhysics(nodes, w, h, dt);

      // ── Draw ──────────────────────────────────────────────────────────────
      ctx.clearRect(0, 0, w, h);

      // Background
      ctx.fillStyle = "#07090f";
      ctx.fillRect(0, 0, w, h);

      // Stars — layer 1 (slow)
      const mxOff1 = mouse.x * 0.015, myOff1 = mouse.y * 0.015;
      const mxOff2 = mouse.x * 0.030, myOff2 = mouse.y * 0.030;

      ctx.save();
      stars.slow.forEach(s => {
        s.x = (s.x + s.dx * dt + w) % w;
        s.y = (s.y + s.dy * dt + h) % h;
        const sx = (s.x + mxOff1 + w) % w;
        const sy = (s.y + myOff1 + h) % h;
        ctx.beginPath();
        ctx.arc(sx, sy, s.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255,255,255,0.4)";
        ctx.fill();
      });
      stars.fast.forEach(s => {
        s.x = (s.x + s.dx * dt + w) % w;
        s.y = (s.y + s.dy * dt + h) % h;
        const sx = (s.x + mxOff2 + w) % w;
        const sy = (s.y + myOff2 + h) % h;
        ctx.beginPath();
        ctx.arc(sx, sy, s.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255,255,255,0.25)";
        ctx.fill();
      });
      ctx.restore();

      // Cluster wells
      const anchors = clusterAnchors(nodes.map(n => n.portfolioId), w, h);
      const portfolioIds = [...new Set(nodes.map(n => n.portfolioId))];
      portfolioIds.forEach(pid => {
        const anchor = anchors[pid];
        if (!anchor) return;
        const color = palette[pid] ?? "#7C5CFC";
        ctx.save();
        ctx.beginPath();
        ctx.arc(anchor.x, anchor.y, 80, 0, Math.PI * 2);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 5]);
        ctx.globalAlpha = 0.18;
        ctx.stroke();
        ctx.setLineDash([]);
        // Label — use the portfolio name from portfolios prop if available
        const pid_ = pid;
        const label = pid_.toUpperCase();
        ctx.globalAlpha = 0.45;
        ctx.fillStyle = color;
        ctx.font = "10px 'JetBrains Mono', monospace";
        ctx.textAlign = "center";
        ctx.fillText(label, anchor.x, anchor.y - 86);
        ctx.restore();
      });

      // Arc connections (same portfolio pairs, skip if cluster > 12 nodes)
      portfolioIds.forEach(pid => {
        const cluster = nodes.filter(n => n.portfolioId === pid);
        if (cluster.length > 12) return;
        const color = palette[pid] ?? "#7C5CFC";
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 0.6;
        ctx.globalAlpha = 0.10;
        for (let i = 0; i < cluster.length; i++) {
          for (let j = i + 1; j < cluster.length; j++) {
            ctx.beginPath();
            ctx.moveTo(cluster[i].x, cluster[i].y);
            ctx.lineTo(cluster[j].x, cluster[j].y);
            ctx.stroke();
          }
        }
        ctx.restore();
      });

      // Nodes
      const t = now / 1000;
      const isHovering = hover !== null;

      nodes.forEach(nd => {
        const isHovered = nd.ticker === hover;
        const dimmed = isHovering && !isHovered;

        // Breathing radius
        const period = 3 + (tickerPhase(nd.ticker) / (Math.PI * 2)) * 2; // 3–5s
        const breathR = nd.r + Math.sin(t * (Math.PI * 2 / period) + nd.phase) * 2;
        const drawR   = breathR + (isHovered ? 3 : 0);

        // Color
        const color = nodeColor(nd.pnlPct);

        // Ripple ring
        const RIPPLE_INTERVAL = 4;
        if (Math.abs(nd.dayChangePct) > 1 && nd.rippleT >= RIPPLE_INTERVAL) {
          nd.rippleT = 0;
        }
        if (Math.abs(nd.dayChangePct) > 1 && nd.rippleT < 0.8) {
          const progress = nd.rippleT / 0.8;
          const rr = drawR + progress * drawR * 1.5;
          ctx.save();
          ctx.beginPath();
          ctx.arc(nd.x, nd.y, rr, 0, Math.PI * 2);
          ctx.strokeStyle = color;
          ctx.lineWidth = 1;
          ctx.globalAlpha = (1 - progress) * 0.4 * (dimmed ? 0.3 : 1);
          ctx.stroke();
          ctx.restore();
        }

        // Three-pass glow
        const baseAlpha = dimmed ? 0.35 : 1.0;
        const glowMult  = isHovered ? 2.0 : 1.0;

        // Pass 1 — outer halo
        ctx.save();
        ctx.shadowBlur  = 32 * glowMult;
        ctx.shadowColor = color;
        ctx.globalAlpha = 0.12 * baseAlpha;
        ctx.beginPath();
        ctx.arc(nd.x, nd.y, drawR, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.restore();

        // Pass 2 — mid glow
        ctx.save();
        ctx.shadowBlur  = 12 * glowMult;
        ctx.shadowColor = color;
        ctx.globalAlpha = 0.35 * baseAlpha;
        ctx.beginPath();
        ctx.arc(nd.x, nd.y, drawR, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.restore();

        // Pass 3 — core
        ctx.save();
        ctx.globalAlpha = 1.0 * baseAlpha;
        ctx.beginPath();
        ctx.arc(nd.x, nd.y, drawR, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.restore();

        // Ticker label
        ctx.save();
        ctx.font = "9px 'JetBrains Mono', monospace";
        ctx.textAlign = "center";
        ctx.fillStyle = `rgba(255,255,255,${dimmed ? 0.25 : 0.65})`;
        ctx.fillText(nd.ticker, nd.x, nd.y + drawR + 10);
        ctx.restore();

        // Day change label (only if significant)
        if (Math.abs(nd.dayChangePct) > 0.5 && !dimmed) {
          const sign = nd.dayChangePct >= 0 ? "+" : "";
          ctx.save();
          ctx.font = "8px 'JetBrains Mono', monospace";
          ctx.textAlign = "center";
          ctx.fillStyle = nd.dayChangePct >= 0 ? "#4ADE80" : "#F87171";
          ctx.globalAlpha = 0.85;
          ctx.fillText(`${sign}${nd.dayChangePct.toFixed(2)}%`, nd.x, nd.y - drawR - 8);
          ctx.restore();
        }
      });

      rafRef.current = requestAnimationFrame(frame);
    }

    rafRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ position: "relative" }}>
      <canvas
        ref={canvasRef}
        style={{ display: "block", width: "100%", height: "360px" }}
        onMouseMove={e => {
          const canvas = canvasRef.current;
          if (!canvas) return;
          const rect = canvas.getBoundingClientRect();
          const scaleX = canvas.width / rect.width;
          const scaleY = canvas.height / rect.height;
          mouseRef.current = {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top)  * scaleY,
          };
          // Hover detection
          const mx = mouseRef.current.x, my = mouseRef.current.y;
          let found: string | null = null;
          for (const nd of nodesRef.current) {
            const dx = nd.x - mx, dy = nd.y - my;
            if (Math.sqrt(dx * dx + dy * dy) < nd.r + 10) { found = nd.ticker; break; }
          }
          hoverRef.current = found;
        }}
        onMouseLeave={() => {
          hoverRef.current = null;
          mouseRef.current = { x: 0, y: 0 };
        }}
        onClick={e => {
          const canvas = canvasRef.current;
          if (!canvas) return;
          const rect = canvas.getBoundingClientRect();
          const scaleX = canvas.width / rect.width;
          const scaleY = canvas.height / rect.height;
          const mx = (e.clientX - rect.left) * scaleX;
          const my = (e.clientY - rect.top)  * scaleY;
          let found: string | null = null;
          for (const nd of nodesRef.current) {
            const dx = nd.x - mx, dy = nd.y - my;
            if (Math.sqrt(dx * dx + dy * dy) < nd.r + 10) { found = nd.ticker; break; }
          }
          clickRef.current = found === clickRef.current ? null : found;
        }}
      />
    </div>
  );
}

// ─── Color helpers ─────────────────────────────────────────────────────────────
function lerpColor(a: string, b: string, t: number): string {
  const ah = parseInt(a.slice(1), 16);
  const bh = parseInt(b.slice(1), 16);
  const ar = (ah >> 16) & 0xff, ag = (ah >> 8) & 0xff, ab_ = ah & 0xff;
  const br = (bh >> 16) & 0xff, bg = (bh >> 8) & 0xff, bb_ = bh & 0xff;
  const r  = Math.round(ar + (br - ar) * t);
  const g  = Math.round(ag + (bg - ag) * t);
  const b_ = Math.round(ab_ + (bb_ - ab_) * t);
  return `#${((r << 16) | (g << 8) | b_).toString(16).padStart(6, "0")}`;
}

function nodeColor(pnlPct: number): string {
  if (pnlPct >= 8)  return "#00FF9C";
  if (pnlPct >= 2)  return lerpColor("#4ADE80", "#00FF9C", (pnlPct - 2) / 6);
  if (pnlPct >= -2) return lerpColor("#94A3B8", "#4ADE80", (pnlPct + 2) / 4);
  if (pnlPct >= -8) return lerpColor("#FBBF24", "#94A3B8", (pnlPct + 8) / 6);
  return "#EF4444";
}
