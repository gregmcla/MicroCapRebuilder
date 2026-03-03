/** Solar-system portfolio map — portfolios as suns, positions as orbiting planets. */

import { useEffect, useRef, useState } from "react";
import type { CrossPortfolioMover, PortfolioSummary } from "../lib/types";

// ── Constants ──────────────────────────────────────────────────────────────────
const SUN_R           = 26;
const BASE_SPEED      = 0.014;   // rad/s at reference orbit radius 60px
const RIPPLE_INTERVAL = 5.0;     // seconds between day-change ripples
const RIPPLE_DURATION = 0.85;    // seconds per ripple
const CANVAS_H        = 360;

// Orbit ring radii (px from sun centre) + max planets per ring
const ORBIT_RINGS = [
  { r: 62,  cap: 5 },
  { r: 94,  cap: 8 },
  { r: 126, cap: 10 },
  { r: 158, cap: 12 },
];

// ── Colour helpers ─────────────────────────────────────────────────────────────
function lerpHex(a: string, b: string, t: number): string {
  t = Math.max(0, Math.min(1, t));
  const ah = parseInt(a.slice(1), 16), bh = parseInt(b.slice(1), 16);
  const r  = Math.round(((ah >> 16) & 0xff) * (1 - t) + ((bh >> 16) & 0xff) * t);
  const g  = Math.round(((ah >>  8) & 0xff) * (1 - t) + ((bh >>  8) & 0xff) * t);
  const bl = Math.round(( ah        & 0xff) * (1 - t) + ( bh        & 0xff) * t);
  return `#${r.toString(16).padStart(2,"0")}${g.toString(16).padStart(2,"0")}${bl.toString(16).padStart(2,"0")}`;
}

function planetColor(pct: number): string {
  if (pct >=  8) return "#00ff9c";
  if (pct >=  2) return lerpHex("#4ade80", "#00ff9c",  (pct - 2) / 6);
  if (pct >=  0) return lerpHex("#94a3b8", "#4ade80",   pct / 2);
  if (pct >= -2) return lerpHex("#fbbf24", "#94a3b8",  (pct + 2) / 2);
  if (pct >= -8) return lerpHex("#ef4444", "#fbbf24",  (pct + 8) / 6);
  return "#ef4444";
}

function sunColor(ret: number): string {
  if (ret >= 5)  return "#22c55e";
  if (ret >= 0)  return "#f59e0b";
  return "#ef4444";
}

function planetR(mv: number): number {
  return Math.max(5, Math.min(13, Math.sqrt(Math.max(0, mv) / 700)));
}

function lighten(hex: string, amt: number): string {
  const h = parseInt(hex.slice(1), 16);
  const clamp = (v: number) => Math.min(255, Math.round(v + 255 * amt));
  const r = clamp((h >> 16) & 0xff), g = clamp((h >> 8) & 0xff), b = clamp(h & 0xff);
  return `#${r.toString(16).padStart(2,"0")}${g.toString(16).padStart(2,"0")}${b.toString(16).padStart(2,"0")}`;
}

function darken(hex: string, amt: number): string {
  const h = parseInt(hex.slice(1), 16);
  const clamp = (v: number) => Math.max(0, Math.round(v - 255 * amt));
  const r = clamp((h >> 16) & 0xff), g = clamp((h >> 8) & 0xff), b = clamp(h & 0xff);
  return `#${r.toString(16).padStart(2,"0")}${g.toString(16).padStart(2,"0")}${b.toString(16).padStart(2,"0")}`;
}

function strHash(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = (((h << 5) + h) + s.charCodeAt(i)) >>> 0;
  return h;
}

// ── Sun layout ─────────────────────────────────────────────────────────────────
function layoutSuns(count: number, w: number, h: number): Array<{x: number; y: number}> {
  const cx = w / 2, cy = h / 2;
  if (count <= 0) return [];
  if (count === 1) return [{ x: cx, y: cy }];
  if (count === 2) return [{ x: w * 0.27, y: cy }, { x: w * 0.73, y: cy }];
  if (count === 3) return [
    { x: cx,       y: h * 0.26 },
    { x: w * 0.23, y: h * 0.72 },
    { x: w * 0.77, y: h * 0.72 },
  ];
  if (count === 4) return [
    { x: w * 0.26, y: h * 0.29 }, { x: w * 0.74, y: h * 0.29 },
    { x: w * 0.26, y: h * 0.73 }, { x: w * 0.74, y: h * 0.73 },
  ];
  const r = Math.min(w * 0.37, h * 0.37);
  return Array.from({ length: count }, (_, i) => ({
    x: cx + Math.cos(-Math.PI / 2 + (i / count) * Math.PI * 2) * r,
    y: cy + Math.sin(-Math.PI / 2 + (i / count) * Math.PI * 2) * r,
  }));
}

