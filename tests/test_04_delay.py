"""Ticket 04: atraso com data controlada — sem falso positivo em entrega normal."""
from datetime import timedelta

from .conftest import T0


def test_in_course_past_sla_is_delayed(client, fake):
    fake.store.seed(
        "D1",
        [("e1", "POSTED", T0 - timedelta(hours=100)), ("e2", "IN_TRANSIT", T0 - timedelta(hours=50))],
    )
    body = client.post("/shipments", json={"code": "D1"}).json()  # SLA default 72h
    assert body["delayed"] is True
    assert body["t0"] == (T0 - timedelta(hours=100)).isoformat()


def test_on_time_delivery_is_not_delayed(client, fake):
    fake.store.seed(
        "D2",
        [("e1", "POSTED", T0 - timedelta(hours=10)), ("e4", "DELIVERED", T0 - timedelta(hours=5))],
    )
    body = client.post("/shipments", json={"code": "D2"}).json()
    assert body["status"] == "entregue"
    assert body["delayed"] is False


def test_late_delivery_freezes_delayed_true(client, fake):
    fake.store.seed(
        "D3",
        [("e1", "POSTED", T0 - timedelta(hours=100)), ("e4", "DELIVERED", T0 - timedelta(hours=1))],
    )
    assert client.post("/shipments", json={"code": "D3"}).json()["delayed"] is True


def test_exception_alone_is_not_delayed(client, fake):
    fake.store.seed("D4", [("e9", "ZBLORP", T0 - timedelta(hours=200))])
    body = client.post("/shipments", json={"code": "D4"}).json()
    assert body["status"] == "excecao"
    assert body["delayed"] is False


def test_late_registration_without_posted_still_detects_delay(client, fake):
    fake.store.seed("D5", [("e2", "IN_TRANSIT", T0 - timedelta(hours=100))])
    body = client.post("/shipments", json={"code": "D5"}).json()
    assert body["t0"] == (T0 - timedelta(hours=100)).isoformat()
    assert body["delayed"] is True


def test_per_shipment_sla_override(client, fake):
    fake.store.seed("D6", [("e1", "POSTED", T0 - timedelta(hours=100))])
    body = client.post("/shipments", json={"code": "D6", "sla_hours": 200}).json()
    assert body["delayed"] is False


def test_global_sla_from_env(client, fake, monkeypatch):
    monkeypatch.setenv("TRANSIT_SLA_HOURS", "200")
    fake.store.seed("D7", [("e1", "POSTED", T0 - timedelta(hours=100))])
    body = client.post("/shipments", json={"code": "D7"}).json()
    assert body["sla_hours"] == 200
    assert body["delayed"] is False
