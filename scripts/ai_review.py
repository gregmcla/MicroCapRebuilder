#!/usr/bin/env python3
"""
AI Review Module - The wisdom layer on top of quantitative decisions.

This module reviews proposed trades from the rule-based system and can:
- APPROVE: Execute as proposed
- MODIFY: Adjust position size, stop/target levels
- VETO: Block the trade with reasoning

The AI adds contextual wisdom that rules can't capture:
- Macro conditions not in the model
- Pattern recognition from experience
- Risk factors the quant model misses
- Timing considerations
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Import ProposedAction from centralized data structures
from enhanced_structures import ProposedAction

# Load environment
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

# ─── Review Decision Types ────────────────────────────────────────────────────

class ReviewDecision:
    APPROVE = "APPROVE"
    MODIFY = "MODIFY"
    VETO = "VETO"


@dataclass
class ReviewedAction:
    """An action after AI review."""
    original: ProposedAction
    decision: str  # APPROVE, MODIFY, VETO
    ai_reasoning: str
    confidence: float  # 0.0 - 1.0
    # Modified values (only if decision == MODIFY)
    modified_shares: Optional[int] = None
    modified_stop: Optional[float] = None
    modified_target: Optional[float] = None


def get_ai_client():
    """Get the AI client (Anthropic or OpenAI)."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if anthropic_key:
        try:
            import anthropic
            return ("anthropic", anthropic.Anthropic(api_key=anthropic_key))
        except ImportError:
            pass

    if openai_key:
        try:
            import openai
            return ("openai", openai.OpenAI(api_key=openai_key))
        except ImportError:
            pass

    return (None, None)


def build_review_prompt(
    proposed_actions: list,
    portfolio_context: dict,
) -> str:
    """Build the prompt for AI review."""

    sector_map = portfolio_context.get("sector_map", {})

    actions_text = ""
    for i, action in enumerate(proposed_actions, 1):
        sector = sector_map.get(action.ticker, "Unknown")
        actions_text += f"""
Action {i}:
  Type: {action.action_type}
  Ticker: {action.ticker}
  Sector: {sector}
  Shares: {action.shares}
  Price: ${action.price:.2f}
  Stop Loss: ${action.stop_loss:.2f} ({((action.price - action.stop_loss) / action.price * 100):.1f}% risk)
  Take Profit: ${action.take_profit:.2f} ({((action.take_profit - action.price) / action.price * 100):.1f}% upside)
  Quant Score: {action.quant_score:.1f}/100
  Factor Scores: {json.dumps(action.factor_scores)}
  Market Regime: {action.regime}
  Quant Reason: {action.reason}
"""

    projected_sectors = portfolio_context.get("projected_sector_allocation", {})
    if projected_sectors:
        sorted_sectors = sorted(projected_sectors.items(), key=lambda x: x[1], reverse=True)
        sector_lines = "\n".join(f"  {s}: {p:.1f}%" for s, p in sorted_sectors)
        sector_section = f"""
PROJECTED SECTOR ALLOCATION (after all proposed buys):
{sector_lines}

If any sector is heavily overweighted relative to portfolio diversity goals, consider VETOing or MODIFYing (reducing size) lower-conviction picks in that sector.
"""
    else:
        sector_section = ""

    prompt = f"""You are GScott's risk management AI. You review proposed trades from the quantitative system and decide whether to APPROVE, MODIFY, or VETO each one.

PORTFOLIO CONTEXT:
- Total Equity: ${portfolio_context.get('total_equity', 0):,.0f}
- Cash Available: ${portfolio_context.get('cash', 0):,.0f}
- Current Positions: {portfolio_context.get('num_positions', 0)}
- Market Regime: {portfolio_context.get('regime', 'UNKNOWN')}
- Recent Win Rate: {portfolio_context.get('win_rate', 0):.0%}

CURRENT POSITIONS:
{json.dumps(portfolio_context.get('positions', []), indent=2)}
{sector_section}
PROPOSED ACTIONS TO REVIEW:
{actions_text}

For each proposed action, provide your decision in this JSON format:
{{
  "reviews": [
    {{
      "ticker": "SYMBOL",
      "decision": "APPROVE" | "MODIFY" | "VETO",
      "reasoning": "Brief explanation of your decision",
      "confidence": 0.0-1.0,
      "modified_shares": null or new_number (only if MODIFY),
      "modified_stop": null or new_price (only if MODIFY),
      "modified_target": null or new_price (only if MODIFY)
    }}
  ]
}}

DECISION GUIDELINES:
- APPROVE if the quant signal is strong AND you see no red flags
- MODIFY if the idea is good but position size or levels should be adjusted
- VETO if you see risks the quant model missed (correlation, sector concentration, timing, macro)
- Use your judgment on sector concentration — there are no hard rules, but use common sense: if 60%+ of proposed capital is going into one sector, critically evaluate whether each pick genuinely earns its spot or if some are just riding the sector wave

- ROTATION SELLS: Sells labeled "ROTATION: Upgrading to {{ticker}}" sell a modestly-performing position to fund a higher-scoring candidate. A 20+ point score gap generally justifies the switch.

Be protective but not overly cautious. A 70+ score with good regime usually deserves APPROVE.

Respond ONLY with the JSON, no other text."""

    return prompt


