"""FastAPI app.  Run:  uvicorn app.main:app --reload   (from backend/)"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import transit, weather
from app.config import REPO_ROOT, get_settings

app = FastAPI(title="commuter-sim", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

api = FastAPI()  # mounted under /api so the frontend can be served from / later


@api.get("/health")
def health():
    s = get_settings()
    return {"status": "ok", "config": s.source_file.name, "routes": list(s.routes)}


@api.get("/routes")
def routes():
    s = get_settings()
    return [
        {"id": r.id, "name": r.name, "home": asdict(r.home), "work": asdict(r.work), "stops": list(r.stops),
         "period": {"start": r.period_start.isoformat(), "end": r.period_end.isoformat()},
         "commute_days": len(r.commute_days())}
        for r in s.routes.values()
    ]


api.include_router(weather.router)
api.include_router(transit.router)
app.mount("/api", api)

# Serve the built frontend (npm run build) if present - single process for "deploy later".
_dist = REPO_ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
