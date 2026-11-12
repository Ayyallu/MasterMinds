"""Browser end-to-end pass over every page for every role (Edge via Playwright).

For each page: no uncaught JS errors, no console errors, no 5xx API responses,
no error-state screen, a visible H1. Plus interactive flows.
"""
from __future__ import annotations

import json
import sys
import time

from playwright.sync_api import sync_playwright, expect

WEB = "http://localhost:3000"
OUT = sys.argv[1]
results = []


def check(cid, desc, ok, detail=""):
    results.append({"area": "UI", "id": cid, "desc": desc, "ok": bool(ok), "detail": "" if ok else str(detail)[:500]})
    print(f"  {'PASS' if ok else 'FAIL'} {cid} {desc}" + ("" if ok else f"\n       -> {str(detail)[:300]}"))


class Watch:
    def __init__(self, page):
        self.errors, self.bad = [], []
        page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: self.errors.append(f"console.{m.type}: {m.text[:160]}") if m.type == "error" else None)
        page.on("response", lambda r: self.bad.append(f"{r.status} {r.request.method} {r.url}") if r.status >= 500 else None)

    def reset(self):
        self.errors.clear(); self.bad.clear()


def staff_login(page, email, password):
    page.goto(f"{WEB}/admin")
    page.get_by_label("Email").wait_for(timeout=15000)
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