// ── Types ──────────────────────────────────────────────────────────────────────
interface SunData {
  id: string; name: string; color: string; x: number; y: number;
}

interface PlanetData {
  key:          string;
  ticker:       string;
  portfolioId:  string;
  portfolioName: string;
  color:        string;
  radius:       number;
  orbitR:       number;
  speed:        number;
  angle:        number;
  rippleT:      number;
  pnlPct:       number;
  dayChangePct: number;
  marketValue:  number;
  pnl:          number;
}

interface HoverCard {
  ticker: string; portfolioName: string; color: string;
  marketValue: number; pnl: number; pnlPct: number; dayChangePct: number;
  cssX: number; cssY: number;
}

// ── Scene builder ──────────────────────────────────────────────────────────────
function buildScene(
  positions: CrossPortfolioMover[],
  portfolios: PortfolioSummary[],
  w: number,
  h: number,
): { suns: SunData[]; planets: PlanetData[] } {
  const activePids = new Set(positions.map(p => p.portfolio_id));
  const activePorts = portfolios.filter(p => !p.error && activePids.has(p.id));
  const sunPositions = layoutSuns(activePorts.length, w, h);

  const suns: SunData[] = activePorts.map((p, i) => ({
    id:    p.id,
    name:  p.name ?? p.id,
    color: sunColor(p.total_return_pct ?? 0),
    x:     sunPositions[i]?.x ?? w / 2,
    y:     sunPositions[i]?.y ?? h / 2,
  }));

  const sunMap = new Map(suns.map(s => [s.id, s]));

  const byPort = new Map<string, CrossPortfolioMover[]>();
  for (const pos of positions) {
    const arr = byPort.get(pos.portfolio_id) ?? [];
    arr.push(pos);
    byPort.set(pos.portfolio_id, arr);
  }

  const planets: PlanetData[] = [];

  for (const [pid, posGroup] of byPort.entries()) {
    const sun = sunMap.get(pid);
    if (!sun) continue;

    const sorted = [...posGroup].sort((a, b) => (b.market_value ?? 0) - (a.market_value ?? 0));
    const ringCounts = ORBIT_RINGS.map(() => 0);
    const portHash = strHash(pid);

    for (const pos of sorted) {
      let ringIdx = 0;
      for (let ri = 0; ri < ORBIT_RINGS.length; ri++) {
        if (ringCounts[ri] < ORBIT_RINGS[ri].cap) { ringIdx = ri; break; }
        ringIdx = ORBIT_RINGS.length - 1;
      }
      const ring = ORBIT_RINGS[ringIdx];
      const posInRing = ringCounts[ringIdx];
      ringCounts[ringIdx]++;

      const ringOffset = ((portHash + ringIdx * 1234) % 10000) / 10000 * Math.PI * 2;
      const tickerOffset = (strHash(pos.ticker) % 10000) / 10000 * 0.4;
      const angle = ringOffset + (posInRing / ring.cap) * Math.PI * 2 + tickerOffset;
      const speed = BASE_SPEED * Math.sqrt(62 / ring.r);
      const r = planetR(pos.market_value ?? 3000);

      planets.push({
        key:          `${pos.ticker}:${pid}`,
        ticker:       pos.ticker,
        portfolioId:  pid,
        portfolioName: sun.name,
        color:        planetColor(pos.pnl_pct ?? 0),
        radius:       r,
        orbitR:       ring.r,
        speed,
        angle,
        rippleT:      (strHash(pos.ticker) % 500) / 500 * RIPPLE_INTERVAL,
        pnlPct:       pos.pnl_pct ?? 0,
        dayChangePct: pos.day_change_pct ?? 0,
        marketValue:  pos.market_value ?? 0,
        pnl:          pos.pnl ?? 0,
      });
    }
  }

  return { suns, planets };
}

