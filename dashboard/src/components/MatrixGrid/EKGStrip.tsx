import { useRef, useEffect } from "react";
import type { MatrixPortfolio } from "./types";

interface EKGStripProps {
  portfolios: MatrixPortfolio[];
}

/** Expand an array of daily pnl % values into a smooth scrolling point buffer.
 *  Each day → 20 points: flat noise → spike → flat noise. */
function buildBuffer(pnlArray: number[]): { v: number; pct: number; flat: boolean }[] {
  const pts: { v: number; pct: number; flat: boolean }[] = [];
  for (const pct of pnlArray) {
    const amp = Math.max(-4, Math.min(4, pct));
    for (let k = 0; k < 20; k++) {
      let v: number;
      let flat = false;
      if      (k === 9 || k === 10) v = amp;
      else if (k === 8 || k === 11) v = amp * 0.55;
      else if (k === 7 || k === 12) v = amp * 0.22;
      else if (k === 6 || k === 13) v = amp * 0.07;
      else { v = 0; flat = true; }
      pts.push({ v, pct, flat });
    }
  }
  return pts;
}

export default function EKGStrip({ portfolios }: EKGStripProps) {
  const ref        = useRef<HTMLCanvasElement>(null);
  const frameRef   = useRef<number>(0);

  // Synthetic heartbeat state (used when no real data)
  const linesRef = useRef(
    portfolios.map(() => ({ pts: [] as number[], phase: Math.random() * 100 }))
  );

  // Real-data buffer state
  const realRef = useRef<{ pts: { v: number; pct: number; flat: boolean }[]; pos: number; color: string } | null>(null);

  useEffect(() => {
    linesRef.current = portfolios.map(() => ({
      pts: [] as number[],
      phase: Math.random() * 100,
    }));
    // Rebuild real buffer when equity curve changes
    const curve = portfolios[0]?.equityCurve;
    if (curve && curve.length >= 3) {
      realRef.current = { pts: buildBuffer(curve), pos: 0, color: portfolios[0]?.color ?? "#4ade80" };
    } else {
      realRef.current = null;
    }
  }, [portfolios]);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const parent = c.parentElement!;
    const dpr = 2;
    let w = 0, h = 0;

    const resize = () => {
      w = parent.clientWidth;
      h = parent.clientHeight;
      c.width  = w * dpr;
      c.height = h * dpr;
      c.style.width  = w + "px";
      c.style.height = h + "px";
    };
    resize();
    window.addEventListener("resize", resize);

    let frame = 0;

    const draw = () => {
      frameRef.current = requestAnimationFrame(draw);
      frame++;
      const ctx = c.getContext("2d")!;
      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, w, h);

      if (realRef.current && realRef.current.pts.length >= 3) {
        // ── Real-data path ──────────────────────────────────────────────
        const real    = realRef.current;
        const step    = 1.5;
        const visible = Math.floor(w / step) + 2;
        const y0      = h / 2;
        const range   = h * 0.38;
        const color   = real.color;

        // Advance scroll every 2 frames
        if (frame % 2 === 0) real.pos = (real.pos + 1) % real.pts.length;

        // Collect visible slice
        const slice: { v: number; pct: number }[] = [];
        for (let k = 0; k < visible; k++) {
          const pt = real.pts[(real.pos + k) % real.pts.length];
          slice.push({
            v:   pt.flat ? (Math.random() - 0.5) * 0.09 : pt.v,
            pct: pt.pct,
          });
        }

        // Zero baseline
        ctx.beginPath();
        ctx.moveTo(0, y0);
        ctx.lineTo(w, y0);
        ctx.strokeStyle = "rgba(255,255,255,0.04)";
        ctx.lineWidth   = 0.5;
        ctx.stroke();

        // Colored segments
        for (let j = 1; j < slice.length; j++) {
          const x0 = (j - 1) * step;
          const x1 = j       * step;
          const yA = y0 - slice[j - 1].v * range;
          const yB = y0 - slice[j].v     * range;
          const pct   = slice[j].pct;
          const isGain = pct >  0.05;
          const isLoss = pct < -0.05;
          const isBig  = Math.abs(pct) >= 1.0;
          const col    = isGain ? "#4ade80" : isLoss ? "#f87171" : color;
          const alpha  = isBig             ? "ee"
                       : Math.abs(pct) > 0.4 ? "bb"
                       : Math.abs(pct) > 0.1 ? "77"
                       : "2a";

          // Glow halo on big moves
          if (isBig) {
            ctx.beginPath();
            ctx.moveTo(x0, yA);
            ctx.lineTo(x1, yB);
            ctx.strokeStyle = col + "22";
            ctx.lineWidth   = 6;
            ctx.stroke();
          }

          // Main line
          ctx.beginPath();
          ctx.moveTo(x0, yA);
          ctx.lineTo(x1, yB);
          ctx.strokeStyle = col + alpha;
          ctx.lineWidth   = 1.2;
          ctx.stroke();
        }

        // Cursor dot at right edge
        const last   = slice[slice.length - 1];
        const cx     = Math.min((slice.length - 1) * step, w - 2);
        const cy     = y0 - last.v * range;
        const dotCol = last.pct > 0 ? "#4ade80" : last.pct < 0 ? "#f87171" : "#4ade80";
        ctx.beginPath();
        ctx.arc(cx, cy, 2, 0, Math.PI * 2);
        ctx.fillStyle = dotCol + "cc";
        ctx.fill();

      } else {
        // ── Synthetic fallback (original logic) ──────────────────────────
        const laneH = portfolios.length > 0 ? h / portfolios.length : h;

        portfolios.forEach((port, i) => {
          const line = linesRef.current[i];
          if (!line) return;
          const y0 = i * laneH + laneH / 2;

          line.phase += 0.06;
          const heartbeat =
            Math.sin(line.phase) * 0.3 +
            (Math.sin(line.phase * 3.7) > 0.85
              ? Math.sin(line.phase * 3.7) * 3
              : 0) +
            (Math.random() - 0.5) * 0.15;
          line.pts.push(heartbeat);
          if (line.pts.length > w / 1.5) line.pts.shift();

          const step = 1.5;
          ctx.beginPath();
          for (let j = 0; j < line.pts.length; j++) {
            const x = w - (line.pts.length - j) * step;
            const y = y0 + line.pts[j] * (laneH * 0.35);
            j === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
          }
          ctx.strokeStyle = port.color + "55";
          ctx.lineWidth   = 1;
          ctx.stroke();

          ctx.strokeStyle = port.color + "18";
          ctx.lineWidth   = 3;
          ctx.stroke();

          ctx.font      = "7px monospace";
          ctx.fillStyle = port.color + "44";
          ctx.fillText(port.abbr, 4, y0 + 3);

          if (i < portfolios.length - 1) {
            ctx.beginPath();
            ctx.moveTo(0, (i + 1) * laneH);
            ctx.lineTo(w, (i + 1) * laneH);
            ctx.strokeStyle = "rgba(255,255,255,0.02)";
            ctx.lineWidth   = 0.5;
            ctx.stroke();
          }
        });
      }

      ctx.restore();
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frameRef.current);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas ref={ref} style={{ width: "100%", height: "100%", display: "block" }} />
  );
}
