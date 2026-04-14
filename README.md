# Advanced Dynamic Survey Platform

Enterprise-grade survey backend built with Django + DRF. Supports dynamic conditional logic, cross-section field dependencies, versioned surveys, encrypted sensitive fields, RBAC, audit logging, async exports, and analytics.

> The full implementation plan that guided this build — structure, data models, rule engine, validation layers, phased delivery — is available at [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md). Included as reference material; helpful for understanding the design rationale behind the codebase.

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- That's it. No local Python or PostgreSQL needed.

### Run the project

```bash
docker compose up --build
```

This starts 5 services:
- **db** — PostgreSQL 16
- **redis** — Redis 7
- **web** — Django dev server on port `8000` (runs migrations automatically)
- **celery_worker** — background task worker
- **celery_beat** — periodic task scheduler

Once `web` reports healthy, the API is available at:
- **API root:** http://localhost:8000/api/v1/
- **Swagger docs:** http://localhost:8000/api/docs/
- **Django admin:** http://localhost:8000/admin/

### Create an admin user

```bash
docker compose exec web python manage.py createsuperuser
```

Then create an `Organization` and a `Membership` with role `admin` through the Django admin, or via the API.

---

## Architecture

### Apps

| App | Responsibility |
|-----|----------------|
| `common` | Shared base models (`UUIDModel`, `TimeStampedModel`), pagination |
| `accounts` | Users, Organizations, Memberships, JWT auth, RBAC permissions |
| `surveys` | Survey/Section/Field builder, VisibilityRule, FieldDependency, RuleEngine, publish workflow |
| `responses` | Submissions, Answers, 3-level validation, encryption, resume tokens |
| `analytics` | Aggregations, async CSV/XLSX/PDF exports, Celery tasks |
| `audit` | AuditLog model, middleware, service-layer logging |

### Layering inside each app

```
models.py           — data definitions
serializers/        — input/output shaping
views/              — thin HTTP handlers
services/           — write-side business logic (publish, submit, encrypt)
selectors/          — read-side query logic (analytics aggregations)
validators/         — 3-level validation (static, logic, integrity)
```

Business logic lives in `services/` and `selectors/` — views stay thin.

---

## Key Design Decisions

### 1. Survey versioning via snapshots
Publishing a survey freezes its full structure (sections, fields, options, rules, dependencies) into a JSON snapshot on a `SurveyVersion` row. Submissions always reference the version they started on. Draft edits never break active respondents.

### 2. Typed answer columns (not single JSONField)
`Answer` has typed columns — `value_text`, `value_number`, `value_date`, `value_datetime`, `value_boolean`, `value_json`, `value_encrypted`. Only one is populated per answer. This lets analytics queries use native B-tree indexes (`AVG(value_number)`, `COUNT(*) WHERE value_text = 'X'`) without JSONB GIN overhead.

### 3. Conditional logic in dedicated tables
`VisibilityRule` + `VisibilityCondition` + `FieldDependency` are real relational tables with FK integrity — not JSON blobs. Benefits:
- Cascade deletes when a source field is removed
- "Find all rules that depend on field X" is a simple query
- Django admin can display rules as inlines

### 4. Rule engine works on both live models and snapshot dicts
`RuleEngine` and `DependencyResolver` transparently accept either model instances (for builder UI preview) or dicts (for validating against a frozen snapshot).

### 5. 3-level validation
- **Static** (`static_validator.py`) — type checks, required, min/max, regex, option membership
- **Logic** (`logic_validator.py`) — visibility, `required_if`, filtered options
- **Integrity** (`integrity_validator.py`) — orchestrates both; checks all visible required fields answered; strips answers for hidden fields on submit

### 6. Encryption for sensitive fields
Fields marked `is_sensitive=True` are stored encrypted via Fernet (`cryptography` library). Plaintext never hits `value_text` — it's replaced with `"[ENCRYPTED]"`. Only Admin role sees the decrypted value; Analyst/DataViewer see `"[REDACTED]"`.

