# Strategy-Focused Portfolio Creation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add sector focus and trading style selection to portfolio creation, with both a step-by-step wizard and AI-generated strategy option.

**Architecture:** Extend the existing `portfolio_registry.py` with `TRADING_STYLES` and `SECTOR_ETF_MAP` data. Add a `POST /api/portfolios/generate-strategy` endpoint that calls Anthropic to produce config from a text prompt. Redesign `CreatePortfolioModal.tsx` as a multi-step wizard with a wizard/AI toggle. Both paths produce the same config.json output.

**Tech Stack:** Python/FastAPI backend, React/TypeScript/Tailwind frontend, Anthropic API for AI strategy generation.

**Design doc:** `docs/plans/2026-02-24-strategy-focused-portfolios-design.md`

---

### Task 1: Add Trading Styles and Sector Map to Registry

**Files:**
- Modify: `scripts/portfolio_registry.py`

**Step 1: Add SECTOR_ETF_MAP and TRADING_STYLES constants**

Add after `UNIVERSE_PRESETS` (after line 142):

```python
# ─── Sector ETF Map ──────────────────────────────────────────────────────────
# Maps GICS sectors to ETF tickers used as data sources for stock discovery.
# We never buy ETFs — these are used to find individual stocks.
SECTOR_ETF_MAP = {
    "Technology": ["XLK", "SOXX"],
    "Communication": ["XLC"],
    "Healthcare": ["XLV", "XBI"],
    "Financials": ["XLF"],
    "Consumer Discretionary": ["XLY"],
    "Consumer Staples": ["XLP"],
    "Industrials": ["XLI"],
    "Energy": ["XLE", "XOP"],
    "Materials": ["XLB"],
    "Utilities": ["XLU"],
    "Real Estate": ["XLRE"],
}

ALL_SECTORS = list(SECTOR_ETF_MAP.keys())

# ─── Trading Style Presets ────────────────────────────────────────────────────
TRADING_STYLES = {
    "aggressive_momentum": {
        "label": "Aggressive Momentum",
        "description": "High momentum + relative strength, tight stops, larger positions",
        "scoring_weights": {
            "momentum": 0.35,
            "volatility": 0.05,
            "volume": 0.15,
            "relative_strength": 0.25,
            "mean_reversion": 0.05,
            "rsi": 0.15,
        },
        "default_stop_loss_pct": 5.0,
        "risk_per_trade_pct": 5.0,
        "max_position_pct": 10.0,
        "trailing_stop_trigger_pct": 8.0,
        "trailing_stop_distance_pct": 5.0,
        "scan_types": {
            "momentum_breakouts": True,
            "oversold_bounces": False,
            "sector_leaders": True,
            "volume_anomalies": True,
        },
    },
    "balanced": {
        "label": "Balanced",
        "description": "Even factor weights, moderate risk, all scan types",
        "scoring_weights": {
            "momentum": 0.20,
            "volatility": 0.15,
            "volume": 0.15,
            "relative_strength": 0.20,
            "mean_reversion": 0.15,
            "rsi": 0.15,
        },
        "default_stop_loss_pct": 7.0,
        "risk_per_trade_pct": 3.0,
        "max_position_pct": 8.0,
        "trailing_stop_trigger_pct": 12.0,
        "trailing_stop_distance_pct": 7.0,
        "scan_types": {
            "momentum_breakouts": True,
            "oversold_bounces": True,
            "sector_leaders": True,
            "volume_anomalies": True,
        },
    },
    "conservative_value": {
        "label": "Conservative Value",
        "description": "Low volatility preference, wide stops, smaller positions",
        "scoring_weights": {
            "momentum": 0.10,
            "volatility": 0.25,
            "volume": 0.10,
            "relative_strength": 0.15,
            "mean_reversion": 0.20,
            "rsi": 0.20,
        },
        "default_stop_loss_pct": 8.0,
        "risk_per_trade_pct": 2.0,
        "max_position_pct": 6.0,
        "trailing_stop_trigger_pct": 15.0,
        "trailing_stop_distance_pct": 8.0,
        "scan_types": {
            "momentum_breakouts": False,
            "oversold_bounces": True,
            "sector_leaders": True,
            "volume_anomalies": False,
        },
    },
    "mean_reversion": {
        "label": "Mean Reversion",
        "description": "Buy dips in quality stocks, oversold bounces, moderate risk",
        "scoring_weights": {
            "momentum": 0.10,
            "volatility": 0.15,
            "volume": 0.15,
            "relative_strength": 0.10,
            "mean_reversion": 0.35,
            "rsi": 0.15,
        },
        "default_stop_loss_pct": 6.0,
        "risk_per_trade_pct": 3.0,
        "max_position_pct": 8.0,
        "trailing_stop_trigger_pct": 10.0,
        "trailing_stop_distance_pct": 6.0,
        "scan_types": {
            "momentum_breakouts": False,
            "oversold_bounces": True,
            "sector_leaders": False,
            "volume_anomalies": True,
        },
    },
}
```

