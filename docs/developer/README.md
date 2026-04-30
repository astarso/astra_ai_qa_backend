# Developer Documentation

This folder contains complete technical documentation for the Astra QA Backend platform.

## 📚 Documentation Overview

| File | Description | Size |
|------|-------------|------|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Architecture, tech stack, data model, services, authentication, configuration, development workflow | 26 KB |
| **[API_REFERENCE.md](API_REFERENCE.md)** | Complete API reference with all endpoints, request/response schemas, examples | 52 KB |

---

## Quick Start for Frontend Developers

### 1. Authentication Flow

```
1. GET /api/v1/auth/login → Redirect to SSO provider (Indid)
2. User enters credentials on SSO page
3. SSO redirects to /api/v1/auth/callback?code=xxx
4. Backend exchanges code for token
5. Frontend receives JWT in response or via redirect URL fragment
6. Store token and send with every request: Authorization: Bearer <token>
```

### 2. Frontend-Backend Integration Checklist

- [ ] Integrate OIDC login flow (redirect to `/api/v1/auth/login`)
- [ ] Handle callback URL `/api/v1/auth/callback`
- [ ] Store JWT token in localStorage/sessionStorage
- [ ] Add Authorization header to all API requests
- [ ] Handle 401 responses (redirect to login)
- [ ] Connect WebSocket at `/api/v1/ws/runs/{run_id}` for real-time updates
- [ ] Configure CORS origins to include your frontend URL

### 3. Key API Endpoints for Frontend

| Screen | Endpoints |
|--------|-----------|
| **Login** | `GET /api/v1/auth/login` → SSO redirect |
| **Projects Dashboard** | `GET /api/v1/projects` |
| **Test Suites** | `GET /api/v1/test-suites?project_id=` |
| **Test Cases** | `GET /api/v1/test-cases?suite_id=` |
| **Test Runs List** | `GET /api/v1/runs` |
| **Run Detail** | `GET /api/v1/runs/{id}` + `GET /api/v1/runs/{id}/analyses` |
| **Run Diff** | `GET /api/v1/runs/{id}/diff?compare_to={other_id}` |
| **Risk Score** | `GET /api/v1/runs/{id}/risk` |
| **Create Run** | `POST /api/v1/runs` |
| **Rerun Failed** | `POST /api/v1/runs/{id}/rerun` |
| **AI Generate Test Case** | `POST /api/v1/test-cases/generate` |
| **DORA Metrics** | `GET /api/v1/analytics/dora?project_id=` |
| **Flaky Tests** | `GET /api/v1/analytics/flaky?suite_id=` |
| **PDF Report** | `POST /api/v1/runs/{id}/report` |
| **Export Results** | `GET /api/v1/runs/{id}/export?format=csv|json` |
| **Admin Settings** | `GET/PUT /api/v1/admin/settings` |
| **User Management** | `GET/POST/PUT /api/v1/admin/users` |

### 4. Real-Time Updates (WebSocket)

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/runs/RUN_ID');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(msg.event, msg.run_id, msg.status);
  // Events: 'status_change', 'result_added', 'analysis_complete'
};
```

### 5. RBAC Permissions

| Role | Can Do |
|------|--------|
| `viewer` | Read projects, suites, runs, test cases |
| `qa_engineer` | + Create runs, submit results, create defects |
| `qa_lead` | + Create/edit test cases, manage suites |
| `admin` | + Manage users, update settings |

### 6. Response Format

All endpoints return JSON. Error responses:
```json
{
  "status": 400,
  "message": "Human-readable error",
  "details": {}
}
```

### 7. CORS Configuration

The backend accepts requests from origins listed in `CORS_ORIGINS` env variable. For development, set:
```
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

### 8. Environment Variables Reference

See [ARCHITECTURE.md](ARCHITECTURE.md) Section 6 for full list.

Key for frontend development:
```
APP_HOST=0.0.0.0
APP_PORT=8000
CORS_ORIGINS=["http://localhost:3000"]
OIDC_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback
```

### 9. Health & Metrics

- `GET /api/v1/health` — Health check (no auth required)
- `GET /metrics` — Prometheus metrics (no auth required)

### 10. Common Integration Patterns

#### Trigger a test run from CI:
```bash
POST /api/v1/runs
{
  "suite_id": "uuid",
  "commit_sha": "abc123",
  "branch": "main",
  "triggered_by": "user-uuid",
  "priority": 3,
  "environment": "dev"
}
```

#### Import JUnit results from worker:
```bash
POST /api/v1/runs/{run_id}/results
{
  "results": [
    {"test_case_id": "uuid", "status": "passed", "duration_ms": 150},
    {"test_case_id": "uuid", "status": "failed", "duration_ms": 200, "error_message": "..."}
  ]
}
```

#### GitLab CI webhook:
```bash
POST /api/v1/webhooks/gitlab
X-Gitlab-Token: your_secret_token
{
  "object_kind": "pipeline",
  "ref": "main",
  "sha": "abc123",
  "status": "success"
}
```

---

## Architecture Overview

```
┌──────────────┐     ┌─────────────────┐     ┌───────────────┐
│   Browser    │────▶│   api_core      │────▶│  PostgreSQL   │
│   (React)    │     │   (Litestar)    │     │  + pgvector   │
└──────────────┘     └────────┬────────┘     └───────────────┘
                             │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
   ┌──────────┐      ┌──────────┐       ┌──────────┐
   │ RabbitMQ │      │  Redis   │      │  MinIO   │
   │ (Taskiq) │      │          │      │ (S3 API) │
   └────┬─────┘      └──────────┘       └──────────┘
        │
        ▼
   ┌─────────────────┐
   │ worker/run_shard │
   │ (Kubernetes Job) │
   └─────────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for full technical details.