### 7. Audit logging from the service layer
Audit entries are emitted by service functions (`publish_survey`, `submit_response`, etc.) — not by model signals. This gives precise control over what gets logged and with what context (IP, UA, changes).

---

## Data Model & Relationships

### Entity relationships

```
Organization ──< Membership >── User
     │
     └──< Survey ──< SurveyVersion (snapshot JSON)
              │
              ├──< SurveySection ──< SurveyField ──< FieldOption
              │                           │
              │                           └──< VisibilityCondition.source_field
              │
              ├──< VisibilityRule ──< VisibilityCondition
              │         │                   │
              │         └── target_id ──────┴──> points to Section OR Field
              │
              ├──< FieldDependency (source_field ──> target_field, cross-section)
              │
              └──< SurveySubmission ──< Answer ──> SurveyField
                          │
                          └── survey_version (FK to frozen snapshot)
```

### Model cheat sheet

| Model | Purpose | Key fields |
|-------|---------|------------|
| `Survey` | Top-level survey container | `status` (draft/published/archived), `organization` |
| `SurveyVersion` | Frozen JSON snapshot created on publish | `version_number`, `snapshot` |
| `SurveySection` | Ordered group of fields | `order`, unique per survey |
| `SurveyField` | A question | `key`, `field_type`, `required`, `is_sensitive`, `validation_rules` |
| `FieldOption` | Choice for dropdown/radio/checkbox | `value`, `label`, `order` |
| `VisibilityRule` | Show/hide a section or a field | `target_type`, `target_id`, `logical_operator` (AND/OR) |
| `VisibilityCondition` | One clause inside a rule | `source_field`, `operator`, `expected_value` |
| `FieldDependency` | Cross-section link between two fields | `source_field`, `target_field`, `dependency_type`, `config` |
| `SurveySubmission` | A respondent's attempt | `status`, `resume_token`, `survey_version` |
| `Answer` | One answer in a submission | Typed columns (`value_text`, `value_number`, …), `value_encrypted` |

### Two relationship systems, explained

The platform separates **structural ordering** (Section → Field) from **logical relationships** (Rules + Dependencies). Both are independent concerns and can be exercised separately.

**1. Structural ordering** — `SurveySection.order` and `SurveyField.order` define how the form is displayed. These are unique-together with their parent, so reordering is a dedicated operation.

**2. Visibility rules** — attach to a *target* (a section or field) and reference any number of *source fields* through conditions. `logical_operator=AND` means all conditions must pass; `OR` means any. Multiple rules on the same target are OR'd together (visible if *any* rule passes).

**3. Field dependencies** — directional links (`source_field → target_field`) that can cross sections. Four types, each with its own `config` shape:

| Type | What it does | `config` shape |
|------|--------------|----------------|
| `options_filter` | Filter `target_field.options` based on `source_field` answer | `{"mapping": {"source_val": ["opt1", "opt2"]}, "default": [...]}` |
| `visibility` | Show/hide target based on source answer | `{"condition": {"operator": "eq", "value": "yes"}}` |
| `required_if` | Make target required based on source answer | `{"condition": {"operator": "eq", "value": "yes"}}` |
| `value_constraint` | Constrain target's value range | `{"min_field": "<uuid>", "max_field": "<uuid>"}` |

---

## End-to-end example

This walkthrough exercises **sections, fields, options, a multi-condition AND rule, a cross-section `options_filter` dependency, and a `required_if` dependency**. Every step is a single HTTP call — paste into Swagger at `/api/docs/` or use `curl` with a JWT from `/auth/login/`.

**Scenario** — a job application survey:
- **Section 1: "About You"** — asks `employment_status` (dropdown) and `years_experience` (number).
- **Section 2: "Role"** — asks `department` (dropdown) and `role_level` (dropdown).
  - `role_level` options are **filtered** based on `department` (cross-section `options_filter`).
  - `role_level` is **required only if** `employment_status == "employed"` (cross-section `required_if`).
