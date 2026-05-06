/**
 * Pure presentational sub-components extracted from OverviewPage (Fix 18).
 *
 * Each function takes props and returns JSX. No hooks (except useMemo for
 * derived values), no context, no store access. Safe to render anywhere.
 */
import { useMemo } from "react";

export function EquitySparkline({
  values,
  returnPct,
  id,
}: {
  values: number[];
  returnPct: number;
  id: string;
}) {
  const W = 200;
  const H = 36;
  const points = useMemo(() => {
    if (values.length < 2) return "";
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    return values
      .map((v, i) => {
        const x = (i / (values.length - 1)) * W;
        const y = H - 1 - ((v - min) / range) * (H - 4);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [values]);

  if (!points) return null;
  const up = returnPct >= 0;
  const color = up ? "var(--green)" : "var(--red)";
  const gradId = `sparkgrad-${id}`;

  return (
    <svg
      width="100%"
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      style={{ display: "block" }}
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.22" />
          <stop offset="100%" stopColor={color} stopOpacity="0.01" />
        </linearGradient>
      </defs>
      <polygon points={`0,${H} ${points} ${W},${H}`} fill={`url(#${gradId})`} />
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.9"
      />
    </svg>
  );
}

export function SideHeader({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: "9px",
        textTransform: "uppercase",
        letterSpacing: "0.10em",
        color: "var(--text-0)",
        fontWeight: 700,
        paddingBottom: "6px",
        borderBottom: "1px solid var(--border-0)",
      }}
    >
      {children}
    </div>
  );
}

export function LoadingPane({ text }: { text: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "300px",
        color: "var(--text-1)",
        fontSize: "12px",
      }}
    >
      {text}
    </div>
  );
}

export function SkeletonBlock({
  width,
  height,
  style,
}: {
  width: number | string;
  height: number;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className="animate-pulse-slow"
      style={{
        width: typeof width === "number" ? `${width}px` : width,
        height: `${height}px`,
        borderRadius: "5px",
        background: "var(--surface-3)",
        flexShrink: 0,
        ...style,
      }}
    />
  );
}
