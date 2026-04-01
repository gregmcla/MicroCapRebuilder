/** Portfolio Composition: sector breakdown, concentration, near-stop alerts. */

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

interface Props { brief?: IntelligenceBriefData }

export default function CompositionPanel({ brief }: Props) {
  const sectorMap = brief?.sector_breakdown ?? {};
  const sectorEntries = Object.entries(sectorMap)
    .map(([sector, data]) => ({ sector, pct: data.pct, count: data.count }))
    .sort((a, b) => b.pct - a.pct);

  const top3 = brief?.top3_concentration_pct ?? 0;
  const nearStop = brief?.positions_near_stop ?? [];
  const hasSectors = sectorEntries.length > 0;

  const MAX_SECTORS = 6;
  const visibleSectors = sectorEntries.slice(0, MAX_SECTORS);
  const hiddenCount = sectorEntries.length - MAX_SECTORS;

  return (
    <div style={{
      background: 'rgba(255,255,255,0.028)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderTop: '1px solid rgba(255,255,255,0.11)',
      borderLeft: '3px solid #60a5fa',
      borderRadius: '8px',
      padding: '16px 20px',
      boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 4px rgba(0,0,0,0.35)',
    }}>
      <SectionHeader label="Composition" color="#60a5fa" />

      {!hasSectors ? (
        <div style={{
          display: 'flex', justifyContent: 'center', alignItems: 'center',
          padding: '20px 0',
        }}>
          <span style={{
            fontSize: '10px', letterSpacing: '0.15em', color: 'rgba(255,255,255,0.2)',
            fontFamily: PROSE_FONT, fontWeight: 600, textTransform: 'uppercase' as const,
          }}>
            No Positions
          </span>
        </div>
      ) : (
        <>
          {/* Sector bars */}
          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '8px' }}>
            {visibleSectors.map(({ sector, pct, count }) => (
              <div key={sector} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  fontSize: '10px', fontFamily: PROSE_FONT, color: 'rgba(255,255,255,0.7)',
                  width: '90px', textOverflow: 'ellipsis', overflow: 'hidden',
                  whiteSpace: 'nowrap' as const, flexShrink: 0,
                }}>
                  {sector}
                </span>
                <div style={{
                  flex: 1, height: '4px', background: 'rgba(255,255,255,0.06)',
                  borderRadius: '2px', overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%', borderRadius: '2px', background: '#60a5fa',
                    width: `${pct}%`,
                    transition: 'width 600ms cubic-bezier(0.25, 1, 0.5, 1)',
                  }} />
                </div>
                <span style={{
                  fontSize: '10px', fontFamily: DATA_FONT, color: 'rgba(255,255,255,0.5)',
                  width: '36px', textAlign: 'right' as const, flexShrink: 0,
                }}>
                  {pct.toFixed(0)}%
                </span>
                <span style={{
                  fontSize: '9px', color: 'rgba(255,255,255,0.3)', marginLeft: '4px',
                  fontFamily: DATA_FONT, flexShrink: 0,
                }}>
                  ({count})
                </span>
              </div>
            ))}
          </div>

          {hiddenCount > 0 && (
            <p style={{
              fontSize: '10px', color: 'rgba(255,255,255,0.3)', fontFamily: PROSE_FONT,
              margin: '6px 0 0 0',
            }}>
              +{hiddenCount} more
            </p>
          )}

          {/* Concentration warning + near-stop */}
          {(top3 > 60 || nearStop.length > 0) && (
            <div style={{ marginTop: '12px', display: 'flex', flexWrap: 'wrap' as const, gap: '8px', alignItems: 'center' }}>
              {top3 > 60 && (
                <span style={{
                  fontSize: '10px', padding: '2px 8px', borderRadius: '4px',
                  background: 'rgba(249,115,22,0.12)', color: '#f97316',
                  border: '1px solid rgba(249,115,22,0.2)',
                  fontFamily: DATA_FONT, fontWeight: 600,
                }}>
                  {'\u26A0'} TOP 3: {top3.toFixed(0)}%
                </span>
              )}
              {nearStop.length > 0 && (
                <span style={{
                  fontSize: '10px', color: '#f97316', fontFamily: PROSE_FONT,
                }}>
                  {nearStop.length} near stop-loss
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