- **Section 3: "References"** — shown only if `years_experience >= 3` AND `employment_status == "employed"` (AND rule with two conditions).

### Step 1 — Create the survey

```http
POST /api/v1/surveys/
{"title": "Job Application", "description": "Demo survey"}
```

Save the returned `id` as `SURVEY_ID`.

### Step 2 — Create 3 sections

```http
POST /api/v1/surveys/{SURVEY_ID}/sections/
{"title": "About You", "order": 0}          → SECTION_ABOUT

POST /api/v1/surveys/{SURVEY_ID}/sections/
{"title": "Role", "order": 1}               → SECTION_ROLE

POST /api/v1/surveys/{SURVEY_ID}/sections/
{"title": "References", "order": 2}         → SECTION_REFS
```

### Step 3 — Create fields (with inline options where applicable)

```http
POST /api/v1/sections/{SECTION_ABOUT}/fields/
{
  "key": "employment_status", "label": "Employment status",
  "field_type": "dropdown", "required": true, "order": 0,
  "options": [
    {"label": "Employed",  "value": "employed",  "order": 0},
    {"label": "Student",   "value": "student",   "order": 1},
    {"label": "Unemployed","value": "unemployed","order": 2}
  ]
}                                           → FIELD_EMP

POST /api/v1/sections/{SECTION_ABOUT}/fields/
{"key": "years_experience", "label": "Years of experience",
 "field_type": "number", "required": true, "order": 1,
 "validation_rules": {"min_value": 0, "max_value": 50}}
                                            → FIELD_YEARS

POST /api/v1/sections/{SECTION_ROLE}/fields/
{
  "key": "department", "label": "Department",
  "field_type": "dropdown", "required": true, "order": 0,
  "options": [
    {"label": "Engineering", "value": "eng", "order": 0},
    {"label": "Sales",       "value": "sales", "order": 1}
  ]
}                                           → FIELD_DEPT

POST /api/v1/sections/{SECTION_ROLE}/fields/
{
  "key": "role_level", "label": "Role level",
  "field_type": "dropdown", "required": false, "order": 1,
  "options": [
    {"label": "Junior Engineer", "value": "eng_junior", "order": 0},
    {"label": "Senior Engineer", "value": "eng_senior", "order": 1},
    {"label": "Account Executive", "value": "sales_ae", "order": 2},
    {"label": "Sales Manager", "value": "sales_mgr", "order": 3}
  ]
}                                           → FIELD_ROLE

POST /api/v1/sections/{SECTION_REFS}/fields/
{"key": "reference_name", "label": "Reference name",
 "field_type": "text", "required": true, "order": 0}
                                            → FIELD_REF
```

### Step 4 — Visibility rule (AND of two conditions) on Section 3

Hide the References section unless the applicant is employed **and** has ≥ 3 years experience.

```http
POST /api/v1/surveys/{SURVEY_ID}/rules/
{
  "target_type": "section",
  "target_id": "{SECTION_REFS}",
  "logical_operator": "AND",
  "conditions": [
    {"source_field": "{FIELD_EMP}",   "operator": "eq",  "expected_value": "employed"},
    {"source_field": "{FIELD_YEARS}", "operator": "gte", "expected_value": 3}
  ]
}
```

### Step 5 — Cross-section dependency: `options_filter`

`role_level` options change based on `department`.

```http
POST /api/v1/surveys/{SURVEY_ID}/dependencies/
{
  "source_field": "{FIELD_DEPT}",
  "target_field": "{FIELD_ROLE}",
  "dependency_type": "options_filter",
  "config": {
    "mapping": {
      "eng":   ["eng_junior", "eng_senior"],
      "sales": ["sales_ae", "sales_mgr"]
    },
    "default": []
  }
}
```

### Step 6 — Cross-section dependency: `required_if`

`role_level` becomes required only when the applicant is employed.

