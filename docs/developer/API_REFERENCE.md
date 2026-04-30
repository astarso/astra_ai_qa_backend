# Astra QA Backend API Reference

API version: 1.0.0

## 1. Introduction

Astra QA Backend is a platform for continuous testing and software verification with AI LLM agents. It provides a comprehensive REST API for managing test projects, suites, cases, runs, analytics, and integrations with external CI/CD systems.

### Base URL

```
https://astra.example.com
```

All API endpoints are prefixed with `/api/v1`.

### Authentication

The platform uses OpenID Connect (OIDC) / SSO for authentication. All endpoints except health checks and webhooks require a Bearer token.

#### OIDC JWT Bearer Token

Include the JWT token in the Authorization header:

```
Authorization: Bearer <token>
```

Token claims include `sub`, `email`, `name`, and `roles`. Roles are extracted from `realm_access.roles` or the top-level `roles` claim.

#### RBAC Roles

| Role | Description |
|------|-------------|
| `admin` | Full access to all endpoints including admin settings |
| `qa_lead` | Manage projects, suites, schedules, and view analytics |
| `qa_engineer` | Create and run tests, view results |
| `viewer` | Read-only access to projects and test results |

### Rate Limiting

Rate limits are enforced per IP and per user. Default limits:

- 1000 requests per minute for authenticated users
- 100 requests per minute for unauthenticated endpoints

### Error Response Format

All errors follow a consistent JSON structure:

```json
{
  "status": 500,
  "message": "Human-readable error message",
  "details": {}
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | integer | HTTP status code |
| `message` | string | Human-readable error description |
| `details` | object | Optional additional error context |

---

## 2. Authentication

### `GET /api/v1/auth/login`

Initiate SSO login by redirecting to the OIDC provider.

**Authentication:** None

**Response:** `302 Redirect` to OIDC authorization endpoint

**Query Parameters:** None

**Response Headers:**
- `Location`: OIDC authorization URL with query parameters

---

### `GET /api/v1/auth/callback`

OIDC callback handler. Exchanges authorization code for tokens.

**Authentication:** None

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code` | string | Yes | Authorization code from OIDC provider |
| `error` | string | No | Error message if authentication failed |

**Response Codes:**
- `200 OK` — Successful authentication
- `400 Bad Request` — Missing code or error parameter
- `502 Bad Gateway` — Token exchange with IdP failed

**Response Body:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "sub": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "John Doe",
    "roles": ["qa_engineer"]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `access_token` | string | JWT access token for API authentication |
| `id_token` | string | OIDC ID token |
| `refresh_token` | string | Token for refreshing access |
| `token_type` | string | Always "Bearer" |
| `expires_in` | integer | Seconds until token expiration |
| `user.sub` | string (UUID) | User identifier |
| `user.email` | string | User email address |
| `user.name` | string | User display name |
| `user.roles` | array[string] | Assigned RBAC roles |

---

## 3. Projects

### `POST /api/v1/projects`

Create a new project.

**Authentication:** Authenticated user (role: `admin` or `qa_lead`)

**Request Body:**
```json
{
  "code": "MYPROJECT",
  "name": "My Project",
  "owner_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | Yes | Unique project code (alphanumeric) |
| `name` | string | Yes | Human-readable project name |
| `owner_id` | string (UUID) | Yes | Owner user ID |

**Response Codes:**
- `201 Created` — Project created successfully
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions

**Response Body:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "code": "MYPROJECT",
  "name": "My Project",
  "owner_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-04-28T12:00:00Z"
}
```

---

### `GET /api/v1/projects`

List all projects.

**Authentication:** Authenticated user

**Query Parameters:** None

**Response Codes:**
- `200 OK` — List returned successfully
- `401 Unauthorized` — Missing or invalid token

**Response Body:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "code": "MYPROJECT",
    "name": "My Project",
    "owner_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-04-28T12:00:00Z"
  }
]
```

---

### `GET /api/v1/projects/{project_id}`

Get a specific project by ID.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | UUID | Project identifier |

**Response Codes:**
- `200 OK` — Project found
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Project not found

**Response Body:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "code": "MYPROJECT",
  "name": "My Project",
  "owner_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-04-28T12:00:00Z"
}
```

---

### `PUT /api/v1/projects/{project_id}`

Update a project.

