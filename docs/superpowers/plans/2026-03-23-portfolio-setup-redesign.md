# Portfolio Setup Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 3-mode, 954-line portfolio creation modal with a 2-step AI-driven-only flow, harden scan defaults, and delete dead code.

**Architecture:** New `POST /api/portfolios/suggest-config` endpoint calls Opus 4.6 to infer name, universe, ETFs, and risk params from strategy DNA. Frontend packs response into existing `ai_config` parameter for `POST /api/portfolios`. Creation defaults hardened to prevent scan timeouts.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript (frontend), Anthropic SDK (Claude API)

**Spec:** `docs/superpowers/specs/2026-03-23-portfolio-setup-redesign.md`

---

### Task 1: Backend — `suggest_config_for_dna()` function

**Files:**
- Modify: `scripts/strategy_generator.py`
- Test: `tests/test_suggest_config.py`

- [ ] **Step 1: Write the failing test for `suggest_config_for_dna()`**

Create `tests/test_suggest_config.py`:

```python
"""Tests for suggest_config_for_dna()."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from strategy_generator import suggest_config_for_dna


def _mock_claude_response(content: str):
    """Build a mock Anthropic message response."""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=content)]
    return mock_resp


def test_suggest_config_returns_expected_fields():
    fake_response = json.dumps({
        "name": "Defense Tech Portfolio",
        "universe": "midcap",
        "etfs": ["ITA", "FITE", "ROBO"],
        "stop_loss_pct": 7.0,
        "risk_per_trade_pct": 8.0,
        "max_position_pct": 12.0,
    })
    with patch("strategy_generator.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(fake_response)

        result = suggest_config_for_dna("defense tech thesis", 1_000_000)

    assert result["name"] == "Defense Tech Portfolio"
    assert result["universe"] == "midcap"
    assert result["etfs"] == ["ITA", "FITE", "ROBO"]
    assert result["stop_loss_pct"] == 7.0


def test_suggest_config_falls_back_to_allcap_for_invalid_universe():
    fake_response = json.dumps({
        "name": "Test Portfolio",
        "universe": "mega-cap",
        "etfs": ["SPY"],
        "stop_loss_pct": 7.0,
        "risk_per_trade_pct": 8.0,
        "max_position_pct": 12.0,
    })
    with patch("strategy_generator.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(fake_response)

        result = suggest_config_for_dna("test", 1_000_000)

    assert result["universe"] == "allcap"


def test_suggest_config_handles_markdown_wrapped_json():
    fake_response = '```json\n{"name": "Test", "universe": "allcap", "etfs": ["SPY"], "stop_loss_pct": 7.0, "risk_per_trade_pct": 8.0, "max_position_pct": 12.0}\n```'
    with patch("strategy_generator.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(fake_response)

        result = suggest_config_for_dna("test", 1_000_000)

    assert result["name"] == "Test"


def test_suggest_config_raises_on_missing_api_key():
    with patch("strategy_generator.get_api_key", return_value=None):
        try:
            suggest_config_for_dna("test", 1_000_000)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "API key" in str(e)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/test_suggest_config.py -v`
Expected: FAIL — `suggest_config_for_dna` not found

- [ ] **Step 3: Rewrite `strategy_generator.py`**

Replace the entire file contents. Keep `get_api_key()` (lines 73-83) and `_clean_json_response()` (lines 86-95). Delete everything else. Add `suggest_config_for_dna()`:

