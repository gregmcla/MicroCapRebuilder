/** Trade Intelligence: win rate, profit factor, hold time, working/struggling factors, most traded. */

import type { IntelligenceBriefData } from "../../lib/types";

const DATA_FONT = "var(--font-mono)";
const PROSE_FONT = "var(--font-sans)";

function SectionHeader({ label, color }: { label: string; color?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
      <span style={{
        fontSize: '10px', fontFamily: PROSE_FONT,
        fontWeight: 600, letterSpacing: '0.1em', color: color ?? 'var(--text-dim)',
        textTransform: 'uppercase' as const, whiteSpace: 'nowrap' as const,
      }}>
        {label}
      </span>
      <div style={{ flex: 1, height: '1px', background: 'linear-gradient(90deg, var(--border) 0%, transparent 100%)' }} />
    </div>
  );
}

function formatFactor(name: string): string {
  return name.replace(/_/g, " ");
}

interface Props { brief?: IntelligenceBriefData }

export default function TradeIntelligence({ brief }: Props) {
  // Extract trade stats from the health "Trading Edge" component
  const tradingEdge = brief?.health?.components?.find(
    (c: { name: string }) => c.name === "Trading Edge"
  );
  const details = (tradingEdge?.details ?? {}) as Record<string, unknown>;

  const winRate = details.win_rate as number | undefined;
  const profitFactor = details.profit_factor as number | undefined;
  const avgHoldDays = brief?.avg_hold_days ?? 0;
  const mostTraded = brief?.most_traded_tickers ?? [];

  // Working / struggling from health
  const workingFactors = brief?.health?.what_working ?? [];
  const strugglingFactors = brief?.health?.what_struggling ?? [];

  const hasData = (winRate != null && winRate > 0) ||
    (profitFactor != null && profitFactor > 0) ||
    avgHoldDays > 0;

  // Color helpers — win_rate from API is already a percentage (e.g. 42.9 = 42.9%)
  const winRateColor = winRate != null
    ? (winRate >= 55 ? 'var(--green)' : winRate >= 45 ? 'var(--amber)' : 'var(--red)')
    : 'var(--text-dim)';

  const pfColor = profitFactor != null
    ? (profitFactor > 1.5 ? 'var(--green)' : profitFactor >= 1 ? 'var(--amber)' : 'var(--red)')
    : 'var(--text-dim)';

  const placeholder = '\u2014';

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderTop: '1px solid var(--border-hover)',
      borderLeft: '3px solid var(--accent)',
      borderRadius: 'var(--radius)',
      padding: '16px 20px',
      boxShadow: '0 1px 4px rgba(0,0,0,0.35)',
    }}>
      <SectionHeader label="Trade Intelligence" color="var(--accent)" />

      {/* 3-stat row */}
      <div style={{ display: 'flex', gap: '24px', marginBottom: '0' }}>
        {/* Win Rate */}
        <div style={{ display: 'flex', flexDirection: 'column' as const }}>
          <span style={{
            fontFamily: PROSE_FONT, fontSize: '10px', fontWeight: 500,
            letterSpacing: '0.08em', color: 'var(--text-dim)', textTransform: 'uppercase' as const,
            marginBottom: '4px',
          }}>
            Win Rate
          </span>
          <span style={{
            fontFamily: DATA_FONT, fontSize: '22px', fontWeight: 600,
            color: hasData ? winRateColor : 'rgba(255,255,255,0.2)',
          }}>
            {winRate != null && winRate > 0
              ? `${winRate.toFixed(0)}%`
              : placeholder}
          </span>
        </div>

        {/* Profit Factor */}
        <div style={{ display: 'flex', flexDirection: 'column' as const }}>
          <span style={{
            fontFamily: PROSE_FONT, fontSize: '10px', fontWeight: 500,
            letterSpacing: '0.08em', color: 'var(--text-dim)', textTransform: 'uppercase' as const,
            marginBottom: '4px',
          }}>
            Profit Factor
          </span>
          <span style={{
            fontFamily: DATA_FONT, fontSize: '22px', fontWeight: 600,
            color: hasData ? pfColor : 'rgba(255,255,255,0.2)',
          }}>
            {profitFactor != null && profitFactor > 0
              ? profitFactor.toFixed(2)
              : placeholder}
          </span>
        </div>

        {/* Avg Hold */}
        <div style={{ display: 'flex', flexDirection: 'column' as const }}>
          <span style={{
            fontFamily: PROSE_FONT, fontSize: '10px', fontWeight: 500,
            letterSpacing: '0.08em', color: 'var(--text-dim)', textTransform: 'uppercase' as const,
            marginBottom: '4px',
          }}>
            Avg Hold
          </span>
          <span style={{
            fontFamily: DATA_FONT, fontSize: '22px', fontWeight: 600,
            color: hasData ? 'var(--text-primary)' : 'var(--text-dim)',
          }}>
            {avgHoldDays > 0 ? `${Math.round(avgHoldDays)}d` : placeholder}
          </span>
        </div>
      </div>

      {hasData && (workingFactors.length > 0 || strugglingFactors.length > 0 || mostTraded.length > 0) && (
        <>
          {/* Divider */}
          <div style={{ height: '1px', background: 'var(--bg-elevated)', margin: '12px 0' }} />

          {/* Working */}
          {workingFactors.length > 0 && (
            <div style={{ marginBottom: strugglingFactors.length > 0 || mostTraded.length > 0 ? '8px' : '0' }}>
              <span style={{
                fontFamily: PROSE_FONT, fontSize: '9px', fontWeight: 600,
                letterSpacing: '0.1em', color: 'var(--green)',
                textTransform: 'uppercase' as const, display: 'block', marginBottom: '4px',
              }}>
                Working
              </span>
              {workingFactors.slice(0, 3).map((item, i) => (
                <div key={i} style={{
                  fontSize: '10px', color: 'var(--text-secondary)', fontFamily: PROSE_FONT,
                  lineHeight: 1.5, paddingLeft: '8px', borderLeft: '2px solid rgba(34,197,94,0.3)',
                  marginBottom: '3px',
                }}>
                  {item}
                </div>
              ))}
            </div>
          )}

          {/* Struggling */}
          {strugglingFactors.length > 0 && (
            <div style={{ marginBottom: mostTraded.length > 0 ? '8px' : '0' }}>
              <span style={{
                fontFamily: PROSE_FONT, fontSize: '9px', fontWeight: 600,
                letterSpacing: '0.1em', color: 'var(--red)',
                textTransform: 'uppercase' as const, display: 'block', marginBottom: '4px',
              }}>
                Struggling
              </span>
              {strugglingFactors.slice(0, 3).map((item, i) => (
                <div key={i} style={{
                  fontSize: '10px', color: 'var(--text-secondary)', fontFamily: PROSE_FONT,
                  lineHeight: 1.5, paddingLeft: '8px', borderLeft: '2px solid rgba(239,68,68,0.3)',
                  marginBottom: '3px',
                }}>
                  {item}
                </div>
              ))}
            </div>
          )}

          {/* Most traded */}
          {mostTraded.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' as const }}>
              <span style={{
                fontFamily: PROSE_FONT, fontSize: '9px', fontWeight: 600,
                letterSpacing: '0.1em', color: 'var(--text-dim)',
                textTransform: 'uppercase' as const, whiteSpace: 'nowrap' as const,
              }}>
                Most Traded
              </span>
              {mostTraded.map(({ ticker }) => (
                <span key={ticker} style={{
                  fontSize: '10px', padding: '2px 8px', borderRadius: '4px',
                  background: 'var(--bg-elevated)', color: 'var(--text-secondary)',
                  border: '1px solid var(--border)',
                  fontFamily: DATA_FONT, fontWeight: 600,
                }}>
                  {ticker}
                </span>
              ))}
            </div>
          )}
        </>
      )}

      {/* Empty state note */}
      {!hasData && (
        <p style={{
          fontSize: '10px', color: 'var(--text-dim)', fontStyle: 'italic',
          fontFamily: PROSE_FONT, margin: '12px 0 0 0',
        }}>
          Trade history builds as positions are closed
        </p>
      )}
    </div>
  );
}