**Authentication:** Authenticated user (role: `admin` or `qa_lead`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | UUID | Project identifier |

**Request Body:**
```json
{
  "code": "UPDATED",
  "name": "Updated Project Name"
}
```

All fields are optional. Only provided fields are updated.

**Response Codes:**
- `200 OK` — Project updated successfully
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Project not found

**Response Body:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "code": "UPDATED",
  "name": "Updated Project Name",
  "owner_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-04-28T12:00:00Z"
}
```

---

### `DELETE /api/v1/projects/{project_id}`

Delete a project.

**Authentication:** Authenticated user (role: `admin`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | UUID | Project identifier |

**Response Codes:**
- `200 OK` — Project deleted successfully
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Project not found

**Response Body:**
```json
{
  "status": "deleted"
}
```

---

## 4. Test Suites

### `POST /api/v1/test-suites`

Create a new test suite.

**Authentication:** Authenticated user (role: `admin`, `qa_lead`, or `qa_engineer`)

**Request Body:**
```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Integration Tests",
  "kind": "pytest",
  "config": {
    "command": "pytest tests/",
    "timeout": 300
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project_id` | UUID | Yes | Parent project ID |
| `name` | string | Yes | Suite name |
| `kind` | string | Yes | Test framework type (e.g., "pytest", "junit", "allure") |
| `config` | object | No | Suite configuration options |

**Response Codes:**
- `201 Created` — Test suite created
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Project not found

**Response Body:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Integration Tests",
  "kind": "pytest",
  "config": {
    "command": "pytest tests/",
    "timeout": 300
  },
  "created_at": "2026-04-28T12:00:00Z"
}
```

---

### `GET /api/v1/test-suites`

List all test suites.

**Authentication:** Authenticated user

**Query Parameters:** None

**Response Codes:**
- `200 OK` — List returned successfully
- `401 Unauthorized` — Missing or invalid token

**Response Body:**
```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "project_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Integration Tests",
    "kind": "pytest",
    "config": {
      "command": "pytest tests/",
      "timeout": 300
    },
    "created_at": "2026-04-28T12:00:00Z"
  }
]
```

---

### `GET /api/v1/test-suites/{suite_id}`

Get a specific test suite by ID.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `suite_id` | UUID | Test suite identifier |

**Response Codes:**
- `200 OK` — Test suite found
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Test suite not found

**Response Body:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Integration Tests",
  "kind": "pytest",
  "config": {
    "command": "pytest tests/",
    "timeout": 300
  },
  "created_at": "2026-04-28T12:00:00Z"
}
```

---

### `PUT /api/v1/test-suites/{suite_id}`

Update a test suite.

**Authentication:** Authenticated user (role: `admin`, `qa_lead`, or `qa_engineer`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `suite_id` | UUID | Test suite identifier |

**Request Body:**
```json
{
  "name": "Updated Suite Name",
  "kind": "junit",
  "config": {
    "command": "python -m pytest",
    "timeout": 600
  }
}
```

All fields are optional. Only provided fields are updated.

**Response Codes:**
- `200 OK` — Test suite updated
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Test suite not found

**Response Body:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Updated Suite Name",
  "kind": "junit",
  "config": {
    "command": "python -m pytest",
    "timeout": 600
  },
  "created_at": "2026-04-28T12:00:00Z"
}
```

---

### `DELETE /api/v1/test-suites/{suite_id}`

Delete a test suite.

**Authentication:** Authenticated user (role: `admin` or `qa_lead`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `suite_id` | UUID | Test suite identifier |

**Response Codes:**
- `200 OK` — Test suite deleted
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Test suite not found

**Response Body:**
```json
{
  "status": "deleted"
}
```

---

## 5. Test Cases

### `POST /api/v1/test-cases`

Create a new test case.

**Authentication:** Authenticated user (role: `admin`, `qa_lead`, or `qa_engineer`)

**Request Body:**
```json
{
  "title": "User login with valid credentials",
  "source": "manual",
  "suite_id": "660e8400-e29b-41d4-a716-446655440001",
  "description": "Verify that users can log in with valid email and password",
  "code_path": "tests/test_login.py::test_valid_login",
  "requirement_id": "770e8400-e29b-41d4-a716-446655440002"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Test case title |
| `source` | string | Yes | Source of test case ("manual", "generated", "imported") |
| `suite_id` | UUID | Yes | Parent test suite ID |
| `description` | string | No | Detailed test description |
| `code_path` | string | No | Path to test code |
| `requirement_id` | UUID | No | Linked requirement ID |

**Response Codes:**
- `201 Created` — Test case created
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Test suite not found

**Response Body:**
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440003",
  "title": "User login with valid credentials",
  "suite_id": "660e8400-e29b-41d4-a716-446655440001",
  "source": "manual",
  "created_at": "2026-04-28T12:00:00Z",
  "requirement_id": "770e8400-e29b-41d4-a716-446655440002"
}
```

---

### `GET /api/v1/test-cases`

List test cases with optional filtering.

**Authentication:** Authenticated user

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `suite_id` | UUID | No | Filter by test suite |

**Response Codes:**
- `200 OK` — List returned successfully
- `401 Unauthorized` — Missing or invalid token

**Response Body:**
```json
[
  {
    "id": "880e8400-e29b-41d4-a716-446655440003",
    "title": "User login with valid credentials",
    "suite_id": "660e8400-e29b-41d4-a716-446655440001",
    "source": "manual",
    "created_at": "2026-04-28T12:00:00Z",
    "requirement_id": "770e8400-e29b-41d4-a716-446655440002"
  }
]
```

---

### `GET /api/v1/test-cases/{case_id}`

Get a specific test case by ID.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `case_id` | UUID | Test case identifier |

**Response Codes:**
- `200 OK` — Test case found
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Test case not found

**Response Body:**
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440003",
  "title": "User login with valid credentials",
  "suite_id": "660e8400-e29b-41d4-a716-446655440001",
  "source": "manual",
  "created_at": "2026-04-28T12:00:00Z",
  "requirement_id": "770e8400-e29b-41d4-a716-446655440002"
}
```

---

### `PUT /api/v1/test-cases/{case_id}`

Update a test case.

**Authentication:** Authenticated user (role: `admin`, `qa_lead`, or `qa_engineer`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `case_id` | UUID | Test case identifier |

**Request Body:**
```json
{
  "title": "Updated test case title",
  "description": "Updated description",
  "code_path": "tests/test_auth.py::test_login"
}
```

All fields are optional.

**Response Codes:**
- `200 OK` — Test case updated
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Test case not found

**Response Body:**
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440003",
  "title": "Updated test case title",
  "suite_id": "660e8400-e29b-41d4-a716-446655440001",
  "source": "manual",
  "created_at": "2026-04-28T12:00:00Z",
  "requirement_id": "770e8400-e29b-41d4-a716-446655440002"
}
```

