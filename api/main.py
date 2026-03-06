"""
FastAPI application entry point for CHM GOLD EXCHANGE.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import router
from database.engine import DATABASE_URL, create_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CHM GOLD EXCHANGE API")
    # Auto-create tables for SQLite dev environment
    if "sqlite" in DATABASE_URL:
        await create_tables()
        logger.info("SQLite tables created/verified")
    yield
    logger.info("Shutting down CHM GOLD EXCHANGE API")


app = FastAPI(
    title="CHM GOLD EXCHANGE API",
    description="Crypto and fiat currency exchange service",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Telegram WebApp and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
