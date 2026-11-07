"""Modular Failure Detection and Classification Engine.

Implements versioned deterministic classification taxonomy across:
- BUILD_FAILURE
- DEPLOYMENT_FAILURE
- CONFIGURATION_FAILURE
- INFRASTRUCTURE_FAILURE
- UNKNOWN_FAILURE

Never fabricates errors. Distinguishes cancelled, skipped, timed out, and failed states.
"""
from __future__ import annotations
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

CLASSIFIER_VERSION = "1.0.0"

# Category Definitions
CAT_BUILD_FAILURE = "BUILD_FAILURE"
CAT_DEPLOYMENT_FAILURE = "DEPLOYMENT_FAILURE"
CAT_CONFIGURATION_FAILURE = "CONFIGURATION_FAILURE"
CAT_INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
CAT_UNKNOWN_FAILURE = "UNKNOWN_FAILURE"

# Subcategory Definitions
SUB_COMPILATION = "Compilation failure"
SUB_DEPENDENCY = "Dependency installation failure"
SUB_UNIT_TEST = "Unit test failure"
SUB_INTEGRATION_TEST = "Integration test failure"
SUB_CONTAINER_BUILD = "Container image build failure"
SUB_ARTIFACT = "Artifact generation failure"

SUB_DEPLOY_REJECTED = "Deployment rejected"
SUB_DEPLOY_STATUS_FAILED = "Deployment status failure"
SUB_HEALTH_CHECK_FAILED = "Health-check failure"
SUB_ROLLBACK = "Rollback event"
SUB_DEPLOY_TIMEOUT = "Deployment timeout"

SUB_MISSING_CONFIG = "Missing configuration"
SUB_INVALID_CONFIG = "Invalid environment configuration"
SUB_CONFIG_MISMATCH = "Configuration mismatch"
SUB_SECRET_REF_FAILED = "Secret reference failure"

SUB_CONTAINER_CRASH = "Container crash"
SUB_RESOURCE_EXHAUSTION = "Resource exhaustion"
SUB_POD_SCHEDULING = "Pod scheduling failure"
SUB_SERVICE_UNAVAILABLE = "Service unavailable"
SUB_INFRA_DEP_UNAVAILABLE = "Infrastructure dependency unavailable"

SUB_INSUFFICIENT_EVIDENCE = "Insufficient evidence"
SUB_UNCLASSIFIED = "Unclassified event"
SUB_INCOMPLETE_DIAGNOSTIC = "Incomplete diagnostic information"
SUB_CANCELLED_OR_SKIPPED = "Cancelled or skipped workflow"


@dataclass
class ClassificationResult:
    category: str
    subcategory: str
    classification_method: str = "DETERMINISTIC_RULE"
    classifier_version: str = CLASSIFIER_VERSION
    confidence_level: str = "HIGH"  # HIGH, MEDIUM, LOW, INSUFFICIENT_EVIDENCE
    evidence: Dict[str, Any] = field(default_factory=dict)
    is_terminal_failure: bool = True


