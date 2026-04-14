# Advanced Dynamic Survey Platform - Optimal Implementation Plan

## Context

Build an enterprise-grade dynamic survey platform backend using Django + DRF + Docker. Must demonstrate: clean architecture, scalable data modeling, conditional logic engine, security, and production readiness.

---

## Project Structure

```
survey_platform/
├── docker/
│   ├── django/
│   │   ├── Dockerfile
│   │   └── entrypoint.sh
├── docker-compose.yml
├── requirements.txt
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── celery.py
├── apps/
│   ├── __init__.py
│   ├── common/              # Shared utilities, base models, mixins
│   │   ├── models.py        # TimeStampedModel, UUIDModel base classes
│   │   ├── pagination.py
│   │   └── utils.py
│   ├── accounts/            # Users, Orgs, RBAC
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py
│   │   ├── services/
│   │   └── tests/
│   ├── surveys/             # Survey builder: templates, sections, fields, rules
│   │   ├── models.py
│   │   ├── serializers/
│   │   │   ├── __init__.py
│   │   │   ├── survey.py
│   │   │   ├── section.py
│   │   │   ├── field.py
│   │   │   └── rules.py
│   │   ├── views/
│   │   │   ├── __init__.py
│   │   │   ├── survey.py
│   │   │   ├── section.py
│   │   │   └── field.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── rule_engine.py
│   │   │   ├── dependency_resolver.py
│   │   │   └── survey_builder.py
│   │   ├── selectors/       # Read-only query logic
│   │   │   ├── __init__.py
│   │   │   └── survey_selectors.py
│   │   ├── urls.py
│   │   └── tests/
│   ├── responses/           # Submissions, answers, partial saves
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── submission_service.py
│   │   │   ├── partial_save_service.py
│   │   │   └── encryption.py
│   │   ├── validators/
│   │   │   ├── __init__.py
│   │   │   ├── static_validator.py      # Field-level type/format checks
│   │   │   ├── logic_validator.py       # Visibility/dependency rule checks
│   │   │   └── integrity_validator.py   # Full submission completeness checks
│   │   └── tests/
│   ├── analytics/           # Reports, exports, async tasks
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── services/
│   │   │   ├── report_generator.py
│   │   │   └── export_service.py
│   │   ├── selectors/
│   │   │   └── analytics_selectors.py
│   │   ├── tasks.py
│   │   └── tests/
│   └── audit/               # Audit logging
│       ├── models.py
│       ├── middleware.py
│       ├── mixins.py
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       └── tests/
├── tests/                   # Cross-app and specialized tests
│   ├── integration/
│   ├── load/
│   └── security/
├── manage.py
├── pytest.ini
├── setup.cfg
├── .env.example
└── .gitignore
```

**Key structural decisions:**
- **`services/`** for write/business logic, **`selectors/`** for read/query logic — keeps business logic out of views and serializers
- **`validators/`** in responses app split into 3 layers (static, logic, integrity)
- **`common/`** for shared base classes (TimeStampedModel, etc.)
- Top-level `tests/` for cross-cutting integration, load, and security tests; per-app `tests/` for unit tests

---

## Data Models

### accounts app

```python
class Organization(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=255)

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)

class Membership(UUIDModel):
    """Maps user to org with a role. Supports multi-tenant: same user, different roles per org."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=[
        ("admin", "Admin"),
        ("analyst", "Analyst"),
        ("data_viewer", "Data Viewer"),
    ])
    class Meta:
        unique_together = [("user", "organization")]
```

**Why Membership table over role on User**: A user can belong to multiple orgs with different roles. This is standard multi-tenant design and what the enterprise context demands.

### surveys app