```python
#!/usr/bin/env python3
"""Strategy configuration generator — suggests portfolio config from strategy DNA."""

import json
import os
import re
from pathlib import Path
from typing import Optional

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    from dotenv import load_dotenv
    for env_path in [
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
    ]:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            break
except ImportError:
    pass

# Import valid universes from registry to stay in sync
from portfolio_registry import UNIVERSE_PRESETS

SUGGEST_CONFIG_PROMPT = """You are GScott's portfolio architect. Given a strategy DNA (investment thesis), suggest the optimal portfolio configuration.

Return a JSON object with exactly these fields:
{
  "name": "Short descriptive portfolio name (2-5 words)",
  "universe": "one of: microcap, smallcap, midcap, largecap, allcap",
  "etfs": ["4-6 real ETF tickers that best source candidates for this thesis"],
  "stop_loss_pct": <number 5-10>,
  "risk_per_trade_pct": <number 5-10>,
  "max_position_pct": <number 5-15>
}

Guidelines:
- Universe: pick the market cap range that best fits the thesis. Use "allcap" if the thesis spans multiple cap sizes.
- ETFs: pick ETFs whose holdings overlap with the thesis. Only use real, liquid ETFs. No leveraged/inverse ETFs (no TQQQ, SOXL, etc.).
- Risk params: aggressive theses get tighter stops (5-6%) and larger positions (10-15%). Conservative theses get wider stops (8-10%) and smaller positions (5-8%).
- Name: be descriptive but concise. "AI Infrastructure" not "Artificial Intelligence Adjacent Infrastructure Investment Strategy".

Starting capital: ${starting_capital:,.0f}

Return ONLY the JSON object, no other text."""


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
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return text


def suggest_config_for_dna(strategy_dna: str, starting_capital: float) -> dict:
    """Use Claude to suggest portfolio config from strategy DNA.

    Returns dict with: name, universe, etfs, stop_loss_pct, risk_per_trade_pct, max_position_pct.
    Raises ValueError if API key is missing or response is unparseable.
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("Anthropic API key not configured")

    client = anthropic.Anthropic(api_key=api_key, timeout=60.0)
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=SUGGEST_CONFIG_PROMPT.format(starting_capital=starting_capital),
        messages=[{"role": "user", "content": f"Strategy DNA:\n{strategy_dna}"}],
    )

    raw = response.content[0].text
    cleaned = _clean_json_response(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI returned invalid JSON: {e}")

    # Validate universe
    if data.get("universe") not in UNIVERSE_PRESETS:
        data["universe"] = "allcap"

    # Ensure required fields
    required = ["name", "universe", "etfs", "stop_loss_pct", "risk_per_trade_pct", "max_position_pct"]
    for field in required:
        if field not in data:
            raise ValueError(f"AI response missing required field: {field}")

    return {
        "name": str(data["name"]),
        "universe": data["universe"],
        "etfs": [str(t).upper() for t in data["etfs"]],
        "stop_loss_pct": float(data["stop_loss_pct"]),
        "risk_per_trade_pct": float(data["risk_per_trade_pct"]),
        "max_position_pct": float(data["max_position_pct"]),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/test_suggest_config.py -v`
Expected: 4 PASS

- [ ] **Step 5: Delete old test file**

Delete `tests/test_task2_strategy_generator.py` (tests `GeneratedStrategy` and `_normalize_sector_weights` which no longer exist).

- [ ] **Step 6: Commit**

```bash
git add scripts/strategy_generator.py tests/test_suggest_config.py
git rm tests/test_task2_strategy_generator.py
git commit -m "feat: replace strategy_generator with suggest_config_for_dna()"
```

---

### Task 2: Backend — New `suggest-config` endpoint + delete old endpoints

**Files:**
- Modify: `api/routes/portfolios.py`

- [ ] **Step 1: Add `suggest-config` endpoint and delete old endpoints**

In `api/routes/portfolios.py`:

1. Replace the import on line 17 (`from strategy_generator import generate_strategy`) with:
   ```python
   from strategy_generator import suggest_config_for_dna
   ```

2. Delete `GenerateStrategyRequest` model and `generate_strategy_endpoint` (lines 81-109).

3. Delete `get_trading_styles` endpoint (lines 112-114).

4. Delete `get_sectors` endpoint (lines 117-119).

5. Add new endpoint after the existing `create_new_portfolio`:

```python
class SuggestConfigRequest(BaseModel):
    strategy_dna: str
    starting_capital: float


@router.post("/suggest-config")
def suggest_config(req: SuggestConfigRequest):
    """Use AI to suggest portfolio config from strategy DNA."""
    try:
        result = suggest_config_for_dna(req.strategy_dna, req.starting_capital)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 2: Verify API starts cleanly**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && uvicorn api.main:app --host 0.0.0.0 --port 8001 &`
Then: `curl -s http://localhost:8001/api/health`
Expected: `{"status":"ok"}`
Then: `kill %1`

- [ ] **Step 3: Commit**

```bash
git add api/routes/portfolios.py
git commit -m "feat: add suggest-config endpoint, delete generate-strategy/trading-styles/sectors endpoints"
```

---

### Task 3: Backend — Harden AI-driven creation defaults

**Files:**
- Modify: `scripts/portfolio_registry.py` (lines 533-549)

- [ ] **Step 1: Update AI-driven code path in `create_portfolio()`**

Replace the AI-driven block (lines 533-549) with:

