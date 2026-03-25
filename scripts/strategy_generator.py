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
  "stop_loss_pct": <number 5-10>,
  "risk_per_trade_pct": <number 5-10>,
  "max_position_pct": <number 5-15>
}}

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

    return {
        "name": str(data["name"]),
        "universe": data["universe"],
        "etfs": [str(t).upper() for t in data["etfs"]],
        "stop_loss_pct": float(data["stop_loss_pct"]),
        "risk_per_trade_pct": float(data["risk_per_trade_pct"]),
        "max_position_pct": float(data["max_position_pct"]),
    }
