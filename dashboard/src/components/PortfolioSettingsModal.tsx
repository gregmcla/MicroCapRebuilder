/**
 * PortfolioSettingsModal — 4-tab config editor for an existing portfolio.
 * Tabs: Risk · Strategy · Universe & Sectors · Advanced
 * On save: deep-merges changes → auto-triggers watchlist rescan.
 */

import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { usePortfolioStore } from "../lib/store";

// ── Constants mirrored from CreatePortfolioModal ──────────────────────────────

const ALL_SECTORS = [
  "Technology", "Communication Services", "Real Estate", "Healthcare",
  "Industrials", "Financial Services", "Consumer Cyclical", "Consumer Defensive",
  "Energy", "Utilities", "Basic Materials",
];

const TRADING_STYLES = [
  { id: "aggressive_momentum", label: "Aggressive Momentum", desc: "High conviction, momentum-driven, larger positions" },
  { id: "balanced",            label: "Balanced",            desc: "Mix of momentum and value, moderate risk" },
  { id: "conservative_value",  label: "Conservative Value",  desc: "Value-focused, tighter stops, smaller positions" },
  { id: "mean_reversion",      label: "Mean Reversion",      desc: "Buy dips, sell recoveries, high RSI sensitivity" },
];

const STYLE_WEIGHTS: Record<string, Record<string, number>> = {
  aggressive_momentum: { momentum: 0.35, volatility: 0.05, volume: 0.20, relative_strength: 0.25, mean_reversion: 0.05, rsi: 0.10 },
  balanced:            { momentum: 0.20, volatility: 0.15, volume: 0.15, relative_strength: 0.20, mean_reversion: 0.15, rsi: 0.15 },
  conservative_value:  { momentum: 0.10, volatility: 0.20, volume: 0.10, relative_strength: 0.15, mean_reversion: 0.30, rsi: 0.15 },
  mean_reversion:      { momentum: 0.10, volatility: 0.15, volume: 0.15, relative_strength: 0.10, mean_reversion: 0.35, rsi: 0.15 },
};

const UNIVERSES = [
  { id: "microcap", label: "Micro Cap",  desc: "$50M–$300M market cap" },
  { id: "smallcap", label: "Small Cap",  desc: "$300M–$2B market cap" },
  { id: "midcap",   label: "Mid Cap",    desc: "$2B–$10B market cap" },
  { id: "largecap", label: "Large Cap",  desc: "$10B+ market cap" },
  { id: "allcap",   label: "Everything", desc: "No market cap filter" },
];

const TABS = ["Risk", "Strategy", "Universe & Sectors", "Advanced"] as const;
type Tab = typeof TABS[number];

// ── Shared UI primitives ──────────────────────────────────────────────────────

function Label({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ fontSize: "11px", letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-0)", fontWeight: 600 }}>
      {children}
    </span>
  );
}

function Value({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono tabular-nums" style={{ fontSize: "12px", color: "var(--accent)", minWidth: "36px", textAlign: "right" }}>
      {children}
    </span>
  );
}

function SettingRow({ label, value, children }: { label: string; value: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <Label>{label}</Label>
        <Value>{value}</Value>
      </div>
      {children}
    </div>
  );
}

function Slider({
  min, max, step = 1, value, onChange,
}: { min: number; max: number; step?: number; value: number; onChange: (v: number) => void }) {
  return (
    <input
      type="range"
      min={min} max={max} step={step}
      value={value}
      onChange={e => onChange(Number(e.target.value))}
      style={{
        width: "100%",
        accentColor: "var(--accent)",
        height: "4px",
        cursor: "pointer",
      }}
    />
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: "10px", letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--text-0)", fontWeight: 700, borderBottom: "1px solid var(--border-0)", paddingBottom: "6px", marginBottom: "12px" }}>
      {children}
    </div>
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      style={{
        width: "36px", height: "18px",
        borderRadius: "9px",
        background: checked ? "var(--accent)" : "var(--border-1)",
        border: "none",
        cursor: "pointer",
        position: "relative",
        transition: "background 0.2s",
        flexShrink: 0,
      }}
    >
      <span style={{
        position: "absolute",
        top: "2px",
        left: checked ? "18px" : "2px",
        width: "14px", height: "14px",
        borderRadius: "50%",
        background: "white",
        transition: "left 0.2s",
      }} />
    </button>
  );
}

