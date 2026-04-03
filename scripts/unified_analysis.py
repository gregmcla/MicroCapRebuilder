#!/usr/bin/env python3
"""
Unified Analysis Engine - The single source of truth for trading decisions.

This module combines:
1. Quantitative scoring (momentum, volatility, volume, relative strength)
2. Stop loss/take profit trigger checking
3. AI review and reasoning
4. Safety rails enforcement

Output is a unified set of recommendations that can be executed.

Usage:
    from unified_analysis import run_unified_analysis, execute_approved_actions

    result = run_unified_analysis()
    # result contains proposed_buys, proposed_sells, all with AI review

    execute_approved_actions(result)
"""

import json
import logging
import os
import uuid
from datetime import date, datetime
from pathlib import Path

from schema import Action, Reason
from stock_scorer import StockScorer
from market_regime import MarketRegime, get_position_size_multiplier
from opportunity_layer import OpportunityLayer
from composition_layer import CompositionLayer
from capital_preservation import get_preservation_status
from early_warning import get_warning_severity, get_warnings
from enhanced_structures import ProposedAction
from analytics import PortfolioAnalytics
from ai_review import (
    ReviewedAction, ReviewDecision,
    review_proposed_actions, format_review_summary
)
from post_mortem import PostMortemAnalyzer, save_post_mortem
from factor_learning import apply_weight_adjustments as _apply_weight_adjustments, FactorLearner
from data_files import get_mode_indicator, get_transactions_file
from portfolio_state import (
    load_portfolio_state,
    load_watchlist,
    save_transactions_batch,
    update_position,
    remove_position,
    save_positions,
    fetch_prices_batch,
)
from public_quotes import fetch_live_quotes, is_configured as public_api_configured
from risk_layer import RiskLayer
from stock_discovery import prewarm_info_for_tickers
from execution_sequencer import ExecutionSequencer
from data_files import get_watchlist_file
from trade_analyzer import TradeAnalyzer
from ai_allocator import run_ai_allocation
from reentry_guard import get_reentry_context


# ─── Shared Helpers ───────────────────────────────────────────────────────────

def _build_sector_map(state) -> dict:
    """Build a ticker→sector dict from positions CSV then watchlist (positions win)."""
    sector_map: dict = {}
    if not state.positions.empty and "sector" in state.positions.columns:
        for _, pos in state.positions.iterrows():
            s = str(pos.get("sector", "")).strip()
            if s and s not in ("", "nan", "Unknown"):
                sector_map[pos["ticker"]] = s
    try:
        watchlist_file = get_watchlist_file(state.portfolio_id)
        if watchlist_file.exists():
            with open(watchlist_file) as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("sector") and entry["ticker"] not in sector_map:
                            sector_map[entry["ticker"]] = entry["sector"]
    except Exception as e:
        print(f"Warning: failed to build sector map from watchlist: {e}")
    return sector_map


# ─── AI-Driven Analysis Helper ────────────────────────────────────────────────

def _run_ai_driven_analysis(
    state,
    regime,
    warning_severity: str,
    stale_positions: dict,
    layer1_sell_actions: list,
) -> dict:
    """
    AI-driven path: Layer 1 mechanicals + Claude as full portfolio manager.

    Replaces Layers 2-4 and AI review. Returns result dict in the same shape
    as the mechanical path so execute_approved_actions() works unchanged.
    """
    config = state.config
    strategy_dna = config.get("strategy_dna") or config.get("strategy", {}).get("strategy_dna", "")

    rg_config = config.get("enhanced_trading", {}).get("reentry_guard", {})
    rg_enabled = bool(rg_config.get("enabled", True))
    rg_lookback = int(rg_config.get("lookback_days", 30))
    rg_threshold = float(rg_config.get("meaningful_change_threshold_pts", 10))
    tx_file = get_transactions_file(state.portfolio_id)

    # Load watchlist and filter already-held tickers
    try:
        from watchlist_manager import WatchlistManager
        wm = WatchlistManager(portfolio_id=state.portfolio_id)
        wl_entries = wm._load_watchlist()
        wl_tickers = [e.ticker for e in wl_entries if e.status == "ACTIVE"]
    except Exception as e:
        print(f"  [AI-Driven] Watchlist load failed: {e}")
        wl_tickers = []

    current_tickers = set(state.positions["ticker"].tolist()) if not state.positions.empty else set()
    candidates = [t for t in wl_tickers if t not in current_tickers]

    # Pre-warm info cache for fundamentals
    info_cache = {}
    if candidates:
        try:
            info_cache = prewarm_info_for_tickers(candidates)
        except Exception as e:
            print(f"  [AI-Driven] Info pre-warm failed (non-fatal): {e}")

    # Score candidates (quant data as advisory input for Claude)
    scored_candidates = []
    if candidates:
        print(f"  Scoring {len(candidates)} watchlist candidate(s) for AI input...")
        scorer = StockScorer(config=state.config)
        scored_results = scorer.score_watchlist(candidates)
        for s in scored_results:
            if s:
                current_scores = {
                    "price_momentum": s.price_momentum_score,
                    "earnings_growth": s.earnings_growth_score,
                    "quality": s.quality_score,
                    "value_timing": s.value_timing_score,
                    "volume": s.volume_score,
                    "volatility": s.volatility_score,
                }
                candidate = {
                    "ticker": s.ticker,
                    "composite_score": s.composite_score,
                    "current_price": s.current_price,
                    "factor_scores": current_scores,
                    "reentry_context": None,
                }
                if rg_enabled:
                    try:
                        candidate["reentry_context"] = get_reentry_context(
                            ticker=s.ticker,
                            transactions_path=tx_file,
                            current_scores=current_scores,
                            lookback_days=rg_lookback,
                            meaningful_change_threshold_pts=rg_threshold,
                        )
                    except Exception as e:
                        logging.warning("reentry_guard: AI path failed for %s: %s", s.ticker, e)
                scored_candidates.append(candidate)
        scored_candidates.sort(key=lambda x: x["composite_score"], reverse=True)
        print(f"  Scored {len(scored_candidates)} candidate(s) for AI review")

    # ─── Gather rich context for AI prompt ─────────────────────────────────────
    prompt_extras: dict = {
        "trade_stats": None,
        "portfolio_metrics": None,
        "warnings": [],
        "days_since_last_buy": None,
        "factor_summary": None,
    }
    _portfolio_id = state.portfolio_id

    try:
        prompt_extras["warnings"] = get_warnings(portfolio_id=_portfolio_id) or []
    except Exception as e:
        print(f"  [AI-Driven] Warnings fetch failed (non-fatal): {e}")

    try:
        trade_stats = TradeAnalyzer(portfolio_id=_portfolio_id).calculate_trade_stats()
        prompt_extras["trade_stats"] = trade_stats
    except Exception as e:
        print(f"  [AI-Driven] TradeAnalyzer failed (non-fatal): {e}")

    try:
        prompt_extras["portfolio_metrics"] = PortfolioAnalytics(portfolio_id=_portfolio_id).calculate_all_metrics()
    except Exception as e:
        print(f"  [AI-Driven] PortfolioAnalytics failed (non-fatal): {e}")

    try:
        import pandas as _pd
        if not state.transactions.empty:
            buys = state.transactions[state.transactions["action"] == "BUY"]
            if not buys.empty:
                last_buy_date = _pd.to_datetime(buys["date"], format="mixed").max().date()
                prompt_extras["days_since_last_buy"] = (date.today() - last_buy_date).days
    except Exception as e:
        print(f"  [AI-Driven] Cash idle time failed (non-fatal): {e}")

    try:
        summary = FactorLearner(portfolio_id=_portfolio_id).get_factor_summary()
        if summary.get("status") == "ok":
            prompt_extras["factor_summary"] = summary
    except Exception as e:
        print(f"  [AI-Driven] FactorLearner failed (non-fatal): {e}")

    # Build sector map from positions + watchlist
    sector_map = _build_sector_map(state)

    # Run AI allocation
    print("\n  🤖 AI-DRIVEN MODE — Claude is the portfolio manager")
    reviewed_actions = run_ai_allocation(
        state=state,
        layer1_sells=layer1_sell_actions,
        scored_candidates=scored_candidates,
        sector_map=sector_map,
        regime=regime,
        warning_severity=warning_severity,
        strategy_dna=strategy_dna,
        info_cache=info_cache,
        regime_analysis=state.regime_analysis,
        prompt_extras=prompt_extras,
    )
    import ai_allocator as _ai_alloc_mod
    ai_mode = _ai_alloc_mod._last_ai_mode

    # Split by decision (all will be APPROVE in AI-driven mode)
    approved = [r for r in reviewed_actions if r.decision == ReviewDecision.APPROVE]
    proposed_actions = [r.original for r in reviewed_actions]

    # Portfolio context (required by execute_approved_actions for sector tagging)
    portfolio_context = {
        "total_equity": state.total_equity,
        "cash": state.cash,
        "num_positions": state.num_positions,
        "regime": regime.value,
        "win_rate": 0.5,
        "positions": [
            {
                "ticker": pos["ticker"],
                "sector": sector_map.get(pos["ticker"], "Unknown"),
                "shares": pos["shares"],
                "pnl_pct": pos.get("unrealized_pnl_pct", 0),
                "weight": (pos["market_value"] / state.total_equity * 100) if state.total_equity > 0 else 0,
            }
            for _, pos in state.positions.iterrows()
        ] if not state.positions.empty else [],
        "sector_map": sector_map,
        "stale_positions_note": "",
        "system_warning_level": warning_severity,
        "system_warning_note": "",
    }

    return {
        "proposed_actions": proposed_actions,
        "reviewed_actions": reviewed_actions,
        "approved": approved,
        "modified": [],
        "vetoed": [],
        "summary": {
            "total_proposed": len(proposed_actions),
            "approved": len(approved),
            "modified": 0,
            "vetoed": 0,
            "can_execute": len(approved) > 0,
        },
        "portfolio_context": portfolio_context,
        "regime": regime.value,
        "timestamp": datetime.now().isoformat(),
        "stale_positions": stale_positions,
        "ai_mode": ai_mode,
    }


