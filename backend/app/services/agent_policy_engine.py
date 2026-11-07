"""Deterministic Deployment Policy Evaluation Engine.

Evaluates organizational deployment policies against collected deployment context,
risk assessments, operational memory, and topology.

Policy Outcomes:
- ALLOW_WITHOUT_ADDITIONAL_REVIEW
- REQUIRE_APPROVAL
- REQUIRE_ADDITIONAL_REVIEW
- RECOMMEND_DELAY
- INSUFFICIENT_EVIDENCE

Invariants:
- Deterministic rule evaluation based on persisted policy configuration.
- Never executes production changes autonomously.
- Persists evaluation evidence and policy version pinning.
"""

from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentExecution, DeploymentPolicy, PolicyEvaluation
from app.services.agent_context_collector import CollectedContext

logger = logging.getLogger(__name__)

OUTCOME_ALLOW = "ALLOW_WITHOUT_ADDITIONAL_REVIEW"
OUTCOME_REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
OUTCOME_REQUIRE_ADDITIONAL_REVIEW = "REQUIRE_ADDITIONAL_REVIEW"
OUTCOME_RECOMMEND_DELAY = "RECOMMEND_DELAY"
OUTCOME_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

DEFAULT_POLICY_VERSION = "v1.0.0"

DEFAULT_POLICY_DEFINITION = {
    "max_risk_threshold": 0.65,
    "max_impact_threshold": 0.80,
    "block_on_active_p1_incident": True,
    "require_approval_environments": ["production", "prod"],
    "require_additional_review_tier1": True,
    "require_ci_tests_passed": True,
    "require_minimum_context_fields": ["repository", "service_tier"],
}


class PolicyEvaluationResult(BaseModel):
    policy_id: str
    policy_name: str
    policy_version: str
    outcome: str
    reasons: List[str]
    evidence: Dict[str, Any]
    required_reviewers_count: int = 1
    escalation_required: bool = False