```python
    # AI-driven mode: store flag, strategy DNA, harden defaults
    if ai_driven:
        config["ai_driven"] = True
        if strategy_dna:
            config["strategy_dna"] = strategy_dna
        # Hardened scan defaults — prevent timeout issues
        config.setdefault("universe", {}).setdefault("tiers", {}).setdefault("extended", {})
        config["universe"]["tiers"]["extended"]["max_tickers"] = 3000
        config["universe"]["tiers"]["extended"]["scan_frequency"] = "rotating_3day"
        config.setdefault("universe", {}).setdefault("sources", {}).setdefault("exchange_listings", {})
        config["universe"]["sources"]["exchange_listings"]["enabled"] = False
        # Larger watchlist gives Claude more candidates to reason across
        config.setdefault("discovery", {}).setdefault("watchlist", {})
        config["discovery"]["watchlist"]["total_watchlist_slots"] = 500
```

Note: the old `suggest_etfs_for_dna()` call is removed — ETFs now come through `ai_config.etf_sources` from the frontend, which is already handled by Layer 4 (lines 515-519).

- [ ] **Step 2: Run existing portfolio_registry tests**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/ -k "portfolio" -v`
Expected: All pass (or no matching tests — either is fine)

- [ ] **Step 3: Commit**

```bash
git add scripts/portfolio_registry.py
git commit -m "feat: harden AI-driven defaults (3000 extended, rotating_3day, no exchange_listings)"
```

---

### Task 4: Frontend — Add `SuggestConfigResponse` type and API call

**Files:**
- Modify: `dashboard/src/lib/types.ts` (lines 469-488)
- Modify: `dashboard/src/lib/api.ts` (lines 1-2, 68-71)

- [ ] **Step 1: Update `types.ts`**

1. Delete `GenerateStrategyRequest` (lines 469-473).
2. Delete `GeneratedStrategy` (lines 475-488).
3. Delete `TradingStyle` interface (lines 490-493) — dead code after `getTradingStyles` removal.
4. Add in their place:

```typescript
export interface SuggestConfigRequest {
  strategy_dna: string;
  starting_capital: number;
}

export interface SuggestConfigResponse {
  name: string;
  universe: string;
  etfs: string[];
  stop_loss_pct: number;
  risk_per_trade_pct: number;
  max_position_pct: number;
}
```

- [ ] **Step 2: Update `api.ts`**

1. Update imports (line 1-2): replace `GenerateStrategyRequest, GeneratedStrategy` with `SuggestConfigRequest, SuggestConfigResponse`. Also remove `TradingStyle` from the import.
2. Replace lines 68-71 (generateStrategy, getTradingStyles, getSectors) with:

```typescript
  suggestConfig: (req: SuggestConfigRequest) =>
    post<SuggestConfigResponse>("/portfolios/suggest-config", req),
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit 2>&1 | head -20`
Expected: Errors about CreatePortfolioModal (still imports deleted types) — that's expected, fixed in Task 5.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/lib/types.ts dashboard/src/lib/api.ts
git commit -m "feat: add SuggestConfigResponse type, replace generateStrategy with suggestConfig"
```

---

### Task 5: Frontend — Rewrite `CreatePortfolioModal.tsx`

**Files:**
- Rewrite: `dashboard/src/components/CreatePortfolioModal.tsx`
- Delete: `dashboard/src/components/StrategyReviewCard.tsx`

- [ ] **Step 1: Delete `StrategyReviewCard.tsx`**

```bash
rm dashboard/src/components/StrategyReviewCard.tsx
```

- [ ] **Step 2: Rewrite `CreatePortfolioModal.tsx`**

Replace the entire file with the new 2-step AI-driven-only modal:

