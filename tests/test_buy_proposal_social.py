import sys
sys.path.insert(0, "scripts")
from enhanced_structures import BuyProposal
from social_sentiment import SocialSignal


def test_buy_proposal_has_social_field():
    from enhanced_structures import ConvictionScore, ConvictionLevel
    cs = ConvictionScore(ticker="AAPL", composite_score=75, final_conviction=75,
                         conviction_level=ConvictionLevel.GOOD,
                         conviction_multiplier=1.0,
                         patterns_detected=[], atr_pct=2.0, factors={})
    bp = BuyProposal(ticker="AAPL", shares=100, price=150.0, total_value=15000.0,
                     conviction_score=cs, position_size_pct=5.0, rationale="test")
    assert hasattr(bp, "social_signal")
    assert bp.social_signal is None


def test_social_signal_attached_to_proposal():
    from enhanced_structures import ConvictionScore, ConvictionLevel
    sig = SocialSignal(ticker="AAPL", ape_rank=15, st_bullish_pct=80.0, heat="SPIKING")
    cs = ConvictionScore(ticker="AAPL", composite_score=75, final_conviction=75,
                         conviction_level=ConvictionLevel.GOOD,
                         conviction_multiplier=1.0,
                         patterns_detected=[], atr_pct=2.0, factors={})
    bp = BuyProposal(ticker="AAPL", shares=100, price=150.0, total_value=15000.0,
                     conviction_score=cs, position_size_pct=5.0, rationale="test",
                     social_signal=sig)
    assert bp.social_signal is not None
    assert bp.social_signal.heat == "SPIKING"
