# GitHub App Integration Setup Guide

This guide walks you through connecting a real GitHub App or repository webhook to the **Predictive DevOps Intelligence Platform**.

---

## 1. GitHub App Permissions & Events

When creating a GitHub App on GitHub (`https://github.com/settings/apps/new`):

### A. General Configuration
- **GitHub App name**: `Predictive DevOps Intelligence Agent`
- **Homepage URL**: `https://your-domain.com` (or `http://localhost:3000`)
- **Webhook URL**: `https://your-public-url.com/api/v1/integrations/github/webhook` (use [ngrok](https://ngrok.com) or [smee.io](https://smee.io) for local development)
- **Webhook secret**: Create a secure random string (minimum 32 characters) and configure it in `.env` as `GITHUB_WEBHOOK_SECRET`.

### B. Repository Permissions Required (Least Privilege)
| Resource | Permission | Purpose |
|---|---|---|
| **Repository contents** | `Read-only` | Commit metadata, diffs, changed files |
| **Pull requests** | `Read-only` | PR merges, review status, base/head branches |
| **Actions** | `Read-only` | Workflow runs, jobs, durations, conclusions |
| **Deployments** | `Read-only` | Deployment status updates, target environments |
| **Metadata** | `Read-only` | Basic repository discovery |

### C. Webhook Event Subscriptions
Subscribe to the following operational events:
- [x] **Push** (`push`)
- [x] **Pull request** (`pull_request`)
- [x] **Workflow run** (`workflow_run`)
- [x] **Workflow job** (`workflow_job`)
- [x] **Deployment** (`deployment`)
- [x] **Deployment status** (`deployment_status`)

---

## 2. Environment Configuration

Generate a Private Key from your GitHub App page (PEM format) and copy the values into your `.env` file:

```env
# GitHub App Authentication
GITHUB_APP_ID=123456
GITHUB_APP_INSTALLATION_ID=78901234
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMIIEogIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET="your-configured-webhook-secret"

# Optional Alternative: Personal Access Token (for reconciliation fallback)
GITHUB_API_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

---

## 3. Webhook Delivery & Event Pipeline

Every GitHub delivery undergoes:
1. **HMAC-SHA256 Signature Verification** (`X-Hub-Signature-256`) via constant-time comparison.
2. **Payload Size Limit Verification** (capped at 10 MB).
3. **Delivery Deduplication** via unique `X-GitHub-Delivery` ID in the `webhook_deliveries` ledger.
4. **Redis Streams Ingestion** (`stream:devops:events`) in consumer group `group:devops:intelligence`.
5. **Deterministic Correlation**:
   - Push commits linked to repository and changed files.
   - Pull requests correlated to head commit SHA.
   - GitHub Actions workflow runs correlated to commit SHA.
   - Successful workflows generate build execution records.
   - Deployment events generate discrete environment deployments (independently of builds).
   - Deployment timelines assemble chronologically.

---

## 4. Testing Webhook Ingestion Locally

You can test local webhook delivery using `curl`:

```bash
# Generate signature:
PAYLOAD='{"repository":{"id":123,"name":"test-service","full_name":"acme/test-service"},"ref":"refs/heads/main","after":"c0ffee1234567890c0ffee1234567890c0ffee12","commits":[]}'
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "test-github-webhook-secret" | awk '{print $2}')

curl -X POST http://localhost:8000/api/v1/integrations/github/webhook \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=$SIG" \
  -H "X-GitHub-Event: push" \
  -H "X-GitHub-Delivery: manual-test-001" \
  -d "$PAYLOAD"
```

---

## 5. Known Limitations & Fallbacks
- **Offline / Isolated Mode**: When Redis is temporarily unavailable or in local test environments, the webhook receiver safely persists deliveries to PostgreSQL and falls back to synchronous processing without dropping events.
- **GitHub API Rate Limits**: Reconciliation queries use exponential backoff and caching to respect GitHub's 5,000 req/hr rate limit.
- **Private Key Storage**: In production deployments on Kubernetes, mount `GITHUB_APP_PRIVATE_KEY` as a secret file via `GITHUB_APP_PRIVATE_KEY_PATH`.
