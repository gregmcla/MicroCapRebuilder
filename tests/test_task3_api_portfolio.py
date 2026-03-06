import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.routes.portfolios import CreatePortfolioRequest
import inspect


def test_create_portfolio_request_has_sector_weights():
    fields = CreatePortfolioRequest.model_fields
    assert "sector_weights" in fields


def test_create_portfolio_request_sector_weights_optional():
    req = CreatePortfolioRequest(
        id="test", name="Test", universe="largecap", starting_capital=10000
    )
    assert req.sector_weights is None
