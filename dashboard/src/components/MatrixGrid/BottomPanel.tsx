import { useEffect, useState } from "react";
import type { MatrixPosition, WatchlistCandidate, TradeRationale, Transaction } from "./types";
import type { TickerInfo, ChartDataPoint, Position } from "../../lib/types";
import { api } from "../../lib/api";
import InteractiveSparkline from "./InteractiveSparkline";
import Reticle from "./Reticle";
import TradeThesis from "./TradeThesis";
import { tradeExplanation } from "../../lib/tradeUtils";
import { pc, MATRIX_FONT } from "./constants";
import SellModal from "../SellModal";

function matrixToPosition(mp: MatrixPosition): Position {
  return {
    ticker: mp.ticker,
    shares: mp.shares ?? 0,
    avg_cost_basis: mp.avgCost ?? 0,
    current_price: mp.currentPrice ?? 0,
    market_value: mp.value,
    unrealized_pnl: mp.unrealizedPnl ?? 0,
    unrealized_pnl_pct: mp.perf,
    stop_loss: mp.stopLoss ?? 0,
    take_profit: mp.takeProfit ?? 0,
    entry_date: mp.entryDate ?? "",
    day_change: mp.dayChangeDollar,
    day_change_pct: mp.day,
  };
}

const HEAT_COLOR: Record<string, string> = {
  SPIKING: "var(--red)", HOT: "#fb923c", WARM: "var(--amber)", COLD: "var(--text-muted)",
};

interface BottomPanelProps {
  pos: MatrixPosition | null;
  onClose: () => void;
  portfolioId?: string;
  watchlistCandidates?: WatchlistCandidate[];
  rationale?: TradeRationale | null;
  buyTx?: Transaction | null;
  sellReasoning?: string | null;
}