**Step 2: Extend `create_portfolio()` to accept strategy params**

Replace the `create_portfolio` function signature and body (lines 205-285):

```python
def create_portfolio(
    portfolio_id: str,
    name: str,
    universe: str,
    starting_capital: float,
    sectors: list[str] = None,
    trading_style: str = None,
    ai_config: dict = None,
) -> PortfolioMeta:
    """Create a new portfolio: directory, config, and registry entry.

    Clones the current data/config.json and applies:
    1. Universe preset overrides (cap size)
    2. Trading style overrides (scoring weights, risk params, scan types)
    3. Sector focus (ETF sources, sector filter)
    4. AI-generated config overrides (if provided)
    """
    if universe not in UNIVERSE_PRESETS:
        raise ValueError(
            f"Unknown universe '{universe}'. "
            f"Valid options: {', '.join(UNIVERSE_PRESETS.keys())}"
        )

    portfolio_dir = get_portfolio_dir(portfolio_id)
    portfolio_dir.mkdir(parents=True, exist_ok=True)

    # Clone base config
    base_config_file = Path(__file__).parent.parent / "data" / "config.json"
    if base_config_file.exists():
        with open(base_config_file) as f:
            config = json.load(f)
    else:
        config = {}

    # --- Layer 1: Universe preset (cap size) ---
    preset = UNIVERSE_PRESETS[universe]
    config["starting_capital"] = starting_capital
    config["default_stop_loss_pct"] = preset["default_stop_loss_pct"]
    config["risk_per_trade_pct"] = preset["risk_per_trade_pct"]
    config["max_position_pct"] = preset["max_position_pct"]
    config["benchmark_symbol"] = preset["benchmark_symbol"]
    config["fallback_benchmark"] = preset["fallback_benchmark"]

    if "scoring" not in config:
        config["scoring"] = {}
    config["scoring"]["default_weights"] = dict(preset["scoring_weights"])

    if "discovery" not in config:
        config["discovery"] = {}
    config["discovery"]["filters"] = dict(preset["discovery_filters"])

    if "universe" not in config:
        config["universe"] = {}
    if "sources" not in config["universe"]:
        config["universe"]["sources"] = {}
    if "etf_holdings" not in config["universe"]["sources"]:
        config["universe"]["sources"]["etf_holdings"] = {}
    config["universe"]["sources"]["etf_holdings"]["etfs"] = list(preset["etf_sources"])
    config["universe"]["filters"] = dict(preset["discovery_filters"])

    # --- Layer 2: Trading style overrides ---
    if trading_style and trading_style in TRADING_STYLES:
        style = TRADING_STYLES[trading_style]
        config["scoring"]["default_weights"] = dict(style["scoring_weights"])
        config["default_stop_loss_pct"] = style["default_stop_loss_pct"]
        config["risk_per_trade_pct"] = style["risk_per_trade_pct"]
        config["max_position_pct"] = style["max_position_pct"]
        config["discovery"]["scan_types"] = dict(style["scan_types"])

        # Apply trailing stop settings
        if "enhanced_trading" not in config:
            config["enhanced_trading"] = {}
        if "layer1" not in config["enhanced_trading"]:
            config["enhanced_trading"]["layer1"] = {}
        config["enhanced_trading"]["layer1"]["trailing_stop_trigger_pct"] = style["trailing_stop_trigger_pct"]
        config["enhanced_trading"]["layer1"]["trailing_stop_distance_pct"] = style["trailing_stop_distance_pct"]

    # --- Layer 3: Sector focus ---
    if sectors and len(sectors) < len(ALL_SECTORS):
        # Build ETF sources from selected sectors + cap-size base ETF
        sector_etfs = []
        for sector in sectors:
            sector_etfs.extend(SECTOR_ETF_MAP.get(sector, []))
        # Keep first cap-size ETF for breadth
        base_etf = preset["etf_sources"][0] if preset["etf_sources"] else None
        if base_etf and base_etf not in sector_etfs:
            sector_etfs.insert(0, base_etf)
        # Deduplicate while preserving order
        seen = set()
        unique_etfs = []
        for etf in sector_etfs:
            if etf not in seen:
                seen.add(etf)
                unique_etfs.append(etf)
        config["universe"]["sources"]["etf_holdings"]["etfs"] = unique_etfs
        config["discovery"]["sector_filter"] = list(sectors)
    else:
        # "All" sectors — no filter
        config["discovery"].pop("sector_filter", None)

    # --- Layer 4: AI-generated overrides ---
    if ai_config:
        if "scoring_weights" in ai_config:
            config["scoring"]["default_weights"] = ai_config["scoring_weights"]
        if "stop_loss_pct" in ai_config:
            config["default_stop_loss_pct"] = ai_config["stop_loss_pct"]
        if "risk_per_trade_pct" in ai_config:
            config["risk_per_trade_pct"] = ai_config["risk_per_trade_pct"]
        if "max_position_pct" in ai_config:
            config["max_position_pct"] = ai_config["max_position_pct"]
        if "scan_types" in ai_config:
            config["discovery"]["scan_types"] = ai_config["scan_types"]
        if "sectors" in ai_config:
            sector_etfs = []
            for sector in ai_config["sectors"]:
                sector_etfs.extend(SECTOR_ETF_MAP.get(sector, []))
            base_etf = preset["etf_sources"][0] if preset["etf_sources"] else None
            if base_etf and base_etf not in sector_etfs:
                sector_etfs.insert(0, base_etf)
            config["universe"]["sources"]["etf_holdings"]["etfs"] = list(dict.fromkeys(sector_etfs))
            config["discovery"]["sector_filter"] = ai_config["sectors"]
        if "etf_sources" in ai_config:
            existing = config["universe"]["sources"]["etf_holdings"]["etfs"]
            for etf in ai_config["etf_sources"]:
                if etf not in existing:
                    existing.append(etf)

    # Store strategy metadata
    config["strategy"] = {
        "name": (TRADING_STYLES[trading_style]["label"] if trading_style and trading_style in TRADING_STYLES
                 else ai_config.get("strategy_name", "Custom") if ai_config else "Default"),
        "sectors": sectors or [],
        "trading_style": trading_style or (ai_config.get("trading_style") if ai_config else None),
        "created_via": "ai" if ai_config else "wizard",
        "ai_prompt": ai_config.get("prompt") if ai_config else None,
        "ai_rationale": ai_config.get("rationale") if ai_config else None,
    }

    # Write config
    config_path = portfolio_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # Register
    meta = PortfolioMeta(
        id=portfolio_id,
        name=name,
        universe=universe,
        created=datetime.now().isoformat(timespec="seconds"),
        starting_capital=starting_capital,
        active=True,
    )
    registry = load_registry()
    registry["portfolios"][portfolio_id] = asdict(meta)
    if registry.get("default_portfolio") is None:
        registry["default_portfolio"] = portfolio_id
    save_registry(registry)

    return meta
```

