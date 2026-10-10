"""Ticket 03: status inventado vira exceção, destrava e entregue é terminal."""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as appmod
from provider import FakeAggregadorProvider, FixedClock, ShipmentRepository

T0 = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def ctx():
    appmod.repo = ShipmentRepository()
    appmod.provider = FakeAggregadorProvider()
    appmod.clock = FixedClock(T0)
    return TestClient(appmod.app), appmod.provider


def test_unknown_carrier_status_becomes_exception_not_delivered(ctx):
    client, provider = ctx
    provider.seed(
        "EX1",
        [("e1", "POSTED", T0 - timedelta(hours=9)), ("e9", "ZBLORP_INVENTADO", T0 - timedelta(hours=2))],
    )
    body = client.post("/shipments", json={"code": "EX1"}).json()
    assert body["status"] == "excecao"
    assert body["last_valid_status"] == "postado"
    assert body["history"][-1]["status_raw"] == "ZBLORP_INVENTADO"


def test_valid_event_unlocks_exception(ctx):
    client, provider = ctx
    provider.seed("EX2", [("e1", "POSTED", T0 - timedelta(hours=9)), ("e9", "ZBLORP", T0 - timedelta(hours=4))])
    assert client.post("/shipments", json={"code": "EX2"}).json()["status"] == "excecao"

    provider.seed(
        "EX2",
        [
            ("e1", "POSTED", T0 - timedelta(hours=9)),
            ("e9", "ZBLORP", T0 - timedelta(hours=4)),
            ("e2", "IN_TRANSIT", T0 - timedelta(hours=1)),
        ],
    )
    body = client.get("/shipments/EX2").json()
    assert body["status"] == "em_transito"


def test_post_delivery_events_are_audited_but_status_stays(ctx):
    client, provider = ctx
    provider.seed(
        "EX3",
        [
            ("e1", "POSTED", T0 - timedelta(hours=30)),
            ("e4", "DELIVERED", T0 - timedelta(hours=2)),
            ("e9", "ZBLORP_TARDIO", T0 - timedelta(hours=1)),
        ],
    )
    body = client.post("/shipments", json={"code": "EX3"}).json()
    assert body["status"] == "entregue"
    assert len(body["history"]) == 3