class AgentPolicyEngine:
    """Evaluates deployment policies deterministically."""

    async def get_or_create_default_policy(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> DeploymentPolicy:
        stmt = select(DeploymentPolicy).where(
            and_(
                DeploymentPolicy.tenant_id == tenant_id,
                DeploymentPolicy.name == "Standard Enterprise Deployment Governance",
            )
        )
        res = await db.execute(stmt)
        policy = res.scalar_one_or_none()
        if policy:
            return policy

        new_policy = DeploymentPolicy(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name="Standard Enterprise Deployment Governance",
            description="Default enterprise deployment policy enforcing CI validation, risk thresholds, and Tier-1 approvals.",
            policy_version=DEFAULT_POLICY_VERSION,
            enabled=True,
            policy_definition=DEFAULT_POLICY_DEFINITION,
        )
        db.add(new_policy)
        await db.flush()
        return new_policy

    async def evaluate_policies(
        self,
        db: AsyncSession,
        execution: AgentExecution,
        context: CollectedContext,
        risk_score: float,
        impact_score: float,
        risk_level: str,
    ) -> List[PolicyEvaluation]:
        """Evaluates all enabled policies for the tenant against the deployment execution."""
        stmt = select(DeploymentPolicy).where(
            and_(
                DeploymentPolicy.tenant_id == execution.tenant_id,
                DeploymentPolicy.enabled.is_(True),
            )
        )
        res = await db.execute(stmt)
        policies = res.scalars().all()

        if not policies:
            default_p = await self.get_or_create_default_policy(db, execution.tenant_id)
            policies = [default_p]

        evaluations: List[PolicyEvaluation] = []
        now = datetime.now(timezone.utc)

        for p in policies:
            result = self._evaluate_single_policy(p, context, risk_score, impact_score, risk_level)
            evaluation_rec = PolicyEvaluation(
                id=uuid.uuid4(),
                tenant_id=execution.tenant_id,
                execution_id=execution.id,
                policy_id=p.id,
                policy_version=p.policy_version,
                outcome=result.outcome,
                evidence={
                    "reasons": result.reasons,
                    "evidence_details": result.evidence,
                    "required_reviewers_count": result.required_reviewers_count,
                    "escalation_required": result.escalation_required,
                },
                evaluated_at=now,
            )
            db.add(evaluation_rec)
            evaluations.append(evaluation_rec)

        await db.flush()
        return evaluations

    def _evaluate_single_policy(
        self,
        policy: DeploymentPolicy,
        context: CollectedContext,
        risk_score: float,
        impact_score: float,
        risk_level: str,
    ) -> PolicyEvaluationResult:
        defn = policy.policy_definition or DEFAULT_POLICY_DEFINITION
        reasons: List[str] = []
        evidence: Dict[str, Any] = {}
        outcome = OUTCOME_ALLOW

        gh = context.github_context
        infra = context.infrastructure_context
        op_mem = context.operational_memory

        environment = (gh.get("environment") or "production").lower()
        service_tier = infra.get("target_service", {}).get("tier", "tier-2")
        build_info = gh.get("build")

        # 1. Check missing evidence threshold
        missing_count = len(context.missing_context)
        evidence["missing_context"] = context.missing_context
        if missing_count >= 3:
            outcome = OUTCOME_INSUFFICIENT_EVIDENCE
            reasons.append(
                f"Deployment missing {missing_count} critical telemetry signals ({', '.join(context.missing_context)})."
            )
            return PolicyEvaluationResult(
                policy_id=str(policy.id),
                policy_name=policy.name,
                policy_version=policy.policy_version,
                outcome=outcome,
                reasons=reasons,
                evidence=evidence,
                required_reviewers_count=1,
            )

        # 2. Check active critical incidents (RECOMMEND_DELAY)
        if defn.get("block_on_active_p1_incident", True):
            active_p1s = [
                inc
                for inc in op_mem.get("similar_incidents", [])
                if inc.get("status") in ("OPEN", "MITIGATING") and inc.get("severity") in ("P1", "CRITICAL")
            ]
            if active_p1s:
                outcome = OUTCOME_RECOMMEND_DELAY
                reasons.append(
                    f"Found {len(active_p1s)} active unresolved P1/Critical incident(s) on target component. Recommending deployment delay."
                )
                evidence["active_critical_incidents"] = [i["key"] for i in active_p1s]

        # 3. Check CI Test Results (RECOMMEND_DELAY or REQUIRE_APPROVAL)
        if defn.get("require_ci_tests_passed", True):
            if build_info:
                if build_info.get("status") == "FAILED" or build_info.get("tests_failed", 0) > 0:
                    outcome = OUTCOME_RECOMMEND_DELAY
                    failed_tests = build_info.get("tests_failed", 1)
                    reasons.append(
                        f"CI build reported failure ({failed_tests} test failures). Verification incomplete."
                    )
                    evidence["ci_test_failure"] = True
            elif "build_telemetry" in context.missing_context:
                reasons.append("CI build telemetry was not provided; cannot verify automated test execution.")

        # 4. Check Risk Thresholds
        max_risk = defn.get("max_risk_threshold", 0.65)
        evidence["risk_score"] = risk_score
        evidence["max_risk_threshold"] = max_risk
        if risk_score > max_risk or risk_level == "CRITICAL":
            outcome = OUTCOME_REQUIRE_ADDITIONAL_REVIEW if outcome != OUTCOME_RECOMMEND_DELAY else outcome
            reasons.append(f"Composite risk score ({risk_score:.2f}) exceeds policy maximum ({max_risk:.2f}).")

        # 5. Check Impact & Service Tier Criticality
        max_impact = defn.get("max_impact_threshold", 0.80)
        evidence["impact_score"] = impact_score
        is_tier1 = service_tier.lower() in ("tier-1", "tier1", "critical")
        if (impact_score > max_impact or is_tier1) and defn.get("require_additional_review_tier1", True):
            if outcome == OUTCOME_ALLOW:
                outcome = OUTCOME_REQUIRE_ADDITIONAL_REVIEW
            reasons.append(
                f"Target service is {service_tier} with high operational blast radius ({impact_score:.2f}). Requires senior reviewer authorization."
            )
            evidence["tier1_critical"] = True

        # 6. Check Environment Review Requirement
        req_envs = [e.lower() for e in defn.get("require_approval_environments", ["production", "prod"])]
        if environment in req_envs:
            if outcome == OUTCOME_ALLOW:
                outcome = OUTCOME_REQUIRE_APPROVAL
            reasons.append(
                f"Deployment environment '{environment}' requires mandatory human sign-off per organizational policy."
            )
            evidence["environment"] = environment

        required_reviewers = 2 if outcome == OUTCOME_REQUIRE_ADDITIONAL_REVIEW else 1
        escalation = outcome in (OUTCOME_REQUIRE_ADDITIONAL_REVIEW, OUTCOME_RECOMMEND_DELAY)

        if not reasons:
            reasons.append("Deployment satisfies all policy thresholds and automated checks.")

        return PolicyEvaluationResult(
            policy_id=str(policy.id),
            policy_name=policy.name,
            policy_version=policy.policy_version,
            outcome=outcome,
            reasons=reasons,
            evidence=evidence,
            required_reviewers_count=required_reviewers,
            escalation_required=escalation,
        )


agent_policy_engine = AgentPolicyEngine()
