"""Agregador fictício: HTTP de verdade, para os testes e o README.

Roda com `python fake_server.py --port 8100`. Guarda eventos brutos por
código, pode devolver repetidos/fora de ordem e pode falhar sob demanda.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from fastapi import FastAPI, Response


class Store:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.events: dict[str, list[dict]] = {}
        self.failures: set[str] = set()
        self.fail_all = False

    def seed(
        self,
        code: str,
        raws: list[tuple[str | None, str, datetime]],
        carrier: str = "agregador-fake",
    ) -> None:
        self.events[code.upper()] = [
            {
                "id": event_id,
                "status_raw": raw,
                "occurred_at": (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).isoformat(),
                "carrier": carrier,
            }
            for event_id, raw, at in raws
        ]

    def fail_for(self, code: str) -> None:
        self.failures.add(code.upper())


def build_app(store: Store) -> FastAPI:
    app = FastAPI(title="Agregador fictício de rastreio")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/track/{code}")
    def track(code: str):
        code = code.upper()
        if store.fail_all or code in store.failures:
            return Response(status_code=500, content='{"detail":"aggregator unavailable"}')
        return {"events": store.events.get(code, [])}

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()
    import uvicorn

    uvicorn.run(build_app(Store()), host="127.0.0.1", port=args.port)
