/** Portfolio Intelligence Brief — redesigned full-screen modal. */

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { IntelligenceBriefData } from "../../lib/types";
import { usePortfolioState } from "../../hooks/usePortfolioState";

// Section components
import DnaCard from "./DnaCard";
import TradeIntelligence from "./TradeIntelligence";
import CompositionPanel from "./CompositionPanel";
import RiskPulse from "./RiskPulse";
import FactorIntelligence from "./FactorIntelligence";
import AuditChat from "./AuditChat";
import TradesTab from "./TradesTab";

const FONT = "var(--font-mono)";

interface Props {
  portfolioId: string;
  portfolioName: string;
  initialTab?: string;
  initialTradeId?: string | null;
  onClose: () => void;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmt(v: number | null | undefined, decimals = 1, suffix = ""): string {
  if (v == null || Number.isNaN(v)) return "\u2014";
  return v.toFixed(decimals) + suffix;
}

function gradeColor(grade: string): string {
  if (grade.startsWith("A")) return "var(--green)";
  if (grade.startsWith("B")) return "#60a5fa";
  if (grade.startsWith("C")) return "var(--amber)";
  if (grade.startsWith("D") || grade.startsWith("F")) return "var(--red)";
  return "var(--text-dim)";
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "var(--red)",
  high: "#f97316",
  medium: "var(--amber)",
  info: "#60a5fa",
  low: "#60a5fa",
};

function SectionHeader({ label, color }: { label: string; color?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px" }}>
      <span
        style={{
          fontSize: "10px",
          fontFamily: "var(--font-sans)",
          fontWeight: 600,
          letterSpacing: "0.1em",
          color: color ?? "var(--text-dim)",
          textTransform: "uppercase" as const,
          whiteSpace: "nowrap" as const,
        }}
      >
        {label}
      </span>
      <div
        style={{
          flex: 1,
          height: "1px",
          background: "linear-gradient(90deg, var(--border) 0%, transparent 100%)",
        }}
      />
    </div>
  );
}

// ── Sparkline (inline SVG) ───────────────────────────────────────────────────

function Sparkline({ data }: { data: number[] }) {
  if (data.length < 3) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span
          style={{
            fontSize: "10px",
            letterSpacing: "0.15em",
            color: "rgba(255,255,255,0.2)",
          }}
        >
          ACCUMULATING HISTORY
        </span>
      </div>
    );
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 100;
  const h = 100;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x},${y}`;
  });
  const polyline = points.join(" ");
  const fillPoints = `0,${h} ${polyline} ${w},${h}`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
      <defs>
        <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(139,92,246,0.15)" />
          <stop offset="100%" stopColor="transparent" />
        </linearGradient>
      </defs>
      <polygon points={fillPoints} fill="url(#sparkGrad)" />
      <polyline points={polyline} fill="none" stroke="var(--accent)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

// ── Mini Risk Pulse (Performance tab bottom row) ─────────────────────────────

function MiniRiskPulse({ brief }: { brief?: IntelligenceBriefData }) {
  const score = brief?.risk?.overall_score ?? 0;
  const nearStop = brief?.positions_near_stop ?? [];
  const borderColor = score <= 30 ? "var(--green)" : score <= 60 ? "var(--amber)" : "var(--red)";

  return (
    <div
      style={{
        padding: "16px",
        borderRadius: "8px",
        background: "var(--bg-elevated)",
        border: "1px solid var(--border)",
        borderLeft: `3px solid ${borderColor}`,
      }}
    >
      <SectionHeader label="RISK SCORE" />
      <div style={{ display: "flex", alignItems: "baseline", gap: "12px" }}>
        <span
          style={{
            fontSize: "28px",
            fontFamily: FONT,
            fontWeight: 700,
            color: borderColor,
          }}
        >
          {score}
        </span>
        <span
          style={{
            fontSize: "10px",
            fontFamily: "system-ui",
            fontWeight: 500,
            letterSpacing: "0.08em",
            color: "var(--text-dim)",
            textTransform: "uppercase" as const,
          }}
        >
          / 100
        </span>
      </div>
      {nearStop.length > 0 && (
        <span
          style={{
            display: "inline-block",
            marginTop: "8px",
            fontSize: "10px",
            fontWeight: 600,
            letterSpacing: "0.06em",
            color: "#f97316",
            padding: "3px 8px",
            borderRadius: "999px",
            background: "var(--amber-dim)",
            border: "1px solid rgba(245,158,11,0.3)",
          }}
        >
          {nearStop.length} NEAR STOP
        </span>
      )}
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function IntelligenceBrief({ portfolioId, portfolioName, initialTab, initialTradeId, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<"performance" | "risk" | "factors" | "gscott" | "trades">(
    (initialTab as "performance" | "risk" | "factors" | "gscott" | "trades") ?? "performance"
  );
  const [closeHover, setCloseHover] = useState(false);
  const { data: state } = usePortfolioState();

  const { data: brief, isLoading } = useQuery({
    queryKey: ["intelligence-brief", portfolioId],
    queryFn: () => api.getIntelligenceBrief(portfolioId),
    staleTime: 5 * 60_000,
  });

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Prevent body scroll
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  const snapshots =
    brief?.snapshots ??
    state?.snapshots?.map((s) => ({
      date: s.date,
      total_equity: s.total_equity,
      day_pnl_pct: s.day_pnl_pct,
    })) ??
    [];

  // Derived values
  const grade = brief?.health?.grade ?? "?";
  const gc = gradeColor(grade);
  const regime = brief?.regime ?? null;
  const totalReturn = brief?.total_return_pct ?? brief?.metrics?.total_return_pct ?? null;
  const sharpe = brief?.metrics?.sharpe_ratio ?? null;
  const maxDD = brief?.metrics?.max_drawdown_pct ?? null;
  const alpha = brief?.metrics?.alpha_pct ?? null;
  const warnings = brief?.warnings ?? [];
  const recommendations = brief?.health?.recommendations ?? [];
  const equityCurve = snapshots.map((s) => s.total_equity);

  const tabs = [
    { key: "performance" as const, label: "PERFORMANCE", dot: null },
    {
      key: "risk" as const,
      label: "RISK",
      dot: (brief?.risk?.overall_score ?? 0) > 65 ? "var(--red)" : null,
    },
    { key: "factors" as const, label: "FACTORS", dot: null },
    { key: "gscott" as const, label: "GSCOTT", dot: "var(--accent)" },
    { key: "trades" as const, label: "TRADES", dot: null },
  ];

  return (
    <>
      <style>{shimmerStyle}</style>

      {/* Backdrop */}
      <div
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 9999,
          background: "rgba(2,6,23,0.94)",
          backdropFilter: "blur(48px) saturate(160%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget) onClose();
        }}
      >
        {/* Modal container */}
        <div
          style={{
            width: "min(1400px, calc(100vw - 48px))",
            height: "calc(100vh - 48px)",
            background: "var(--bg-surface)",
            border: "1px solid rgba(139,92,246,0.18)",
            borderRadius: "var(--radius-lg)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            boxShadow:
              "0 0 0 1px rgba(139,92,246,0.08), 0 48px 96px rgba(0,0,0,0.85), 0 0 160px rgba(139,92,246,0.05)",
            position: "relative",
          }}
        >
          {/* ── Header Zone (80px) ─────────────────────────────────────── */}
          <div
            style={{
              height: "80px",
              flexShrink: 0,
              padding: "0 24px",
              display: "flex",
              alignItems: "center",
              borderBottom: "1px solid var(--border)",
              background: "linear-gradient(180deg, rgba(139,92,246,0.06) 0%, transparent 100%)",
            }}
          >
            {/* Left group: grade + name + regime */}
            <div style={{ display: "flex", alignItems: "center" }}>
              <div style={{ marginRight: "16px" }}>
                <span
                  style={{
                    fontSize: "44px",
                    fontFamily: FONT,
                    fontWeight: 700,
                    lineHeight: 1,
                    letterSpacing: "-0.04em",
                    color: gc,
                    textShadow: `0 0 16px ${gc}99`,
                  }}
                >
                  {grade}
                </span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span
                  style={{
                    fontSize: "15px",
                    fontFamily: "var(--font-mono)",
                    fontWeight: 600,
                    letterSpacing: "0.04em",
                    color: "var(--text-primary)",
                    textShadow: "0 0 20px rgba(139,92,246,0.4)",
                  }}
                >
                  {portfolioName}
                </span>
                {regime && (
                  <span
                    style={{
                      display: "inline-block",
                      width: "fit-content",
                      fontSize: "10px",
                      fontFamily: "system-ui",
                      fontWeight: 600,
                      letterSpacing: "0.08em",
                      borderRadius: "999px",
                      padding: "3px 10px",
                      border: "1px solid",
                      ...(regime === "BULL"
                        ? {
                            color: "var(--green)",
                            borderColor: "rgba(34,197,94,0.4)",
                            background: "var(--green-dim)",
                          }
                        : regime === "BEAR"
                          ? {
                              color: "var(--red)",
                              borderColor: "rgba(239,68,68,0.4)",
                              background: "var(--red-dim)",
                            }
                          : {
                              color: "var(--amber)",
                              borderColor: "rgba(245,158,11,0.4)",
                              background: "var(--amber-dim)",
                            }),
                    }}
                  >
                    {regime}
                  </span>
                )}
              </div>
            </div>

            {/* Right group: metrics + close */}
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center" }}>
              {/* Total return */}
              <span
                style={{
                  fontSize: "28px",
                  fontFamily: FONT,
                  fontWeight: 600,
                  letterSpacing: "-0.01em",
                  ...(totalReturn != null && totalReturn >= 0
                    ? {
                        background: "linear-gradient(135deg, var(--text-primary) 0%, #c8c0ff 60%, var(--accent) 100%)",
                        WebkitBackgroundClip: "text",
                        WebkitTextFillColor: "transparent",
                      }
                    : {
                        background: "linear-gradient(135deg, var(--text-primary) 0%, #ffb0b0 60%, var(--red) 100%)",
                        WebkitBackgroundClip: "text",
                        WebkitTextFillColor: "transparent",
                      }),
                }}
              >
                {totalReturn != null ? (totalReturn >= 0 ? "+" : "") + totalReturn.toFixed(1) + "%" : "\u2014"}
              </span>

              {/* Divider */}
              <div
                style={{
                  width: "1px",
                  height: "28px",
                  background: "var(--border)",
                  margin: "0 20px",
                }}
              />

              {/* Stat pairs */}
              <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
                <StatPair label="SHARPE" value={fmt(sharpe, 2)} />
                <StatPair label="MAX DD" value={fmt(maxDD, 1, "%")} color="var(--red)" />
                <StatPair
                  label="ALPHA"
                  value={fmt(alpha, 1, "%")}
                  color={alpha != null && alpha >= 0 ? "var(--green)" : "var(--red)"}
                />
              </div>

              {/* Close button */}
              <button
                onClick={onClose}
                onMouseEnter={() => setCloseHover(true)}
                onMouseLeave={() => setCloseHover(false)}
                style={{
                  width: "28px",
                  height: "28px",
                  borderRadius: "6px",
                  background: closeHover ? "var(--red-dim)" : "transparent",
                  border: closeHover
                    ? "1px solid rgba(239,68,68,0.3)"
                    : "1px solid var(--border)",
                  color: closeHover ? "var(--red)" : "var(--text-dim)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  marginLeft: "20px",
                  fontSize: "16px",
                  transition: "all 150ms ease",
                }}
              >
                ×
              </button>
            </div>
          </div>

          {/* ── Warning Rail ───────────────────────────────────────────── */}
          {warnings.length > 0 && (
            <div
              style={{
                padding: "8px 24px",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
                flexShrink: 0,
              }}
            >
              {warnings.slice(0, 3).map((w, i) => {
                const sc = SEVERITY_COLORS[w.severity] ?? "#60a5fa";
                return (
                  <div
                    key={w.id ?? i}
                    style={{
                      padding: "8px 12px",
                      borderRadius: "var(--radius)",
                      borderLeft: `3px solid ${sc}`,
                      background: "var(--bg-elevated)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center" }}>
                      <span
                        style={{
                          fontSize: "8px",
                          letterSpacing: "0.12em",
                          fontWeight: 700,
                          color: sc,
                          textTransform: "uppercase" as const,
                        }}
                      >
                        {w.severity}
                      </span>
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          color: "var(--text-primary)",
                          marginLeft: "8px",
                        }}
                      >
                        {w.title}
                      </span>
                    </div>
                    {w.description && (
                      <div
                        style={{
                          fontSize: "10px",
                          color: "var(--text-muted)",
                          lineHeight: 1.5,
                          marginTop: "2px",
                        }}
                      >
                        {w.description}
                      </div>
                    )}
                  </div>
                );
              })}
              {warnings.length > 3 && (
                <span
                  style={{
                    fontSize: "10px",
                    color: "var(--text-dim)",
                    paddingLeft: "12px",
                  }}
                >
                  +{warnings.length - 3} more
                </span>
              )}
            </div>
          )}

          {/* ── Tab Strip ──────────────────────────────────────────────── */}
          <div style={{ padding: "0 24px", flexShrink: 0, borderBottom: "1px solid var(--border)" }}>
            <div
              style={{
                display: "inline-flex",
                gap: "2px",
                padding: "4px",
                background: "transparent",
                borderRadius: "var(--radius)",
                margin: "8px 0",
              }}
            >
              {tabs.map((tab) => {
                const active = activeTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    style={
                      active
                        ? {
                            padding: "7px 16px",
                            borderRadius: "var(--radius)",
                            fontSize: "13px",
                            fontWeight: 600,
                            letterSpacing: "0.02em",
                            fontFamily: "var(--font-sans)",
                            color: "var(--text-primary)",
                            background: "var(--accent-dim)",
                            border: "1px solid rgba(139,92,246,0.25)",
                            cursor: "pointer",
                            boxShadow: "0 0 12px rgba(139,92,246,0.15)",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }
                        : {
                            padding: "7px 16px",
                            borderRadius: "var(--radius)",
                            fontSize: "13px",
                            fontWeight: 500,
                            letterSpacing: "0.02em",
                            fontFamily: "var(--font-sans)",
                            color: "var(--text-muted)",
                            background: "transparent",
                            border: "none",
                            cursor: "pointer",
                            transition: "color 150ms ease, background 150ms ease",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }
                    }
                  >
                    {tab.label}
                    {tab.dot && (
                      <span
                        style={{
                          width: "6px",
                          height: "6px",
                          borderRadius: "50%",
                          background: tab.dot,
                          flexShrink: 0,
                        }}
                      />
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── Tab Body ───────────────────────────────────────────────── */}
          <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            {isLoading ? (
              <LoadingState />
            ) : activeTab === "performance" ? (
              <PerformanceTab
                brief={brief}
                equityCurve={equityCurve}
                recommendations={recommendations}
              />
            ) : activeTab === "risk" ? (
              <div className="ib-scroll" style={{ flex: 1, overflowY: "auto", padding: "24px", display: "flex", flexDirection: "column", gap: "16px" }}>
                <RiskPulse brief={brief} />
              </div>
            ) : activeTab === "factors" ? (
              <div className="ib-scroll" style={{ flex: 1, overflowY: "auto", padding: "24px" }}>
                <FactorIntelligence brief={brief} />
              </div>
            ) : activeTab === "gscott" ? (
              <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
                <AuditChat portfolioId={portfolioId} />
              </div>
            ) : activeTab === "trades" ? (
              <TradesTab portfolioId={portfolioId} initialTradeId={initialTradeId ?? null} />
            ) : null}
          </div>
        </div>
      </div>
    </>
  );
}

// ── Stat Pair (header metric) ────────────────────────────────────────────────

function StatPair({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span
        style={{
          fontSize: "10px",
          fontFamily: "var(--font-sans)",
          fontWeight: 500,
          letterSpacing: "0.08em",
          color: "var(--text-dim)",
          textTransform: "uppercase" as const,
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: "14px",
          fontFamily: "var(--font-mono)",
          fontWeight: 500,
          color: color ?? "var(--text-primary)",
        }}
      >
        {value}
      </span>
    </div>
  );
}

// ── Performance Tab ──────────────────────────────────────────────────────────

function PerformanceTab({
  brief,
  equityCurve,
  recommendations,
}: {
  brief?: IntelligenceBriefData;
  equityCurve: number[];
  recommendations: string[];
}) {
  return (
    <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
      {/* Left panel (65%) */}
      <div
        className="ib-scroll"
        style={{
          width: "65%",
          borderRight: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
          padding: "20px 24px",
          gap: "16px",
        }}
      >
        {/* Diagnosis */}
        {brief?.health?.diagnosis && (
          <div
            style={{
              fontSize: "13px",
              fontFamily: "var(--font-sans)",
              color: "var(--text-secondary)",
              lineHeight: 1.6,
              padding: "12px 16px",
              background: "var(--accent-dim)",
              borderRadius: "var(--radius)",
              borderLeft: "3px solid rgba(139,92,246,0.4)",
            }}
          >
            {brief.health.diagnosis}
          </div>
        )}

        {/* Sparkline / Equity Curve */}
        <div
          style={{
            width: "100%",
            height: "140px",
            background: "var(--bg-elevated)",
            border: "1px solid var(--border)",
            borderTop: "1px solid var(--border-hover)",
            borderRadius: "var(--radius)",
            padding: "12px 16px",
            position: "relative",
            boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 4px rgba(0,0,0,0.35)",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <SectionHeader label="EQUITY CURVE" />
          <div style={{ flex: 1, minHeight: 0 }}>
            <Sparkline data={equityCurve} />
          </div>
        </div>

        {/* Trade Intelligence */}
        <TradeIntelligence brief={brief} />

        {/* Composition + Mini Risk row */}
        <div style={{ display: "flex", gap: "12px" }}>
          <div style={{ flex: 1 }}>
            <CompositionPanel brief={brief} />
          </div>
          <div style={{ flex: 1 }}>
            <MiniRiskPulse brief={brief} />
          </div>
        </div>
      </div>

      {/* Right panel (35%) */}
      <div
        className="ib-scroll"
        style={{
          width: "35%",
          padding: "20px",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
        }}
      >
        {/* Health recommendations */}
        {recommendations.length > 0 && (
          <div>
            <SectionHeader label="RECOMMENDATIONS" />
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {recommendations.map((rec, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    gap: "8px",
                    fontSize: "12px",
                    fontFamily: "var(--font-sans)",
                    color: "var(--text-secondary)",
                    lineHeight: 1.5,
                  }}
                >
                  <span style={{ color: "var(--accent)", flexShrink: 0, fontWeight: 700 }}>{"\u203A"}</span>
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* DNA Card (recessed) */}
        <div
          style={{
            background: "var(--bg-elevated)",
            borderRadius: "var(--radius)",
            border: "1px solid var(--border)",
            padding: "16px",
          }}
        >
          <DnaCard brief={brief} />
        </div>
      </div>
    </div>
  );
}

// ── Loading State ────────────────────────────────────────────────────────────

const shimmerStyle = `
  @keyframes shimmer {
    from { background-position: 200% 0; }
    to { background-position: -200% 0; }
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes slideIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: none; }
  }
  .ib-scroll::-webkit-scrollbar { width: 4px; }
  .ib-scroll::-webkit-scrollbar-track { background: transparent; }
  .ib-scroll::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.25); border-radius: 2px; }
  .ib-scroll::-webkit-scrollbar-thumb:hover { background: rgba(139,92,246,0.45); }
