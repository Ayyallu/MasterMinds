"""Faculty authoring, institution approval and student availability browser journey."""
from __future__ import annotations

import os
from urllib.parse import urlparse

from playwright.sync_api import Page, expect

BASE_URL = os.getenv("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:3000")
API_ORIGIN = os.getenv("PLAYWRIGHT_API_ORIGIN", "http://localhost:8000")
INSTITUTION_ID = 77
EXAM_ID = 901


def test_faculty_creates_exam_admin_schedules_and_student_can_start(page: Page) -> None:
    """Cover the staff hand-off and verify the scheduled exam reaches its student."""
    state = {"role": "", "created_payload": None, "scheduled": False, "started": False}
    cors_headers = {
        "access-control-allow-origin": BASE_URL,
        "access-control-allow-credentials": "true",
        "access-control-allow-headers": "authorization,content-type",
        "access-control-allow-methods": "GET,POST,PUT,OPTIONS",
    }

    def fulfill(route, status: int, payload: dict | list) -> None:
        route.fulfill(status=status, json=payload, headers=cors_headers)

    def exam(status: str) -> dict:
        return {
            "id": EXAM_ID,
            "title": "Faculty-created Mathematics Assessment",
            "status": status,
            "num_questions": 1,
            "duration_minutes": 30,
            "attempt_limit": 1,
            "randomize": True,
            "result_release_rule": "manual",
            "frozen": status in {"approved", "scheduled", "live"},
            "start_at": "2026-11-03T00:00:00Z" if status == "scheduled" else None,
            "end_at": "2026-11-04T00:00:00Z" if status == "scheduled" else None,
            "timezone": "UTC",
        }

    def mock_api(route) -> None:
        request = route.request
        path, method = urlparse(request.url).path, request.method
        if method == "OPTIONS":
            route.fulfill(status=204, headers=cors_headers)
            return

        if path == "/auth/login" and method == "POST":
            body = request.post_data_json or {}
            if body.get("institution_code"):
                state["role"] = "student"
            elif body.get("email", "").startswith("teacher@"):
                state["role"] = "teacher"
            else:
                state["role"] = "institution_admin"
            fulfill(route, 200, {
                "access_token": f"automation-{state['role']}-token",
                "refresh_token": f"automation-{state['role']}-refresh",
                "token_type": "bearer",
                "mfa_required": False,
            })
        elif path == "/auth/me" and method == "GET":
            role = state["role"]
            if role == "student":
                fulfill(route, 200, {
                    "id": 9003, "full_name": "Automation Student", "email": None,
                    "is_super_admin": False, "roles": ["student"],
                    "institution_ids": [INSTITUTION_ID],
                })
            else:
                fulfill(route, 200, {
                    "id": 9002 if role == "teacher" else 9004,
                    "full_name": "Automation Faculty" if role == "teacher" else "Automation Admin",
                    "email": "teacher@demo.example.com" if role == "teacher" else "admin@demo.example.com",
                    "is_super_admin": False, "roles": [role],
                    "institution_ids": [INSTITUTION_ID],
                })
        elif path == f"/institutions/{INSTITUTION_ID}/class-groups/available-for-exam" and method == "GET":
            fulfill(route, 200, [{"id": 770, "name": "Grade 10 - Section A"}])
        elif path == f"/institutions/{INSTITUTION_ID}/exams" and method == "POST":
            state["created_payload"] = request.post_data_json
            fulfill(route, 201, exam("draft"))
        elif path == f"/institutions/{INSTITUTION_ID}/exams/{EXAM_ID}" and method == "GET":
            fulfill(route, 200, exam("awaiting_approval" if state["role"] == "institution_admin" else "draft"))
        elif path == f"/institutions/{INSTITUTION_ID}/exams/{EXAM_ID}/submit" and method == "POST":
            fulfill(route, 200, exam("awaiting_approval"))
        elif path == f"/institutions/{INSTITUTION_ID}/exams/{EXAM_ID}/approve" and method == "POST":
            fulfill(route, 200, exam("approved"))
        elif path == f"/institutions/{INSTITUTION_ID}/exams/{EXAM_ID}/schedule" and method == "POST":
            state["scheduled"] = True
            fulfill(route, 200, exam("scheduled"))
        elif path == "/student/exams" and method == "GET":
            fulfill(route, 200, [{
                "id": EXAM_ID, "institution_id": INSTITUTION_ID,
                "institution_name": "Automation Demo School",
                "title": "Faculty-created Mathematics Assessment",
                "status": "live", "start_at": None, "end_at": None,
                "duration_minutes": 30, "attempt_limit": 1,
                "results_published": False, "can_start": state["scheduled"],
                "attempts": [],
            }])
        elif path == f"/exams/{EXAM_ID}/attempts/start" and method == "POST":
            state["started"] = True
            fulfill(route, 200, {
                "id": 950, "exam_id": EXAM_ID, "status": "in_progress",
                "attempt_no": 1, "started_at": "2026-11-03T09:00:00Z",
                "deadline_at": "2026-11-03T09:30:00Z", "submitted_at": None,
                "seconds_remaining": 1800,
                "questions": [{
                    "question_version_id": 951, "type": "single_mcq",
                    "text": "What is 5 × 5?", "marks": 2,
                    "options": [{"id": 952, "text": "20"}, {"id": 953, "text": "25"}],
                    "answer": None,
                }],
            })
        elif path == "/attempts/950" and method == "GET":
            fulfill(route, 200, {
                "id": 950, "exam_id": EXAM_ID, "status": "in_progress",
                "attempt_no": 1, "started_at": "2026-11-03T09:00:00Z",
                "deadline_at": "2026-11-03T09:30:00Z", "submitted_at": None,
                "seconds_remaining": 1800,
                "questions": [{
                    "question_version_id": 951, "type": "single_mcq",
                    "text": "What is 5 × 5?", "marks": 2,
                    "options": [{"id": 952, "text": "20"}, {"id": 953, "text": "25"}],
                    "answer": None,
                }],
            })
        else:
            fulfill(route, 404, {"detail": f"Unexpected test API request: {method} {path}"})

    page.route(f"{API_ORIGIN}/**", mock_api)

    # Faculty creates a draft and submits it for Institution Admin approval.
    page.goto(f"{BASE_URL}/admin")
    expect(page.get_by_role("heading", name="Sign in to your workspace")).to_be_visible()
    page.get_by_label("Email").fill("teacher@demo.example.com")
    page.get_by_label("Password").fill("Automation-Only-Password")
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_text("Automation Faculty")).to_be_visible()
    page.get_by_role("link", name="Exams").click()
    page.get_by_role("button", name="Create exam").click()
    page.get_by_label("Exam title").fill("Faculty-created Mathematics Assessment")
    expect(page.get_by_label("Target class group")).to_have_value("770")
    page.get_by_role("button", name="Create draft").click()

    expect(page.get_by_role("heading", name="Faculty-created Mathematics Assessment")).to_be_visible()
    expect(page.get_by_text("draft", exact=True)).to_be_visible()
    page.get_by_role("button", name="Submit for approval").click()
    expect(page.get_by_text("awaiting approval", exact=False)).to_be_visible()
    assert state["created_payload"] == {
        "title": "Faculty-created Mathematics Assessment",
        "class_group_id": 770,
        "duration_minutes": 60,
        "attempt_limit": 1,
        "randomize": True,
        "negative_marking": False,
        "result_release_rule": "manual",
        "timezone": "UTC",
        "distribution": [{"count": 10}],
    }

    # Institution Admin approves and schedules the submitted exam.
    admin = page.context.new_page()
    admin.route(f"{API_ORIGIN}/**", mock_api)
    admin.goto(f"{BASE_URL}/admin")
    admin.get_by_label("Email").fill("admin@demo.example.com")
    admin.get_by_label("Password").fill("Automation-Only-Password")
    admin.get_by_role("button", name="Sign in").click()
    admin.goto(f"{BASE_URL}/admin/exams/{EXAM_ID}")
    expect(admin.get_by_role("heading", name="Faculty-created Mathematics Assessment")).to_be_visible()
    admin.get_by_role("button", name="Approve").click()
    expect(admin.get_by_text("approved", exact=True)).to_be_visible()
    admin.get_by_role("button", name="Schedule").click()
    admin.get_by_label("Start time").fill("2026-11-03T09:00")
    admin.get_by_label("End time").fill("2026-11-03T10:00")
    admin.get_by_role("button", name="Schedule", exact=True).last.click()
    expect(admin.get_by_text("scheduled", exact=True)).to_be_visible()
    assert state["scheduled"] is True

    # Student sees the scheduled assessment and can launch an attempt.
    student = page.context.new_page()
    student.route(f"{API_ORIGIN}/**", mock_api)
    student.goto(f"{BASE_URL}/student")
    student.get_by_label("Institution code").fill("DEMO01")
    student.get_by_label("Register number").fill("MM-AUTO-001")
    student.get_by_label("Password").fill("Automation-Only-Password")
    student.get_by_role("button", name="Sign in").click()
    expect(student.get_by_role("heading", name="Your exams")).to_be_visible()
    expect(student.get_by_role("heading", name="Faculty-created Mathematics Assessment")).to_be_visible()
    student.get_by_role("button", name="Start exam").click()
    expect(student.get_by_text("What is 5 × 5?")).to_be_visible()
    assert state["started"] is True
