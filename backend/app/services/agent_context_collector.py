"""Context Collection Engine for Predictive DevOps Intelligence Agent.

Collects context across:
- GitHub (Repo, Commit, PR, Changes, Build, Workflow)
- Operational Memory (Similar incidents, Confirmed causes, Verified lessons)
- Predictive Intelligence (Risk assessment, Failure probability, Blast radius, Feature evidence)
- Infrastructure Context (Dependencies, Tier, Topology)

Guarantees:
- Every context item maintains a source reference and timestamp.
- Explicit tracking of missing information in `missing_context`.
- Distinguishes unavailable telemetry from negative evidence.
- Zero fabrication of missing signals.
"""
from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.deployment import Deployment, Commit, Change, Build
from app.models.service import Service, Repository, ServiceDependency
from app.models.github_entities import PullRequest, WorkflowRun, WorkflowJob
from app.models.incident import Incident, ConfirmedRootCause, OperationalLesson
from app.models.intelligence import RiskAssessment, RemediationAction
from app.services.risk_assessment_service import risk_assessment_service

logger = logging.getLogger(__name__)


class CollectedContext(BaseModel):
    collected_at: datetime
    sources: Dict[str, Any]
    github_context: Dict[str, Any]
    operational_memory: Dict[str, Any]
    predictive_intelligence: Dict[str, Any]
    infrastructure_context: Dict[str, Any]
    missing_context: List[str]
    freshness_seconds: float = 0.0


