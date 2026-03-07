import { useRef, useEffect, useState, useCallback } from "react";

interface InteractiveSparklineProps {
  data: number[];   // raw price / equity values
  color: string;
  w?: number;
  h?: number;
}

const PAD_T = 8;
const PAD_B = 8;
const PAD_L = 4;
const PAD_R = 4;

export default function InteractiveSparkline({ data, color, w = 340, h = 72 }: InteractiveSparklineProps) {
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const cw = w - PAD_L - PAD_R;
  const ch = h - PAD_T - PAD_B;

  const px = useCallback((i: number) => PAD_L + (i / Math.max(data.length - 1, 1)) * cw, [data.length, cw]);
  const py = useCallback((v: number, mn: number, rg: number) => PAD_T + ((Math.max(...data) - v) / rg) * ch, [data, ch]);

  // Single effect: resize + draw whenever any dep changes (including hoverIdx)
  useEffect(() => {
    const c = canvasRef.current;
    if (!c || data.length < 2) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    c.width  = w * dpr;
    c.height = h * dpr;
    const ctx = c.getContext("2d")!;
    ctx.scale(dpr, dpr);

    const mn  = Math.min(...data);
    const mx  = Math.max(...data);
    const rg  = mx - mn || 1;
    const toY = (v: number) => PAD_T + ((mx - v) / rg) * ch;
    const toX = (i: number) => px(i);

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

      // Dot core (portfolio color ring + white centre)
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
      const valStr = val >= 1000
        ? `$${(val / 1000).toFixed(1)}k`
        : `$${val.toFixed(2)}`;
      const pctStr  = `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
      const pctColor = pct >= 0 ? "#4ade80" : "#f87171";

      ctx.save();
      ctx.font         = "700 9px/1 monospace";
      ctx.textBaseline = "middle";

      const valW  = ctx.measureText(valStr).width;
      const pctW  = ctx.measureText("  " + pctStr).width;
      const boxW  = valW + pctW + 16;
      const boxH  = 20;

      // Position: prefer right of cursor, flip left near edge
      let tx = dotX + 10;
      if (tx + boxW > w - PAD_R) tx = dotX - boxW - 10;
      tx = Math.max(PAD_L, tx);
      const ty = Math.max(PAD_T + 2, Math.min(dotY - boxH / 2, PAD_T + ch - boxH));

      // Card background
      ctx.fillStyle   = "rgba(4,6,10,0.92)";
      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      ctx.lineWidth   = 1;
      ctx.beginPath();
      ctx.roundRect?.(tx, ty, boxW, boxH, 2) ?? ctx.rect(tx, ty, boxW, boxH);
      ctx.fill();
      ctx.stroke();

      // Values
      ctx.textAlign = "left";
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.fillText(valStr, tx + 8, ty + boxH / 2);
      ctx.fillStyle = pctColor;
      ctx.fillText(pctStr, tx + 8 + valW + 6, ty + boxH / 2);
      ctx.restore();
    }
  }, [data, color, w, h, hoverIdx, px, ch]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const relX = e.clientX - rect.left;
    // Convert CSS pixel → data index
    const frac = (relX - PAD_L) / (rect.width - PAD_L - PAD_R);
    const idx  = Math.round(frac * (data.length - 1));
    setHoverIdx(Math.max(0, Math.min(data.length - 1, idx)));
  }, [data.length]);

  const handleMouseLeave = useCallback(() => setHoverIdx(null), []);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: w, height: h, display: "block", cursor: "crosshair" }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    />
  );
}