**Step 3: Commit**

```bash
git add scripts/portfolio_registry.py
git commit -m "feat: add trading styles, sector map, and strategy params to portfolio creation"
```

---

### Task 2: Add Sector Filter to Discovery Pipeline

**Files:**
- Modify: `scripts/stock_discovery.py` (the `_passes_filters` method)
- Modify: `scripts/universe_provider.py` (sector filtering in `_load_etf_holdings`)

**Step 1: Add sector filter check to `stock_discovery.py`**

Find the `_passes_filters` method and add sector checking. The method filters candidates during discovery scans. Add after the existing market cap / volume / price checks:

```python
# Check sector filter
sector_filter = self.discovery_config.get("sector_filter")
if sector_filter:
    info = self._get_stock_info(ticker)
    stock_sector = info.get("sector", "")
    if stock_sector not in sector_filter:
        return False
```

**Step 2: Add sector filtering to `universe_provider.py`**

In `_load_etf_holdings`, after fetching holdings from ETFs, filter by sector if `sector_filter` is configured. Add after the ETF holdings are loaded into `self._universe`:

```python
# Filter by sector if configured
sector_filter = self.config.get("discovery", {}).get("sector_filter")
if sector_filter:
    # We can't filter here efficiently (would need yfinance calls per ticker)
    # Instead, sector filtering happens in stock_discovery._passes_filters()
    pass
```

