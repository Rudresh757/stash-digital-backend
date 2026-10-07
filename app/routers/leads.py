import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Lead
from app.schemas import LeadCreate, LeadCreated
from app.security import rate_limit

logger = logging.getLogger("stash.leads")
router = APIRouter(prefix="/api", tags=["leads"])


@router.post(
    "/leads",
    response_model=LeadCreated,
    status_code=201,
    dependencies=[Depends(rate_limit(5, 60))],
)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)) -> LeadCreated:
    if payload.website:  # honeypot filled: bot
        raise HTTPException(status_code=400, detail="Invalid submission.")

    lead = Lead(
        name=payload.name,
        email=str(payload.email).lower(),
        phone=payload.phone,
        business_name=payload.business_name,
        industry=payload.industry,
        country=payload.country,
        consent=payload.consent,
        source=payload.source,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        status="new",
    )

    try:
        db.add(lead)
        db.commit()
        db.refresh(lead)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not save lead")
        raise HTTPException(
            status_code=503,
            detail="We couldn't save your details right now. Please try again in a moment.",
        )

    return LeadCreated(id=lead.id, message="Got it. Now pick a time that suits you.")