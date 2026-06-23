"""FastAPI app — thin REST layer over existing Python trading modules."""

import resource

# Raise file descriptor limit — scans open many yfinance/cache files simultaneously
try:
    _soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (min(4096, _hard), _hard))
except Exception:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure scripts/ is on sys.path before route imports
import api.deps  # noqa: F401

# Configure structured logging once at startup so every cache hit / warn /
# error from `scripts/` and `api/` lands in /tmp/uvicorn.log with consistent
# formatting (Fix 15). Reads LOG_LEVEL env var; default INFO.
from logging_setup import configure_logging  # noqa: E402

configure_logging()

from api.routes import state, risk, performance, analysis, market, controls, discovery, portfolios
from api.routes import system as system_routes
from api.routes import intelligence as intelligence_routes
from api.routes import trade_reviews as trade_reviews_routes
from api.routes import cache as cache_routes
from api.routes import digest as digest_routes
from api.routes import decisions as decisions_routes
from api.routes import lineage as lineage_routes
from api.routes import dna as dna_routes

app = FastAPI(title="GScott Trading Cockpit", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Portfolio management routes MUST come before portfolio-scoped routes
# (otherwise /api/portfolios matches /api/{portfolio_id})
app.include_router(portfolios.router)
app.include_router(state.router)
app.include_router(risk.router)
app.include_router(performance.router)
app.include_router(analysis.router)
app.include_router(market.router)
app.include_router(controls.router)
app.include_router(discovery.router)
app.include_router(discovery.global_router)
app.include_router(system_routes.router)
app.include_router(intelligence_routes.router)
app.include_router(trade_reviews_routes.router)
app.include_router(cache_routes.router)
app.include_router(digest_routes.router)
app.include_router(decisions_routes.router)
app.include_router(lineage_routes.router)
app.include_router(dna_routes.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
