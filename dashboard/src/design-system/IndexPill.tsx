export interface IndexPillProps {
  /** Short label, e.g. "S&P", "RUT", "VIX". */
  label: string;
  /** Current index value. */
  value: number;
  /** Day percent change, e.g. -0.42. */
  changePct: number;
  /** When true, sentiment inverts and label/value render in amber. */
  isVix?: boolean;
}

/** Compact market-index readout: label, value, percent change.
 *  Sentiment colors invert when `isVix` is true (rising VIX = fear = red).
 *  @category Data
 */
export function IndexPill({ label, value, changePct, isVix }: IndexPillProps) {
  const up = changePct >= 0;
  const color = isVix
    ? (up ? "var(--loss)" : "var(--profit)")
    : (up ? "var(--profit)" : "var(--loss)");
  return (
    <div className="flex items-baseline gap-1.5 px-3">
      <span
        style={{
          fontSize: "9px",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: isVix ? "var(--amber)" : "var(--color-text-muted)",
          fontFamily: "var(--font-sans)",
        }}
      >
        {label}
      </span>
      <span
        className="font-mono tabular-nums"
        style={{
          fontSize: "12px",
          color: isVix ? "rgba(251,191,36,0.65)" : "var(--color-text-2)",
          letterSpacing: "-0.01em",
        }}
      >
        {value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
      <span
        className="font-mono tabular-nums font-semibold"
        style={{ fontSize: "10px", color }}
      >
        {up ? "+" : ""}{changePct.toFixed(2)}%
      </span>
    </div>
  );
}

export default IndexPill;