// ── Draw helpers ───────────────────────────────────────────────────────────────
function drawSun(ctx: CanvasRenderingContext2D, sun: SunData) {
  const { x, y, color } = sun;
  const r = SUN_R;

  const corona = ctx.createRadialGradient(x, y, r * 0.6, x, y, r * 3.0);
  corona.addColorStop(0, color + "22");
  corona.addColorStop(1, color + "00");
  ctx.beginPath(); ctx.arc(x, y, r * 3.0, 0, Math.PI * 2);
  ctx.fillStyle = corona; ctx.fill();

  const glow = ctx.createRadialGradient(x, y, 0, x, y, r * 1.8);
  glow.addColorStop(0, color + "55");
  glow.addColorStop(1, color + "00");
  ctx.beginPath(); ctx.arc(x, y, r * 1.8, 0, Math.PI * 2);
  ctx.fillStyle = glow; ctx.fill();

  const surface = ctx.createRadialGradient(x - r * 0.32, y - r * 0.32, 0, x, y, r);
  surface.addColorStop(0, lighten(color, 0.52));
  surface.addColorStop(0.45, color);
  surface.addColorStop(1, darken(color, 0.42));
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = surface; ctx.fill();

  const spec = ctx.createRadialGradient(x - r * 0.36, y - r * 0.36, 0, x - r * 0.36, y - r * 0.36, r * 0.58);
  spec.addColorStop(0, "rgba(255,255,255,0.75)");
  spec.addColorStop(1, "rgba(255,255,255,0)");
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = spec; ctx.fill();
}

function drawSunLabel(ctx: CanvasRenderingContext2D, sun: SunData) {
  ctx.save();
  ctx.font = "700 8.5px 'JetBrains Mono', monospace";
  ctx.fillStyle = sun.color;
  ctx.globalAlpha = 0.72;
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";
  ctx.fillText(sun.name.toUpperCase(), sun.x, sun.y - SUN_R * 3.0 - 3);
  ctx.restore();
}

function drawOrbit(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, color: string) {
  ctx.save();
  ctx.globalAlpha = 0.13;
  ctx.strokeStyle = color;
  ctx.lineWidth = 0.6;
  ctx.setLineDash([2, 8]);
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();
}

function drawPlanet(ctx: CanvasRenderingContext2D, x: number, y: number, p: PlanetData, alpha: number) {
  const { color, radius: r } = p;

  ctx.save(); ctx.globalAlpha = 0.08 * alpha;
  const halo = ctx.createRadialGradient(x, y, 0, x, y, r * 3.4);
  halo.addColorStop(0, color); halo.addColorStop(1, "transparent");
  ctx.fillStyle = halo;
  ctx.beginPath(); ctx.arc(x, y, r * 3.4, 0, Math.PI * 2); ctx.fill();
  ctx.restore();

  ctx.save(); ctx.globalAlpha = 0.28 * alpha;
  const inner = ctx.createRadialGradient(x, y, 0, x, y, r * 1.7);
  inner.addColorStop(0, color); inner.addColorStop(1, "transparent");
  ctx.fillStyle = inner;
  ctx.beginPath(); ctx.arc(x, y, r * 1.7, 0, Math.PI * 2); ctx.fill();
  ctx.restore();

  ctx.save(); ctx.globalAlpha = alpha;
  const core = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, 0, x, y, r);
  core.addColorStop(0, lighten(color, 0.5));
  core.addColorStop(0.55, color);
  core.addColorStop(1, darken(color, 0.32));
  ctx.fillStyle = core;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}

function drawPlanetLabel(ctx: CanvasRenderingContext2D, x: number, y: number, p: PlanetData, alpha: number) {
  if (p.radius < 7) return;
  ctx.save();
  ctx.font = "600 7px 'JetBrains Mono', monospace";
  ctx.fillStyle = `rgba(255,255,255,${0.62 * alpha})`;
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillText(p.ticker, x, y + p.radius + 4);
  ctx.restore();
}