// ── Tab contents ──────────────────────────────────────────────────────────────

function RiskTab({ draft, onChange }: { draft: ConfigDraft; onChange: (path: string[], value: unknown) => void }) {
  const risk = draft.risk;
  return (
    <div className="flex flex-col gap-5">
      <SectionTitle>Position Risk</SectionTitle>
      <SettingRow label="Stop Loss" value={`${risk.stop_loss_pct}%`}>
        <Slider min={3} max={15} step={0.5} value={risk.stop_loss_pct} onChange={v => onChange(["risk", "stop_loss_pct"], v)} />
      </SettingRow>
      <SettingRow label="Risk Per Trade" value={`${risk.risk_per_trade_pct}%`}>
        <Slider min={1} max={10} step={0.5} value={risk.risk_per_trade_pct} onChange={v => onChange(["risk", "risk_per_trade_pct"], v)} />
      </SettingRow>
      <SettingRow label="Max Position Size" value={`${risk.max_position_pct}%`}>
        <Slider min={4} max={20} step={1} value={risk.max_position_pct} onChange={v => onChange(["risk", "max_position_pct"], v)} />
      </SettingRow>
      <SettingRow label="Take Profit Target" value={`${risk.take_profit_pct}%`}>
        <Slider min={10} max={40} step={1} value={risk.take_profit_pct} onChange={v => onChange(["risk", "take_profit_pct"], v)} />
      </SettingRow>

      <SectionTitle>Capital Preservation</SectionTitle>
      <SettingRow label="Drawdown Trigger" value={`${risk.drawdown_threshold_pct}%`}>
        <Slider min={5} max={25} step={1} value={risk.drawdown_threshold_pct} onChange={v => onChange(["risk", "drawdown_threshold_pct"], v)} />
      </SettingRow>
      <SettingRow label="Risk Score Trigger" value={String(risk.risk_score_threshold)}>
        <Slider min={20} max={60} step={5} value={risk.risk_score_threshold} onChange={v => onChange(["risk", "risk_score_threshold"], v)} />
      </SettingRow>
    </div>
  );
}