# ─── Unified Analysis ─────────────────────────────────────────────────────────

def run_unified_analysis(dry_run: bool = True, portfolio_id: str = None) -> dict:
    """
    Run the complete unified analysis pipeline.

    Steps:
    1. Check stop loss / take profit triggers (sells)
    2. Score watchlist candidates (potential buys)
    3. AI reviews all proposed actions
    4. Return unified recommendations

    Args:
        dry_run: If True, don't execute - just return recommendations

    Returns:
        dict with keys:
            - proposed_sells: List of sell recommendations (stop/target triggers)
            - proposed_buys: List of buy recommendations (scored candidates)
            - reviewed_actions: All actions after AI review
            - summary: Human-readable summary
            - can_execute: Whether there are actions to execute
    """
    print(f"\n{'='*60}")
    print(f"UNIFIED ANALYSIS - {get_mode_indicator()}")
    print(f"{'='*60}\n")

    # Single state load replaces 5 separate loads
    state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)
    config = state.config
    regime = state.regime
    position_multiplier = get_position_size_multiplier(regime)

    print(f"Portfolio: ${state.total_equity:,.0f} | Cash: ${state.cash:,.0f} | Positions: {state.num_positions}")
    print(f"Market Regime: {regime.value} | Position Multiplier: {position_multiplier:.0%}")
    print()

    # Check preservation mode
    try:
        preservation = get_preservation_status()
        preservation_active = preservation.active
        if preservation_active:
            print("⚠️  CAPITAL PRESERVATION MODE ACTIVE - No new buys")
    except Exception as e:
        print(f"  [WARN] Capital preservation check failed: {e}")
        print(f"  [WARN] Defaulting to preservation_active=True (safe default)")
        preservation_active = True  # Fail safe: halt buys on error

    # Check early warning severity (Bug #9)
    try:
        warning_severity = get_warning_severity(portfolio_id=portfolio_id)
        if warning_severity == "DANGER":
            print("🔴 EARLY WARNING: DANGER level — position sizing reduced 50%")
        elif warning_severity == "CAUTION":
            print("🟠 EARLY WARNING: CAUTION level — position sizing reduced 25%")
    except Exception as e:
        print(f"  [WARN] Early warning severity check failed: {e}")
        warning_severity = "NORMAL"

    info_cache: dict = {}  # Pre-warmed fundamental data for scoring and AI review

    proposed_actions = []

    # ─── Step 1: Layer 1 Risk Management (Dynamic Stops + Re-evaluation) ─────
    print("Running Layer 1: Risk Management...")

    layer1 = RiskLayer(config)
    layer1_output = layer1.process(state)

    # Convert SellProposal objects to ProposedAction objects
    for sell_proposal in layer1_output["sell_proposals"]:
        proposed_actions.append(ProposedAction(
            action_type="SELL",
            ticker=sell_proposal.ticker,
            shares=sell_proposal.shares,
            price=sell_proposal.current_price,
            stop_loss=sell_proposal.stop_loss,
            take_profit=sell_proposal.take_profit,
            quant_score=0,  # N/A for sells
            factor_scores={},
            regime=regime.value,
            reason=sell_proposal.reason
        ))

        # Print with appropriate emoji based on urgency
        emoji = "🚨" if sell_proposal.urgency_score >= 90 else \
                "🔴" if sell_proposal.urgency_score >= 70 else \
                "🟡" if sell_proposal.urgency_score >= 50 else "🟢"
        print(f"  {emoji} {sell_proposal.ticker}: {sell_proposal.reason} (urgency={sell_proposal.urgency_score})")

    # Report deterioration alerts (warnings, not sells)
    if layer1_output["deterioration_alerts"]:
        print(f"\n  ⚠️  {len(layer1_output['deterioration_alerts'])} position(s) deteriorating:")
        for alert in layer1_output["deterioration_alerts"]:
            print(f"     {alert.ticker}: Score dropped {alert.score_drop:.0f} points ({alert.entry_score:.0f} → {alert.current_score:.0f})")

    # Report updated stops
    if layer1_output["updated_stops"]:
        print(f"\n  📊 Dynamic stops calculated for {len(layer1_output['updated_stops'])} position(s)")
        for ticker, stops in layer1_output["updated_stops"].items():
            if stops.stop_type != "fixed":
                print(f"     {ticker}: ${stops.recommended_stop:.2f} ({stops.stop_type} stop)")

    num_sells = len([a for a in proposed_actions if a.action_type == "SELL"])
    print(f"\n  Found {num_sells} sell trigger(s)")
    print()

    # ─── AI-Driven Mode Branch ────────────────────────────────────────────────
    # For AI-driven portfolios, Layers 2-4 and AI review are replaced by a
    # single Claude allocation call. Layer 1 always runs as mechanical safety.
    if config.get("ai_driven"):
        print("=" * 60)
        print("AI-DRIVEN MODE — Claude replaces Layers 2-4")
        print("=" * 60)
        return _run_ai_driven_analysis(
            state=state,
            regime=regime,
            warning_severity=warning_severity,
            stale_positions=state.stale_alerts,
            layer1_sell_actions=proposed_actions,  # contains Layer 1 sells only at this point
        )

    # ─── Step 2: Score Watchlist Candidates ───────────────────────────────────
    # Use Layer 2 (Opportunity Management) if enabled, otherwise fallback to basic scoring
    if config.get("enhanced_trading", {}).get("enable_layers", False):
        print("\nRunning Layer 2: Opportunity Management...")
        layer2 = OpportunityLayer(config)

        # Fetch watchlist tickers once — used for both info pre-warm and social signals
        social_signals = {}
        try:
            from watchlist_manager import WatchlistManager
            _wm = WatchlistManager(portfolio_id=portfolio_id)
            _wl_entries = _wm._load_watchlist()
            _wl_tickers = [e.ticker for e in _wl_entries if e.status == "ACTIVE"]
            if _wl_tickers:
                # Pre-warm fundamental info cache for scoring
                try:
                    info_cache = prewarm_info_for_tickers(_wl_tickers)
                except Exception as e:
                    print(f"[analysis] Info pre-warm failed (non-fatal): {e}")
                # Social signals (disabled when DISABLE_SOCIAL=true)
                if not os.environ.get("DISABLE_SOCIAL"):
                    try:
                        from social_sentiment import SocialSentimentProvider
                        provider = SocialSentimentProvider(portfolio_id=portfolio_id)
                        social_signals = provider.get_signals(_wl_tickers)
                    except Exception as e:
                        print(f"[analysis] Social sentiment fetch failed (non-fatal): {e}")
        except Exception as e:
            print(f"[analysis] Watchlist pre-warm failed (non-fatal): {e}")

        layer2_output = layer2.process(state, layer1_output, social_signals=social_signals, info_cache=info_cache)

        # Convert BuyProposal to ProposedAction for AI review
        stop_loss_pct = config.get("default_stop_loss_pct", 8.0)
        take_profit_pct = config.get("default_take_profit_pct", 20.0)

        for buy_proposal in layer2_output["buy_proposals"]:
            conviction = buy_proposal.conviction_score

            proposed_actions.append(ProposedAction(
                action_type="BUY",
                ticker=buy_proposal.ticker,
                shares=buy_proposal.shares,
                price=buy_proposal.price,
                stop_loss=buy_proposal.price * (1 - stop_loss_pct / 100),
                take_profit=buy_proposal.price * (1 + take_profit_pct / 100),
                quant_score=conviction.composite_score,
                factor_scores=conviction.factors,
                regime=regime.value,
                reason=buy_proposal.rationale,
                reentry_context=buy_proposal.reentry_context,
            ))

            # Enhanced display with conviction info
            patterns_str = ", ".join([p.pattern_type.value for p in conviction.patterns_detected]) if conviction.patterns_detected else "none"
            print(f"  💡 {buy_proposal.ticker}: Conviction {conviction.final_conviction:.1f} ({conviction.conviction_level.value}), {buy_proposal.shares} shares @ ${buy_proposal.price:.2f} = ${buy_proposal.total_value:.2f} ({buy_proposal.position_size_pct:.1f}% of portfolio) - patterns: {patterns_str}")

        # Log rotation proposals
        if layer2_output.get("rotation_sells"):
            print(f"\n  🔄 Portfolio Rotation: {len(layer2_output['rotation_sells'])} swap(s) proposed")
            for sell, buy in zip(layer2_output["rotation_sells"], layer2_output["rotation_buys"]):
                print(f"     SELL {sell.ticker} → BUY {buy.ticker} ({sell.reason})")

        # Track rotation buy tickers so we can block them under preservation (Bug #8)
        rotation_buy_tickers = {b.ticker for b in layer2_output.get("rotation_buys", [])}

        # Merge rotation buys into Layer 3 input so composition checks them too
        all_buys = layer2_output["buy_proposals"] + layer2_output.get("rotation_buys", [])
        layer2_for_l3 = {**layer2_output, "buy_proposals": all_buys}

        # Build sector_map from watchlist so Layer 3 can resolve sectors for
        # proposed buys (watchlist candidates won't be in the static file yet).
        l3_sector_map = _build_sector_map(state)

        # Run Layer 3: Portfolio Composition
        print("\nRunning Layer 3: Portfolio Composition...")
        layer3 = CompositionLayer(config)
        layer3_output = layer3.process(state, layer1_output, layer2_for_l3, sector_map=l3_sector_map)

        # Remove originally proposed buys and add only filtered buys
        proposed_actions = [a for a in proposed_actions if a.action_type != "BUY"]

        # Add filtered buys back — skip rotation buys when preservation is active (Bug #8)
        for buy_proposal in layer3_output["filtered_buys"]:
            is_rotation_buy = buy_proposal.ticker in rotation_buy_tickers
            if preservation_active and is_rotation_buy:
                print(f"  🛡️  Blocked rotation BUY {buy_proposal.ticker}: capital preservation mode active (rotation SELL side still executes)")
                continue
            conviction = buy_proposal.conviction_score
            proposed_actions.append(ProposedAction(
                action_type="BUY",
                ticker=buy_proposal.ticker,
                shares=buy_proposal.shares,
                price=buy_proposal.price,
                stop_loss=buy_proposal.price * (1 - stop_loss_pct / 100),
                take_profit=buy_proposal.price * (1 + take_profit_pct / 100),
                quant_score=conviction.composite_score,
                factor_scores=conviction.factors,
                regime=regime.value,
                reason=buy_proposal.rationale,
                reentry_context=buy_proposal.reentry_context,
            ))

        # Add rebalancing sells
        for rebalance_sell in layer3_output["rebalance_sells"]:
            proposed_actions.append(ProposedAction(
                action_type="SELL",
                ticker=rebalance_sell.ticker,
                shares=rebalance_sell.shares,
                price=rebalance_sell.current_price,
                reason=rebalance_sell.reason,
                stop_loss=0.0,
                take_profit=0.0,
                quant_score=0,
                factor_scores={},
                regime=regime.value,
            ))

        # Add rotation sells
        for sell_proposal in layer2_output.get("rotation_sells", []):
            proposed_actions.append(ProposedAction(
                action_type="SELL",
                ticker=sell_proposal.ticker,
                shares=sell_proposal.shares,
                price=sell_proposal.current_price,
                stop_loss=sell_proposal.stop_loss,
                take_profit=sell_proposal.take_profit,
                quant_score=0,
                factor_scores={},
                regime=regime.value,
                reason=sell_proposal.reason,
                source_proposal=sell_proposal,
            ))

        # Display composition warnings
        for warning in layer3_output["warnings"]:
            print(f"  ⚠️  {warning}")

        # Display blocked buys
        for blocked in layer3_output["blocked_buys"]:
            violation = next((v for v in layer3_output["violations"] if v.ticker == blocked.ticker), None)
            if violation:
                print(f"  🚫 Blocked {blocked.ticker}: {violation.description}")

        num_buys = len([a for a in proposed_actions if a.action_type == "BUY"])
        print(f"  Found {num_buys} buy candidate(s)")
        print()
    else:
        # Fallback to basic scoring if Layer 2 disabled
        print("Scoring watchlist candidates...")

        # Skip buying in bear markets or preservation mode
        if regime == MarketRegime.BEAR:
            print("  ⚠️  Bear market - skipping new buys")
        elif preservation_active:
            print("  ⚠️  Preservation mode - skipping new buys")
        elif state.num_positions >= config.get("max_positions", 15):
            print(f"  ⚠️  At max positions ({state.num_positions}) - skipping new buys")
        else:
            watchlist = load_watchlist(portfolio_id=state.portfolio_id)
            current_tickers = set(state.positions["ticker"].tolist()) if not state.positions.empty else set()
            candidates = [t for t in watchlist if t not in current_tickers]

            if candidates:
                scorer = StockScorer(config=config)
                scored_results = scorer.score_watchlist(candidates)
                # Convert StockScore objects to dicts with factor_scores built from individual attributes
                scored = []
                for s in scored_results:
                    if s:
                        scored.append({
                            "ticker": s.ticker,
                            "composite_score": s.composite_score,
                            "current_price": s.current_price,
                            "factor_scores": {
                                "price_momentum": s.price_momentum_score,
                                "earnings_growth": s.earnings_growth_score,
                                "quality": s.quality_score,
                                "value_timing": s.value_timing_score,
                                "volume": s.volume_score,
                                "volatility": s.volatility_score,
                            }
                        })

                # Filter to top candidates with score >= 60
                top_candidates = [s for s in scored if s.get("composite_score", 0) >= 60]
                top_candidates = sorted(top_candidates, key=lambda x: x.get("composite_score", 0), reverse=True)

                # Calculate position size
                risk_per_trade = config.get("risk_per_trade_pct", 10.0) / 100
                max_position_value = state.total_equity * risk_per_trade * position_multiplier
                stop_loss_pct = config.get("default_stop_loss_pct", 8.0) / 100
                take_profit_pct = config.get("default_take_profit_pct", 20.0) / 100

                slots_available = config.get("max_positions", 15) - state.num_positions
                remaining_cash = state.cash  # Track how much cash is left as we propose buys

                for i, candidate in enumerate(top_candidates[:slots_available]):
                    ticker = candidate["ticker"]
                    price = candidate.get("current_price", 0)
                    score = candidate.get("composite_score", 0)
                    factor_scores = candidate.get("factor_scores", {})

                    if price <= 0:
                        continue

                    # Calculate position size (capped by remaining cash)
                    position_value = min(max_position_value, remaining_cash)
                    shares = int(position_value / price)
                    if shares < 1:
                        print(f"  ⏸️ Skipping {ticker} - insufficient cash (${remaining_cash:.0f} remaining)")
                        continue

                    actual_cost = shares * price
                    if actual_cost > remaining_cash:
                        # Reduce shares to fit remaining cash
                        shares = int(remaining_cash / price)
                        if shares < 1:
                            continue
                        actual_cost = shares * price

                    stop_loss = round(price * (1 - stop_loss_pct), 2)
                    take_profit = round(price * (1 + take_profit_pct), 2)

                    proposed_actions.append(ProposedAction(
                        action_type="BUY",
                        ticker=ticker,
                        shares=shares,
                        price=price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        quant_score=score,
                        factor_scores=factor_scores,
                        regime=regime.value,
                        reason=f"Quant score {score:.0f}/100 - Rank #{i+1}"
                    ))
                    remaining_cash -= actual_cost
                    print(f"  📈 {ticker}: Score {score:.0f}, {shares} shares @ ${price:.2f} (${actual_cost:.0f}, ${remaining_cash:.0f} remaining)")

        num_buys = len([a for a in proposed_actions if a.action_type == "BUY"])
        print(f"  Found {num_buys} buy candidate(s)")
        print()

    # ─── Run Layer 4: Execution Sequencer (if layers enabled) ────────────────
    if config.get("enhanced_trading", {}).get("enable_layers", False):
        print("\nRunning Layer 4: Execution Sequencer...")
        sequencer = ExecutionSequencer(config)
        execution_plan = sequencer.process(state, proposed_actions)

        # Display execution plan
        if execution_plan.sequenced_actions:
            print(f"\n  📋 Execution Plan ({len(execution_plan.sequenced_actions)} actions):")
            for paction in execution_plan.sequenced_actions:
                action = paction.action
                priority_badge = f"[{paction.priority}]"
                action_str = f"{action.action_type} {action.ticker}"
                print(f"  {paction.execution_order}. {priority_badge} {action_str} - {paction.priority_reason}")

        # Display skipped actions
        if execution_plan.skipped_actions:
            print(f"\n  ⏭️  Skipped {len(execution_plan.skipped_actions)} action(s):")
            for skipped in execution_plan.skipped_actions:
                action = skipped["action"]
                print(f"  - {action.action_type} {action.ticker}: {skipped['reason']}")

        # Update proposed_actions to only include sequenced actions
        proposed_actions = [pa.action for pa in execution_plan.sequenced_actions]

    # ─── Bug #9: Apply warning severity position size reductions ─────────────
    # Applied post-hoc to all buy proposals regardless of which path generated them.
    # Drop proposals that would fall below a minimum position value after reduction
    # rather than passing useless micro-positions to AI review.
    if warning_severity in ("CAUTION", "DANGER"):
        size_reduction = 0.25 if warning_severity == "CAUTION" else 0.50
        label = "25%" if warning_severity == "CAUTION" else "50%"
        min_position_value = max(500.0, state.total_equity * 0.005)  # $500 or 0.5% of equity
        reduced_count = 0
        kept_actions = []
        for action in proposed_actions:
            if action.action_type != "BUY":
                kept_actions.append(action)
                continue
            original_shares = action.shares
            new_shares = int(action.shares * (1 - size_reduction))
            position_value = new_shares * action.price
            if new_shares < 1 or position_value < min_position_value:
                print(f"  ⚠️  Dropping {action.ticker} buy: reduced to ${position_value:.0f} ({new_shares} shares) below minimum ${min_position_value:.0f}")
                continue
            action.shares = new_shares
            if action.shares != original_shares:
                reduced_count += 1
            kept_actions.append(action)
        proposed_actions = kept_actions
        if reduced_count:
            print(f"  ⚠️  Warning severity {warning_severity}: reduced shares by {label} on {reduced_count} buy proposal(s)")

    # ─── Price refresh: fetch live prices for all proposed BUY tickers ────────
    # Scoring uses a 4hr disk cache, so proposed prices can be stale. Refresh
    # just the handful of proposed tickers so the Actions tab and AI review
    # both see current market prices. Uses the same rescaling logic as execute time.
    buy_tickers = [a.ticker for a in proposed_actions if a.action_type == "BUY"]
    if buy_tickers:
        try:
            live_prices, _, _ = fetch_prices_batch(buy_tickers)
            for action in proposed_actions:
                if action.action_type != "BUY":
                    continue
                fresh = live_prices.get(action.ticker)
                if not fresh or fresh <= 0:
                    continue
                old_price = action.price
                if abs(fresh - old_price) / max(old_price, 0.01) < 0.001:
                    continue
                stop_pct = (old_price - action.stop_loss) / old_price if old_price > 0 else 0.08
                target_pct = (action.take_profit - old_price) / old_price if old_price > 0 else 0.20
                old_dollar_value = action.shares * old_price
                action.price = round(fresh, 4)
                action.shares = max(1, int(old_dollar_value / fresh))
                action.stop_loss = round(fresh * (1 - stop_pct), 2)
                action.take_profit = round(fresh * (1 + target_pct), 2)
                print(f"  🔄 {action.ticker}: refreshed price ${old_price:.2f} → ${fresh:.2f}")
        except Exception as e:
            print(f"  ⚠️  Price refresh failed (using scorer prices): {e}")

    # ─── Same-run reentry veto ────────────────────────────────────────────────
    # If a ticker appears as both SELL and BUY in the same run, veto the BUY
    # when buy_price >= avg_cost_basis of the position being sold. Buying at or
    # above cost basis in the same run is a no-op trade cycle. Buying below cost
    # basis (lowering avg cost on a dip) is legitimate and allowed.
    if not state.positions.empty:
        sell_cost_basis = {}
        for action in proposed_actions:
            if action.action_type == "SELL":
                matching = state.positions[state.positions["ticker"] == action.ticker]
                if not matching.empty:
                    sell_cost_basis[action.ticker] = float(matching.iloc[0]["avg_cost_basis"])
        if sell_cost_basis:
            vetoed, kept = [], []
            for action in proposed_actions:
                if (action.action_type == "BUY"
                        and action.ticker in sell_cost_basis
                        and action.price >= sell_cost_basis[action.ticker]):
                    logging.info(
                        "Same-run reentry veto: %s buy@%.2f >= avg_cost_basis %.2f",
                        action.ticker, action.price, sell_cost_basis[action.ticker],
                    )
                    vetoed.append(action.ticker)
                else:
                    kept.append(action)
            if vetoed:
                print(f"  🚫 Same-run reentry vetoed for {vetoed}: buy price >= avg cost basis")
            proposed_actions = kept

    # ─── Step 3: AI Review ────────────────────────────────────────────────────
    print("AI reviewing proposed actions...")

    # Build sector map: positions.csv sector column (most reliable) + watchlist
    sector_map = _build_sector_map(state)

    # Compute projected sector breakdown after proposed buys
    projected_sectors: dict = {}
    projected_equity = state.total_equity
    # Seed with current held positions (prefer positions.csv sector column)
    if not state.positions.empty:
        for _, pos in state.positions.iterrows():
            ticker = pos["ticker"]
            pos_sector = str(pos.get("sector", "")).strip() if "sector" in pos.index else ""
            sec = pos_sector if pos_sector and pos_sector not in ("nan", "Unknown", "") \
                else sector_map.get(ticker, "Unknown")
            projected_sectors[sec] = projected_sectors.get(sec, 0.0) + pos["market_value"]
    # Add proposed buys
    buy_proposals = [a for a in proposed_actions if a.action_type == "BUY"]
    for action in buy_proposals:
        sec = sector_map.get(action.ticker, "Unknown")
        projected_sectors[sec] = projected_sectors.get(sec, 0.0) + (action.shares * action.price)
        projected_equity += action.shares * action.price
    # Convert to percentages
    projected_sector_pct = {
        sec: round(val / projected_equity * 100, 1)
        for sec, val in projected_sectors.items()
    } if projected_equity > 0 else {}

    # Surface stale position alerts before AI review
    stale_positions = state.stale_alerts  # dict: ticker -> consecutive_days_without_price_update
    if stale_positions:
        print(f"\n  ⚠️  {len(stale_positions)} position(s) have stale prices (no update for 2+ days):")
        for ticker, days in stale_positions.items():
            print(f"     {ticker}: {days} consecutive day(s) without a price update")

    # Build portfolio context for AI
    stale_note = (
        f"Note: the following positions have stale prices and may not reflect current market "
        f"values (days without update): "
        + ", ".join(f"{t} ({d}d)" for t, d in stale_positions.items())
    ) if stale_positions else ""

    # Calculate real win rate from completed trades using the same path as strategy_health.py
    try:
        _trade_analyzer = TradeAnalyzer()
        _trade_stats = _trade_analyzer.calculate_trade_stats()
        _min_trades_for_win_rate = 5
        if _trade_stats is not None and _trade_stats.total_trades >= _min_trades_for_win_rate:
            win_rate = _trade_stats.win_rate_pct / 100.0
        else:
            win_rate = 0.5  # Fallback: insufficient completed trades
    except Exception as e:
        print(f"  [WARN] Win rate calculation failed: {e}")
        win_rate = 0.5

    # Build warning note for AI context (Bug #9)
    warning_note = ""
    if warning_severity == "DANGER":
        warning_note = (
            "SYSTEM WARNING: Early warning system has flagged DANGER level conditions "
            "(critical warnings active). Position sizes have been reduced 50%. "
            "Apply extra scrutiny to all buy proposals."
        )
    elif warning_severity == "CAUTION":
        warning_note = (
            "SYSTEM WARNING: Early warning system has flagged CAUTION level conditions "
            "(high-severity warnings active). Position sizes have been reduced 25%."
        )

    portfolio_context = {
        "total_equity": state.total_equity,
        "cash": state.cash,
        "num_positions": state.num_positions,
        "regime": regime.value,
        "win_rate": win_rate,
        "positions": [
            {
                "ticker": pos["ticker"],
                "sector": sector_map.get(pos["ticker"], "Unknown"),
                "shares": pos["shares"],
                "pnl_pct": pos.get("unrealized_pnl_pct", 0),
                "weight": (pos["market_value"] / state.total_equity * 100) if state.total_equity > 0 else 0
            }
            for _, pos in state.positions.iterrows()
        ] if not state.positions.empty else [],
        "projected_sector_allocation": projected_sector_pct,
        "sector_map": sector_map,
        "stale_positions_note": stale_note,
        "system_warning_level": warning_severity,
        "system_warning_note": warning_note,
    }

    reviewed_actions = review_proposed_actions(proposed_actions, portfolio_context, info_cache=info_cache)
    print(format_review_summary(reviewed_actions))

    # ─── Build Result ─────────────────────────────────────────────────────────
    approved = [r for r in reviewed_actions if r.decision == ReviewDecision.APPROVE]
    modified = [r for r in reviewed_actions if r.decision == ReviewDecision.MODIFY]
    vetoed = [r for r in reviewed_actions if r.decision == ReviewDecision.VETO]

    # Drop any modified BUY proposals where the AI set shares so low the
    # position would be below the minimum notional floor (e.g. 1 share @ $12)
    def _above_min_notional(r: ReviewedAction) -> bool:
        if r.original.action_type != "BUY":
            return True
        shares = r.modified_shares or r.original.shares
        price = r.original.price
        min_notional = max(price * 5, 250.0)
        return shares * price >= min_notional

    modified = [r for r in modified if _above_min_notional(r)]

    result = {
        "proposed_actions": proposed_actions,
        "reviewed_actions": reviewed_actions,
        "approved": approved,
        "modified": modified,
        "vetoed": vetoed,
        "summary": {
            "total_proposed": len(proposed_actions),
            "approved": len(approved),
            "modified": len(modified),
            "vetoed": len(vetoed),
            "can_execute": len(approved) + len(modified) > 0,
        },
        "portfolio_context": portfolio_context,
        "regime": regime.value,
        "timestamp": datetime.now().isoformat(),
        # stale_positions: dict of ticker -> consecutive_days without a price update (>= 2)
        # Surfaced here so the API and dashboard can display a warning to the user.
        "stale_positions": stale_positions,
        "ai_mode": "mechanical",
    }

    return result