`;

const skeletonBase: React.CSSProperties = {
  background:
    "linear-gradient(90deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 100%)",
  backgroundSize: "200% 100%",
  animation: "shimmer 1.5s ease-in-out infinite",
  borderRadius: "4px",
};

function LoadingState() {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "24px",
        padding: "48px",
      }}
    >
      {/* Grade skeleton */}
      <div style={{ ...skeletonBase, width: "140px", height: "44px" }} />

      {/* Stat skeletons */}
      <div style={{ display: "flex", gap: "16px" }}>
        <div style={{ ...skeletonBase, width: "60px", height: "26px" }} />
        <div style={{ ...skeletonBase, width: "60px", height: "26px" }} />
        <div style={{ ...skeletonBase, width: "60px", height: "26px" }} />
      </div>

      {/* Card skeletons */}
      <div style={{ display: "flex", gap: "16px", width: "100%", maxWidth: "600px" }}>
        <div style={{ ...skeletonBase, flex: 1, height: "120px", borderRadius: "8px" }} />
        <div style={{ ...skeletonBase, flex: 1, height: "120px", borderRadius: "8px" }} />
      </div>

      <p
        style={{
          fontSize: "11px",
          fontFamily: "var(--font-mono)",
          color: "var(--text-dim)",
          letterSpacing: "0.08em",
        }}
      >
        LOADING BRIEF
      </p>
    </div>
  );
}