---

### `DELETE /api/v1/test-cases/{case_id}`

Delete a test case.

**Authentication:** Authenticated user (role: `admin` or `qa_lead`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `case_id` | UUID | Test case identifier |

**Response Codes:**
- `200 OK` — Test case deleted
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Test case not found

**Response Body:**
```json
{
  "status": "deleted"
}
```

---

### `POST /api/v1/test-cases/generate`

Generate test cases from a user story using AI.

**Authentication:** Authenticated user (role: `admin`, `qa_lead`, or `qa_engineer`)

**Request Body:**
```json
{
  "suite_id": "660e8400-e29b-41d4-a716-446655440001",
  "user_story": "As a user, I want to reset my password so that I can recover access to my account when I forget my password"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `suite_id` | UUID | Yes | Target test suite ID |
| `user_story` | string | Yes | User story in natural language |

**Response Codes:**
- `201 Created` — Test case generated
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions

**Response Body:**
```json
{
  "title": "Password reset functionality",
  "preconditions": "User has valid email and is logged out",
  "steps": [
    {
      "step": "Navigate to login page",
      "expected": "Login page is displayed"
    },
    {
      "step": "Click 'Forgot password' link",
      "expected": "Password reset form is displayed"
    },
    {
      "step": "Enter registered email address",
      "expected": "Email field accepts valid email format"
    },
    {
      "step": "Click 'Send reset link' button",
      "expected": "Success message is displayed and email is sent"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Generated test case title |
| `preconditions` | string | Required preconditions |
| `steps` | array[object] | List of test steps with `step` and `expected` |

---

### `POST /api/v1/test-cases/import`

Import test cases from external formats.

**Authentication:** Authenticated user (role: `admin` or `qa_lead`)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `suite_id` | UUID | Yes | Target test suite ID |
| `format` | string | No | Format type: "allure" (default), "testrail", "testit" |

**Request Body:**
```json
{
  "content": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<allure...>\n</allure>"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Import content in specified format |

**Response Codes:**
- `201 Created` — Import successful
- `400 Bad Request` — Invalid content or format
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions

**Response Body:**
```json
{
  "imported": 15,
  "skipped": 2,
  "errors": 0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `imported` | integer | Number of test cases imported |
| `skipped` | integer | Number of test cases skipped (duplicates) |
| `errors` | integer | Number of import errors |

---

## 6. Test Runs

### `POST /api/v1/runs`

Create and start a new test run.

**Authentication:** Authenticated user (role: `admin`, `qa_lead`, or `qa_engineer`)

**Request Body:**
```json
{
  "suite_id": "660e8400-e29b-41d4-a716-446655440001",
  "commit_sha": "a1b2c3d4e5f6g7h8i9j0",
  "branch": "main",
  "triggered_by": "550e8400-e29b-41d4-a716-446655440000",
  "priority": 3,
  "environment": "dev"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `suite_id` | UUID | Yes | Test suite to run |
| `commit_sha` | string | Yes | Git commit SHA |
| `branch` | string | Yes | Git branch name |
| `triggered_by` | UUID | Yes | User ID who triggered the run |
| `priority` | integer | No | Priority (1=highest, 5=lowest, default: 3) |
| `environment` | string | No | Target environment (default: "dev") |

**Response Codes:**
- `201 Created` — Test run created and started
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Test suite not found

**Response Body:**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440004",
  "suite_id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "running",
  "commit_sha": "a1b2c3d4e5f6g7h8i9j0",
  "branch": "main",
  "started_at": "2026-04-28T12:00:00Z",
  "finished_at": null,
  "pass_count": 0,
  "fail_count": 0,
  "skipped_count": 0
}
```

---

### `GET /api/v1/runs`

List all test runs.

**Authentication:** Authenticated user

**Query Parameters:** None

**Response Codes:**
- `200 OK` — List returned successfully
- `401 Unauthorized` — Missing or invalid token

**Response Body:**
```json
[
  {
    "id": "990e8400-e29b-41d4-a716-446655440004",
    "suite_id": "660e8400-e29b-41d4-a716-446655440001",
    "status": "completed",
    "commit_sha": "a1b2c3d4e5f6g7h8i9j0",
    "branch": "main",
    "started_at": "2026-04-28T12:00:00Z",
    "finished_at": "2026-04-28T12:05:30Z",
    "pass_count": 85,
    "fail_count": 10,
    "skipped_count": 5
  }
]
```

---

### `GET /api/v1/runs/{run_id}`

Get a specific test run with pass/fail/skipped counts.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Test run identifier |

**Response Codes:**
- `200 OK` — Test run found
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Test run not found

**Response Body:**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440004",
  "suite_id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "completed",
  "commit_sha": "a1b2c3d4e5f6g7h8i9j0",
  "branch": "main",
  "started_at": "2026-04-28T12:00:00Z",
  "finished_at": "2026-04-28T12:05:30Z",
  "pass_count": 85,
  "fail_count": 10,
  "skipped_count": 5
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "pending", "running", "completed", "failed" |
| `pass_count` | integer | Number of passed tests |
| `fail_count` | integer | Number of failed tests |
| `skipped_count` | integer | Number of skipped tests |

---

### `POST /api/v1/runs/{run_id}/results`

Submit test results from worker callback.

**Authentication:** Authenticated user (worker token)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Test run identifier |

**Request Body:**
```json
{
  "results": [
    {
      "test_case_id": "880e8400-e29b-41d4-a716-446655440003",
      "status": "passed",
      "duration_ms": 1500,
      "error_message": null
    },
    {
      "test_case_id": "880e8400-e29b-41d4-a716-446655440004",
      "status": "failed",
      "duration_ms": 500,
      "error_message": "AssertionError: expected 'John' got 'Jane'"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `results` | array[object] | Yes | List of test results |
| `results[].test_case_id` | UUID | Yes | Test case identifier |
| `results[].status` | string | Yes | "passed", "failed", or "skipped" |
| `results[].duration_ms` | number | No | Execution time in milliseconds |
| `results[].error_message` | string | No | Error message if failed |

**Response Codes:**
- `200 OK` — Results submitted
- `400 Bad Request` — Invalid results format
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Test run not found

**Response Body:**
```json
{
  "status": "ok",
  "run_id": "990e8400-e29b-41d4-a716-446655440004"
}
```

---

### `GET /api/v1/runs/{run_id}/analyses`

Get AI analyses for a test run.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Test run identifier |

**Response Codes:**
- `200 OK` — Analyses returned
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Test run not found

**Response Body:**
```json
[
  {
    "id": "aa0e8400-e29b-41d4-a716-446655440005",
    "result_id": "bb0e8400-e29b-41d4-a716-446655440006",
    "category": "real_defect",
    "probability": 0.92,
    "short_cause": "Null pointer in UserService.getProfile()",
    "suggestion": "Add null check before accessing user profile",
    "llm_model": "gpt-4"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Analysis identifier |
| `result_id` | UUID | Test result this analysis belongs to |
| `category` | string | Failure category: "real_defect", "infrastructure", "flaky", "test_issue" |
| `probability` | float | Confidence score (0.0 to 1.0) |
| `short_cause` | string | Short AI-generated cause description |
| `suggestion` | string | Recommended fix |
| `llm_model` | string | LLM model used for analysis |

---

### `POST /api/v1/runs/{run_id}/rerun`

Rerun failed tests from a previous run.

**Authentication:** Authenticated user (role: `admin`, `qa_lead`, or `qa_engineer`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Original test run identifier |

**Response Codes:**
- `201 Created` — New run created
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Original run not found

**Response Body:**
```json
{
  "new_run_id": "cc0e8400-e29b-41d4-a716-446655440007",
  "rerun_count": 1,
  "status": "pending"
}
```

---

### `GET /api/v1/runs/{run_id}/diff`

Compare test results between two runs.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Base test run (source) |
| `compare_to` | UUID | Comparison target run |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `compare_to` | UUID | Yes | Run ID to compare against |

**Response Codes:**
- `200 OK` — Diff computed
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — One or both runs not found

**Response Body:**
```json
{
  "base_run_id": "990e8400-e29b-41d4-a716-446655440004",
  "compare_run_id": "cc0e8400-e29b-41d4-a716-446655440007",
  "added": [
    {
      "test_case_id": "dd0e8400-e29b-41d4-a716-446655440008",
      "title": "New test case",
      "status_before": null,
      "status_after": "passed"
    }
  ],
  "removed": [
    {
      "test_case_id": "ee0e8400-e29b-41d4-a716-446655440009",
      "title": "Deleted test case",
      "status_before": "failed",
      "status_after": null
    }
  ],
  "changed": [
    {
      "test_case_id": "ff0e8400-e29b-41d4-a716-446655440010",
      "title": "Modified test case",
      "status_before": "failed",
      "status_after": "passed"
    }
  ],
  "unchanged_count": 78,
  "summary": {
    "total_base": 100,
    "total_compare": 99,
    "added": 1,
    "removed": 1,
    "changed": 1
  }
}
```

---

### `GET /api/v1/runs/{run_id}/risk`

Get AI risk score for a test run.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Test run identifier |

**Response Codes:**
- `200 OK` — Risk score computed
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Test run not found

**Response Body:**
```json
{
  "run_id": "990e8400-e29b-41d4-a716-446655440004",
  "score": 35,
  "risk_level": "medium",
  "recommendation": "release_with_caution",
  "total_tests": 100,
  "passed_count": 85,
  "failed_count": 10,
  "skipped_count": 5,
  "factors": [
    {
      "test_case_id": "ff0e8400-e29b-41d4-a716-446655440010",
      "title": "Critical business flow test",
      "category": "real_defect",
      "weight": 3.0
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `score` | integer | Risk score (0-100) |
| `risk_level` | string | "low", "medium", "high", "critical" |
| `recommendation` | string | "release", "release_with_caution", "investigate", "hold" |
| `factors` | array[object] | Contributing risk factors with weights |

Risk score calculation:
- `real_defect` failure: weight 3.0
- `infrastructure` failure: weight 2.0
- `flaky` failure: weight 1.0
- Score = (weighted_sum / max_possible_weight) * 100, capped at 100

---

### `POST /api/v1/runs/{run_id}/report`

Generate PDF release report for a test run.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Test run identifier |

**Response Codes:**
- `200 OK` — PDF generated
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Test run not found

**Response Headers:**
- `Content-Disposition`: `attachment; filename="report-<commit_sha[:8]>.pdf"`
- `Content-Type`: `application/pdf`

**Response Body:** Binary PDF content

---

### `GET /api/v1/runs/{run_id}/export`

Export test run results.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Test run identifier |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `format` | string | No | "json" | Export format: "csv" or "json" |

**Response Codes:**
- `200 OK` — Export generated
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Test run not found

**Response for `format=csv`:**
```
test_case_id,title,status,duration_ms,error_message
880e8400-e29b-41d4-a716-446655440003,User login test,passed,1500,
990e8400-e29b-41d4-a716-446655440004,Payment test,failed,500,AssertionError
```

**Response for `format=json`:**
```json
[
  {
    "test_case_id": "880e8400-e29b-41d4-a716-446655440003",
    "title": "User login test",
    "status": "passed",
    "duration_ms": 1500,
    "error_message": null
  },
  {
    "test_case_id": "990e8400-e29b-41d4-a716-446655440004",
    "title": "Payment test",
    "status": "failed",
    "duration_ms": 500,
    "error_message": "AssertionError"
  }
]
```

---

### `POST /api/v1/runs/{run_id}/import/junit`

Import test results from JUnit XML format.

**Authentication:** Authenticated user (role: `admin` or `qa_lead`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Target test run identifier |

**Request Body:**
```json
{
  "xml_content": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<testsuite name=\"tests\" tests=\"10\" failures=\"1\">\n  <testcase name=\"test_login\" classname=\"tests.test_auth\"/>\n</testsuite>"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `xml_content` | string | Yes | JUnit XML content |

Supports both `<testsuites>` and single `<testsuite>` formats.

**Response Codes:**
- `200 OK` — Import completed
- `400 Bad Request` — Invalid XML
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Test run not found

**Response Body:**
```json
{
  "imported": 8,
  "skipped": 2,
  "errors": 0
}
```

---

### `POST /api/v1/runs/{run_id}/import/allure`

Import test results from Allure XML format.

**Authentication:** Authenticated user (role: `admin` or `qa_lead`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Target test run identifier |

**Request Body:**
```json
{
  "xml_content": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<allure...>\n</allure>"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `xml_content` | string | Yes | Allure XML content |

**Response Codes:**
- `200 OK` — Import completed
- `400 Bad Request` — Invalid XML
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Test run not found

**Response Body:**
```json
{
  "imported": 12,
  "skipped": 1,
  "errors": 0
}
```

---

### `POST /api/v1/runs/{run_id}/deploy`

Trigger deployment based on test run results.

**Authentication:** Authenticated user (role: `admin` or `qa_lead`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Test run identifier |

**Request Body:**
```json
{
  "environment": "preprod",
  "approve": true
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `environment` | string | No | "preprod" | Target environment: "preprod" or "prod" |
| `approve` | boolean | No | false | Approval flag to proceed with deployment |

**Response Codes:**
- `200 OK` — Deployment triggered
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Test run not found

**Response Body:**
```json
{
  "status": "deployment_triggered",
  "environment": "preprod",
  "run_id": "990e8400-e29b-41d4-a716-446655440004"
}
```

---

### `POST /api/v1/runs/{run_id}/attachments`

Upload attachment for a test run.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | UUID | Test run identifier |

**Request Body:**
```json
{
  "filename": "screenshot.png",
  "content_type": "image/png",
  "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `filename` | string | Yes | Attachment filename |
| `content_type` | string | No | MIME content type (default: "application/octet-stream") |
| `data` | string | Yes | Base64-encoded file content |

**Response Codes:**
- `200 OK` — Upload successful
- `400 Bad Request` — Invalid base64 data
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Test run not found

**Response Body:**
```json
{
  "status": "ok",
  "key": "runs/990e8400-e29b-41d4-a716-446655440004/screenshot.png",
  "size": 1024
}
```

---

## 7. Schedules

### `POST /api/v1/schedules`

Create a new schedule for recurring test runs.

**Authentication:** Authenticated user (role: `admin` or `qa_lead`)

**Request Body:**
```json
{
  "suite_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "Nightly integration tests",
  "cron_expression": "0 2 * * *",
  "triggered_by": "550e8400-e29b-41d4-a716-446655440000",
  "timezone": "Europe/Moscow"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `suite_id` | UUID | Yes | Test suite to schedule |
| `name` | string | Yes | Schedule name |
| `cron_expression` | string | Yes | Cron expression (5 fields) |
| `triggered_by` | UUID | Yes | User creating the schedule |
| `timezone` | string | No | Timezone (default: "UTC") |

**Response Codes:**
- `201 Created` — Schedule created
- `400 Bad Request` — Invalid cron expression
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Test suite not found

**Response Body:**
```json
{
  "id": "110e8400-e29b-41d4-a716-446655440011",
  "suite_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "Nightly integration tests",
  "cron_expression": "0 2 * * *",
  "timezone": "Europe/Moscow",
  "is_active": true,
  "created_at": "2026-04-28T12:00:00Z"
}
```

---

### `GET /api/v1/schedules`

List all schedules with optional filtering.

**Authentication:** Authenticated user

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `suite_id` | UUID | No | Filter by test suite |

**Response Codes:**
- `200 OK` — List returned
- `401 Unauthorized` — Missing or invalid token

**Response Body:**
```json
[
  {
    "id": "110e8400-e29b-41d4-a716-446655440011",
    "suite_id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "Nightly integration tests",
    "cron_expression": "0 2 * * *",
    "timezone": "Europe/Moscow",
    "is_active": true,
    "created_at": "2026-04-28T12:00:00Z"
  }
]
```

---

### `GET /api/v1/schedules/{schedule_id}`

Get a specific schedule by ID.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `schedule_id` | UUID | Schedule identifier |

**Response Codes:**
- `200 OK` — Schedule found
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Schedule not found

**Response Body:**
```json
{
  "id": "110e8400-e29b-41d4-a716-446655440011",
  "suite_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "Nightly integration tests",
  "cron_expression": "0 2 * * *",
  "timezone": "Europe/Moscow",
  "is_active": true,
  "created_at": "2026-04-28T12:00:00Z"
}
```

---

### `PUT /api/v1/schedules/{schedule_id}`

Update a schedule.

**Authentication:** Authenticated user (role: `admin` or `qa_lead`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `schedule_id` | UUID | Schedule identifier |

**Request Body:**
```json
{
  "name": "Updated schedule name",
  "cron_expression": "0 3 * * *",
  "timezone": "UTC",
  "is_active": false
}
```

All fields are optional.

**Response Codes:**
- `200 OK` — Schedule updated
- `400 Bad Request` — Invalid cron expression
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Schedule not found

**Response Body:**
```json
{
  "status": "updated"
}
```

---

### `DELETE /api/v1/schedules/{schedule_id}`

Delete a schedule.

**Authentication:** Authenticated user (role: `admin` or `qa_lead`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `schedule_id` | UUID | Schedule identifier |

**Response Codes:**
- `200 OK` — Schedule deleted
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Schedule not found

**Response Body:**
```json
{
  "status": "deleted"
}
```

---

## 8. Analytics

### `GET /api/v1/analytics/dora`

Get DORA metrics for software delivery performance.

**Authentication:** Authenticated user

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_id` | UUID | No | null | Filter by project |
| `days` | integer | No | 30 | Lookback period in days |

**Response Codes:**
- `200 OK` — Metrics computed
- `401 Unauthorized` — Missing or invalid token

**Response Body:**
```json
{
  "lead_time_hours": 4.5,
  "deployment_frequency_per_day": 2.3,
  "change_failure_rate_pct": 12.5,
  "mttr_hours": 1.2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lead_time_hours` | float | Time from commit to production deployment |
| `deployment_frequency_per_day` | float | Number of deployments per day |
| `change_failure_rate_pct` | float | Percentage of deployments causing failures |
| `mttr_hours` | float | Mean time to recover from failures |

---

### `GET /api/v1/analytics/flaky`

Detect flaky tests based on result history.

**Authentication:** Authenticated user

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_id` | UUID | No | null | Filter by project |
| `suite_id` | UUID | No | null | Filter by test suite |
| `threshold` | integer | No | 3 | Minimum status transitions to flag as flaky |
| `lookback` | integer | No | 30 | Number of days to analyze |

**Response Codes:**
- `200 OK` — Flaky tests detected
- `401 Unauthorized` — Missing or invalid token

**Response Body:**
```json
{
  "flaky_tests": [
    {
      "test_case_id": "120e8400-e29b-41d4-a716-446655440012",
      "title": "Payment gateway test",
      "transitions": 5,
      "total_runs": 30,
      "flaky_score": 0.17,
      "last_statuses": ["passed", "failed", "passed", "failed", "passed"]
    }
  ],
  "total_count": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `flaky_tests[].test_case_id` | UUID | Test case identifier |
| `flaky_tests[].title` | string | Test case title |
| `flaky_tests[].transitions` | integer | Number of status changes |
| `flaky_tests[].total_runs` | integer | Total runs in lookback period |
| `flaky_tests[].flaky_score` | float | Ratio of transitions to total runs |
| `flaky_tests[].last_statuses` | array[string] | Recent test statuses |

---

## 9. Defects

### `POST /api/v1/defects`

Create a new defect record.

**Authentication:** Authenticated user

**Request Body:**
```json
{
  "title": "Login button not responding on mobile",
  "description": "When clicking the login button on mobile devices, nothing happens. The button works on desktop.",
  "severity": 2,
  "jira_key": "AST-1234"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Defect title |
| `description` | string | Yes | Detailed description |
| `severity` | integer | Yes | Severity level (1=critical, 2=major, 3=minor, 4=cosmetic) |
| `jira_key` | string | No | Associated Jira issue key |

If `jira_key` is not provided, the system attempts to auto-create a Jira issue.

**Response Codes:**
- `201 Created` — Defect created
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token

**Response Body:**
```json
{
  "id": "130e8400-e29b-41d4-a716-446655440013",
  "title": "Login button not responding on mobile",
  "severity": 2,
  "status": "open",
  "created_at": "2026-04-28T12:00:00Z",
  "jira_key": "AST-1234"
}
```

---

### `GET /api/v1/defects`

List all defect records.

**Authentication:** Authenticated user

**Query Parameters:** None

**Response Codes:**
- `200 OK` — List returned
- `401 Unauthorized` — Missing or invalid token

**Response Body:**
```json
[
  {
    "id": "130e8400-e29b-41d4-a716-446655440013",
    "title": "Login button not responding on mobile",
    "severity": 2,
    "status": "open",
    "created_at": "2026-04-28T12:00:00Z",
    "jira_key": "AST-1234"
  }
]
```

---

### `GET /api/v1/defects/{defect_id}`

Get a specific defect by ID.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `defect_id` | UUID | Defect identifier |

**Response Codes:**
- `200 OK` — Defect found
- `401 Unauthorized` — Missing or invalid token
- `404 Not Found` — Defect not found

**Response Body:**
```json
{
  "id": "130e8400-e29b-41d4-a716-446655440013",
  "title": "Login button not responding on mobile",
  "severity": 2,
  "status": "open",
  "created_at": "2026-04-28T12:00:00Z",
  "jira_key": "AST-1234"
}
```

---

### `PUT /api/v1/defects/{defect_id}`

Update a defect record.

**Authentication:** Authenticated user

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `defect_id` | UUID | Defect identifier |

**Request Body:**
```json
{
  "title": "Updated defect title",
  "description": "Updated description",
  "severity": 1,
  "status": "in_progress",
  "jira_key": "AST-5678"
}
```

All fields are optional.

**Response Codes:**
- `200 OK` — Defect updated
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — Defect not found

**Response Body:**
```json
{
  "id": "130e8400-e29b-41d4-a716-446655440013",
  "title": "Updated defect title",
  "severity": 1,
  "status": "in_progress",
  "created_at": "2026-04-28T12:00:00Z",
  "jira_key": "AST-5678"
}
```

---

## 10. Search

### `GET /api/v1/search`

Full-text search across test results.

**Authentication:** None (excluded from auth)

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query string |
| `status` | string | No | Filter by status ("passed", "failed", "skipped") |
| `run_id` | string | No | Filter by specific run ID |

**Response Codes:**
- `200 OK` — Search results returned
- `400 Bad Request` — Missing query parameter

**Response Body:**
```json
[
  {
    "test_case_id": "880e8400-e29b-41d4-a716-446655440003",
    "run_id": "990e8400-e29b-41d4-a716-446655440004",
    "title": "User login test",
    "status": "failed",
    "error_message": "AssertionError: expected 'John' got 'Jane'",
    "matched_in": "error_message"
  }
]
```

---

## 11. Admin

### `GET /api/v1/admin/users`

List all users.

**Authentication:** Authenticated user (role: `admin`)

**Response Codes:**
- `200 OK` — User list returned
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions

**Response Body:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "admin@example.com",
    "full_name": "Admin User",
    "role_id": 1,
    "is_active": true,
    "created_at": "2026-04-01T10:00:00Z"
  }
]
```

---

### `POST /api/v1/admin/users`

Create a new user.

**Authentication:** Authenticated user (role: `admin`)

**Request Body:**
```json
{
  "email": "newuser@example.com",
  "full_name": "New User",
  "role_id": 3,
  "is_active": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | User email address |
| `full_name` | string | Yes | User full name |
| `role_id` | integer | Yes | Role ID (1=admin, 2=qa_lead, 3=qa_engineer, 4=viewer) |
| `is_active` | boolean | No | Active status (default: true) |

**Response Codes:**
- `201 Created` — User created
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions

**Response Body:**
```json
{
  "id": "140e8400-e29b-41d4-a716-446655440014",
  "email": "newuser@example.com",
  "full_name": "New User",
  "role_id": 3,
  "is_active": true,
  "created_at": "2026-04-28T12:00:00Z"
}
```

---

### `PUT /api/v1/admin/users/{user_id}`

Update a user.

**Authentication:** Authenticated user (role: `admin`)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | UUID | User identifier |

**Request Body:**
```json
{
  "full_name": "Updated Name",
  "role_id": 2,
  "is_active": false
}
```

All fields are optional.

**Response Codes:**
- `200 OK` — User updated
- `400 Bad Request` — Invalid request body
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions
- `404 Not Found` — User not found

**Response Body:**
```json
{
  "id": "140e8400-e29b-41d4-a716-446655440014",
  "email": "newuser@example.com",
  "full_name": "Updated Name",
  "role_id": 2,
  "is_active": false,
  "created_at": "2026-04-28T12:00:00Z"
}
```

---

### `GET /api/v1/admin/settings`

Get LLM settings configuration.

**Authentication:** Authenticated user (role: `admin`)

**Response Codes:**
- `200 OK` — Settings returned
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions

**Response Body:**
```json
{
  "llm_model_name": "gpt-4",
  "llm_temperature": 0.7,
  "llm_max_tokens": 2000,
  "llm_request_timeout_seconds": 120
}
```

---

### `PUT /api/v1/admin/settings`

Update LLM settings.

**Authentication:** Authenticated user (role: `admin`)

**Request Body:**
```json
{
  "llm_model_name": "gpt-4-turbo",
  "llm_temperature": 0.5,
  "llm_max_tokens": 4000,
  "llm_request_timeout_seconds": 180
}
```

All fields are optional.

**Response Codes:**
- `200 OK` — Settings updated
- `400 Bad Request` — Invalid values
- `401 Unauthorized` — Missing or invalid token
- `403 Forbidden` — Insufficient permissions

**Response Body:**
```json
{
  "llm_model_name": "gpt-4-turbo",
  "llm_temperature": 0.5,
  "llm_max_tokens": 4000,
  "llm_request_timeout_seconds": 180
}
```

---

## 12. Webhooks

### `POST /api/v1/webhooks/gitlab`

Handle GitLab CI pipeline webhooks.

**Authentication:** None (webhook signature verification recommended)

**Request Body:**
```json
{
  "object_kind": "pipeline",
  "object_attributes": {
    "id": 12345,
    "status": "success",
    "ref": "main",
    "sha": "abc123def456"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `object_kind` | string | Event type (e.g., "pipeline", "merge_request") |
| `object_attributes.status` | string | Pipeline status ("success", "failed", "running") |
| `object_attributes.ref` | string | Git branch or tag reference |
| `object_attributes.sha` | string | Commit SHA |

**Response Codes:**
- `200 OK` — Webhook processed
- `400 Bad Request` — Invalid payload

**Response Body:**
```json
{
  "status": "triggered",
  "ref": "main",
  "sha": "abc123def456"
}
```

---

### `POST /api/v1/webhooks/jira`

Handle Jira issue status synchronization webhooks.

**Authentication:** None

**Request Body:**
```json
{
  "issue": {
    "key": "AST-1234",
    "fields": {
      "status": {
        "name": "Done"
      },
      "priority": {
        "name": "High"
      }
    }
  },
  "changelog": {
    "items": [
      {
        "field": "status",
        "fromString": "In Progress",
        "toString": "Done"
      }
    ]
  }
}
```

**Response Codes:**
- `200 OK` — Webhook processed
- `400 Bad Request` — Invalid payload
- `500 Internal Server Error` — Processing error

**Response Body:**
```json
{
  "status": "synced",
  "issue_key": "AST-1234",
  "changes": ["status"]
}
```

---

## 13. Infrastructure

### `GET /api/v1/health`

Health check endpoint.

**Authentication:** None

**Response Codes:**
- `200 OK` — Service is healthy

**Response Body:**
```json
{
  "status": "ok",
  "service": "astra-qa-backend"
}
```

---

### `GET /metrics`

Prometheus metrics endpoint.

**Authentication:** None

**Response Codes:**
- `200 OK` — Metrics in Prometheus text format

**Response Body:**
```
# HELP astra_test_runs_total Total number of test runs
# TYPE astra_test_runs_total counter
astra_test_runs_total 150

# HELP astra_test_runs_failed_total Total number of failed test runs
# TYPE astra_test_runs_failed_total counter
astra_test_runs_failed_total 25

# HELP astra_test_results_total Total number of test results by status
# TYPE astra_test_results_total counter
astra_test_results_total{status="passed"} 1200
astra_test_results_total{status="failed"} 150
astra_test_results_total{status="skipped"} 50

# HELP astra_test_run_duration_seconds Average duration of test runs in seconds
# TYPE astra_test_run_duration_seconds gauge
astra_test_run_duration_seconds 180.500
```

---

### `WS /api/v1/ws/runs/{run_id}`

WebSocket endpoint for real-time test run updates.

**Authentication:** None (or token in query parameter)

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `run_id` | string | Test run identifier |

**WebSocket Messages:**

Server sends JSON messages for each run event:

```json
{
  "event": "result_received",
  "run_id": "990e8400-e29b-41d4-a716-446655440004",
  "data": {
    "test_case_id": "880e8400-e29b-41d4-a716-446655440003",
    "status": "passed",
    "duration_ms": 1500
  }
}
```

| Event Type | Description |
|------------|-------------|
| `run_started` | Test run has started |
| `result_received` | A test result was received |
| `run_completed` | Test run has completed |
| `run_failed` | Test run failed |

**Connection Example:**
```javascript
const ws = new WebSocket('wss://astra.example.com/api/v1/ws/runs/990e8400-e29b-41d4-a716-446655440004');
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(message.event, message.data);
};
```

---

## Appendix: Common Error Responses

### 400 Bad Request
```json
{
  "status": 400,
  "message": "Invalid request body",
  "details": {
    "field": "suite_id",
    "error": "Invalid UUID format"
  }
}
```

### 401 Unauthorized
```json
{
  "status": 401,
  "message": "Missing Authorization header",
  "details": {}
}
```

### 403 Forbidden
```json
{
  "status": 403,
  "message": "Requires one of roles: admin",
  "details": {
    "required_roles": ["admin"]
  }
}
```

### 404 Not Found
```json
{
  "status": 404,
  "message": "Test run 990e8400-e29b-41d4-a716-446655440004 not found",
  "details": {}
}
```

### 500 Internal Server Error
```json
{
  "status": 500,
  "message": "An unexpected error occurred",
  "details": {
    "exception": "DatabaseConnectionError"
  }
}
```