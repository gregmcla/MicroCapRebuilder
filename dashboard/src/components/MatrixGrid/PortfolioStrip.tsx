/**
 * PortfolioStrip — compact proportional tile row replacing the card grid.
 * Tiles are sized proportionally to equity. Click a tile to filter the Matrix.
 */

import { useState, useEffect, useRef } from "react";
import type { PortfolioSummary } from "../../lib/types";
import type { MatrixPortfolio } from "./types";
import { play } from "../../lib/sounds";

interface ScanResult {
  status: "running" | "complete" | "error";
  added: number;
  active: number;
  error: string | null;
}

interface PortfolioStripProps {
  summaries: PortfolioSummary[];
  matrixPortfolios: MatrixPortfolio[];
  totalEquity: number;
  activeFilter: string | null;
  onFilter: (id: string | null) => void;
  onNavigate: (id: string) => void;
  scanResults: Record<string, ScanResult>;
  onUpdateAll: () => void;
  updatingAll: boolean;
  updateResult: string | null;
  onScanAll: () => void;
  scanAllRunning: boolean;
  scanAllLabel: string | null;
  onNewPortfolio: () => void;
  onDelete?: (id: string) => void;
}

function fmtCompact(v: number) {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}k`;
  return `$${v.toFixed(0)}`;
}

function fmtPct(v: number) {
  return `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
}

export default function PortfolioStrip({
  summaries,
  matrixPortfolios,
  totalEquity,
  activeFilter,
  onFilter,
  onNavigate,
  scanResults,
  onUpdateAll,
  updatingAll,
  updateResult,
  onScanAll,
  scanAllRunning,
  scanAllLabel,
  onNewPortfolio,
  onDelete,
}: PortfolioStripProps) {
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const colorMap = new Map(matrixPortfolios.map((p) => [p.id, p.color]));

  // Play scanComplete when scanAllRunning transitions from true → false
  const wasScanAllRunning = useRef(false);
  useEffect(() => {
    if (wasScanAllRunning.current && !scanAllRunning) play("scanComplete");
    wasScanAllRunning.current = scanAllRunning;
  }, [scanAllRunning]);
  const valid = summaries.filter((s) => !s.error);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "stretch",
        height: 52,
        flexShrink: 0,
        background: "#040608",
        borderBottom: "1px solid rgba(74,222,128,0.08)",
        overflow: "hidden",
      }}
    >
      {/* ALL tile */}
      <button
        onClick={() => onFilter(null)}
        style={{
          flexShrink: 0,
          width: 44,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: !activeFilter ? "rgba(74,222,128,0.06)" : "transparent",
          border: "none",
          borderRight: "1px solid rgba(74,222,128,0.06)",
          color: !activeFilter ? "#4ade80" : "#333",
          fontSize: 8,
          fontFamily: "'Azeret Mono', 'JetBrains Mono', monospace",
          fontWeight: 700,
          letterSpacing: "0.12em",
          cursor: "pointer",
          transition: "all 0.15s",
          boxShadow: !activeFilter ? "inset 0 -2px 0 #4ade80" : "none",
        }}
        onMouseEnter={(e) => {
          if (activeFilter !== null) e.currentTarget.style.color = "#4ade8066";
        }}
        onMouseLeave={(e) => {
          if (activeFilter !== null) e.currentTarget.style.color = "#333";
        }}
      >
        ALL
      </button>

      {/* Proportional portfolio tiles */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {valid.map((s) => {
          const color = colorMap.get(s.id) ?? "#4ade80";
          const pct = totalEquity > 0 ? (s.equity / totalEquity) * 100 : 100 / valid.length;
          const active = activeFilter === s.id;
          const ret = s.total_return_pct ?? 0;
          const dayUp = (s.day_pnl ?? 0) >= 0;
          const scanResult = scanResults[s.id];

          return (
            <div
              key={s.id}
              style={{
                flex: `${pct} 0 0`,
                minWidth: 72,
                position: "relative",
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                padding: "0 10px",
                background: active ? `${color}0d` : "transparent",
                borderRight: "1px solid rgba(255,255,255,0.03)",
                cursor: "pointer",
                transition: "background 0.15s",
                boxShadow: active ? `inset 0 -2px 0 ${color}` : "none",
                overflow: "hidden",
              }}
              onClick={() => onFilter(active ? null : s.id)}
              onDoubleClick={() => onNavigate(s.id)}
              onMouseEnter={(e) => {
                if (!active) (e.currentTarget as HTMLDivElement).style.background = `${color}07`;
              }}
              onMouseLeave={(e) => {
                if (!active) (e.currentTarget as HTMLDivElement).style.background = "transparent";
              }}
            >
              {/* Delete button */}
              {onDelete && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirmId === s.id) {
                      onDelete(s.id);
                      setConfirmId(null);
                    } else {
                      setConfirmId(s.id);
                    }
                  }}
                  onBlur={() => setConfirmId(null)}
                  style={{
                    position: "absolute", top: 4, right: 4, zIndex: 10,
                    background: "none", border: "none", padding: "1px 4px",
                    fontSize: 9, cursor: "pointer", lineHeight: 1,
                    color: confirmId === s.id ? "#f87171" : "transparent",
                    fontWeight: confirmId === s.id ? 700 : 400,
                    transition: "color 0.1s",
                  }}
                  onMouseEnter={(e) => {
                    if (confirmId !== s.id) e.currentTarget.style.color = "rgba(248,113,113,0.5)";
                  }}
                  onMouseLeave={(e) => {
                    if (confirmId !== s.id) e.currentTarget.style.color = "transparent";
                  }}
                >
                  {confirmId === s.id ? "del?" : "×"}
                </button>
              )}

              {/* Left accent bar */}
              <div style={{
                position: "absolute",
                left: 0, top: 6, bottom: 6,
                width: 2,
                background: color,
                opacity: active ? 0.9 : 0.2,
                borderRadius: "0 1px 1px 0",
                transition: "opacity 0.15s",
              }} />

              {/* Name row */}
              <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 1 }}>
                <span style={{
                  fontSize: 9,
                  fontFamily: "'Azeret Mono', monospace",
                  fontWeight: 700,
                  color: active ? color : "#888",
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  transition: "color 0.15s",
                  textShadow: active ? `0 0 12px ${color}55` : "none",
                }}>
                  {s.name}
                </span>
                {/* Scan indicator */}
                {scanResult && (
                  <span style={{
                    width: 4, height: 4, borderRadius: "50%", flexShrink: 0,
                    background: scanResult.status === "complete" ? "#4ade80"
                      : scanResult.status === "error" ? "#f87171" : "#fbbf24",
                    animation: scanResult.status === "running" ? "pulse 1s ease-in-out infinite" : "none",
                  }} />
                )}
              </div>

              {/* Value + return row */}
              <div style={{ display: "flex", alignItems: "baseline", gap: 5 }}>
                <span style={{
                  fontSize: 11,
                  fontFamily: "'Azeret Mono', monospace",
                  fontWeight: 600,
                  color: active ? "#e8ffe8" : "#555",
                  transition: "color 0.15s",
                }}>
                  {fmtCompact(s.equity)}
                </span>
                <span style={{
                  fontSize: 8,
                  fontFamily: "'Azeret Mono', monospace",
                  fontWeight: 600,
                  color: ret >= 0 ? "#4ade8099" : "#f8717199",
                }}>
                  {fmtPct(ret)}
                </span>
              </div>

              {/* Day-direction bar at very bottom */}
              <div style={{
                position: "absolute",
                left: 0, right: 0, bottom: 0,
                height: 2,
                background: dayUp ? "rgba(74,222,128,0.35)" : "rgba(248,113,113,0.35)",
              }} />
            </div>
          );
        })}
      </div>

      {/* Action buttons */}
      <div style={{
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "0 12px",
        borderLeft: "1px solid rgba(74,222,128,0.06)",
      }}>
        <ActionBtn
          onClick={() => { play("update"); onUpdateAll(); }}
          disabled={updatingAll}
          spinning={updatingAll}
          label={updateResult ?? "Update All"}
        />
        <ActionBtn
          onClick={() => { play("scan"); onScanAll(); }}
          disabled={scanAllRunning}
          pulse={scanAllRunning}
          label={scanAllLabel ?? "Scan All"}
        />
        <ActionBtn onClick={onNewPortfolio} label="+ New" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tiny action button