```python
class Survey(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=[
        ("draft", "Draft"), ("published", "Published"), ("archived", "Archived")
    ], default="draft")
    settings = models.JSONField(default=dict)
    # settings: allow_anonymous, require_login, max_submissions, deadline, etc.
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["status", "published_at"]),
        ]

class SurveyVersion(UUIDModel):
    """Frozen snapshot of a survey at publish time. Responses reference this."""
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    snapshot = models.JSONField()  # Full serialized survey structure at publish time
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("survey", "version_number")]

class SurveySection(UUIDModel):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
        unique_together = [("survey", "order")]

class SurveyField(UUIDModel):
    section = models.ForeignKey(SurveySection, on_delete=models.CASCADE, related_name="fields")
    key = models.CharField(max_length=100)  # Stable identifier for the field
    label = models.CharField(max_length=1000)
    field_type = models.CharField(max_length=20, choices=[
        ("text", "Text"), ("textarea", "Textarea"), ("number", "Number"),
        ("email", "Email"), ("date", "Date"), ("datetime", "Datetime"),
        ("dropdown", "Dropdown"), ("checkbox", "Checkbox"), ("radio", "Radio"),
        ("file_upload", "File Upload"), ("rating", "Rating"), ("matrix", "Matrix"),
    ])
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField()
    is_sensitive = models.BooleanField(default=False)
    placeholder = models.CharField(max_length=500, blank=True)
    help_text = models.TextField(blank=True)
    validation_rules = models.JSONField(default=dict, blank=True)
    # {"min_length": 5, "max_length": 200, "pattern": "^...$", "min_value": 0, ...}
    default_value = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("section", "order")]

class FieldOption(models.Model):
    """Separate model for choice-based fields (dropdown, radio, checkbox)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    field = models.ForeignKey(SurveyField, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=500)
    value = models.CharField(max_length=255)
    order = models.PositiveIntegerField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("field", "value")]
```

**Why FieldOption as a separate model instead of JSONField**:
- FK references from FieldDependency (can point to specific options)
- Queryable: "which fields have option X?"
- Better admin UI
- Options can have their own metadata without nesting JSON

**Why SurveyVersion snapshot**:
- When a survey is published, the full structure is serialized and frozen
- Responses always reference the version they were started on
- Draft edits never break active respondents
- Analytics can be version-aware

### Conditional Logic (separate tables)

```python
class VisibilityRule(UUIDModel):
    """Controls whether a section or field is shown based on conditions."""
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="visibility_rules")
    target_type = models.CharField(max_length=10, choices=[
        ("section", "Section"), ("field", "Field")
    ])
    target_id = models.UUIDField()  # ID of SurveySection or SurveyField
    logical_operator = models.CharField(max_length=5, choices=[
        ("AND", "All conditions must be true"),
        ("OR", "Any condition must be true"),
    ], default="AND")

    class Meta:
        indexes = [
            models.Index(fields=["survey"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

class VisibilityCondition(UUIDModel):
    """A single condition within a visibility rule."""
    rule = models.ForeignKey(VisibilityRule, on_delete=models.CASCADE, related_name="conditions")
    source_field = models.ForeignKey(SurveyField, on_delete=models.CASCADE, related_name="dependent_conditions")
    operator = models.CharField(max_length=20, choices=[
        ("eq", "Equals"), ("neq", "Not Equals"),
        ("gt", "Greater Than"), ("lt", "Less Than"),
        ("gte", ">="), ("lte", "<="),
        ("in", "In List"), ("not_in", "Not In List"),
        ("contains", "Contains"), ("not_contains", "Not Contains"),
        ("is_empty", "Is Empty"), ("is_not_empty", "Is Not Empty"),
        ("between", "Between"),
    ])
    expected_value = models.JSONField()
    # Scalar for eq/gt/lt, list for in/not_in, [min,max] for between

class FieldDependency(UUIDModel):
    """Cross-section dependency between fields."""
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="field_dependencies")
    source_field = models.ForeignKey(SurveyField, on_delete=models.CASCADE, related_name="dependents")
    target_field = models.ForeignKey(SurveyField, on_delete=models.CASCADE, related_name="depends_on")
    dependency_type = models.CharField(max_length=20, choices=[
        ("options_filter", "Filter target options based on source answer"),
        ("visibility", "Show/hide target based on source answer"),
        ("required_if", "Target becomes required based on source answer"),
        ("value_constraint", "Constrain target value based on source answer"),
    ])
    config = models.JSONField(default=dict)
    # For options_filter: {"mapping": {"source_val": ["opt1", "opt2"], ...}, "default": [...]}
    # For required_if: {"condition": {"operator": "eq", "value": "yes"}}
    # For value_constraint: {"min_field": "source_field_id", "max_field": "..."}
```

**Why separate tables over JSONFields for rules**:
- **Referential integrity**: `source_field` is a real FK — if the field is deleted, cascade handles cleanup. JSON references are dangling pointers.
- **Queryability**: "Find all rules that depend on field X" is a simple queryset filter, not a JSON scan.
- **Admin UI**: Django admin can display and edit rules as inlines.
- **FieldDependency types**: `options_filter`, `visibility`, `required_if`, `value_constraint` are distinct behaviors. A dedicated model with `dependency_type` makes this explicit rather than overloading a single JSON blob.
- **Complexity is in the engine, not the storage**: The rule evaluation service handles the complex logic; the data model just stores the rules cleanly.

