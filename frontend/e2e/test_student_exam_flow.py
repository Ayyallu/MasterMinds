"""Browser-level student exam journey against a deterministic API test double."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

BASE_URL = os.getenv("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:3000")
API_ORIGIN = os.getenv("PLAYWRIGHT_API_ORIGIN", "http://localhost:8000")


def test_student_signs_in_answers_and_submits_exam(page: Page) -> None:
    """Exercise the student-facing browser journey without touching demo data."""
    observed: dict[str, object] = {"answer_saved": False, "submitted": False}

    cors_headers = {
        "access-control-allow-origin": BASE_URL,
        "access-control-allow-credentials": "true",
        "access-control-allow-headers": "authorization,content-type",
        "access-control-allow-methods": "GET,POST,PUT,OPTIONS",
    }

    def respond(route, status: int, payload: dict | list) -> None:
        route.fulfill(status=status, json=payload, headers=cors_headers)

    def mock_api(route) -> None:
        request = route.request
        path, method = urlparse(request.url).path, request.method
        if method == "OPTIONS":
            route.fulfill(status=204, headers=cors_headers)
            return
        if path == "/auth/login" and method == "POST":
            respond(route, 200, {
                "access_token": "playwright-access-token",
                "refresh_token": "playwright-refresh-token",
                "token_type": "bearer", "mfa_required": False,
            })
        elif path == "/auth/me" and method == "GET":
            respond(route, 200, {
                "id": 9001, "full_name": "Automation Student", "email": None,
                "is_super_admin": False, "roles": ["student"], "institution_ids": [77],
            })
        elif path == "/student/exams" and method == "GET":
            respond(route, 200, [{
                "id": 501, "institution_id": 77,
                "institution_name": "Automation Demo School",
                "title": "Playwright Mathematics Test", "status": "live",
                "start_at": None, "end_at": None, "duration_minutes": 30,
                "attempt_limit": 1, "results_published": False, "can_start": True,
                "attempts": [],
            }])
        elif path == "/exams/501/attempts/start" and method == "POST":
            respond(route, 200, _attempt_payload())
        elif path == "/attempts/601" and method == "GET":
            respond(route, 200, _attempt_payload())
        elif path == "/attempts/601/answers/701" and method == "PUT":
            observed["answer_saved"] = request.post_data_json == {"selected_option_ids": [802]}
            respond(route, 200, {"question_version_id": 701, "answer_version": 1})
        elif path == "/attempts/601/submit" and method == "POST":
            observed["submitted"] = True
            payload = _attempt_payload()
            payload.update({
                "status": "submitted", "submitted_at": "2026-11-03T09:05:00Z",
                "seconds_remaining": 0, "questions": [],
            })
            respond(route, 200, payload)
        else:
            respond(route, 404, {"detail": f"Unexpected test API request: {method} {path}"})

    page.route(f"{API_ORIGIN}/**", mock_api)
    page.goto(f"{BASE_URL}/student")
    expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
    page.get_by_label("Institution code").fill("DEMO01")
    page.get_by_label("Register number").fill("MM-AUTO-001")
    page.get_by_label("Password").fill("Automation-Only-Password")
    page.get_by_role("button", name="Sign in").click()

    expect(page.get_by_role("heading", name="Your exams")).to_be_visible()
    expect(page.get_by_text("Automation Student")).to_be_visible()
    expect(page.get_by_role("heading", name="Playwright Mathematics Test")).to_be_visible()
    page.get_by_role("button", name="Start exam").click()

    expect(page.get_by_text("What is 2 + 2?")).to_be_visible()
    page.get_by_label("4", exact=True).check()
    page.get_by_role("button", name="Review & submit").click()
    page.get_by_role("button", name="Submit exam", exact=True).last.click()

    expect(page.get_by_role("heading", name="Exam submitted")).to_be_visible()
    assert observed["answer_saved"] is True
    assert observed["submitted"] is True


def _attempt_payload() -> dict:
    # Relative to now: a fixed past deadline makes the UI treat the attempt as
    # expired and auto-submit before the test can answer.
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return {
        "id": 601, "exam_id": 501, "status": "in_progress", "attempt_no": 1,
        "started_at": now.isoformat().replace("+00:00", "Z"),
        "deadline_at": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        "submitted_at": None,
        "seconds_remaining": 1800,
        "questions": [{
            "question_version_id": 701, "type": "single_mcq",
            "text": "What is 2 + 2?", "marks": 2,
            "options": [{"id": 801, "text": "3"}, {"id": 802, "text": "4"}],
            "answer": None,
        }],
    }
