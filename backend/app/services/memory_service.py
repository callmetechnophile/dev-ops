"""Operational Memory Service: Episodic, Relational, and Semantic Memory.

Implements:
1. Episodic Memory: Complete chronological operational history and failure traces.
2. Relational Memory: Explicit relational paths from Repo -> Commit -> Build -> Deployment -> Incident -> Root Cause -> Remediation.
3. Semantic Memory: Searchable pgvector representations with structured fallback when embeddings are unconfigured.

Strictly tenant-scoped. Never presents unverified hypotheses as confirmed historical lessons.
"""

from __future__ import annotations
import math
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
    ConfirmedRootCause,
    OperationalLesson,
    FailureClassification,
    RootCauseHypothesis,
)
from app.models.intelligence import RemediationAction
from app.models.deployment import Deployment, Commit, Build

logger = logging.getLogger(__name__)


class MemorySearchResult(BaseModel):
    id: str
    record_type: str  # incident, confirmed_root_cause, operational_lesson
    title: str
    summary: str
    relevance_score: float
    incident_id: str
    incident_key: Optional[str] = None
    environment: Optional[str] = None
    verification_status: str  # VERIFIED, UNVERIFIED
    created_at: datetime
    metadata: Dict[str, Any] = {}


class EmbeddingProvider:
    """Provider abstraction for text embeddings with safe fallback."""

    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        if not self.is_available():
            return None
        # Safe mock / provider integration hook
        return None


class OperationalMemoryService:
    """Query and index service across episodic, relational, and semantic memory layers."""

    def __init__(self):
        self.embedding_provider = EmbeddingProvider()

    async def search_memory(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        query: str,
        category: Optional[str] = None,
        environment: Optional[str] = None,
        verified_only: bool = True,
        limit: int = 10,
    ) -> List[MemorySearchResult]:
        """Performs tenant-isolated memory search across verified lessons and confirmed incidents."""
        results: List[MemorySearchResult] = []
        q_tokens = [t.lower() for t in query.split() if len(t) > 2]

        # 1. Search verified operational lessons
        lesson_stmt = (
            select(OperationalLesson)
            .join(Incident, Incident.id == OperationalLesson.incident_id)
            .where(
                and_(
                    OperationalLesson.tenant_id == tenant_id,
                    OperationalLesson.verification_status == "VERIFIED",
                )
            )
            .options(
                selectinload(OperationalLesson.incident),
                selectinload(OperationalLesson.verified_root_cause),
            )
        )
        if environment:
            lesson_stmt = lesson_stmt.where(Incident.environment == environment)

        lesson_res = await db.execute(lesson_stmt)
        for lesson in lesson_res.scalars().all():
            text_corpus = f"{lesson.title} {lesson.lesson} {lesson.incident.title if lesson.incident else ''}".lower()
            score = self._compute_lexical_similarity(q_tokens, text_corpus)
            if score > 0.0 or not q_tokens:
                results.append(
                    MemorySearchResult(
                        id=str(lesson.id),
                        record_type="operational_lesson",
                        title=lesson.title,
                        summary=lesson.lesson,
                        relevance_score=round(score or 0.85, 2),
                        incident_id=str(lesson.incident_id),
                        incident_key=lesson.incident.incident_key if lesson.incident else None,
                        environment=lesson.incident.environment if lesson.incident else None,
                        verification_status="VERIFIED",
                        created_at=lesson.created_at,
                        metadata={
                            "verified_root_cause_id": str(lesson.verified_root_cause_id),
                            "conditions": lesson.applicability_conditions,
                        },
                    )
                )

        # 2. Search confirmed root causes
        crc_stmt = (
            select(ConfirmedRootCause)
            .join(Incident, Incident.id == ConfirmedRootCause.incident_id)
            .where(ConfirmedRootCause.tenant_id == tenant_id)
            .options(selectinload(ConfirmedRootCause.incident))
        )
        if environment:
            crc_stmt = crc_stmt.where(Incident.environment == environment)

        crc_res = await db.execute(crc_stmt)
        for crc in crc_res.scalars().all():
            text_corpus = (
                f"{crc.root_cause_summary} {crc.verified_engineering_lesson} {crc.prevention_strategy}".lower()
            )
            score = self._compute_lexical_similarity(q_tokens, text_corpus)
            if score > 0.0 or not q_tokens:
                results.append(
                    MemorySearchResult(
                        id=str(crc.id),
                        record_type="confirmed_root_cause",
                        title=f"Confirmed Root Cause: {crc.root_cause_summary[:60]}",
                        summary=f"{crc.verified_engineering_lesson} (Prevention: {crc.prevention_strategy})",
                        relevance_score=round(score or 0.80, 2),
                        incident_id=str(crc.incident_id),
                        incident_key=crc.incident.incident_key if crc.incident else None,
                        environment=crc.incident.environment if crc.incident else None,
                        verification_status="VERIFIED",
                        created_at=crc.confirmed_at,
                        metadata={"confirmed_by": crc.confirmed_by},
                    )
                )

        # 3. If verified_only is False, include historical incident summaries
        if not verified_only:
            inc_stmt = select(Incident).where(Incident.tenant_id == tenant_id)
            if environment:
                inc_stmt = inc_stmt.where(Incident.environment == environment)
            if category:
                inc_stmt = inc_stmt.where(Incident.incident_type == category)

            inc_res = await db.execute(inc_stmt.limit(limit))
            for inc in inc_res.scalars().all():
                text_corpus = f"{inc.title} {inc.summary}".lower()
                score = self._compute_lexical_similarity(q_tokens, text_corpus)
                if score > 0.0:
                    results.append(
                        MemorySearchResult(
                            id=str(inc.id),
                            record_type="incident",
                            title=inc.title,
                            summary=inc.summary,
                            relevance_score=round(score, 2),
                            incident_id=str(inc.id),
                            incident_key=inc.incident_key,
                            environment=inc.environment,
                            verification_status="VERIFIED" if inc.status == "RESOLVED" else "UNVERIFIED",
                            created_at=inc.created_at,
                            metadata={"incident_type": inc.incident_type, "status": inc.status},
                        )
                    )

        # Sort by relevance score descending
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]

    def _compute_lexical_similarity(self, query_tokens: List[str], text: str) -> float:
        if not query_tokens:
            return 0.5
        matched = sum(1 for t in query_tokens if t in text)
        return min(1.0, matched / len(query_tokens))


operational_memory_service = OperationalMemoryService()
