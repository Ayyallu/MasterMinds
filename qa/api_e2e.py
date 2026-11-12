"""MasterMinds end-to-end API scenario suite (senior QA pass).

Runs against an isolated backend (default http://localhost:8001, QA database).
Every check records PASS/FAIL with evidence; results go to results.json.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import sys
import time
import traceback

import httpx
import pyotp

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
OUT = sys.argv[2] if len(sys.argv) > 2 else "results.json"
RUN = dt.datetime.now().strftime("%H%M%S")
c = httpx.Client(base_url=BASE, timeout=60)
results: list[dict] = []
area = "?"


def section(name):
    global area
    area = name
    print(f"\n=== {name}")


def check(cid, desc, cond, detail=""):
    ok = bool(cond)
    results.append({"area": area, "id": cid, "desc": desc, "ok": ok, "detail": "" if ok else str(detail)[:600]})
    print(f"  {'PASS' if ok else 'FAIL'} {cid} {desc}" + ("" if ok else f"\n       -> {str(detail)[:300]}"))
    return ok


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def login(**body):
    return c.post("/auth/login", json=body)


def tok(**body):
    r = login(**body)
    assert r.status_code == 200, f"login failed {body.get('email') or body.get('register_number')}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def j(r):
    try:
        return r.json()
    except Exception:
        return r.text


def has_key_leak(obj) -> list[str]:
    """Find answer-key fields with non-null values anywhere in a payload."""
    leaks = []

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("is_correct", "numerical_answer", "numerical_tolerance", "explanation", "correct_option_ids", "correct_answer") and v not in (None, [], ""):
                    leaks.append(f"{path}.{k}={v!r}")
                walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(obj)
    return leaks


now = dt.datetime.now(dt.timezone.utc)
S = {}  # shared state

try:
    # ------------------------------------------------------------------ A
    section("A. Platform, authentication & sessions")
    r = c.get("/health")
    check("A01", "Health endpoint reports app + DB up", r.status_code == 200 and j(r).get("database") == "up", j(r))

    r = login(email="qa.root@qa.example.com", password="QaRootPass#2026")
    check("A02", "Super Admin can sign in", r.status_code == 200, j(r))
    S["root"] = r.json()["access_token"]
    root_refresh = r.json()["refresh_token"]
    me = j(c.get("/auth/me", headers=H(S["root"])))
    check("A03", "/auth/me identifies Super Admin", me.get("is_super_admin") is True, me)

    r1 = login(email="qa.root@qa.example.com", password="wrong-password")
    r2 = login(email="nobody@qa.example.com", password="wrong-password")
    check("A04", "Wrong password and unknown user both 401 with same message (no user enumeration)",
          r1.status_code == r2.status_code == 401 and j(r1) == j(r2), (r1.status_code, j(r1), r2.status_code, j(r2)))

    codes = [login(email="ratelimit@qa.example.com", password="x").status_code for _ in range(7)]
    check("A05", "Login is rate-limited after repeated failures (429)", 429 in codes, codes)

    check("A06", "No token -> 401", c.get("/auth/me").status_code == 401)
    check("A07", "Garbage token -> 401", c.get("/auth/me", headers=H("not.a.jwt")).status_code == 401)

    r = c.post("/auth/refresh", json={"refresh_token": root_refresh})
    check("A08", "Refresh token rotates (new pair issued)", r.status_code == 200 and r.json()["refresh_token"] != root_refresh, j(r))
    new_refresh = r.json().get("refresh_token")
    replay = c.post("/auth/refresh", json={"refresh_token": root_refresh})
    check("A09", "Replaying a rotated refresh token is rejected", replay.status_code == 401, (replay.status_code, j(replay)))
    fam = c.post("/auth/refresh", json={"refresh_token": new_refresh})
    check("A10", "Replay revokes the whole token family (newer refresh also dead)", fam.status_code == 401, (fam.status_code, j(fam)))

    r = login(email="qa.root@qa.example.com", password="QaRootPass#2026")
    lo = c.post("/auth/logout", json={"refresh_token": r.json()["refresh_token"]})
    after = c.post("/auth/refresh", json={"refresh_token": r.json()["refresh_token"]})
    check("A11", "Logout invalidates the refresh token", lo.status_code in (200, 204) and after.status_code == 401, (lo.status_code, after.status_code))

    # MFA on the QA super admin.
    S["root"] = tok(email="qa.root@qa.example.com", password="QaRootPass#2026")
    setup = c.post("/auth/mfa/setup", headers=H(S["root"]))
    secret = (j(setup) or {}).get("secret") if isinstance(j(setup), dict) else None
    check("A12", "MFA setup returns a TOTP secret / provisioning URI", setup.status_code == 200 and secret, j(setup))
    if secret:
        bad = c.post("/auth/mfa/enable", json={"totp_code": "000000"}, headers=H(S["root"]))
        check("A13", "MFA enable rejects a wrong code", bad.status_code >= 400, (bad.status_code, j(bad)))
        en = c.post("/auth/mfa/enable", json={"totp_code": pyotp.TOTP(secret).now()}, headers=H(S["root"]))
        check("A14", "MFA enable accepts a valid code", en.status_code in (200, 204), (en.status_code, j(en)))
        r = login(email="qa.root@qa.example.com", password="QaRootPass#2026")
        check("A15", "With MFA on, password alone does not issue tokens", r.status_code in (200, 401) and not (r.status_code == 200 and r.json().get("access_token")), j(r))
        r = login(email="qa.root@qa.example.com", password="QaRootPass#2026", totp_code=pyotp.TOTP(secret).now())
        check("A16", "With MFA on, password + valid TOTP signs in", r.status_code == 200 and r.json().get("access_token"), j(r))
        S["root"] = r.json()["access_token"]
        S["root_totp"] = secret

    # ------------------------------------------------------------------ B
    section("B. Institution onboarding & profile (Super Admin)")
    reg = c.post("/registrations", json={"institution_name": f"QA Alpha School {RUN}", "requested_code": f"QAA{RUN}",
                                          "contact_name": "Alpha Head", "contact_email": f"alpha.head.{RUN}@qa.example.com"})
    check("B01", "Public institution registration request accepted", reg.status_code == 201, j(reg))
    reg2 = c.post("/registrations", json={"institution_name": "QA Rejected", "requested_code": f"QAR{RUN}",
                                           "contact_name": "R", "contact_email": f"r.{RUN}@qa.example.com"})
    pend = j(c.get("/admin/registrations?status_filter=pending", headers=H(S["root"])))
    check("B02", "Super Admin sees pending registrations", isinstance(pend, list) and any(p["id"] == reg.json()["id"] for p in pend), pend)

    ap = c.post(f"/admin/registrations/{reg.json()['id']}/approve", headers=H(S["root"]),
                json={"admin_email": f"admin.a.{RUN}@qa.example.com", "admin_full_name": "Alpha Admin"})
    check("B03", "Approving a registration provisions institution + admin (temp password in dev)",
          ap.status_code == 200 and ap.json().get("debug_admin_temp_password"), j(ap))
    S["A"] = ap.json()["institution"]["id"]
    S["A_code"] = ap.json()["institution"]["code"]
    S["adminA_pw"] = ap.json()["debug_admin_temp_password"]
    again = c.post(f"/admin/registrations/{reg.json()['id']}/approve", headers=H(S["root"]),
                   json={"admin_email": f"x.{RUN}@qa.example.com", "admin_full_name": "X"})
    check("B04", "Approving an already-decided request is refused (409)", again.status_code == 409, (again.status_code, j(again)))
    rj = c.post(f"/admin/registrations/{reg2.json()['id']}/reject", headers=H(S["root"]), json={"reason": "Incomplete documents"})
    check("B05", "Rejecting a registration with a reason", rj.status_code == 204, (rj.status_code, j(rj)))
    rj0 = c.post(f"/admin/registrations/{reg2.json()['id']}/reject", headers=H(S["root"]), json={"reason": ""})
    check("B06", "Reject requires a reason (empty -> 422) / already decided", rj0.status_code in (409, 422), rj0.status_code)

    body = {"name": f"QA Beta College {RUN}", "code": f"qab{RUN}", "institution_type": "college", "affiliation": "QA University",
            "established_year": 2001, "head_name": "Dr Beta", "email": "office@beta.qa.example.com", "phone": "+91 44 1234 5678",
            "website": "beta.qa.example.com", "address_line1": "1 Beta Road", "city": "Chennai", "state": "TN",
            "postal_code": "600001", "country": "India", "time_zone": "Asia/Kolkata",
            "admin_full_name": "Beta Admin", "admin_email": f"admin.b.{RUN}@qa.example.com", "admin_password": "BetaAdmin#2026"}
    bad = dict(body); bad.pop("city")
    r = c.post("/admin/institutions", json=bad, headers=H(S["root"]))
    check("B07", "Direct create rejects missing required profile field (422)", r.status_code == 422, r.status_code)
    r = c.post("/admin/institutions", json={**body, "time_zone": "Mars/Olympus"}, headers=H(S["root"]))
    check("B08", "Direct create rejects an unknown time zone (422)", r.status_code == 422, r.status_code)
    r = c.post("/admin/institutions", json=body, headers=H(S["root"]))
    check("B09", "Super Admin creates institution with full profile + admin", r.status_code == 201 and r.json()["institution"]["code"] == f"QAB{RUN}", j(r))
    S["B"] = r.json()["institution"]["id"]
    r = c.post("/admin/institutions", json={**body, "admin_email": f"other.{RUN}@qa.example.com"}, headers=H(S["root"]))
    check("B10", "Duplicate institution code is refused (409)", r.status_code == 409, (r.status_code, j(r)))
    r = c.post("/admin/institutions", json={**body, "code": f"QAC{RUN}"}, headers=H(S["root"]))
    check("B11", "Duplicate admin email is refused (409) and no half-created institution remains",
          r.status_code == 409 and not any(i["code"] == f"QAC{RUN}" for i in j(c.get("/admin/institutions", headers=H(S["root"])))), (r.status_code, j(r)))

    prof = {k: body[k] for k in ("name", "institution_type", "affiliation", "established_year", "head_name", "email", "phone",
                                 "website", "address_line1", "city", "state", "postal_code", "country", "time_zone")}
    r = c.put(f"/admin/institutions/{S['A']}", json={**prof, "name": f"QA Alpha School {RUN}", "institution_type": "school"}, headers=H(S["root"]))
    check("B12", "Super Admin completes the profile of a registration-approved institution", r.status_code == 200 and r.json()["institution_type"] == "school", j(r))
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    r = c.put(f"/institutions/{S['A']}/logo", files={"file": ("l.png", png, "image/png")}, headers=H(S["root"]))
    check("B13", "Logo upload (PNG) succeeds", r.status_code == 200 and r.json()["has_logo"], j(r))
    r = c.put(f"/institutions/{S['A']}/logo", files={"file": ("l.svg", b"<svg onload=alert(1)/>", "image/svg+xml")}, headers=H(S["root"]))
    check("B14", "SVG logo rejected (XSS vector)", r.status_code == 400, r.status_code)

    S["adminA"] = tok(email=f"admin.a.{RUN}@qa.example.com", password=S["adminA_pw"])
    S["adminB"] = tok(email=f"admin.b.{RUN}@qa.example.com", password="BetaAdmin#2026")
    check("B15", "Provisioned admins of both institutions can sign in", True)
    r = c.post("/auth/password/change", json={"current_password": "wrong", "new_password": "AlphaAdmin#2026"}, headers=H(S["adminA"]))
    check("B16", "Password change with wrong current password is refused", r.status_code in (400, 401, 403), r.status_code)
    r = c.post("/auth/password/change", json={"current_password": S["adminA_pw"], "new_password": "AlphaAdmin#2026"}, headers=H(S["adminA"]))
    check("B17", "Admin changes temporary password", r.status_code in (200, 204), (r.status_code, j(r)))
    check("B18", "Old temp password no longer works", login(email=f"admin.a.{RUN}@qa.example.com", password=S["adminA_pw"]).status_code == 401)
    S["adminA"] = tok(email=f"admin.a.{RUN}@qa.example.com", password="AlphaAdmin#2026")
    r = c.get("/admin/institutions", headers=H(S["adminA"]))
    check("B19", "Institution Admin cannot use Super Admin endpoints (403)", r.status_code == 403, r.status_code)

    # ------------------------------------------------------------------ C
    section("C. Academic structure (Institution Admin)")
    A = S["A"]; base = f"/institutions/{A}"; hA = H(S["adminA"])
    yr = c.post(f"{base}/academic-years", json={"name": "2026-27", "is_current": True}, headers=hA)
    check("C01", "Create academic year", yr.status_code == 201, j(yr))
    S["year"] = yr.json()["id"]
    tm = c.post(f"{base}/terms", json={"academic_year_id": S["year"], "name": "Term 1"}, headers=hA)
    check("C02", "Create term in the year", tm.status_code == 201, j(tm)); S["term"] = tm.json()["id"]
    gl = c.post(f"{base}/grade-levels", json={"name": "Grade 8"}, headers=hA); S["grade"] = gl.json().get("id")
    dp = c.post(f"{base}/departments", json={"name": "Mathematics", "code": "MATH"}, headers=hA); S["dept"] = dp.json().get("id")
    co = c.post(f"{base}/courses", json={"name": "Algebra", "code": "ALG8", "department_id": S["dept"]}, headers=hA); S["course"] = co.json().get("id")
    check("C03", "Create grade level, department, course", all(x.status_code == 201 for x in (gl, dp, co)), [j(x) for x in (gl, dp, co)])
    cg1 = c.post(f"{base}/class-groups", json={"name": "8-A", "kind": "section", "grade_level_id": S["grade"], "term_id": S["term"], "course_id": S["course"]}, headers=hA)
    cg2 = c.post(f"{base}/class-groups", json={"name": "8-B", "kind": "section"}, headers=hA)
    check("C04", "Create two class groups", cg1.status_code == 201 and cg2.status_code == 201, (j(cg1), j(cg2)))
    S["cg1"], S["cg2"] = cg1.json()["id"], cg2.json()["id"]
    lst = j(c.get(f"{base}/class-groups", headers=hA))
    check("C05", "List class groups returns full rows", len(lst) == 2 and lst[0].get("grade_level_id") == S["grade"], lst)
    up = c.put(f"{base}/courses/{S['course']}", json={"name": "Algebra I", "code": "ALG8", "department_id": S["dept"]}, headers=hA)
    check("C06", "Edit course", up.status_code == 200 and up.json()["name"] == "Algebra I", j(up))
    dup = c.put(f"{base}/class-groups/{S['cg2']}", json={"name": "8-A", "kind": "section"}, headers=hA)
    check("C07", "Renaming to a duplicate name -> 409", dup.status_code == 409, (dup.status_code, j(dup)))
    # Cross-tenant FK: a term in A pointing at an academic year of B.
    yB = c.post(f"/institutions/{S['B']}/academic-years", json={"name": "B-2026"}, headers=H(S["adminB"])).json()["id"]
    x = c.put(f"{base}/terms/{S['term']}", json={"academic_year_id": yB, "name": "Term 1"}, headers=hA)
    check("C08", "Cannot link a term to another institution's year (404)", x.status_code == 404, (x.status_code, j(x)))
    x = c.post(f"{base}/terms", json={"academic_year_id": yB, "name": "Sneaky"}, headers=hA)
    check("C09", "Cannot create a term under another institution's year", x.status_code == 404, (x.status_code, j(x)))
    x = c.post(f"{base}/class-groups", json={"name": "Sneaky", "term_id": S["term"] + 100000}, headers=hA)
    check("C10", "Class group with a non-existent/foreign term is refused", x.status_code in (400, 404, 409, 422), (x.status_code, j(x)))
    tmp = c.post(f"{base}/grade-levels", json={"name": "Temp grade"}, headers=hA).json()["id"]
    d = c.delete(f"{base}/grade-levels/{tmp}", headers=hA)
    check("C11", "Delete an unused grade level (204)", d.status_code == 204, d.status_code)
    check("C12", "Deleted row is gone (second delete 404)", c.delete(f"{base}/grade-levels/{tmp}", headers=hA).status_code == 404)
    x = c.delete(f"/institutions/{S['B']}/grade-levels/{S['grade']}", headers=H(S["adminB"]))
    check("C13", "Another institution's admin cannot delete my rows", x.status_code in (403, 404), x.status_code)

    # ------------------------------------------------------------------ D
    section("D. People: invitations, self-registration, roster, assignments, enrollment")
    inv = c.post(f"{base}/invitations", json={"role": "teacher", "email": f"teacher.a.{RUN}@qa.example.com"}, headers=hA)
    check("D01", "Invite a teacher (dev token returned)", inv.status_code == 201 and inv.json().get("debug_invitation_token"), j(inv))
    acc = c.post("/invitations/accept", json={"token": inv.json()["debug_invitation_token"], "full_name": "Tara Teacher", "password": "TeacherA#2026"})
    check("D02", "Teacher accepts invitation", acc.status_code == 201, j(acc)); S["teacherA_id"] = acc.json()["user_id"]
    reuse = c.post("/invitations/accept", json={"token": inv.json()["debug_invitation_token"], "full_name": "X", "password": "Whatever#2026"})
    check("D03", "Invitation token cannot be reused", reuse.status_code == 400, (reuse.status_code, j(reuse)))
    bad_role = c.post(f"{base}/invitations", json={"role": "institution_admin", "email": f"esc.{RUN}@qa.example.com"}, headers=hA)
    check("D04", "Invitations cannot grant admin role (privilege escalation)", bad_role.status_code == 400, (bad_role.status_code, j(bad_role)))
    inv2 = c.post(f"{base}/invitations", json={"role": "teacher", "email": f"teacher2.a.{RUN}@qa.example.com"}, headers=hA)
    S["teacher2A_id"] = c.post("/invitations/accept", json={"token": inv2.json()["debug_invitation_token"], "full_name": "Uma Unassigned", "password": "TeacherA2#2026"}).json()["user_id"]
    S["teacherA"] = tok(email=f"teacher.a.{RUN}@qa.example.com", password="TeacherA#2026")
    S["teacher2A"] = tok(email=f"teacher2.a.{RUN}@qa.example.com", password="TeacherA2#2026")

    sinv = c.post(f"{base}/invitations", json={"role": "student", "register_number": "S-001"}, headers=hA)
    sacc = c.post("/invitations/accept", json={"token": sinv.json()["debug_invitation_token"], "full_name": "Sam Student", "password": "StudentA#2026"})
    check("D05", "Invite + accept a student with register number", sacc.status_code == 201, j(sacc)); S["s1_id"] = sacc.json()["user_id"]
    S["s1"] = tok(institution_code=S["A_code"], register_number="S-001", password="StudentA#2026")
    check("D06", "Student signs in with institution code + register number", True)

    sr = c.post("/students/self-register", json={"institution_code": S["A_code"], "register_number": "S-002", "full_name": "Priya Pending", "password": "StudentB#2026"})
    check("D07", "Student self-registers (pending approval)", sr.status_code == 201 and sr.json()["status"] == "pending_admin_approval", j(sr))
    S["s2_id"] = sr.json()["user_id"]
    pl = login(institution_code=S["A_code"], register_number="S-002", password="StudentB#2026")
    check("D08", "Pending student cannot sign in", pl.status_code in (401, 403), (pl.status_code, j(pl)))
    dupe = c.post("/students/self-register", json={"institution_code": S["A_code"], "register_number": "S-002", "full_name": "Dup", "password": "StudentB#2026"})
    check("D09", "Duplicate register number refused (409)", dupe.status_code == 409, dupe.status_code)
    wrong = c.post("/students/self-register", json={"institution_code": "NOPE-XYZ", "register_number": "S-9", "full_name": "N", "password": "StudentB#2026"})
    check("D10", "Unknown institution code refused (404)", wrong.status_code == 404, wrong.status_code)
    apr = c.post(f"{base}/memberships/approve", json={"user_id": S["s2_id"]}, headers=hA)
    check("D11", "Admin approves the pending student", apr.status_code == 200 and apr.json()["status"] == "active", j(apr))
    S["s2"] = tok(institution_code=S["A_code"], register_number="S-002", password="StudentB#2026")
    check("D12", "Approved student can sign in", True)
    x = c.post(f"/institutions/{S['B']}/memberships/approve", json={"user_id": S["s2_id"]}, headers=H(S["adminB"]))
    check("D13", "Another institution's admin cannot approve my student", x.status_code == 404, (x.status_code, j(x)))

    ta = c.post(f"{base}/teacher-assignments", json={"teacher_user_id": S["teacherA_id"], "class_group_id": S["cg1"]}, headers=hA)
    check("D14", "Assign teacher to class group 8-A", ta.status_code == 201, j(ta))
    x = c.post(f"{base}/teacher-assignments", json={"teacher_user_id": S["s1_id"], "class_group_id": S["cg1"]}, headers=hA)
    check("D15", "Cannot assign a student as teacher (400)", x.status_code == 400, (x.status_code, j(x)))
    e1 = c.post(f"{base}/enrollments", json={"student_user_id": S["s1_id"], "class_group_id": S["cg1"], "term_id": S["term"]}, headers=hA)
    e2 = c.post(f"{base}/enrollments", json={"student_user_id": S["s2_id"], "class_group_id": S["cg1"], "term_id": S["term"]}, headers=hA)
    check("D16", "Enroll both students in 8-A", e1.status_code == e2.status_code == 201, (j(e1), j(e2)))
    S["enr2"] = e2.json()["id"]
    x = c.post(f"{base}/enrollments", json={"student_user_id": S["teacherA_id"], "class_group_id": S["cg1"]}, headers=hA)
    check("D17", "Enrolling a non-student (teacher) as a student is refused", x.status_code in (400, 409, 422), (x.status_code, j(x)))
    i3 = c.post(f"{base}/invitations", json={"role": "student", "register_number": "S-003"}, headers=hA)
    s3 = c.post("/invitations/accept", json={"token": i3.json()["debug_invitation_token"], "full_name": "Dee Double", "password": "StudentD#2026"}).json()["user_id"]
    c.post(f"{base}/enrollments", json={"student_user_id": s3, "class_group_id": S["cg1"]}, headers=hA)
    x = c.post(f"{base}/enrollments", json={"student_user_id": s3, "class_group_id": S["cg1"]}, headers=hA)
    check("D18", "Duplicate active enrollment in the same class is refused", x.status_code in (400, 409, 422), (x.status_code, j(x)))
    S["s3"] = tok(institution_code=S["A_code"], register_number="S-003", password="StudentD#2026")
    S["s3_dup"] = x.status_code == 201
    tmpcg = c.post(f"{base}/class-groups", json={"name": f"8-Z"}, headers=hA).json()["id"]
    c.post(f"{base}/teacher-assignments", json={"teacher_user_id": S["teacher2A_id"], "class_group_id": tmpcg}, headers=hA)
    d = c.delete(f"{base}/class-groups/{tmpcg}", headers=hA)
    check("D19", "Cannot delete a class group that is in use (teacher assignment) -> 409", d.status_code == 409, (d.status_code, j(d)))
    tmpy = c.post(f"{base}/academic-years", json={"name": "Temp year"}, headers=hA).json()["id"]
    c.post(f"{base}/terms", json={"academic_year_id": tmpy, "name": "Temp term"}, headers=hA)
    d = c.delete(f"{base}/academic-years/{tmpy}", headers=hA)
    check("D19b", "Cannot delete an academic year that still has terms -> 409", d.status_code == 409, (d.status_code, j(d)))

    csv_bad = "register_number,full_name,email\nR-1,Rita Roster,rita@qa.example.com\nR-1,Dup Row,\n,No Reg,\nR-3,Bad Email,not-an-email\n"
    pv = c.post(f"{base}/roster/import", json={"csv_text": csv_bad, "class_group_code": "8-B"}, headers=hA)
    check("D20", "Roster preview reports row errors (duplicate, missing, bad email)", pv.status_code == 200 and pv.json()["error_rows"] == 3 and not pv.json()["committed"], j(pv))
    cm = c.post(f"{base}/roster/import", json={"csv_text": csv_bad, "class_group_code": "8-B", "commit": True}, headers=hA)
    check("D21", "Commit with errors does not import anything", cm.status_code == 200 and not cm.json()["committed"], j(cm))
    csv_ok = "register_number,full_name,email\nR-1,Rita Roster,rita.{0}@qa.example.com\nR-2,Ravi Roster,\n".format(RUN)
    cm = c.post(f"{base}/roster/import", json={"csv_text": csv_ok, "class_group_code": "8-B", "commit": True}, headers=hA)
    check("D22", "Clean roster commits", cm.status_code == 200 and cm.json()["committed"], j(cm))
    cm2 = c.post(f"{base}/roster/import", json={"csv_text": csv_ok, "class_group_code": "8-B", "commit": True}, headers=hA)
    check("D23", "Re-importing the same roster is idempotent (no duplicates/errors)", cm2.status_code == 200 and cm2.json()["error_rows"] == 0, j(cm2))
    x = c.post(f"{base}/roster/import", json={"csv_text": "name\nx\n"}, headers=hA)
    check("D24", "Roster with missing required columns fails cleanly", x.status_code == 200 and x.json()["status"] == "failed", j(x))
    x = c.post(f"{base}/roster/import", json={"csv_text": csv_ok, "class_group_code": "8-B"}, headers=H(S["teacherA"]))
    check("D25", "Teacher cannot import rosters (403)", x.status_code == 403, x.status_code)

    # Password reset for the teacher.
    rr = c.post("/auth/password/reset-request", json={"email": f"teacher.a.{RUN}@qa.example.com"})
    tokn = (j(rr) or {}).get("debug_reset_token") if isinstance(j(rr), dict) else None
    check("D26", "Password reset request issues a token (dev)", rr.status_code in (200, 202) and tokn, j(rr))
    rr2 = c.post("/auth/password/reset-request", json={"email": f"nobody.{RUN}@qa.example.com"})
    check("D27", "Reset request for unknown email gives the same response code (no enumeration)", rr2.status_code == rr.status_code, (rr.status_code, rr2.status_code))
    if tokn:
        cf = c.post("/auth/password/reset-confirm", json={"token": tokn, "new_password": "TeacherA#2027"})
        check("D28", "Reset confirm sets a new password", cf.status_code in (200, 204), (cf.status_code, j(cf)))
        cf2 = c.post("/auth/password/reset-confirm", json={"token": tokn, "new_password": "TeacherA#2028"})
        check("D29", "Reset token is single-use", cf2.status_code >= 400, cf2.status_code)
        S["teacherA"] = tok(email=f"teacher.a.{RUN}@qa.example.com", password="TeacherA#2027")
        check("D30", "Teacher signs in with the new password", True)

    # ------------------------------------------------------------------ E
    section("E. Question bank, review workflow, documents, AI")
    hT = H(S["teacherA"])
    tt = c.post(f"{base}/topics", json={"name": "Teacher topic", "course_id": S["course"]}, headers=hT)
    check("E00", "Syllabus topics are admin-managed (teacher gets 403) [design check]", tt.status_code == 403, (tt.status_code, j(tt)))
    tp = c.post(f"{base}/topics", json={"name": "Linear equations", "course_id": S["course"]}, headers=hA)
    ob = c.post(f"{base}/objectives", json={"topic_id": tp.json().get("id"), "description": "Solve one-variable linear equations"}, headers=hA)
    check("E01", "Admin creates topic + learning objective", tp.status_code == ob.status_code == 201, (j(tp), j(ob)))
    S["topic"] = tp.json()["id"]
    Q = {
        "single": {"type": "single_mcq", "text": f"Solve 2x + 3 = 11 [{RUN}]", "marks": 2, "difficulty": "easy", "topic_id": S["topic"],
                   "explanation": "2x = 8", "options": [{"text": "x = 4", "is_correct": True}, {"text": "x = 3"}, {"text": "x = 7"}]},
        "multi": {"type": "multi_mcq", "text": f"Which are prime? [{RUN}]", "marks": 2, "options": [{"text": "2", "is_correct": True}, {"text": "3", "is_correct": True}, {"text": "4"}]},
        "tf": {"type": "true_false", "text": f"0 is an even number [{RUN}]", "marks": 1, "options": [{"text": "True", "is_correct": True}, {"text": "False"}]},
        "num": {"type": "numerical", "text": f"What is 22/7 to 2 dp? [{RUN}]", "marks": 3, "numerical_answer": "3.14", "numerical_tolerance": "0.01"},
    }
    S["q"] = {}
    for k, qb in Q.items():
        r = c.post(f"{base}/questions", json=qb, headers=hT)
        S["q"][k] = j(r)
        check(f"E02.{k}", f"Teacher creates a valid {qb['type']} question (draft)", r.status_code == 201 and r.json()["status"] == "draft", j(r))
    invalid = {
        "single with two correct": {"type": "single_mcq", "text": "bad", "options": [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": True}]},
        "single with no correct": {"type": "single_mcq", "text": "bad", "options": [{"text": "a"}, {"text": "b"}]},
        "multi with no correct": {"type": "multi_mcq", "text": "bad", "options": [{"text": "a"}, {"text": "b"}]},
        "single with one option": {"type": "single_mcq", "text": "bad", "options": [{"text": "a", "is_correct": True}]},
        "true/false wrong labels": {"type": "true_false", "text": "bad", "options": [{"text": "Yes", "is_correct": True}, {"text": "No"}]},
        "numerical with options": {"type": "numerical", "text": "bad", "numerical_answer": "1", "options": [{"text": "1"}]},
        "numerical non-numeric": {"type": "numerical", "text": "bad", "numerical_answer": "abc"},
        "duplicate option texts": {"type": "single_mcq", "text": "bad", "options": [{"text": "a", "is_correct": True}, {"text": "A"}]},
        "empty text": {"type": "single_mcq", "text": "", "options": [{"text": "a", "is_correct": True}, {"text": "b"}]},
        "zero marks": {"type": "single_mcq", "text": "bad", "marks": 0, "options": [{"text": "a", "is_correct": True}, {"text": "b"}]},
    }
    for name, qb in invalid.items():
        r = c.post(f"{base}/questions", json=qb, headers=hT)
        check("E03", f"Rejects invalid question: {name}", r.status_code == 422, (r.status_code, j(r)))

    # Versioning on a separate question (keeps the exam pool deterministic).
    vq = c.post(f"{base}/questions", json={**Q["single"], "text": f"Version me [{RUN}]"}, headers=hT).json()
    v2 = c.post(f"{base}/questions/{vq['question_id']}/versions", json={**Q["single"], "text": f"Version me v2 [{RUN}]"}, headers=hT)
    vs = j(c.get(f"{base}/questions/{vq['question_id']}/versions", headers=hT))
    check("E04", "Editing creates version 2; version 1 kept unchanged",
          v2.status_code == 201 and v2.json()["version_no"] == 2 and any(v["version_no"] == 1 and v["text"] == f"Version me [{RUN}]" for v in vs), (j(v2), vs))

    for k in Q:
        vid = S["q"][k]["version_id"]
        r = c.post(f"{base}/versions/{vid}/submit", headers=hT)
        check(f"E05.{k}", f"Teacher submits {k} for review", r.status_code == 200 and r.json()["status"] == "in_review", j(r))
    x = c.post(f"{base}/versions/{S['q']['single']['version_id']}/review?approve=true", headers=hT)
    check("E06", "Teacher cannot approve questions (403)", x.status_code == 403, x.status_code)
    for k in Q:
        r = c.post(f"{base}/versions/{S['q'][k]['version_id']}/review?approve=true", headers=hA)
        check(f"E07.{k}", f"Admin approves {k}", r.status_code == 200 and r.json()["status"] == "approved", j(r))
    rq = c.post(f"{base}/questions", json={**Q["single"], "text": f"To reject [{RUN}]"}, headers=hT).json()
    c.post(f"{base}/versions/{rq['version_id']}/submit", headers=hT)
    r = c.post(f"{base}/versions/{rq['version_id']}/review?approve=false", headers=hA)
    check("E08", "Admin rejects a question", r.status_code == 200 and r.json()["status"] == "rejected", j(r))
    x = c.post(f"{base}/versions/{S['q']['single']['version_id']}/submit", headers=hT)
    check("E09", "An approved version cannot be re-submitted / changed in place", x.status_code in (400, 409), (x.status_code, j(x)))

    sr_ = c.post(f"{base}/questions/search", json={"type": "numerical"}, headers=hT)
    check("E10", "Search filters by type", sr_.status_code == 200 and sr_.json() and all(v["type"] == "numerical" for v in sr_.json()), j(sr_))
    sr_ = c.post(f"{base}/questions/search", json={"status": "approved"}, headers=hT)
    check("E11", "Search filters by status (4 approved)", sr_.status_code == 200 and len(sr_.json()) == 4, [(v["text"], v["status"]) for v in j(sr_)] if sr_.status_code == 200 else j(sr_))
    x = c.post(f"{base}/questions/search", json={}, headers=H(S["s1"]))
    check("E12", "Students cannot access the question bank (403)", x.status_code == 403, x.status_code)
    x = c.post(f"/institutions/{S['B']}/questions/search", json={}, headers=hT)
    check("E13", "Teacher cannot search another institution's bank (403)", x.status_code == 403, x.status_code)

    up = c.post(f"{base}/documents", files={"file": ("syllabus.pdf", b"%PDF-1.4 test", "application/pdf")}, headers=hT)
    check("E14", "Upload a PDF syllabus document", up.status_code == 201, j(up))
    x = c.post(f"{base}/documents", files={"file": ("evil.exe", b"MZ....", "application/x-msdownload")}, headers=hT)
    check("E15", "Executable upload rejected", x.status_code == 400, x.status_code)
    x = c.post(f"{base}/documents", files={"file": ("../../etc/passwd.pdf", b"%PDF-1.4", "application/pdf")}, headers=hT)
    check("E16", "Path-traversal filename is neutralised", x.status_code == 201 and "/" not in x.json()["filename"] and ".." not in x.json()["filename"].replace("..pdf", ""), j(x))
    if up.status_code == 201:
        d = c.get(f"{base}/documents/{up.json()['id']}/download", headers=hT)
        check("E17", "Staff can download the document", d.status_code == 200 and d.content.startswith(b"%PDF"), d.status_code)
        d = c.get(f"{base}/documents/{up.json()['id']}/download", headers=H(S["s1"]))
        check("E18", "Student cannot download staff documents (403)", d.status_code == 403, d.status_code)
        d = c.get(f"/institutions/{S['B']}/documents/{up.json()['id']}/download", headers=H(S["adminB"]))
        check("E19", "Other institution cannot download it via its own path (404)", d.status_code == 404, d.status_code)

    st = c.get("/ai/status", headers=hT)
    check("E20", "AI status visible to staff (mock on QA)", st.status_code == 200 and st.json()["provider"] == "mock", j(st))
    check("E21", "AI status hidden from students", c.get("/ai/status", headers=H(S["s1"])).status_code == 403)
    g = c.post(f"{base}/ai/generate", json={"question_type": "single_mcq", "count": 3, "subject": "Maths", "idempotency_key": f"k-{RUN}"}, headers=hT)
    check("E22", "AI generation stores candidates as in_review", g.status_code == 201 and g.json()["stored_count"] == 3, j(g))
    g2 = c.post(f"{base}/ai/generate", json={"question_type": "single_mcq", "count": 3, "subject": "Maths", "idempotency_key": f"k-{RUN}"}, headers=hT)
    check("E23", "Same idempotency key returns the same job (no double generation)", g2.status_code == 201 and g2.json()["id"] == g.json()["id"], (j(g), j(g2)))
    x = c.post(f"{base}/ai/generate", json={"question_type": "single_mcq", "count": 51}, headers=hT)
    check("E24", "Pool size above the cap is refused", x.status_code in (400, 422), (x.status_code, j(x)))
    x = c.post(f"{base}/ai/generate", json={"question_type": "single_mcq", "count": 2}, headers=H(S["s1"]))
    check("E25", "Students cannot trigger AI generation", x.status_code == 403, x.status_code)
    sr_ = c.post(f"{base}/questions/search", json={"status": "approved"}, headers=hT)
    check("E26", "AI candidates are not approved automatically (approved count still 4)", len(j(sr_)) == 4, len(j(sr_)))

    gg = c.post("/global/ai/generate", json={"question_type": "true_false", "count": 2, "subject": "Science"}, headers=H(S["root"]))
    check("E27", "Super Admin generates global library candidates", gg.status_code == 201 and gg.json()["is_global"], j(gg))
    x = c.post("/global/ai/generate", json={"question_type": "true_false", "count": 1}, headers=hT)
    check("E28", "Teacher cannot generate global questions (403)", x.status_code == 403, x.status_code)
    lib = c.post("/global/library/search", json={}, headers=H(S["root"]))
    gl_items = j(lib) if lib.status_code == 200 else []
    check("E29", "Central reviewer sees in-review global candidates", lib.status_code == 200 and any(v["status"] == "in_review" for v in gl_items), j(lib))
    if gl_items:
        gv = gl_items[0]["version_id"]
        r = c.post(f"/global/questions/versions/{gv}/review?approve=true", headers=H(S["root"]))
        check("E30", "Central reviewer approves a global question", r.status_code == 200, j(r))
        tl = j(c.post("/global/library/search", json={}, headers=hT))
        check("E31", "Teachers see only approved global questions", isinstance(tl, list) and tl and all(v["status"] == "approved" for v in tl), tl)
        check("E32", "Global library never exposes private institution questions",
              all(v["text"].find(RUN) == -1 for v in tl), [v["text"] for v in tl])

    # ------------------------------------------------------------------ F
    section("F. Exam authoring, approval & scheduling")
    dist = [{"count": 1, "type": "single_mcq"}, {"count": 1, "type": "multi_mcq"}, {"count": 1, "type": "true_false"}, {"count": 1, "type": "numerical"}]
    ex = {"title": f"QA Algebra Test {RUN}", "class_group_id": S["cg1"], "course_id": S["course"], "duration_minutes": 30, "attempt_limit": 1,
          "distribution": dist, "randomize": True, "result_release_rule": "manual", "timezone": "Asia/Kolkata"}
    r = c.post(f"{base}/exams", json=ex, headers=hT)
    check("F01", "Teacher drafts an exam for an assigned class", r.status_code == 201 and r.json()["status"] == "draft", j(r))
    S["exam"] = r.json()["id"]
    x = c.post(f"{base}/exams", json={**ex, "class_group_id": S["cg2"]}, headers=hT)
    check("F02", "Teacher cannot target an unassigned class (403)", x.status_code == 403, (x.status_code, j(x)))
    x = c.post(f"{base}/exams", json=ex, headers=H(S["teacher2A"]))
    check("F03", "Unassigned teacher cannot create exams for 8-A", x.status_code == 403, (x.status_code, j(x)))
    av = c.get(f"{base}/class-groups/available-for-exam", headers=hT)
    check("F04", "Teacher's available classes list only assigned groups", av.status_code == 200 and [g["id"] for g in av.json()] == [S["cg1"]], j(av))
    x = c.post(f"{base}/exams", json={**ex, "duration_minutes": 0}, headers=hT)
    check("F05", "Invalid duration rejected (422)", x.status_code == 422, x.status_code)
    upd = c.put(f"{base}/exams/{S['exam']}", json={**ex, "duration_minutes": 45}, headers=hT)
    check("F06", "Teacher edits own draft", upd.status_code == 200 and upd.json()["duration_minutes"] == 45, j(upd))
    sb = c.post(f"{base}/exams/{S['exam']}/submit", headers=hT)
    check("F07", "Teacher submits exam for approval", sb.status_code == 200 and sb.json()["status"] == "awaiting_approval", j(sb))
    for act in ("approve", "schedule"):
        body_ = {"start_at": now.isoformat(), "end_at": (now + dt.timedelta(hours=2)).isoformat()} if act == "schedule" else None
        x = c.post(f"{base}/exams/{S['exam']}/{act}", json=body_, headers=hT)
        check("F08", f"Teacher cannot {act} (403)", x.status_code == 403, (x.status_code, j(x)))
    x = c.post(f"{base}/exams/{S['exam']}/schedule", json={"start_at": now.isoformat(), "end_at": (now + dt.timedelta(hours=2)).isoformat()}, headers=hA)
    check("F09", "Cannot schedule before approval (state machine)", x.status_code == 409, (x.status_code, j(x)))

    big = c.post(f"{base}/exams", json={**ex, "title": f"Too big {RUN}", "distribution": [{"count": 9, "type": "single_mcq"}]}, headers=hT).json()
    c.post(f"{base}/exams/{big['id']}/submit", headers=hT)
    x = c.post(f"{base}/exams/{big['id']}/approve", headers=hA)
    check("F10", "Approval blocked when the approved question pool is too small", x.status_code in (400, 409, 422), (x.status_code, j(x)))
    x = c.post(f"{base}/exams/{big['id']}/reject", headers=hA)
    check("F11", "Admin rejects (sends back) an exam", x.status_code == 200 and x.json()["status"] == "draft", j(x))

    apx = c.post(f"{base}/exams/{S['exam']}/approve", headers=hA)
    check("F12", "Admin approves: pool selected and config frozen", apx.status_code == 200 and apx.json()["status"] == "approved" and apx.json()["frozen"] and apx.json()["num_questions"] == 4, j(apx))
    x = c.put(f"{base}/exams/{S['exam']}", json={**ex, "title": "changed"}, headers=hT)
    check("F13", "Approved (frozen) exam cannot be edited", x.status_code in (403, 409), (x.status_code, j(x)))
    pv = c.get(f"{base}/exams/{S['exam']}/preview", headers=hT)
    leaks = has_key_leak(j(pv))
    check("F14", "Staff preview contains no answer keys", pv.status_code == 200 and not leaks, leaks or j(pv))
    x = c.post(f"{base}/exams/{S['exam']}/schedule", json={"start_at": (now + dt.timedelta(hours=2)).isoformat(), "end_at": now.isoformat()}, headers=hA)
    check("F15", "Schedule with end before start is rejected", x.status_code in (400, 409, 422), (x.status_code, j(x)))
    sc = c.post(f"{base}/exams/{S['exam']}/schedule", json={"start_at": (now - dt.timedelta(minutes=1)).isoformat(),
                                                            "end_at": (now + dt.timedelta(hours=2)).isoformat(), "timezone": "Asia/Kolkata"}, headers=hA)
    check("F16", "Admin schedules the exam (stored UTC, zone kept)", sc.status_code == 200 and sc.json()["status"] == "scheduled" and sc.json()["timezone"] == "Asia/Kolkata", j(sc))
    x = c.get(f"{base}/exams/{S['exam']}", headers=H(S["adminB"]))
    check("F17", "Other institution cannot read the exam", x.status_code in (403, 404), x.status_code)

    # ------------------------------------------------------------------ G
    section("G. Student exam delivery & attempts")
    hS1, hS2 = H(S["s1"]), H(S["s2"])
    se = c.get("/student/exams", headers=hS1)
    mine = [e for e in j(se) if e["id"] == S["exam"]] if se.status_code == 200 else []
    check("G01", "Enrolled student sees the scheduled exam", mine and mine[0]["can_start"], j(se))
    # Transfer s2 out of 8-A -> no longer eligible.
    tr = c.post(f"{base}/enrollments/transfer", json={"enrollment_id": S["enr2"], "new_class_group_id": S["cg2"]}, headers=hA)
    check("G02", "Admin transfers student 2 to 8-B (history preserved)", tr.status_code == 201, j(tr))
    x = c.post(f"/exams/{S['exam']}/attempts/start", headers=hS2)
    check("G03", "Transferred (no longer enrolled) student cannot start", x.status_code == 403, (x.status_code, j(x)))
    rB = c.post(f"/institutions/{S['B']}/invitations", json={"role": "student", "register_number": "B-1"}, headers=H(S["adminB"]))
    c.post("/invitations/accept", json={"token": rB.json()["debug_invitation_token"], "full_name": "Bob Beta", "password": "StudentBB#2026"})
    S["sB"] = tok(institution_code=f"QAB{RUN}", register_number="B-1", password="StudentBB#2026")
    x = c.post(f"/exams/{S['exam']}/attempts/start", headers=H(S["sB"]))
    check("G04", "Student of another institution cannot start the exam", x.status_code in (403, 404), (x.status_code, j(x)))
    check("G05", "Other institution's student does not see the exam", all(e["id"] != S["exam"] for e in j(c.get("/student/exams", headers=H(S["sB"])))))
    x = c.post(f"/exams/{S['exam']}/attempts/start", headers=hT)
    check("G06", "Teacher cannot take the exam as a student", x.status_code in (403, 404), (x.status_code, j(x)))

    st_ = c.post(f"/exams/{S['exam']}/attempts/start", headers=hS1)
    check("G07", "Student starts an attempt", st_.status_code in (200, 201), j(st_))
    att = st_.json(); S["att"] = att["id"]
    leaks = has_key_leak(att)
    check("G08", "Attempt payload has NO answer keys / explanations", not leaks, leaks)
    check("G09", "Attempt has 4 questions and a server deadline", len(att["questions"]) == 4 and att.get("deadline_at"), att)
    again = c.post(f"/exams/{S['exam']}/attempts/start", headers=hS1)
    check("G10", "Starting again resumes the same attempt (no duplicate)", again.status_code in (200, 201) and again.json()["id"] == att["id"], j(again))
    check("G11", "Resumed attempt keeps the same question order (snapshot)",
          [q["question_version_id"] for q in again.json()["questions"]] == [q["question_version_id"] for q in att["questions"]])

    by_type = {q["type"]: q for q in att["questions"]}
    def opt(q, text):
        return next(o["id"] for o in q["options"] if o["text"] == text)
    qs, qm, qt, qn = by_type["single_mcq"], by_type["multi_mcq"], by_type["true_false"], by_type["numerical"]
    a = c.put(f"/attempts/{S['att']}/answers/{qs['question_version_id']}", json={"selected_option_ids": [opt(qs, "x = 3")]}, headers=hS1)
    check("G12", "Autosave an answer", a.status_code == 200 and a.json().get("answer_version") == 1, j(a))
    a2 = c.put(f"/attempts/{S['att']}/answers/{qs['question_version_id']}", json={"selected_option_ids": [opt(qs, "x = 4")]}, headers=hS1)
    check("G13", "Changing an answer bumps answer_version (last write wins)", a2.status_code == 200 and a2.json().get("answer_version") == 2, j(a2))
    x = c.put(f"/attempts/{S['att']}/answers/{qs['question_version_id']}", json={"selected_option_ids": [opt(qs, "x = 4"), opt(qs, "x = 7")]}, headers=hS1)
    check("G14", "Two selections on a single-answer question rejected", x.status_code == 400, (x.status_code, j(x)))
    x = c.put(f"/attempts/{S['att']}/answers/{qs['question_version_id']}", json={"selected_option_ids": [opt(qm, "2")]}, headers=hS1)
    check("G15", "Option from another question rejected", x.status_code == 400, (x.status_code, j(x)))
    x = c.put(f"/attempts/{S['att']}/answers/999999", json={"selected_option_ids": []}, headers=hS1)
    check("G16", "Answer for a question not in the attempt rejected", x.status_code in (400, 404), (x.status_code, j(x)))
    x = c.put(f"/attempts/{S['att']}/answers/{qn['question_version_id']}", json={"numerical_value": "abc"}, headers=hS1)
    check("G17", "Non-numeric numerical answer rejected", x.status_code in (400, 422), (x.status_code, j(x)))
    c.put(f"/attempts/{S['att']}/answers/{qm['question_version_id']}", json={"selected_option_ids": [opt(qm, "2")]}, headers=hS1)  # partial -> 0
    c.put(f"/attempts/{S['att']}/answers/{qt['question_version_id']}", json={"selected_option_ids": [opt(qt, "True")]}, headers=hS1)
    c.put(f"/attempts/{S['att']}/answers/{qn['question_version_id']}", json={"numerical_value": "3.145"}, headers=hS1)
    x = c.get(f"/attempts/{S['att']}", headers=hS2)
    check("G18", "Another student cannot read my attempt", x.status_code in (403, 404), x.status_code)
    x = c.put(f"/attempts/{S['att']}/answers/{qt['question_version_id']}", json={"selected_option_ids": [opt(qt, "False")]}, headers=hS2)
    check("G19", "Another student cannot write to my attempt", x.status_code in (403, 404), x.status_code)
    res = c.get(f"/attempts/{S['att']}", headers=hS1)
    saved = {q["question_version_id"]: q.get("answer") for q in res.json()["questions"]}
    check("G20", "Resumed attempt returns my saved answers", all(saved.values()), saved)
    sub = c.post(f"/attempts/{S['att']}/submit", headers=hS1)
    check("G21", "Student submits the attempt", sub.status_code == 200 and sub.json()["status"] in ("submitted", "auto_submitted"), j(sub))
    sub2 = c.post(f"/attempts/{S['att']}/submit", headers=hS1)
    check("G22", "Duplicate submit is idempotent (same submitted_at)", sub2.status_code == 200 and sub2.json().get("submitted_at") == sub.json().get("submitted_at"), (j(sub), j(sub2)))
    x = c.put(f"/attempts/{S['att']}/answers/{qt['question_version_id']}", json={"selected_option_ids": [opt(qt, "False")]}, headers=hS1)
    check("G23", "Cannot change answers after submit (409)", x.status_code == 409, (x.status_code, j(x)))
    x = c.post(f"/exams/{S['exam']}/attempts/start", headers=hS1)
    check("G24", "Attempt limit enforced (1 attempt)", x.status_code == 403, (x.status_code, j(x)))
    x = c.get(f"/attempts/{S['att']}/result", headers=hS1)
    check("G25", "Result hidden before the admin publishes", x.status_code in (403, 404, 409), (x.status_code, j(x)))

    if S.get("s3_dup"):
        x = c.get("/student/exams", headers=H(S["s3"]))
        check("G26", "Impact of D18: student with a duplicate enrollment can still list exams", x.status_code == 200, (x.status_code, j(x)))

    # ------------------------------------------------------------------ H
    section("H. Scoring, result release, corrections & reports")
    x = c.post(f"{base}/exams/{S['exam']}/score", headers=hT)
    check("H01", "Teacher cannot run official scoring (admin only)", x.status_code == 403, (x.status_code, j(x)))
    s1 = c.post(f"{base}/exams/{S['exam']}/score", headers=hA)
    check("H02", "Admin scores the exam", s1.status_code == 200, j(s1))
    rep = c.get(f"{base}/exams/{S['exam']}/report", headers=hA)
    row = None
    if rep.status_code == 200:
        rows = rep.json().get("rows") or rep.json().get("attempts") or []
        row = next((r_ for r_ in rows if r_.get("attempt_id") == S["att"]), rows[0] if rows else None)
    score = (row or {}).get("awarded_marks", (row or {}).get("score"))
    check("H03", "Deterministic score = 6/8 (single 2 + multi partial 0 + T/F 1 + numerical within tol 3)", score == 6, row or j(rep))
    s2 = c.post(f"{base}/exams/{S['exam']}/score", headers=hA)
    rep2 = j(c.get(f"{base}/exams/{S['exam']}/report", headers=hA))
    rows2 = rep2.get("rows") or rep2.get("attempts") or [] if isinstance(rep2, dict) else []
    check("H04", "Re-scoring is reproducible (same score)", s2.status_code == 200 and any(r_.get("awarded_marks", r_.get("score")) == 6 for r_ in rows2), rep2)
    csvr = c.get(f"{base}/exams/{S['exam']}/report.csv", headers=hA)
    check("H05", "CSV export downloads", csvr.status_code == 200 and "text/csv" in csvr.headers.get("content-type", "") and len(csvr.text.splitlines()) >= 2, (csvr.status_code, csvr.text[:200]))
    formula = any(line.split(",")[0:1] and line.split(",")[0].startswith(("=", "+", "-", "@")) for line in csvr.text.splitlines()[1:])
    check("H06", "CSV cells are not spreadsheet formulas (CSV injection)", not formula, csvr.text[:300])
    x = c.get(f"{base}/exams/{S['exam']}/report", headers=hT)
    check("H07", "Assigned teacher can view the class report", x.status_code == 200, x.status_code)
    x = c.get(f"{base}/exams/{S['exam']}/report", headers=H(S["teacher2A"]))
    check("H08", "Unassigned teacher cannot view the report", x.status_code == 403, x.status_code)
    x = c.get(f"{base}/exams/{S['exam']}/report", headers=hS1)
    check("H09", "Student cannot view the class report", x.status_code == 403, x.status_code)
    x = c.get(f"/admin/institutions/{A}/exams/{S['exam']}/report", headers=H(S["root"]))
    check("H10", "Super Admin cross-tenant report (audited path)", x.status_code == 200, x.status_code)
    x = c.get(f"/admin/institutions/{A}/exams/{S['exam']}/report", headers=hA)
    check("H11", "Institution Admin cannot use the Super Admin report path", x.status_code == 403, x.status_code)

    pub = c.post(f"{base}/exams/{S['exam']}/publish-results", headers=hA)
    check("H12", "Admin publishes results", pub.status_code == 200 and pub.json()["results_published"], j(pub))
    rs = c.get(f"/attempts/{S['att']}/result", headers=hS1)
    check("H13", "Student sees own released result", rs.status_code == 200, j(rs))
    leaks = has_key_leak(j(rs))
    check("H14", "Released result does not reveal correct answers/explanations", not leaks, leaks)
    x = c.get(f"/attempts/{S['att']}/result", headers=hS2)
    check("H15", "Another student cannot see my result", x.status_code in (403, 404), x.status_code)
    x = c.post(f"{base}/exams/{S['exam']}/score", headers=hA)
    check("H16", "Re-scoring after publish is blocked", x.status_code in (400, 409), (x.status_code, j(x)))
    x = c.post(f"{base}/attempts/{S['att']}/correct", json={"awarded_marks": 7, "reason": ""}, headers=hA)
    check("H17", "Correction without a reason is refused", x.status_code == 422, (x.status_code, j(x)))
    x = c.post(f"{base}/attempts/{S['att']}/correct", json={"awarded_marks": 99, "reason": "typo"}, headers=hA)
    check("H18", "Correction above max marks is refused", x.status_code in (400, 409, 422), (x.status_code, j(x)))
    x = c.post(f"{base}/attempts/{S['att']}/correct", json={"awarded_marks": -1, "reason": "typo"}, headers=hA)
    check("H19", "Negative correction is refused", x.status_code in (400, 409, 422), (x.status_code, j(x)))
    x = c.post(f"{base}/attempts/{S['att']}/correct", json={"awarded_marks": 7, "reason": "Re-marked multi-select after appeal"}, headers=hA)
    check("H20", "Audited correction with reason", x.status_code == 200 and x.json()["awarded_marks"] == 7, j(x))
    x = c.post(f"{base}/attempts/{S['att']}/correct", json={"awarded_marks": 8, "reason": "x"}, headers=hT)
    check("H21", "Teacher cannot apply corrections", x.status_code == 403, x.status_code)
    cen = c.get(f"{base}/reports/enrollment?census_date={now.date().isoformat()}", headers=hA)
    check("H22", "Enrollment census report", cen.status_code == 200, j(cen))

    # ------------------------------------------------------------------ I
    section("I. Cross-tenant isolation sweep & institution lifecycle")
    hB = H(S["adminB"])
    probes = [("GET", f"{base}/academic-years"), ("GET", f"{base}/class-groups"), ("GET", f"{base}/terms"),
              ("POST", f"{base}/questions/search"), ("GET", f"{base}/exams/{S['exam']}"), ("GET", f"{base}/exams/{S['exam']}/report"),
              ("GET", f"{base}/exams/{S['exam']}/report.csv"), ("GET", f"/institutions/{A}/profile"), ("GET", f"/institutions/{A}/logo"),
              ("POST", f"{base}/class-groups"), ("POST", f"{base}/invitations"), ("GET", f"{base}/reports/enrollment?census_date=2026-01-01")]
    leaked = []
    for m, p in probes:
        r = c.request(m, p, headers=hB, json={"name": "x", "role": "teacher"} if m == "POST" else None)
        if r.status_code not in (403, 404):
            leaked.append((m, p, r.status_code))
    check("I01", f"Admin of B is denied on {len(probes)} of A's endpoints", not leaked, leaked)
    leaked = []
    for who in ("s1", "teacherA"):
        for m, p in [("GET", f"/institutions/{S['B']}/profile"), ("GET", f"/institutions/{S['B']}/class-groups")]:
            r = c.request(m, p, headers=H(S[who]))
            if r.status_code not in (403, 404):
                leaked.append((who, p, r.status_code))
    check("I02", "Members of A are denied B's data", not leaked, leaked)
    ctx = c.get(f"/auth/tenant/{S['B']}/context", headers=hA)
    check("I03", "Tenant context for a foreign institution is denied", ctx.status_code == 403, ctx.status_code)
    prof_ = c.get(f"/institutions/{A}/profile", headers=hS1)
    check("I04", "Student sees own institution profile", prof_.status_code == 200 and prof_.json()["id"] == A, j(prof_))

    dis = c.post(f"/admin/institutions/{A}/disable", headers=H(S["root"]))
    check("I05", "Super Admin disables institution A", dis.status_code == 200 and dis.json()["status"] == "disabled", j(dis))
    r = login(email=f"admin.a.{RUN}@qa.example.com", password="AlphaAdmin#2026")
    check("I06", "Users of a DISABLED institution cannot sign in", r.status_code in (401, 403), (r.status_code, "login succeeded" if r.status_code == 200 else j(r)))
    r = c.get(f"{base}/academic-years", headers=hA)
    check("I07", "Existing sessions of a DISABLED institution are blocked", r.status_code in (401, 403), (r.status_code, "API still served"))
    r = c.post(f"/exams/{S['exam']}/attempts/start", headers=hS1)
    se = c.get("/student/exams", headers=hS1)
    check("I08", "Students of a DISABLED institution cannot use exams", se.status_code in (401, 403), (se.status_code, j(se)))
    sr_ = c.post("/students/self-register", json={"institution_code": S["A_code"], "register_number": "S-777", "full_name": "Late", "password": "StudentL#2026"})
    check("I09", "Self-registration into a DISABLED institution is refused", sr_.status_code in (400, 403, 404, 409), (sr_.status_code, j(sr_)))
    en = c.post(f"/admin/institutions/{A}/enable", headers=H(S["root"]))
    check("I10", "Super Admin re-enables institution A", en.status_code == 200 and en.json()["status"] == "active", j(en))

    # ------------------------------------------------------------------ J
    section("J. Reliability: timer expiry, concurrent submit, tolerance edges")
    import threading
    x = c.post(f"{base}/class-groups", json={"name": "Sneaky-2", "term_id": c.get(f"/institutions/{S['B']}/terms", headers=hB).json()[0]["id"] if c.get(f"/institutions/{S['B']}/terms", headers=hB).json() else None}, headers=hA)
    tB = c.post(f"/institutions/{S['B']}/terms", json={"academic_year_id": yB, "name": "B-T1"}, headers=hB).json()["id"]
    x = c.post(f"{base}/class-groups", json={"name": "Sneaky-3", "term_id": tB}, headers=hA)
    check("J01", "Class group cannot be linked to ANOTHER institution's term on create", x.status_code in (400, 403, 404, 422), (x.status_code, j(x)))

    def new_student(reg):
        i = c.post(f"{base}/invitations", json={"role": "student", "register_number": reg}, headers=hA)
        uid = c.post("/invitations/accept", json={"token": i.json()["debug_invitation_token"], "full_name": f"Student {reg}", "password": "StudentX#2026"}).json()["user_id"]
        c.post(f"{base}/enrollments", json={"student_user_id": uid, "class_group_id": S["cg1"]}, headers=hA)
        return tok(institution_code=S["A_code"], register_number=reg, password="StudentX#2026")

    def ready_exam(title, minutes, dist, end_minutes=60):
        e = c.post(f"{base}/exams", json={"title": title, "class_group_id": S["cg1"], "duration_minutes": minutes, "attempt_limit": 1,
                                          "distribution": dist}, headers=hT).json()
        c.post(f"{base}/exams/{e['id']}/submit", headers=hT)
        c.post(f"{base}/exams/{e['id']}/approve", headers=hA)
        n = dt.datetime.now(dt.timezone.utc)
        r = c.post(f"{base}/exams/{e['id']}/schedule", json={"start_at": (n - dt.timedelta(minutes=1)).isoformat(),
                                                              "end_at": (n + dt.timedelta(minutes=end_minutes)).isoformat()}, headers=hA)
        return e["id"], r.status_code

    # Concurrent double-submit.
    e2, sc_ = ready_exam(f"Concurrency {RUN}", 30, [{"count": 1, "type": "true_false"}])
    s4 = new_student("S-004")
    a4 = c.post(f"/exams/{e2}/attempts/start", headers=H(s4)).json()
    outs = []
    def sub_():
        with httpx.Client(base_url=BASE, timeout=30) as cc:
            r_ = cc.post(f"/attempts/{a4['id']}/submit", headers=H(s4))
            outs.append((r_.status_code, r_.json().get("submitted_at") if r_.status_code == 200 else r_.text))
    ts = [threading.Thread(target=sub_) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    check("J02", "6 concurrent submits -> all succeed with ONE submission time", all(o[0] == 200 for o in outs) and len({o[1] for o in outs}) == 1, outs)

    # Concurrent autosaves keep a monotonic version.
    e3, _ = ready_exam(f"Autosave race {RUN}", 30, [{"count": 1, "type": "single_mcq"}])
    s5 = new_student("S-005")
    a5 = c.post(f"/exams/{e3}/attempts/start", headers=H(s5)).json()
    q5 = a5["questions"][0]
    outs = []
    def save_(oid):
        with httpx.Client(base_url=BASE, timeout=30) as cc:
            r_ = cc.put(f"/attempts/{a5['id']}/answers/{q5['question_version_id']}", json={"selected_option_ids": [oid]}, headers=H(s5))
            outs.append(r_.status_code if r_.status_code != 200 else r_.json()["answer_version"])
    ts = [threading.Thread(target=save_, args=(q5["options"][i % len(q5["options"])]["id"],)) for i in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    check("J03", "8 concurrent autosaves -> no errors, versions unique", all(isinstance(o, int) and o < 400 for o in outs) and len(set(outs)) == len(outs), outs)

    # Concurrent "Start exam" (double-click) -> exactly one attempt.
    e5, _ = ready_exam(f"Start race {RUN}", 30, [{"count": 1, "type": "true_false"}])
    s7 = new_student("S-007")
    outs = []
    def start_():
        with httpx.Client(base_url=BASE, timeout=30) as cc:
            r_ = cc.post(f"/exams/{e5}/attempts/start", headers=H(s7))
            outs.append(r_.json().get("id") if r_.status_code in (200, 201) else r_.status_code)
    ts = [threading.Thread(target=start_) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    check("J08", "6 concurrent 'Start exam' clicks -> one attempt, no errors", len(set(outs)) == 1 and all(isinstance(o, int) and o < 100000 for o in outs), outs)

    # Timer expiry -> auto-submit (1-minute exam).
    e4, _ = ready_exam(f"Expiry {RUN}", 1, [{"count": 1, "type": "numerical"}])
    s6 = new_student("S-006")
    a6 = c.post(f"/exams/{e4}/attempts/start", headers=H(s6)).json()
    c.put(f"/attempts/{a6['id']}/answers/{a6['questions'][0]['question_version_id']}", json={"numerical_value": "3.14"}, headers=H(s6))
    print("   ...waiting 65s for the attempt timer to expire")
    time.sleep(65)
    late = c.put(f"/attempts/{a6['id']}/answers/{a6['questions'][0]['question_version_id']}", json={"numerical_value": "9"}, headers=H(s6))
    check("J04", "Answers after the deadline are refused", late.status_code == 409, (late.status_code, j(late)))
    g6 = c.get(f"/attempts/{a6['id']}", headers=H(s6)).json()
    check("J05", "Expired attempt is auto-submitted on next request, answers kept", g6["status"] in ("auto_submitted", "submitted", "expired") and g6["questions"][0].get("answer"), g6)
    c.post(f"{base}/exams/{e4}/score", headers=hA)
    rep6 = j(c.get(f"{base}/exams/{e4}/report", headers=hA))
    rows6 = (rep6.get("rows") or rep6.get("attempts") or []) if isinstance(rep6, dict) else []
    check("J06", "Auto-submitted attempt is scored from autosaved answer (3/3)", any(r_.get("awarded_marks", r_.get("score")) == 3 for r_ in rows6), rep6)

    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))
    from app.services.scoring_service import _numeric_match
    edges = {("3.13", "3.14", "0.01"): True, ("3.15", "3.14", "0.01"): True, ("0.3", "0.1", "0.2"): True, ("3.16", "3.14", "0.01"): False}
    got = {k: _numeric_match(*k) for k in edges}
    check("J07", "Numerical tolerance is inclusive at the boundary (no float error)", got == edges, {str(k): v for k, v in got.items()})

except Exception as exc:  # noqa: BLE001
    results.append({"area": area, "id": "CRASH", "desc": "Suite aborted", "ok": False, "detail": traceback.format_exc()[-1500:]})
    print("SUITE CRASHED:\n", traceback.format_exc())

passed = sum(r["ok"] for r in results)
print(f"\nTOTAL {passed}/{len(results)} passed, {len(results) - passed} failed")
json.dump(results, open(OUT, "w", encoding="utf-8"), indent=1)
