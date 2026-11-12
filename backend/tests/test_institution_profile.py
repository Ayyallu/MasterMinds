"""Institution profile: Super Admin create/edit, logo, and member visibility."""
from __future__ import annotations

from app.models import RoleName

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def _headers(client, email, password="Password123!"):
    r = await client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _profile(**over):
    body = {
        "name": "Sunrise Public School",
        "institution_type": "school",
        "affiliation": "CBSE",
        "established_year": 1998,
        "head_name": "Dr. A. Rao",
        "email": "office@sunrise.example.com",
        "phone": "+91 44 2345 6789",
        "website": "sunrise.example.com",
        "address_line1": "12 Lake View Road",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "postal_code": "600001",
        "country": "India",
        "time_zone": "Asia/Kolkata",
    }
    body.update(over)
    return body


def _create_body(**over):
    base = {
        "code": "sunrise",
        "admin_full_name": "Sunrise Admin",
        "admin_email": "admin@sunrise.example.com",
    }
    base.update(over)
    return _profile(**base)


async def test_super_admin_creates_institution_with_profile(client, factory):
    await factory.user(email="root@example.com", is_super_admin=True)
    h = await _headers(client, "root@example.com")

    r = await client.post("/admin/institutions", json=_create_body(), headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    inst = body["institution"]
    assert inst["code"] == "SUNRISE"  # normalised
    assert inst["status"] == "active"
    assert inst["city"] == "Chennai" and inst["institution_type"] == "school"
    assert inst["website"] == "https://sunrise.example.com"
    assert inst["has_logo"] is False

    # Provisioned admin can sign in and sees their institution's profile.
    admin_h = await _headers(client, "admin@sunrise.example.com", body["debug_admin_temp_password"])
    prof = await client.get(f"/institutions/{inst['id']}/profile", headers=admin_h)
    assert prof.status_code == 200
    assert prof.json()["name"] == "Sunrise Public School"

    listing = await client.get("/admin/institutions", headers=h)
    assert [i["code"] for i in listing.json()] == ["SUNRISE"]


async def test_create_validates_required_fields_and_duplicates(client, factory):
    await factory.user(email="root@example.com", is_super_admin=True)
    h = await _headers(client, "root@example.com")

    missing = _create_body()
    del missing["address_line1"]
    assert (await client.post("/admin/institutions", json=missing, headers=h)).status_code == 422
    bad_tz = await client.post("/admin/institutions", json=_create_body(time_zone="Mars/Base"), headers=h)
    assert bad_tz.status_code == 422
    bad_type = await client.post("/admin/institutions", json=_create_body(institution_type="gym"), headers=h)
    assert bad_type.status_code == 422

    assert (await client.post("/admin/institutions", json=_create_body(), headers=h)).status_code == 201
    dup = await client.post(
        "/admin/institutions",
        json=_create_body(admin_email="other@sunrise.example.com"),
        headers=h,
    )
    assert dup.status_code == 409


async def test_only_super_admin_can_create_or_edit(client, factory):
    inst = await factory.institution("IA")
    await factory.user(email="admin_a@example.com", role=RoleName.institution_admin, institution=inst)
    h = await _headers(client, "admin_a@example.com")
    assert (await client.post("/admin/institutions", json=_create_body(), headers=h)).status_code == 403
    assert (await client.put(f"/admin/institutions/{inst.id}", json=_profile(), headers=h)).status_code == 403
    assert (await client.get("/admin/institutions", headers=h)).status_code == 403


async def test_super_admin_edits_profile(client, factory):
    inst = await factory.institution("IA")
    await factory.user(email="root@example.com", is_super_admin=True)
    h = await _headers(client, "root@example.com")
    r = await client.put(
        f"/admin/institutions/{inst.id}",
        json=_profile(name="Renamed College", institution_type="college"),
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Renamed College"
    assert r.json()["code"] == "IA"  # code is not editable
    assert r.json()["updated_at"] is not None


async def test_members_see_only_their_own_institution(client, factory):
    a = await factory.institution("IA", "Alpha")
    b = await factory.institution("IB", "Beta")
    await factory.user(email="t@example.com", role=RoleName.teacher, institution=a)
    await factory.user(
        role=RoleName.student, institution=a, register_number="S1", full_name="Stu"
    )
    t = await _headers(client, "t@example.com")
    assert (await client.get(f"/institutions/{a.id}/profile", headers=t)).json()["name"] == "Alpha"
    assert (await client.get(f"/institutions/{b.id}/profile", headers=t)).status_code == 403

    s = await client.post(
        "/auth/login",
        json={"institution_code": "IA", "register_number": "S1", "password": "Password123!"},
    )
    sh = {"Authorization": f"Bearer {s.json()['access_token']}"}
    assert (await client.get(f"/institutions/{a.id}/profile", headers=sh)).status_code == 200
    assert (await client.get(f"/institutions/{b.id}/profile", headers=sh)).status_code == 403
    assert (await client.get(f"/institutions/{b.id}/logo", headers=sh)).status_code == 403


async def test_logo_upload_validation_and_access(client, factory):
    a = await factory.institution("IA")
    await factory.user(email="admin_a@example.com", role=RoleName.institution_admin, institution=a)
    await factory.user(email="t@example.com", role=RoleName.teacher, institution=a)
    admin = await _headers(client, "admin_a@example.com")
    teacher = await _headers(client, "t@example.com")
    url = f"/institutions/{a.id}/logo"

    assert (await client.get(url, headers=admin)).status_code == 404

    svg = await client.put(url, files={"file": ("x.svg", b"<svg/>", "image/svg+xml")}, headers=admin)
    assert svg.status_code == 400
    spoof = await client.put(url, files={"file": ("x.png", b"GIF89a....", "image/png")}, headers=admin)
    assert spoof.status_code == 400
    big = await client.put(url, files={"file": ("x.png", PNG + b"\x00" * (1024 * 1024), "image/png")}, headers=admin)
    assert big.status_code == 400

    # Teachers can view but not change the logo.
    assert (await client.put(url, files={"file": ("x.png", PNG, "image/png")}, headers=teacher)).status_code == 403

    ok = await client.put(url, files={"file": ("logo.png", PNG, "image/png")}, headers=admin)
    assert ok.status_code == 200 and ok.json()["has_logo"] is True
    got = await client.get(url, headers=teacher)
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/png"
    assert got.headers["x-content-type-options"] == "nosniff"
    assert got.content == PNG

    assert (await client.delete(url, headers=admin)).status_code == 204
    assert (await client.get(url, headers=teacher)).status_code == 404


async def test_enable_after_disable(client, factory):
    a = await factory.institution("IA")
    await factory.user(email="root@example.com", is_super_admin=True)
    h = await _headers(client, "root@example.com")
    assert (await client.post(f"/admin/institutions/{a.id}/disable", headers=h)).json()["status"] == "disabled"
    assert (await client.post(f"/admin/institutions/{a.id}/enable", headers=h)).json()["status"] == "active"
