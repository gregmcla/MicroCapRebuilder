import sys
sys.path.insert(0, "scripts")


def test_spiking_heat_appears_in_prompt():
    """When a buy has SPIKING heat, the AI prompt must contain a pump warning."""
    from ai_review import _build_review_prompt
    from social_sentiment import SocialSignal

    action = {
        "action_type": "BUY",
        "ticker": "MEME",
        "shares": 100,
        "price": 10.0,
        "stop_loss": 9.0,
        "take_profit": 12.0,
        "quant_score": 75.0,
        "factor_scores": {"momentum": 80, "volatility": 60},
        "regime": "SIDEWAYS",
        "reason": "Strong momentum",
    }
    social_signals = {
        "MEME": SocialSignal(ticker="MEME", ape_rank=5, st_bullish_pct=82.0,
                             heat="SPIKING")
    }
    portfolio_context = {"total_equity": 50000, "cash": 40000,
                         "num_positions": 2, "regime": "SIDEWAYS", "win_rate": 0.6}

    prompt = _build_review_prompt([action], portfolio_context,
                                  social_signals=social_signals)
    assert "SPIKING" in prompt
    assert "pump" in prompt.lower() or "retail" in prompt.lower()


def test_cold_heat_shows_cold_note():
    from ai_review import _build_review_prompt
    from social_sentiment import SocialSignal

    action = {
        "action_type": "BUY", "ticker": "QUIET", "shares": 50, "price": 20.0,
        "stop_loss": 18.0, "take_profit": 25.0, "quant_score": 70.0,
        "factor_scores": {}, "regime": "BULL", "reason": "Momentum",
    }
    social_signals = {
        "QUIET": SocialSignal(ticker="QUIET", heat="COLD")
    }
    prompt = _build_review_prompt([action], {"total_equity": 50000, "cash": 40000,
                                              "num_positions": 2, "regime": "BULL",
                                              "win_rate": 0.6},
                                  social_signals=social_signals)
    assert "COLD" in prompt or "independent" in prompt.lower()
