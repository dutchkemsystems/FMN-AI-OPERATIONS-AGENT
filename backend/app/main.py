"""FastAPI application entry point."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .models.database import init_db

logger = logging.getLogger("fmn")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    settings = get_settings()
    logger.info("Starting FMN-AI Operations Agent (%s)", settings.environment)

    try:
        init_db(seed_admin=True)
        logger.info("Database initialised")
    except Exception:
        logger.exception("Database initialisation failed — continuing without DB")

    yield

    logger.info("Shutting down FMN-AI Operations Agent")


app = FastAPI(
    title="FMN-AI Operations Agent",
    description="AI-powered multi-agent operations platform for Flour Mills of Nigeria",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
from .middleware.rate_limit import RateLimitMiddleware

app.add_middleware(RateLimitMiddleware, default_limit=settings.rate_limit_per_minute)

# Request metrics
from .middleware.metrics import MetricsMiddleware, get_metrics

app.add_middleware(MetricsMiddleware)

# Gzip compression
from starlette.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=500)

from .api.routes import router  # noqa: E402

app.include_router(router)


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "api": "/api",
    }


@app.get("/metrics")
def metrics():
    return get_metrics()
