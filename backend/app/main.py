"""Kabadiwala Connect — FastAPI application entrypoint.

SIH26229 · Ministry of Mines / JNARDDC
Bringing the informal collector into the formal EPR recycling chain.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("kabadiwala")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the ML classifier lazily/off-thread so /docs opens instantly.
    import threading

    def _warm():
        try:
            from app.ml.classifier import MaterialClassifier

            clf = MaterialClassifier.instance()
            logger.info("Material classifier ready: %s (available=%s)", clf.model_name, clf.available)
        except Exception as exc:  # pragma: no cover
            logger.warning("Classifier warm-up failed: %s", exc)

    threading.Thread(target=_warm, daemon=True).start()
    logger.info("Kabadiwala Connect API starting (env=%s)", settings.env)
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Backend for **Kabadiwala Connect** (SIH26229). Composition-aware "
        "valuation, declared-vs-verified trust layer, offline-tolerant collector "
        "PWA, recycler console and Ministry analytics.\n\n"
        "All critical-mineral figures are *estimates* from published "
        "stoichiometric composition ratios — not laboratory assays."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://.*\.prod-runtime\.all-hands\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Never leak internals to clients; log server-side instead."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/", tags=["meta"])
def root():
    return {
        "name": "Kabadiwala Connect API",
        "problem_statement": "SIH26229",
        "organization": "Ministry of Mines / JNARDDC",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/health", tags=["meta"])
def health():
    from sqlalchemy import text

    from app.core.db import engine

    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        logger.warning("DB health check failed: %s", exc)
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "env": settings.env}
