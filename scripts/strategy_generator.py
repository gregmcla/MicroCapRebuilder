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

SUGGEST_CONFIG_PROMPT = """You are GScott's portfolio architect. Given a strategy DNA (investment thesis), suggest the optimal portfolio configuration.

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
  }}
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
        model=CLAUDE_MODEL,
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

    rg = data.get("reentry_guard", {})
    reentry_guard_config = {
        "enabled": True,
        "stop_loss_cooldown_days": int(rg.get("stop_loss_cooldown_days", 7)),
        "lookback_days": int(rg.get("lookback_days", 30)),
        "meaningful_change_threshold_pts": float(rg.get("meaningful_change_threshold_pts", 10)),
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
    }
