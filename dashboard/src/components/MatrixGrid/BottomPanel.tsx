import { useEffect, useState } from "react";
import type { MatrixPosition, WatchlistCandidate, TradeRationale, Transaction } from "./types";
import type { TickerInfo, ChartDataPoint } from "../../lib/types";
import { api } from "../../lib/api";
import InteractiveSparkline from "./InteractiveSparkline";
import Reticle from "./Reticle";
import TradeThesis from "./TradeThesis";
import { tradeExplanation } from "../../lib/tradeUtils";
import { pc, MATRIX_FONT } from "./constants";

const HEAT_COLOR: Record<string, string> = {
  SPIKING: "#f87171", HOT: "#fb923c", WARM: "#facc15", COLD: "#555",
};

interface BottomPanelProps {
  pos: MatrixPosition | null;
  onClose: () => void;
  portfolioId?: string;
  watchlistCandidates?: WatchlistCandidate[];
  rationale?: TradeRationale | null;
  buyTx?: Transaction | null;
}

export default function BottomPanel({ pos, onClose, portfolioId, watchlistCandidates = [], rationale = null, buyTx = null }: BottomPanelProps) {
  const [info,      setInfo]      = useState<TickerInfo | null>(null);
  const [chartPts,  setChartPts]  = useState<ChartDataPoint[]>([]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  useEffect(() => {
    if (!pos) { setInfo(null); setChartPts([]); return; }
    const pid = portfolioId ?? pos.portfolioId;
    api.getTickerInfo(pid, pos.ticker)
      .then(setInfo)
      .catch(() => setInfo(null));
    api.getChartData(pos.ticker, "3M")
      .then(d => setChartPts(d.data ?? []))
      .catch(() => setChartPts([]));
  }, [pos?.ticker, pos?.portfolioId, portfolioId]);

  if (!pos) return null;
  const col = pos.portfolioColor;
  const social = watchlistCandidates.find(c => c.ticker === pos.ticker);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 0, left: 0, right: 0,
        height: 280,
        background: "rgba(4,6,9,0.98)",
        borderTop: `1px solid ${col}44`,
        zIndex: 300,
        display: "flex",
        flexDirection: "column",
        animation: "matrixSlideUp 0.22s cubic-bezier(0.16,1,0.3,1)",
        fontFamily: MATRIX_FONT,
      }}
    >
      {/* Top accent line */}
      <div style={{ height: 2, flexShrink: 0, background: `linear-gradient(90deg,transparent,${col}99,transparent)` }} />

      {/* Scanline overlay */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none", zIndex: 1,
        background: "repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.04) 2px,rgba(0,0,0,0.04) 4px)",
      }} />

      {/* Close button */}
      <button
        onClick={onClose}
        style={{
          position: "absolute", top: 8, right: 12, zIndex: 10,
          background: "none", border: "none", cursor: "pointer",
          color: "#555", fontSize: 14, lineHeight: 1, padding: "2px 6px",
          fontFamily: MATRIX_FONT,
        }}
        title="Close (Esc)"
      >
        ✕
      </button>

      {/* 3-column body */}
      <div style={{
        flex: 1, display: "grid", gridTemplateColumns: "1fr 1.6fr 0.85fr",
        gap: 0, overflow: "hidden", position: "relative", zIndex: 2,
      }}>

        {/* ── LEFT: identity + P&L ─────────────────────────────────────────── */}
        <div style={{
          padding: "14px 18px", borderRight: `1px solid ${col}18`,
          display: "flex", flexDirection: "column", gap: 6, overflow: "hidden",
        }}>
          {/* Ticker */}
          <div style={{ position: "relative", display: "inline-flex", alignItems: "center", padding: "0 6px" }}>
            <Reticle color={col} s={7} />
            <span style={{
              fontSize: 28, fontWeight: 700, color: "#fff", letterSpacing: "0.06em",
              textShadow: `0 0 24px ${col}55`,
            }}>{pos.ticker}</span>
          </div>

          {/* Portfolio + sector */}
          <div style={{ fontSize: 9, color: col, letterSpacing: "0.08em", marginLeft: 6 }}>
            ● {pos.portfolioName}
            {pos.sector && pos.sector !== "N/A" && pos.sector !== "" && ` · ${pos.sector}`}
            {pos.mktCap && pos.mktCap !== "N/A" && pos.mktCap !== "" && ` · ${pos.mktCap}`}
          </div>

          {pos.entryDate && (
            <div style={{ fontSize: 7, color: "#555", marginLeft: 6, letterSpacing: "0.08em" }}>
              ENTERED {pos.entryDate.slice(0, 10)}
            </div>
          )}

          {/* P&L block */}
          <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <div style={{
                fontSize: 26, fontWeight: 700, color: pc(pos.perf),
                textShadow: `0 0 16px ${pc(pos.perf)}55`,
              }}>
                {pos.perf > 0 ? "+" : ""}{pos.perf.toFixed(1)}%
              </div>
              <div style={{ fontSize: 7, color: "#555", letterSpacing: "0.1em" }}>ALL-TIME</div>
            </div>

            {pos.unrealizedPnl != null && (
              <div style={{ fontSize: 13, color: pc(pos.perf), fontWeight: 600 }}>
                {pos.unrealizedPnl >= 0 ? "+" : ""}${pos.unrealizedPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })} unrealized
              </div>
            )}

            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {pos.day !== 0 && (
                <div>
                  <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.12em" }}>DAY %</div>
                  <div style={{ fontSize: 11, color: pc(pos.day), fontWeight: 600 }}>
                    {pos.day > 0 ? "+" : ""}{pos.day.toFixed(2)}%
                  </div>
                </div>
              )}
              {pos.dayChangeDollar != null && (
                <div>
                  <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.12em" }}>DAY $</div>
                  <div style={{ fontSize: 11, color: pc(pos.dayChangeDollar), fontWeight: 600 }}>
                    {pos.dayChangeDollar >= 0 ? "+" : ""}${Math.abs(pos.dayChangeDollar).toFixed(0)}
                  </div>
                </div>
              )}
              {pos.vol != null && (
                <div>
                  <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.12em" }}>VOL</div>
                  <div style={{ fontSize: 11, color: "#888" }}>{pos.vol}%</div>
                </div>
              )}
              {pos.beta != null && (
                <div>
                  <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.12em" }}>BETA</div>
                  <div style={{ fontSize: 11, color: "#888" }}>{pos.beta}</div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── MIDDLE: sparkline + position stats ───────────────────────────── */}
        <div style={{
          padding: "14px 18px", borderRight: `1px solid ${col}18`,
          display: "flex", flexDirection: "column", gap: 8, overflow: "hidden",
        }}>
          {/* Sparkline — interactive with real price data */}
          {(() => {
            const prices     = chartPts.length > 1 ? chartPts.map(d => d.close) : pos.sparkline;
            const timestamps = chartPts.length > 1 ? chartPts.map(d => d.time)  : undefined;
            if (prices.length < 2) return null;
            return (
              <div style={{
                padding: "10px 12px",
                background: "rgba(255,255,255,0.015)", border: "1px solid rgba(255,255,255,0.03)",
                flex: 1, display: "flex", alignItems: "center", width: "100%",
              }}>
                <InteractiveSparkline data={prices} color={pos.portfolioColor} h={80} timestamps={timestamps} />
              </div>
            );
          })()}

          {/* Position stats 2×2 */}
          {(() => {
            const items = [
              pos.value > 0 ? { label: "VALUE", val: `$${pos.value.toLocaleString()}` } : null,
              pos.currentPrice != null ? { label: "PRICE", val: `$${pos.currentPrice.toFixed(2)}` } : null,
              pos.shares != null ? { label: "SHARES", val: String(pos.shares) } : null,
              pos.avgCost != null ? { label: "AVG COST", val: `$${pos.avgCost.toFixed(2)}` } : null,
            ].filter(Boolean) as { label: string; val: string }[];
            if (items.length === 0) return null;
            return (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
                {items.map((s) => (
                  <div key={s.label} style={{ background: "rgba(255,255,255,0.015)", padding: "6px 8px", border: "1px solid rgba(255,255,255,0.03)" }}>
                    <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.14em", marginBottom: 3 }}>{s.label}</div>
                    <div style={{ fontSize: 11, color: "#ccc", fontWeight: 500 }}>{s.val}</div>
                  </div>
                ))}
              </div>
            );
          })()}

          {/* Stop / take-profit inline with signal bars */}
          <div style={{ display: "flex", gap: 6, alignItems: "flex-end" }}>
            {pos.stopLoss != null && (
              <div style={{ background: "rgba(248,113,113,0.04)", padding: "6px 8px", border: "1px solid rgba(248,113,113,0.14)", minWidth: 80 }}>
                <div style={{ fontSize: 6, color: "#f87171", letterSpacing: "0.14em", marginBottom: 3 }}>STOP</div>
                <div style={{ fontSize: 11, color: "#f87171", fontWeight: 600 }}>${pos.stopLoss.toFixed(2)}</div>
                {pos.currentPrice != null && (
                  <div style={{ fontSize: 7, color: "#666", marginTop: 1 }}>
                    {((pos.stopLoss - pos.currentPrice) / pos.currentPrice * 100).toFixed(1)}%
                  </div>
                )}
              </div>
            )}
            {pos.takeProfit != null && (
              <div style={{ background: "rgba(74,222,128,0.04)", padding: "6px 8px", border: "1px solid rgba(74,222,128,0.14)", minWidth: 80 }}>
                <div style={{ fontSize: 6, color: "#4ade80", letterSpacing: "0.14em", marginBottom: 3 }}>TARGET</div>
                <div style={{ fontSize: 11, color: "#4ade80", fontWeight: 600 }}>${pos.takeProfit.toFixed(2)}</div>
                {pos.currentPrice != null && (
                  <div style={{ fontSize: 7, color: "#666", marginTop: 1 }}>
                    {((pos.takeProfit - pos.currentPrice) / pos.currentPrice * 100).toFixed(1)}%
                  </div>
                )}
              </div>
            )}
            {/* Signal bars fill remaining space */}
            <div style={{ flex: 1, display: "flex", gap: 1, alignItems: "flex-end", height: 28 }}>
              {Array.from({ length: 60 }, (_, i) => {
                const h = 2 + Math.abs(Math.sin(i * 0.3 + pos.perf) * Math.cos(i * 0.17)) * 26;
                return (
                  <div key={i} style={{
                    flex: 1, height: h,
                    background: pos.perf >= 0
                      ? `rgba(74,222,128,${0.10 + (h / 28) * 0.38})`
                      : `rgba(248,113,113,${0.10 + (h / 28) * 0.38})`,
                  }} />
                );
              })}
            </div>
          </div>
        </div>

        {/* ── RIGHT: trade thesis + company info (both always shown) ─────────── */}
        <div style={{
          padding: "14px 16px",
          display: "flex", flexDirection: "column", gap: 0, overflowY: "auto",
        }}>

          {/* Trade Thesis section — always present */}
          <div style={{ marginBottom: 10 }}>
            {rationale ? (
              <TradeThesis rationale={rationale} accentColor={col} />
            ) : buyTx ? (
              /* Fallback: reconstruct from factor scores for pre-feature positions */
              <>
                <div style={{ fontSize: 6, color: col, letterSpacing: "0.14em", fontWeight: 700, marginBottom: 5 }}>
                  TRADE THESIS
                </div>
                <div style={{ height: 1, background: `linear-gradient(90deg, ${col}33, transparent)`, marginBottom: 6 }} />
                <div style={{ fontSize: 7, color: "#555", lineHeight: 1.65 }}>
                  {tradeExplanation(buyTx)}
                </div>
              </>
            ) : (
              <>
                <div style={{ fontSize: 6, color: "#333", letterSpacing: "0.14em", fontWeight: 700, marginBottom: 5 }}>
                  TRADE THESIS
                </div>
                <div style={{ height: 1, background: "rgba(255,255,255,0.04)", marginBottom: 6 }} />
                <div style={{ fontSize: 7, color: "#333", lineHeight: 1.65 }}>No rationale captured</div>
              </>
            )}
          </div>

          {/* Divider */}
          <div style={{ height: 1, background: `linear-gradient(90deg, ${col}18, transparent)`, marginBottom: 10, flexShrink: 0 }} />

          {/* Company info section — always present */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {/* Company name + link */}
            {info?.name ? (
              <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                <span style={{ fontSize: 10, color: "#bbb", fontWeight: 700, letterSpacing: "0.03em" }}>{info.name}</span>
                {info.website && (
                  <a href={info.website} target="_blank" rel="noreferrer"
                    style={{ color: col, fontSize: 9, textDecoration: "none", opacity: 0.7, marginLeft: "auto" }}>
                    ↗
                  </a>
                )}
              </div>
            ) : (
              <div style={{ fontSize: 9, color: "#444", letterSpacing: "0.06em" }}>LOADING INFO...</div>
            )}
            {info?.industry && <div style={{ fontSize: 8, color: "#555" }}>{info.industry}</div>}
            {info?.description && (
              <div style={{ fontSize: 8, color: "#666", lineHeight: 1.65 }}>
                {info.description}
              </div>
            )}
            {info && (
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                {info.market_cap != null && (
                  <div>
                    <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.12em" }}>MKT CAP</div>
                    <div style={{ fontSize: 9, color: "#888" }}>
                      {info.market_cap >= 1e9 ? `$${(info.market_cap / 1e9).toFixed(1)}B` : `$${(info.market_cap / 1e6).toFixed(0)}M`}
                    </div>
                  </div>
                )}
                {info.trailing_pe != null && (
                  <div>
                    <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.12em" }}>P/E</div>
                    <div style={{ fontSize: 9, color: "#888" }}>{info.trailing_pe.toFixed(1)}</div>
                  </div>
                )}
                {info.week_52_high != null && info.week_52_low != null && (
                  <div>
                    <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.12em" }}>52W</div>
                    <div style={{ fontSize: 9, color: "#888" }}>${info.week_52_low.toFixed(0)}–${info.week_52_high.toFixed(0)}</div>
                  </div>
                )}
                {info.analyst_rating && (
                  <div>
                    <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.12em" }}>ANALYST</div>
                    <div style={{ fontSize: 9, color: "#888" }}>
                      {info.analyst_rating}
                      {info.analyst_count != null && <span style={{ color: "#555" }}> ({info.analyst_count})</span>}
                    </div>
                  </div>
                )}
                {info.dividend_yield != null && info.dividend_yield > 0 && (
                  <div>
                    <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.12em" }}>DIV</div>
                    <div style={{ fontSize: 9, color: "#4ade80" }}>{(info.dividend_yield * 100).toFixed(2)}%</div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Social heat */}
          {social?.social_heat && (
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "5px 8px", marginTop: "auto",
              background: `${HEAT_COLOR[social.social_heat] ?? "#555"}0e`,
              border: `1px solid ${HEAT_COLOR[social.social_heat] ?? "#555"}22`,
            }}>
              <div>
                <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.12em", marginBottom: 2 }}>SOCIAL</div>
                <div style={{
                  fontSize: 10, fontWeight: 700, letterSpacing: "0.1em",
                  color: HEAT_COLOR[social.social_heat] ?? "#555",
                  textShadow: `0 0 8px ${HEAT_COLOR[social.social_heat] ?? "#555"}55`,
                }}>
                  {social.social_heat}
                </div>
              </div>
              {social.social_bullish_pct != null && (
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 6, color: "#555", letterSpacing: "0.12em", marginBottom: 4 }}>
                    BULL {social.social_bullish_pct.toFixed(0)}%
                  </div>
                  <div style={{ height: 3, background: "rgba(255,255,255,0.06)", position: "relative" }}>
                    <div style={{
                      position: "absolute", left: 0, top: 0, bottom: 0,
                      width: `${social.social_bullish_pct}%`,
                      background: social.social_bullish_pct >= 60 ? "#4ade80" : social.social_bullish_pct >= 40 ? "#facc15" : "#f87171",
                    }} />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bottom hint */}
      <div style={{
        height: 18, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 7, color: "#2a2a2a", letterSpacing: "0.14em",
        borderTop: "1px solid rgba(255,255,255,0.02)",
      }}>
        ESC OR ✕ TO CLOSE
      </div>
    </div>
  );
}
