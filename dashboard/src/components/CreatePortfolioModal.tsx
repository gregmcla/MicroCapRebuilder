/** Multi-step portfolio creation modal with Strategy Wizard and AI Strategy modes. */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { usePortfolioStore } from "../lib/store";
import type { GeneratedStrategy } from "../lib/types";
import StrategyReviewCard from "./StrategyReviewCard";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const UNIVERSES = [
  { id: "microcap", label: "Micro Cap", desc: "<$300M — High volatility, aggressive momentum" },
  { id: "smallcap", label: "Small Cap", desc: "$300M-$2B — Moderate volatility, balanced factors" },
  { id: "midcap", label: "Mid Cap", desc: "$2B-$10B — Lower volatility, mean-reversion bias" },
  { id: "largecap", label: "Large Cap", desc: "$10B+ — Stable, relative-strength focused" },
  { id: "custom", label: "Custom", desc: "User-defined — start from microcap defaults" },
];

const ALL_SECTORS = [
  "Technology", "Communication", "Healthcare", "Financials",
  "Consumer Discretionary", "Consumer Staples", "Industrials",
  "Energy", "Materials", "Utilities", "Real Estate",
];

const TRADING_STYLE_OPTIONS = [
  { id: "aggressive_momentum", label: "Aggressive Momentum", desc: "High momentum + relative strength, tight stops, larger positions" },
  { id: "balanced", label: "Balanced", desc: "Even factor weights, moderate risk, all scan types" },
  { id: "conservative_value", label: "Conservative Value", desc: "Low volatility preference, wide stops, smaller positions" },
  { id: "mean_reversion", label: "Mean Reversion", desc: "Buy dips in quality stocks, oversold bounces, moderate risk" },
];

const STYLE_WEIGHTS: Record<string, Record<string, number>> = {
  aggressive_momentum: { momentum: 0.35, volatility: 0.05, volume: 0.15, relative_strength: 0.25, mean_reversion: 0.05, rsi: 0.15 },
  balanced: { momentum: 0.20, volatility: 0.15, volume: 0.15, relative_strength: 0.20, mean_reversion: 0.15, rsi: 0.15 },
  conservative_value: { momentum: 0.10, volatility: 0.25, volume: 0.10, relative_strength: 0.15, mean_reversion: 0.20, rsi: 0.20 },
  mean_reversion: { momentum: 0.10, volatility: 0.15, volume: 0.15, relative_strength: 0.10, mean_reversion: 0.35, rsi: 0.15 },
};

const STYLE_RISK: Record<string, { stopLoss: number; riskPerTrade: number; maxPosition: number }> = {
  aggressive_momentum: { stopLoss: 5, riskPerTrade: 5, maxPosition: 10 },
  balanced: { stopLoss: 7, riskPerTrade: 3, maxPosition: 8 },
  conservative_value: { stopLoss: 8, riskPerTrade: 2, maxPosition: 6 },
  mean_reversion: { stopLoss: 6, riskPerTrade: 3, maxPosition: 8 },
};