**For the API response**: When serving a survey to respondents, all rules are serialized into the response as nested JSON anyway — so the frontend gets the same convenient structure regardless of backend storage.

### responses app

```python
class SurveySubmission(UUIDModel):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="submissions")
    survey_version = models.ForeignKey(SurveyVersion, on_delete=models.CASCADE)
    respondent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ("in_progress", "In Progress"), ("submitted", "Submitted"), ("abandoned", "Abandoned")
    ], default="in_progress")
    resume_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_saved_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completion_percentage = models.FloatField(default=0.0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["survey", "status"]),
            models.Index(fields=["respondent", "status"]),
            models.Index(fields=["resume_token"]),
            models.Index(fields=["survey", "submitted_at"]),
        ]

class Answer(models.Model):
    """Typed answer columns for analytics query performance."""
    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(SurveySubmission, on_delete=models.CASCADE, related_name="answers")
    field = models.ForeignKey(SurveyField, on_delete=models.CASCADE, related_name="answers")

    # Only one typed column is populated per answer
    value_text = models.TextField(null=True, blank=True)
    value_number = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)
    value_datetime = models.DateTimeField(null=True, blank=True)
    value_boolean = models.BooleanField(null=True)
    value_json = models.JSONField(null=True, blank=True)
    # value_json for: checkbox (list of selected), matrix (dict of responses), file metadata

    value_encrypted = models.BinaryField(null=True, blank=True)

    is_valid = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("submission", "field")]
        indexes = [
            models.Index(fields=["field", "value_text"]),
            models.Index(fields=["field", "value_number"]),
        ]
```

**Why typed columns over single JSONField**:
Analytics queries like `AVG(value_number)`, `COUNT(*) WHERE value_text = 'X'`, date range filtering — all work natively with B-tree indexes. A single JSON value field requires GIN indexes and jsonpath, which is 10-100x slower for aggregation queries. The `is_valid` field tracks per-answer validation state.

### analytics app

```python
class ReportExport(UUIDModel, TimeStampedModel):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    export_format = models.CharField(max_length=10, choices=[
        ("csv", "CSV"), ("xlsx", "XLSX"), ("pdf", "PDF")
    ])
    status = models.CharField(max_length=20, choices=[
        ("pending", "Pending"), ("processing", "Processing"),
        ("completed", "Completed"), ("failed", "Failed")
    ], default="pending")
    file_path = models.FileField(upload_to="exports/%Y/%m/", null=True, blank=True)
    filters = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
```

### audit app

```python
class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50, db_index=True)
    # "survey.create", "survey.publish", "response.submit", "export.request", etc.
    entity_type = models.CharField(max_length=50, db_index=True)
    entity_id = models.CharField(max_length=36)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["actor", "timestamp"]),
            models.Index(fields=["organization", "timestamp"]),
        ]
```

**Audit events emitted from service layer**, not model signals — gives full control over what actions are logged and with what context.

---

## Rule Engine & Dependency Resolver

Located in `apps/surveys/services/`.

### RuleEngine (rule_engine.py)

```python
class RuleEngine:
    OPERATORS = {
        "eq": lambda a, v: a == v,
        "neq": lambda a, v: a != v,
        "gt": lambda a, v: float(a) > float(v),
        "lt": lambda a, v: float(a) < float(v),
        "gte": lambda a, v: float(a) >= float(v),
        "lte": lambda a, v: float(a) <= float(v),
        "in": lambda a, v: a in v,
        "not_in": lambda a, v: a not in v,
        "contains": lambda a, v: v in str(a),
        "not_contains": lambda a, v: v not in str(a),
        "is_empty": lambda a, v: not a,
        "is_not_empty": lambda a, v: bool(a),
        "between": lambda a, v: v[0] <= float(a) <= v[1],
    }

    def __init__(self, answers: dict[str, Any]):
        self.answers = answers  # {field_id_str: value}

    def evaluate_rule(self, rule: VisibilityRule) -> bool:
        conditions = rule.conditions.all()
        if not conditions:
            return True
        results = [self._eval_condition(c) for c in conditions]
        if rule.logical_operator == "AND":
            return all(results)
        return any(results)

    def _eval_condition(self, cond: VisibilityCondition) -> bool:
        answer = self.answers.get(str(cond.source_field_id))
        if answer is None and cond.operator not in ("is_empty",):
            return False
        op = self.OPERATORS.get(cond.operator)
        if not op:
            raise ValueError(f"Unknown operator: {cond.operator}")
        try:
            return op(answer, cond.expected_value)
        except (TypeError, ValueError):
            return False

    def is_visible(self, target_type: str, target_id: str, rules: list) -> bool:
        """Multiple rules on the same target: OR logic (visible if ANY rule passes)."""
        applicable = [r for r in rules if r.target_type == target_type and str(r.target_id) == target_id]
        if not applicable:
            return True  # No rules = always visible
        return any(self.evaluate_rule(r) for r in applicable)

    def get_visible_fields(self, survey, rules) -> set[str]:
        visible = set()
        for section in survey.sections.all():
            if not self.is_visible("section", str(section.id), rules):
                continue
            for field in section.fields.all():
                if self.is_visible("field", str(field.id), rules):
                    visible.add(str(field.id))
        return visible
```