Note: Sector filtering is best done in `stock_discovery.py` since it already has the `_get_stock_info` cache. The universe provider just feeds raw ticker lists.

**Step 3: Commit**

```bash
git add scripts/stock_discovery.py scripts/universe_provider.py
git commit -m "feat: add sector_filter support to discovery pipeline"
```

---

### Task 3: Add AI Strategy Generation Endpoint

**Files:**
- Create: `scripts/strategy_generator.py`
- Modify: `api/routes/portfolios.py`

**Step 1: Create `scripts/strategy_generator.py`**

```python
#!/usr/bin/env python3
"""AI strategy generation — Mommy generates a portfolio config from a text description."""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class GeneratedStrategy:
    sectors: list[str]
    trading_style: Optional[str]
    scoring_weights: dict[str, float]
    stop_loss_pct: float
    risk_per_trade_pct: float
    max_position_pct: float
    scan_types: dict[str, bool]
    etf_sources: list[str]
    strategy_name: str
    rationale: str
    prompt: str


VALID_SECTORS = [
    "Technology", "Communication", "Healthcare", "Financials",
    "Consumer Discretionary", "Consumer Staples", "Industrials",
    "Energy", "Materials", "Utilities", "Real Estate",
]

STRATEGY_SYSTEM_PROMPT = """You are Mommy Bot's strategy architect. Given a user's description of their desired trading strategy, generate a portfolio configuration.

You MUST return ONLY valid JSON with these exact fields:
{
  "strategy_name": "Short descriptive name for this strategy",
  "sectors": ["list of GICS sectors to focus on"],
  "trading_style": "aggressive_momentum" | "balanced" | "conservative_value" | "mean_reversion" | null,
  "scoring_weights": {
    "momentum": 0.0-1.0,
    "volatility": 0.0-1.0,
    "volume": 0.0-1.0,
    "relative_strength": 0.0-1.0,
    "mean_reversion": 0.0-1.0,
    "rsi": 0.0-1.0
  },
  "stop_loss_pct": 3.0-10.0,
  "risk_per_trade_pct": 1.0-8.0,
  "max_position_pct": 4.0-15.0,
  "scan_types": {
    "momentum_breakouts": true/false,
    "oversold_bounces": true/false,
    "sector_leaders": true/false,
    "volume_anomalies": true/false
  },
  "etf_sources": ["additional sector ETFs beyond base"],
  "rationale": "2-3 sentence explanation of why these settings fit the strategy"
}

Rules:
- scoring_weights MUST sum to 1.0
- Valid sectors: """ + json.dumps(VALID_SECTORS) + """
- If user wants broad market exposure, return all sectors
- If user mentions specific themes (AI, semiconductors, etc.), map to appropriate sectors
- Match risk parameters to the aggressiveness implied by the description
- Return ONLY the JSON object, no markdown, no explanation outside the JSON"""


def get_api_key() -> Optional[str]:
    """Get Anthropic API key from environment or .env file."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _clean_json_response(text: str) -> str:
    """Extract JSON from AI response, stripping markdown blocks."""
    # Remove markdown code blocks
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    # Find JSON boundaries
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return text


def _validate_weights(weights: dict) -> dict:
    """Ensure scoring weights sum to 1.0."""
    total = sum(weights.values())
    if abs(total - 1.0) > 0.01:
        # Normalize
        for k in weights:
            weights[k] = round(weights[k] / total, 2)
        # Fix rounding
        diff = 1.0 - sum(weights.values())
        first_key = next(iter(weights))
        weights[first_key] = round(weights[first_key] + diff, 2)
    return weights


def generate_strategy(prompt: str, universe: str, starting_capital: float) -> GeneratedStrategy:
    """Use AI to generate a portfolio strategy config from a text description.

    Args:
        prompt: User's strategy description
        universe: Cap size (microcap/smallcap/midcap/largecap)
        starting_capital: Portfolio starting capital

    Returns:
        GeneratedStrategy with all config values

    Raises:
        ValueError: If API key missing or AI response invalid
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("No Anthropic API key found. Add ANTHROPIC_API_KEY to your .env file.")

    try:
        import anthropic
    except ImportError:
        raise ValueError("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)

    user_msg = f"""Portfolio context:
- Universe: {universe} (market cap range)
- Starting capital: ${starting_capital:,.0f}

User's strategy description:
{prompt}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=STRATEGY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text
    cleaned = _clean_json_response(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI returned invalid JSON: {e}")

    # Validate sectors
    sectors = [s for s in data.get("sectors", []) if s in VALID_SECTORS]
    if not sectors:
        sectors = list(VALID_SECTORS)

    # Validate and normalize weights
    weights = data.get("scoring_weights", {})
    required_factors = ["momentum", "volatility", "volume", "relative_strength", "mean_reversion", "rsi"]
    for f in required_factors:
        if f not in weights:
            weights[f] = 1.0 / len(required_factors)
    weights = _validate_weights(weights)

    return GeneratedStrategy(
        sectors=sectors,
        trading_style=data.get("trading_style"),
        scoring_weights=weights,
        stop_loss_pct=max(3.0, min(10.0, data.get("stop_loss_pct", 7.0))),
        risk_per_trade_pct=max(1.0, min(8.0, data.get("risk_per_trade_pct", 3.0))),
        max_position_pct=max(4.0, min(15.0, data.get("max_position_pct", 8.0))),
        scan_types=data.get("scan_types", {
            "momentum_breakouts": True, "oversold_bounces": True,
            "sector_leaders": True, "volume_anomalies": False,
        }),
        etf_sources=data.get("etf_sources", []),
        strategy_name=data.get("strategy_name", "AI Strategy"),
        rationale=data.get("rationale", ""),
        prompt=prompt,
    )
```

