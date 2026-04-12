import { useRef, useEffect } from "react";

interface BackgroundCanvasProps {
  mouseX: React.MutableRefObject<number>;
  mouseY: React.MutableRefObject<number>;
  tickers: string[];
}

export default function BackgroundCanvas({ mouseX, mouseY, tickers }: BackgroundCanvasProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);
  const dropsRef = useRef<Array<{ x: number; y: number; speed: number; opacity: number; char: string }>>([]);
  const particlesRef = useRef<Array<{
    x: number; y: number; vx: number; vy: number;
    size: number; opacity: number; color: [number, number, number];
  }>>([]);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const parent = c.parentElement!;
    const dpr = Math.min(window.devicePixelRatio, 2);
    let w = 0, h = 0;

    const tickerList = tickers.length > 0 ? tickers : ["AAPL", "MSFT", "NVDA"];

    const resize = () => {
      w = parent.clientWidth;
      h = parent.clientHeight;
      c.width = w * dpr;
      c.height = h * dpr;
      c.style.width = w + "px";
      c.style.height = h + "px";

      dropsRef.current = Array.from({ length: 50 }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        speed: 0.2 + Math.random() * 1,
        opacity: 0.01 + Math.random() * 0.03,
        char: tickerList[Math.floor(Math.random() * tickerList.length)],
      }));

      particlesRef.current = Array.from({ length: 80 }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.2,
        vy: (Math.random() - 0.5) * 0.2,
        size: 0.5 + Math.random() * 1.5,
        opacity: 0.05 + Math.random() * 0.15,
        color: (Math.random() > 0.5 ? [34, 197, 94] : [239, 68, 68]) as [number, number, number],
      }));
    };

    resize();
    window.addEventListener("resize", resize);

    let t = 0;
    const draw = () => {
      frameRef.current = requestAnimationFrame(draw);
      const ctx = c.getContext("2d")!;
      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, w, h);
      t += 0.016;

      ctx.strokeStyle = "rgba(34,197,94,0.008)";
      ctx.lineWidth = 0.5;
      for (let x = 0; x < w; x += 50) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      }
      for (let y = 0; y < h; y += 50) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
      }

      particlesRef.current.forEach((p) => {
        if (mouseX.current > 0) {
          const dx = mouseX.current - p.x;
          const dy = mouseY.current - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 200 && dist > 0) {
            p.vx += (dx / dist) * 0.01;
            p.vy += (dy / dist) * 0.01;
          }
        }
        p.vx *= 0.995; p.vy *= 0.995;
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = w; if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h; if (p.y > h) p.y = 0;

        const pulse = 0.7 + Math.sin(t * 2 + p.x * 0.01) * 0.3;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * pulse, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color.join(",")},${p.opacity * pulse})`;
        ctx.fill();

        particlesRef.current.forEach((q) => {
          if (p === q) return;
          const d = Math.sqrt((p.x - q.x) ** 2 + (p.y - q.y) ** 2);
          if (d < 60) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = `rgba(34,197,94,${(1 - d / 60) * 0.02})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        });
      });

      ctx.font = "8px monospace";
      dropsRef.current.forEach((d) => {
        ctx.fillStyle = `rgba(34,197,94,${d.opacity})`;
        ctx.fillText(d.char, d.x, d.y);
        d.y += d.speed;
        if (d.y > h + 20) {
          d.y = -20;
          d.x = Math.random() * w;
          d.char = tickerList[Math.floor(Math.random() * tickerList.length)];
        }
      });

      const sy = (t * 30) % (h + 60) - 30;
      const sg = ctx.createLinearGradient(0, sy - 20, 0, sy + 20);
      sg.addColorStop(0, "rgba(34,197,94,0)");
      sg.addColorStop(0.5, "rgba(34,197,94,0.025)");
      sg.addColorStop(1, "rgba(34,197,94,0)");
      ctx.fillStyle = sg;
      ctx.fillRect(0, sy - 20, w, 40);
      ctx.beginPath(); ctx.moveTo(0, sy); ctx.lineTo(w, sy);
      ctx.strokeStyle = "rgba(34,197,94,0.04)"; ctx.lineWidth = 1; ctx.stroke();

      const sx = (t * 15) % (w + 60) - 30;
      const sg2 = ctx.createLinearGradient(sx - 20, 0, sx + 20, 0);
      sg2.addColorStop(0, "rgba(34,211,238,0)");
      sg2.addColorStop(0.5, "rgba(34,211,238,0.012)");
      sg2.addColorStop(1, "rgba(34,211,238,0)");
      ctx.fillStyle = sg2;
      ctx.fillRect(sx - 20, 0, 40, h);

      ctx.restore();
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frameRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [mouseX, mouseY, tickers]);

  return (
    <canvas
      ref={ref}
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
    />
  );
}