```tsx
/** Create Portfolio Modal — 2-step AI-driven flow. */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";
import type { SuggestConfigResponse } from "../lib/types";

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export default function CreatePortfolioModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const setActivePortfolio = usePortfolioStore((s) => s.setPortfolio);

  // Step 1 state
  const [step, setStep] = useState(1);
  const [capital, setCapital] = useState(1_000_000);
  const [dna, setDna] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Step 2 state
  const [suggestion, setSuggestion] = useState<SuggestConfigResponse | null>(null);

  // Suggest config mutation
  const suggestMutation = useMutation({
    mutationFn: () => api.suggestConfig({ strategy_dna: dna, starting_capital: capital }),
    onSuccess: (data) => {
      setSuggestion(data);
      setError(null);
      setStep(2);
    },
    onError: (err: Error) => {
      setError(err.message || "Failed to generate config");
    },
  });

  // Create portfolio mutation
  const createMutation = useMutation({
    mutationFn: () => {
      if (!suggestion) throw new Error("No suggestion");
      return api.createPortfolio({
        id: slugify(suggestion.name),
        name: suggestion.name,
        universe: suggestion.universe,
        starting_capital: capital,
        ai_driven: true,
        strategy_dna: dna,
        ai_config: {
          stop_loss_pct: suggestion.stop_loss_pct,
          risk_per_trade_pct: suggestion.risk_per_trade_pct,
          max_position_pct: suggestion.max_position_pct,
          etf_sources: suggestion.etfs,
        },
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      setActivePortfolio(data.portfolio.id);
      onClose();
    },
    onError: (err: Error) => {
      setError(err.message || "Failed to create portfolio");
    },
  });

  const labelStyle: React.CSSProperties = {
    fontSize: "9px",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.10em",
    color: "var(--text-0)",
    marginBottom: "6px",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    fontSize: "13px",
    fontFamily: "var(--font-mono)",
    background: "var(--void)",
    border: "1px solid var(--border-1)",
    borderRadius: "6px",
    color: "var(--text-3)",
    outline: "none",
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.6)",
        backdropFilter: "blur(4px)",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "480px",
          maxHeight: "85vh",
          overflowY: "auto",
          background: "var(--surface-0)",
          border: "1px solid var(--border-1)",
          borderRadius: "12px",
          padding: "24px",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <h2 style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-4)", margin: 0 }}>
            {step === 1 ? "New Portfolio" : "Review & Create"}
          </h2>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--text-1)",
              fontSize: "18px",
              cursor: "pointer",
              padding: "4px",
            }}
          >
            ×
          </button>
        </div>

        {step === 1 && (
          <>
            {/* Starting Capital */}
            <div style={{ marginBottom: "16px" }}>
              <p style={labelStyle}>Starting Capital</p>
              <input
                type="number"
                value={capital}
                onChange={(e) => setCapital(Number(e.target.value))}
                style={inputStyle}
              />
            </div>

            {/* Strategy DNA */}
            <div style={{ marginBottom: "20px" }}>
              <p style={labelStyle}>Strategy DNA</p>
              <textarea
                value={dna}
                onChange={(e) => setDna(e.target.value)}
                rows={7}
                placeholder="Describe your investment thesis..."
                style={{
                  ...inputStyle,
                  resize: "vertical",
                  fontFamily: "var(--font-sans)",
                  lineHeight: 1.5,
                }}
              />
            </div>

            {/* Error */}
            {error && (
              <p style={{ fontSize: "11px", color: "var(--red)", marginBottom: "12px" }}>{error}</p>
            )}

            {/* Next button */}
            <button
              onClick={() => {
                setError(null);
                suggestMutation.mutate();
              }}
              disabled={!dna.trim() || suggestMutation.isPending}
              style={{
                width: "100%",
                padding: "10px 0",
                fontSize: "12px",
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                background: !dna.trim() || suggestMutation.isPending
                  ? "var(--surface-1)"
                  : "linear-gradient(135deg, #7c5cfc 0%, #9b7eff 100%)",
                color: !dna.trim() || suggestMutation.isPending ? "var(--text-0)" : "#fff",
                border: "none",
                borderRadius: "6px",
                cursor: !dna.trim() || suggestMutation.isPending ? "not-allowed" : "pointer",
              }}
            >
              {suggestMutation.isPending ? "Generating..." : "Next"}
            </button>
          </>
        )}

        {step === 2 && suggestion && (
          <>
            {/* Suggestion card */}
            <div
              style={{
                background: "var(--surface-1)",
                border: "1px solid var(--border-0)",
                borderRadius: "8px",
                padding: "16px",
                marginBottom: "16px",
              }}
            >
              <div style={{ marginBottom: "12px" }}>
                <p style={labelStyle}>Name</p>
                <p style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-4)", margin: 0 }}>
                  {suggestion.name}
                </p>
                <p style={{ fontSize: "10px", color: "var(--text-0)", marginTop: "2px", fontFamily: "var(--font-mono)" }}>
                  {slugify(suggestion.name)}
                </p>
              </div>

              <div style={{ display: "flex", gap: "24px", marginBottom: "12px" }}>
                <div>
                  <p style={labelStyle}>Universe</p>
                  <p style={{ fontSize: "12px", color: "var(--text-3)", margin: 0, fontWeight: 600 }}>
                    {suggestion.universe}
                  </p>
                </div>
                <div>
                  <p style={labelStyle}>Capital</p>
                  <p style={{ fontSize: "12px", color: "var(--text-3)", margin: 0, fontFamily: "var(--font-mono)" }}>
                    ${capital.toLocaleString()}
                  </p>
                </div>
              </div>

              <div style={{ marginBottom: "12px" }}>
                <p style={labelStyle}>ETFs</p>
                <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                  {suggestion.etfs.map((etf) => (
                    <span
                      key={etf}
                      style={{
                        fontSize: "10px",
                        fontWeight: 600,
                        fontFamily: "var(--font-mono)",
                        padding: "2px 6px",
                        borderRadius: "3px",
                        background: "rgba(124,92,252,0.15)",
                        color: "var(--accent-bright)",
                      }}
                    >
                      {etf}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <p style={labelStyle}>Risk</p>
                <p style={{ fontSize: "11px", color: "var(--text-2)", margin: 0, fontFamily: "var(--font-mono)" }}>
                  {suggestion.stop_loss_pct}% stop · {suggestion.risk_per_trade_pct}% risk/trade · {suggestion.max_position_pct}% max position
                </p>
              </div>
            </div>

            {/* DNA preview */}
            <div style={{ marginBottom: "16px" }}>
              <p style={labelStyle}>Strategy DNA</p>
              <p
                style={{
                  fontSize: "11px",
                  color: "var(--text-2)",
                  lineHeight: 1.5,
                  fontStyle: "italic",
                  margin: 0,
                  maxHeight: "80px",
                  overflow: "hidden",
                }}
              >
                {dna}
              </p>
            </div>

            {/* Error */}
            {error && (
              <p style={{ fontSize: "11px", color: "var(--red)", marginBottom: "12px" }}>{error}</p>
            )}

            {/* Buttons */}
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                onClick={() => { setStep(1); setError(null); }}
                style={{
                  flex: 1,
                  padding: "10px 0",
                  fontSize: "12px",
                  fontWeight: 600,
                  background: "var(--surface-1)",
                  color: "var(--text-2)",
                  border: "1px solid var(--border-0)",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                Back
              </button>
              <button
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending}
                style={{
                  flex: 2,
                  padding: "10px 0",
                  fontSize: "12px",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  background: createMutation.isPending
                    ? "var(--surface-1)"
                    : "linear-gradient(135deg, #7c5cfc 0%, #9b7eff 100%)",
                  color: createMutation.isPending ? "var(--text-0)" : "#fff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: createMutation.isPending ? "not-allowed" : "pointer",
                }}
              >
                {createMutation.isPending ? "Creating..." : "Create Portfolio"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit`
