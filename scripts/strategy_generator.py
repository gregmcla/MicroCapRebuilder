#!/usr/bin/env python3
"""Strategy configuration generator — suggests portfolio config from strategy DNA."""

import json
import os
import re
from pathlib import Path
from typing import Optional

from schema import CLAUDE_MODEL

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

SUGGEST_CONFIG_PROMPT = """You are GScott's portfolio architect. Given a strategy DNA (investment thesis), suggest the optimal portfolio configuration AND a curated starter universe of individual stocks.

Return a JSON object with exactly these fields:
{{
  "name": "Short descriptive portfolio name (2-5 words)",
  "universe": "one of: microcap, smallcap, midcap, largecap, allcap",
  "etfs": ["4-6 real ETF tickers that best source candidates for this thesis"],
  "stop_loss_pct": <number 5-15>,
  "take_profit_pct": <number 15-300>,
  "risk_per_trade_pct": <number 5-50>,
  "max_position_pct": <number 5-95>,
  "max_positions": <integer 1-20>,
  "reentry_guard": {{
    "stop_loss_cooldown_days": <integer 1-14>,
    "lookback_days": <integer 5-90>,
    "meaningful_change_threshold_pts": <integer 5-20>
  }},
  "curated_tickers": [
    {{"ticker": "AAPL", "sector": "Technology", "rationale": "1-sentence reason this fits the thesis"}},
    ...
  ],
  "screener": {{
    "sectors": ["1-3 sector names from: Basic Materials, Consumer Cyclical, Financial Services, Real Estate, Consumer Defensive, Healthcare, Utilities, Communication Services, Energy, Industrials, Technology"],
    "industries": ["3-8 specific Yahoo Finance industries within those sectors that match the thesis"],
    "market_cap_min": "<integer in dollars, e.g. 500000000 for $500M>",
    "market_cap_max": "<integer in dollars, e.g. 15000000000 for $15B>"
  }},
  "ai_refinement_prompt": "1-2 sentence filter describing what to include/exclude from screener results. Only for thematic strategies where industry codes don't fully capture the thesis. Empty string if sectors+industries are sufficient."
}}

Guidelines:
- Universe: pick the market cap range that best fits the thesis. Use "allcap" if the thesis spans multiple cap sizes.
- ETFs: pick ETFs whose holdings overlap with the thesis. Only use real, liquid ETFs. No leveraged/inverse ETFs (no TQQQ, SOXL, etc.).
- Risk params: read the DNA carefully and use the exact values it specifies. If the DNA says "risk_per_trade_pct MUST be 45", use 45. If it says "max_positions: 2", use 2.
- Concentrated strategies (1-3 positions) should have high risk_per_trade_pct (30-50) and high max_position_pct (50-95).
- Diversified strategies (10+ positions) should have low risk_per_trade_pct (3-10) and low max_position_pct (5-15).
- take_profit_pct: aggressive momentum strategies targeting 2-5x moves should use 100-200. Conservative strategies use 15-30.
- Name: be descriptive but concise. "AI Infrastructure" not "Artificial Intelligence Adjacent Infrastructure Investment Strategy".
- reentry_guard: Set based on rotation speed and universe breadth.
  - Fast rotation (hold < 3 days, large universe): cooldown 1, lookback 5–7, threshold 5
  - Standard momentum (7–14 day holds): cooldown 7, lookback 30, threshold 10
  - High conviction, long holds (1–3 positions, >30 day targets): cooldown 14, lookback 60, threshold 15
  - Narrow curated universe (<20 tickers): keep cooldown low (1–3) to avoid starving the universe
- curated_tickers: Return 50-150 individual stock tickers that best fit this thesis.
  - Pick real, currently-traded tickers on NYSE/NASDAQ.
  - Match the market cap range of the chosen universe preset.
  - Cover the thesis sectors — diversify within theme, don't cluster in one sub-industry.
  - Include a mix of established leaders and emerging growth names.
  - Each entry needs: ticker (string), sector (GICS sector name), and rationale (1-sentence).
  - For microcap/smallcap: focus on $50M-$2B names. For largecap: $10B+. For allcap: full range.
  - Quality filter: skip SPACs, blank check companies, pre-revenue biotechs (unless DNA specifically targets biotech).
- screener.sectors: pick the 1-3 GICS sectors that contain the target companies. Use exact names from the list above.
- screener.industries: pick specific Yahoo Finance industries within those sectors. Be precise — "Engineering & Construction" not just "Industrials".
- screener market cap: match the universe preset (microcap: 50000000-2000000000, smallcap: 300000000-5000000000, midcap: 500000000-15000000000, largecap: 5000000000-999000000000, allcap: 50000000-999000000000).
- ai_refinement_prompt: write a clear 1-2 sentence filter for thematic strategies. Leave as empty string "" for generic strategies where sector+industry filters are sufficient.

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

    client = anthropic.Anthropic(api_key=api_key, timeout=300.0)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8192,
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

    rg = data.get("reentry_guard", {})
    reentry_guard_config = {
        "enabled": True,
        "stop_loss_cooldown_days": int(rg.get("stop_loss_cooldown_days", 7)),
        "lookback_days": int(rg.get("lookback_days", 30)),
        "meaningful_change_threshold_pts": float(rg.get("meaningful_change_threshold_pts", 10)),
    }

    # Parse curated tickers (optional — graceful fallback to empty list)
    raw_tickers = data.get("curated_tickers", [])
    curated_tickers = []
    for entry in raw_tickers:
        if isinstance(entry, dict) and "ticker" in entry:
            curated_tickers.append({
                "ticker": str(entry["ticker"]).upper().strip(),
                "sector": str(entry.get("sector", "")),
                "rationale": str(entry.get("rationale", "")),
            })
        elif isinstance(entry, str):
            curated_tickers.append({
                "ticker": entry.upper().strip(),
                "sector": "",
                "rationale": "",
            })

    screener_data = data.get("screener", {})
    screener_config = {
        "enabled": True,
        "sectors": [str(s) for s in screener_data.get("sectors", [])],
        "industries": [str(i) for i in screener_data.get("industries", [])],
        "market_cap_min": int(screener_data.get("market_cap_min", 500000000)),
        "market_cap_max": int(screener_data.get("market_cap_max", 15000000000)),
        "region": "us",
    }

    refinement_prompt = str(data.get("ai_refinement_prompt", ""))
    ai_refinement = {
        "enabled": bool(refinement_prompt),
        "prompt": refinement_prompt,
    }

    return {
        "name": str(data["name"]),
        "universe": data["universe"],
        "etfs": [str(t).upper() for t in data["etfs"]],
        "stop_loss_pct": float(data["stop_loss_pct"]),
        "take_profit_pct": float(data.get("take_profit_pct", 20.0)),
        "risk_per_trade_pct": float(data["risk_per_trade_pct"]),
        "max_position_pct": float(data["max_position_pct"]),
        "max_positions": int(data.get("max_positions", 10)),
        "reentry_guard": reentry_guard_config,
        "curated_tickers": curated_tickers,
        "screener": screener_config,
        "ai_refinement": ai_refinement,
    }
