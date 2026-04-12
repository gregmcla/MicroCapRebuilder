import type { TradeRationale } from "../../lib/types";

const DECISION_COLOR: Record<string, string> = {
  APPROVE: "#22C55E",
  MODIFY:  "#F59E0B",
  VETO:    "#EF4444",
};

const FACTOR_LABEL: Record<string, string> = {
  price_momentum:  "MOMENTUM",
  earnings_growth: "EARNINGS",
  quality:         "QUALITY",
  volume:          "VOLUME",
  volatility:      "VOLATILITY",
  value_timing:    "VALUE",
};

interface TradeThesisProps {
  rationale: TradeRationale;
  accentColor?: string;
  sellReasoning?: string;
}

export default function TradeThesis({ rationale, accentColor = "#22C55E", sellReasoning }: TradeThesisProps) {
  const decisionColor = DECISION_COLOR[rationale.ai_decision] ?? "#888";

  return (
    <div style={{ fontFamily: "var(--font-mono)", display: "flex", flexDirection: "column", gap: 7 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: 9, color: sellReasoning ? "#EF4444" : accentColor, letterSpacing: "0.1em", fontWeight: 700 }}>
          {sellReasoning ? "EXIT THESIS" : "TRADE THESIS"}
        </div>
        {rationale.ai_decision && (
          <div style={{
            fontSize: 9, fontWeight: 700, letterSpacing: "0.08em",
            color: decisionColor,
            padding: "2px 6px",
            border: `1px solid ${decisionColor}44`,
            background: `${decisionColor}0e`,
          }}>
            {rationale.ai_decision}
          </div>
        )}
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: `linear-gradient(90deg, ${sellReasoning ? "#EF4444" : accentColor}33, transparent)` }} />

      {/* Pending sell reasoning — shown prominently when there's an active sell proposal */}
      {sellReasoning && (
        <div style={{
          fontSize: 11, color: "#ddd", lineHeight: 1.6,
          padding: "6px 8px",
          background: "rgba(239,68,68,0.06)",
          border: "1px solid rgba(239,68,68,0.18)",
        }}>
          {sellReasoning}
        </div>
      )}

      {/* Factor bars */}
      {rationale.top_factors?.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {rationale.top_factors.map(f => (
            <div key={f.name} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ fontSize: 9, color: "#475569", letterSpacing: "0.06em", width: 64, flexShrink: 0 }}>
                {FACTOR_LABEL[f.name] ?? f.name.toUpperCase().slice(0, 8)}
              </div>
              <div style={{ flex: 1, height: 2, background: "rgba(255,255,255,0.05)", position: "relative" }}>
                <div style={{
                  position: "absolute", left: 0, top: 0, bottom: 0,
                  width: `${Math.min(f.score, 100)}%`,
                  background: accentColor,
                  opacity: 0.4 + (f.score / 100) * 0.5,
                }} />
              </div>
              <div style={{ fontSize: 10, color: "#64748B", width: 22, textAlign: "right", flexShrink: 0 }}>
                {f.score.toFixed(0)}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Regime + confidence row */}
      {(rationale.regime || rationale.ai_confidence > 0) && (
        <div style={{ display: "flex", gap: 14 }}>
          {rationale.regime && (
            <div>
              <div style={{ fontSize: 9, color: "#475569", letterSpacing: "0.08em", marginBottom: 2 }}>REGIME</div>
              <div style={{ fontSize: 10, color: "#64748B" }}>{rationale.regime}</div>
            </div>
          )}
          {rationale.ai_confidence > 0 && (
            <div>
              <div style={{ fontSize: 9, color: "#475569", letterSpacing: "0.08em", marginBottom: 2 }}>AI CONF</div>
              <div style={{ fontSize: 10, color: "#64748B" }}>{(rationale.ai_confidence * 100).toFixed(0)}%</div>
            </div>
          )}
        </div>
      )}

      {/* AI reasoning — primary display when no sell pending */}
      {!sellReasoning && rationale.ai_reasoning && (
        <div style={{
          fontSize: 11, color: "#94A3B8", lineHeight: 1.6,
          overflowY: "auto",
        }}>
          {rationale.ai_reasoning}
        </div>
      )}
      {/* De-emphasized buy entry context when sell reasoning is showing */}
      {sellReasoning && rationale.ai_reasoning && (
        <div style={{ fontSize: 9, color: "#475569", lineHeight: 1.6, marginTop: 2 }}>
          <span style={{ letterSpacing: "0.08em", fontSize: 9 }}>ENTRY: </span>
          {rationale.ai_reasoning}
        </div>
      )}
    </div>
  );
}
