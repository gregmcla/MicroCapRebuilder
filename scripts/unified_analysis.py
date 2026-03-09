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
import uuid
from datetime import date, datetime

from schema import Action, Reason
from stock_scorer import StockScorer
from market_regime import MarketRegime, get_position_size_multiplier
from risk_manager import RiskManager
from opportunity_layer import OpportunityLayer
from composition_layer import CompositionLayer
from capital_preservation import get_preservation_status
from early_warning import get_warning_severity
from enhanced_structures import ProposedAction
from ai_review import (
    ReviewedAction, ReviewDecision,
    review_proposed_actions, format_review_summary
)
from post_mortem import PostMortemAnalyzer, save_post_mortem
from factor_learning import apply_weight_adjustments as _apply_weight_adjustments
from data_files import get_mode_indicator
from portfolio_state import (
    load_portfolio_state,
    load_watchlist,
    save_transactions_batch,
    update_position,
    remove_position,
    save_positions,
    fetch_prices_batch,
)
from risk_layer import RiskLayer
from stock_discovery import prewarm_info_for_tickers
from execution_sequencer import ExecutionSequencer
from data_files import get_watchlist_file
from trade_analyzer import TradeAnalyzer


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
                # Social signals
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
                reason=buy_proposal.rationale
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
        l3_sector_map: dict = {}
        try:
            watchlist_file = get_watchlist_file(state.portfolio_id)
            if watchlist_file.exists():
                with open(watchlist_file) as _wf:
                    for _line in _wf:
                        if _line.strip():
                            _entry = json.loads(_line)
                            if _entry.get("sector"):
                                l3_sector_map[_entry["ticker"]] = _entry["sector"]
        except Exception:
            pass

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
                reason=buy_proposal.rationale
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
                scorer = StockScorer()
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

    # ─── Step 3: AI Review ────────────────────────────────────────────────────
    print("AI reviewing proposed actions...")

    # Build sector map: positions.csv sector column (most reliable) + watchlist
    sector_map = {}
    # 1. Seed from positions.csv sector column (set at buy time)
    if not state.positions.empty and "sector" in state.positions.columns:
        for _, pos in state.positions.iterrows():
            s = str(pos.get("sector", "")).strip()
            if s and s not in ("", "nan", "Unknown"):
                sector_map[pos["ticker"]] = s
    # 2. Fill in missing from watchlist
    try:
        watchlist_file = get_watchlist_file(state.portfolio_id)
        if watchlist_file.exists():
            with open(watchlist_file) as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("sector") and entry["ticker"] not in sector_map:
                            sector_map[entry["ticker"]] = entry["sector"]
    except Exception:
        pass

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
    }

    return result


def execute_approved_actions(analysis_result: dict, portfolio_id: str = None) -> dict:
    """
    Execute the approved and modified actions from unified analysis.

    Returns:
        dict with execution results
    """
    approved = analysis_result.get("approved", [])
    modified = analysis_result.get("modified", [])

    actions_to_execute = approved + modified
    if not actions_to_execute:
        return {"executed": 0, "message": "No actions to execute"}

    # Load fresh state for execution with live prices so stop/target checks use today's prices
    state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)
    transactions = []

    # Fetch live prices for ALL tickers (buys and sells) so we record the real
    # fill price, not the stale cache price from analyze time.
    all_tickers = [r.original.ticker for r in actions_to_execute]
    if all_tickers:
        live_prices, _, _ = fetch_prices_batch(all_tickers)
        for reviewed in actions_to_execute:
            action = reviewed.original
            fresh = live_prices.get(action.ticker)
            if not fresh or fresh <= 0:
                continue
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
                continue
            # BUY: cap to what cash can afford
            if action.price > 0:
                max_affordable = int(available_cash / action.price)
            else:
                max_affordable = 0
            if max_affordable < 1:
                print(f"  ⏭️  Skipping BUY {action.ticker}: insufficient cash (need ${shares * action.price:,.0f}, have ${available_cash:,.0f})")
                continue
            if shares > max_affordable:
                print(f"  ⚠️  {action.ticker}: Capping shares {shares} → {max_affordable} (cash constraint)")
                shares = max_affordable
            available_cash -= shares * action.price

        tx = {
            "transaction_id": str(uuid.uuid4())[:8],
            "date": date.today().isoformat(),
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
        }
        validated.append((reviewed, tx))

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
                    save_post_mortem(pm)
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

    return {"executed": len(transactions), "transactions": transactions}


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
