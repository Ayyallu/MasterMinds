"""Browser-level student exam journey against a deterministic API test double."""
from __future__ import annotations

import os
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

BASE_URL = os.getenv("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:3000")
API_ORIGIN = os.getenv("PLAYWRIGHT_API_ORIGIN", "http://localhost:8000")


def test_student_signs_in_answers_and_submits_exam(page: Page) -> None:
    """Exercise the student-facing browser journey without touching demo data."""
    observed: dict[str, object] = {"answer_saved": False, "submitted": False}

    def mock_api(route) -> None:
        request = route.request
        path, method = urlparse(request.url).path, request.method
        if path == "/auth/login" and method == "POST":
            route.fulfill(status=200, json={
                "access_token": "playwright-access-token",
                "refresh_token": "playwright-refresh-token",
                "token_type": "bearer", "mfa_required": False,
            })
        elif path == "/auth/me" and method == "GET":
            route.fulfill(status=200, json={
                "id": 9001, "full_name": "Automation Student", "email": None,
                "is_super_admin": False, "roles": ["student"], "institution_ids": [77],
            })
        elif path == "/student/exams" and method == "GET":
            route.fulfill(status=200, json=[{
                "id": 501, "institution_id": 77,
                "institution_name": "Automation Demo School",
                "title": "Playwright Mathematics Test", "status": "live",
                "start_at": None, "end_at": None, "duration_minutes": 30,
                "attempt_limit": 1, "results_published": False, "can_start": True,
                "attempts": [],
            }])
        elif path == "/exams/501/attempts/start" and method == "POST":
            route.fulfill(status=200, json=_attempt_payload())
        elif path == "/attempts/601" and method == "GET":
            route.fulfill(status=200, json=_attempt_payload())
        elif path == "/attempts/601/answers/701" and method == "PUT":
            observed["answer_saved"] = request.post_data_json == {"selected_option_ids": [802]}
            route.fulfill(status=200, json={"question_version_id": 701, "answer_version": 1})
        elif path == "/attempts/601/submit" and method == "POST":
            observed["submitted"] = True
            payload = _attempt_payload()
            payload.update({
                "status": "submitted", "submitted_at": "2026-11-03T09:05:00Z",
                "seconds_remaining": 0, "questions": [],
            })
            route.fulfill(status=200, json=payload)
        else:
            route.fulfill(status=404, json={"detail": f"Unexpected test API request: {method} {path}"})

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
    return {
        "id": 601, "exam_id": 501, "status": "in_progress", "attempt_no": 1,
        "started_at": "2026-11-03T09:00:00Z",
        "deadline_at": "2026-11-03T09:30:00Z", "submitted_at": None,
        "seconds_remaining": 1800,
        "questions": [{
            "question_version_id": 701, "type": "single_mcq",
            "text": "What is 2 + 2?", "marks": 2,
            "options": [{"id": 801, "text": "3"}, {"id": 802, "text": "4"}],
            "answer": None,
        }],
    }