def sweep(page, w, cid, role, paths, shots=True):
    for path in paths:
        w.reset()
        page.goto(WEB + path)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(600)
        h1 = page.locator("h1").first
        has_h1 = h1.count() > 0 and h1.is_visible()
        err_screen = page.get_by_text("Something went wrong").count()
        # 404s from optional probes (e.g. no logo) are fine; console errors for them are filtered.
        cons = [e for e in w.errors if "404" not in e and "Failed to load resource" not in e]
        ok = has_h1 and not err_screen and not cons and not w.bad
        check(f"{cid}{path}", f"[{role}] {path} renders cleanly", ok,
              {"h1": has_h1, "error_screen": err_screen, "console": cons[:3], "5xx": w.bad[:3]})
        if shots:
            page.screenshot(path=f"{OUT}/{role}_{path.strip('/').replace('/', '_') or 'home'}.png", full_page=True)


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")

    # ---------------------------------------------------------------- public
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); page = ctx.new_page(); w = Watch(page)
    sweep(page, w, "U01", "public", ["/", "/student/register"])
    w.reset(); page.goto(f"{WEB}/admin")
    hd = page.get_by_role("heading", name="Sign in to your workspace")
    hd.wait_for(timeout=15000)
    check("U02", "Staff login screen shows sign-in heading", hd.is_visible())
    staff_login(page, "admin@demo.example.com", "definitely-wrong")
    page.wait_for_timeout(1500)
    alert = page.get_by_role("alert")
    check("U03", "Wrong password shows an inline error (no crash)", alert.count() > 0 and alert.first.is_visible(), page.content()[:200])
    # Student register form: client-side required fields.
    page.goto(f"{WEB}/student/register")
    page.wait_for_load_state("networkidle")
    page.locator("form button[type=submit]").first.click()
    page.wait_for_timeout(500)
    check("U04", "Student registration blocks empty submit (required fields)", "/student/register" in page.url and not w.bad, w.bad)
    ctx.close()

    # ---------------------------------------------------------------- super admin
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); page = ctx.new_page(); w = Watch(page)
    staff_login(page, "superadmin@demo.example.com", "SuperAdmin#2026!")
    page.get_by_role("heading", name="Welcome, Platform").wait_for(timeout=15000)
    check("U05", "Super Admin signs in via the form", True)
    sweep(page, w, "U06", "superadmin", ["/admin", "/admin/registrations", "/admin/institutions", "/admin/institutions/new",
                                         "/admin/reports", "/admin/global", "/admin/settings"])
    page.goto(f"{WEB}/admin/institutions"); page.wait_for_load_state("networkidle")
    page.locator("a[href^='/admin/institutions/']").filter(has_text="Edit").first.wait_for()
    href = page.locator("a[href^='/admin/institutions/']").filter(has_text="Edit").first.get_attribute("href")
    page.goto(WEB + href); page.wait_for_load_state("networkidle"); page.locator(".inst-card").wait_for(timeout=10000)
    check("U07", "Institution detail page opens from the list", page.locator(".inst-card").count() == 1, page.url)
    page.get_by_role("button", name="Edit profile").click()
    page.get_by_label("Institution name").fill("")
    page.get_by_role("button", name="Save changes").click(); page.wait_for_timeout(600)
    check("U08", "Profile edit blocks an empty required name (browser validation)", page.get_by_role("button", name="Save changes").is_visible())
    page.get_by_role("button", name="Cancel").click()
    page.get_by_role("button", name="Sign out").click()
    try:
        page.get_by_role("heading", name="Sign in to your workspace").wait_for(timeout=8000); ok9 = True
    except Exception:
        ok9 = False
    check("U09", "Sign out returns to the login screen", ok9, page.url)
    page.goto(f"{WEB}/admin/institutions")
    try:
        page.get_by_role("heading", name="Sign in to your workspace").wait_for(timeout=8000); ok10 = True
    except Exception:
        ok10 = False
    check("U10", "After sign-out, protected pages show login (no data)", ok10, page.url)
    ctx.close()

    # ---------------------------------------------------------------- institution admin
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); page = ctx.new_page(); w = Watch(page)
    staff_login(page, "admin@demo.example.com", "Demo-Admin#2026")
    page.get_by_role("heading", name="Welcome, Demo").wait_for(timeout=15000)
    sweep(page, w, "U11", "admin", ["/admin", "/admin/academic", "/admin/people", "/admin/questions", "/admin/ai",
                                    "/admin/exams", "/admin/results", "/admin/settings"])
    # Academic CRUD through the UI.
    page.goto(f"{WEB}/admin/academic"); page.wait_for_load_state("networkidle")
    page.get_by_role("tab", name="Grades, departments & courses").click()
    name = f"UI Grade {time.strftime('%H%M%S')}"
    grade_form = page.locator("form").filter(has=page.get_by_label("Name")).first
    grade_form.get_by_label("Name").fill(name)
    grade_form.get_by_role("button", name="Create").click()
    page.get_by_role("cell", name=name, exact=True).wait_for(timeout=8000)
    check("U12", "Create a grade level from the UI; it appears in the list", True)
    page.get_by_role("button", name=f"Edit grade level {name}").click()
    dlg = page.get_by_role("dialog")
    dlg.get_by_label("Name").fill(name + " (edited)")
    dlg.get_by_role("button", name="Save changes").click()
    page.get_by_role("cell", name=name + " (edited)", exact=True).wait_for(timeout=8000)
    check("U13", "Edit the grade level in the dialog", True)
    page.get_by_role("button", name=f"Delete grade level {name} (edited)").click()
    page.get_by_role("dialog").get_by_role("button", name="Delete").click()
    page.wait_for_timeout(1500)
    check("U14", "Delete the grade level after confirmation", page.get_by_role("cell", name=name + " (edited)", exact=True).count() == 0)
    page.keyboard.press("Escape")
    # Toast on server error: duplicate name.
    grade_form.get_by_label("Name").fill("Dup Grade X"); grade_form.get_by_role("button", name="Create").click(); page.wait_for_timeout(1200)
    grade_form.get_by_label("Name").fill("Dup Grade X"); grade_form.get_by_role("button", name="Create").click(); page.wait_for_timeout(1500)
    toasts = page.locator(".toast-error")
    check("U15", "Duplicate name shows a friendly error toast (not a crash)", toasts.count() > 0 and not w.bad, (toasts.count(), w.bad[:2]))
    page.get_by_role("button", name="Delete grade level Dup Grade X").click()
    page.get_by_role("dialog").get_by_role("button", name="Delete").click(); page.wait_for_timeout(800)
    ctx.close()

    # ---------------------------------------------------------------- teacher
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); page = ctx.new_page(); w = Watch(page)
    staff_login(page, "teacher@demo.example.com", "Demo-Teacher#2026")
    page.get_by_role("heading", name="Welcome, Demo").wait_for(timeout=15000)
    sweep(page, w, "U16", "teacher", ["/admin", "/admin/questions", "/admin/ai", "/admin/exams", "/admin/results", "/admin/settings"])
    nav = [a.inner_text() for a in page.locator("nav a").all()]
    check("U17", "Teacher nav hides admin-only sections", "Academic structure" not in nav and "People" not in nav, nav)
    w.reset(); page.goto(f"{WEB}/admin/academic"); page.wait_for_load_state("networkidle"); page.wait_for_timeout(800)
    body = page.inner_text("main")
    check("U18", "Teacher typing /admin/academic gets no admin data (forbidden handled)",
          not w.bad and ("Institution Admin required" in body or "permission" in body.lower() or "not" in body.lower()), body[:300])
    w.reset(); page.goto(f"{WEB}/admin/institutions"); page.wait_for_load_state("networkidle"); page.wait_for_timeout(800)
    body = page.inner_text("main")
    check("U19", "Teacher typing /admin/institutions sees no platform data", "Super Admin required" in body or "DEMO01" not in body, body[:300])
    ctx.close()

    # ---------------------------------------------------------------- student
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); page = ctx.new_page(); w = Watch(page)
    page.goto(f"{WEB}/student")
    page.get_by_label("Institution code").wait_for(timeout=15000)
    page.get_by_label("Institution code").fill("DEMO01")
    page.get_by_label("Register number").fill("MM-DEMO-001")
    page.get_by_label("Password").fill("Demo-Student#2026")
    page.get_by_role("button", name="Sign in").click()
    page.get_by_role("heading", name="Your exams").wait_for(timeout=15000)
    check("U20", "Student signs in via the form", True)
    sweep(page, w, "U21", "student", ["/student"])
    w.reset(); page.goto(f"{WEB}/admin"); page.wait_for_timeout(2500)
    check("U22", "Student opening /admin is redirected to the student portal", "/student" in page.url, page.url)
    w.reset(); page.goto(f"{WEB}/student/attempts/999999"); page.wait_for_load_state("networkidle"); page.wait_for_timeout(1200)
    check("U23", "Unknown attempt id shows a handled message (no crash, no 5xx)", not w.bad and not [e for e in w.errors if "pageerror" in e], (w.bad, w.errors[:3]))
    page.screenshot(path=f"{OUT}/student_bad_attempt.png")
    w.reset(); page.goto(f"{WEB}/student/results/999999"); page.wait_for_load_state("networkidle"); page.wait_for_timeout(1200)
    check("U24", "Unknown result id shows a handled message", not w.bad and not [e for e in w.errors if "pageerror" in e], (w.bad, w.errors[:3]))
    ctx.close()

    # ---------------------------------------------------------------- mobile
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True); page = ctx.new_page(); w = Watch(page)
    staff_login(page, "admin@demo.example.com", "Demo-Admin#2026")
    page.get_by_role("heading", name="Welcome, Demo").wait_for(timeout=15000)
    sidebar = page.locator("aside.sidebar")
    box = sidebar.bounding_box()
    check("U25", "Mobile: sidebar is hidden off-canvas initially", box is None or box["x"] + box["width"] <= 1, box)
    page.get_by_role("button", name="Toggle navigation").click(); page.wait_for_timeout(500)
    box = sidebar.bounding_box()
    check("U26", "Mobile: menu button opens the sidebar", box and box["x"] >= -1, box)
    page.get_by_role("link", name="Academic structure", exact=True).click(); page.wait_for_load_state("networkidle"); page.wait_for_timeout(500)
    box = sidebar.bounding_box()
    check("U27", "Mobile: navigating closes the sidebar", box is None or box["x"] + box["width"] <= 1, box)
    overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
    check("U28", "Mobile: academic page has no horizontal page overflow", not overflow)
    page.screenshot(path=f"{OUT}/mobile_academic.png", full_page=True)
    for path in ["/admin", "/admin/people", "/admin/exams"]:
        page.goto(WEB + path); page.wait_for_load_state("networkidle"); page.wait_for_timeout(400)
        ov = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        check(f"U29{path}", f"Mobile: {path} has no horizontal page overflow", not ov)
    ctx.close()

    # ---------------------------------------------------------------- a11y basics
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); page = ctx.new_page()
    staff_login(page, "admin@demo.example.com", "Demo-Admin#2026")
    page.get_by_role("heading", name="Welcome, Demo").wait_for(timeout=15000)
    issues = {}
    for path in ["/admin/academic", "/admin/people", "/admin/questions", "/admin/exams", "/admin/ai"]:
        page.goto(WEB + path); page.wait_for_load_state("networkidle"); page.wait_for_timeout(500)
        unl = page.evaluate("""() => [...document.querySelectorAll('input:not([type=hidden]),select,textarea')]
            .filter(e => !e.hidden && e.offsetParent !== null && !e.getAttribute('aria-label') && !(e.id && document.querySelector(`label[for="${e.id}"]`)) && !e.closest('label'))
            .map(e => e.outerHTML.slice(0, 80))""")
        btn = page.evaluate("""() => [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null && !b.innerText.trim() && !b.getAttribute('aria-label')).length""")
        imgs = page.evaluate("""() => [...document.querySelectorAll('img')].filter(i => !i.getAttribute('alt')).length""")
        if unl or btn or imgs:
            issues[path] = {"unlabelled_inputs": unl[:3], "icon_buttons_without_name": btn, "img_without_alt": imgs}
    check("U30", "A11y: all visible inputs labelled, icon buttons named, images have alt", not issues, issues)
    page.keyboard.press("Tab"); page.keyboard.press("Tab")
    focus_ring = page.evaluate("getComputedStyle(document.activeElement).boxShadow !== 'none' || getComputedStyle(document.activeElement).outlineStyle !== 'none'")
    check("U31", "A11y: keyboard focus is visible", focus_ring)
    ctx.close()
    b.close()

passed = sum(r["ok"] for r in results)
print(f"\nUI TOTAL {passed}/{len(results)} passed")
json.dump(results, open(f"{OUT}/ui_results.json", "w", encoding="utf-8"), indent=1)
