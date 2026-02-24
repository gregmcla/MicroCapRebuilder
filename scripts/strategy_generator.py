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
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return text


def _validate_weights(weights: dict) -> dict:
    """Ensure scoring weights sum to 1.0."""
    total = sum(weights.values())
    if abs(total - 1.0) > 0.01:
        for k in weights:
            weights[k] = round(weights[k] / total, 2)
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
