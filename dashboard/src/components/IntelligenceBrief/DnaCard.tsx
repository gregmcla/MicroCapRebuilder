/** Strategy DNA: trading style, DNA prose, factor weights, ETF sources. */

import type { IntelligenceBriefData } from "../../lib/types";

const DATA_FONT = "'JetBrains Mono', 'SF Mono', monospace";
const PROSE_FONT = "-apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif";

function SectionHeader({ label, color }: { label: string; color?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
      <span style={{
        fontSize: '10px', fontFamily: PROSE_FONT,
        fontWeight: 600, letterSpacing: '0.1em', color: color ?? '#5a5a78',
        textTransform: 'uppercase' as const, whiteSpace: 'nowrap' as const,
      }}>
        {label}
      </span>
      <div style={{ flex: 1, height: '1px', background: 'linear-gradient(90deg, rgba(255,255,255,0.08) 0%, transparent 100%)' }} />
    </div>
  );
}

function formatFactor(name: string): string {
  return name.replace(/_/g, " ");
}

interface Props { brief?: IntelligenceBriefData }

export default function DnaCard({ brief }: Props) {
  const config = brief?.config ?? {};

  // Config shape: strategy_dna at top level, trading_style at top level,
  // scoring.default_weights for factor weights, universe.sources.etf_holdings.etfs for ETFs
  const tradingStyle = (config.trading_style as string) ??
    ((config as Record<string, unknown>).strategy as Record<string, unknown>)?.trading_style as string ??
    (config.ai_driven ? "AI-Driven" : null);
  const dna = (config.strategy_dna as string) ??
    ((config as Record<string, unknown>).strategy as Record<string, unknown>)?.dna ??
    ((config as Record<string, unknown>).strategy as Record<string, unknown>)?.ai_prompt ??
    null;

  const scoring = (config.scoring ?? {}) as Record<string, unknown>;
  const defaultWeights = (scoring.default_weights ?? {}) as Record<string, number>;
  const weightEntries = Object.entries(defaultWeights).sort((a, b) => b[1] - a[1]);

  const universe = (config.universe ?? {}) as Record<string, unknown>;
  const sources = (universe.sources ?? {}) as Record<string, unknown>;
  const etfHoldings = (sources.etf_holdings ?? {}) as Record<string, unknown>;
  const etfs = (etfHoldings.etfs ?? []) as string[];

  const hasConfig = config && Object.keys(config).length > 0;

  return (
    <div style={{
      background: 'rgba(0,0,0,0.25)',
      border: '1px solid rgba(255,255,255,0.05)',
      borderRadius: '8px',
      padding: '16px 20px',
      boxShadow: 'inset 0 2px 8px rgba(0,0,0,0.4)',
    }}>
      <SectionHeader label="Strategy DNA" color="#5a5a78" />

      {!hasConfig ? (
        <p style={{
          fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontFamily: PROSE_FONT,
          margin: 0,
        }}>
          No config available
        </p>
      ) : (
        <>
          {/* Trading style pill */}
          {tradingStyle && (
            <div style={{ marginBottom: '12px' }}>
              <span style={{
                fontSize: '10px', padding: '2px 8px', borderRadius: '4px',
                background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.5)',
                border: '1px solid rgba(255,255,255,0.08)',
                fontFamily: DATA_FONT,
              }}>
                {tradingStyle}
              </span>
            </div>
          )}

          {/* DNA prose */}
          {dna && (
            <p style={{
              fontSize: '11px', fontFamily: PROSE_FONT, color: 'rgba(255,255,255,0.5)',
              lineHeight: 1.6, marginBottom: '12px', marginTop: 0,
            }}>
              {dna}
            </p>
          )}

          {/* Factor weights */}
          {weightEntries.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '6px', marginBottom: etfs.length > 0 ? '12px' : '0' }}>
              {weightEntries.map(([factor, weight]) => (
                <div key={factor} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    fontSize: '10px', fontFamily: PROSE_FONT, color: 'rgba(255,255,255,0.5)',
                    width: '90px', flexShrink: 0,
                  }}>
                    {formatFactor(factor)}
                  </span>
                  <div style={{
                    flex: 1, height: '3px', background: 'rgba(255,255,255,0.06)',
                    borderRadius: '2px', overflow: 'hidden',
                  }}>
                    <div style={{
                      height: '100%', borderRadius: '2px',
                      background: 'rgba(124,92,252,0.5)',
                      width: `${weight * 100}%`,
                    }} />
                  </div>
                  <span style={{
                    fontSize: '10px', fontFamily: DATA_FONT, color: 'rgba(255,255,255,0.35)',
                    width: '32px', textAlign: 'right' as const, flexShrink: 0,
                  }}>
                    {(weight * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* ETF badges */}
          {etfs.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: '4px' }}>
              {etfs.map(etf => (
                <span key={etf} style={{
                  fontSize: '9px', padding: '1px 5px', borderRadius: '3px',
                  background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.35)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  fontFamily: DATA_FONT,
                }}>
                  {etf}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
