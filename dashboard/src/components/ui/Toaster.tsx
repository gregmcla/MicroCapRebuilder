/** Global toast stack — mounted once in App, top-right, above all modals.
 *  Purely visual feedback; sounds stay at their existing call sites. */

import { useEffect } from "react";
import { useToastStore, type Toast, type ToastKind } from "../../lib/toastStore";

const KIND_COLOR: Record<ToastKind, string> = {
  success: "var(--green)",
  error: "var(--red)",
  info: "var(--accent)",
  warning: "var(--amber)",
};

function Icon({ kind }: { kind: ToastKind }) {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: KIND_COLOR[kind],
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  switch (kind) {
    case "success":
      return (<svg {...common}><path d="M20 6 9 17l-5-5" /></svg>);
    case "error":
      return (<svg {...common}><circle cx="12" cy="12" r="9" /><path d="M15 9l-6 6M9 9l6 6" /></svg>);
    case "warning":
      return (<svg {...common}><path d="M12 3l9 16H3z" /><path d="M12 10v4M12 17h.01" /></svg>);
    default:
      return (<svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 16v-4M12 8h.01" /></svg>);
  }
}

function ToastRow({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss);

  useEffect(() => {
    if (!toast.duration) return;
    const t = setTimeout(() => dismiss(toast.id), toast.duration);
    return () => clearTimeout(t);
  }, [toast.id, toast.duration, dismiss]);

  const color = KIND_COLOR[toast.kind];

  return (
    <div
      role="status"
      aria-live={toast.kind === "error" ? "assertive" : "polite"}
      className="gscott-toast"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "10px",
        width: "340px",
        maxWidth: "calc(100vw - 32px)",
        padding: "11px 12px",
        background: "var(--surface-2)",
        border: "1px solid var(--border-2)",
        borderLeft: `3px solid ${color}`,
        borderRadius: "var(--radius-sm)",
        boxShadow: "0 8px 28px rgba(0,0,0,0.45)",
        pointerEvents: "auto",
      }}
    >
      <span style={{ flexShrink: 0, marginTop: "1px" }}>
        <Icon kind={toast.kind} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-4)", lineHeight: 1.35 }}>
          {toast.title}
        </div>
        {toast.detail && (
          <div style={{ fontSize: "11px", color: "var(--text-1)", lineHeight: 1.45, marginTop: "2px", wordBreak: "break-word" }}>
            {toast.detail}
          </div>
        )}
        {toast.action && (
          <button
            onClick={() => {
              toast.action!.onClick();
              dismiss(toast.id);
            }}
            style={{
              marginTop: "7px",
              fontSize: "11px",
              fontWeight: 600,
              color,
              background: "transparent",
              border: "none",
              padding: 0,
              cursor: "pointer",
            }}
          >
            {toast.action.label}
          </button>
        )}
      </div>
      <button
        onClick={() => dismiss(toast.id)}
        aria-label="Dismiss notification"
        style={{
          flexShrink: 0,
          background: "transparent",
          border: "none",
          color: "var(--text-0)",
          cursor: "pointer",
          fontSize: "14px",
          lineHeight: 1,
          padding: "2px",
        }}
      >
        ×
      </button>
    </div>
  );
}

export default function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  if (toasts.length === 0) return null;
  return (
    <div
      style={{
        position: "fixed",
        top: "56px",
        right: "16px",
        zIndex: 10000,
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        pointerEvents: "none",
      }}
    >
      {toasts.map((t) => (
        <ToastRow key={t.id} toast={t} />
      ))}
    </div>
  );
}