// ---------------------------------------------------------------------------
function ActionBtn({
  onClick,
  disabled,
  spinning,
  pulse,
  label,
}: {
  onClick: () => void;
  disabled?: boolean;
  spinning?: boolean;
  pulse?: boolean;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "0 9px",
        height: 22,
        background: "transparent",
        border: "1px solid rgba(255,255,255,0.06)",
        borderRadius: 4,
        color: disabled ? "#4ade80" : "#555",
        fontSize: 8,
        fontFamily: "'Azeret Mono', monospace",
        fontWeight: 700,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "border-color 0.15s, color 0.15s",
        opacity: disabled ? 0.75 : 1,
        whiteSpace: "nowrap",
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.borderColor = "#4ade8066";
          e.currentTarget.style.color = "#4ade80";
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled) {
          e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)";
          e.currentTarget.style.color = "#555";
        }
      }}
    >
      {spinning && (
        <svg width="8" height="8" viewBox="0 0 12 12" fill="none" className="animate-spin" style={{ flexShrink: 0 }}>
          <path d="M10 6A4 4 0 1 1 6 2a4 4 0 0 1 2.83 1.17L10 2v4H6"
            stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
      {pulse && (
        <span style={{
          width: 4, height: 4, borderRadius: "50%",
          background: "currentColor",
          animation: "pulse 1s ease-in-out infinite",
          flexShrink: 0,
        }} />
      )}
      {label}
    </button>
  );
}