**Step 2: Add generate-strategy endpoint to `api/routes/portfolios.py`**

Add new request model and endpoint:

```python
from strategy_generator import generate_strategy, GeneratedStrategy, VALID_SECTORS
from portfolio_registry import TRADING_STYLES, SECTOR_ETF_MAP, ALL_SECTORS

class GenerateStrategyRequest(BaseModel):
    prompt: str
    universe: str
    starting_capital: float

@router.post("/generate-strategy")
def generate_strategy_endpoint(req: GenerateStrategyRequest):
    """Use AI to generate a portfolio strategy from a text description."""
    try:
        strategy = generate_strategy(req.prompt, req.universe, req.starting_capital)
        return {
            "sectors": strategy.sectors,
            "trading_style": strategy.trading_style,
            "scoring_weights": strategy.scoring_weights,
            "stop_loss_pct": strategy.stop_loss_pct,
            "risk_per_trade_pct": strategy.risk_per_trade_pct,
            "max_position_pct": strategy.max_position_pct,
            "scan_types": strategy.scan_types,
            "etf_sources": strategy.etf_sources,
            "strategy_name": strategy.strategy_name,
            "rationale": strategy.rationale,
            "prompt": strategy.prompt,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

Also update `CreatePortfolioRequest` and the create endpoint:

```python
class CreatePortfolioRequest(BaseModel):
    id: str
    name: str
    universe: str
    starting_capital: float
    sectors: list[str] | None = None
    trading_style: str | None = None
    ai_config: dict | None = None

