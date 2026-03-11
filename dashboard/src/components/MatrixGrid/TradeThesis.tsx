import type { TradeRationale } from "../../lib/types";
import { MATRIX_FONT } from "./constants";

const DECISION_COLOR: Record<string, string> = {
  APPROVE: "#4ade80",
  MODIFY:  "#facc15",
  VETO:    "#f87171",
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
}

export default function TradeThesis({ rationale, accentColor = "#4ade80" }: TradeThesisProps) {
  const decisionColor = DECISION_COLOR[rationale.ai_decision] ?? "#888";
  const topLine = rationale.quant_reason?.split(" | ")[0] ?? "";

  return (
    <div style={{ fontFamily: MATRIX_FONT, display: "flex", flexDirection: "column", gap: 7 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: 6, color: accentColor, letterSpacing: "0.14em", fontWeight: 700 }}>
          TRADE THESIS
        </div>
        {rationale.ai_decision && (
          <div style={{
            fontSize: 7, fontWeight: 700, letterSpacing: "0.1em",
            color: decisionColor,
            padding: "1px 5px",
            border: `1px solid ${decisionColor}44`,
            background: `${decisionColor}0e`,
          }}>
            {rationale.ai_decision}
          </div>
        )}
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: `linear-gradient(90deg, ${accentColor}33, transparent)` }} />

      {/* Quant conviction line */}
      {topLine && (
        <div style={{ fontSize: 8, color: "#999", lineHeight: 1.5 }}>
          {topLine}
        </div>
      )}

      {/* Factor bars */}
      {rationale.top_factors?.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {rationale.top_factors.map(f => (
            <div key={f.name} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div style={{ fontSize: 6, color: "#444", letterSpacing: "0.1em", width: 60, flexShrink: 0 }}>
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
              <div style={{ fontSize: 8, color: "#666", width: 20, textAlign: "right", flexShrink: 0 }}>
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
              <div style={{ fontSize: 6, color: "#444", letterSpacing: "0.12em", marginBottom: 1 }}>REGIME</div>
              <div style={{ fontSize: 8, color: "#777" }}>{rationale.regime}</div>
            </div>
          )}
          {rationale.ai_confidence > 0 && (
            <div>
              <div style={{ fontSize: 6, color: "#444", letterSpacing: "0.12em", marginBottom: 1 }}>AI CONF</div>
              <div style={{ fontSize: 8, color: "#777" }}>{(rationale.ai_confidence * 100).toFixed(0)}%</div>
            </div>
          )}
        </div>
      )}

      {/* AI reasoning text */}
      {rationale.ai_reasoning && (
        <div style={{
          fontSize: 7, color: "#555", lineHeight: 1.65,
          overflowY: "auto", maxHeight: 52,
        }}>
          {rationale.ai_reasoning}
        </div>
      )}
    </div>
  );
}
