import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.intelligence import Recommendation
from app.schemas.risk import RecommendationRead
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("", response_model=PaginatedResponse[RecommendationRead])
async def list_recommendations(
    deployment_id: Optional[str] = None,
    recommendation_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Recommendation)
    if deployment_id:
        stmt = stmt.where(Recommendation.deployment_id == uuid.UUID(deployment_id))
    if recommendation_type:
        stmt = stmt.where(Recommendation.recommendation_type == recommendation_type)

    stmt = stmt.order_by(Recommendation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    records = result.scalars().all()

    items = [
        RecommendationRead(
            id=str(r.id),
            risk_assessment_id=str(r.risk_assessment_id),
            deployment_id=str(r.deployment_id),
            recommendation_type=r.recommendation_type,
            title=r.title,
            rationale=r.rationale,
            mitigation_steps=r.mitigation_steps or [],
            confidence_score=r.confidence_score,
            requires_approval=r.requires_approval,
        )
        for r in records
    ]

    return PaginatedResponse(
        items=items, total=len(items), page=page, page_size=page_size, has_more=len(items) == page_size
    )