function drawRipple(ctx: CanvasRenderingContext2D, x: number, y: number, p: PlanetData) {
  if (Math.abs(p.dayChangePct) < 0.5) return;
  const t = p.rippleT / RIPPLE_DURATION;
  if (t < 0 || t > 1) return;
  const ringR = p.radius + t * p.radius * 2.4;
  ctx.save();
  ctx.globalAlpha = (1 - t) * 0.55;
  ctx.strokeStyle = p.color;
  ctx.lineWidth = 1.2;
  ctx.beginPath(); ctx.arc(x, y, ringR, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

// ── Component ──────────────────────────────────────────────────────────────────
export interface ConstellationMapProps {
  positions: CrossPortfolioMover[];
  portfolios: PortfolioSummary[];
}

export default function ConstellationMap({ positions, portfolios }: ConstellationMapProps) {
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const sunsRef     = useRef<SunData[]>([]);
  const planetsRef  = useRef<PlanetData[]>([]);
  const hoveredRef  = useRef<string | null>(null);
  const hitRef      = useRef<Array<{key: string; x: number; y: number; r: number}>>([]);
  const rafRef      = useRef<number>(0);
  const dimsRef     = useRef({ w: 0, h: 0 });
  const [card, setCard] = useState<HoverCard | null>(null);

  function rebuild(w: number, h: number) {
    const scene = buildScene(positions, portfolios, w, h);
    sunsRef.current  = scene.suns;
    planetsRef.current = scene.planets;
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(entries => {
      const cssW = entries[0].contentRect.width;
      const dpr  = window.devicePixelRatio || 1;
      canvas.width  = Math.floor(cssW * dpr);
      canvas.height = Math.floor(CANVAS_H * dpr);
      const ctx = canvas.getContext("2d")!;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      dimsRef.current = { w: cssW, h: CANVAS_H };
      rebuild(cssW, CANVAS_H);
    });
    ro.observe(canvas);
    return () => ro.disconnect();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positions, portfolios]);

  useEffect(() => {
    const { w, h } = dimsRef.current;
    if (w > 0) rebuild(w, h);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positions, portfolios]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let last = performance.now();

    function frame(now: number) {
      try {
        const ctx = canvas!.getContext("2d");
        if (!ctx) { rafRef.current = requestAnimationFrame(frame); return; }

        const dt = Math.min((now - last) / 1000, 0.05);
        last = now;

        const { w, h } = dimsRef.current;
        if (w === 0) { rafRef.current = requestAnimationFrame(frame); return; }

        const suns    = sunsRef.current;
        const planets = planetsRef.current;
        const hovered = hoveredRef.current;

        for (const p of planets) {
          if (p.key !== hovered) p.angle += p.speed * dt;
          p.rippleT += dt;
          if (p.rippleT > RIPPLE_INTERVAL) p.rippleT -= RIPPLE_INTERVAL;
        }

        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = "#05060f";
        ctx.fillRect(0, 0, w, h);

        const sunMap = new Map(suns.map(s => [s.id, s]));

        // Orbit rings — one per unique (portfolioId, orbitR) pair
        const drawnRings = new Set<string>();
        for (const p of planets) {
          const rk = `${p.portfolioId}:${p.orbitR}`;
          if (drawnRings.has(rk)) continue;
          drawnRings.add(rk);
          const sun = sunMap.get(p.portfolioId);
          if (sun) drawOrbit(ctx, sun.x, sun.y, p.orbitR, sun.color);
        }

        for (const sun of suns) { drawSun(ctx, sun); drawSunLabel(ctx, sun); }

        const sorted = [...planets].sort((a, b) => b.orbitR - a.orbitR);
        const hits: typeof hitRef.current = [];

        for (const p of sorted) {
          const sun = sunMap.get(p.portfolioId);
          if (!sun) continue;
          const px = sun.x + Math.cos(p.angle) * p.orbitR;
          const py = sun.y + Math.sin(p.angle) * p.orbitR;
          hits.push({ key: p.key, x: px, y: py, r: p.radius });
          const alpha = hovered && p.key !== hovered ? 0.22 : 1.0;
          drawRipple(ctx, px, py, p);
          drawPlanet(ctx, px, py, p, alpha);
          drawPlanetLabel(ctx, px, py, p, alpha);
        }
        hitRef.current = hits;
      } catch (err) {
        console.error("[SolarMap] frame:", err);
      }
      rafRef.current = requestAnimationFrame(frame);
    }

    rafRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  function handleMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;

    let found: typeof hitRef.current[number] | null = null;
    for (const h of hitRef.current) {
      const dx = h.x - cx, dy = h.y - cy;
      if (dx * dx + dy * dy < (h.r + 12) ** 2) { found = h; break; }
    }

    if (found) {
      hoveredRef.current = found.key;
      const p = planetsRef.current.find(pl => pl.key === found!.key);
      if (p) setCard({ ticker: p.ticker, portfolioName: p.portfolioName, color: p.color,
        marketValue: p.marketValue, pnl: p.pnl, pnlPct: p.pnlPct,
        dayChangePct: p.dayChangePct, cssX: found.x, cssY: found.y });
    } else {
      hoveredRef.current = null;
      setCard(null);
    }
  }

  return (
    <div style={{ position: "relative", borderRadius: 8, overflow: "hidden", background: "#05060f", border: "1px solid var(--border-0)" }}>
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none", zIndex: 1,
        background: "radial-gradient(ellipse at 50% 50%, transparent 35%, rgba(0,0,0,0.65) 100%)",
      }} />
      <canvas
        ref={canvasRef}
        style={{ display: "block", width: "100%", height: `${CANVAS_H}px` }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => { hoveredRef.current = null; setCard(null); }}
      />
      {card && <PlanetCard card={card} canvasRef={canvasRef} />}
    </div>
  );
}

