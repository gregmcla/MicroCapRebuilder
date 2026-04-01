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

from api.routes import state, risk, performance, analysis, market, controls, discovery, portfolios
from api.routes import system as system_routes
from api.routes import intelligence as intelligence_routes

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
app.include_router(system_routes.router)
app.include_router(intelligence_routes.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