def _normalize_reviewed_action(r):
    """
    Normalize a ReviewedAction to a consistent object regardless of whether
    it came from an in-memory analysis (Python dataclass) or was round-tripped
    through JSON (plain dict). Returns a SimpleNamespace with .original,
    .decision, .modified_shares, .modified_stop, .modified_target.
    """
    from types import SimpleNamespace

    if isinstance(r, dict):
        orig_dict = r.get("original", {}) or {}
        if isinstance(orig_dict, dict):
            original = SimpleNamespace(
                action_type=orig_dict.get("action_type", ""),
                ticker=orig_dict.get("ticker", ""),
                shares=orig_dict.get("shares", 0),
                price=orig_dict.get("price", 0.0),
                stop_loss=orig_dict.get("stop_loss", 0.0),
                take_profit=orig_dict.get("take_profit", 0.0),
                quant_score=orig_dict.get("quant_score", 0.0),
                factor_scores=orig_dict.get("factor_scores", {}),
                regime=orig_dict.get("regime", ""),
                reason=orig_dict.get("reason", ""),
            )
        else:
            original = orig_dict  # already an object
        return SimpleNamespace(
            original=original,
            decision=r.get("decision", "APPROVE"),
            ai_reasoning=r.get("ai_reasoning", ""),
            confidence=r.get("confidence", 0.9),
            modified_shares=r.get("modified_shares"),
            modified_stop=r.get("modified_stop"),
            modified_target=r.get("modified_target"),
        )
    return r  # already a ReviewedAction dataclass


