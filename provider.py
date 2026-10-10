"""Portas: relógio, repositório e o agregador atrás de interface.

O cliente HTTP fala com o agregador fictício; o mapa raw -> normalizado mora
aqui, no adapter. O service/domínio só recebe NormalizedStatus: trocar o
agregador = implementar TrackingProvider.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import httpx

from domain import NormalizedStatus, Shipment, TrackingEvent


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
    def fetch_events(self, code: str) -> list[TrackingEvent]: ...


class HttpTrackingProvider:
    """Cliente HTTP do agregador; cada dialeto é uma subclasse com seu mapa."""

    carrier = "agregador-fake"
    mapping: dict[str, NormalizedStatus] = {}

    def __init__(self, base_url: str, timeout: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def fetch_events(self, code: str) -> list[TrackingEvent]:
        try:
            response = httpx.get(f"{self.base_url}/track/{code}", timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise ProviderError(f"aggregator unreachable: {exc}") from exc
        if response.status_code != 200:
            raise ProviderError(f"aggregator failed with {response.status_code}")
        try:
            items = response.json()["events"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError(f"aggregator returned malformed payload: {exc}") from exc
        if not isinstance(items, list):
            raise ProviderError("aggregator returned malformed payload: events is not a list")
        return [self._translate(item) for item in items]

    def _translate(self, item: dict) -> TrackingEvent:
        try:
            raw = item["status_raw"]
            at = datetime.fromisoformat(item["occurred_at"])
            event_id = item["id"]
        except (KeyError, TypeError, ValueError) as exc:
            # Payload fora do formato degrada para stale em vez de 500:
            # _synchronize só conhece ProviderError.
            raise ProviderError(f"aggregator returned malformed event: {exc}") from exc
        if not isinstance(raw, str):
            raise ProviderError(f"aggregator returned malformed event: status_raw={raw!r}")
        return TrackingEvent(
            event_id=event_id,
            status_raw=raw,
            normalized=self.mapping.get(raw.strip().upper(), NormalizedStatus.EXCECAO),
            occurred_at=at if at.tzinfo else at.replace(tzinfo=timezone.utc),
            carrier=item.get("carrier", self.carrier),
        )


class FakeAggregadorProvider(HttpTrackingProvider):
    """Dialeto A do agregador fictício."""

    carrier = "agregador-fake"
    mapping = {
        "POSTED": NormalizedStatus.POSTADO,
        "IN_TRANSIT": NormalizedStatus.EM_TRANSITO,
        "OUT_FOR_DELIVERY": NormalizedStatus.SAIU_PARA_ENTREGA,
        "DELIVERED": NormalizedStatus.ENTREGUE,
        "EXCEPTION": NormalizedStatus.EXCECAO,
    }


class CarrierXProvider(HttpTrackingProvider):
    """Dialeto B: prova de que o agregador é trocável (mesmo contrato)."""

    carrier = "carrier-x"
    mapping = {
        "PACOTE_POSTADO": NormalizedStatus.POSTADO,
        "EM_ROTA": NormalizedStatus.EM_TRANSITO,
        "SAIU_PARA_ENTREGA": NormalizedStatus.SAIU_PARA_ENTREGA,
        "ENTREGUE_CRIADOR": NormalizedStatus.ENTREGUE,
        "EXTRAVIO_AVARIA": NormalizedStatus.EXCECAO,
    }
