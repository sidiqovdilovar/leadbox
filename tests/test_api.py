import importlib

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEADBOX_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "5")
    import app.main as main

    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def payload(**kw):
    base = {"name": "Иван", "contact": "+7 916 123-45-67", "message": "Здравствуйте"}
    base.update(kw)
    return base


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_variant_is_sticky(client):
    first = client.get("/api/variant").json()
    assert first["variant"] in ("A", "B") and first["fresh"] is True
    cookie = client.cookies.get("lb_variant")
    second = client.get("/api/variant").json()
    assert second["variant"] == cookie and second["fresh"] is False


def test_create_lead_ok(client):
    r = client.post("/api/leads", json=payload())
    assert r.status_code == 201
    body = r.json()
    assert body["ok"] is True and isinstance(body["id"], int)


def test_create_lead_validation(client):
    r = client.post("/api/leads", json=payload(name="", contact="позвоните мне"))
    assert r.status_code == 422
    errors = r.json()["errors"]
    assert "name" in errors and "contact" in errors


def test_duplicate_contact_blocked(client):
    assert client.post("/api/leads", json=payload()).status_code == 201
    again = client.post("/api/leads", json=payload(contact="89161234567"))
    assert again.status_code == 409
    assert "contact" in again.json()["errors"]


def test_rate_limit(client):
    contacts = ["+7916123456" + str(i) for i in range(6)]
    codes = [client.post("/api/leads", json=payload(contact=c)).status_code for c in contacts]
    assert codes[:5] == [201] * 5
    assert codes[5] == 429


def test_stats_requires_token(client):
    assert client.get("/api/stats").status_code == 401
    assert client.get("/api/stats", headers={"Authorization": "Bearer wrong"}).status_code == 403


def test_stats_counts(client):
    client.get("/api/variant")
    client.post("/api/leads", json=payload(variant="A"))
    data = client.get("/api/stats", headers=AUTH).json()
    assert data["total_leads"] == 1
    assert set(data["views"]) == {"A", "B"}


def test_leads_list_and_delete(client):
    lead_id = client.post("/api/leads", json=payload()).json()["id"]
    items = client.get("/api/leads", headers=AUTH).json()["items"]
    assert [i["id"] for i in items] == [lead_id]
    assert client.delete(f"/api/leads/{lead_id}", headers=AUTH).status_code == 204
    assert client.get("/api/leads", headers=AUTH).json()["items"] == []
    assert client.delete(f"/api/leads/{lead_id}", headers=AUTH).status_code == 404


def test_public_stats_hides_personal_data(client):
    client.post("/api/leads", json=payload())
    data = client.get("/api/public-stats").json()
    assert set(data) == {"views", "leads", "best_conversion"}
    assert data["leads"] == 1


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Leadbox" in r.text


def test_admin_page_has_noindex(client):
    r = client.get("/admin.html")
    assert "noindex" in r.text
