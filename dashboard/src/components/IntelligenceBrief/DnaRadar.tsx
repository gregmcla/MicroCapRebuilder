/** DNA Radar — SVG 8-axis radar with stated (dashed outline) + measured
 * (filled polygon) overlay. Hand-rolled SVG; follows the polygon-sparkline
 * pattern used elsewhere in the codebase.
 */

import type { DnaGenome, DnaAxis } from "../../lib/types";
import { DNA_AXES } from "../../lib/types";

interface Props {
  stated: DnaGenome;
  measured: DnaGenome;
  drift: Record<DnaAxis, number>;
  size?: number;             // px, square
  showLabels?: boolean;
  showValues?: boolean;
}

const AXIS_LABELS: Record<DnaAxis, string> = {
  time_horizon: "Time horizon",
  aggression: "Aggression",
  concentration: "Concentration",
  regime_sensitivity: "Regime sense",
  momentum_bias: "Momentum",
  quality_bias: "Quality",
  catalyst_hunting: "Catalyst",
  drawdown_discipline: "Discipline",
};

export default function DnaRadar({
  stated,
  measured,
  drift,
  size = 480,
  showLabels = true,
  showValues = true,
}: Props) {
  const cx = size / 2;
  const cy = size / 2;
  const radius = (size / 2) * 0.62;        // leave room for labels
  const angles = DNA_AXES.map((_, i) => (i / DNA_AXES.length) * Math.PI * 2 - Math.PI / 2);

  // Convert a genome into N polygon vertices
  const genomePoints = (g: DnaGenome): string =>
    DNA_AXES.map((axis, i) => {
      const v = (g[axis] as number) ?? 0;
      const r = (v / 100) * radius;
      const x = cx + Math.cos(angles[i]) * r;
      const y = cy + Math.sin(angles[i]) * r;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");

  // Grid rings (25/50/75/100)
  const rings = [25, 50, 75, 100];

  return (
    <svg viewBox={`0 0 ${size} ${size}`} style={{ width: "100%", height: "auto" }}>
      <defs>
        <radialGradient id="dnaGrad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#7c5cfc" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#7c5cfc" stopOpacity="0.1" />
        </radialGradient>
      </defs>

      {/* Grid rings */}
      {rings.map((pct) => (
        <circle
          key={pct}
          cx={cx}
          cy={cy}
          r={(pct / 100) * radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="1"
        />
      ))}

      {/* Axes (radial lines) */}
      {DNA_AXES.map((_, i) => {
        const x2 = cx + Math.cos(angles[i]) * radius;
        const y2 = cy + Math.sin(angles[i]) * radius;
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={x2}
            y2={y2}
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="1"
          />
        );
      })}

      {/* Stated polygon: dashed outline, no fill */}
      <polygon
        points={genomePoints(stated)}
        fill="none"
        stroke="#fbbf24"
        strokeWidth="1.5"
        strokeDasharray="4 3"
        opacity="0.9"
      />

      {/* Measured polygon: filled, semi-opaque */}
      <polygon
        points={genomePoints(measured)}
        fill="url(#dnaGrad)"
        stroke="#a78bfa"
        strokeWidth="2"
        fillOpacity="0.45"
      />

      {/* Axis labels + drift indicators around the perimeter */}
      {showLabels && DNA_AXES.map((axis, i) => {
        const labelR = radius + 28;
        const x = cx + Math.cos(angles[i]) * labelR;
        const y = cy + Math.sin(angles[i]) * labelR;
        // Anchor based on angle so labels read left/center/right naturally
        const cos = Math.cos(angles[i]);
        const anchor = cos > 0.3 ? "start" : cos < -0.3 ? "end" : "middle";
        const driftV = drift[axis] ?? 0;
        const driftAbs = Math.abs(driftV);
        return (
          <g key={axis}>
            <text
              x={x}
              y={y}
              fontSize="10"
              fill="#a0a0c0"
              textAnchor={anchor}
              fontFamily="'JetBrains Mono', monospace"
              dominantBaseline="middle"
            >
              {AXIS_LABELS[axis]}
            </text>
            {showValues && (
              <text
                x={x}
                y={y + 12}
                fontSize="9"
                fill="#7c5cfc"
                textAnchor={anchor}
                fontFamily="'JetBrains Mono', monospace"
                dominantBaseline="middle"
              >
                {(measured[axis] as number).toFixed(0)}
                {driftAbs >= 10 && (
                  <tspan
                    fill={driftV > 0 ? "#f87171" : "#34d399"}
                    fontSize="8"
                    dx="4"
                  >
                    {driftV > 0 ? "↓" : "↑"}{driftAbs.toFixed(0)}
                  </tspan>
                )}
              </text>
            )}
          </g>
        );
      })}

      {/* Center label */}
      <text
        x={cx}
        y={cy - 4}
        fontSize="8"
        fill="#5a5a78"
        textAnchor="middle"
        fontFamily="'JetBrains Mono', monospace"
        letterSpacing="0.1em"
      >
        DNA
      </text>
    </svg>
  );
}
