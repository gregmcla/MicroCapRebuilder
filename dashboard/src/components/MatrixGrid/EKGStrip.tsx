import { useRef, useEffect } from "react";
import type { MatrixPortfolio } from "./types";

interface EKGStripProps {
  portfolios: MatrixPortfolio[];
}

export default function EKGStrip({ portfolios }: EKGStripProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);
  const linesRef = useRef(
    portfolios.map(() => ({ pts: [] as number[], phase: Math.random() * 100 }))
  );

  useEffect(() => {
    linesRef.current = portfolios.map(() => ({
      pts: [] as number[],
      phase: Math.random() * 100,
    }));
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
      c.width = w * dpr;
      c.height = h * dpr;
      c.style.width = w + "px";
      c.style.height = h + "px";
    };
    resize();
    window.addEventListener("resize", resize);

    const draw = () => {
      frameRef.current = requestAnimationFrame(draw);
      const ctx = c.getContext("2d")!;
      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, w, h);

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
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.strokeStyle = port.color + "18";
        ctx.lineWidth = 3;
        ctx.stroke();

        ctx.font = "7px monospace";
        ctx.fillStyle = port.color + "44";
        ctx.fillText(port.abbr, 4, y0 + 3);

        if (i < portfolios.length - 1) {
          ctx.beginPath();
          ctx.moveTo(0, (i + 1) * laneH);
          ctx.lineTo(w, (i + 1) * laneH);
          ctx.strokeStyle = "rgba(255,255,255,0.02)";
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      });

      ctx.restore();
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frameRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [portfolios]);

  return (
    <canvas ref={ref} style={{ width: "100%", height: "100%", display: "block" }} />
  );
}
