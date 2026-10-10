"""Ticket 05: degradação stale, agregador trocável e endpoint de eventos."""
from datetime import timedelta

import pytest

import app as appmod
from provider import CarrierXProvider, FakeAggregadorProvider

from .conftest import T0

# Vocabulário de cada dialeto: o mesmo cenário, duas línguas.
DIALECTS = {
    "A": {
        "make": FakeAggregadorProvider,
        "posted": "POSTED",
        "transit": "IN_TRANSIT",
        "out": "OUT_FOR_DELIVERY",
        "delivered": "DELIVERED",
        "unknown": "ZBLORP_INVENTADO",
        "carrier": "agregador-fake",
    },
    "B": {
        "make": CarrierXProvider,
        "posted": "PACOTE_POSTADO",
        "transit": "EM_ROTA",
        "out": "SAIU_PARA_ENTREGA",
        "delivered": "ENTREGUE_CRIADOR",
        "unknown": "XPT0_DESCONHECIDO",
        "carrier": "carrier-x",
    },
}


@pytest.fixture(params=["A", "B"])
def dialect(request, fake):
    return request.param, DIALECTS[request.param], fake


@pytest.fixture
def dialect_client(client, dialect, fake):
    _, vocab, _ = dialect
    appmod.provider = vocab["make"](fake.base_url)
    return client


def test_contract_progression_and_unknown(dialect_client, dialect, fake):
    _, vocab, _ = dialect
    code = f"CT-{dialect[0]}"
    fake.store.seed(
        code,
        [
            ("e2", vocab["transit"], T0 - timedelta(hours=2)),
            ("e1", vocab["posted"], T0 - timedelta(hours=5)),
            ("e2", vocab["transit"], T0 - timedelta(hours=2)),
            ("e9", vocab["unknown"], T0 - timedelta(hours=1)),
        ],
        carrier=vocab["carrier"],
    )
    body = dialect_client.post("/shipments", json={"code": code}).json()
    assert body["status"] == "excecao"  # desconhecido nunca vira entregue
    assert body["last_valid_status"] == "em_transito"
    assert [e["normalized"] for e in body["history"]] == ["postado", "em_transito", "excecao"]
    assert body["history"][0]["carrier"] == vocab["carrier"]

    again = dialect_client.get(f"/shipments/{code}").json()
    assert len(again["history"]) == 3  # reconsulta não duplica


def test_aggregator_failure_degrades_with_stale(client, fake):
    fake.store.seed("S1", [("e1", "POSTED", T0 - timedelta(hours=9))])
    assert client.post("/shipments", json={"code": "S1"}).json()["stale"] is False

    fake.store.fail_for("S1")
    body = client.get("/shipments/S1").json()
    assert body["stale"] is True
    assert body["status"] == "postado"  # último estado local preservado


def test_events_endpoint_shows_raw_and_normalized(client, fake):
    fake.store.seed(
        "S2", [("e1", "POSTED", T0 - timedelta(hours=9)), ("e9", "ZBLORP", T0 - timedelta(hours=2))]
    )
    client.post("/shipments", json={"code": "S2"})
    events = client.get("/shipments/S2/events").json()["events"]
    assert [(e["status_raw"], e["normalized"]) for e in events] == [
        ("POSTED", "postado"),
        ("ZBLORP", "excecao"),
    ]
