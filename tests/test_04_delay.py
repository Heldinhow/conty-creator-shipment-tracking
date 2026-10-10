"""Ticket 04: atraso com data controlada — sem falso positivo em entrega normal."""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as appmod
from provider import FakeAggregadorProvider, FixedClock, ShipmentRepository

T0 = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)  # relógio fixo: data controlada


@pytest.fixture
def ctx():
    appmod.repo = ShipmentRepository()
    appmod.provider = FakeAggregadorProvider()
    appmod.clock = FixedClock(T0)
    return TestClient(appmod.app), appmod.provider


def test_in_course_past_sla_is_delayed(ctx):
    client, provider = ctx
    provider.seed(
        "D1",
        [("e1", "POSTED", T0 - timedelta(hours=100)), ("e2", "IN_TRANSIT", T0 - timedelta(hours=50))],
    )
    body = client.post("/shipments", json={"code": "D1"}).json()  # SLA default 72h
    assert body["delayed"] is True
    assert body["t0"] == (T0 - timedelta(hours=100)).isoformat()


def test_on_time_delivery_is_not_delayed(ctx):
    client, provider = ctx
    provider.seed(
        "D2",
        [("e1", "POSTED", T0 - timedelta(hours=10)), ("e4", "DELIVERED", T0 - timedelta(hours=5))],
    )
    body = client.post("/shipments", json={"code": "D2"}).json()
    assert body["status"] == "entregue"
    assert body["delayed"] is False


def test_late_delivery_freezes_delayed_true(ctx):
    client, provider = ctx
    provider.seed(
        "D3",
        [("e1", "POSTED", T0 - timedelta(hours=100)), ("e4", "DELIVERED", T0 - timedelta(hours=1))],
    )
    assert client.post("/shipments", json={"code": "D3"}).json()["delayed"] is True


def test_exception_alone_is_not_delayed(ctx):
    client, provider = ctx
    provider.seed("D4", [("e9", "ZBLORP", T0 - timedelta(hours=200))])
    body = client.post("/shipments", json={"code": "D4"}).json()
    assert body["status"] == "excecao"
    assert body["delayed"] is False


def test_late_registration_without_posted_still_detects_delay(ctx):
    client, provider = ctx
    provider.seed("D5", [("e2", "IN_TRANSIT", T0 - timedelta(hours=100))])
    body = client.post("/shipments", json={"code": "D5"}).json()
    assert body["t0"] == (T0 - timedelta(hours=100)).isoformat()
    assert body["delayed"] is True


def test_per_shipment_sla_override(ctx):
    client, provider = ctx
    provider.seed("D6", [("e1", "POSTED", T0 - timedelta(hours=100))])
    body = client.post("/shipments", json={"code": "D6", "sla_hours": 200}).json()
    assert body["delayed"] is False
