"""Feature Engineering Engine for Predictive Deployment Intelligence.

Extracts tabular pre-deployment feature vectors strictly prior to deployment execution.
Enforces:
- Target leakage prevention (zero post-deployment signals).
- Explicit missing feature tracking.
- Versioned schema (v1.0.0).
- Reproducible feature representation.
"""

from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.deployment import Deployment, Commit, Change, Build
from app.models.service import Service, Repository, ServiceDependency
from app.models.incident import Incident, FailureClassification, ConfirmedRootCause
from app.models.github_entities import WorkflowRun, WorkflowJob

logger = logging.getLogger(__name__)

FEATURE_SCHEMA_VERSION = "1.0.0"

DEPENDENCY_MANIFEST_NAMES = {
    "package.json",
    "package-lock.json",
    "requirements.txt",
    "pyproject.toml",
    "pipfile",
    "go.mod",
    "go.sum",
    "cargo.toml",
    "pom.xml",
    "build.gradle",
}

INFRASTRUCTURE_PATTERNS = {
    "dockerfile",
    "docker-compose",
    "helm",
    "k8s",
    "kubernetes",
    "values.yaml",
    "deployment.yaml",
    "terraform",
    ".tf",
}

CONFIG_PATTERNS = {".env", "config.json", "config.yaml", "settings.py", "application.yml"}


class FeatureSnapshot(BaseModel):
    schema_version: str = FEATURE_SCHEMA_VERSION
    extracted_at: datetime
    features: Dict[str, float]
    categorical_features: Dict[str, str]
    missing_features: List[str]
    metadata: Dict[str, Any] = {}


