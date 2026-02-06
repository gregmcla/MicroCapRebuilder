"""FastAPI app — thin REST layer over existing Python trading modules."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure scripts/ is on sys.path before route imports
import api.deps  # noqa: F401

from api.routes import state, risk, performance, analysis, chat, market

app = FastAPI(title="Mommy Trading Cockpit", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(state.router)
app.include_router(risk.router)
app.include_router(performance.router)
app.include_router(analysis.router)
app.include_router(chat.router)
app.include_router(market.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