const STYLE_SCANS: Record<string, Record<string, boolean>> = {
  aggressive_momentum: { momentum_breakouts: true, oversold_bounces: false, sector_leaders: true, volume_anomalies: true },
  balanced: { momentum_breakouts: true, oversold_bounces: true, sector_leaders: true, volume_anomalies: true },
  conservative_value: { momentum_breakouts: false, oversold_bounces: true, sector_leaders: true, volume_anomalies: false },
  mean_reversion: { momentum_breakouts: false, oversold_bounces: true, sector_leaders: false, volume_anomalies: true },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function slugify(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

type Mode = "wizard" | "ai";

const WIZARD_STEPS = ["Name & Capital", "Cap Size", "Sectors", "Trading Style", "Review"];
const AI_STEPS = ["Name & Capital", "Cap Size", "Describe Strategy", "Review"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CreatePortfolioModal({ onClose }: { onClose: () => void }) {
  // Shared state
  const [mode, setMode] = useState<Mode>("wizard");
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [id, setId] = useState("");
  const [idManual, setIdManual] = useState(false);
  const [universe, setUniverse] = useState("microcap");
  const [capital, setCapital] = useState("50000");
  const [error, setError] = useState<string | null>(null);

  // Wizard state
  const [sectors, setSectors] = useState<string[]>([...ALL_SECTORS]);
  const [tradingStyle, setTradingStyle] = useState("balanced");

  // AI state
  const [aiPrompt, setAiPrompt] = useState("");
  const [generatedStrategy, setGeneratedStrategy] = useState<GeneratedStrategy | null>(null);
  const [generating, setGenerating] = useState(false);

  const queryClient = useQueryClient();
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);

  const mutation = useMutation({
    mutationFn: api.createPortfolio,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      setPortfolio(data.portfolio.id);
      onClose();
    },
    onError: (e: Error) => setError(e.message),
  });

  const steps = mode === "wizard" ? WIZARD_STEPS : AI_STEPS;
  const maxStep = steps.length;

  // ---- Handlers ----

  function handleNameChange(val: string) {
    setName(val);
    if (!idManual) setId(slugify(val));
  }

  function switchMode(m: Mode) {
    if (m === mode) return;
    setMode(m);
    setStep(1);
    setError(null);
    // preserve name/capital/id
  }

  function toggleSector(s: string) {
    setSectors((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );
  }

  function toggleAllSectors() {
    setSectors((prev) => (prev.length === ALL_SECTORS.length ? [] : [...ALL_SECTORS]));
  }

  async function handleGenerateStrategy() {
    setError(null);
    if (!aiPrompt.trim()) {
      setError("Please describe your strategy");
      return;
    }
    setGenerating(true);
    try {
      const result = await api.generateStrategy({
        prompt: aiPrompt.trim(),
        universe,
        starting_capital: parseFloat(capital) || 50000,
      });
      setGeneratedStrategy(result);
      setStep(step + 1); // advance to review
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Strategy generation failed");
    } finally {
      setGenerating(false);
    }
  }

  function validateCurrentStep(): boolean {
    setError(null);
    if (step === 1) {
      if (!name.trim()) { setError("Name is required"); return false; }
      if (!id.trim()) { setError("ID is required"); return false; }
      const c = parseFloat(capital);
      if (isNaN(c) || c <= 0) { setError("Capital must be a positive number"); return false; }
    }
    if (mode === "wizard" && step === 3) {
      if (sectors.length === 0) { setError("Select at least one sector"); return false; }
    }
    return true;
  }

  function handleNext() {
    if (!validateCurrentStep()) return;
    // For AI mode step 3 (prompt), generation handles the advance
    if (mode === "ai" && step === 3) {
      handleGenerateStrategy();
      return;
    }
    setStep((s) => Math.min(s + 1, maxStep));
  }

  function handleBack() {
    setError(null);
    setStep((s) => Math.max(s - 1, 1));
  }

  function handleSubmit() {
    setError(null);
    if (mode === "wizard") {
      mutation.mutate({
        id,
        name: name.trim(),
        universe,
        starting_capital: parseFloat(capital),
        sectors: sectors.length === ALL_SECTORS.length ? undefined : sectors,
        trading_style: tradingStyle,
      });
    } else {
      if (!generatedStrategy) return;
      mutation.mutate({
        id,
        name: name.trim(),
        universe,
        starting_capital: parseFloat(capital),
        ai_config: {
          ...generatedStrategy,
          prompt: aiPrompt,
        },
      });
    }
  }

  // ---- Step renderers ----

  function renderNameStep() {
    return (
      <div className="space-y-4">
        {/* Name */}
        <div>
          <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="My Large Cap Portfolio"
            className="w-full bg-bg-surface border border-border rounded px-3 py-2 text-sm text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent"
            autoFocus
          />
        </div>
        {/* ID */}
        <div>
          <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
            ID <span className="text-text-muted/50">(slug)</span>
          </label>
          <input
            type="text"
            value={id}
            onChange={(e) => { setId(e.target.value); setIdManual(true); }}
            placeholder="my-large-cap-portfolio"
            className="w-full bg-bg-surface border border-border rounded px-3 py-2 text-sm text-text-primary font-mono placeholder:text-text-muted/50 focus:outline-none focus:border-accent"
          />
        </div>
        {/* Starting Capital */}
        <div>
          <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">Starting Capital</label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted text-sm">$</span>
            <input
              type="text"
              value={capital}
              onChange={(e) => setCapital(e.target.value.replace(/[^0-9.]/g, ""))}
              className="w-full bg-bg-surface border border-border rounded pl-7 pr-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent"
            />
          </div>
        </div>
      </div>
    );
  }

  function renderUniverseStep() {
    return (
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1.5">Universe</label>
        <div className="space-y-1.5">
          {UNIVERSES.map((u) => (
            <button
              type="button"
              key={u.id}
              onClick={() => setUniverse(u.id)}
              className={`w-full text-left px-3 py-2 rounded border text-xs transition-colors ${
                universe === u.id
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-border bg-bg-surface text-text-primary hover:border-text-muted"
              }`}
            >
              <span className="font-semibold">{u.label}</span>
              <span className="text-text-muted ml-2">{u.desc}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  function renderSectorStep() {
    const allSelected = sectors.length === ALL_SECTORS.length;
    return (
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1.5">Sector Focus</label>
        <div className="mb-2">
          <button
            type="button"
            onClick={toggleAllSectors}
            className={`px-3 py-1.5 rounded border text-xs transition-colors ${
              allSelected
                ? "border-accent bg-accent/10 text-accent"
                : "border-border bg-bg-surface text-text-primary hover:border-text-muted"
            }`}
          >
            {allSelected ? "Deselect All" : "Select All"}
          </button>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {ALL_SECTORS.map((s) => {
            const selected = sectors.includes(s);
            return (
              <button
                type="button"
                key={s}
                onClick={() => toggleSector(s)}
                className={`text-left px-3 py-2 rounded border text-xs transition-colors ${
                  selected
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-border bg-bg-surface text-text-primary hover:border-text-muted"
                }`}
              >
                {s}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  function renderTradingStyleStep() {
    return (
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1.5">Trading Style</label>
        <div className="space-y-1.5">
          {TRADING_STYLE_OPTIONS.map((ts) => (
            <button
              type="button"
              key={ts.id}
              onClick={() => setTradingStyle(ts.id)}
              className={`w-full text-left px-3 py-2.5 rounded border text-xs transition-colors ${
                tradingStyle === ts.id
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-border bg-bg-surface text-text-primary hover:border-text-muted"
              }`}
            >
              <div className="font-semibold">{ts.label}</div>
              <div className="text-text-muted mt-0.5">{ts.desc}</div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  function renderWizardReview() {
    const styleOption = TRADING_STYLE_OPTIONS.find((ts) => ts.id === tradingStyle);
    const risk = STYLE_RISK[tradingStyle];
    return (
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-2">Strategy Summary</label>
        <div className="bg-bg-surface border border-border rounded-lg p-4">
          <StrategyReviewCard
            sectors={sectors}
            tradingStyle={tradingStyle}
            tradingStyleLabel={styleOption?.label ?? tradingStyle}
            scoringWeights={STYLE_WEIGHTS[tradingStyle]}
            stopLoss={risk.stopLoss}
            riskPerTrade={risk.riskPerTrade}
            maxPosition={risk.maxPosition}
            scanTypes={STYLE_SCANS[tradingStyle]}
          />
        </div>
      </div>
    );
  }

  function renderAiPromptStep() {
    return (
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1.5">Describe Your Strategy</label>
        <textarea
          value={aiPrompt}
          onChange={(e) => setAiPrompt(e.target.value)}
          placeholder="I want an aggressive momentum strategy focused on tech and healthcare sectors with tight stops..."
          rows={5}
          className="w-full bg-bg-surface border border-border rounded px-3 py-2 text-sm text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:border-accent resize-none"
          autoFocus
        />
        <p className="text-[10px] text-text-muted mt-1.5">
          Describe sectors, risk tolerance, trading approach, or any preferences. AI will generate a complete strategy configuration.
        </p>
      </div>
    );
  }

  function renderAiReview() {
    if (!generatedStrategy) return null;
    return (
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-2">AI-Generated Strategy</label>
        <div className="bg-bg-surface border border-border rounded-lg p-4">
          <StrategyReviewCard
            sectors={generatedStrategy.sectors}
            tradingStyle={generatedStrategy.trading_style}
            tradingStyleLabel={generatedStrategy.strategy_name}
            scoringWeights={generatedStrategy.scoring_weights}
            stopLoss={generatedStrategy.stop_loss_pct}
            riskPerTrade={generatedStrategy.risk_per_trade_pct}
            maxPosition={generatedStrategy.max_position_pct}
            scanTypes={generatedStrategy.scan_types}
            rationale={generatedStrategy.rationale}
          />
        </div>
      </div>
    );
  }

  function renderCurrentStep() {
    if (step === 1) return renderNameStep();
    if (step === 2) return renderUniverseStep();
    if (mode === "wizard") {
      if (step === 3) return renderSectorStep();
      if (step === 4) return renderTradingStyleStep();
      if (step === 5) return renderWizardReview();
    } else {
      if (step === 3) return renderAiPromptStep();
      if (step === 4) return renderAiReview();
    }
    return null;
  }

  const isLastStep = step === maxStep;
  const isAiPromptStep = mode === "ai" && step === 3;

  // ---- Render ----

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-bg-elevated border border-border rounded-xl w-full max-w-lg shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-bold text-text-primary">Create Portfolio</h2>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary text-lg leading-none">&times;</button>
        </div>

        <div className="p-5 space-y-4">
          {/* Mode toggle */}
          <div className="flex rounded border border-border overflow-hidden">
            <button
              type="button"
              onClick={() => switchMode("wizard")}
              className={`flex-1 px-3 py-1.5 text-xs font-semibold transition-colors ${
                mode === "wizard"
                  ? "bg-accent text-bg-primary"
                  : "bg-bg-surface text-text-muted hover:text-text-primary"
              }`}
            >
              Strategy Wizard
            </button>
            <button
              type="button"
              onClick={() => switchMode("ai")}
              className={`flex-1 px-3 py-1.5 text-xs font-semibold transition-colors ${
                mode === "ai"
                  ? "bg-accent text-bg-primary"
                  : "bg-bg-surface text-text-muted hover:text-text-primary"
              }`}
            >
              AI Strategy
            </button>
          </div>

          {/* Step indicator */}
          <div className="flex items-center justify-center gap-1.5">
            {steps.map((label, i) => {
              const stepNum = i + 1;
              const isCurrent = stepNum === step;
              const isDone = stepNum < step;
              return (
                <div key={label} className="flex items-center gap-1.5">
                  <div
                    className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold transition-colors ${
                      isCurrent
                        ? "bg-accent text-bg-primary"
                        : isDone
                          ? "bg-accent/30 text-accent"
                          : "bg-bg-surface text-text-muted border border-border"
                    }`}
                  >
                    {stepNum}
                  </div>
                  {i < steps.length - 1 && (
                    <div className={`w-4 h-px ${isDone ? "bg-accent/40" : "bg-border"}`} />
                  )}
                </div>
              );
            })}
          </div>

          {/* Step title */}
          <div className="text-center">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">
              Step {step} of {maxStep} — {steps[step - 1]}
            </span>
          </div>

          {/* Step content */}
          <div className="min-h-[200px]">
            {renderCurrentStep()}
          </div>

          {/* Error */}
          {error && (
            <p className="text-xs text-red-400 bg-red-500/10 rounded px-3 py-2">{error}</p>
          )}

          {/* Navigation */}
          <div className="flex justify-between pt-2">
            <div>
              {step > 1 ? (
                <button
                  type="button"
                  onClick={handleBack}
                  className="px-4 py-2 text-xs text-text-muted hover:text-text-primary transition-colors"
                >
                  Back
                </button>
              ) : (
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs text-text-muted hover:text-text-primary transition-colors"
                >
                  Cancel
                </button>
              )}
            </div>
            <div>
              {isLastStep ? (
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={mutation.isPending}
                  className="px-4 py-2 text-xs font-semibold bg-accent text-bg-primary rounded hover:bg-accent/80 transition-colors disabled:opacity-50"
                >
                  {mutation.isPending ? "Creating..." : "Create Portfolio"}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleNext}
                  disabled={generating}
                  className="px-4 py-2 text-xs font-semibold bg-accent text-bg-primary rounded hover:bg-accent/80 transition-colors disabled:opacity-50"
                >
                  {isAiPromptStep
                    ? generating
                      ? "Generating..."
                      : "Generate Strategy"
                    : "Next"}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
