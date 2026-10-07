"""Application settings, loaded from environment variables (backend/.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _normalize_db_url(url: str) -> str:
    """Force the psycopg v3 driver and make sure SSL is required (Neon needs it)."""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    frontend_origins: list[str]
    admin_token: str
    calendly_signing_key: str

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    raw_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy backend/.env.example to backend/.env "
            "and paste your Neon pooled connection string."
        )

    origins = [
        o.strip().rstrip("/")
        for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",")
        if o.strip()
    ]

    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        database_url=_normalize_db_url(raw_url),
        frontend_origins=origins,
        admin_token=os.getenv("ADMIN_TOKEN", "").strip(),
        calendly_signing_key=os.getenv("CALENDLY_WEBHOOK_SIGNING_KEY", "").strip(),
    )