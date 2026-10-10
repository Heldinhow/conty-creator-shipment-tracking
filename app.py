"""API do rastreio: cadastra código, consulta status estável, expõe atraso."""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from domain import NormalizedStatus, Shipment, apply_events, normalize_code
from provider import (
    FakeAggregadorProvider,
    ProviderError,
    ShipmentRepository,
    SystemClock,
)

DEFAULT_SLA_HOURS = float(os.getenv("TRANSIT_SLA_HOURS", "72"))

app = FastAPI(title="Conty — Rastreio do produto ao criador")

repo = ShipmentRepository()
provider = FakeAggregadorProvider()
clock = SystemClock()


class ShipmentIn(BaseModel):
    code: str
    sla_hours: float | None = None

    @field_validator("code")
    @classmethod
    def code_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("code é obrigatório")
        return v

    @field_validator("sla_hours")
    @classmethod
    def sla_positive(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("sla_hours deve ser > 0")
        return v


def _payload(s: Shipment) -> dict:
    return {
        "code": s.code,
        "status": s.status.value,
        "last_valid_status": s.last_valid_status.value if s.last_valid_status else None,
        "delayed": s.delayed,
        "stale": s.stale,
        "t0": s.t0.isoformat() if s.t0 else None,
        "sla_hours": s.sla_hours,
        "history": [
            {
                "event_id": e.event_id,
                "status_raw": e.status_raw,
                "normalized": e.normalized.value,
                "occurred_at": e.occurred_at.isoformat(),
                "carrier": e.carrier,
            }
            for e in s.history
        ],
    }


def _synchronize(shipment: Shipment) -> None:
    try:
        events = provider.fetch_events(shipment.code)
    except ProviderError:
        shipment.stale = True
    else:
        shipment.stale = False
        apply_events(shipment, events, clock.now())
        repo.save(shipment)
        return
    # Degradada: recalcula o atraso com o relógio atual sobre o último estado.
    apply_events(shipment, [], clock.now())
    repo.save(shipment)


@app.post("/shipments", status_code=201)
def create_shipment(body: ShipmentIn):
    code = normalize_code(body.code)
    existing = repo.get(code)
    if existing:
        _synchronize(existing)
        return JSONResponse(status_code=200, content=_payload(existing))
    shipment = Shipment(
        code=code,
        sla_hours=body.sla_hours or DEFAULT_SLA_HOURS,
        created_at=clock.now(),
    )
    repo.save(shipment)
    _synchronize(shipment)
    return _payload(shipment)


@app.get("/shipments/{code}")
def get_shipment(code: str):
    shipment = repo.get(normalize_code(code))
    if shipment is None:
        raise HTTPException(status_code=404, detail="código não cadastrado")
    _synchronize(shipment)
    return _payload(shipment)


@app.get("/shipments/{code}/events")
def get_events(code: str):
    shipment = repo.get(normalize_code(code))
    if shipment is None:
        raise HTTPException(status_code=404, detail="código não cadastrado")
    return {
        "code": shipment.code,
        "events": [
            {
                "event_id": e.event_id,
                "status_raw": e.status_raw,
                "normalized": e.normalized.value,
                "occurred_at": e.occurred_at.isoformat(),
                "carrier": e.carrier,
            }
            for e in shipment.history
        ],
    }


@app.get("/health")
def health():
    return {"ok": True}
