import { useRef, useEffect } from "react";

interface WaveformProps {
  width?: number;
  height?: number;
}

export default function Waveform({ width = 160, height = 16 }: WaveformProps) {
  const ref = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const d = 2;
    c.width = width * d;
    c.height = height * d;
    const ctx = c.getContext("2d")!;
    let t = 0;

    const draw = () => {
      frameRef.current = requestAnimationFrame(draw);
      ctx.save();
      ctx.scale(d, d);
      ctx.clearRect(0, 0, width, height);
      t += 0.03;
      const bars = 40;
      const bw = width / bars;
      for (let i = 0; i < bars; i++) {
        const h2 =
          (Math.sin(t + i * 0.3) * 0.5 + 0.5) *
          (Math.sin(t * 1.7 + i * 0.15) * 0.5 + 0.5) *
          height * 0.8 + 1;
        ctx.fillStyle = `rgba(74,222,128,${0.1 + (h2 / height) * 0.25})`;
        ctx.fillRect(i * bw + 1, (height - h2) / 2, bw - 2, h2);
      }
      ctx.restore();
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameRef.current);
  }, [width, height]);

  return <canvas ref={ref} style={{ width, height, display: "block", opacity: 0.6 }} />;
}