### DependencyResolver (dependency_resolver.py)

```python
class DependencyResolver:
    def __init__(self, answers: dict[str, Any]):
        self.answers = answers

    def resolve(self, dependency: FieldDependency) -> dict:
        source_answer = self.answers.get(str(dependency.source_field_id))
        config = dependency.config

        if dependency.dependency_type == "options_filter":
            mapping = config.get("mapping", {})
            default = config.get("default", [])
            return {"options": mapping.get(str(source_answer), default)}

        elif dependency.dependency_type == "required_if":
            condition = config.get("condition", {})
            op = RuleEngine.OPERATORS.get(condition.get("operator", "eq"))
            is_required = op(source_answer, condition.get("value")) if op and source_answer else False
            return {"required": is_required}

        elif dependency.dependency_type == "value_constraint":
            return {"constraints": config}  # Pass through for field-level validation

        elif dependency.dependency_type == "visibility":
            # Handled by VisibilityRule, but can also be expressed as dependency
            condition = config.get("condition", {})
            op = RuleEngine.OPERATORS.get(condition.get("operator", "eq"))
            is_visible = op(source_answer, condition.get("value")) if op and source_answer else False
            return {"visible": is_visible}

        return {}
```

---

## 3-Level Validation Strategy

### Level 1: Static Field Validation (`static_validator.py`)
- Type checking (number field gets a number, date gets a date)
- Required field check
- Min/max length, min/max value
- Regex pattern matching
- Allowed options (dropdown value is in FieldOption set)
- File size/extension constraints

### Level 2: Dynamic Logic Validation (`logic_validator.py`)
- Field must only be answered if visible (per rule engine)
- Field becomes required if `required_if` dependency is met
- Options must match dependency constraints (filtered options)
- Value must satisfy `value_constraint` dependencies

### Level 3: Submission Integrity Validation (`integrity_validator.py`)
- All visible required fields have answers
- No answers exist for hidden fields (delete them — prevents data injection)
- Survey version hasn't changed mid-submission
- Submission is still in `in_progress` status (not already submitted)

---

## API Endpoints (all under `/api/v1/`)

### Auth
- `POST /auth/login/` — JWT obtain
- `POST /auth/refresh/` — JWT refresh
- `POST /auth/logout/` — blacklist token

### Users & Org (Admin)
- `GET/POST /users/` | `GET/PATCH/DELETE /users/{id}/` | `GET /users/me/`

### Surveys (Admin creates, Analyst views)
- `GET/POST /surveys/`
- `GET/PATCH/DELETE /surveys/{id}/`
- `POST /surveys/{id}/publish/` — creates SurveyVersion snapshot
- `POST /surveys/{id}/archive/`
- `POST /surveys/{id}/duplicate/`

### Sections (nested under surveys)
- `GET/POST /surveys/{sid}/sections/`
- `GET/PATCH/DELETE /surveys/{sid}/sections/{id}/`
- `POST /surveys/{sid}/sections/reorder/`

### Fields & Options (nested under sections)
- `GET/POST /sections/{sid}/fields/`
- `GET/PATCH/DELETE /sections/{sid}/fields/{id}/`
- `POST /sections/{sid}/fields/reorder/`
- `GET/POST /fields/{fid}/options/`
- `PATCH/DELETE /fields/{fid}/options/{id}/`

### Rules & Dependencies (on surveys)
- `GET/POST /surveys/{sid}/rules/` — visibility rules
- `GET/PATCH/DELETE /surveys/{sid}/rules/{id}/`
- `GET/POST /surveys/{sid}/dependencies/` — field dependencies
- `GET/PATCH/DELETE /surveys/{sid}/dependencies/{id}/`

