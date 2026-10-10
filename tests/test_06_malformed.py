"""Payload 200 malformado do agregador degrada para stale, nunca 500.

Contrato (README): precedência 404 > 422 > 200 com stale:true —
"agregador fora/timeout/500 — degrada, não quebra". Um 200 com corpo
fora do formato é agregador quebrado e cai na mesma regra.
"""
from fastapi.testclient import TestClient


def _register(client: TestClient, code: str = "AB123") -> None:
    res = client.post("/shipments", json={"code": code})
    assert res.status_code in (200, 201), res.text


def test_missing_field_degrades_to_stale(client, fake):
    _register(client)
    fake.store.events["AB123"] = [
        {"id": "e1", "occurred_at": "2026-01-05T12:00:00+00:00", "carrier": "agregador-fake"}
    ]  # sem status_raw
    res = client.get("/shipments/AB123")
    assert res.status_code == 200
    assert res.json()["stale"] is True


def test_invalid_timestamp_degrades_to_stale(client, fake):
    _register(client)
    fake.store.events["AB123"] = [
        {"id": "e1", "status_raw": "POSTED", "occurred_at": "ontem de tarde",
         "carrier": "agregador-fake"}
    ]
    res = client.get("/shipments/AB123")
    assert res.status_code == 200
    assert res.json()["stale"] is True


def test_non_string_status_degrades_to_stale(client, fake):
    _register(client)
    fake.store.events["AB123"] = [
        {"id": "e1", "status_raw": 42, "occurred_at": "2026-01-05T12:00:00+00:00",
         "carrier": "agregador-fake"}
    ]
    res = client.get("/shipments/AB123")
    assert res.status_code == 200
    assert res.json()["stale"] is True


def test_missing_events_key_degrades_to_stale(client, fake, monkeypatch):
    import httpx
    import provider as providermod

    _register(client)

    real_get = httpx.get

    def fake_get(url, **kwargs):
        if "/track/" in str(url):
            req = httpx.Request("GET", url)
            return httpx.Response(200, json={"unexpected": True}, request=req)
        return real_get(url, **kwargs)

    monkeypatch.setattr(providermod.httpx, "get", fake_get)
    res = client.get("/shipments/AB123")
    assert res.status_code == 200
    assert res.json()["stale"] is True