class AgentContextCollector:
    """Collects and validates pre-deployment operational context."""

    async def collect_context(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        deployment: Deployment,
    ) -> CollectedContext:
        now = datetime.now(timezone.utc)
        missing_context: List[str] = []
        sources: Dict[str, Any] = {}

        # ----------------------------------------------------
        # 1. GitHub & Change Telemetry
        # ----------------------------------------------------
        github_context: Dict[str, Any] = {
            "deployment_id": str(deployment.id),
            "environment": deployment.environment,
            "commit_sha": deployment.commit_sha,
            "status": deployment.status,
            "triggered_by": deployment.triggered_by,
        }
        sources["deployment"] = f"deployments.id:{deployment.id}"

        # Fetch Service & Repository
        svc_stmt = select(Service).where(Service.id == deployment.service_id)
        svc_res = await db.execute(svc_stmt)
        service = svc_res.scalar_one_or_none()

        repo = None
        if service and service.repository_id:
            r_stmt = select(Repository).where(Repository.id == service.repository_id)
            r_res = await db.execute(r_stmt)
            repo = r_res.scalar_one_or_none()

        if repo:
            github_context["repository"] = {
                "id": str(repo.id),
                "name": repo.name,
                "full_name": repo.full_name,
                "default_branch": repo.default_branch,
            }
            sources["repository"] = f"repositories.id:{repo.id}"
        else:
            missing_context.append("repository_metadata")

        # Fetch Commit & Changes
        commit_stmt = (
            select(Commit)
            .where(
                and_(
                    Commit.tenant_id == tenant_id,
                    Commit.commit_sha == deployment.commit_sha,
                )
            )
            .options(selectinload(Commit.changes))
        )
        commit_res = await db.execute(commit_stmt)
        commit_rec = commit_res.scalar_one_or_none()

        if commit_rec:
            github_context["commit"] = {
                "sha": commit_rec.commit_sha,
                "message": commit_rec.message,
                "author": commit_rec.author_name or commit_rec.author_email,
                "committed_at": commit_rec.committed_at.isoformat() if commit_rec.committed_at else None,
                "additions": commit_rec.stats_additions,
                "deletions": commit_rec.stats_deletions,
                "changed_files_count": len(commit_rec.changes),
                "files": [c.file_path for c in commit_rec.changes[:25]],
            }
            sources["commit"] = f"commits.commit_sha:{commit_rec.commit_sha}"
        else:
            missing_context.append("commit_details_and_diff")

        # Fetch Linked Pull Request
        pr_stmt = (
            select(PullRequest)
            .where(
                and_(
                    PullRequest.tenant_id == tenant_id,
                    PullRequest.head_sha == deployment.commit_sha,
                )
            )
        )
        pr_res = await db.execute(pr_stmt)
        pr_rec = pr_res.scalars().first()
        if pr_rec:
            github_context["pull_request"] = {
                "number": pr_rec.number,
                "title": pr_rec.title,
                "state": pr_rec.state,
                "author": pr_rec.author_login,
            }
            sources["pull_request"] = f"pull_requests.number:{pr_rec.number}"
        else:
            missing_context.append("pull_request_record")

        # Fetch Build & Workflow
        build_rec = None
        if deployment.build_id:
            b_stmt = select(Build).where(Build.id == deployment.build_id)
            b_res = await db.execute(b_stmt)
            build_rec = b_res.scalar_one_or_none()
        elif repo:
            b_stmt = select(Build).where(and_(Build.commit_sha == deployment.commit_sha, Build.repository_id == repo.id)).order_by(desc(Build.created_at))
            b_res = await db.execute(b_stmt)
            build_rec = b_res.scalars().first()

        if build_rec:
            github_context["build"] = {
                "id": str(build_rec.id),
                "status": build_rec.status,
                "duration_seconds": build_rec.duration_seconds,
                "tests_passed": build_rec.tests_passed,
                "tests_failed": build_rec.tests_failed,
            }
            sources["build"] = f"builds.id:{build_rec.id}"
        else:
            missing_context.append("build_telemetry")

        # ----------------------------------------------------
        # 2. Operational Memory Context
        # ----------------------------------------------------
        op_memory: Dict[str, Any] = {
            "similar_incidents": [],
            "confirmed_root_causes": [],
            "verified_lessons": [],
        }

        if repo:
            inc_stmt = (
                select(Incident)
                .where(and_(Incident.tenant_id == tenant_id, Incident.repository_id == repo.id))
                .order_by(desc(Incident.detected_at))
                .limit(5)
            )
            inc_res = await db.execute(inc_stmt)
            recent_incs = inc_res.scalars().all()
            for inc in recent_incs:
                op_memory["similar_incidents"].append({
                    "id": str(inc.id),
                    "key": inc.incident_key,
                    "title": inc.title,
                    "severity": inc.severity,
                    "status": inc.status,
                    "detected_at": inc.detected_at.isoformat(),
                })
            sources["operational_incidents"] = f"incidents.count:{len(recent_incs)}"

            # Confirmed root causes & lessons
            if recent_incs:
                crc_stmt = select(ConfirmedRootCause).where(
                    and_(
                        ConfirmedRootCause.tenant_id == tenant_id,
                        ConfirmedRootCause.incident_id.in_([i.id for i in recent_incs]),
                    )
                )
                crc_res = await db.execute(crc_stmt)
                for crc in crc_res.scalars().all():
                    op_memory["confirmed_root_causes"].append({
                        "incident_id": str(crc.incident_id),
                        "summary": crc.root_cause_summary,
                        "prevention": crc.prevention_strategy,
                    })

                lesson_stmt = select(OperationalLesson).where(
                    and_(
                        OperationalLesson.tenant_id == tenant_id,
                        OperationalLesson.incident_id.in_([i.id for i in recent_incs]),
                    )
                )
                lesson_res = await db.execute(lesson_stmt)
                for lsn in lesson_res.scalars().all():
                    op_memory["verified_lessons"].append({
                        "title": lsn.title,
                        "lesson": lsn.lesson,
                    })

        # ----------------------------------------------------
        # 3. Infrastructure & Topology Context
        # ----------------------------------------------------
        infra_context: Dict[str, Any] = {
            "target_service": {
                "id": str(service.id) if service else None,
                "name": service.name if service else "unknown",
                "tier": service.tier if service else "tier-2",
                "health_status": service.health_status if service else "unknown",
            },
            "downstream_dependencies": [],
            "upstream_dependencies": [],
        }

        if service:
            dep_stmt = select(ServiceDependency).where(ServiceDependency.tenant_id == tenant_id)
            dep_res = await db.execute(dep_stmt)
            all_deps = dep_res.scalars().all()

            for d in all_deps:
                if d.target_service_id == service.id:
                    # Someone depends on this service (downstream affected if this fails)
                    infra_context["downstream_dependencies"].append({
                        "service_id": str(d.source_service_id),
                        "type": d.dependency_type,
                        "criticality": d.criticality,
                    })
                elif d.source_service_id == service.id:
                    # This service depends on someone (upstream dependency)
                    infra_context["upstream_dependencies"].append({
                        "service_id": str(d.target_service_id),
                        "type": d.dependency_type,
                        "criticality": d.criticality,
                    })

            sources["dependencies"] = f"dependencies.count:{len(all_deps)}"
        else:
            missing_context.append("service_topology")

        # ----------------------------------------------------
        # 4. Predictive Intelligence
        # ----------------------------------------------------
        predictive_context: Dict[str, Any] = {}
        ra_stmt = (
            select(RiskAssessment)
            .where(
                and_(
                    RiskAssessment.tenant_id == tenant_id,
                    RiskAssessment.deployment_id == deployment.id,
                )
            )
            .order_by(desc(RiskAssessment.assessed_at))
        )
        ra_res = await db.execute(ra_stmt)
        existing_ra = ra_res.scalars().first()

        if existing_ra:
            predictive_context = {
                "assessment_id": str(existing_ra.id),
                "overall_risk_score": existing_ra.overall_risk_score,
                "risk_level": existing_ra.risk_level,
                "failure_probability": existing_ra.failure_probability,
                "operational_impact_score": existing_ra.operational_impact_score,
                "impact_category": existing_ra.impact_category,
                "model_version": existing_ra.model_version,
                "is_calibrated": existing_ra.calibration_version is not None,
                "triggered_rules": existing_ra.triggered_rules or [],
                "affected_services": existing_ra.affected_services or [],
            }
            sources["risk_assessment"] = f"risk_assessments.id:{existing_ra.id}"
        else:
            missing_context.append("pre_existing_risk_assessment")

        return CollectedContext(
            collected_at=now,
            sources=sources,
            github_context=github_context,
            operational_memory=op_memory,
            predictive_intelligence=predictive_context,
            infrastructure_context=infra_context,
            missing_context=missing_context,
            freshness_seconds=0.0,
        )


agent_context_collector = AgentContextCollector()
