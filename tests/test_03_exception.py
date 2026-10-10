"""Ticket 03: status inventado vira exceção, destrava e entregue é terminal."""
from datetime import timedelta

from .conftest import T0


def test_unknown_carrier_status_becomes_exception_not_delivered(client, fake):
    fake.store.seed(
        "EX1",
        [("e1", "POSTED", T0 - timedelta(hours=9)), ("e9", "ZBLORP_INVENTADO", T0 - timedelta(hours=2))],
    )
    body = client.post("/shipments", json={"code": "EX1"}).json()
    assert body["status"] == "excecao"
    assert body["last_valid_status"] == "postado"
    assert body["history"][-1]["status_raw"] == "ZBLORP_INVENTADO"


def test_valid_event_unlocks_exception(client, fake):
    fake.store.seed(
        "EX2", [("e1", "POSTED", T0 - timedelta(hours=9)), ("e9", "ZBLORP", T0 - timedelta(hours=4))]
    )
    assert client.post("/shipments", json={"code": "EX2"}).json()["status"] == "excecao"

    fake.store.seed(
        "EX2",
        [
            ("e1", "POSTED", T0 - timedelta(hours=9)),
            ("e9", "ZBLORP", T0 - timedelta(hours=4)),
            ("e2", "IN_TRANSIT", T0 - timedelta(hours=1)),
        ],
    )
    body = client.get("/shipments/EX2").json()
    assert body["status"] == "em_transito"


def test_post_delivery_events_are_audited_but_status_stays(client, fake):
    fake.store.seed(
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