function StrategyTab({ draft, onChange }: { draft: ConfigDraft; onChange: (path: string[], value: unknown) => void }) {
  const weights = draft.weights;
  const total = Object.values(weights).reduce((s, v) => s + v, 0);
  const valid = Math.abs(total - 1.0) < 0.01;

  function applyPreset(styleId: string) {
    const w = STYLE_WEIGHTS[styleId];
    if (w) {
      Object.entries(w).forEach(([k, v]) => onChange(["weights", k], v));
      onChange(["trading_style"], styleId);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <SectionTitle>Trading Style Preset</SectionTitle>
      <div className="grid grid-cols-2 gap-2">
        {TRADING_STYLES.map(s => (
          <button
            key={s.id}
            onClick={() => applyPreset(s.id)}
            style={{
              background: draft.trading_style === s.id ? "rgba(var(--accent-rgb, 99,102,241), 0.15)" : "var(--surface-0)",
              border: `1px solid ${draft.trading_style === s.id ? "var(--accent)" : "var(--border-1)"}`,
              borderRadius: "6px",
              padding: "10px 12px",
              textAlign: "left",
              cursor: "pointer",
              transition: "all 0.15s",
            }}
          >
            <div style={{ fontSize: "12px", fontWeight: 600, color: draft.trading_style === s.id ? "var(--accent)" : "var(--text-1)", marginBottom: "3px" }}>
              {s.label}
            </div>
            <div style={{ fontSize: "10px", color: "var(--text-0)", lineHeight: 1.4 }}>{s.desc}</div>
          </button>
        ))}
      </div>

      <SectionTitle>
        Scoring Weights
        <span style={{ float: "right", color: valid ? "var(--green)" : "var(--red)", letterSpacing: 0, fontFamily: "monospace" }}>
          {(total * 100).toFixed(0)}% {valid ? "✓" : "≠ 100%"}
        </span>
      </SectionTitle>
      {(["momentum", "volatility", "volume", "relative_strength", "mean_reversion", "rsi"] as const).map(factor => (
        <SettingRow key={factor} label={factor.replace(/_/g, " ")} value={`${Math.round(weights[factor] * 100)}%`}>
          <Slider min={0} max={60} step={1} value={Math.round(weights[factor] * 100)} onChange={v => onChange(["weights", factor], v / 100)} />
        </SettingRow>
      ))}
    </div>
  );
}

function UniverseTab({ draft, onChange }: { draft: ConfigDraft; onChange: (path: string[], value: unknown) => void }) {
  const toggleSector = (sector: string) => {
    const cur = draft.sectors;
    const next = cur.includes(sector) ? cur.filter(s => s !== sector) : [...cur, sector];
    onChange(["sectors"], next);
  };

  return (
    <div className="flex flex-col gap-5">
      <SectionTitle>Universe Preset</SectionTitle>
      <div className="grid grid-cols-3 gap-2">
        {UNIVERSES.map(u => (
          <button
            key={u.id}
            onClick={() => onChange(["universe"], u.id)}
            style={{
              background: draft.universe === u.id ? "rgba(var(--accent-rgb, 99,102,241), 0.15)" : "var(--surface-0)",
              border: `1px solid ${draft.universe === u.id ? "var(--accent)" : "var(--border-1)"}`,
              borderRadius: "6px",
              padding: "9px 10px",
              textAlign: "left",
              cursor: "pointer",
              transition: "all 0.15s",
            }}
          >
            <div style={{ fontSize: "11px", fontWeight: 600, color: draft.universe === u.id ? "var(--accent)" : "var(--text-1)", marginBottom: "2px" }}>{u.label}</div>
            <div style={{ fontSize: "10px", color: "var(--text-0)" }}>{u.desc}</div>
          </button>
        ))}
      </div>

      <SectionTitle>
        Sector Filter
        <span style={{ float: "right", fontSize: "10px", letterSpacing: 0, fontWeight: 400, color: "var(--text-0)" }}>
          {draft.sectors.length === 0 ? "all sectors" : `${draft.sectors.length} selected`}
        </span>
      </SectionTitle>
      <div className="flex flex-wrap gap-2">
        {ALL_SECTORS.map(sector => {
          const active = draft.sectors.includes(sector);
          return (
            <button
              key={sector}
              onClick={() => toggleSector(sector)}
              style={{
                fontSize: "11px",
                fontWeight: 500,
                padding: "4px 10px",
                borderRadius: "20px",
                border: `1px solid ${active ? "var(--accent)" : "var(--border-1)"}`,
                background: active ? "rgba(var(--accent-rgb, 99,102,241), 0.12)" : "transparent",
                color: active ? "var(--accent)" : "var(--text-0)",
                cursor: "pointer",
                transition: "all 0.12s",
              }}
            >
              {sector}
            </button>
          );
        })}
      </div>
      <p style={{ fontSize: "10px", color: "var(--text-0)", marginTop: "-8px" }}>
        No sectors selected = scan all sectors. Saving will rescan the watchlist.
      </p>

      <SectionTitle>Scan Types</SectionTitle>
      {([
        ["momentum_breakouts", "Momentum Breakouts"],
        ["oversold_bounces",   "Oversold Bounces"],
        ["sector_leaders",     "Sector Leaders"],
        ["volume_anomalies",   "Volume Anomalies"],
      ] as [keyof ConfigDraft["scan_types"], string][]).map(([key, label]) => (
        <div key={key} className="flex items-center justify-between">
          <Label>{label}</Label>
          <Toggle checked={draft.scan_types[key]} onChange={v => onChange(["scan_types", key], v)} />
        </div>
      ))}
    </div>
  );
}

function AdvancedTab({ draft, onChange }: { draft: ConfigDraft; onChange: (path: string[], value: unknown) => void }) {
  return (
    <div className="flex flex-col gap-5">
      <SectionTitle>
        Rotation
        <span style={{ float: "right" }}>
          <Toggle checked={draft.rotation.enabled} onChange={v => onChange(["rotation", "enabled"], v)} />
        </span>
      </SectionTitle>
      <SettingRow label="Min Score Upgrade Gap" value={String(draft.rotation.min_upgrade_score_gap)}>
        <Slider min={5} max={40} step={1} value={draft.rotation.min_upgrade_score_gap} onChange={v => onChange(["rotation", "min_upgrade_score_gap"], v)} />
      </SettingRow>
      <SettingRow label="Max Rotations Per Cycle" value={String(draft.rotation.max_rotations_per_cycle)}>
        <Slider min={1} max={5} step={1} value={draft.rotation.max_rotations_per_cycle} onChange={v => onChange(["rotation", "max_rotations_per_cycle"], v)} />
      </SettingRow>
      <SettingRow label="Min Days Held Before Rotation" value={String(draft.rotation.min_held_days)}>
        <Slider min={1} max={30} step={1} value={draft.rotation.min_held_days} onChange={v => onChange(["rotation", "min_held_days"], v)} />
      </SettingRow>
      <SettingRow label="Max Loss % for Rotation" value={`${draft.rotation.max_unrealized_loss_pct}%`}>
        <Slider min={-40} max={0} step={1} value={draft.rotation.max_unrealized_loss_pct} onChange={v => onChange(["rotation", "max_unrealized_loss_pct"], v)} />
      </SettingRow>

      <SectionTitle>Min Score Thresholds</SectionTitle>
      <SettingRow label="Bull Market" value={String(draft.thresholds.bull)}>
        <Slider min={20} max={70} step={5} value={draft.thresholds.bull} onChange={v => onChange(["thresholds", "bull"], v)} />
      </SettingRow>
      <SettingRow label="Sideways Market" value={String(draft.thresholds.sideways)}>
        <Slider min={30} max={75} step={5} value={draft.thresholds.sideways} onChange={v => onChange(["thresholds", "sideways"], v)} />
      </SettingRow>
      <SettingRow label="Bear Market" value={String(draft.thresholds.bear)}>
        <Slider min={40} max={85} step={5} value={draft.thresholds.bear} onChange={v => onChange(["thresholds", "bear"], v)} />
      </SettingRow>

      <SectionTitle>RSI Filter</SectionTitle>
      <SettingRow label="Hard Filter Above RSI" value={String(draft.rsi_hard_filter)}>
        <Slider min={70} max={99} step={1} value={draft.rsi_hard_filter} onChange={v => onChange(["rsi_hard_filter"], v)} />
      </SettingRow>
      <p style={{ fontSize: "10px", color: "var(--text-0)", marginTop: "-8px" }}>
        Stocks above this RSI are excluded from buy proposals entirely.
      </p>
    </div>
  );
}

// ── Draft state (typed extraction from raw config) ────────────────────────────

interface ConfigDraft {
  risk: {
    stop_loss_pct: number;
    risk_per_trade_pct: number;
    max_position_pct: number;
    take_profit_pct: number;
    drawdown_threshold_pct: number;
    risk_score_threshold: number;
  };
  weights: Record<string, number>;
  trading_style: string;
  universe: string;
  sectors: string[];
  scan_types: { momentum_breakouts: boolean; oversold_bounces: boolean; sector_leaders: boolean; volume_anomalies: boolean };
  rotation: { enabled: boolean; min_upgrade_score_gap: number; max_rotations_per_cycle: number; min_held_days: number; max_unrealized_loss_pct: number };
  thresholds: { bull: number; sideways: number; bear: number };
  rsi_hard_filter: number;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractDraft(cfg: any): ConfigDraft {
  return {
    risk: {
      stop_loss_pct:       cfg.default_stop_loss_pct     ?? 8,
      risk_per_trade_pct:  cfg.risk_per_trade_pct        ?? 3,
      max_position_pct:    cfg.max_position_pct           ?? 10,
      take_profit_pct:     cfg.default_take_profit_pct   ?? 20,
      drawdown_threshold_pct: cfg.risk_management?.capital_preservation?.triggers?.drawdown_threshold_pct ?? 10,
      risk_score_threshold:   cfg.risk_management?.capital_preservation?.triggers?.risk_score_threshold   ?? 40,
    },
    weights: cfg.scoring?.default_weights ?? {
      momentum: 0.2, volatility: 0.15, volume: 0.15, relative_strength: 0.2, mean_reversion: 0.15, rsi: 0.15,
    },
    trading_style: cfg.strategy?.trading_style ?? "balanced",
    universe:      cfg.strategy?.universe      ?? "allcap",
    sectors:       cfg.discovery?.sector_filter ?? [],
    scan_types: {
      momentum_breakouts: cfg.discovery?.scan_types?.momentum_breakouts ?? false,
      oversold_bounces:   cfg.discovery?.scan_types?.oversold_bounces   ?? true,
      sector_leaders:     cfg.discovery?.scan_types?.sector_leaders     ?? false,
      volume_anomalies:   cfg.discovery?.scan_types?.volume_anomalies   ?? true,
    },
    rotation: {
      enabled:                   cfg.enhanced_trading?.rotation?.enabled                   ?? true,
      min_upgrade_score_gap:     cfg.enhanced_trading?.rotation?.min_upgrade_score_gap     ?? 15,
      max_rotations_per_cycle:   cfg.enhanced_trading?.rotation?.max_rotations_per_cycle   ?? 3,
      min_held_days:             cfg.enhanced_trading?.rotation?.min_held_days_before_rotation ?? 3,
      max_unrealized_loss_pct:   cfg.enhanced_trading?.rotation?.max_unrealized_loss_pct_for_rotation ?? -15,
    },
    thresholds: {
      bull:     cfg.scoring?.min_score_threshold?.BULL     ?? 40,
      sideways: cfg.scoring?.min_score_threshold?.SIDEWAYS ?? 50,
      bear:     cfg.scoring?.min_score_threshold?.BEAR     ?? 60,
    },
    rsi_hard_filter: cfg.scoring?.rsi?.hard_filter_above ?? 85,
  };
}

function draftToChanges(draft: ConfigDraft): Record<string, unknown> {
  return {
    default_stop_loss_pct:   draft.risk.stop_loss_pct,
    risk_per_trade_pct:      draft.risk.risk_per_trade_pct,
    max_position_pct:        draft.risk.max_position_pct,
    default_take_profit_pct: draft.risk.take_profit_pct,
    risk_management: {
      capital_preservation: {
        triggers: {
          drawdown_threshold_pct: draft.risk.drawdown_threshold_pct,
          risk_score_threshold:   draft.risk.risk_score_threshold,
        },
      },
    },
    scoring: {
      default_weights:     draft.weights,
      min_score_threshold: { BULL: draft.thresholds.bull, SIDEWAYS: draft.thresholds.sideways, BEAR: draft.thresholds.bear },
      rsi: { hard_filter_above: draft.rsi_hard_filter },
    },
    strategy: { trading_style: draft.trading_style, universe: draft.universe },
    discovery: {
      sector_filter: draft.sectors,
      scan_types:    draft.scan_types,
    },
    enhanced_trading: {
      rotation: {
        enabled:                          draft.rotation.enabled,
        min_upgrade_score_gap:            draft.rotation.min_upgrade_score_gap,
        max_rotations_per_cycle:          draft.rotation.max_rotations_per_cycle,
        min_held_days_before_rotation:    draft.rotation.min_held_days,
        max_unrealized_loss_pct_for_rotation: draft.rotation.max_unrealized_loss_pct,
      },
    },
  };
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function PortfolioSettingsModal({ onClose }: { onClose: () => void }) {
  const portfolioId = usePortfolioStore(s => s.activePortfolioId);
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>("Risk");
  const [draft, setDraft] = useState<ConfigDraft | null>(null);
  const [saved, setSaved] = useState(false);

  const { data: rawConfig, isLoading } = useQuery({
    queryKey: ["portfolioConfig", portfolioId],
    queryFn: () => api.getPortfolioConfig(portfolioId),
    staleTime: 0,
  });

  useEffect(() => {
    if (rawConfig && !draft) {
      setDraft(extractDraft(rawConfig));
    }
  }, [rawConfig, draft]);

  const mutation = useMutation({
    mutationFn: (changes: Record<string, unknown>) => api.updatePortfolioConfig(portfolioId, changes),
    onSuccess: () => {
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ["portfolioState", portfolioId] });
      queryClient.invalidateQueries({ queryKey: ["portfolioConfig", portfolioId] });
      setTimeout(() => {
        setSaved(false);
        onClose();
      }, 1500);
    },
  });

  const handleChange = useCallback((path: string[], value: unknown) => {
    setDraft(prev => {
      if (!prev) return prev;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const next = JSON.parse(JSON.stringify(prev)) as any;
      let node = next;
      for (let i = 0; i < path.length - 1; i++) node = node[path[i]];
      node[path[path.length - 1]] = value;
      return next as ConfigDraft;
    });
  }, []);

  const handleSave = () => {
    if (!draft) return;
    mutation.mutate(draftToChanges(draft));
  };

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          width: "680px",
          maxHeight: "85vh",
          background: "var(--bg-elevated)",
          border: "1px solid var(--border-1)",
          borderRadius: "10px",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 24px 80px rgba(0,0,0,0.6)",
        }}
      >
        {/* Header */}
        <div style={{ padding: "16px 20px 0", borderBottom: "1px solid var(--border-0)" }}>
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 style={{ fontSize: "13px", fontWeight: 700, color: "var(--text-1)", margin: 0 }}>Portfolio Settings</h2>
              <p style={{ fontSize: "10px", color: "var(--text-0)", margin: "2px 0 0" }}>
                Changes apply to future analyses. Watchlist rescans automatically on save.
              </p>
            </div>
            <button
              onClick={onClose}
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-0)", fontSize: "18px", lineHeight: 1, padding: "2px 4px" }}
            >
              ×
            </button>
          </div>

          {/* Tab bar */}
          <div className="flex gap-0">
            {TABS.map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  fontSize: "11px",
                  fontWeight: 600,
                  letterSpacing: "0.04em",
                  padding: "8px 14px",
                  background: "none",
                  border: "none",
                  borderBottom: `2px solid ${activeTab === tab ? "var(--accent)" : "transparent"}`,
                  color: activeTab === tab ? "var(--accent)" : "var(--text-0)",
                  cursor: "pointer",
                  transition: "color 0.15s, border-color 0.15s",
                  marginBottom: "-1px",
                }}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 20px" }}>
          {isLoading || !draft ? (
            <div className="flex items-center justify-center h-32">
              <span style={{ fontSize: "12px", color: "var(--text-0)" }} className="animate-pulse">Loading config…</span>
            </div>
          ) : (
            <>
              {activeTab === "Risk"               && <RiskTab     draft={draft} onChange={handleChange} />}
              {activeTab === "Strategy"           && <StrategyTab draft={draft} onChange={handleChange} />}
              {activeTab === "Universe & Sectors" && <UniverseTab draft={draft} onChange={handleChange} />}
              {activeTab === "Advanced"           && <AdvancedTab draft={draft} onChange={handleChange} />}
            </>
          )}
        </div>

        {/* Footer */}
        <div
          style={{ padding: "12px 20px", borderTop: "1px solid var(--border-0)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--surface-0)" }}
        >
          <span style={{ fontSize: "10px", color: "var(--text-0)" }}>
            {mutation.isError ? (
              <span style={{ color: "var(--red)" }}>Save failed — check API logs</span>
            ) : saved ? (
              <span style={{ color: "var(--green)" }}>✓ Saved · rescanning watchlist…</span>
            ) : (
              "Saving will trigger a background watchlist rescan."
            )}
          </span>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              style={{ padding: "6px 14px", fontSize: "11px", fontWeight: 600, background: "var(--surface-0)", border: "1px solid var(--border-1)", borderRadius: "6px", color: "var(--text-1)", cursor: "pointer" }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={mutation.isPending || saved || !draft}
              style={{
                padding: "6px 18px",
                fontSize: "11px",
                fontWeight: 700,
                background: saved ? "var(--green)" : "var(--accent)",
                border: "none",
                borderRadius: "6px",
                color: "white",
                cursor: mutation.isPending ? "wait" : "pointer",
                opacity: mutation.isPending ? 0.7 : 1,
                transition: "background 0.2s",
              }}
            >
              {mutation.isPending ? "Saving…" : saved ? "Saved ✓" : "Save & Rescan"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