def review_proposed_actions(
    proposed_actions: list,
    portfolio_context: dict,
    batch_size: int = 10,
) -> list:
    """
    Review proposed actions using AI.

    Returns list of ReviewedAction objects.
    """
    if not proposed_actions:
        return []

    client_type, client = get_ai_client()

    if client is None:
        # No AI available - approve based on quant score
        return [
            ReviewedAction(
                original=action,
                decision=ReviewDecision.APPROVE,
                ai_reasoning=f"AI unavailable - approved based on quant score {action.quant_score:.0f}/100",
                confidence=min(0.3 + (action.quant_score / 100) * 0.4, 0.7),
            )
            for action in proposed_actions
        ]

    # Batch large numbers of actions to avoid overwhelming the AI
    if len(proposed_actions) > batch_size:
        all_reviewed = []
        for i in range(0, len(proposed_actions), batch_size):
            batch = proposed_actions[i:i + batch_size]
            batch_reviewed = _review_batch(client_type, client, batch, portfolio_context)
            all_reviewed.extend(batch_reviewed)
        return all_reviewed

    return _review_batch(client_type, client, proposed_actions, portfolio_context)


def _review_batch(client_type, client, proposed_actions: list, portfolio_context: dict) -> list:
    """Review a batch of proposed actions."""

    prompt = build_review_prompt(proposed_actions, portfolio_context)

    try:
        if client_type == "anthropic":
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.content[0].text if response.content else ""
        else:  # openai
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.choices[0].message.content if response.choices else ""

        # Check for empty response
        if not response_text or not response_text.strip():
            raise ValueError("Empty response from AI")

        # Parse JSON response
        # Handle potential markdown code blocks and extra text
        clean_text = response_text.strip()

        # Remove markdown code blocks
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0]
        elif "```" in clean_text:
            parts = clean_text.split("```")
            if len(parts) >= 2:
                clean_text = parts[1]

        # Try to find JSON object boundaries
        clean_text = clean_text.strip()
        if not clean_text.startswith("{"):
            # Find first { and last }
            start = clean_text.find("{")
            end = clean_text.rfind("}") + 1
            if start >= 0 and end > start:
                clean_text = clean_text[start:end]
            else:
                raise ValueError(f"No JSON found in response: {clean_text[:200]}")

        # Try parsing, with fallback to fix common issues
        try:
            reviews_data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            # Try fixing common issues: trailing commas
            import re
            fixed_text = clean_text
            # Remove trailing commas before } or ]
            fixed_text = re.sub(r',(\s*[}\]])', r'\1', fixed_text)
            try:
                reviews_data = json.loads(fixed_text)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON after fixes: {str(e)[:100]}")

        # Map reviews back to actions
        reviews_by_ticker = {r["ticker"]: r for r in reviews_data.get("reviews", [])}

        reviewed_actions = []
        for action in proposed_actions:
            review = reviews_by_ticker.get(action.ticker, {})

            reviewed_actions.append(ReviewedAction(
                original=action,
                decision=review.get("decision", ReviewDecision.APPROVE),
                ai_reasoning=review.get("reasoning", "No specific review provided"),
                confidence=review.get("confidence", 0.5),
                modified_shares=review.get("modified_shares"),
                modified_stop=review.get("modified_stop"),
                modified_target=review.get("modified_target"),
            ))

        return reviewed_actions

    except Exception as e:
        # On error, approve all with low confidence
        return [
            ReviewedAction(
                original=action,
                decision=ReviewDecision.APPROVE,
                ai_reasoning=f"AI review error: {str(e)} - auto-approved",
                confidence=0.3,
            )
            for action in proposed_actions
        ]


def format_review_summary(reviewed_actions: list) -> str:
    """Format a human-readable summary of the review."""
    if not reviewed_actions:
        return "No actions to review."

    lines = ["=" * 60, "AI REVIEW SUMMARY", "=" * 60, ""]

    approved = [r for r in reviewed_actions if r.decision == ReviewDecision.APPROVE]
    modified = [r for r in reviewed_actions if r.decision == ReviewDecision.MODIFY]
    vetoed = [r for r in reviewed_actions if r.decision == ReviewDecision.VETO]

    if approved:
        lines.append(f"✅ APPROVED ({len(approved)}):")
        for r in approved:
            lines.append(f"   {r.original.action_type} {r.original.ticker} - {r.ai_reasoning}")
            lines.append(f"      Confidence: {r.confidence:.0%}")
        lines.append("")

    if modified:
        lines.append(f"🔧 MODIFIED ({len(modified)}):")
        for r in modified:
            mods = []
            if r.modified_shares:
                mods.append(f"shares: {r.original.shares} → {r.modified_shares}")
            if r.modified_stop:
                mods.append(f"stop: ${r.original.stop_loss:.2f} → ${r.modified_stop:.2f}")
            if r.modified_target:
                mods.append(f"target: ${r.original.take_profit:.2f} → ${r.modified_target:.2f}")
            lines.append(f"   {r.original.action_type} {r.original.ticker} - {r.ai_reasoning}")
            lines.append(f"      Changes: {', '.join(mods)}")
            lines.append(f"      Confidence: {r.confidence:.0%}")
        lines.append("")

    if vetoed:
        lines.append(f"❌ VETOED ({len(vetoed)}):")
        for r in vetoed:
            lines.append(f"   {r.original.action_type} {r.original.ticker} - {r.ai_reasoning}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test the review system
    test_actions = [
        ProposedAction(
            action_type="BUY",
            ticker="CRDO",
            shares=10,
            price=120.50,
            stop_loss=110.86,
            take_profit=144.60,
            quant_score=78.5,
            factor_scores={"momentum": 82, "volatility": 71, "volume": 65, "relative_strength": 85},
            regime="BULL",
            reason="Strong momentum with relative strength above benchmark"
        ),
    ]

    test_context = {
        "total_equity": 50000,
        "cash": 10000,
        "num_positions": 15,
        "regime": "BULL",
        "win_rate": 0.55,
        "positions": []
    }

    print("Testing AI Review...")
    reviews = review_proposed_actions(test_actions, test_context)
    print(format_review_summary(reviews))
