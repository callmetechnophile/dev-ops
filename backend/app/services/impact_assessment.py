"""Blast Radius and Impact Assessment Engine.

Evaluates potential operational impact separately from failure probability.
Traverses service dependency graphs to identify direct, downstream, and critical
tier-1 service exposures.
"""
from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Set, Optional
from collections import deque
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service, ServiceDependency
from app.models.deployment import Deployment

logger = logging.getLogger(__name__)


class ServiceNodeImpact(BaseModel):
    service_id: str
    name: str
    tier: str
    distance: int  # 0 for direct target, 1 for immediate dependent, 2+ for downstream
    criticality: str
    dependency_type: str = "direct"


class ImpactAssessment(BaseModel):
    target_service_id: Optional[str] = None
    target_service_name: Optional[str] = "Unknown"
    environment: str
    impact_category: str  # LOW, MEDIUM, HIGH, CRITICAL
    blast_radius_score: float  # 0.0 to 1.0
    direct_services_count: int
    downstream_services_count: int
    critical_tier1_exposed: bool
    affected_services: List[ServiceNodeImpact]
    graph_complete: bool = True
    assessment_notes: List[str] = []


class BlastRadiusImpactService:
    """Calculates downstream failure blast radius."""

    async def calculate_impact(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        target_service_id: Optional[uuid.UUID],
        environment: str = "production",
    ) -> ImpactAssessment:
        if not target_service_id:
            return ImpactAssessment(
                target_service_id=None,
                target_service_name="Unknown Component",
                environment=environment,
                impact_category="LOW",
                blast_radius_score=0.2,
                direct_services_count=1,
                downstream_services_count=0,
                critical_tier1_exposed=False,
                affected_services=[],
                graph_complete=False,
                assessment_notes=["Target service identifier not provided; cannot traverse dependency graph."],
            )

        # 1. Fetch target service
        svc_stmt = select(Service).where(and_(Service.id == target_service_id, Service.tenant_id == tenant_id))
        svc_res = await db.execute(svc_stmt)
        target_svc = svc_res.scalar_one_or_none()

        target_name = target_svc.name if target_svc else "service"
        target_tier = target_svc.tier if target_svc else "tier-2"

        # 2. Fetch all dependencies for tenant
        dep_stmt = select(ServiceDependency).where(ServiceDependency.tenant_id == tenant_id)
        dep_res = await db.execute(dep_stmt)
        all_deps = dep_res.scalars().all()

        # Build reverse adjacency list: target -> services that depend on target
        # If A depends on B (source=A, target=B), then if B fails, A is affected downstream.
        reverse_graph: Dict[uuid.UUID, List[ServiceDependency]] = {}
        for dep in all_deps:
            reverse_graph.setdefault(dep.target_service_id, []).append(dep)

        # 3. BFS Traversal to find all downstream affected services
        visited: Set[uuid.UUID] = {target_service_id}
        queue = deque([(target_service_id, 0, "direct")])  # (svc_id, distance, dep_type)

        affected: List[ServiceNodeImpact] = [
            ServiceNodeImpact(
                service_id=str(target_service_id),
                name=target_name,
                tier=target_tier,
                distance=0,
                criticality="critical" if target_tier == "tier-1" else "standard",
                dependency_type="direct_target",
            )
        ]

        critical_exposed = (target_tier == "tier-1")

        # Map for quick service name lookup
        all_svc_stmt = select(Service).where(Service.tenant_id == tenant_id)
        all_svc_res = await db.execute(all_svc_stmt)
        svc_lookup = {s.id: s for s in all_svc_res.scalars().all()}

        while queue:
            current_id, dist, dep_type = queue.popleft()

            for dep in reverse_graph.get(current_id, []):
                dep_svc_id = dep.source_service_id
                if dep_svc_id not in visited:
                    visited.add(dep_svc_id)
                    dep_svc = svc_lookup.get(dep_svc_id)
                    tier = dep_svc.tier if dep_svc else "tier-2"
                    name = dep_svc.name if dep_svc else f"service-{str(dep_svc_id)[:6]}"
                    if tier == "tier-1":
                        critical_exposed = True

                    affected.append(
                        ServiceNodeImpact(
                            service_id=str(dep_svc_id),
                            name=name,
                            tier=tier,
                            distance=dist + 1,
                            criticality="critical" if tier == "tier-1" else dep.criticality,
                            dependency_type=dep.dependency_type,
                        )
                    )
                    queue.append((dep_svc_id, dist + 1, dep.dependency_type))

        downstream_count = len(affected) - 1
        is_prod = str(environment).lower() in ("prod", "production")

        # Compute blast radius score (0.0 to 1.0)
        base_score = 0.20
        if is_prod:
            base_score += 0.20
        if critical_exposed:
            base_score += 0.35
        base_score += min(0.35, downstream_count * 0.10)

        blast_radius_score = round(min(1.0, base_score), 2)

        # Categorize impact
        if blast_radius_score >= 0.75:
            impact_cat = "CRITICAL"
        elif blast_radius_score >= 0.50:
            impact_cat = "HIGH"
        elif blast_radius_score >= 0.30:
            impact_cat = "MEDIUM"
        else:
            impact_cat = "LOW"

        notes: List[str] = []
        if critical_exposed:
            notes.append("Exposure reaches Tier-1 critical infrastructure services.")
        if downstream_count > 0:
            notes.append(f"Propagation path touches {downstream_count} downstream dependent service(s).")
        else:
            notes.append("Isolated component with zero registered downstream consumers.")

        return ImpactAssessment(
            target_service_id=str(target_service_id),
            target_service_name=target_name,
            environment=environment,
            impact_category=impact_cat,
            blast_radius_score=blast_radius_score,
            direct_services_count=1,
            downstream_services_count=downstream_count,
            critical_tier1_exposed=critical_exposed,
            affected_services=affected,
            graph_complete=True,
            assessment_notes=notes,
        )


blast_radius_service = BlastRadiusImpactService()
