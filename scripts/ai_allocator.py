#!/usr/bin/env python3
"""
AI Allocator — Claude as portfolio manager with full allocation authority.

In AI-driven mode, Claude replaces Layers 2-4. It receives quant scores as
advisory inputs and makes all position sizing and stock selection decisions.

Layer 1 sells (stop/target triggers) always execute mechanically and are passed
to Claude as context so it can factor freed cash into its allocation plan.
"""

import json
import re
from typing import Optional

from enhanced_structures import ProposedAction
from ai_review import ReviewedAction, ReviewDecision, get_ai_client
from market_regime import MarketRegime, RegimeAnalysis
from schema import CLAUDE_MODEL


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def run_ai_allocation(
    state,
    layer1_sells: list,
    scored_candidates: list,
    sector_map: dict,
    regime: MarketRegime,
    warning_severity: str,
    strategy_dna: str,
    info_cache: Optional[dict] = None,
    regime_analysis: Optional[RegimeAnalysis] = None,
    prompt_extras: Optional[dict] = None,
) -> list:
    """
    Run full AI allocation for an AI-driven portfolio.

    Returns list of ReviewedAction objects (all APPROVE):
    - Layer 1 sells (mechanical, passed through)
    - AI-directed buys
    - AI-initiated additional sells (optional, used sparingly)

    Args:
        state: PortfolioState
        layer1_sells: ProposedAction objects from Layer 1 (SELL only)
        scored_candidates: list of score dicts sorted by composite_score desc
        sector_map: ticker -> sector string
        regime: current MarketRegime
        warning_severity: "NORMAL" | "CAUTION" | "DANGER"
        strategy_dna: free-text strategy mandate from portfolio config
        info_cache: yfinance .info dict per ticker (fundamentals)
    """
    client = get_ai_client()

    # Build set of held tickers for sell validation
    held_tickers: set = set()
    if not state.positions.empty:
        held_tickers = set(state.positions["ticker"].tolist())

    # Layer 1 sells are mechanical — always APPROVE them
    reviewed: list[ReviewedAction] = []
    for sell_action in layer1_sells:
        reviewed.append(ReviewedAction(
            original=sell_action,
            decision=ReviewDecision.APPROVE,
            ai_reasoning="Layer 1 mechanical sell — stop/target/quality trigger",
            confidence=1.0,
        ))

    if client is None:
        print("  [AI Allocator] No AI client available — returning Layer 1 sells only")
        return reviewed

    # Calculate cash after Layer 1 sells (freed cash is available for new buys)
    freed_cash = sum(s.shares * s.price for s in layer1_sells)
    available_cash = state.cash + freed_cash

    full_watchlist = bool(state.config.get("full_watchlist_prompt", False))

    prompt = _build_allocation_prompt(
        state=state,
        layer1_sells=layer1_sells,
        scored_candidates=scored_candidates,
        sector_map=sector_map,
        regime=regime,
        warning_severity=warning_severity,
        strategy_dna=strategy_dna,
        available_cash=available_cash,
        info_cache=info_cache,
        full_watchlist=full_watchlist,
        regime_analysis=regime_analysis,
        prompt_extras=prompt_extras,
    )

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text if response.content else ""

        if not response_text or not response_text.strip():
            raise ValueError("Empty response from AI allocator")

        allocation_data = _parse_json(response_text)

        valid_buys, ai_sells = _validate_allocation(
            allocation_data, available_cash, state.total_equity, scored_candidates,
            held_tickers=held_tickers,
        )

        ai_actions = _convert_to_reviewed_actions(
            valid_buys, ai_sells, regime
        )
        reviewed.extend(ai_actions)

        thesis = allocation_data.get("portfolio_thesis", "")
        if thesis:
            print(f"\n  AI Portfolio Thesis: {thesis[:250]}{'...' if len(thesis) > 250 else ''}")
        print(f"  AI allocation: {len(valid_buys)} buy(s), {len(ai_sells)} AI-initiated sell(s)")

    except Exception as e:
        print(f"  [AI Allocator] Error during AI allocation: {e}")
        print("  [AI Allocator] Proceeding with Layer 1 sells only")

    return reviewed