Expected: Clean compile (0 errors)

- [ ] **Step 4: Verify dev server runs**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx vite build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git rm dashboard/src/components/StrategyReviewCard.tsx
git add dashboard/src/components/CreatePortfolioModal.tsx
git commit -m "feat: rewrite CreatePortfolioModal as 2-step AI-driven-only flow"
```

---

### Task 6: Update CLAUDE.md endpoint table

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update endpoint table**

In the API Endpoints table in CLAUDE.md:

1. Remove these rows:
   - `POST | /api/portfolios/generate-strategy | AI strategy generation`
   - `GET | /api/portfolios/trading-styles | Available trading style presets`
   - `GET | /api/portfolios/sectors | Available sectors`

2. Add this row:
   - `POST | /api/portfolios/suggest-config | AI config suggestion from strategy DNA`

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md endpoint table for portfolio setup redesign"
```

---

### Task 7: End-to-end verification

- [ ] **Step 1: Start API**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && uvicorn api.main:app --host 0.0.0.0 --port 8001 &`

- [ ] **Step 2: Verify suggest-config endpoint works**

Run: `curl -s -X POST http://localhost:8001/api/portfolios/suggest-config -H "Content-Type: application/json" -d '{"strategy_dna": "aggressive momentum in semiconductor stocks", "starting_capital": 1000000}' | python3 -m json.tool`
Expected: JSON with name, universe, etfs, stop_loss_pct, risk_per_trade_pct, max_position_pct

- [ ] **Step 3: Verify old endpoints are gone**

Run: `curl -s http://localhost:8001/api/portfolios/trading-styles`
Expected: 404 or "Not Found"

Run: `curl -s http://localhost:8001/api/portfolios/sectors`
Expected: 404 or "Not Found"

- [ ] **Step 4: Start dashboard and test the full flow**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx vite --port 5173 &`

Manual test:
1. Open http://localhost:5173
2. Click "+ New Portfolio" on overview page
3. Enter capital + strategy DNA
4. Click "Next" — verify suggestion card appears
5. Click "Create Portfolio" — verify portfolio appears in sidebar
6. Verify new portfolio has `ai_driven: true` in config.json
7. Verify config has `extended_max: 3000`, `rotating_3day`, `exchange_listings: false`

- [ ] **Step 5: Run all tests**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Kill background processes**

```bash
kill %1 %2 2>/dev/null
```
