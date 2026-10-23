from __future__ import annotations

import pyotp
import pytest

from app.models import RoleName, UserStatus


async def _login(client, **body):
    return await client.post("/auth/login", json=body)


async def test_login_success_and_me(client, factory):
    inst = await factory.institution("INST1")
    await factory.user(
        email="teacher@example.com", role=RoleName.teacher, institution=inst
    )

    r = await _login(client, email="teacher@example.com", password="Password123!")
    assert r.status_code == 200
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    data = me.json()
    assert data["email"] == "teacher@example.com"
    assert RoleName.teacher.value in data["roles"]
    assert data["institution_ids"] == [inst.id]


async def test_login_wrong_password(client, factory):
    await factory.user(email="a@example.com")
    r = await _login(client, email="a@example.com", password="wrong")
    assert r.status_code == 401


async def test_login_register_number(client, factory):
    inst = await factory.institution("SCHOOL9")
    await factory.user(
        full_name="Student A",
        role=RoleName.student,
        institution=inst,
        register_number="R-1001",
    )
    r = await _login(
        client,
        institution_code="SCHOOL9",
        register_number="R-1001",
        password="Password123!",
    )
    assert r.status_code == 200


async def test_disabled_account_rejected(client, factory):
    await factory.user(email="dis@example.com", status=UserStatus.disabled.value)
    r = await _login(client, email="dis@example.com", password="Password123!")
    assert r.status_code == 403


async def test_access_requires_token(client):
    r = await client.get("/auth/me")
    assert r.status_code == 401


async def test_refresh_rotation(client, factory):
    await factory.user(email="rot@example.com")
    r = await _login(client, email="rot@example.com", password="Password123!")
    first = r.json()["refresh_token"]

    r2 = await client.post("/auth/refresh", json={"refresh_token": first})
    assert r2.status_code == 200
    second = r2.json()["refresh_token"]
    assert second != first


async def test_refresh_replay_revokes_family(client, factory):
    await factory.user(email="replay@example.com")
    r = await _login(client, email="replay@example.com", password="Password123!")
    first = r.json()["refresh_token"]

    # Use it once (rotates).
    ok = await client.post("/auth/refresh", json={"refresh_token": first})
    assert ok.status_code == 200
    new = ok.json()["refresh_token"]

    # Replaying the old token must fail AND revoke the family.
    replay = await client.post("/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401

    # The rotated-out (new) token is now also revoked.
    after = await client.post("/auth/refresh", json={"refresh_token": new})
    assert after.status_code == 401


async def test_logout_revokes(client, factory):
    await factory.user(email="out@example.com")
    r = await _login(client, email="out@example.com", password="Password123!")
    refresh = r.json()["refresh_token"]
    lo = await client.post("/auth/logout", json={"refresh_token": refresh})
    assert lo.status_code == 204
    again = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert again.status_code == 401


async def test_rate_limiting(client, factory):
    await factory.user(email="rl@example.com")
    # 5 allowed attempts, then 429.
    for _ in range(5):
        bad = await _login(client, email="rl@example.com", password="nope")
        assert bad.status_code == 401
    limited = await _login(client, email="rl@example.com", password="nope")
    assert limited.status_code == 429


async def test_password_reset_flow(client, factory):
    await factory.user(email="reset@example.com")
    req = await client.post(
        "/auth/password/reset-request", json={"email": "reset@example.com"}
    )
    assert req.status_code == 202
    token = req.json()["debug_reset_token"]

    confirm = await client.post(
        "/auth/password/reset-confirm",
        json={"token": token, "new_password": "NewPassw0rd!"},
    )
    assert confirm.status_code == 204

    # Old password fails, new one works.
    old = await _login(client, email="reset@example.com", password="Password123!")
    assert old.status_code == 401
    new = await _login(client, email="reset@example.com", password="NewPassw0rd!")
    assert new.status_code == 200


async def test_password_reset_unknown_email_is_quiet(client):
    req = await client.post(
        "/auth/password/reset-request", json={"email": "nobody@example.com"}
    )
    assert req.status_code == 202
    assert "debug_reset_token" not in req.json()


async def test_mfa_setup_enable_and_required_on_login(client, factory):
    await factory.user(email="super@example.com", is_super_admin=True)
    login = await _login(client, email="super@example.com", password="Password123!")
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    setup = await client.post("/auth/mfa/setup", headers=headers)
    assert setup.status_code == 200
    secret = setup.json()["secret"]

    code = pyotp.TOTP(secret).now()
    enable = await client.post(
        "/auth/mfa/enable", json={"totp_code": code}, headers=headers
    )
    assert enable.status_code == 204

    # Login now requires the TOTP code.
    no_code = await _login(client, email="super@example.com", password="Password123!")
    assert no_code.status_code == 401
    with_code = await _login(
        client,
        email="super@example.com",
        password="Password123!",
        totp_code=pyotp.TOTP(secret).now(),
    )
    assert with_code.status_code == 200


async def test_mfa_setup_requires_super_admin(client, factory):
    inst = await factory.institution("INST2")
    await factory.user(
        email="plain@example.com", role=RoleName.teacher, institution=inst
    )
    login = await _login(client, email="plain@example.com", password="Password123!")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post("/auth/mfa/setup", headers=headers)
    assert setup.status_code == 403


# --- Tenant isolation ---
async def test_tenant_scope_denies_other_institution(client, factory):
    inst_a = await factory.institution("A")
    inst_b = await factory.institution("B")
    await factory.user(
        email="admin_a@example.com",
        role=RoleName.institution_admin,
        institution=inst_a,
    )
    login = await _login(client, email="admin_a@example.com", password="Password123!")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    own = await client.get(f"/auth/tenant/{inst_a.id}/context", headers=headers)
    assert own.status_code == 200

    # Manipulated institution id for another tenant must be denied server-side.
    other = await client.get(f"/auth/tenant/{inst_b.id}/context", headers=headers)
    assert other.status_code == 403


async def test_super_admin_cross_tenant_allowed(client, factory):
    inst = await factory.institution("C")
    await factory.user(email="root@example.com", is_super_admin=True)
    login = await _login(client, email="root@example.com", password="Password123!")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    r = await client.get(f"/auth/tenant/{inst.id}/context", headers=headers)
    assert r.status_code == 200
