import { useEffect } from "react";
import type { MatrixPosition } from "./types";
import Sparkline from "./Sparkline";
import Reticle from "./Reticle";
import { pc } from "./constants";

interface DetailCardProps {
  pos: MatrixPosition | null;
  onClose: () => void;
}

export default function DetailCard({ pos, onClose }: DetailCardProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!pos) return null;
  const col = pos.portfolioColor;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 500,
        background: "rgba(3,3,6,0.7)", backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        animation: "matrixFadeIn 0.2s ease", cursor: "pointer",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "rgba(8,10,14,0.95)",
          border: `1px solid ${col}33`,
          borderRadius: 2, padding: 0, width: 480, maxHeight: "90vh",
          overflowY: "auto",
          position: "relative",
          boxShadow: `0 0 60px ${col}11, 0 0 120px rgba(0,0,0,0.8)`,
          cursor: "default", animation: "matrixScaleIn 0.2s ease",
        }}
      >
        <div style={{ height: 2, background: `linear-gradient(90deg,transparent,${col}88,transparent)`, position: "sticky", top: 0, zIndex: 1 }} />

        <div style={{ padding: "20px 24px" }}>
          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ position: "relative", display: "inline-block", padding: "2px 8px" }}>
                <Reticle color={col} s={8} />
                <span style={{
                  fontSize: 24, fontWeight: 700, color: "#fff", letterSpacing: "0.06em",
                  textShadow: `0 0 20px ${col}44`,
                }}>{pos.ticker}</span>
              </div>
              <div style={{ fontSize: 10, color: col, letterSpacing: "0.08em", marginTop: 6, marginLeft: 8 }}>
                ● {pos.portfolioName} · {pos.sector} · {pos.mktCap}
              </div>
              {pos.entryDate && (
                <div style={{ fontSize: 8, color: "#555", marginTop: 3, marginLeft: 8, letterSpacing: "0.08em" }}>
                  ENTERED {pos.entryDate.slice(0, 10)}
                </div>
              )}
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{
                fontSize: 22, fontWeight: 700, color: pc(pos.perf),
                textShadow: `0 0 12px ${pc(pos.perf)}44`,
              }}>
                {pos.perf > 0 ? "+" : ""}{pos.perf.toFixed(1)}%
              </div>
              <div style={{ fontSize: 10, color: "#888", marginTop: 2 }}>ALL-TIME P&L</div>
              {pos.unrealizedPnl != null && (
                <div style={{ fontSize: 12, color: pc(pos.perf), marginTop: 4, fontWeight: 600 }}>
                  {pos.unrealizedPnl >= 0 ? "+" : ""}${pos.unrealizedPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
              )}
            </div>
          </div>

          {/* Sparkline */}
          <div style={{
            margin: "16px 0 14px", padding: "12px",
            background: "rgba(255,255,255,0.015)", border: "1px solid rgba(255,255,255,0.03)",
          }}>
            <Sparkline data={pos.sparkline} color={pos.perf >= 0 ? "#4ade80" : "#f87171"} w={424} h={60} />
          </div>

          {/* Primary stats grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 10, marginBottom: 12 }}>
            {[
              { label: "MARKET VALUE", val: `$${pos.value.toLocaleString()}` },
              { label: "CURRENT PRICE", val: pos.currentPrice != null ? `$${pos.currentPrice.toFixed(2)}` : "N/A" },
              { label: "SHARES", val: pos.shares != null ? pos.shares.toString() : "N/A" },
              { label: "AVG COST", val: pos.avgCost != null ? `$${pos.avgCost.toFixed(2)}` : "N/A" },
            ].map((s) => (
              <div key={s.label} style={{ background: "rgba(255,255,255,0.015)", padding: "8px 10px", border: "1px solid rgba(255,255,255,0.03)" }}>
                <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.14em", marginBottom: 4 }}>{s.label}</div>
                <div style={{ fontSize: 13, color: "#ccc", fontWeight: 500 }}>{s.val}</div>
              </div>
            ))}
          </div>

          {/* Secondary stats grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 10, marginBottom: 12 }}>
            {[
              { label: "DAY %", val: `${pos.day > 0 ? "+" : ""}${pos.day.toFixed(2)}%`, color: pc(pos.day) },
              { label: "DAY $", val: pos.dayChangeDollar != null ? `${pos.dayChangeDollar >= 0 ? "+" : ""}$${Math.abs(pos.dayChangeDollar).toFixed(0)}` : "N/A", color: pos.dayChangeDollar != null ? pc(pos.dayChangeDollar) : undefined },
              { label: "VOLATILITY", val: pos.vol != null ? `${pos.vol}%` : "N/A" },
              { label: "BETA", val: pos.beta != null ? String(pos.beta) : "N/A" },
            ].map((s) => (
              <div key={s.label} style={{ background: "rgba(255,255,255,0.015)", padding: "8px 10px", border: "1px solid rgba(255,255,255,0.03)" }}>
                <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.14em", marginBottom: 4 }}>{s.label}</div>
                <div style={{ fontSize: 13, color: (s as { color?: string }).color ?? "#ccc", fontWeight: 500 }}>{s.val}</div>
              </div>
            ))}
          </div>

          {/* Stop/Target row */}
          {(pos.stopLoss != null || pos.takeProfit != null) && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
              {pos.stopLoss != null && (
                <div style={{ background: "rgba(248,113,113,0.04)", padding: "8px 10px", border: "1px solid rgba(248,113,113,0.1)" }}>
                  <div style={{ fontSize: 6, color: "#f87171", letterSpacing: "0.14em", marginBottom: 4 }}>STOP LOSS</div>
                  <div style={{ fontSize: 13, color: "#f87171", fontWeight: 600 }}>${pos.stopLoss.toFixed(2)}</div>
                  {pos.currentPrice != null && (
                    <div style={{ fontSize: 8, color: "#666", marginTop: 2 }}>
                      {((pos.stopLoss - pos.currentPrice) / pos.currentPrice * 100).toFixed(1)}% from current
                    </div>
                  )}
                </div>
              )}
              {pos.takeProfit != null && (
                <div style={{ background: "rgba(74,222,128,0.04)", padding: "8px 10px", border: "1px solid rgba(74,222,128,0.1)" }}>
                  <div style={{ fontSize: 6, color: "#4ade80", letterSpacing: "0.14em", marginBottom: 4 }}>TAKE PROFIT</div>
                  <div style={{ fontSize: 13, color: "#4ade80", fontWeight: 600 }}>${pos.takeProfit.toFixed(2)}</div>
                  {pos.currentPrice != null && (
                    <div style={{ fontSize: 8, color: "#666", marginTop: 2 }}>
                      {((pos.takeProfit - pos.currentPrice) / pos.currentPrice * 100).toFixed(1)}% from current
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Signal bars */}
          <div style={{ display: "flex", gap: 1, alignItems: "flex-end", height: 20 }}>
            {Array.from({ length: 60 }, (_, i) => {
              const h2 = 2 + Math.abs(Math.sin(i * 0.3 + pos.perf) * Math.cos(i * 0.17)) * 18;
              return (
                <div key={i} style={{
                  width: 5, height: h2,
                  background: pos.perf >= 0
                    ? `rgba(74,222,128,${0.15 + (h2 / 20) * 0.35})`
                    : `rgba(248,113,113,${0.15 + (h2 / 20) * 0.35})`,
                }} />
              );
            })}
          </div>
        </div>

        <div style={{ height: 1, background: `linear-gradient(90deg,transparent,${col}33,transparent)` }} />
        <div style={{
          padding: "6px 0", textAlign: "center", fontSize: 8, color: "#555",
          letterSpacing: "0.12em", background: "rgba(255,255,255,0.01)",
          position: "sticky", bottom: 0,
        }}>
          ESC OR CLICK OUTSIDE TO CLOSE
        </div>
      </div>
    </div>
  );
}
