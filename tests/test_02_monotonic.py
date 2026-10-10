"""Ticket 02: tradução monotônica, dedup e fora de ordem (via HTTP + fake)."""
from datetime import timedelta

from .conftest import T0


def test_out_of_order_does_not_regress_and_dedups(client, fake):
    fake.store.seed(
        "PK1",
        [
            ("e2", "IN_TRANSIT", T0 - timedelta(hours=2)),  # chega "antes"
            ("e1", "POSTED", T0 - timedelta(hours=5)),  # evento antigo
            ("e2", "IN_TRANSIT", T0 - timedelta(hours=2)),  # repetido
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


def test_old_event_arriving_late_does_not_move_status(client, fake):
    fake.store.seed(
        "PK2",
        [("e1", "POSTED", T0 - timedelta(hours=9)), ("e3", "OUT_FOR_DELIVERY", T0 - timedelta(hours=1))],
    )
    assert client.post("/shipments", json={"code": "PK2"}).json()["status"] == "saiu_para_entrega"

    fake.store.seed(
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


def test_events_without_id_fall_back_to_content_hash(client, fake):
    at = T0 - timedelta(hours=3)
    fake.store.seed("PK3", [(None, "POSTED", at), (None, "POSTED", at)])
    body = client.post("/shipments", json={"code": "PK3"}).json()
    assert len(body["history"]) == 1