def execute_approved_actions(analysis_result: dict, portfolio_id: str = None) -> dict:
    """
    Execute the approved and modified actions from unified analysis.

    Returns:
        dict with execution results
    """
    approved = [_normalize_reviewed_action(r) for r in analysis_result.get("approved", [])]
    modified = [_normalize_reviewed_action(r) for r in analysis_result.get("modified", [])]

    actions_to_execute = approved + modified
    if not actions_to_execute:
        return {"executed": 0, "message": "No actions to execute"}

    proposed_buys = len([r for r in actions_to_execute if r.original.action_type == "BUY"])
    proposed_sells = len([r for r in actions_to_execute if r.original.action_type == "SELL"])
    dropped_actions = []

    # Load fresh state for execution with live prices so stop/target checks use today's prices
    state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)
    transactions = []

    # Fetch live prices for ALL tickers (buys and sells) so we record the real
    # fill price, not the stale cache price from analyze time.
    # BUYs with no confirmed live price are dropped entirely — never fall back to stale data.
    confirmed_live: set[str] = set()
    bad_data_tickers: set[str] = set()
    all_tickers = [r.original.ticker for r in actions_to_execute]
    if all_tickers:
        # Try Public.com API first — real-time bid/ask data, single batch call.
        # Fall back to yfinance for any tickers the API couldn't quote.
        public_tickers: set[str] = set()
        if public_api_configured():
            pub_prices, pub_failures = fetch_live_quotes(all_tickers)
            public_tickers = set(pub_prices.keys())
            if pub_failures:
                yf_prices, _, prev_closes = fetch_prices_batch(pub_failures)
                live_prices = {**pub_prices, **yf_prices}
            else:
                live_prices, prev_closes = pub_prices, {}
            src = "Public.com" if public_tickers else "yfinance"
            print(f"  📡 Live prices via {src} ({len(public_tickers)} tickers); "
                  f"yfinance fallback for {len(all_tickers) - len(public_tickers)}")
        else:
            live_prices, _, prev_closes = fetch_prices_batch(all_tickers)

        for reviewed in actions_to_execute:
            action = reviewed.original
            fresh = live_prices.get(action.ticker)
            if not fresh or fresh <= 0:
                if action.action_type == "BUY":
                    print(f"  ⛔ {action.ticker}: no live price — buy skipped (won't use stale data)")
                continue
            # Sanity-check: price must be within 2× of yesterday's close.
            # Only needed for yfinance-sourced prices — Public.com prices are real-time
            # and trusted, so skip the check for those.
            prev = prev_closes.get(action.ticker)
            if prev and prev > 0 and action.action_type == "BUY" and action.ticker not in public_tickers:
                ratio = fresh / prev
                if ratio > 2.0 or ratio < 0.5:
                    print(f"  ⛔ {action.ticker}: live price ${fresh:.2f} is {ratio:.2f}× prev_close ${prev:.2f} — bad data, buy skipped")
                    bad_data_tickers.add(action.ticker)
                    continue
            confirmed_live.add(action.ticker)
            old_price = action.price
            if abs(fresh - old_price) / old_price < 0.001:
                continue  # price hasn't moved meaningfully, skip
            if action.action_type == "BUY":
                # Preserve stop/target as % distances from the old price, then rescale
                stop_pct = (old_price - action.stop_loss) / old_price if old_price > 0 else 0.08
                target_pct = (action.take_profit - old_price) / old_price if old_price > 0 else 0.20
                old_dollar_value = action.shares * old_price
                action.price = round(fresh, 4)
                action.shares = max(1, int(old_dollar_value / fresh))
                action.stop_loss = round(fresh * (1 - stop_pct), 2)
                action.take_profit = round(fresh * (1 + target_pct), 2)
                print(f"  🔄 {action.ticker}: refreshed BUY price ${old_price:.2f} → ${fresh:.2f} "
                      f"({action.shares} shares, stop ${action.stop_loss:.2f}, target ${action.take_profit:.2f})")
            else:
                # For sells, just update the price — no stop/target to rescale
                action.price = round(fresh, 4)
                print(f"  🔄 {action.ticker}: refreshed SELL price ${old_price:.2f} → ${fresh:.2f}")

    # Drop any BUY that didn't get a confirmed live price
    before = len(actions_to_execute)
    for r in actions_to_execute:
        if r.original.action_type == "BUY" and r.original.ticker not in confirmed_live:
            reason = "bad price data" if r.original.ticker in bad_data_tickers else "no live price"
            dropped_actions.append({"ticker": r.original.ticker, "reason": reason})
    actions_to_execute = [
        r for r in actions_to_execute
        if r.original.action_type != "BUY" or r.original.ticker in confirmed_live
    ]
    skipped = before - len(actions_to_execute)
    if skipped:
        print(f"  ⛔ Dropped {skipped} buy(s) with no confirmed live price")

    print(f"\n{'='*60}")
    print("EXECUTING APPROVED ACTIONS")
    print(f"{'='*60}\n")

    # Sort: sells first so freed cash is available for buy validation
    actions_to_execute.sort(key=lambda r: 0 if r.original.action_type == "SELL" else 1)

    # Build transactions with running cash validation — one clean pass
    available_cash = state.cash
    validated = []  # list of (reviewed, tx) pairs that passed cash check

    for reviewed in actions_to_execute:
        action = reviewed.original
        shares = reviewed.modified_shares or action.shares
        stop_loss = reviewed.modified_stop or action.stop_loss
        take_profit = reviewed.modified_target or action.take_profit

        if action.action_type == "SELL":
            available_cash += shares * action.price
        else:
            # BUY: reject micro-positions (AI may modify shares to tiny numbers)
            min_notional = max(action.price * 5, 250.0)  # at least 5 shares or $250
            if shares * action.price < min_notional:
                print(f"  ⏭️  Skipping BUY {action.ticker}: position too small ({shares} shares = ${shares * action.price:.0f} < ${min_notional:.0f} minimum)")
                dropped_actions.append({"ticker": action.ticker, "reason": "position too small"})
                continue
            # BUY: cap to what cash can afford
            if action.price > 0:
                max_affordable = int(available_cash / action.price)
            else:
                max_affordable = 0
            if max_affordable < 1:
                print(f"  ⏭️  Skipping BUY {action.ticker}: insufficient cash (need ${shares * action.price:,.0f}, have ${available_cash:,.0f})")
                dropped_actions.append({"ticker": action.ticker, "reason": "insufficient cash"})
                continue
            if shares > max_affordable:
                print(f"  ⚠️  {action.ticker}: Capping shares {shares} → {max_affordable} (cash constraint)")
                shares = max_affordable
            available_cash -= shares * action.price

        # Build trade rationale JSON so the UI can display "why was this trade made"
        _fs = action.factor_scores or {}
        _top_factors = sorted(
            [{"name": k, "score": round(float(v), 1)} for k, v in _fs.items() if k != "composite"],
            key=lambda x: x["score"], reverse=True
        )[:3]
        _ai_decision = reviewed.decision.value if hasattr(reviewed.decision, "value") else str(reviewed.decision)
        _trade_rationale = json.dumps({
            "ai_decision": _ai_decision,
            "ai_confidence": round(float(reviewed.confidence or 0), 3),
            "ai_reasoning": (reviewed.ai_reasoning or "")[:500],
            "quant_reason": action.reason or "",
            "regime": action.regime or "",
            "top_factors": _top_factors,
        })

        tx = {
            "transaction_id": str(uuid.uuid4())[:8],
            "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "ticker": action.ticker,
            "action": action.action_type,
            "shares": shares,
            "price": round(action.price, 2),
            "total_value": round(shares * action.price, 2),
            "stop_loss": round(stop_loss, 2) if action.action_type == "BUY" else "",
            "take_profit": round(take_profit, 2) if action.action_type == "BUY" else "",
            "reason": "SIGNAL" if action.action_type == "BUY" else (
                "STOP_LOSS" if "STOP LOSS" in action.reason else
                "TAKE_PROFIT" if "TAKE PROFIT" in action.reason else
                "STOP_LOSS" if "QUALITY DEGRADATION" in action.reason else
                "MANUAL" if "MANUAL" in action.reason else "INTELLIGENCE"
            ),
            "regime_at_entry": action.regime if action.action_type == "BUY" else "",
            "composite_score": action.quant_score if action.action_type == "BUY" else "",
            "factor_scores": json.dumps(action.factor_scores) if action.action_type == "BUY" else "",
            "signal_rank": "",
            "trade_rationale": _trade_rationale,
        }
        validated.append((reviewed, tx))

    # Filter out sells for tickers not actually held (prevents phantom cash)
    held_tickers = set(state.positions["ticker"].tolist()) if not state.positions.empty else set()
    phantom_sells = [tx["ticker"] for r, tx in validated
                     if r.original.action_type == "SELL" and tx["ticker"] not in held_tickers]
    if phantom_sells:
        print(f"  ⚠️  [Guard] Blocked phantom sells for unheld tickers: {phantom_sells}")
        for ticker in phantom_sells:
            dropped_actions.append({"ticker": ticker, "reason": "not held (phantom sell blocked)"})
    validated = [
        (r, tx) for r, tx in validated
        if r.original.action_type != "SELL" or tx["ticker"] in held_tickers
    ]
    transactions = [tx for _, tx in validated]

    # Save sells first so cash is updated before buy validation runs
    sell_pairs = [(r, tx) for r, tx in validated if r.original.action_type == "SELL"]
    buy_pairs  = [(r, tx) for r, tx in validated if r.original.action_type == "BUY"]

    if sell_pairs:
        state = save_transactions_batch(state, [tx for _, tx in sell_pairs])
    if buy_pairs:
        state = save_transactions_batch(state, [tx for _, tx in buy_pairs])

    # Now update positions and print results
    for reviewed, tx in validated:
        action = reviewed.original
        shares = tx["shares"]

        if action.action_type == "BUY":
            ticker_sector = analysis_result.get("portfolio_context", {}).get(
                "sector_map", {}
            ).get(action.ticker, "")
            state = update_position(state, action.ticker, shares, action.price,
                                    tx["stop_loss"], tx["take_profit"],
                                    sector=ticker_sector)
        elif action.action_type == "SELL":
            pos_row = state.positions[state.positions["ticker"] == action.ticker]
            if pos_row.empty:
                print(f"  ⚠️  Skipping sell {action.ticker}: not in positions")
                dropped_actions.append({"ticker": action.ticker, "reason": "not in positions"})
                continue
            held_shares = int(pos_row["shares"].iloc[0])
            if shares > held_shares:
                print(f"  ⚠️  {action.ticker}: capping sell {shares} → {held_shares} (held)")
                shares = held_shares
            if shares < held_shares:
                # Partial sell: reduce shares, keep avg_cost_basis unchanged
                df = state.positions.copy()
                idx = df[df["ticker"] == action.ticker].index[0]
                remaining = held_shares - shares
                cost = df.at[idx, "avg_cost_basis"]
                df.at[idx, "shares"] = remaining
                df.at[idx, "market_value"] = round(remaining * action.price, 2)
                df.at[idx, "current_price"] = action.price
                df.at[idx, "unrealized_pnl"] = round(remaining * (action.price - cost), 2)
                df.at[idx, "unrealized_pnl_pct"] = round((action.price - cost) / cost * 100 if cost > 0 else 0, 2)
                positions_value = float(df["market_value"].sum())
                from dataclasses import replace as _replace
                state = _replace(state, positions=df, positions_value=positions_value,
                                 total_equity=positions_value + state.cash,
                                 num_positions=len(df))
            else:
                state = remove_position(state, action.ticker)

        mod_note = " (MODIFIED)" if reviewed.decision == ReviewDecision.MODIFY else ""
        print(f"  ✅ {action.action_type} {action.ticker}: {shares} shares @ ${action.price:.2f}{mod_note}")
        print(f"     AI: {reviewed.ai_reasoning}")

    save_positions(state)

    # Generate post-mortems for sells
    sell_data = sell_pairs
    if sell_data:
        print("\n  Generating post-mortems...")
        try:
            analyzer = PostMortemAnalyzer()
            for reviewed, sell_tx in sell_data:
                ticker = sell_tx["ticker"]
                buy_txns = state.transactions[
                    (state.transactions["ticker"] == ticker) &
                    (state.transactions["action"] == "BUY")
                ]
                if not buy_txns.empty:
                    buy_txn = buy_txns.iloc[-1].to_dict()
                    pm = analyzer.analyze_trade(sell_tx, buy_txn, analysis_result.get("regime", "UNKNOWN"))
                    save_post_mortem(pm, portfolio_id=portfolio_id)
                    print(f"    📝 {ticker}: {pm.summary}")
        except Exception as e:
            print(f"    [warn] Post-mortem generation failed: {e}")

    print(f"\n✅ Executed {len(transactions)} action(s)")

    # ─── Periodic Factor Weight Learning ─────────────────────────────────────
    # Apply learned weight adjustments to config after executing trades.
    # Only triggers when there are enough completed trades (threshold enforced
    # inside apply_weight_adjustments → suggest_weight_adjustments → min_trades).
    try:
        if sell_pairs:
            # New sells create new post-mortems — good time to re-evaluate weights
            _apply_weight_adjustments(portfolio_id=portfolio_id)
    except Exception as e:
        print(f"  [factor_learning] Weight adjustment skipped: {e}")

    executed_buys = len([t for t in transactions if t["action"] == "BUY"])
    executed_sells = len([t for t in transactions if t["action"] == "SELL"])
    return {
        "executed": len(transactions),
        "transactions": transactions,
        "execution_summary": {
            "proposed": {"buys": proposed_buys, "sells": proposed_sells},
            "executed": {"buys": executed_buys, "sells": executed_sells},
            "dropped": dropped_actions,
            "ai_mode": analysis_result.get("ai_mode", "unknown"),
        },
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Unified Analysis Engine")
    parser.add_argument("--execute", action="store_true", help="Execute approved actions")
    parser.add_argument("--dry-run", action="store_true", help="Show recommendations without executing")
    parser.add_argument("--portfolio", default=None, help="Portfolio ID (default: registry default)")
    args = parser.parse_args()

    result = run_unified_analysis(dry_run=not args.execute, portfolio_id=args.portfolio)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total Proposed: {result['summary']['total_proposed']}")
    print(f"Approved: {result['summary']['approved']}")
    print(f"Modified: {result['summary']['modified']}")
    print(f"Vetoed: {result['summary']['vetoed']}")
    print(f"Can Execute: {result['summary']['can_execute']}")

    if args.execute and result['summary']['can_execute']:
        execute_approved_actions(result, portfolio_id=args.portfolio)