```http
POST /api/v1/surveys/{SURVEY_ID}/dependencies/
{
  "source_field": "{FIELD_EMP}",
  "target_field": "{FIELD_ROLE}",
  "dependency_type": "required_if",
  "config": {"condition": {"operator": "eq", "value": "employed"}}
}
```

### Step 7 — Publish and submit

```http
POST /api/v1/surveys/{SURVEY_ID}/publish/
POST /api/v1/public/surveys/{SURVEY_ID}/start/     → SUBMISSION_ID, resume_token
```

**Case A — expect References section shown, role_level required, filtered to engineering options:**

```http
POST /api/v1/public/responses/{SUBMISSION_ID}/answers/
[
  {"field_id": "{FIELD_EMP}",   "value": "employed"},
  {"field_id": "{FIELD_YEARS}", "value": 5},
  {"field_id": "{FIELD_DEPT}",  "value": "eng"},
  {"field_id": "{FIELD_ROLE}",  "value": "eng_senior"},
  {"field_id": "{FIELD_REF}",   "value": "Jane Doe"}
]
POST /api/v1/public/responses/{SUBMISSION_ID}/submit/   → 200 submitted
```

**Case B — expect References hidden, role_level not required, submitting "sales_mgr" under "eng" department rejected:**

Start a new submission, then:

```http
POST /api/v1/public/responses/{SUBMISSION_ID}/answers/
[
  {"field_id": "{FIELD_EMP}",   "value": "student"},
  {"field_id": "{FIELD_YEARS}", "value": 1},
  {"field_id": "{FIELD_DEPT}",  "value": "eng"},
  {"field_id": "{FIELD_ROLE}",  "value": "sales_mgr"}   ← invalid option under eng
]
POST /api/v1/public/responses/{SUBMISSION_ID}/submit/
  → 400 with errors[role_level]: option not in filtered list
```

**Case C — expect integrity validator to strip hidden answers:**

Answer the References field while employment_status is "student" (which hides the section). On submit, the Answer row for `FIELD_REF` is deleted because the integrity validator removes answers for hidden fields.

### What this exercises

| Step | Feature under test |
|------|-------------------|
| 4 | `VisibilityRule` with AND logical_operator, two `VisibilityCondition` rows targeting a section |
| 5 | `FieldDependency` of type `options_filter` spanning sections 1→2 |
| 6 | `FieldDependency` of type `required_if` spanning sections 1→2 |
| 7 (A) | Rule engine evaluates AND, dependency resolver filters options, required_if promotes the field, all 3 validation levels pass |
| 7 (B) | Static validator rejects option not in filtered set (logic validator cooperating with dependency resolver) |
| 7 (C) | Integrity validator strips answers to hidden fields on submit |

---

## RBAC Matrix

| Capability | Admin | Analyst | Data Viewer |
|-----------|:-----:|:-------:|:-----------:|
| Create/edit/publish surveys | ✓ | | |
| Manage rules & dependencies | ✓ | | |
| View survey definitions | ✓ | ✓ | |
| View individual submissions | ✓ | ✓ | |
| View aggregated analytics | ✓ | ✓ | ✓ |
| Request exports | ✓ | ✓ | |
| Decrypt sensitive fields | ✓ | | |
| View audit logs | ✓ | | |
| Manage users/memberships | ✓ | | |

Implemented via DRF permission classes (`IsAdmin`, `IsAnalystOrAbove`, `IsDataViewerOrAbove`) plus queryset filtering by `organization`. Multi-tenant: one user can hold different roles in different orgs — the `X-Organization-Id` header selects context.

---

## API Overview

All endpoints under `/api/v1/`. Full interactive docs at `/api/docs/`, and a ready-to-import Postman collection is available at [`postman_collection.json`](postman_collection.json) — set the `baseUrl` variable to `http://localhost:8000/api/v1` and log in via the `Auth → Login` request; the returned `access` token is captured automatically for subsequent calls.

### Auth
- `POST /auth/login/` — obtain JWT
- `POST /auth/refresh/` — refresh JWT

