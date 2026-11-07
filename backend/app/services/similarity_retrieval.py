"""Historical Incident Similarity Retrieval Service.

Retrieves historically similar incidents, matching failure classifications, confirmed root causes,
and remediation outcomes. Enforces tenant boundaries strictly.
"""
from __future__ import annotations
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.incident import (
    Incident,
    FailureClassification,
    ConfirmedRootCause,
    RootCauseHypothesis,
)
from app.models.intelligence import RemediationAction

logger = logging.getLogger(__name__)


class SimilarIncidentMatch(BaseModel):
    incident_id: str
    incident_key: str
    title: str
    similarity_score: float
    matching_categories: List[str]
    environment: str
    status: str
    confirmed_root_cause_summary: Optional[str] = None
    verified_engineering_lesson: Optional[str] = None
    prevention_strategy: Optional[str] = None
    historical_remediations: List[Dict[str, Any]] = []
    evidence_snippet: Optional[str] = None
    detected_at: datetime


class SimilarityRetrievalService:
    """Retrieves similar historical incidents based on structured signals and operational context."""

    async def find_similar_incidents(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        incident_id: uuid.UUID,
        limit: int = 5,
    ) -> List[SimilarIncidentMatch]:
        # 1. Fetch target incident
        target_stmt = (
            select(Incident)
            .where(and_(Incident.id == incident_id, Incident.tenant_id == tenant_id))
            .options(
                selectinload(Incident.classifications),
            )
        )
        t_res = await db.execute(target_stmt)
        target = t_res.scalar_one_or_none()
        if not target:
            return []

        target_categories = {c.category for c in target.classifications}
        target_subcategories = {c.subcategory for c in target.classifications}

        # 2. Query historical incidents in the same tenant excluding the target itself
        stmt = (
            select(Incident)
            .where(
                and_(
                    Incident.tenant_id == tenant_id,
                    Incident.id != incident_id,
                )
            )
            .options(
                selectinload(Incident.classifications),
                selectinload(Incident.confirmed_root_cause),
                selectinload(Incident.remediations),
            )
            .order_by(desc(Incident.detected_at))
            .limit(50)
        )
        candidates_res = await db.execute(stmt)
        candidates = candidates_res.scalars().all()

        matches: List[SimilarIncidentMatch] = []

        for cand in candidates:
            cand_cats = {c.category for c in cand.classifications}
            cand_subs = {c.subcategory for c in cand.classifications}

            # Score matching attributes
            score = 0.0

            # 1. Category overlap (weight: 0.40)
            common_cats = target_categories.intersection(cand_cats)
            if common_cats:
                score += 0.40
            elif target.incident_type == cand.incident_type:
                score += 0.30

            # 2. Subcategory overlap (weight: 0.30)
            common_subs = target_subcategories.intersection(cand_subs)
            if common_subs:
                score += 0.30

            # 3. Same repository (weight: 0.15)
            if target.repository_id and cand.repository_id and target.repository_id == cand.repository_id:
                score += 0.15

            # 4. Same environment (weight: 0.15)
            if target.environment == cand.environment:
                score += 0.15

            if score >= 0.30:
                crc = cand.confirmed_root_cause
                remediations = [
                    {
                        "action_type": r.action_type,
                        "description": r.description,
                        "outcome": r.outcome,
                        "effectiveness": r.effectiveness,
                    }
                    for r in cand.remediations
                ]

                matches.append(
                    SimilarIncidentMatch(
                        incident_id=str(cand.id),
                        incident_key=cand.incident_key,
                        title=cand.title,
                        similarity_score=round(min(1.0, score), 2),
                        matching_categories=list(common_cats or [cand.incident_type]),
                        environment=cand.environment,
                        status=cand.status,
                        confirmed_root_cause_summary=crc.root_cause_summary if crc else None,
                        verified_engineering_lesson=crc.verified_engineering_lesson if crc else None,
                        prevention_strategy=crc.prevention_strategy if crc else None,
                        historical_remediations=remediations,
                        evidence_snippet=cand.summary[:200],
                        detected_at=cand.detected_at,
                    )
                )

        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches[:limit]


similarity_retrieval_service = SimilarityRetrievalService()
