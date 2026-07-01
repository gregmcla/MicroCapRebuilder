/** Shared loading / error states for Intelligence Brief tabs.
 *  Prevents the "stuck on Loading… forever" bug when a fetch errors: tabs
 *  render <PanelError> with a Retry instead of an eternal loading string. */

const FONT = "'JetBrains Mono', 'SF Mono', monospace";

export function PanelLoading({ label }: { label: string }) {
  return (
    <div style={{ padding: "24px", color: "#5a5a78", fontFamily: FONT, fontSize: "12px", letterSpacing: "0.06em" }}>
      {label}
    </div>
  );
}

export function PanelError({
  label = "Couldn’t load this panel",
  detail,
  onRetry,
}: {
  label?: string;
  detail?: string;
  onRetry?: () => void;
}) {
  return (
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "10px", alignItems: "flex-start" }}>
      <div style={{ fontSize: "12px", color: "#f87171", fontFamily: FONT, fontWeight: 600 }}>{label}</div>
      {detail && (
        <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.42)", maxWidth: "480px", lineHeight: 1.5 }}>
          {detail}
        </div>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            marginTop: "2px",
            fontSize: "11px",
            fontWeight: 600,
            color: "#c8bcff",
            background: "rgba(124,92,252,0.12)",
            border: "1px solid rgba(124,92,252,0.3)",
            borderRadius: "6px",
            padding: "5px 12px",
            cursor: "pointer",
          }}
        >
          Retry
        </button>
      )}
    </div>
  );
}