# ─── Prompt Builder ────────────────────────────────────────────────────────────

def _build_allocation_prompt(
    state,
    layer1_sells: list,
    scored_candidates: list,
    sector_map: dict,
    regime: MarketRegime,
    warning_severity: str,
    strategy_dna: str,
    available_cash: float,
    info_cache: Optional[dict] = None,
    full_watchlist: bool = False,
    regime_analysis: Optional[RegimeAnalysis] = None,
    prompt_extras: Optional[dict] = None,
) -> str:
    """Build the full allocation prompt for Claude."""

    # Current positions block
    if not state.positions.empty:
        positions_lines = []
        for _, pos in state.positions.iterrows():
            ticker = pos["ticker"]
            pnl_pct = pos.get("unrealized_pnl_pct", 0) or 0
            weight = (pos["market_value"] / state.total_equity * 100) if state.total_equity > 0 else 0
            sector = sector_map.get(ticker, "Unknown")
            stop = pos.get("stop_loss", 0) or 0
            target = pos.get("take_profit", 0) or 0
            positions_lines.append(
                f"  {ticker}: {pos['shares']} shares @ ${pos['current_price']:.2f}, "
                f"P&L {pnl_pct:+.1f}%, weight {weight:.1f}%, sector: {sector}, "
                f"stop ${stop:.2f}, target ${target:.2f}"
            )
        positions_block = "CURRENT POSITIONS:\n" + "\n".join(positions_lines)
    else:
        positions_block = "CURRENT POSITIONS: None (new portfolio — start fresh)"

    # Sector allocation
    sector_totals: dict = {}
    if not state.positions.empty:
        for _, pos in state.positions.iterrows():
            sec = sector_map.get(pos["ticker"], "Unknown")
            sector_totals[sec] = sector_totals.get(sec, 0.0) + float(pos.get("market_value", 0) or 0)

    sector_block = ""
    if sector_totals and state.total_equity > 0:
        sector_lines = []
        for sec, val in sorted(sector_totals.items(), key=lambda x: x[1], reverse=True):
            sector_lines.append(f"  {sec}: {val / state.total_equity * 100:.1f}%")
        sector_block = "CURRENT SECTOR ALLOCATION:\n" + "\n".join(sector_lines) + "\n"

    # Layer 1 sells block
    freed_cash = sum(s.shares * s.price for s in layer1_sells)
    if layer1_sells:
        l1_lines = []
        for s in layer1_sells:
            proceeds = s.shares * s.price
            l1_lines.append(
                f"  SELL {s.ticker}: {s.shares} shares @ ${s.price:.2f} = ${proceeds:,.0f} freed — {s.reason}"
            )
        l1_block = (
            "LAYER 1 MECHANICAL SELLS (executing regardless — factor freed cash into your budget):\n"
            + "\n".join(l1_lines) + "\n"
        )
    else:
        l1_block = "LAYER 1 MECHANICAL SELLS: None\n"

    def _pct(v) -> str:
        return f"{v * 100:+.1f}%" if v is not None else "N/A"

    def _num(v) -> str:
        return f"{v:.1f}" if v is not None else "N/A"

    cand_lines = []

    if full_watchlist:
        # Compact mode: 1 line per stock, all candidates visible
        # Drop earnings_growth/quality factor scores (always 50 in AI-driven — useless noise)
        # Format: TICKER | score | price | sector | pm=X vt=X vol=X vlty=X | revG=X gm=X P/E=X
        candidates_to_show = scored_candidates  # ALL of them
        for c in candidates_to_show:
            ticker = c["ticker"]
            score = c.get("composite_score", 0)
            price = c.get("current_price", 0)
            sector = sector_map.get(ticker, c.get("sector", "Unknown"))
            factors = c.get("factor_scores", {})
            pm = factors.get("price_momentum", 50)
            vt = factors.get("value_timing", 50)
            vol = factors.get("volume", 50)
            vlty = factors.get("volatility", 50)
            factor_part = f"pm={pm:.0f} vt={vt:.0f} vol={vol:.0f} vlty={vlty:.0f}"

            fund_part = ""
            if info_cache:
                info = info_cache.get(ticker, {})
                if info:
                    rg = _pct(info.get("revenueGrowth"))
                    gm = _pct(info.get("grossMargins"))
                    pe = _num(info.get("trailingPE"))
                    fund_part = f" | revG={rg} gm={gm} P/E={pe}"

            cand_lines.append(
                f"\n  {ticker} | {score:.0f} | ${price:.2f} | {sector} | {factor_part}{fund_part}"
            )

        header = f"ALL {len(candidates_to_show)} WATCHLIST CANDIDATES (sorted highest to lowest quant score — advisory data; you may pick any):"

    else:
        # Detailed mode: top 50, multi-line per stock (original behavior)
        top_n = 50
        candidates_to_show = scored_candidates[:top_n]
        for c in candidates_to_show:
            ticker = c["ticker"]
            score = c.get("composite_score", 0)
            price = c.get("current_price", 0)
            sector = sector_map.get(ticker, c.get("sector", "Unknown"))
            factors = c.get("factor_scores", {})
            factor_str = ", ".join(f"{k}={v:.0f}" for k, v in factors.items())
            cand_lines.append(f"\n  {ticker}: score={score:.0f}/100, ${price:.2f}, sector={sector}")
            cand_lines.append(f"    factors: [{factor_str}]")

            if info_cache:
                info = info_cache.get(ticker, {})
                if info:
                    rev_growth = info.get("revenueGrowth")
                    gross_margin = info.get("grossMargins")
                    t_pe = info.get("trailingPE")
                    roe = info.get("returnOnEquity")
                    d2e = info.get("debtToEquity")
                    cand_lines.append(
                        f"    fundamentals: rev_growth={_pct(rev_growth)}, "
                        f"gross_margin={_pct(gross_margin)}, P/E={_num(t_pe)}, "
                        f"ROE={_pct(roe)}, D/E={_num(d2e)}"
                    )

        header = f"WATCHLIST CANDIDATES (top {len(candidates_to_show)} by quant score — advisory data for your reasoning, sorted highest to lowest):"

    candidates_block = header + "".join(cand_lines)

    # Regime context block — rich market data for Claude's judgment
    if regime_analysis is not None:
        gap = regime_analysis.sma_200_gap_pct
        ret_20d = regime_analysis.recent_return_20d
        gap_dir = "above" if gap >= 0 else "below"
        regime_block = (
            f"MARKET REGIME ({regime_analysis.benchmark_symbol}):\n"
            f"  Regime: {regime_analysis.regime.value} ({regime_analysis.regime_strength})\n"
            f"  Benchmark price: ${regime_analysis.current_price:.2f} — {gap:+.1f}% {gap_dir} 200d SMA\n"
            f"  50d SMA: ${regime_analysis.sma_50:.2f} | 200d SMA: ${regime_analysis.sma_200:.2f}\n"
            f"  20-day benchmark return: {ret_20d:+.1f}%\n"
            f"  Note: Regime is context for your judgment — not a mechanical constraint.\n"
            f"        Adjust selectivity and sizing as your mandate demands.\n"
        )
    else:
        regime_block = f"MARKET REGIME: {regime.value}\n"

    prompt = f"""You are the portfolio manager for this trading portfolio. You have FULL AUTHORITY over stock selection and position sizing.

YOUR MANDATE — STRATEGY DNA:
{strategy_dna or "Generate alpha through disciplined stock selection. Buy high-quality companies with strong momentum. Preserve capital. Manage risk tightly."}

PORTFOLIO STATE:
- Total Equity: ${state.total_equity:,.0f}
- Current Cash: ${state.cash:,.0f}
- Cash After Layer 1 Sells: ${state.cash + freed_cash:,.0f} (available for new buys)
- Current Positions: {state.num_positions}

{positions_block}

{sector_block}
{regime_block}
{l1_block}
{candidates_block}

HARD CONSTRAINTS (non-negotiable):
1. Total cost of ALL buys MUST NOT exceed available cash: ${available_cash:,.2f}
2. Every BUY entry in allocation_plan MUST include stop_loss and take_profit
3. No single position may exceed 25% of total equity (${state.total_equity * 0.25:,.0f})
4. "shares" must be positive integers (whole shares only)
5. Use candidate list prices as reference (up to 4 hours old — may differ slightly from live)

YOUR AUTHORITY:
- Quant scores are DATA INPUTS to inform your reasoning — they are NOT constraints
- You MAY buy low-scoring stocks if they fit the strategy DNA
- You MAY skip high-scoring stocks that don't fit the strategy
- You MAY propose 0 buys if conditions don't warrant new positions
- You MAY propose additional sells (beyond Layer 1) if positions are misaligned with the strategy
- You determine position sizes based on conviction, not config percentages

Respond ONLY with valid JSON in this exact format (no markdown, no extra text):
{{
  "allocation_plan": [
    {{
      "ticker": "SYMBOL",
      "shares": 10,
      "price": 150.00,
      "stop_loss": 138.00,
      "take_profit": 180.00,
      "reasoning": "Why this fits the strategy DNA and current conditions"
    }}
  ],
  "sells": [
    {{
      "ticker": "SYMBOL",
      "shares": 5,
      "price": 200.00,
      "reasoning": "Why selling this improves portfolio alignment"
    }}
  ],
  "portfolio_thesis": "Your overall allocation rationale and market view",
  "cash_after_plan": 5000.00
}}

"allocation_plan" = new buys. "sells" = AI-initiated sells beyond Layer 1 mechanicals (use sparingly — only when genuinely misaligned with strategy). If no buys, return empty array. If no extra sells, return empty array."""

    return prompt


