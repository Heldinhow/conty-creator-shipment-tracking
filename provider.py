"""Portas: relógio, repositório e o agregador atrás de interface.

O mapa raw -> normalizado mora aqui, no adapter. O service/domínio só
recebe NormalizedStatus: trocar o agregador = implementar TrackingProvider.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from domain import CarrierEvent, NormalizedStatus, Shipment


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    def __init__(self, at: datetime):
        self.at = at

    def now(self) -> datetime:
        return self.at


class ShipmentRepository:
    """Memória atrás de interface; trocável por SQLite/Postgres sem tocar no domínio."""

    def __init__(self):
        self._items: dict[str, Shipment] = {}

    def get(self, code: str) -> Shipment | None:
        return self._items.get(code)

    def save(self, shipment: Shipment) -> None:
        self._items[shipment.code] = shipment


class ProviderError(Exception):
    pass


class TrackingProvider(Protocol):
    def fetch_events(self, code: str) -> list[CarrierEvent]: ...


class _MemoryProviderBase:
    """Fake HTTP-like do agregador fictício: guarda eventos por código,
    pode devolver repetidos/fora de ordem e pode falhar sob demanda."""

    carrier = "fake"
    mapping: dict[str, NormalizedStatus] = {}

    def __init__(self):
        self._events: dict[str, list[CarrierEvent]] = {}
        self._failures: set[str] = set()
        self.fail_all = False

    def seed(self, code: str, raws: list[tuple[str | None, str, datetime]]) -> None:
        self._events[code.upper()] = [self._translate(eid, raw, at) for eid, raw, at in raws]

    def fail_for(self, code: str) -> None:
        self._failures.add(code.upper())

    def fetch_events(self, code: str) -> list[CarrierEvent]:
        code = code.upper()
        if self.fail_all or code in self._failures:
            raise ProviderError(f"aggregator unavailable for {code}")
        return list(self._events.get(code, []))

    def _translate(self, event_id: str | None, raw: str, at: datetime) -> CarrierEvent:
        return CarrierEvent(
            event_id=event_id,
            status_raw=raw,
            normalized=self.mapping.get(raw.strip().upper(), NormalizedStatus.EXCECAO),
            occurred_at=at if at.tzinfo else at.replace(tzinfo=timezone.utc),
            carrier=self.carrier,
        )


class FakeAggregadorProvider(_MemoryProviderBase):
    """Dialeto A do agregador fictício."""

    carrier = "agregador-fake"
    mapping = {
        "POSTED": NormalizedStatus.POSTADO,
        "IN_TRANSIT": NormalizedStatus.EM_TRANSITO,
        "OUT_FOR_DELIVERY": NormalizedStatus.SAIU_PARA_ENTREGA,
        "DELIVERED": NormalizedStatus.ENTREGUE,
        "EXCEPTION": NormalizedStatus.EXCECAO,
    }


class CarrierXProvider(_MemoryProviderBase):
    """Dialeto B: prova de que o agregador é trocável (mesmo contrato)."""

    carrier = "carrier-x"
    mapping = {
        "PACOTE_POSTADO": NormalizedStatus.POSTADO,
        "EM_ROTA": NormalizedStatus.EM_TRANSITO,
        "SAIU_PARA_ENTREGA": NormalizedStatus.SAIU_PARA_ENTREGA,
        "ENTREGUE_CRIADOR": NormalizedStatus.ENTREGUE,
        "EXTRAVIO_AVARIA": NormalizedStatus.EXCECAO,
    }
