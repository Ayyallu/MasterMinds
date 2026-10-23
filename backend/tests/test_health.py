import httpx
import pytest

from app import main


@pytest.fixture
def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=main.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_health_ok(monkeypatch, client):
    async def _db_up() -> bool:
        return True

    monkeypatch.setattr(main, "_check_database", _db_up)

    async with client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "up"}


async def test_health_unavailable(monkeypatch, client):
    async def _db_down() -> bool:
        return False

    monkeypatch.setattr(main, "_check_database", _db_down)

    async with client:
        resp = await client.get("/health")

    assert resp.status_code == 503
    assert resp.json() == {"status": "unavailable", "database": "down"}
