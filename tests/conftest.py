import socket
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

import app as appmod
from fake_server import Store, build_app
from provider import FakeAggregadorProvider, FixedClock, ShipmentRepository

T0 = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)  # relógio fixo: data controlada


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def fake():
    """Agregador fictício rodando HTTP de verdade (uvicorn em thread)."""
    store = Store()
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(build_app(store), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{base_url}/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        raise RuntimeError("fake aggregator não subiu")
    yield SimpleNamespace(base_url=base_url, store=store)
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def client(fake):
    fake.store.reset()
    appmod.repo = ShipmentRepository()
    appmod.provider = FakeAggregadorProvider(fake.base_url)
    appmod.clock = FixedClock(T0)
    return TestClient(appmod.app)
