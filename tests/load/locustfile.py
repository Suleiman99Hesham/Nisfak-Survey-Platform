"""Locust load test for the Survey Platform.

Usage:
    locust -f tests/load/locustfile.py --host http://localhost:8000

Assumes a published survey exists. Set env vars before running:

    SURVEY_ID            — UUID of a published survey (required for submission flow)
    ADMIN_USERNAME       — defaults to "admin"
    ADMIN_PASSWORD       — defaults to "admin"

Three user classes simulate distinct traffic patterns — weight them with
`--class-picker` or `-u` per class if desired:

    PublicRespondent  — anonymous, hits public endpoints (80% of traffic)
    AdminOperator     — authenticated admin, lists/views surveys (15%)
    AnalystViewer     — authenticated analyst, pulls analytics summary (5%)
"""
import os
import random

from locust import HttpUser, between, task


SURVEY_ID = os.environ.get("SURVEY_ID", "")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")


def _login(client, username, password):
    r = client.post(
        "/api/v1/auth/login/",
        json={"username": username, "password": password},
        name="/auth/login/",
    )
    if r.status_code == 200:
        return r.json().get("access")
    print(
        f"[locust] login failed for user '{username}' -> status={r.status_code} "
        f"body={r.text[:200]}. Set ADMIN_USERNAME / ADMIN_PASSWORD env vars."
    )
    return None


class PublicRespondent(HttpUser):
    """Anonymous respondent: fetch published survey -> start -> save -> submit."""
    weight = 8
    wait_time = between(1, 3)

    def on_start(self):
        self.survey_id = SURVEY_ID
        self.sections = []
        self.visibility_rules = []
        self.field_dependencies = []
        if not self.survey_id:
            return
        with self.client.get(
            f"/api/v1/public/surveys/{self.survey_id}/",
            name="/public/surveys/[id]/",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                body = resp.json()
                self.sections = body.get("sections", [])
                self.visibility_rules = body.get("visibility_rules", [])
                self.field_dependencies = body.get("field_dependencies", [])
            else:
                resp.failure(f"survey fetch {resp.status_code}")

    @task(5)
    def get_survey(self):
        if not self.survey_id:
            return
        self.client.get(
            f"/api/v1/public/surveys/{self.survey_id}/",
            name="/public/surveys/[id]/",
        )

    @task(3)
    def full_submission(self):
        if not self.survey_id or not self.sections:
            return

        with self.client.post(
            f"/api/v1/public/surveys/{self.survey_id}/start/",
            name="/public/surveys/[id]/start/",
            catch_response=True,
        ) as r:
            if r.status_code != 201:
                r.failure(f"start {r.status_code}")
                return
            sub = r.json()

        sub_id = sub["id"]
        token = sub.get("resume_token", "")

        answers = _build_rule_aware_answers(
            self.sections, self.visibility_rules, self.field_dependencies
        )

        if answers:
            self.client.post(
                f"/api/v1/public/responses/{sub_id}/answers/",
                json=answers,
                headers={"X-Resume-Token": token},
                name="/public/responses/[id]/answers/",
            )

        self.client.post(
            f"/api/v1/public/responses/{sub_id}/submit/",
            headers={"X-Resume-Token": token},
            name="/public/responses/[id]/submit/",
        )


class AdminOperator(HttpUser):
    """Authenticated admin — list surveys, view submissions."""
    weight = 2
    wait_time = between(2, 5)

    def on_start(self):
        token = _login(self.client, ADMIN_USERNAME, ADMIN_PASSWORD)
        self.client.headers.update({"Authorization": f"Bearer {token}"} if token else {})

    @task(3)
    def list_surveys(self):
        self.client.get("/api/v1/surveys/")

    @task(1)
    def list_submissions(self):
        if SURVEY_ID:
            self.client.get(
                f"/api/v1/surveys/{SURVEY_ID}/submissions/",
                name="/surveys/[id]/submissions/",
            )


class AnalystViewer(HttpUser):
    """Analytics dashboard watcher — repeatedly polls the summary endpoint (caching!)."""
    weight = 1
    wait_time = between(3, 8)

    def on_start(self):
        token = _login(self.client, ADMIN_USERNAME, ADMIN_PASSWORD)
        self.client.headers.update({"Authorization": f"Bearer {token}"} if token else {})

    @task
    def analytics_summary(self):
        if SURVEY_ID:
            self.client.get(
                f"/api/v1/surveys/{SURVEY_ID}/analytics/summary/",
                name="/surveys/[id]/analytics/summary/",
            )


_OPERATORS = {
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


def _eval_condition(cond, answers):
    answer = answers.get(str(cond["source_field"]))
    if answer is None and cond["operator"] != "is_empty":
        return False
    op = _OPERATORS.get(cond["operator"])
    if not op:
        return False
    try:
        return op(answer, cond["expected_value"])
    except (TypeError, ValueError):
        return False


def _is_target_visible(target_type, target_id, rules, answers):
    applicable = [
        r for r in rules
        if r["target_type"] == target_type and str(r["target_id"]) == str(target_id)
    ]
    if not applicable:
        return True
    for rule in applicable:
        results = [_eval_condition(c, answers) for c in rule.get("conditions", [])]
        if not results:
            return True
        passed = all(results) if rule.get("logical_operator", "AND") == "AND" else any(results)
        if passed:
            return True
    return False


def _filtered_options(field, dependencies, answers):
    """Apply options_filter dependencies to return the allowed option list."""
    options = field.get("options") or []
    for dep in dependencies:
        if str(dep["target_field"]) != str(field["id"]):
            continue
        if dep["dependency_type"] != "options_filter":
            continue
        src_val = answers.get(str(dep["source_field"]))
        cfg = dep.get("config", {})
        allowed = cfg.get("mapping", {}).get(str(src_val), cfg.get("default", []))
        options = [o for o in options if o["value"] in allowed]
    return options


def _dummy_value(field, dependencies, answers):
    ftype = field.get("field_type")
    if ftype in ("text", "textarea"):
        rules = field.get("validation_rules") or {}
        min_len = rules.get("min_length", 1)
        max_len = rules.get("max_length", 50)
        base = f"load-{random.randint(1, 10_000)}"
        return base[:max_len].ljust(min_len, "x")
    if ftype == "email":
        return f"user{random.randint(1, 10_000)}@example.com"
    if ftype in ("number", "rating"):
        rules = field.get("validation_rules") or {}
        lo = int(rules.get("min_value", 0))
        hi = int(rules.get("max_value", 10))
        return random.randint(lo, hi)
    if ftype == "date":
        return "2026-01-01"
    if ftype == "datetime":
        return "2026-01-01T12:00:00Z"
    if ftype in ("dropdown", "radio"):
        options = _filtered_options(field, dependencies, answers)
        return random.choice(options)["value"] if options else None
    if ftype == "checkbox":
        options = _filtered_options(field, dependencies, answers)
        return [random.choice(options)["value"]] if options else []
    return None


def _build_rule_aware_answers(sections, visibility_rules, field_dependencies):
    """Walk sections in order, skip hidden targets, respect options_filter dependencies."""
    answers_by_fid = {}
    for section in sections:
        if not _is_target_visible("section", section["id"], visibility_rules, answers_by_fid):
            continue
        for field in section.get("fields", []):
            if not _is_target_visible("field", field["id"], visibility_rules, answers_by_fid):
                continue
            val = _dummy_value(field, field_dependencies, answers_by_fid)
            if val is not None and val != []:
                answers_by_fid[str(field["id"])] = val
    return [{"field_id": fid, "value": v} for fid, v in answers_by_fid.items()]
