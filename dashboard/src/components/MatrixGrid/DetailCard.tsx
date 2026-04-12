import { useEffect, useState } from "react";
import type { MatrixPosition, WatchlistCandidate, TradeRationale } from "./types";
import type { TickerInfo } from "../../lib/types";
import { api } from "../../lib/api";
import Sparkline from "./Sparkline";
import Reticle from "./Reticle";
import TradeThesis from "./TradeThesis";
import { pc, MATRIX_FONT } from "./constants";

const HEAT_COLOR: Record<string, string> = {
  SPIKING: "#EF4444", HOT: "#fb923c", WARM: "#F59E0B", COLD: "#64748B",
};

interface DetailCardProps {
  pos: MatrixPosition | null;
  onClose: () => void;
  portfolioId?: string;
  watchlistCandidates?: WatchlistCandidate[];
}

export default function DetailCard({ pos, onClose, portfolioId, watchlistCandidates = [] }: DetailCardProps) {
  const [info, setInfo] = useState<TickerInfo | null>(null);
  // undefined = loading, null = loaded but no data
  const [rationale, setRationale] = useState<TradeRationale | null | undefined>(undefined);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  useEffect(() => {
    if (!pos) { setInfo(null); setRationale(undefined); return; }
    const pid = portfolioId ?? pos.portfolioId;
    api.getTickerInfo(pid, pos.ticker)
      .then(setInfo)
      .catch(() => setInfo(null));
    api.getPositionRationale(pid, pos.ticker)
      .then(r => setRationale(Object.keys(r).length > 0 ? r as TradeRationale : null))
      .catch(() => setRationale(null));
  }, [pos?.ticker, pos?.portfolioId, portfolioId]);

  if (!pos) return null;
  const col = pos.portfolioColor;
  const social = watchlistCandidates.find(c => c.ticker === pos.ticker);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 500,
        background: "rgba(2,6,23,0.7)", backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        animation: "matrixFadeIn 0.2s ease", cursor: "pointer",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--bg-surface)",
          border: `1px solid ${col}33`,
          borderRadius: "var(--radius-lg)", padding: 0, width: 480, maxHeight: "90vh",
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
                  fontSize: 24, fontWeight: 700, color: "#F8FAFC", letterSpacing: "0.06em",
                  fontFamily: "var(--font-mono)",
                  textShadow: `0 0 20px ${col}44`,
                }}>{pos.ticker}</span>
              </div>
              <div style={{ fontSize: 10, color: col, letterSpacing: "0.08em", marginTop: 6, marginLeft: 8 }}>
                ● {pos.portfolioName}
                {pos.sector && pos.sector !== "N/A" && pos.sector !== "" && ` · ${pos.sector}`}
                {pos.mktCap && pos.mktCap !== "N/A" && pos.mktCap !== "" && ` · ${pos.mktCap}`}
              </div>
              {pos.entryDate && (
                <div style={{ fontSize: 8, color: "#475569", marginTop: 3, marginLeft: 8, letterSpacing: "0.08em" }}>
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
              <div style={{ fontSize: 10, color: "#64748B", marginTop: 2 }}>ALL-TIME P&L</div>
              {pos.unrealizedPnl != null && (
                <div style={{ fontSize: 12, color: pc(pos.perf), marginTop: 4, fontWeight: 600 }}>
                  {pos.unrealizedPnl >= 0 ? "+" : ""}${pos.unrealizedPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
              )}
            </div>
          </div>

          {/* Social sentiment — shown when ticker is on watchlist */}
          {social?.social_heat && (
            <div style={{
              display: "flex", alignItems: "center", gap: 12, margin: "12px 0 4px",
              padding: "6px 10px",
              background: `${HEAT_COLOR[social.social_heat] ?? "#555"}0f`,
              border: `1px solid ${HEAT_COLOR[social.social_heat] ?? "#555"}22`,
            }}>
              <div>
                <div style={{ fontSize: 6, color: "#475569", letterSpacing: "0.12em", marginBottom: 2 }}>SOCIAL HEAT</div>
                <div style={{
                  fontSize: 10, fontWeight: 700, letterSpacing: "0.1em",
                  color: HEAT_COLOR[social.social_heat] ?? "#555",
                  textShadow: `0 0 8px ${HEAT_COLOR[social.social_heat] ?? "#555"}55`,
                }}>
                  {social.social_heat}
                </div>
              </div>
              {social.social_rank != null && (
                <div>
                  <div style={{ fontSize: 6, color: "#475569", letterSpacing: "0.12em", marginBottom: 2 }}>RANK</div>
                  <div style={{ fontSize: 10, color: "#aaa" }}>#{social.social_rank}</div>
                </div>
              )}
              {social.social_bullish_pct != null && (
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 6, color: "#475569", letterSpacing: "0.12em", marginBottom: 4 }}>
                    BULLISH SENTIMENT — {social.social_bullish_pct.toFixed(0)}%
                  </div>
                  <div style={{ height: 3, background: "rgba(255,255,255,0.06)", position: "relative" }}>
                    <div style={{
                      position: "absolute", left: 0, top: 0, bottom: 0,
                      width: `${social.social_bullish_pct}%`,
                      background: social.social_bullish_pct >= 60 ? "#22C55E" : social.social_bullish_pct >= 40 ? "#F59E0B" : "#EF4444",
                      transition: "width 0.4s",
                    }} />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Sparkline — only when we have real data */}
          {pos.sparkline.length > 0 && (
            <div style={{
              margin: "16px 0 14px", padding: "12px",
              background: "var(--bg-void)", border: "1px solid var(--border)",
            }}>
              <Sparkline data={pos.sparkline} color={pos.perf >= 0 ? "#22C55E" : "#EF4444"} w={424} h={60} />
            </div>
          )}

          {/* Trade Thesis — always shown (rich data or empty state) */}
          <div style={{
            margin: "4px 0 12px",
            padding: "10px 12px",
            background: "rgba(139,92,246,0.03)",
            border: `1px solid rgba(139,92,246,0.08)`,
          }}>
            {rationale ? (
              <TradeThesis rationale={rationale} accentColor={col} />
            ) : (
              <>
                <div style={{ fontSize: 6, color: "#475569", letterSpacing: "0.14em", fontWeight: 700, marginBottom: 4 }}>
                  TRADE THESIS
                </div>
                <div style={{ height: 1, background: "rgba(255,255,255,0.04)", marginBottom: 6 }} />
                <div style={{ fontSize: 7, color: "#475569" }}>
                  {rationale === undefined ? "Loading..." : "No rationale captured for this position"}
                </div>
              </>
            )}
          </div>

          {/* Company info */}
          {info && (
            <div style={{ marginBottom: 12 }}>
              {info.name && (
                <div style={{ fontSize: 9, color: "#94A3B8", fontWeight: 600, marginBottom: 4, letterSpacing: "0.04em" }}>
                  {info.name}
                  {info.industry && <span style={{ color: "#64748B", fontWeight: 400 }}> · {info.industry}</span>}
                  {info.website && (
                    <a href={info.website} target="_blank" rel="noreferrer"
                      style={{ color: col, marginLeft: 8, fontSize: 8, textDecoration: "none", opacity: 0.7 }}>
                      ↗
                    </a>
                  )}
                </div>
              )}
              {info.description && (
                <div style={{
                  fontSize: 8, color: "#64748B", lineHeight: 1.6,
                  overflow: "visible",
                  fontFamily: MATRIX_FONT,
                }}>
                  {info.description}
                </div>
              )}
              {/* Extra info row */}
              <div style={{ display: "flex", gap: 16, marginTop: 8, flexWrap: "wrap" as const }}>
                {info.market_cap != null && (
                  <div>
                    <div style={{ fontSize: 6, color: "#475569", letterSpacing: "0.12em" }}>MKT CAP</div>
                    <div style={{ fontSize: 9, color: "#64748B" }}>
                      {info.market_cap >= 1e9 ? `$${(info.market_cap / 1e9).toFixed(1)}B` : `$${(info.market_cap / 1e6).toFixed(0)}M`}
                    </div>
                  </div>
                )}
                {info.trailing_pe != null && (
                  <div>
                    <div style={{ fontSize: 6, color: "#475569", letterSpacing: "0.12em" }}>P/E</div>
                    <div style={{ fontSize: 9, color: "#64748B" }}>{info.trailing_pe.toFixed(1)}</div>
                  </div>
                )}
                {info.week_52_high != null && info.week_52_low != null && (
                  <div>
                    <div style={{ fontSize: 6, color: "#475569", letterSpacing: "0.12em" }}>52W</div>
                    <div style={{ fontSize: 9, color: "#64748B" }}>${info.week_52_low.toFixed(0)}–${info.week_52_high.toFixed(0)}</div>
                  </div>
                )}
                {info.analyst_rating && (
                  <div>
                    <div style={{ fontSize: 6, color: "#475569", letterSpacing: "0.12em" }}>ANALYST</div>
                    <div style={{ fontSize: 9, color: "#64748B" }}>{info.analyst_rating}
                      {info.analyst_count != null && <span style={{ color: "#475569" }}> ({info.analyst_count})</span>}
                    </div>
                  </div>
                )}
                {info.dividend_yield != null && info.dividend_yield > 0 && (
                  <div>
                    <div style={{ fontSize: 6, color: "#475569", letterSpacing: "0.12em" }}>DIV YIELD</div>
                    <div style={{ fontSize: 9, color: "#22C55E" }}>{(info.dividend_yield * 100).toFixed(2)}%</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Primary stats grid — only render boxes where data exists */}
          {(() => {
            const items = [
              pos.value > 0 ? { label: "MARKET VALUE", val: `$${pos.value.toLocaleString()}` } : null,
              pos.currentPrice != null ? { label: "CURRENT PRICE", val: `$${pos.currentPrice.toFixed(2)}` } : null,
              pos.shares != null ? { label: "SHARES", val: pos.shares.toString() } : null,
              pos.avgCost != null ? { label: "AVG COST", val: `$${pos.avgCost.toFixed(2)}` } : null,
            ].filter(Boolean) as { label: string; val: string }[];
            if (items.length === 0) return null;
            return (
              <div style={{ display: "grid", gridTemplateColumns: `repeat(${items.length}, 1fr)`, gap: 10, marginBottom: 12 }}>
                {items.map((s) => (
                  <div key={s.label} style={{ background: "var(--bg-void)", padding: "8px 10px", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: 6, color: "#475569", letterSpacing: "0.14em", marginBottom: 4 }}>{s.label}</div>
                    <div style={{ fontSize: 13, color: "#94A3B8", fontWeight: 500 }}>{s.val}</div>
                  </div>
                ))}
              </div>
            );
          })()}

          {/* Secondary stats grid — skip N/A entries */}
          {(() => {
            const items = [
              pos.day !== 0 ? { label: "DAY %", val: `${pos.day > 0 ? "+" : ""}${pos.day.toFixed(2)}%`, color: pc(pos.day) } : null,
              pos.dayChangeDollar != null ? { label: "DAY $", val: `${pos.dayChangeDollar >= 0 ? "+" : ""}$${Math.abs(pos.dayChangeDollar).toFixed(0)}`, color: pc(pos.dayChangeDollar) } : null,
              pos.vol != null ? { label: "VOLATILITY", val: `${pos.vol}%` } : null,
              pos.beta != null ? { label: "BETA", val: String(pos.beta) } : null,
              pos.perf !== 0 ? { label: "ALL-TIME %", val: `${pos.perf > 0 ? "+" : ""}${pos.perf.toFixed(1)}%`, color: pc(pos.perf) } : null,
              pos.unrealizedPnl != null && pos.unrealizedPnl !== 0 ? { label: "UNREALIZED $", val: `${pos.unrealizedPnl >= 0 ? "+" : ""}$${Math.abs(pos.unrealizedPnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, color: pc(pos.unrealizedPnl) } : null,
            ].filter(Boolean) as { label: string; val: string; color?: string }[];
            if (items.length === 0) return null;
            const cols = Math.min(items.length, 4);
            return (
              <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: 10, marginBottom: 12 }}>
                {items.map((s) => (
                  <div key={s.label} style={{ background: "var(--bg-void)", padding: "8px 10px", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: 6, color: "#475569", letterSpacing: "0.14em", marginBottom: 4 }}>{s.label}</div>
                    <div style={{ fontSize: 13, color: s.color ?? "#94A3B8", fontWeight: 500 }}>{s.val}</div>
                  </div>
                ))}
              </div>
            );
          })()}

          {/* Stop/Target row */}
          {(pos.stopLoss != null || pos.takeProfit != null) && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
              {pos.stopLoss != null && (
                <div style={{ background: "var(--red-dim)", padding: "8px 10px", border: "1px solid rgba(239,68,68,0.1)" }}>
                  <div style={{ fontSize: 6, color: "var(--red)", letterSpacing: "0.14em", marginBottom: 4 }}>STOP LOSS</div>
                  <div style={{ fontSize: 13, color: "var(--red)", fontWeight: 600 }}>${pos.stopLoss.toFixed(2)}</div>
                  {pos.currentPrice != null && (
                    <div style={{ fontSize: 8, color: "#64748B", marginTop: 2 }}>
                      {((pos.stopLoss - pos.currentPrice) / pos.currentPrice * 100).toFixed(1)}% from current
                    </div>
                  )}
                </div>
              )}
              {pos.takeProfit != null && (
                <div style={{ background: "var(--green-dim)", padding: "8px 10px", border: "1px solid rgba(34,197,94,0.1)" }}>
                  <div style={{ fontSize: 6, color: "var(--green)", letterSpacing: "0.14em", marginBottom: 4 }}>TAKE PROFIT</div>
                  <div style={{ fontSize: 13, color: "var(--green)", fontWeight: 600 }}>${pos.takeProfit.toFixed(2)}</div>
                  {pos.currentPrice != null && (
                    <div style={{ fontSize: 8, color: "#64748B", marginTop: 2 }}>
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
                    ? `rgba(34,197,94,${0.15 + (h2 / 20) * 0.35})`
                    : `rgba(239,68,68,${0.15 + (h2 / 20) * 0.35})`,
                }} />
              );
            })}
          </div>
        </div>

        <div style={{ height: 1, background: `linear-gradient(90deg,transparent,${col}33,transparent)` }} />
        <div style={{
          padding: "6px 0", textAlign: "center", fontSize: 8, color: "#475569",
          letterSpacing: "0.12em", background: "rgba(255,255,255,0.01)",
          position: "sticky", bottom: 0,
        }}>
          ESC OR CLICK OUTSIDE TO CLOSE
        </div>
      </div>
    </div>
  );
}
