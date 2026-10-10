"""Ticket 05: degradação stale, agregador trocável e endpoint de eventos."""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as appmod
from provider import CarrierXProvider, FakeAggregadorProvider, FixedClock, ShipmentRepository

T0 = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def ctx():
    appmod.repo = ShipmentRepository()
    appmod.provider = FakeAggregadorProvider()
    appmod.clock = FixedClock(T0)
    return TestClient(appmod.app), appmod.provider


def test_aggregator_failure_degrades_with_stale(ctx):
    client, provider = ctx
    provider.seed("S1", [("e1", "POSTED", T0 - timedelta(hours=9))])
    assert client.post("/shipments", json={"code": "S1"}).json()["stale"] is False

    provider.fail_for("S1")
    body = client.get("/shipments/S1").json()
    assert body["stale"] is True
    assert body["status"] == "postado"  # último estado local preservado


def test_swapped_aggregator_speaks_another_dialect():
    appmod.repo = ShipmentRepository()
    provider = CarrierXProvider()
    appmod.provider = provider
    appmod.clock = FixedClock(T0)
    client = TestClient(appmod.app)

    provider.seed(
        "X1",
        [
            ("a1", "PACOTE_POSTADO", T0 - timedelta(hours=9)),
            ("a2", "EM_ROTA", T0 - timedelta(hours=2)),
            ("a9", "intis DIO_desconhecido", T0 - timedelta(hours=1)),
        ],
    )
    body = client.post("/shipments", json={"code": "X1"}).json()
    assert body["status"] == "excecao"  # desconhecido do dialeto B também vira exceção
    assert body["last_valid_status"] == "em_transito"
    assert body["history"][0]["carrier"] == "carrier-x"


def test_events_endpoint_shows_raw_and_normalized(ctx):
    client, provider = ctx
    provider.seed("S2", [("e1", "POSTED", T0 - timedelta(hours=9)), ("e9", "ZBLORP", T0 - timedelta(hours=2))])
    client.post("/shipments", json={"code": "S2"})
    events = client.get("/shipments/S2/events").json()["events"]
    assert [(e["status_raw"], e["normalized"]) for e in events] == [
        ("POSTED", "postado"),
        ("ZBLORP", "excecao"),
    ]
