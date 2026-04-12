import { useRef, useEffect, useState, useCallback } from "react";

interface InteractiveSparklineProps {
  data: number[];        // raw price / equity values
  color: string;
  h?: number;
  timestamps?: number[]; // unix milliseconds — one per data point, for tooltip dates
}

const PAD_T = 8;
const PAD_B = 8;
const PAD_L = 4;
const PAD_R = 4;

export default function InteractiveSparkline({ data, color, h = 80, timestamps }: InteractiveSparklineProps) {
  const wrapRef   = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [w,        setW]        = useState(360);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  // Track container width
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      const width = entries[0].contentRect.width;
      if (width > 0) setW(Math.floor(width));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const cw = w - PAD_L - PAD_R;
  const ch = h - PAD_T - PAD_B;

  const toX = useCallback((i: number) =>
    PAD_L + (i / Math.max(data.length - 1, 1)) * cw,
  [data.length, cw]);

  // Draw: runs whenever w, h, data, color, hoverIdx changes
  useEffect(() => {
    const c = canvasRef.current;
    if (!c || data.length < 2 || w === 0) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    c.width  = w * dpr;
    c.height = h * dpr;
    const ctx = c.getContext("2d")!;
    ctx.scale(dpr, dpr);

    const mn  = Math.min(...data);
    const mx  = Math.max(...data);
    const rg  = mx - mn || 1;
    const toY = (v: number) => PAD_T + ((mx - v) / rg) * ch;

    // ── Area fill ────────────────────────────────────────────────────────────
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      i === 0 ? ctx.moveTo(toX(i), toY(data[i])) : ctx.lineTo(toX(i), toY(data[i]));
    }
    ctx.lineTo(toX(data.length - 1), PAD_T + ch);
    ctx.lineTo(PAD_L, PAD_T + ch);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, PAD_T, 0, PAD_T + ch);
    grad.addColorStop(0, color + "28");
    grad.addColorStop(1, color + "02");
    ctx.fillStyle = grad;
    ctx.fill();

    // ── Glow halo ────────────────────────────────────────────────────────────
    ctx.save();
    ctx.globalCompositeOperation = "screen";
    ctx.filter      = "blur(5px)";
    ctx.globalAlpha = 0.55;
    ctx.strokeStyle = color;
    ctx.lineWidth   = 5;
    ctx.lineJoin    = "round";
    ctx.lineCap     = "round";
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      i === 0 ? ctx.moveTo(toX(i), toY(data[i])) : ctx.lineTo(toX(i), toY(data[i]));
    }
    ctx.stroke();
    ctx.filter = "none";
    ctx.restore();

    // ── Crisp line ───────────────────────────────────────────────────────────
    ctx.save();
    ctx.strokeStyle = color + "cc";
    ctx.lineWidth   = 1.5;
    ctx.lineJoin    = "round";
    ctx.lineCap     = "round";
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      i === 0 ? ctx.moveTo(toX(i), toY(data[i])) : ctx.lineTo(toX(i), toY(data[i]));
    }
    ctx.stroke();
    ctx.restore();

    // ── Endpoint dot ─────────────────────────────────────────────────────────
    ctx.save();
    ctx.beginPath();
    ctx.arc(toX(data.length - 1), toY(data[data.length - 1]), 3, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.restore();

    // ── Hover: crosshair + dot + tooltip ─────────────────────────────────────
    if (hoverIdx !== null) {
      const idx  = Math.max(0, Math.min(data.length - 1, hoverIdx));
      const dotX = toX(idx);
      const dotY = toY(data[idx]);
      const val  = data[idx];
      const pct  = ((val - data[0]) / data[0]) * 100;

      // Vertical crosshair
      ctx.save();
      ctx.strokeStyle = "rgba(255,255,255,0.18)";
      ctx.lineWidth   = 1;
      ctx.setLineDash([3, 4]);
      ctx.beginPath();
      ctx.moveTo(dotX, PAD_T);
      ctx.lineTo(dotX, PAD_T + ch);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();

      // Dot bloom
      ctx.save();
      ctx.globalAlpha = 0.35;
      ctx.filter      = "blur(6px)";
      ctx.beginPath();
      ctx.arc(dotX, dotY, 8, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.filter = "none";
      ctx.restore();

      // Dot core
      ctx.save();
      ctx.beginPath();
      ctx.arc(dotX, dotY, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(dotX, dotY, 2, 0, Math.PI * 2);
      ctx.fillStyle = "#fff";
      ctx.fill();
      ctx.restore();

      // Tooltip
      const valStr   = `$${val.toFixed(2)}`;
      const pctStr   = `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
      const pctColor = pct >= 0 ? "#22C55E" : "#EF4444";
      const dateStr  = timestamps?.[idx]
        ? new Date(timestamps[idx]).toLocaleDateString("en-US", { month: "short", day: "numeric" })
        : null;

      ctx.save();
      ctx.font         = "700 9px/1 monospace";
      ctx.textBaseline = "middle";

      const valW  = ctx.measureText(valStr).width;
      const pctW  = ctx.measureText("  " + pctStr).width;
      const dateW = dateStr ? ctx.measureText(dateStr + "  ").width : 0;
      const boxW  = dateW + valW + pctW + 16;
      const boxH  = 20;

      let tx = dotX + 10;
      if (tx + boxW > w - PAD_R) tx = dotX - boxW - 10;
      tx = Math.max(PAD_L, tx);
      const ty = Math.max(PAD_T + 2, Math.min(dotY - boxH / 2, PAD_T + ch - boxH));

      ctx.fillStyle   = "rgba(4,6,10,0.92)";
      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      ctx.lineWidth   = 1;
      ctx.beginPath();
      ctx.roundRect?.(tx, ty, boxW, boxH, 2) ?? ctx.rect(tx, ty, boxW, boxH);
      ctx.fill();
      ctx.stroke();

      let cx = tx + 8;
      if (dateStr) {
        ctx.fillStyle = "rgba(255,255,255,0.35)";
        ctx.fillText(dateStr, cx, ty + boxH / 2);
        cx += dateW;
      }
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.fillText(valStr, cx, ty + boxH / 2);
      ctx.fillStyle = pctColor;
      ctx.fillText(pctStr, cx + valW + 6, ty + boxH / 2);
      ctx.restore();
    }
  }, [data, color, w, h, hoverIdx, toX, ch, timestamps]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const relX = e.clientX - rect.left;
    const frac = (relX - PAD_L) / (rect.width - PAD_L - PAD_R);
    setHoverIdx(Math.max(0, Math.min(data.length - 1, Math.round(frac * (data.length - 1)))));
  }, [data.length]);

  const handleMouseLeave = useCallback(() => setHoverIdx(null), []);

  return (
    <div ref={wrapRef} style={{ width: "100%", height: h }}>
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: h, display: "block", cursor: "crosshair" }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />
    </div>
  );
}
