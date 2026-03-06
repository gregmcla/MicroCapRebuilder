import { useRef, useEffect } from "react";

interface SparklineProps {
  data: number[];
  color: string;
  w?: number;
  h?: number;
}

export default function Sparkline({ data, color, w = 48, h = 14 }: SparklineProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const aRef = useRef<number>(0);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    const d = 2;
    c.width = w * d;
    c.height = h * d;
    ctx.scale(d, d);
    let rev = 0;

    const draw = () => {
      rev = Math.min(data.length, rev + 0.8);
      ctx.clearRect(0, 0, w, h);
      const mn = Math.min(...data);
      const mx = Math.max(...data);
      const rg = mx - mn || 1;
      const s = w / (data.length - 1);

      ctx.beginPath();
      for (let i = 0; i < Math.floor(rev); i++) {
        const x = i * s;
        const y = h - ((data[i] - mn) / rg) * (h - 2) - 1;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.strokeStyle = color + "33";
      ctx.lineWidth = 3;
      ctx.stroke();

      ctx.beginPath();
      for (let i = 0; i < Math.floor(rev); i++) {
        const x = i * s;
        const y = h - ((data[i] - mn) / rg) * (h - 2) - 1;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.strokeStyle = color + "99";
      ctx.lineWidth = 1;
      ctx.stroke();

      if (rev > 1) {
        ctx.beginPath();
        for (let i = 0; i < Math.floor(rev); i++) {
          const x = i * s;
          const y = h - ((data[i] - mn) / rg) * (h - 2) - 1;
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.lineTo((Math.floor(rev) - 1) * s, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        const g = ctx.createLinearGradient(0, 0, 0, h);
        g.addColorStop(0, color + "14");
        g.addColorStop(1, color + "01");
        ctx.fillStyle = g;
        ctx.fill();
      }

      if (rev >= data.length) {
        const lx = (data.length - 1) * s;
        const ly = h - ((data[data.length - 1] - mn) / rg) * (h - 2) - 1;
        ctx.beginPath();
        ctx.arc(lx, ly, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      }

      if (rev < data.length) aRef.current = requestAnimationFrame(draw);
    };

    aRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(aRef.current);
  }, [data, color, w, h]);

  return <canvas ref={ref} style={{ width: w, height: h, display: "block" }} />;
}
