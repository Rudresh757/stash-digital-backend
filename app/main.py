import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine, get_db, init_db
from app.routers import admin, leads, webhooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("stash")

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Neon may be waking from idle: retry table creation a few times.
    for attempt in range(1, 4):
        try:
            await asyncio.to_thread(init_db)
            break
        except Exception:
            logger.exception("Database init failed (attempt %s/3)", attempt)
            if attempt == 3:
                raise
            await asyncio.sleep(2 * attempt)
    yield
    engine.dispose()


app = FastAPI(
    title="Stash Digital Media API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Token"],
    max_age=600,
)

app.include_router(leads.router)
app.include_router(webhooks.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["health"])
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health check failed")
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return {"status": "ok"}