### Public Survey Runtime (respondent-facing)
- `GET /public/surveys/{id}/` — get published survey for responding
- `POST /public/surveys/{id}/start/` — start new submission (creates draft)
- `POST /public/responses/{id}/answers/` — save answers (auto-save)
- `POST /public/responses/{id}/save-draft/` — explicit draft save
- `POST /public/responses/{id}/submit/` — final submit with full 3-level validation
- `GET /public/responses/resume/{token}/` — resume by token
- `GET /public/responses/{id}/current/` — get current response state with resolved rules

### Analytics & Exports
- `GET /surveys/{id}/analytics/summary/` — aggregated results
- `GET /surveys/{id}/analytics/fields/{fid}/` — per-field breakdown
- `GET /surveys/{id}/submissions/` — list submissions (paginated)
- `POST /surveys/{id}/exports/` — request async export
- `GET /exports/{id}/` — check status / download

### Bulk Operations
- `POST /surveys/{id}/invitations/` — send email invitations (async)

### Audit Logs (Admin)
- `GET /audit-logs/`
- `GET /audit-logs/{id}/`
- Filterable by: entity_type, entity_id, actor, action, date range

---

## Encryption

**Fernet symmetric encryption** via `cryptography` library.
- Key stored as env var (`ENCRYPTION_KEY`)
- When `SurveyField.is_sensitive=True`, answer stored in `Answer.value_encrypted` (BinaryField)
- `value_text` set to `"[ENCRYPTED]"` as sentinel
- Only Admin role can decrypt; Analyst/DataViewer see `"[REDACTED]"`
- Key rotation via `MultiFernet` + Celery re-encryption task
- Sensitive values never logged in audit logs

---

## Caching (Redis)

| Target | Key | TTL | Invalidation |
|--------|-----|-----|--------------|
| Published survey structure | `survey:v{ver}:{id}` | 1h | On publish/archive |
| Compiled rule tree | `survey:{id}:rules:v{ver}` | 1h | On publish |
| Analytics summary | `analytics:{id}:summary` | 5min | On new submission |
| Submission count | `survey:{id}:count` | 2min | On new submission |
| User permissions/membership | `user:{id}:perms` | 15min | On role change |

---

## Celery Tasks (Redis broker)

- `generate_export` — create CSV/XLSX/PDF file (max 3 retries, countdown=60)
- `send_bulk_invitations` — batch emails in groups of 50
- `cleanup_stale_drafts` — delete drafts older than 30 days (daily Beat at 3 AM)
- `recompute_analytics_cache` — triggered after submission
- `reencrypt_sensitive_fields` — for key rotation

---

## RBAC Matrix

| Permission | Admin | Analyst | Data Viewer |
|-----------|-------|---------|-------------|
| Create/edit/delete/publish surveys | Yes | No | No |
| Manage rules and dependencies | Yes | No | No |
| View survey definitions | Yes | Yes | No |
| View individual submissions | Yes | Yes | No |
| View aggregated analytics | Yes | Yes | Yes |
| Export data | Yes | Yes | No |
| Decrypt sensitive fields | Yes | No | No |
| Manage users/memberships | Yes | No | No |
| View audit logs | Yes | No | No |
| Send invitations | Yes | No | No |

Implemented via DRF permission classes + `Membership` queryset filtering for org scoping.

---

## Docker Compose

Single `docker-compose.yml` — `docker compose up` brings the whole stack online.

5 services:
1. **db** — PostgreSQL 16 Alpine, healthcheck: `pg_isready`
2. **redis** — Redis 7 Alpine, healthcheck: `redis-cli ping`
3. **web** — Django `runserver` on :8000, volume mount for hot reload
4. **celery_worker** — Celery worker, concurrency=2
5. **celery_beat** — Celery beat with DatabaseScheduler

No nginx, gunicorn, or prod-specific configs at this layer — production readiness is demonstrated in the code itself (caching, async tasks, DB optimization, indexing), not via DevOps tooling. Swapping `runserver` for gunicorn is a one-line change when deploying.

---

## Testing Strategy

**Tools**: pytest, pytest-django, factory_boy, faker, pytest-cov, locust, bandit

### Unit tests (per-app `tests/`)
- RuleEngine with all operators and edge cases
- DependencyResolver for each dependency type
- All 3 validation levels
- Encryption round-trip
- Serializer validation
- Permission classes