export default function BottomPanel({ pos, onClose, portfolioId, watchlistCandidates = [], rationale = null, buyTx = null, sellReasoning = null }: BottomPanelProps) {
  const [info,      setInfo]      = useState<TickerInfo | null>(null);
  const [chartPts,  setChartPts]  = useState<ChartDataPoint[]>([]);
  const [isMobile,  setIsMobile]  = useState(() => window.innerWidth < 640);
  const [showSell,  setShowSell]  = useState(false);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 640);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);

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
        height: isMobile ? "70vh" : 280,
        background: "rgba(2,6,23,0.98)",
        borderTop: `1px solid var(--border)`,
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
          color: "var(--text-dim)", fontSize: 14, lineHeight: 1, padding: "2px 6px",
          fontFamily: MATRIX_FONT,
        }}
        title="Close (Esc)"
      >
        ✕
      </button>

      {showSell && pos.shares != null && pos.shares > 0 && (
        <SellModal pos={matrixToPosition(pos)} onClose={() => setShowSell(false)} />
      )}

      {/* Body — 3-col on desktop, single scrollable column on mobile */}
      <div style={{
        flex: 1,
        minHeight: 0,
        display: "grid",
        gridTemplateColumns: isMobile ? "1fr" : "0.85fr 1.4fr 1fr",
        gap: 0,
        overflow: isMobile ? "auto" : "hidden",
        position: "relative",
        zIndex: 2,
      }}>

        {/* ── LEFT: identity + P&L ─────────────────────────────────────────── */}
        <div style={{
          padding: "14px 18px",
          borderRight: isMobile ? "none" : `1px solid ${col}18`,
          borderBottom: isMobile ? `1px solid ${col}18` : "none",
          display: "flex", flexDirection: "column", gap: 6,
          overflow: isMobile ? "visible" : "hidden",
        }}>
          {/* Ticker */}
          <div style={{ position: "relative", display: "inline-flex", alignItems: "center", padding: "0 6px" }}>
            <Reticle color={col} s={7} />
            <span style={{
              fontSize: 26, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "0.06em",
              textShadow: `0 0 24px ${col}55`,
            }}>{pos.ticker}</span>
          </div>

          {/* Portfolio + sector */}
          <div style={{ fontSize: 10, color: col, letterSpacing: "0.06em", marginLeft: 6 }}>
            ● {pos.portfolioName}
            {pos.sector && pos.sector !== "N/A" && pos.sector !== "" && ` · ${pos.sector}`}
            {pos.mktCap && pos.mktCap !== "N/A" && pos.mktCap !== "" && ` · ${pos.mktCap}`}
          </div>

          {pos.entryDate && (
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginLeft: 6, letterSpacing: "0.06em" }}>
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
              <div style={{ fontSize: 7, color: "var(--text-dim)", letterSpacing: "0.1em" }}>ALL-TIME</div>
            </div>

            {pos.unrealizedPnl != null && (
              <div style={{ fontSize: 13, color: pc(pos.perf), fontWeight: 600 }}>
                {pos.unrealizedPnl >= 0 ? "+" : ""}${pos.unrealizedPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })} unrealized
              </div>
            )}

            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {pos.day !== 0 && (
                <div>
                  <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em" }}>DAY %</div>
                  <div style={{ fontSize: 12, color: pc(pos.day), fontWeight: 600 }}>
                    {pos.day > 0 ? "+" : ""}{pos.day.toFixed(2)}%
                  </div>
                </div>
              )}
              {pos.dayChangeDollar != null && (
                <div>
                  <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em" }}>DAY $</div>
                  <div style={{ fontSize: 12, color: pc(pos.dayChangeDollar), fontWeight: 600 }}>
                    {pos.dayChangeDollar >= 0 ? "+" : ""}${Math.abs(pos.dayChangeDollar).toFixed(0)}
                  </div>
                </div>
              )}
              {pos.vol != null && (
                <div>
                  <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em" }}>VOL</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{pos.vol}%</div>
                </div>
              )}
              {pos.beta != null && (
                <div>
                  <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em" }}>BETA</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{pos.beta}</div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── MIDDLE: sparkline + position stats ───────────────────────────── */}
        <div style={{
          padding: "14px 18px",
          borderRight: isMobile ? "none" : `1px solid ${col}18`,
          borderBottom: isMobile ? `1px solid ${col}18` : "none",
          display: "flex", flexDirection: "column", gap: 8,
          overflow: isMobile ? "visible" : "hidden",
        }}>
          {/* Sparkline — interactive with real price data */}
          {(() => {
            const prices     = chartPts.length > 1 ? chartPts.map(d => d.close) : pos.sparkline;
            const timestamps = chartPts.length > 1 ? chartPts.map(d => d.time)  : undefined;
            if (prices.length < 2) return null;
            return (
              <div style={{
                padding: "10px 12px",
                background: "var(--bg-void)", border: "1px solid var(--border)",
                flex: isMobile ? undefined : 1,
                height: isMobile ? 120 : undefined,
                display: "flex", alignItems: "center", width: "100%",
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
                  <div key={s.label} style={{ background: "var(--bg-void)", padding: "6px 8px", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em", marginBottom: 3 }}>{s.label}</div>
                    <div style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 500 }}>{s.val}</div>
                  </div>
                ))}
              </div>
            );
          })()}

          {/* Stop / take-profit + SELL inline */}
          <div style={{ display: "flex", gap: 6, alignItems: "flex-end" }}>
            {pos.stopLoss != null && (
              <div style={{ background: "var(--red-dim)", padding: "6px 8px", border: "1px solid rgba(239,68,68,0.18)", minWidth: 80 }}>
                <div style={{ fontSize: 9, color: "var(--red)", letterSpacing: "0.08em", marginBottom: 3 }}>STOP</div>
                <div style={{ fontSize: 12, color: "var(--red)", fontWeight: 600 }}>${pos.stopLoss.toFixed(2)}</div>
                {pos.currentPrice != null && (
                  <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 2 }}>
                    {((pos.stopLoss - pos.currentPrice) / pos.currentPrice * 100).toFixed(1)}%
                  </div>
                )}
              </div>
            )}
            {pos.takeProfit != null && (
              <div style={{ background: "var(--green-dim)", padding: "6px 8px", border: "1px solid rgba(34,197,94,0.18)", minWidth: 80 }}>
                <div style={{ fontSize: 9, color: "var(--green)", letterSpacing: "0.08em", marginBottom: 3 }}>TARGET</div>
                <div style={{ fontSize: 12, color: "var(--green)", fontWeight: 600 }}>${pos.takeProfit.toFixed(2)}</div>
                {pos.currentPrice != null && (
                  <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 2 }}>
                    {((pos.takeProfit - pos.currentPrice) / pos.currentPrice * 100).toFixed(1)}%
                  </div>
                )}
              </div>
            )}
            {pos.shares != null && pos.shares > 0 && (
              <button
                onClick={() => setShowSell(true)}
                style={{
                  background: "var(--red-dim)",
                  border: "1px solid rgba(239,68,68,0.18)",
                  cursor: "pointer",
                  color: "var(--red)",
                  fontSize: 12,
                  fontWeight: 600,
                  padding: "6px 8px",
                  minWidth: 80,
                  fontFamily: MATRIX_FONT,
                  letterSpacing: "0.08em",
                  transition: "all 0.15s",
                  textAlign: "left",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "rgba(239,68,68,0.12)";
                  e.currentTarget.style.borderColor = "rgba(239,68,68,0.40)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "rgba(239,68,68,0.06)";
                  e.currentTarget.style.borderColor = "rgba(239,68,68,0.18)";
                }}
              >
                <div style={{ fontSize: 9, letterSpacing: "0.08em", marginBottom: 3, color: "var(--red)" }}>SELL</div>
                <div style={{ fontWeight: 600 }}>{pos.ticker}</div>
              </button>
            )}
          </div>
        </div>

        {/* ── RIGHT: trade thesis + company info (both always shown) ─────────── */}
        <div style={{
          padding: "14px 16px",
          display: "flex", flexDirection: "column", gap: 0,
          overflowY: isMobile ? "visible" : "auto",
          borderTop: isMobile ? `1px solid ${col}18` : "none",
        }}>

          {/* Trade Thesis section — always present */}
          <div style={{ marginBottom: 10 }}>
            {rationale ? (
              <TradeThesis rationale={rationale} accentColor={col} sellReasoning={sellReasoning ?? undefined} />
            ) : buyTx ? (
              /* Fallback: reconstruct from factor scores for pre-feature positions */
              <>
                <div style={{ fontSize: 6, color: col, letterSpacing: "0.14em", fontWeight: 700, marginBottom: 5 }}>
                  TRADE THESIS
                </div>
                <div style={{ height: 1, background: `linear-gradient(90deg, ${col}33, transparent)`, marginBottom: 6 }} />
                <div style={{ fontSize: 7, color: "var(--text-dim)", lineHeight: 1.65 }}>
                  {tradeExplanation(buyTx)}
                </div>
              </>
            ) : (
              <>
                <div style={{ fontSize: 6, color: "var(--text-dim)", letterSpacing: "0.14em", fontWeight: 700, marginBottom: 5 }}>
                  TRADE THESIS
                </div>
                <div style={{ height: 1, background: "rgba(255,255,255,0.04)", marginBottom: 6 }} />
                <div style={{ fontSize: 7, color: "var(--text-dim)", lineHeight: 1.65 }}>No rationale captured</div>
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
                <span style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 700, letterSpacing: "0.02em" }}>{info.name}</span>
                {info.website && (
                  <a href={info.website} target="_blank" rel="noreferrer"
                    style={{ color: col, fontSize: 10, textDecoration: "none", opacity: 0.7, marginLeft: "auto" }}>
                    ↗
                  </a>
                )}
              </div>
            ) : (
              <div style={{ fontSize: 10, color: "var(--text-dim)", letterSpacing: "0.06em" }}>LOADING INFO...</div>
            )}
            {info?.industry && <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{info.industry}</div>}
            {info?.description && (
              <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6 }}>
                {info.description}
              </div>
            )}
            {info && (
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                {info.market_cap != null && (
                  <div>
                    <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em" }}>MKT CAP</div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      {info.market_cap >= 1e9 ? `$${(info.market_cap / 1e9).toFixed(1)}B` : `$${(info.market_cap / 1e6).toFixed(0)}M`}
                    </div>
                  </div>
                )}
                {info.trailing_pe != null && (
                  <div>
                    <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em" }}>P/E</div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{info.trailing_pe.toFixed(1)}</div>
                  </div>
                )}
                {info.week_52_high != null && info.week_52_low != null && (
                  <div>
                    <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em" }}>52W</div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>${info.week_52_low.toFixed(0)}–${info.week_52_high.toFixed(0)}</div>
                  </div>
                )}
                {info.analyst_rating && (
                  <div>
                    <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em" }}>ANALYST</div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      {info.analyst_rating}
                      {info.analyst_count != null && <span style={{ color: "var(--text-dim)" }}> ({info.analyst_count})</span>}
                    </div>
                  </div>
                )}
                {info.dividend_yield != null && info.dividend_yield > 0 && (
                  <div>
                    <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em" }}>DIV</div>
                    <div style={{ fontSize: 11, color: "var(--green)" }}>{(info.dividend_yield * 100).toFixed(2)}%</div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Social heat */}
          {social?.social_heat && (
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "6px 8px", marginTop: "auto",
              background: `${HEAT_COLOR[social.social_heat] ?? "#555"}0e`,
              border: `1px solid ${HEAT_COLOR[social.social_heat] ?? "#555"}22`,
            }}>
              <div>
                <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.08em", marginBottom: 3 }}>SOCIAL</div>
                <div style={{
                  fontSize: 11, fontWeight: 700, letterSpacing: "0.08em",
                  color: HEAT_COLOR[social.social_heat] ?? "#555",
                  textShadow: `0 0 8px ${HEAT_COLOR[social.social_heat] ?? "#555"}55`,
                }}>
                  {social.social_heat}
                </div>
              </div>
              {social.social_bullish_pct != null && (
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.06em", marginBottom: 4 }}>
                    BULL {social.social_bullish_pct.toFixed(0)}%
                  </div>
                  <div style={{ height: 3, background: "rgba(255,255,255,0.06)", position: "relative" }}>
                    <div style={{
                      position: "absolute", left: 0, top: 0, bottom: 0,
                      width: `${social.social_bullish_pct}%`,
                      background: social.social_bullish_pct >= 60 ? "var(--green)" : social.social_bullish_pct >= 40 ? "var(--amber)" : "var(--red)",
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
        fontSize: 8, color: "var(--text-dim)", letterSpacing: "0.1em",
        borderTop: "1px solid rgba(255,255,255,0.02)",
      }}>
        ESC OR ✕ TO CLOSE
      </div>
    </div>
  );
}
