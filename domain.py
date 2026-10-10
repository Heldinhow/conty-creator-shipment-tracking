"""Domínio do rastreio: estados estáveis, máquina monotônica e regra de atraso.

Nada aqui conhece o formato bruto do agregador: o adapter traduz para
NormalizedStatus e o domínio só enxerga o enum.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha1


class NormalizedStatus(str, Enum):
    POSTADO = "postado"
    EM_TRANSITO = "em_transito"
    SAIU_PARA_ENTREGA = "saiu_para_entrega"
    ENTREGUE = "entregue"
    EXCECAO = "excecao"


RANK = {
    NormalizedStatus.POSTADO: 1,
    NormalizedStatus.EM_TRANSITO: 2,
    NormalizedStatus.SAIU_PARA_ENTREGA: 3,
    NormalizedStatus.ENTREGUE: 4,
}

IN_COURSE = frozenset(
    {
        NormalizedStatus.POSTADO,
        NormalizedStatus.EM_TRANSITO,
        NormalizedStatus.SAIU_PARA_ENTREGA,
    }
)


def normalize_code(code: str) -> str:
    return code.strip().upper()


@dataclass
class CarrierEvent:
    """Evento como o adapter entrega: já traduzido, mas com o bruto anexado."""

    event_id: str | None
    status_raw: str
    normalized: NormalizedStatus
    occurred_at: datetime
    carrier: str


@dataclass
class HistoryEntry:
    event_id: str
    status_raw: str
    normalized: NormalizedStatus
    occurred_at: datetime
    carrier: str


@dataclass
class Shipment:
    code: str
    sla_hours: float
    created_at: datetime
    status: NormalizedStatus = NormalizedStatus.POSTADO
    last_valid_status: NormalizedStatus | None = None
    history: list[HistoryEntry] = field(default_factory=list)
    t0: datetime | None = None
    delivered_at: datetime | None = None
    delayed: bool = False
    stale: bool = False


def dedup_key(event_id: str | None, status_raw: str, occurred_at: datetime, carrier: str) -> str:
    if event_id:
        return event_id
    # shortcut: sem id do agregador, colapsa por conteúdo; dois eventos reais
    # idênticos no mesmo instante são indistinguíveis — upgrade: exigir id.
    digest = sha1(f"{carrier}|{status_raw}|{occurred_at.isoformat()}".encode()).hexdigest()[:16]
    return f"hash:{digest}"


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def apply_events(shipment: Shipment, events: list[CarrierEvent], now: datetime) -> None:
    """Funde eventos (deduplicando) e recalcula status/t0/delayed do zero.

    Recalcular do zero a partir do histórico ordenado torna a Monotonicidade
    barata: evento antigo fora de ordem nunca regride, por construção.
    """
    known = {e.event_id for e in shipment.history}
    for ev in events:
        key = dedup_key(ev.event_id, ev.status_raw, ev.occurred_at, ev.carrier)
        if key in known:
            continue
        known.add(key)
        shipment.history.append(
            HistoryEntry(
                event_id=key,
                status_raw=ev.status_raw,
                normalized=ev.normalized,
                occurred_at=_utc(ev.occurred_at),
                carrier=ev.carrier,
            )
        )
    shipment.history.sort(key=lambda e: e.occurred_at)
    _recompute(shipment, _utc(now))


def _recompute(shipment: Shipment, now: datetime) -> None:
    if not shipment.history:
        shipment.status = NormalizedStatus.POSTADO
        shipment.last_valid_status = None
        shipment.t0 = shipment.created_at
        shipment.delivered_at = None
        shipment.delayed = False
        return

    postados = [e.occurred_at for e in shipment.history if e.normalized == NormalizedStatus.POSTADO]
    if postados:
        shipment.t0 = min(postados)
    else:
        shipment.t0 = min(e.occurred_at for e in shipment.history)

    status: NormalizedStatus = NormalizedStatus.POSTADO
    valid_rank = 0
    last_valid: NormalizedStatus | None = None
    delivered_at: datetime | None = None
    locked = False  # entregue trava o status; o histórico continua auditando
    for entry in shipment.history:
        if locked:
            continue
        if entry.normalized == NormalizedStatus.EXCECAO:
            status = NormalizedStatus.EXCECAO
            continue
        rank = RANK[entry.normalized]
        if rank >= valid_rank:
            valid_rank = rank
            status = entry.normalized
            last_valid = entry.normalized
        if entry.normalized == NormalizedStatus.ENTREGUE:
            locked = True
            delivered_at = entry.occurred_at

    shipment.status = status
    shipment.last_valid_status = last_valid
    shipment.delivered_at = delivered_at

    if shipment.status in IN_COURSE and shipment.t0:
        shipment.delayed = (now - shipment.t0).total_seconds() > shipment.sla_hours * 3600
    elif shipment.status == NormalizedStatus.ENTREGUE and shipment.t0 and delivered_at:
        shipment.delayed = (delivered_at - shipment.t0).total_seconds() > shipment.sla_hours * 3600
    else:
        shipment.delayed = False
