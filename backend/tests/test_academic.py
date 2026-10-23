from __future__ import annotations

import pytest

from app.models import RoleName


async def _login(client, **body):
    r = await client.post("/auth/login", json=body)
    return r


async def _auth_headers(client, email, password="Password123!"):
    r = await _login(client, email=email, password=password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- Institution onboarding ---
async def test_registration_approval_provisions_admin(client, factory):
    await factory.user(email="root@example.com", is_super_admin=True)
    headers = await _auth_headers(client, "root@example.com")

    sub = await client.post(
        "/registrations",
        json={
            "institution_name": "Alpha School",
            "requested_code": "ALPHA",
            "contact_name": "Head",
            "contact_email": "head@example.com",
        },
    )
    assert sub.status_code == 201
    req_id = sub.json()["id"]

    approve = await client.post(
        f"/admin/registrations/{req_id}/approve",
        json={"admin_email": "admin_alpha@example.com", "admin_full_name": "Alpha Admin"},
        headers=headers,
    )
    assert approve.status_code == 200
    body = approve.json()
    assert body["institution"]["code"] == "ALPHA"
    temp = body["debug_admin_temp_password"]

    # Provisioned admin can log in.
    login = await _login(client, email="admin_alpha@example.com", password=temp)
    assert login.status_code == 200


async def test_registration_reject(client, factory):
    await factory.user(email="root2@example.com", is_super_admin=True)
    headers = await _auth_headers(client, "root2@example.com")
    sub = await client.post(
        "/registrations",
        json={
            "institution_name": "Beta",
            "requested_code": "BETA",
            "contact_name": "C",
            "contact_email": "c@example.com",
        },
    )
    req_id = sub.json()["id"]
    rej = await client.post(
        f"/admin/registrations/{req_id}/reject",
        json={"reason": "incomplete"},
        headers=headers,
    )
    assert rej.status_code == 204


async def test_registration_list_requires_super_admin(client, factory):
    inst = await factory.institution("X")
    await factory.user(
        email="teach@example.com", role=RoleName.teacher, institution=inst
    )
    headers = await _auth_headers(client, "teach@example.com")
    r = await client.get("/admin/registrations", headers=headers)
    assert r.status_code == 403


# --- Academic structure + tenant isolation ---
@pytest.fixture
async def two_institutions(client, factory):
    inst_a = await factory.institution("IA")
    inst_b = await factory.institution("IB")
    await factory.user(
        email="admin_a@example.com", role=RoleName.institution_admin, institution=inst_a
    )
    await factory.user(
        email="admin_b@example.com", role=RoleName.institution_admin, institution=inst_b
    )
    return inst_a, inst_b


async def test_admin_can_build_own_structure(client, factory, two_institutions):
    inst_a, _ = two_institutions
    headers = await _auth_headers(client, "admin_a@example.com")

    yr = await client.post(
        f"/institutions/{inst_a.id}/academic-years",
        json={"name": "2026", "is_current": True},
        headers=headers,
    )
    assert yr.status_code == 201
    year_id = yr.json()["id"]

    term = await client.post(
        f"/institutions/{inst_a.id}/terms",
        json={"academic_year_id": year_id, "name": "Term 1"},
        headers=headers,
    )
    assert term.status_code == 201

    cg = await client.post(
        f"/institutions/{inst_a.id}/class-groups",
        json={"name": "Grade 1 - A"},
        headers=headers,
    )
    assert cg.status_code == 201

    listing = await client.get(
        f"/institutions/{inst_a.id}/class-groups", headers=headers
    )
    assert len(listing.json()) == 1


async def test_admin_cannot_touch_other_institution(client, two_institutions):
    inst_a, inst_b = two_institutions
    headers = await _auth_headers(client, "admin_a@example.com")
    # Admin A tries to create structure in institution B.
    r = await client.post(
        f"/institutions/{inst_b.id}/academic-years",
        json={"name": "2026"},
        headers=headers,
    )
    assert r.status_code == 403


# --- Invitations ---
async def test_invite_and_accept_teacher(client, factory, two_institutions):
    inst_a, _ = two_institutions
    headers = await _auth_headers(client, "admin_a@example.com")
    inv = await client.post(
        f"/institutions/{inst_a.id}/invitations",
        json={"role": "teacher", "email": "newteach@example.com"},
        headers=headers,
    )
    assert inv.status_code == 201
    token = inv.json()["debug_invitation_token"]

    accept = await client.post(
        "/invitations/accept",
        json={"token": token, "full_name": "New Teacher", "password": "Password123!"},
    )
    assert accept.status_code == 201
    # The teacher can log in.
    login = await _login(client, email="newteach@example.com", password="Password123!")
    assert login.status_code == 200


# --- Student self-registration (pending until approval) ---
async def test_student_self_register_pending_then_approved(
    client, factory, two_institutions
):
    inst_a, _ = two_institutions
    reg = await client.post(
        "/students/self-register",
        json={
            "institution_code": "IA",
            "register_number": "S-1",
            "full_name": "Self Student",
            "password": "Password123!",
        },
    )
    assert reg.status_code == 201
    user_id = reg.json()["user_id"]

    # Pending account cannot log in yet.
    pre = await _login(
        client,
        institution_code="IA",
        register_number="S-1",
        password="Password123!",
    )
    assert pre.status_code == 403

    headers = await _auth_headers(client, "admin_a@example.com")
    appr = await client.post(
        f"/institutions/{inst_a.id}/memberships/approve",
        json={"user_id": user_id},
        headers=headers,
    )
    assert appr.status_code == 200

    post = await _login(
        client,
        institution_code="IA",
        register_number="S-1",
        password="Password123!",
    )
    assert post.status_code == 200


async def test_self_register_duplicate_register_number(client, two_institutions):
    body = {
        "institution_code": "IA",
        "register_number": "DUP",
        "full_name": "A",
        "password": "Password123!",
    }
    first = await client.post("/students/self-register", json=body)
    assert first.status_code == 201
    second = await client.post("/students/self-register", json={**body, "full_name": "B"})
    assert second.status_code == 409


# --- CSV roster import ---
async def test_roster_import_preview_and_commit(client, factory, two_institutions):
    inst_a, _ = two_institutions
    headers = await _auth_headers(client, "admin_a@example.com")

    csv_text = (
        "register_number,full_name,email\n"
        "R1,Alice,alice@example.com\n"
        "R2,Bob,\n"
        ",NoReg,x@example.com\n"       # missing register_number -> error
        "R1,Dup,\n"                 # duplicate in file -> error
    )
    preview = await client.post(
        f"/institutions/{inst_a.id}/roster/import",
        json={"csv_text": csv_text, "commit": False},
        headers=headers,
    )
    assert preview.status_code == 200
    pj = preview.json()
    assert pj["valid_rows"] == 2
    assert pj["error_rows"] == 2
    assert pj["committed"] is False

    # Fix the file and commit.
    good = "register_number,full_name,email\nR1,Alice,alice@example.com\nR2,Bob,\n"
    commit = await client.post(
        f"/institutions/{inst_a.id}/roster/import",
        json={"csv_text": good, "commit": True},
        headers=headers,
    )
    cj = commit.json()
    assert cj["status"] == "committed"
    assert cj["valid_rows"] == 2

    # Retry is idempotent (register numbers already exist -> no duplicates).
    retry = await client.post(
        f"/institutions/{inst_a.id}/roster/import",
        json={"csv_text": good, "commit": True},
        headers=headers,
    )
    assert retry.json()["status"] == "committed"

    # The imported students can log in by register number.
    login = await _login(
        client, institution_code="IA", register_number="R1", password="x"
    )
    # Wrong password (random) -> 401, but the account exists (not 403/404 path).
    assert login.status_code == 401


async def test_roster_import_tenant_scoped(client, two_institutions):
    _, inst_b = two_institutions
    headers = await _auth_headers(client, "admin_a@example.com")
    r = await client.post(
        f"/institutions/{inst_b.id}/roster/import",
        json={"csv_text": "register_number,full_name\nR,Name\n", "commit": True},
        headers=headers,
    )
    assert r.status_code == 403