### Survey builder (Admin)
- `GET/POST /surveys/`
- `GET/PATCH/DELETE /surveys/{id}/`
- `POST /surveys/{id}/publish/` — freezes snapshot, transitions to published
- `POST /surveys/{id}/archive/`
- `POST /surveys/{id}/duplicate/`
- `GET/POST /surveys/{sid}/sections/` — sections
- `GET/POST /sections/{sid}/fields/` — fields
- `GET/POST /fields/{fid}/options/` — choice options
- `GET/POST /surveys/{sid}/rules/` — visibility rules
- `GET/POST /surveys/{sid}/dependencies/` — field dependencies

### Respondent-facing (public)
- `GET /public/surveys/{id}/` — get published survey
- `POST /public/surveys/{id}/start/` — start submission, returns `resume_token`
- `POST /public/responses/{id}/answers/` — auto-save (anonymous uses `X-Resume-Token` header)
- `POST /public/responses/{id}/submit/` — final submit with full validation
- `GET /public/responses/resume/{token}/` — resume by token

### Analytics (Analyst+)
- `GET /surveys/{id}/analytics/summary/` — totals, completion rate, avg time (cached 5 min)
- `GET /surveys/{id}/analytics/fields/{fid}/` — per-field breakdown
- `POST /surveys/{id}/exports/` — request async CSV/XLSX/PDF
- `GET /exports/{id}/` — check status, download

### Invitations (Admin)
- `POST /surveys/{id}/invitations/` — queue bulk email invitations (async Celery task)
- `GET /surveys/{id}/invitations/list/` — list invitations and their status (Analyst+)

### Audit (Admin)
- `GET /audit-logs/` — filterable by action, entity_type, entity_id, actor

---

## Async & Caching

### Celery tasks
- `generate_export` — builds CSV from submissions (retries up to 3x)
- `send_invitation_batch` — sends bulk email invitations in chunks of 50 (retries up to 3x)
- `cleanup_stale_drafts` — nightly cleanup of abandoned drafts > 30 days old

### Redis cache
Keys tracked in [`apps/common/cache.py`](apps/common/cache.py):

| Key | TTL | Invalidated on |
|-----|-----|----------------|
| `public_survey:{id}` | 1 hour | `publish_survey`, `archive_survey`, `submit_response` |
| `analytics_summary:{id}` | 5 minutes | `publish_survey`, `archive_survey`, `submit_response` |

Redis also serves as the Celery broker + result backend.

---

## Testing

167 tests, all passing. Coverage spans unit + integration + RBAC.

```bash
# From inside the web container (uses container DB):
docker compose exec web pytest

# From host (requires containers running; points pytest at exposed DB port):
DATABASE_URL=postgres://survey_user:survey_pass@localhost:5432/survey_platform \
  pytest
```

### Load testing

A Locust scenario lives at [`tests/load/locustfile.py`](tests/load/locustfile.py). It simulates three traffic profiles — `PublicRespondent` (anonymous submission flow), `AdminOperator` (dashboard), `AnalystViewer` (analytics polling).

```bash
# Point it at a published survey:
SURVEY_ID=<uuid> ADMIN_USERNAME=admin ADMIN_PASSWORD=admin \
  locust -f tests/load/locustfile.py --host http://localhost:8000
```

Then open http://localhost:8089 to configure users/spawn rate.

The scenario parses the published survey's visibility rules and dependencies at startup, so dummy submissions respect them — no spurious 400s from hidden fields or filtered options.

#### Sample run

Local Docker (`runserver`, Postgres with `max_connections=500`), 100 users, spawn rate 10, ~40s steady state against the Job Application sample survey:

| Metric | Value |
|---|---|
| Total requests | 4,242 |
| Aggregate throughput | 111.8 req/s |
| Failure rate | **0.00%** |
| p50 latency | 130 ms |
| p95 latency | 2,200 ms |
| p99 latency | 2,700 ms |