@router.post("")
def create_new_portfolio(req: CreatePortfolioRequest):
    try:
        meta = create_portfolio(
            portfolio_id=req.id, name=req.name,
            universe=req.universe, starting_capital=req.starting_capital,
            sectors=req.sectors, trading_style=req.trading_style,
            ai_config=req.ai_config,
        )
        return {"portfolio": asdict(meta), "message": f"Created portfolio '{req.name}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

Add new endpoint for listing trading styles and sectors:

```python
@router.get("/trading-styles")
def get_trading_styles():
    return {k: {"label": v["label"], "description": v["description"]} for k, v in TRADING_STYLES.items()}

@router.get("/sectors")
def get_sectors():
    return {"sectors": ALL_SECTORS}
```

**Step 3: Commit**

```bash
git add scripts/strategy_generator.py api/routes/portfolios.py
git commit -m "feat: add AI strategy generation endpoint and extended portfolio creation API"
```

---

### Task 4: Add Frontend Types and API Methods

**Files:**
- Modify: `dashboard/src/lib/types.ts`
- Modify: `dashboard/src/lib/api.ts`

**Step 1: Update types**

Add to `types.ts`:

```typescript
export interface CreatePortfolioRequest {
  id: string;
  name: string;
  universe: string;
  starting_capital: number;
  sectors?: string[];
  trading_style?: string;
  ai_config?: AiConfig;
}

export interface AiConfig {
  sectors?: string[];
  trading_style?: string;
  scoring_weights?: Record<string, number>;
  stop_loss_pct?: number;
  risk_per_trade_pct?: number;
  max_position_pct?: number;
  scan_types?: Record<string, boolean>;
  etf_sources?: string[];
  strategy_name?: string;
  rationale?: string;
  prompt?: string;
}

export interface GenerateStrategyRequest {
  prompt: string;
  universe: string;
  starting_capital: number;
}

export interface GeneratedStrategy {
  sectors: string[];
  trading_style: string | null;
  scoring_weights: Record<string, number>;
  stop_loss_pct: number;
  risk_per_trade_pct: number;
  max_position_pct: number;
  scan_types: Record<string, boolean>;
  etf_sources: string[];
  strategy_name: string;
  rationale: string;
  prompt: string;
}

export interface TradingStyle {
  label: string;
  description: string;
}
```

**Step 2: Update api.ts**

Add new methods:

```typescript
generateStrategy: (req: GenerateStrategyRequest) =>
  post<GeneratedStrategy>("/portfolios/generate-strategy", req),
getTradingStyles: () => get<Record<string, TradingStyle>>("/portfolios/trading-styles"),
getSectors: () => get<{ sectors: string[] }>("/portfolios/sectors"),
```

**Step 3: Commit**

```bash
git add dashboard/src/lib/types.ts dashboard/src/lib/api.ts
git commit -m "feat: add strategy types and API methods to frontend"
```

---

### Task 5: Build Strategy Review Card Component

**Files:**
- Create: `dashboard/src/components/StrategyReviewCard.tsx`

**Step 1: Create the shared review card**

This component is used by both the wizard (step 5) and AI path (step 4) to show the assembled strategy before creating.

```tsx
/** Strategy review card — shows assembled config before portfolio creation. */

import type { AiConfig } from "../lib/types";

const WEIGHT_LABELS: Record<string, string> = {
  momentum: "Momentum",
  volatility: "Volatility",
  volume: "Volume",
  relative_strength: "Rel Strength",
  mean_reversion: "Mean Rev",
  rsi: "RSI",
};

interface Props {
  sectors: string[];
  tradingStyle: string | null;
  tradingStyleLabel: string;
  scoringWeights: Record<string, number>;
  stopLoss: number;
  riskPerTrade: number;
  maxPosition: number;
  scanTypes: Record<string, boolean>;
  rationale?: string;
}

export default function StrategyReviewCard({
  sectors,
  tradingStyle,
  tradingStyleLabel,
  scoringWeights,
  stopLoss,
  riskPerTrade,
  maxPosition,
  scanTypes,
  rationale,
}: Props) {
  const enabledScans = Object.entries(scanTypes)
    .filter(([, v]) => v)
    .map(([k]) => k.replace(/_/g, " "));

  return (
    <div className="space-y-3">
      {/* Sectors */}
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
          Sectors
        </label>
        <div className="flex flex-wrap gap-1">
          {sectors.length === 11 || sectors.length === 0 ? (
            <span className="px-2 py-0.5 text-xs bg-accent/10 text-accent rounded">
              All Sectors
            </span>
          ) : (
            sectors.map((s) => (
              <span
                key={s}
                className="px-2 py-0.5 text-xs bg-accent/10 text-accent rounded"
              >
                {s}
              </span>
            ))
          )}
        </div>
      </div>

      {/* Trading Style */}
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
          Trading Style
        </label>
        <span className="text-sm text-text-primary font-medium">
          {tradingStyleLabel}
        </span>
      </div>

      {/* Scoring Weights */}
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
          Factor Weights
        </label>
        <div className="grid grid-cols-3 gap-x-4 gap-y-1">
          {Object.entries(scoringWeights).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between text-xs">
              <span className="text-text-muted">{WEIGHT_LABELS[k] ?? k}</span>
              <span className="font-mono text-text-primary">
                {(v * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Risk Params */}
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
          Risk Parameters
        </label>
        <div className="grid grid-cols-3 gap-x-4 gap-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-text-muted">Stop Loss</span>
            <span className="font-mono text-text-primary">{stopLoss}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">Risk/Trade</span>
            <span className="font-mono text-text-primary">{riskPerTrade}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">Max Pos</span>
            <span className="font-mono text-text-primary">{maxPosition}%</span>
          </div>
        </div>
      </div>

      {/* Enabled Scans */}
      <div>
        <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
          Discovery Scans
        </label>
        <div className="flex flex-wrap gap-1">
          {enabledScans.map((s) => (
            <span
              key={s}
              className="px-2 py-0.5 text-xs bg-bg-surface text-text-secondary rounded"
            >
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* AI Rationale */}
      {rationale && (
        <div>
          <label className="block text-[10px] text-text-muted uppercase tracking-wider mb-1">
            AI Rationale
          </label>
          <p className="text-xs text-text-secondary italic leading-relaxed">
            {rationale}
          </p>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add dashboard/src/components/StrategyReviewCard.tsx
git commit -m "feat: add StrategyReviewCard component"
```

---

### Task 6: Redesign CreatePortfolioModal as Multi-Step Wizard

**Files:**
- Modify: `dashboard/src/components/CreatePortfolioModal.tsx`

**Step 1: Rewrite the modal**

Replace the entire file with a multi-step wizard that has a wizard/AI toggle. This is the largest UI change.

The modal has these states:
- `mode`: `"wizard"` | `"ai"` — toggle at top
- `step`: 1-5 for wizard, 1-4 for AI
- Wizard steps: Name+Capital → Cap Size → Sectors → Trading Style → Review
- AI steps: Name+Capital → Cap Size → Prompt → Review

Key implementation notes:
- Step 1 (Name+Capital) and Step 2 (Cap Size) are shared between both modes
- Wizard Step 3: Sector checkbox grid — 11 checkboxes + "All" toggle
- Wizard Step 4: Trading style radio buttons — 4 options with descriptions
- AI Step 3: Textarea for strategy description + "Generate" button that calls `api.generateStrategy()`, shows loading spinner
- Step 5/4 (Review): Uses `StrategyReviewCard` component, shows "Create Portfolio" button
- AI review step is editable — sectors can be toggled, style can be changed
- Back/Next navigation at bottom of each step
- The `createPortfolio` mutation sends `sectors`, `trading_style`, and/or `ai_config`

The full component code should be written during implementation. It replaces the existing 159-line modal with a ~400-line multi-step version.

**Step 2: Commit**

```bash
git add dashboard/src/components/CreatePortfolioModal.tsx
git commit -m "feat: redesign portfolio creation modal with wizard and AI strategy paths"
```

---

### Task 7: Add Fallback ETF Holdings for Sector ETFs

**Files:**
- Modify: `scripts/etf_holdings_provider.py`

**Step 1: Add sector ETF fallback holdings**

Add entries to the `FALLBACK_HOLDINGS` dict for sector ETFs that don't already have entries (XLK, XLC, XLV, XLF, XLY, XLP, XLI, XLE, XLB, XLU, XLRE, SOXX, XBI, XOP).

Each should have 30-50 representative holdings for that sector. For example:

```python
"XLK": [
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "ADBE", "CSCO", "ACN",
    "IBM", "INTU", "TXN", "QCOM", "AMAT", "NOW", "PANW", "ADI", "LRCX", "KLAC",
    "SNPS", "CDNS", "CRWD", "FTNT", "MCHP", "MU", "MSI", "APH", "NXPI", "TEL",
],
"SOXX": [
    "NVDA", "AVGO", "AMD", "QCOM", "TXN", "AMAT", "LRCX", "KLAC", "ADI", "MCHP",
    "MU", "NXPI", "MRVL", "ON", "MPWR", "INTC", "GFS", "SWKS", "QRVO", "ENTG",
],
# ... etc for all sector ETFs
```

**Step 2: Commit**

```bash
git add scripts/etf_holdings_provider.py
git commit -m "feat: add fallback holdings for sector ETFs"
```

---

### Task 8: Integration Testing and Verification

**Step 1: Test registry with strategy params**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/scripts
python3 -c "
from portfolio_registry import create_portfolio, TRADING_STYLES, SECTOR_ETF_MAP
import json

# Test wizard creation
meta = create_portfolio(
    'test-strategy', 'Test Strategy', 'largecap', 100000,
    sectors=['Technology', 'Communication'],
    trading_style='aggressive_momentum',
)
config = json.load(open('../data/portfolios/test-strategy/config.json'))
print('Strategy:', config.get('strategy'))
print('Weights:', config['scoring']['default_weights'])
print('ETFs:', config['universe']['sources']['etf_holdings']['etfs'])
print('Sector filter:', config['discovery'].get('sector_filter'))
print('Scan types:', config['discovery'].get('scan_types'))
"
```

Expected: Config has Technology+Communication sectors, aggressive momentum weights, XLK+SOXX+XLC ETFs, sector_filter set.

**Step 2: Test AI generation endpoint**

```bash
curl -X POST http://localhost:8000/api/portfolios/generate-strategy \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Aggressive AI and semiconductor play", "universe": "largecap", "starting_capital": 1000000}'
```

Expected: JSON response with sectors, weights, risk params, rationale.

**Step 3: Test full flow in dashboard**

1. Open http://localhost:5173/
2. Click create portfolio
3. Test wizard path: Name → largecap → select Technology + Industrials → Aggressive Momentum → Review → Create
4. Verify portfolio appears with correct config
5. Test AI path: Name → largecap → type "Conservative dividend portfolio focused on utilities and energy" → Generate → Review → Create
6. Verify portfolio appears with correct config
7. Run SCAN on both new portfolios — verify discovery finds sector-appropriate stocks

**Step 4: Clean up test portfolio**

```bash
python3 -c "from portfolio_registry import archive_portfolio; archive_portfolio('test-strategy')"
```

**Step 5: Commit any fixes**

```bash
git add -A && git commit -m "fix: integration testing fixes for strategy-focused portfolios"
```
