"""Ticket 02: tradução monotônica, dedup e fora de ordem (via HTTP + fake)."""
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


def test_out_of_order_does_not_regress_and_dedups(ctx):
    client, provider = ctx
    provider.seed(
        "PK1",
        [
            ("e2", "IN_TRANSIT", T0 - timedelta(hours=2)),      # chega "antes"
            ("e1", "POSTED", T0 - timedelta(hours=5)),          # evento antigo
            ("e2", "IN_TRANSIT", T0 - timedelta(hours=2)),      # repetido
            ("e3", "OUT_FOR_DELIVERY", T0 - timedelta(hours=1)),
        ],
    )
    body = client.post("/shipments", json={"code": "PK1"}).json()
    assert body["status"] == "saiu_para_entrega"
    assert [e["normalized"] for e in body["history"]] == [
        "postado",
        "em_transito",
        "saiu_para_entrega",
    ]

    again = client.get("/shipments/PK1").json()
    assert len(again["history"]) == 3  # reconsulta não duplica


def test_old_event_arriving_late_does_not_move_status(ctx):
    client, provider = ctx
    provider.seed("PK2", [("e1", "POSTED", T0 - timedelta(hours=9)), ("e3", "OUT_FOR_DELIVERY", T0 - timedelta(hours=1))])
    assert client.post("/shipments", json={"code": "PK2"}).json()["status"] == "saiu_para_entrega"

    provider.seed(
        "PK2",
        [
            ("e1", "POSTED", T0 - timedelta(hours=9)),
            ("e2", "IN_TRANSIT", T0 - timedelta(hours=5)),  # antigo, chega depois
            ("e3", "OUT_FOR_DELIVERY", T0 - timedelta(hours=1)),
        ],
    )
    body = client.get("/shipments/PK2").json()
    assert body["status"] == "saiu_para_entrega"
    assert len(body["history"]) == 3


def test_events_without_id_fall_back_to_content_hash(ctx):
    client, provider = ctx
    at = T0 - timedelta(hours=3)
    provider.seed("PK3", [(None, "POSTED", at), (None, "POSTED", at)])
    body = client.post("/shipments", json={"code": "PK3"}).json()
    assert len(body["history"]) == 1
