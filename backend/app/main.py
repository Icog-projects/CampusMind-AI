"""CampusMind AI - FastAPI Application Entry Point.

Exposes core endpoints for authentication, document management, chat, and telemetry.

Responsibilities:
1. lifespan(): Manages database table initialization and startup/shutdown lifecycle.
2. root(): Serves the root health and service information response.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db, get_engine
from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("campusmind")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes database tables on application startup."""
    logger.info("Starting CampusMind AI API backend...")
    try:
        init_db(get_engine())
        logger.info("Database schemas confirmed.")
    except Exception as e:
        logger.warning("Could not auto-initialize database on startup: %s", e)
    yield
    logger.info("Shutting down CampusMind AI API backend.")


app = FastAPI(
    title="CampusMind AI API",
    description="University Knowledge Assistant using RAG, Hybrid Search, and Redis Answer Caching (SRS v1.3)",
    version="1.3.0",
    lifespan=lifespan,
)

# Enable CORS for local client testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)


@app.get("/", tags=["Root"])
def root():
    return {
        "service": "CampusMind AI",
        "version": "1.3.0",
        "status": "operational",
        "docs_url": "/docs",
    }

