from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Lead
from app.schemas import LeadPage, LeadStatus
from app.security import rate_limit, require_admin

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(rate_limit(30, 60)), Depends(require_admin)],
)


@router.get("/leads", response_model=LeadPage)
def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status: LeadStatus | None = None,
    db: Session = Depends(get_db),
) -> LeadPage:
    stmt = select(Lead)
    count_stmt = select(func.count()).select_from(Lead)
    if status:
        stmt = stmt.where(Lead.status == status)
        count_stmt = count_stmt.where(Lead.status == status)

    total = db.scalar(count_stmt) or 0
    items = db.scalars(
        stmt.order_by(Lead.created_at.desc(), Lead.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return LeadPage(items=items, total=total, page=page, page_size=page_size)