### Integration tests (`tests/integration/`)
- Full survey creation: survey -> sections -> fields -> options -> rules -> dependencies -> publish
- Full submission: start -> auto-save -> resume by token -> submit -> validation
- Conditional logic e2e: rules that hide/show fields, verify validation respects visibility
- Cross-section dependency: options_filter, required_if
- RBAC per-endpoint per-role
- Analytics aggregation correctness
- Export task produces correct file
- Survey version isolation (edit draft doesn't affect active version)

### Load tests (`tests/load/`)
- 1000 concurrent survey loads
- 500 concurrent submissions
- Analytics under load with 100k+ submissions

### Security tests (`tests/security/`)
- bandit scan
- Sensitive field plaintext never leaked to non-admin
- Org scoping prevents cross-tenant access
- Hidden field answer injection blocked
- Token misuse (resume token for wrong survey)
- Mass assignment attempts

**Coverage target**: 90%+ on services/validators, 80%+ overall

---

## Implementation Phases

### Phase 1: Foundation
- Create venv, install Django, run `django-admin startproject config .`
- Run `python manage.py startapp` for each app (common, accounts, surveys, responses, analytics, audit)
- Move apps into `apps/` directory, configure settings
- Single `settings.py` with env var support (via `os.environ` + sensible defaults)
- Single `requirements.txt`
- Docker Compose with 5 services, `Dockerfile`, `entrypoint.sh`
- `common` app: base models (UUIDModel, TimeStampedModel)
- `accounts` app: User, Organization, Membership, JWT auth, permission classes
- Verify: `docker compose up`, migrations, admin site

### Phase 2: Survey Builder
- `surveys` models: Survey, SurveySection, SurveyField, FieldOption
- CRUD serializers + views (split into directories)
- Reorder endpoints for sections and fields
- Publish action: creates SurveyVersion snapshot, changes status
- Archive/duplicate actions
- Tests for all CRUD

### Phase 3: Conditional Logic & Dependencies
- VisibilityRule, VisibilityCondition, FieldDependency models
- RuleEngine service with all operators
- DependencyResolver service (options_filter, visibility, required_if, value_constraint)
- Rule/dependency CRUD endpoints
- Survey preview endpoint (includes resolved rules)
- Comprehensive unit tests for rule engine

### Phase 4: Responses & Validation
- SurveySubmission, Answer models
- Start submission (creates draft, generates resume_token)
- Auto-save answers endpoint
- Resume by token endpoint
- 3-level validation: static -> logic -> integrity
- Final submit endpoint
- Encryption service for sensitive fields
- Integration tests for full submission flow

### Phase 5: Analytics & Async
- Analytics summary + per-field breakdown (selectors with optimized queries)
- Export model + async Celery task
- Draft cleanup task + Beat schedule
- Bulk invitation task
- Caching layer on surveys and analytics

### Phase 6: Audit, Security & Docs
- AuditLog model, middleware (captures IP/UA), mixin (logs actions from views)
- Wire audit into all service-layer actions
- Rate limiting on public endpoints
- CORS, security headers
- drf-spectacular Swagger UI setup
- API versioning (URL namespace `/api/v1/`)

### Phase 7: Testing & QA
- Integration tests across app boundaries
- Load tests with Locust
- bandit security scan
- Final review

---

## Key Dependencies (requirements.txt)

Single file — all deps in one place for simplicity.

```
Django>=4.2,<5.0
djangorestframework>=3.14
djangorestframework-simplejwt
django-cors-headers
django-filter
drf-spectacular
celery[redis]>=5.3
django-celery-beat
redis
psycopg2-binary
cryptography
factory-boy
faker
pytest
pytest-django
pytest-cov
locust
bandit
```

---

## Verification Plan

1. `docker compose up` — all 5 services healthy
2. Create admin user + org, obtain JWT
3. Build a survey: 2 sections, mixed field types, options, visibility rules (AND + OR), cross-section dependency (options_filter + required_if)
4. Publish survey — verify SurveyVersion snapshot created
5. As anonymous respondent: start draft, auto-save, resume by token, final submit
6. Test conditional logic: submit with values that hide fields, confirm hidden answers deleted
7. Test dependency: change Section 1 answer, verify Section 2 options filtered
8. Test sensitive field: admin sees decrypted, analyst sees redacted
9. Request CSV export, verify Celery processes it
10. Check analytics endpoints return correct aggregations
11. Verify audit log captured all actions
12. Run `pytest --cov` — confirm coverage targets
13. Run locust load test