# ─── Validation ───────────────────────────────────────────────────────────────

def _validate_allocation(
    allocation_data: dict,
    available_cash: float,
    total_equity: float,
    scored_candidates: list,
    held_tickers: set = None,
) -> tuple[list, list]:
    """
    Enforce hard constraints on AI allocation output.

    Returns:
        (valid_buys, ai_sells) — filtered and capped lists
    """
    price_map = {c["ticker"]: c.get("current_price", 0) for c in scored_candidates}
    max_position = total_equity * 0.25
    if held_tickers is None:
        held_tickers = set()

    valid_buys = []
    running_cost = 0.0

    for buy in allocation_data.get("allocation_plan", []):
        ticker = str(buy.get("ticker", "")).strip().upper()
        if not ticker:
            continue

        shares = buy.get("shares", 0)
        price = buy.get("price", 0.0)
        stop_loss = buy.get("stop_loss")
        take_profit = buy.get("take_profit")
        reasoning = buy.get("reasoning", "AI allocation")

        # Shares must be positive integer
        try:
            shares = int(float(shares))
        except (TypeError, ValueError):
            print(f"  [Validate] Skipping {ticker}: invalid shares {buy.get('shares')}")
            continue
        if shares < 1:
            print(f"  [Validate] Skipping {ticker}: shares < 1")
            continue

        # Must have stop and target
        if stop_loss is None or take_profit is None:
            print(f"  [Validate] Skipping {ticker}: missing stop_loss or take_profit")
            continue

        try:
            price = float(price)
            stop_loss = float(stop_loss)
            take_profit = float(take_profit)
        except (TypeError, ValueError):
            print(f"  [Validate] Skipping {ticker}: invalid numeric values")
            continue

        if price <= 0:
            print(f"  [Validate] Skipping {ticker}: invalid price ${price}")
            continue

        # Stop must be below buy price, target must be above buy price
        if stop_loss >= price:
            print(f"  [Validate] Skipping {ticker}: stop_loss ${stop_loss:.2f} >= price ${price:.2f} (would trigger immediately)")
            continue
        if take_profit <= price:
            print(f"  [Validate] Skipping {ticker}: take_profit ${take_profit:.2f} <= price ${price:.2f}")
            continue

        # Cross-check price against scored price (5% tolerance)
        scored_price = price_map.get(ticker, 0)
        if scored_price > 0:
            drift = abs(price - scored_price) / scored_price
            if drift > 0.05:
                original_cost = shares * price
                price = scored_price
                shares = max(1, int(original_cost / price))
                print(f"  [Validate] {ticker}: price adjusted ${buy.get('price', 0):.2f} → ${price:.2f} (>5% drift from quant cache)")

        # Cap to 25% equity limit
        cost = shares * price
        if cost > max_position:
            shares = max(1, int(max_position / price))
            cost = shares * price
            print(f"  [Validate] {ticker}: capped at 25% equity limit → {shares} shares")

        # Cap to remaining cash
        if running_cost + cost > available_cash:
            affordable = max(0, int((available_cash - running_cost) / price))
            if affordable < 1:
                print(f"  [Validate] Skipping {ticker}: insufficient cash (${available_cash - running_cost:,.0f} remaining)")
                continue
            shares = affordable
            cost = shares * price
            print(f"  [Validate] {ticker}: reduced to {shares} shares (cash constraint)")

        running_cost += cost
        valid_buys.append({
            "ticker": ticker,
            "shares": shares,
            "price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reasoning": reasoning,
        })

    # AI-initiated sells (use from allocation data, basic validation only)
    ai_sells = []
    for sell in allocation_data.get("sells", []):
        ticker = str(sell.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        try:
            shares = int(float(sell.get("shares", 0)))
            price = float(sell.get("price", 0))
        except (TypeError, ValueError):
            continue
        if shares < 1 or price <= 0:
            continue
        ai_sells.append({
            "ticker": ticker,
            "shares": shares,
            "price": price,
            "reasoning": sell.get("reasoning", "AI-initiated sell"),
        })

    return valid_buys, ai_sells


# ─── Action Conversion ────────────────────────────────────────────────────────

def _convert_to_reviewed_actions(
    valid_buys: list,
    ai_sells: list,
    regime: MarketRegime,
) -> list[ReviewedAction]:
    """Wrap validated AI allocation as ReviewedAction(APPROVE) objects."""
    result = []

    for buy in valid_buys:
        action = ProposedAction(
            action_type="BUY",
            ticker=buy["ticker"],
            shares=buy["shares"],
            price=buy["price"],
            stop_loss=buy["stop_loss"],
            take_profit=buy["take_profit"],
            quant_score=0,  # AI-driven — no single quant score
            factor_scores={},
            regime=regime.value,
            reason="AI allocation",
        )
        result.append(ReviewedAction(
            original=action,
            decision=ReviewDecision.APPROVE,
            ai_reasoning=buy["reasoning"],
            confidence=0.9,
        ))

    for sell in ai_sells:
        action = ProposedAction(
            action_type="SELL",
            ticker=sell["ticker"],
            shares=sell["shares"],
            price=sell["price"],
            stop_loss=0.0,
            take_profit=0.0,
            quant_score=0,
            factor_scores={},
            regime=regime.value,
            reason="AI allocation",
        )
        result.append(ReviewedAction(
            original=action,
            decision=ReviewDecision.APPROVE,
            ai_reasoning=sell["reasoning"],
            confidence=0.9,
        ))

    return result


# ─── JSON Parsing ─────────────────────────────────────────────────────────────

def _parse_json(response_text: str) -> dict:
    """Parse JSON from AI response, handling markdown blocks and formatting."""
    clean = response_text.strip()

    # Strip markdown code fences
    if "```json" in clean:
        clean = clean.split("```json")[1].split("```")[0]
    elif "```" in clean:
        parts = clean.split("```")
        if len(parts) >= 2:
            clean = parts[1]

    clean = clean.strip()

    # Find JSON boundaries if not at start
    if not clean.startswith("{"):
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start >= 0 and end > start:
            clean = clean[start:end]
        else:
            raise ValueError(f"No JSON object found in AI response: {clean[:200]}")

    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        # Attempt to fix trailing commas (common LLM artifact)
        fixed = re.sub(r",(\s*[}\]])", r"\1", clean)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            raise ValueError(f"Could not parse JSON from AI response: {str(e)[:100]}")
