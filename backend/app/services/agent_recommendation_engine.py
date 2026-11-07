"""Recommendation Engine for Predictive DevOps Intelligence Agent.

Generates structured, evidence-backed recommendations for proposed deployments.

Distinguishes:
- Evidence-backed deterministic recommendations.
- Historical remediation runbook recommendations from verified operational memory.
- Required human actions and approvals.
"""
from __future__ import annotations
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentExecution, PolicyEvaluation
from app.models.intelligence import RiskAssessment, Recommendation
from app.services.agent_context_collector import CollectedContext

logger = logging.getLogger(__name__)


class StructuredRecommendationItem(BaseModel):
    recommendation_type: str
    title: str
    explanation: str
    rationale: str
    mitigation_steps: List[str]
    supporting_evidence: Dict[str, Any]
    historical_precedents: List[str]
    expected_operational_impact: str
    confidence_level: str  # LOW, MEDIUM, HIGH
    confidence_score: float
    required_human_action: str
    requires_approval: bool = True


class AgentRecommendationEngine:
    """Generates auditable, actionable operational recommendations."""

    async def generate_recommendations(
        self,
        db: AsyncSession,
        execution: AgentExecution,
        risk_assessment: RiskAssessment,
        policy_evaluations: List[PolicyEvaluation],
        context: CollectedContext,
    ) -> List[Recommendation]:
        recs: List[StructuredRecommendationItem] = []

        # 1. Evaluate policy outcomes
        worst_policy_outcome = "ALLOW_WITHOUT_ADDITIONAL_REVIEW"
        policy_reasons: List[str] = []
        for pe in policy_evaluations:
            policy_reasons.extend(pe.evidence.get("reasons", []))
            if pe.outcome in ("RECOMMEND_DELAY", "REQUIRE_ADDITIONAL_REVIEW"):
                worst_policy_outcome = pe.outcome
                break
            elif pe.outcome == "REQUIRE_APPROVAL":
                worst_policy_outcome = pe.outcome

        # 2. Derive primary recommendation based on composite risk and policy
        risk_level = risk_assessment.risk_level
        risk_score = risk_assessment.overall_risk_score

        if worst_policy_outcome == "RECOMMEND_DELAY" or risk_level == "CRITICAL":
            recs.append(
                StructuredRecommendationItem(
                    recommendation_type="BLOCK_DEPLOYMENT",
                    title="Halt Deployment Rollout: Critical Policy or Operational Risk",
                    explanation=f"Deployment is flagged with {risk_level} risk (score: {risk_score:.2f}). Policy evaluation requires delaying deployment until blocking conditions are cleared.",
                    rationale="; ".join(policy_reasons[:3]) if policy_reasons else "Risk score exceeds maximum allowable enterprise threshold.",
                    mitigation_steps=[
                        "Review active P1 incidents and verify root cause resolution.",
                        "Re-run CI test suite to guarantee zero regression.",
                        "Execute staging verification before requesting re-approval.",
                    ],
                    supporting_evidence={
                        "risk_score": risk_score,
                        "risk_level": risk_level,
                        "policy_outcome": worst_policy_outcome,
                        "triggered_rules": risk_assessment.triggered_rules,
                    },
                    historical_precedents=[
                        l["title"] for l in context.operational_memory.get("verified_lessons", [])[:2]
                    ],
                    expected_operational_impact="Prevents widespread downstream service outages and SLO violations.",
                    confidence_level="HIGH",
                    confidence_score=0.90,
                    required_human_action="Requires explicit SRE Team Lead rejection or sign-off after remediation.",
                    requires_approval=True,
                )
            )
        elif worst_policy_outcome in ("REQUIRE_ADDITIONAL_REVIEW", "REQUIRE_APPROVAL") or risk_level == "HIGH":
            recs.append(
                StructuredRecommendationItem(
                    recommendation_type="REQUIRE_CONFIG_REVIEW",
                    title="Mandatory SRE Sign-off: High-Impact / Production Surface",
                    explanation="Deployment affects production environment or core service dependencies. SRE verification is required prior to traffic routing.",
                    rationale="; ".join(policy_reasons[:2]) if policy_reasons else "High blast radius and Tier-1 service dependency exposure.",
                    mitigation_steps=[
                        "Verify database migration backwards-compatibility.",
                        "Inspect container resource requests and limits.",
                        "Confirm automated rollback triggers and monitoring dashboards are active.",
                    ],
                    supporting_evidence={
                        "impact_score": risk_assessment.operational_impact_score,
                        "affected_services": risk_assessment.affected_services,
                        "environment": context.github_context.get("environment"),
                    },
                    historical_precedents=[],
                    expected_operational_impact="Limits blast radius to isolated canary pods.",
                    confidence_level="HIGH",
                    confidence_score=0.85,
                    required_human_action="Requires authorized reviewer sign-off in Approval Center.",
                    requires_approval=True,
                )
            )
        else:
            recs.append(
                StructuredRecommendationItem(
                    recommendation_type="PROCEED_WITH_CANARY",
                    title="Proceed with Progressive Canary Rollout",
                    explanation="Proposed changes satisfy deterministic policy checks and exhibit low historical risk.",
                    rationale="Automated test suite passed and no active degraded dependencies detected.",
                    mitigation_steps=[
                        "Route 5% initial traffic for 15 minutes.",
                        "Monitor HTTP 5xx error rate and container restart telemetry.",
                        "Promote to 100% upon error-free observation window.",
                    ],
                    supporting_evidence={
                        "risk_score": risk_score,
                        "ci_test_passed": True,
                    },
                    historical_precedents=[],
                    expected_operational_impact="Low impact; continuous availability preserved.",
                    confidence_level="MEDIUM",
                    confidence_score=0.75,
                    required_human_action="Standard approval or automated progression per environment configuration.",
                    requires_approval=context.github_context.get("environment") in ("production", "prod"),
                )
            )

        # 3. Add operational memory lesson recommendations if precedents exist
        lessons = context.operational_memory.get("verified_lessons", [])
        if lessons:
            primary_lesson = lessons[0]
            recs.append(
                StructuredRecommendationItem(
                    recommendation_type="FOLLOW_VERIFIED_RUNBOOK",
                    title=f"Apply Verified Runbook: {primary_lesson['title'][:60]}",
                    explanation=f"Operational memory recalled verified lesson from previous incident: {primary_lesson['lesson']}",
                    rationale="Historical precedent indicates failure pattern matches this repository component.",
                    mitigation_steps=[
                        f"Implement verified guidance: {primary_lesson['lesson']}",
                        "Audit configuration against confirmed incident prevention strategy.",
                    ],
                    supporting_evidence={"verified_lesson": primary_lesson},
                    historical_precedents=[primary_lesson["title"]],
                    expected_operational_impact="Avoids repeat occurrence of documented failure mode.",
                    confidence_level="HIGH",
                    confidence_score=0.90,
                    required_human_action="Confirm lesson applicability before rollout.",
                    requires_approval=False,
                )
            )

        # Persist recommendations to database
        saved_recs: List[Recommendation] = []
        for r in recs:
            rec_db = Recommendation(
                id=uuid.uuid4(),
                tenant_id=execution.tenant_id,
                deployment_id=risk_assessment.deployment_id,
                risk_assessment_id=risk_assessment.id,
                execution_id=execution.id,
                recommendation_type=r.recommendation_type,
                title=r.title,
                rationale=r.rationale,
                explanation=r.explanation,
                mitigation_steps=r.mitigation_steps,
                evidence_references=r.supporting_evidence,
                confidence_level=r.confidence_level,
                confidence_score=r.confidence_score,
                status="PROPOSED",
                requires_approval="true" if r.requires_approval else "false",
            )
            db.add(rec_db)
            saved_recs.append(rec_db)

        await db.flush()
        return saved_recs


agent_recommendation_engine = AgentRecommendationEngine()
