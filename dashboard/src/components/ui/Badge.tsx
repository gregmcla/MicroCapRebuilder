/** Badge — small colored label.
 *  Use for: heat (HOT/SPIKING/WARM), source labels, AI-driven flag, status
 *  pills, regime indicators. NOT for data callouts that need glow + border
 *  (those are specialized renders in MatrixGrid).
 *
 *  Color comes from `tone` (semantic) + `variant` (fill style). Width and
 *  height come from `size`. The defaults match the most common pattern in
 *  the dashboard: `tone="neutral" variant="soft" size="xs"`.
 *  @category Data
 */

import type { CSSProperties, ReactNode } from "react";

export type BadgeTone =
  | "profit"   // green — gains, healthy, BULL
  | "loss"     // red — losses, danger, BEAR, SPIKING heat
  | "warning"  // amber — caution, WARM heat
  | "accent"   // violet — AI-driven, brand emphasis
  | "neutral"  // gray — defaults
  | "info";    // cyan — informational, secondary accent
export type BadgeVariant = "filled" | "soft" | "outline";
export type BadgeSize = "xs" | "sm";

export interface BadgeProps {
  tone?: BadgeTone;
  variant?: BadgeVariant;
  size?: BadgeSize;
  /** When true, applies a slow CSS pulse (used for SPIKING heat). */
  pulse?: boolean;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}

// Token-mapped sources for tone colors. Comes from semantic CSS vars so the
// Badge follows theme changes; orange (HOT) doesn't have a token in the
// dashboard's @theme so it falls back to a literal — matches what ActionsTab
// already uses today.
function toneColors(tone: BadgeTone): { text: string; bg: string; border: string } {
  switch (tone) {
    case "profit":  return { text: "var(--color-profit)", bg: "var(--color-profit-dim)", border: "rgba(52,211,153,0.30)" };
    case "loss":    return { text: "var(--color-loss)",   bg: "var(--color-loss-dim)",   border: "rgba(248,113,113,0.35)" };
    case "warning": return { text: "var(--color-warning)", bg: "var(--color-warning-dim)", border: "rgba(251,191,36,0.30)" };
    case "accent":  return { text: "var(--color-accent-bright)", bg: "var(--color-accent-dim)", border: "var(--color-accent-border)" };
    case "info":    return { text: "var(--color-accent-cyan)", bg: "rgba(92,224,214,0.12)", border: "rgba(92,224,214,0.25)" };
    case "neutral":
    default:        return { text: "var(--color-text-secondary)", bg: "rgba(255,255,255,0.06)", border: "var(--color-border-1)" };
  }
}

function sizeStyles(size: BadgeSize): CSSProperties {
  return size === "sm"
    ? { fontSize: "10px", padding: "2px 6px", borderRadius: "4px", letterSpacing: "0.05em", fontWeight: 600 }
    : { fontSize: "9px",  padding: "1px 5px", borderRadius: "3px", letterSpacing: "0.06em", fontWeight: 600 };
}

export function Badge({
  tone = "neutral",
  variant = "soft",
  size = "xs",
  pulse = false,
  className,
  style,
  children,
}: BadgeProps) {
  const tc = toneColors(tone);
  const base: CSSProperties = {
    ...sizeStyles(size),
    display: "inline-block",
    whiteSpace: "nowrap",
    ...(variant === "filled"
      ? { background: tc.text, color: "#0a0a0b" }
      : variant === "outline"
        ? { background: "transparent", color: tc.text, border: `1px solid ${tc.border}` }
        : { background: tc.bg, color: tc.text }),
  };
  return (
    <span
      className={[pulse ? "animate-pulse" : "", className].filter(Boolean).join(" ") || undefined}
      style={{ ...base, ...style }}
    >
      {children}
    </span>
  );
}

// ── Specialized helpers ────────────────────────────────────────────────────

/** Maps social-heat strings to badge tone. SPIKING gets a pulse. */
const HEAT_TONE: Record<string, { tone: BadgeTone; pulse?: boolean }> = {
  WARM:    { tone: "warning" },
  HOT:     { tone: "warning", pulse: false }, // tonally orange, but warning is closest semantic
  SPIKING: { tone: "loss", pulse: true },
};

export interface HeatBadgeProps {
  /** Social heat enum. `undefined`, `""`, or `"COLD"` render nothing. */
  heat?: string | null;
  size?: BadgeSize;
}

/** Watchlist social-heat badge. Renders nothing when heat is cold/absent. */
export function HeatBadge({ heat, size = "xs" }: HeatBadgeProps) {
  if (!heat || heat === "COLD") return null;
  const mapping = HEAT_TONE[heat];
  if (!mapping) return null;
  // HOT gets an orange-only render (no semantic token for orange — keep the
  // ActionsTab literal so the visual doesn't shift).
  if (heat === "HOT") {
    return (
      <Badge
        size={size}
        style={{ color: "#f97316", background: "rgba(249,115,22,0.12)" }}
      >
        {heat}
      </Badge>
    );
  }
  return (
    <Badge tone={mapping.tone} size={size} pulse={mapping.pulse}>
      {heat}
    </Badge>
  );
}

const REGIME_TONE: Record<string, BadgeTone> = {
  BULL: "profit",
  BEAR: "loss",
  SIDEWAYS: "neutral",
};

export interface RegimeBadgeProps {
  regime?: string | null;
  size?: BadgeSize;
}

/** Market regime badge. Renders nothing for unknown values. */
export function RegimeBadge({ regime, size = "xs" }: RegimeBadgeProps) {
  if (!regime) return null;
  const tone = REGIME_TONE[regime.toUpperCase()];
  if (!tone) return null;
  return (
    <Badge tone={tone} size={size}>
      {regime.toUpperCase()}
    </Badge>
  );
}

/** Source-label badge for watchlist candidates. */
export interface SourceBadgeProps {
  source: string;
  /** Optional label override map (e.g. SOURCE_LABELS in ActionsTab). */
  labels?: Record<string, string>;
  size?: BadgeSize;
}

export function SourceBadge({ source, labels, size = "xs" }: SourceBadgeProps) {
  const label = labels?.[source] ?? source.slice(0, 3).toUpperCase();
  return (
    <Badge tone="accent" size={size}>
      {label}
    </Badge>
  );
}

/** "AI" pill for AI-driven portfolios / proposals. */
export function AiDrivenBadge({ size = "xs" }: { size?: BadgeSize }) {
  return (
    <Badge tone="accent" size={size} variant="soft">
      AI
    </Badge>
  );
}

export default Badge;