| Endpoint | req/s | p50 | p95 |
|---|---|---|---|
| `GET /public/surveys/[id]/` (cached) | 39.8 | 83 ms | 890 ms |
| `POST /public/surveys/[id]/start/` | 19.9 | 83 ms | 930 ms |
| `POST /public/responses/[id]/answers/` | 18.6 | 620 ms | 2,700 ms |
| `POST /public/responses/[id]/submit/` | 17.1 | 300 ms | 2,500 ms |
| `GET /surveys/[id]/analytics/summary/` (cached) | 3.5 | 150 ms | 1,600 ms |

Exercises the full stack end-to-end under concurrency: JWT auth, rule engine + dependency resolver on every submission, 3-level validation, Redis cache on the hot read endpoints, and Postgres writes on the submission path — zero failures across 4.2k requests. Tail latency is dominated by Django's dev `runserver` (single-process threaded); a production WSGI server (gunicorn, uvicorn) would flatten the upper percentiles significantly.

### Test layout

| File | Focus |
|------|-------|
| `apps/surveys/tests/test_rule_engine.py` | All 13 operators, AND/OR logic, visibility resolution |
| `apps/surveys/tests/test_dependency_resolver.py` | All 4 dependency types, merging, edge cases |
| `apps/surveys/tests/test_survey_integration.py` | Survey CRUD, publish, archive, duplicate |
| `apps/responses/tests/test_static_validator.py` | Type checks, validation rules, options |
| `apps/responses/tests/test_logic_validator.py` | Hidden fields, `required_if`, filtered options |
| `apps/responses/tests/test_integrity_validator.py` | Full 3-level orchestration |
| `apps/responses/tests/test_encryption.py` | Fernet roundtrip, memoryview handling, missing key |
| `apps/responses/tests/test_submission_integration.py` | Full lifecycle: start → save → resume → submit |
| `apps/accounts/tests/test_permissions.py` | RBAC matrix, org isolation, unauth access |
| `apps/audit/tests/test_audit.py` | Audit entries, filtering |
| `apps/analytics/tests/test_analytics.py` | Aggregations, per-field stats |

---

## Project Structure

```
Nisfak/
├── config/                 Django settings, URLs, Celery
├── apps/
│   ├── common/             Base models, pagination
│   ├── accounts/           Users, Orgs, Membership, JWT, RBAC
│   ├── surveys/            Builder + conditional logic engine
│   │   ├── services/       publish_survey, rule_engine, dependency_resolver
│   │   └── serializers/, views/    (split by resource)
│   ├── responses/          Submissions + 3-level validation + encryption
│   │   ├── services/       submission_service, encryption
│   │   └── validators/     static, logic, integrity
│   ├── analytics/          Summaries + async exports (Celery)
│   └── audit/              AuditLog, middleware, service
├── docker/django/          Dockerfile + entrypoint.sh
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── conftest.py             factory_boy factories
└── manage.py
```

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | `django-insecure-dev-key-change-me` | Django secret |
| `DEBUG` | `1` | Debug mode |
| `DATABASE_URL` | `postgres://survey_user:survey_pass@db:5432/survey_platform` | Postgres DSN |
| `REDIS_URL` | `redis://redis:6379/0` | Redis cache |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | Celery broker |
| `ENCRYPTION_KEY` | — | Fernet key for sensitive fields (base64, 32 bytes) |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | Django allowed hosts |

A working `.env` is included in the repository for local setup. Generate a new `ENCRYPTION_KEY` with:

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

---

## Tech Stack

- **Django 4.2** + **DRF 3.14** + **SimpleJWT**
- **PostgreSQL 16** with typed answer columns + composite indexes
- **Redis 7** for cache + Celery broker
- **Celery 5.3** for async exports & scheduled cleanup
- **Fernet** (cryptography) for field-level encryption
- **drf-spectacular** for OpenAPI/Swagger
- **pytest + pytest-django + factory_boy** for testing
