import pytest
from app.services.failure_classifier import (
    failure_classifier,
    CAT_BUILD_FAILURE,
    CAT_DEPLOYMENT_FAILURE,
    CAT_CONFIGURATION_FAILURE,
    CAT_INFRASTRUCTURE_FAILURE,
    CAT_UNKNOWN_FAILURE,
    SUB_COMPILATION,
    SUB_DEPENDENCY,
    SUB_UNIT_TEST,
    SUB_CONTAINER_BUILD,
    SUB_CONTAINER_CRASH,
    SUB_RESOURCE_EXHAUSTION,
    SUB_SECRET_REF_FAILED,
    SUB_CANCELLED_OR_SKIPPED,
    SUB_INSUFFICIENT_EVIDENCE,
)


def test_classify_compilation_failure():
    payload = {
        "workflow_name": "build-and-test",
        "conclusion": "failure",
        "error_message": "tsc error: cannot find symbol 'DatabaseConfig' in module db.ts",
    }
    results = failure_classifier.classify_event("workflow_run", payload)
    assert len(results) >= 1
    assert any(r.category == CAT_BUILD_FAILURE and r.subcategory == SUB_COMPILATION for r in results)
    assert results[0].confidence_level == "HIGH"


def test_classify_dependency_installation_failure():
    payload = {
        "workflow_name": "ci-check",
        "conclusion": "failure",
        "error_message": "npm ERR! 404 Not Found - GET https://registry.npmjs.org/@internal/billing - Not found",
    }
    results = failure_classifier.classify_event("workflow_run", payload)
    assert any(r.category == CAT_BUILD_FAILURE and r.subcategory == SUB_DEPENDENCY for r in results)


def test_classify_unit_test_failure():
    payload = {
        "workflow_name": "pytest-suite",
        "conclusion": "failure",
        "error_message": "FAILED tests/test_payment.py::test_stripe_webhook - AssertionError: expected 200, actual 500",
    }
    results = failure_classifier.classify_event("workflow_run", payload)
    assert any(r.category == CAT_BUILD_FAILURE and r.subcategory == SUB_UNIT_TEST for r in results)


def test_classify_container_build_failure():
    payload = {
        "workflow_name": "docker-publish",
        "conclusion": "failure",
        "error_message": "error: failed to solve: process '/bin/sh -c pip install -r requirements.txt' did not complete successfully: exit code 1",
    }
    results = failure_classifier.classify_event("workflow_run", payload)
    assert any(r.category == CAT_BUILD_FAILURE for r in results)


def test_classify_infrastructure_oom_killed():
    payload = {
        "message": "Pod payment-service-5b4d7f terminated: command killed due to out of memory (OOMKilled)",
        "exit_code": 137,
    }
    results = failure_classifier.classify_event("diagnostic_log", payload)
    assert any(r.category == CAT_INFRASTRUCTURE_FAILURE and r.subcategory == SUB_RESOURCE_EXHAUSTION for r in results)


def test_classify_infrastructure_crashloop_backoff():
    payload = {
        "message": "Back-off restarting failed container web in pod auth-service-9d4f (CrashLoopBackOff)",
    }
    results = failure_classifier.classify_event("diagnostic_log", payload)
    assert any(r.category == CAT_INFRASTRUCTURE_FAILURE and r.subcategory == SUB_CONTAINER_CRASH for r in results)


def test_classify_configuration_secret_failure():
    payload = {
        "message": "Fatal: Vault secret reference 'production/stripe/api_key' cannot be resolved: permission denied",
    }
    results = failure_classifier.classify_event("diagnostic_log", payload)
    assert any(r.category == CAT_CONFIGURATION_FAILURE and r.subcategory == SUB_SECRET_REF_FAILED for r in results)


def test_classify_cancelled_workflow_not_failure():
    payload = {
        "workflow_name": "ci",
        "conclusion": "cancelled",
    }
    results = failure_classifier.classify_event("workflow_run", payload)
    assert len(results) == 1
    assert results[0].subcategory == SUB_CANCELLED_OR_SKIPPED
    assert results[0].is_terminal_failure is False


def test_classify_skipped_workflow():
    payload = {
        "workflow_name": "cd",
        "conclusion": "skipped",
    }
    results = failure_classifier.classify_event("workflow_run", payload)
    assert len(results) == 1
    assert results[0].subcategory == SUB_CANCELLED_OR_SKIPPED
    assert results[0].is_terminal_failure is False


def test_classify_unknown_failure_with_insufficient_evidence():
    payload = {
        "random_field": "some data without errors",
    }
    results = failure_classifier.classify_event("unknown_custom_signal", payload)
    assert len(results) == 1
    assert results[0].category == CAT_UNKNOWN_FAILURE
    assert results[0].subcategory == SUB_INSUFFICIENT_EVIDENCE
    assert results[0].confidence_level == "INSUFFICIENT_EVIDENCE"
