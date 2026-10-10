"""Ticket 01: cadastro idempotente + consulta base."""


def test_post_creates_and_get_returns_state(client):
    r = client.post("/shipments", json={"code": " abc123 "})
    assert r.status_code == 201
    assert r.json()["code"] == "ABC123"
    assert r.json()["status"] == "postado"

    g = client.get("/shipments/abc123")
    assert g.status_code == 200
    assert g.json()["code"] == "ABC123"


def test_duplicate_post_is_idempotent_and_keeps_sla(client):
    client.post("/shipments", json={"code": "AA1", "sla_hours": 10})
    r = client.post("/shipments", json={"code": "aa1", "sla_hours": 99})
    assert r.status_code == 200
    assert r.json()["sla_hours"] == 10
    assert len(r.json()["history"]) == 0


def test_unknown_code_is_404(client):
    assert client.get("/shipments/NOPE").status_code == 404
    assert client.get("/shipments/NOPE/events").status_code == 404


def test_sla_override_and_validation(client):
    r = client.post("/shipments", json={"code": "S1", "sla_hours": 10})
    assert r.json()["sla_hours"] == 10
    assert client.post("/shipments", json={"code": "S2", "sla_hours": 0}).status_code == 422
    assert client.post("/shipments", json={"code": "  "}).status_code == 422