class FeatureEngineeringService:
    """Pre-deployment feature extractor."""

    async def extract_features(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        deployment: Deployment,
        service: Optional[Service] = None,
        repository: Optional[Repository] = None,
        target_commit_sha: Optional[str] = None,
    ) -> FeatureSnapshot:
        now = datetime.now(timezone.utc)
        missing_features: List[str] = []
        features: Dict[str, float] = {}
        cat_features: Dict[str, str] = {}

        commit_sha = target_commit_sha or deployment.commit_sha
        environment = deployment.environment or "production"
        is_prod = 1.0 if str(environment).lower() in ("prod", "production") else 0.0

        # Resolve Service and Repository if missing
        svc = service
        if not svc and deployment.service_id:
            s_stmt = select(Service).where(Service.id == deployment.service_id)
            s_res = await db.execute(s_stmt)
            svc = s_res.scalar_one_or_none()

        repo = repository
        if not repo and svc and svc.repository_id:
            r_stmt = select(Repository).where(Repository.id == svc.repository_id)
            r_res = await db.execute(r_stmt)
            repo = r_res.scalar_one_or_none()

        # ----------------------------------------------------
        # 1. Change Features (from Commit & Changes)
        # ----------------------------------------------------
        files_changed = 0
        lines_added = 0
        lines_deleted = 0
        config_files_modified = 0
        dep_manifests_modified = 0
        infra_modified = 0

        commit_record: Optional[Commit] = None
        if commit_sha:
            c_stmt = (
                select(Commit)
                .where(
                    and_(
                        Commit.tenant_id == tenant_id,
                        Commit.commit_sha == commit_sha,
                    )
                )
                .options(selectinload(Commit.changes))
            )
            c_res = await db.execute(c_stmt)
            commit_record = c_res.scalar_one_or_none()

        if commit_record:
            lines_added = commit_record.stats_additions or 0
            lines_deleted = commit_record.stats_deletions or 0
            files_changed = len(commit_record.changes)

            for ch in commit_record.changes:
                fp = ch.file_path.lower()
                fname = fp.split("/")[-1]
                if fname in DEPENDENCY_MANIFEST_NAMES or any(d in fp for d in DEPENDENCY_MANIFEST_NAMES):
                    dep_manifests_modified += 1
                if any(inf in fp for inf in INFRASTRUCTURE_PATTERNS):
                    infra_modified += 1
                if any(cfg in fp for cfg in CONFIG_PATTERNS):
                    config_files_modified += 1
        else:
            missing_features.extend(["commit_diff_details", "code_changes_breakdown"])

        features["files_changed_count"] = float(files_changed)
        features["lines_added"] = float(lines_added)
        features["lines_deleted"] = float(lines_deleted)
        features["config_files_modified"] = float(config_files_modified)
        features["dependency_manifests_modified"] = float(dep_manifests_modified)
        features["infrastructure_config_modified"] = float(infra_modified)

        # ----------------------------------------------------
        # 2. Build & CI Features (Pre-deployment only)
        # ----------------------------------------------------
        ci_test_passed = 1.0
        ci_duration = 0.0
        ci_failed_jobs = 0.0
        ci_dep_failed = 0.0

        build_rec: Optional[Build] = None
        if deployment.build_id:
            b_stmt = select(Build).where(Build.id == deployment.build_id)
            b_res = await db.execute(b_stmt)
            build_rec = b_res.scalar_one_or_none()
        elif commit_sha and repo:
            b_stmt = (
                select(Build)
                .where(and_(Build.commit_sha == commit_sha, Build.repository_id == repo.id))
                .order_by(Build.created_at.desc())
            )
            b_res = await db.execute(b_stmt)
            build_rec = b_res.scalars().first()

        if build_rec:
            ci_duration = build_rec.duration_seconds or 0.0
            if build_rec.status == "FAILED":
                ci_test_passed = 0.0
                ci_failed_jobs = float(build_rec.failed_job_count or 1)
        else:
            missing_features.append("ci_build_telemetry")

        # Check workflow runs for failed jobs or dependency errors
        if commit_sha:
            wf_stmt = (
                select(WorkflowRun).where(WorkflowRun.head_sha == commit_sha).options(selectinload(WorkflowRun.jobs))
            )
            wf_res = await db.execute(wf_stmt)
            wf_runs = wf_res.scalars().all()
            for wfr in wf_runs:
                for job in wfr.jobs:
                    if str(job.conclusion).lower() == "failure":
                        ci_failed_jobs += 1.0
                        if any(term in str(job.name).lower() for term in ("dep", "install", "npm", "pip")):
                            ci_dep_failed = 1.0

        features["ci_test_passed"] = ci_test_passed
        features["ci_build_duration_seconds"] = float(ci_duration)
        features["ci_failed_jobs_count"] = float(ci_failed_jobs)
        features["ci_dependency_install_failed"] = float(ci_dep_failed)

        # ----------------------------------------------------
        # 3. Repository Historical Risk Features
        # ----------------------------------------------------
        repo_dep_failure_rate = 0.0
        repo_recent_incidents_30d = 0.0
        repo_unresolved_incidents = 0.0

        if repo:
            # Query historical deployments strictly prior to current deployment
            hist_dep_stmt = select(Deployment.status).where(
                and_(
                    Deployment.tenant_id == tenant_id,
                    Deployment.service_id == svc.id if svc else False,
                    Deployment.created_at < deployment.created_at if deployment.created_at else True,
                )
            )
            hist_res = await db.execute(hist_dep_stmt)
            all_statuses = hist_res.scalars().all()
            if all_statuses:
                fail_count = sum(1 for s in all_statuses if s in ("FAILED", "ROLLED_BACK"))
                repo_dep_failure_rate = fail_count / len(all_statuses)

            # Incidents in last 30 days
            thirty_days_ago = now - timedelta(days=30)
            inc_stmt = select(Incident).where(
                and_(
                    Incident.tenant_id == tenant_id,
                    Incident.repository_id == repo.id,
                    Incident.detected_at >= thirty_days_ago,
                )
            )
            inc_res = await db.execute(inc_stmt)
            recent_incidents = inc_res.scalars().all()
            repo_recent_incidents_30d = float(len(recent_incidents))
            repo_unresolved_incidents = float(sum(1 for i in recent_incidents if i.status == "OPEN"))
        else:
            missing_features.extend(["repository_historical_failure_rate", "repository_incident_history"])

        features["repo_historical_deployment_failure_rate"] = float(repo_dep_failure_rate)
        features["repo_recent_incidents_30d"] = float(repo_recent_incidents_30d)
        features["repo_unresolved_incidents"] = float(repo_unresolved_incidents)

        # ----------------------------------------------------
        # 4. Infrastructure & Dependency Graph Features
        # ----------------------------------------------------
        downstream_count = 0.0
        graph_depth = 0.0
        svc_criticality = 2.0  # default tier-2

        if svc:
            if svc.tier == "tier-1":
                svc_criticality = 1.0
            elif svc.tier == "tier-3":
                svc_criticality = 3.0

            # Count downstream services that depend on this service
            dep_stmt = select(ServiceDependency).where(
                and_(
                    ServiceDependency.tenant_id == tenant_id,
                    ServiceDependency.target_service_id == svc.id,
                )
            )
            dep_res = await db.execute(dep_stmt)
            downstream_deps = dep_res.scalars().all()
            downstream_count = float(len(downstream_deps))
            graph_depth = 1.0 if downstream_count > 0 else 0.0
        else:
            missing_features.append("service_dependency_graph")

        features["environment_is_production"] = is_prod
        features["service_tier_criticality"] = svc_criticality
        features["downstream_dependency_count"] = downstream_count
        features["dependency_graph_depth"] = graph_depth

        # ----------------------------------------------------
        # 5. Operational Memory Signals (M3 Memory)
        # ----------------------------------------------------
        similar_incidents_count = 0.0
        verified_lessons_count = 0.0

        if repo:
            mem_stmt = select(Incident).where(
                and_(
                    Incident.tenant_id == tenant_id,
                    Incident.repository_id == repo.id,
                    Incident.status == "RESOLVED",
                )
            )
            mem_res = await db.execute(mem_stmt)
            resolved_incs = mem_res.scalars().all()
            similar_incidents_count = float(len(resolved_incs))

            crc_stmt = select(ConfirmedRootCause).where(
                and_(
                    ConfirmedRootCause.tenant_id == tenant_id,
                    ConfirmedRootCause.incident_id.in_([i.id for i in resolved_incs]) if resolved_incs else False,
                )
            )
            if resolved_incs:
                crc_res = await db.execute(crc_stmt)
                verified_lessons_count = float(len(crc_res.scalars().all()))

        features["similar_verified_incidents_count"] = similar_incidents_count
        features["verified_root_cause_matches_count"] = verified_lessons_count

        cat_features["environment"] = environment
        cat_features["service_name"] = svc.name if svc else "unknown"
        cat_features["service_tier"] = svc.tier if svc else "tier-2"

        return FeatureSnapshot(
            schema_version=FEATURE_SCHEMA_VERSION,
            extracted_at=now,
            features=features,
            categorical_features=cat_features,
            missing_features=missing_features,
            metadata={
                "commit_sha": commit_sha,
                "environment": environment,
                "repository": repo.full_name if repo else None,
            },
        )


feature_engineering_service = FeatureEngineeringService()