class FailureClassifier:
    """Deterministic failure classification engine."""

    # Pre-compiled regex patterns for deterministic parsing
    COMPILATION_PATTERNS = [
        re.compile(r"(?:syntaxerror|typeerror|cannot find symbol|compilation error|build failed|tsc.*error|fatal error: .* file not found|undeclared identifier)", re.IGNORECASE),
        re.compile(r"(?:javac.*error|gcc.*error|clang.*error|rustc.*error|cargo build.*failed|go build.*failed)", re.IGNORECASE)
    ]

    DEPENDENCY_PATTERNS = [
        re.compile(r"(?:pip.*could not find a version|npm err! 404|yarn error: package not found|resolution failed|cannot resolve dependency|checksum mismatch|could not resolve host: pypi|failed to download package)", re.IGNORECASE),
        re.compile(r"(?:connection refused.*npm|maven.*could not resolve dependencies|gem: could not find a valid gem)", re.IGNORECASE)
    ]

    UNIT_TEST_PATTERNS = [
        re.compile(r"(?:test(?:s)? failed|failed \d+ of \d+ tests|pytest.*failed|junit.*failures=\"[1-9]|assertions failed|jest.*failed|go test.*FAIL)", re.IGNORECASE),
        re.compile(r"(?:FAIL: test_|AssertionError:|expected:.*actual:.*)", re.IGNORECASE)
    ]

    INTEGRATION_TEST_PATTERNS = [
        re.compile(r"(?:integration test.*failed|e2e test.*failed|cypress.*failed|playwright.*failed|selenium.*error)", re.IGNORECASE),
    ]

    CONTAINER_BUILD_PATTERNS = [
        re.compile(r"(?:docker build.*failed|failed to solve with frontend dockerfile|error: failed to solve: process .* did not complete successfully|buildkit error|dockerfile parse error)", re.IGNORECASE),
    ]

    CONFIG_PATTERNS = [
        re.compile(r"(?:missing required environment variable|unknown environment variable|invalid configuration|config error|yaml parse error|unmarshal error|env.*is not set)", re.IGNORECASE),
    ]

    SECRET_PATTERNS = [
        re.compile(r"(?:secret not found|vault: permission denied|failed to read secret|secret reference .* cannot be resolved|auth token expired|unauthorized.*access token)", re.IGNORECASE)
    ]

    CONTAINER_CRASH_PATTERNS = [
        re.compile(r"(?:CrashLoopBackOff|back-off .* restarting failed container|container terminated with exit code|panic: runtime error|segmentation fault|SIGSEGV|SIGABRT)", re.IGNORECASE)
    ]

    RESOURCE_EXHAUSTION_PATTERNS = [
        re.compile(r"(?:OOMKilled|command killed due to out of memory|insufficient memory|out of memory|fatal error: runtime: out of memory|exit code 137)", re.IGNORECASE),
        re.compile(r"(?:disk space full|no space left on device|ephemeral-storage exceeded)", re.IGNORECASE)
    ]

    POD_SCHEDULING_PATTERNS = [
        re.compile(r"(?:0/\d+ nodes are available|insufficient cpu|insufficient memory|ImagePullBackOff|ErrImagePull|failed to pull image|manifest unknown)", re.IGNORECASE)
    ]

    TIMEOUT_PATTERNS = [
        re.compile(r"(?:context deadline exceeded|timed out after|operation timed out|execution timeout|job timed out|timeout reached)", re.IGNORECASE)
    ]

    HEALTH_CHECK_PATTERNS = [
        re.compile(r"(?:liveness probe failed|readiness probe failed|startup probe failed|healthcheck failed|503 service unavailable|502 bad gateway)", re.IGNORECASE)
    ]

    def classify_event(self, event_type: str, payload: Dict[str, Any]) -> List[ClassificationResult]:
        """Classifies a normalized event or raw delivery payload into one or more categories."""
        results: List[ClassificationResult] = []

        # 1. Handle GitHub Actions workflow run / job conclusions
        if event_type in ("workflow_run", "workflow_job"):
            res = self._classify_workflow(event_type, payload)
            if res:
                results.extend(res)
            return results or [self._unknown_result("No explicit failure signal in workflow event", payload)]

        # 2. Handle deployment events
        if event_type in ("deployment", "deployment_status"):
            res = self._classify_deployment(event_type, payload)
            if res:
                results.extend(res)
            return results or [self._unknown_result("No explicit failure signal in deployment event", payload)]

        # 3. Handle raw diagnostic error messages / log signals
        error_msg = payload.get("error_message") or payload.get("message") or payload.get("log_text") or ""
        if error_msg:
            res = self.classify_text(str(error_msg), payload)
            if res:
                results.extend(res)
                return results

        return [self._unknown_result("Unclassified event type with insufficient diagnostic context", payload)]

    def _classify_workflow(self, event_type: str, payload: Dict[str, Any]) -> List[ClassificationResult]:
        conclusion = (
            payload.get("conclusion")
            or payload.get("workflow_run", {}).get("conclusion")
            or payload.get("workflow_job", {}).get("conclusion")
            or payload.get("status")
            or ""
        ).lower()

        name = (
            payload.get("workflow_name")
            or payload.get("workflow_run", {}).get("name")
            or payload.get("workflow_job", {}).get("name")
            or ""
        )
        
        # Check non-failure states
        if conclusion in ("success", "neutral"):
            return []  # Not a failure

        if conclusion in ("cancelled", "skipped"):
            return [
                ClassificationResult(
                    category=CAT_UNKNOWN_FAILURE,
                    subcategory=SUB_CANCELLED_OR_SKIPPED,
                    confidence_level="HIGH",
                    evidence={
                        "event_type": event_type,
                        "conclusion": conclusion,
                        "name": name,
                        "note": "Workflow was deliberately cancelled or skipped by user/rule, not an unexpected failure."
                    },
                    is_terminal_failure=False,
                )
            ]

        if conclusion == "timed_out":
            return [
                ClassificationResult(
                    category=CAT_DEPLOYMENT_FAILURE if "deploy" in name.lower() else CAT_BUILD_FAILURE,
                    subcategory=SUB_DEPLOY_TIMEOUT if "deploy" in name.lower() else "Build execution timeout",
                    confidence_level="HIGH",
                    evidence={"event_type": event_type, "conclusion": "timed_out", "workflow_name": name},
                )
            ]

        # Gather diagnostic text from job steps or errors
        steps = payload.get("workflow_job", {}).get("steps", []) or payload.get("steps", [])
        failed_steps = [s for s in steps if str(s.get("conclusion", "")).lower() == "failure"]
        step_names = " ".join([str(s.get("name", "")) for s in failed_steps])
        
        combined_text = f"{name} {step_names} {payload.get('error_message', '')}"

        matches = self.classify_text(combined_text, {"workflow_name": name, "failed_steps": failed_steps, "conclusion": conclusion})
        if matches:
            return matches

        # Fallback to generic build or deployment failure based on workflow name
        if any(term in name.lower() for term in ("deploy", "release", "cd", "rollout")):
            return [
                ClassificationResult(
                    category=CAT_DEPLOYMENT_FAILURE,
                    subcategory=SUB_DEPLOY_STATUS_FAILED,
                    confidence_level="MEDIUM",
                    evidence={"workflow_name": name, "conclusion": conclusion, "raw_signal": "Failed deployment workflow"},
                )
            ]
        
        return [
            ClassificationResult(
                category=CAT_BUILD_FAILURE,
                subcategory="General workflow execution failure",
                confidence_level="MEDIUM",
                evidence={"workflow_name": name, "conclusion": conclusion, "failed_steps_count": len(failed_steps)},
            )
        ]

    def _classify_deployment(self, event_type: str, payload: Dict[str, Any]) -> List[ClassificationResult]:
        state = (
            payload.get("state")
            or payload.get("deployment_status", {}).get("state")
            or payload.get("status")
            or ""
        ).lower()
        desc = (
            payload.get("description")
            or payload.get("deployment_status", {}).get("description")
            or ""
        )

        if state in ("success", "active"):
            return []

        if state in ("failure", "error"):
            # Check description for specific signals
            matches = self.classify_text(desc, {"deployment_state": state, "description": desc})
            if matches:
                return matches
            return [
                ClassificationResult(
                    category=CAT_DEPLOYMENT_FAILURE,
                    subcategory=SUB_DEPLOY_STATUS_FAILED,
                    confidence_level="HIGH",
                    evidence={"state": state, "description": desc},
                )
            ]

        return []

    def classify_text(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[ClassificationResult]:
        """Inspects text and returns all matching failure classifications."""
        results: List[ClassificationResult] = []
        ctx = context or {}

        # Resource exhaustion
        if any(p.search(text) for p in self.RESOURCE_EXHAUSTION_PATTERNS) or ctx.get("exit_code") == 137:
            results.append(
                ClassificationResult(
                    category=CAT_INFRASTRUCTURE_FAILURE,
                    subcategory=SUB_RESOURCE_EXHAUSTION,
                    confidence_level="HIGH",
                    evidence={**ctx, "matched_text_snippet": text[:300], "pattern": "OOM/Disk Exhaustion"},
                )
            )

        # Container crash
        if any(p.search(text) for p in self.CONTAINER_CRASH_PATTERNS):
            results.append(
                ClassificationResult(
                    category=CAT_INFRASTRUCTURE_FAILURE,
                    subcategory=SUB_CONTAINER_CRASH,
                    confidence_level="HIGH",
                    evidence={**ctx, "matched_text_snippet": text[:300], "pattern": "CrashLoopBackOff/Panic/Segfault"},
                )
            )

        # Pod scheduling / image pull
        if any(p.search(text) for p in self.POD_SCHEDULING_PATTERNS):
            results.append(
                ClassificationResult(
                    category=CAT_INFRASTRUCTURE_FAILURE,
                    subcategory=SUB_POD_SCHEDULING,
                    confidence_level="HIGH",
                    evidence={**ctx, "matched_text_snippet": text[:300], "pattern": "ImagePull/Scheduling"},
                )
            )

        # Secret reference failure
        if any(p.search(text) for p in self.SECRET_PATTERNS):
            results.append(
                ClassificationResult(
                    category=CAT_CONFIGURATION_FAILURE,
                    subcategory=SUB_SECRET_REF_FAILED,
                    confidence_level="HIGH",
                    evidence={**ctx, "matched_text_snippet": text[:300], "pattern": "SecretReferenceError"},
                )
            )

        # Config mismatch / missing
        if any(p.search(text) for p in self.CONFIG_PATTERNS):
            results.append(
                ClassificationResult(
                    category=CAT_CONFIGURATION_FAILURE,
                    subcategory=SUB_MISSING_CONFIG,
                    confidence_level="HIGH",
                    evidence={**ctx, "matched_text_snippet": text[:300], "pattern": "Missing/InvalidConfig"},
                )
            )

        # Unit / Integration test failures
        if any(p.search(text) for p in self.UNIT_TEST_PATTERNS):
            results.append(
                ClassificationResult(
                    category=CAT_BUILD_FAILURE,
                    subcategory=SUB_UNIT_TEST,
                    confidence_level="HIGH",
                    evidence={**ctx, "matched_text_snippet": text[:300], "pattern": "TestFailure"},
                )
            )
        elif any(p.search(text) for p in self.INTEGRATION_TEST_PATTERNS):
            results.append(
                ClassificationResult(
                    category=CAT_BUILD_FAILURE,
                    subcategory=SUB_INTEGRATION_TEST,
                    confidence_level="HIGH",
                    evidence={**ctx, "matched_text_snippet": text[:300], "pattern": "IntegrationTestFailure"},
                )
            )

        # Dependency installation failure
        if any(p.search(text) for p in self.DEPENDENCY_PATTERNS):
            results.append(
                ClassificationResult(
                    category=CAT_BUILD_FAILURE,
                    subcategory=SUB_DEPENDENCY,
                    confidence_level="HIGH",
                    evidence={**ctx, "matched_text_snippet": text[:300], "pattern": "DependencyResolution"},
                )
            )

        # Container build failure
        if any(p.search(text) for p in self.CONTAINER_BUILD_PATTERNS):
            results.append(
                ClassificationResult(
                    category=CAT_BUILD_FAILURE,
                    subcategory=SUB_CONTAINER_BUILD,
                    confidence_level="HIGH",
                    evidence={**ctx, "matched_text_snippet": text[:300], "pattern": "ContainerBuildFailure"},
                )
            )

        # Compilation failure
        if any(p.search(text) for p in self.COMPILATION_PATTERNS):
            results.append(
                ClassificationResult(
                    category=CAT_BUILD_FAILURE,
                    subcategory=SUB_COMPILATION,
                    confidence_level="HIGH",
                    evidence={**ctx, "matched_text_snippet": text[:300], "pattern": "CompilationError"},
                )
            )

        # Healthcheck failure
        if any(p.search(text) for p in self.HEALTH_CHECK_PATTERNS):
            results.append(
                ClassificationResult(
                    category=CAT_DEPLOYMENT_FAILURE,
                    subcategory=SUB_HEALTH_CHECK_FAILED,
                    confidence_level="HIGH",
                    evidence={**ctx, "matched_text_snippet": text[:300], "pattern": "HealthCheckProbeFailure"},
                )
            )

        return results

    def _unknown_result(self, reason: str, payload: Dict[str, Any]) -> ClassificationResult:
        return ClassificationResult(
            category=CAT_UNKNOWN_FAILURE,
            subcategory=SUB_INSUFFICIENT_EVIDENCE,
            confidence_level="INSUFFICIENT_EVIDENCE",
            evidence={"diagnostic_reason": reason, "payload_keys": list(payload.keys())},
            is_terminal_failure=False,
        )


# Global instance
failure_classifier = FailureClassifier()
