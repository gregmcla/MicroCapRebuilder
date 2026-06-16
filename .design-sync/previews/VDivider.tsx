import { VDivider } from "dashboard";

const sectionLabel = {
  fontFamily: "var(--font-sans, system-ui)",
  fontSize: "10px",
  letterSpacing: "0.08em",
  textTransform: "uppercase" as const,
  color: "var(--color-text-muted, rgba(255,255,255,0.6))",
};
const sectionValue = {
  fontFamily: "var(--font-mono, ui-monospace)",
  fontSize: "13px",
  color: "var(--color-text-2, white)",
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
      <span style={sectionLabel}>{label}</span>
      <span style={sectionValue}>{value}</span>
    </div>
  );
}

/** Live default — VDivider sitting between three TopBar-style readouts. */
export function Default() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: 16,
        background: "var(--color-bg-elevated, #141416)",
        borderRadius: 8,
      }}
    >
      <Row label="Equity" value="$142,318" />
      <VDivider />
      <Row label="Day P&amp;L" value="+$1,204" />
      <VDivider />
      <Row label="Regime" value="BULL" />
    </div>
  );
}
