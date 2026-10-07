import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from app.db import SessionLocal
from app.models import Lead
from app.security import rate_limit, verify_calendly_signature

logger = logging.getLogger("stash.webhooks")
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

MAX_BODY_BYTES = 100_000
EVENTS = {"invitee.created", "invitee.canceled"}


def _apply(event: str, email: str) -> bool:
    with SessionLocal() as db:
        lead = db.scalars(
            select(Lead)
            .where(func.lower(Lead.email) == email)
            .order_by(Lead.created_at.desc(), Lead.id.desc())
            .limit(1)
        ).first()
        if lead is None:
            return False

        if event == "invitee.created":
            lead.status = "booked"
        elif lead.status == "booked":  # canceled: only roll back a booking, never a "contacted" lead
            lead.status = "new"

        db.commit()
        return True


@router.post("/calendly", dependencies=[Depends(rate_limit(60, 60))])
async def calendly_webhook(request: Request) -> dict:
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large.")

    verify_calendly_signature(raw, request.headers.get("Calendly-Webhook-Signature"))

    try:
        data = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON.")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid payload.")

    event = data.get("event")
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    email = str(payload.get("email") or "").strip().lower()

    if event not in EVENTS or not email:
        return {"ok": True, "matched": False}

    matched = await run_in_threadpool(_apply, event, email)
    logger.info("Calendly %s for %s matched=%s", event, email, matched)
    return {"ok": True, "matched": matched}