// ── Detail card ────────────────────────────────────────────────────────────────
function PlanetCard({ card, canvasRef }: { card: HoverCard; canvasRef: React.RefObject<HTMLCanvasElement | null> }) {
  const CARD_W = 168, CARD_H = 118;
  const cw = canvasRef.current?.getBoundingClientRect().width ?? 800;
  const left = Math.max(8, Math.min(card.cssX - CARD_W / 2, cw - CARD_W - 8));
  const flip = card.cssY > CANVAS_H / 2;
  const top  = Math.max(8, flip ? card.cssY - CARD_H - 20 : card.cssY + 20);
  const sign = (v: number) => v >= 0 ? "+" : "";
  const pc = card.pnlPct >= 0 ? "#4ade80" : "#f87171";
  const dc = card.dayChangePct >= 0 ? "#4ade80" : "#f87171";

  return (
    <div style={{
      position: "absolute", left, top, width: CARD_W, zIndex: 10,
      background: "rgba(5,6,15,0.94)", backdropFilter: "blur(16px)",
      border: "1px solid rgba(255,255,255,0.09)", borderRadius: 9,
      padding: "11px 14px", pointerEvents: "none",
      boxShadow: `0 0 0 1px rgba(0,0,0,0.3), 0 8px 32px rgba(0,0,0,0.55), 0 0 16px ${card.color}18`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>
        <div style={{ width: 7, height: 7, borderRadius: "50%", background: card.color, flexShrink: 0,
          boxShadow: `0 0 8px ${card.color}` }} />
        <span style={{ fontSize: 8.5, textTransform: "uppercase", letterSpacing: "0.09em", color: card.color, opacity: 0.8 }}>
          {card.portfolioName}
        </span>
      </div>
      <div style={{ fontSize: 22, fontFamily: "monospace", fontWeight: 800, color: "#fff", lineHeight: 1, marginBottom: 7, letterSpacing: "-0.01em" }}>
        {card.ticker}
      </div>
      <div style={{ fontSize: 11.5, color: "rgba(255,255,255,0.4)", marginBottom: 5 }}>
        ${Math.round(card.marketValue).toLocaleString()}
      </div>
      <div style={{ fontSize: 13.5, color: pc, fontFamily: "monospace", fontWeight: 700 }}>
        {sign(card.pnl)}${Math.abs(card.pnl).toFixed(0)}
        <span style={{ fontSize: 11, opacity: 0.8, marginLeft: 6 }}>{sign(card.pnlPct)}{card.pnlPct.toFixed(1)}%</span>
      </div>
      {Math.abs(card.dayChangePct) > 0.01 && (
        <div style={{ fontSize: 10.5, color: dc, fontFamily: "monospace", marginTop: 4, opacity: 0.85 }}>
          today {sign(card.dayChangePct)}{card.dayChangePct.toFixed(2)}%
        </div>
      )}
    </div>
  );
}
