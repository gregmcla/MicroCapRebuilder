import { useRef, useEffect } from "react";
import type { MatrixPosition, MatrixPortfolio } from "./types";

interface AllocRingProps {
  positions: MatrixPosition[];
  portfolios: MatrixPortfolio[];
}

export default function AllocRing({ positions, portfolios }: AllocRingProps) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    const d = 2;
    const s = 32;
    c.width = s * d;
    c.height = s * d;
    ctx.scale(d, d);

    const totals: Record<string, number> = {};
    positions.forEach((p) => {
      totals[p.portfolioId] = (totals[p.portfolioId] ?? 0) + p.value;
    });
    const total = Object.values(totals).reduce((a, b) => a + b, 0) || 1;
    const cx = s / 2, cy = s / 2, r = 12, inner = 8;

    let angle = -Math.PI / 2;
    portfolios.forEach((port) => {
      const val = totals[port.id] ?? 0;
      const sweep = (val / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(cx, cy, r, angle, angle + sweep);
      ctx.arc(cx, cy, inner, angle + sweep, angle, true);
      ctx.closePath();
      ctx.fillStyle = port.color + "88";
      ctx.fill();
      angle += sweep;
    });

    ctx.beginPath();
    ctx.arc(cx, cy, inner - 1, 0, Math.PI * 2);
    ctx.fillStyle = "#06080a";
    ctx.fill();
  }, [positions, portfolios]);

  return <canvas ref={ref} style={{ width: 32, height: 32 }} />;
}
