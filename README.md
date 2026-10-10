# Conty — Rastreio do produto enviado ao criador

API que acompanha o pacote físico até a mão do criador e responde: **chegou? atrasou?**
Traduz qualquer dialeto da transportadora (via agregador) para 5 estados estáveis.

## Rodar

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python fake_server.py --port 8100 &   # agregador fictício
TRANSIT_SLA_HOURS=72 FAKE_BASE_URL=http://127.0.0.1:8100 .venv/bin/uvicorn app:app --port 8000
.venv/bin/python -m pytest tests/ -q
```

## Endpoints

| Método | Rota | Resposta |
|---|---|---|
| POST | `/shipments` `{"code": "AB123", "sla_hours": 48}` | 201 (novo) / 200 (duplicata idempotente) |
| GET | `/shipments/{code}` | estado + `delayed` + `history` |
| GET | `/shipments/{code}/events` | bruto × normalizado lado a lado |

`GET /shipments/{code}` retorna `{code, status, last_valid_status, delayed, stale, t0, sla_hours, history[]}`.
Código inexistente local = 404; agregador fora = 200 com `stale: true` e último estado.

## Exemplo: payload bruto → status normalizado

O agregador entrega isto (repetido, fora de ordem, com dialeto próprio):

```json
[
  {"id": "e2", "status_raw": "IN_TRANSIT", "occurred_at": "2026-01-05T10:00:00+00:00", "carrier": "agregador-fake"},
  {"id": "e1", "status_raw": "POSTED", "occurred_at": "2026-01-05T07:00:00+00:00", "carrier": "agregador-fake"},
  {"id": "e2", "status_raw": "IN_TRANSIT", "occurred_at": "2026-01-05T10:00:00+00:00", "carrier": "agregador-fake"},
  {"id": "e9", "status_raw": "ZBLORP_INVENTADO", "occurred_at": "2026-01-05T11:00:00+00:00", "carrier": "agregador-fake"}
]
```

A API responde isto (`GET /shipments/AB123`):

```json
{
  "code": "AB123",
  "status": "excecao",
  "last_valid_status": "em_transito",
  "delayed": false,
  "stale": false,
  "history": [
    {"status_raw": "POSTED", "normalized": "postado"},
    {"status_raw": "IN_TRANSIT", "normalized": "em_transito"},
    {"status_raw": "ZBLORP_INVENTADO", "normalized": "excecao"}
  ]
}
```

Regras: `ZBLORP_INVENTADO` (desconhecido) vira `excecao`, nunca `entregue`;
o `IN_TRANSIT` repetido entra 1 vez; o histórico ordena por `occurred_at`.

## Como o atraso é detectado (sem marcar entrega normal como atraso)

- `t0` = `occurred_at` do primeiro `postado`; se o código foi cadastrado já em
  trânsito, o menor `occurred_at` conhecido; se zero eventos, o cadastro.
- Em curso (`postado`, `em_transito`, `saiu_para_entrega`):
  `delayed = agora − t0 > SLA` (SLA global via `TRANSIT_SLA_HOURS`, default 72h,
  com override por código).
- `excecao` sozinha **nunca** marca atraso (evita duplo alerta).
- `entregue` **congela** o veredito: `delayed = delivered_at − t0 > SLA`.
  Entrega no prazo = `false` mesmo que o SLA tenha estourado no meio do caminho.

## Testes

```bash
.venv/bin/python -m pytest tests/ -q   # 21 testes, fake HTTP sobe sozinho
```

- `test_02`: lote fora de ordem não regride; reconsulta não duplica.
- `test_03`: status inventado vira exceção (nunca entregue) + destravamento.
- `test_04`: atraso com relógio fixo (estourado / no prazo / entregue-atrasada / exceção / cadastro tardio).
- `test_05`: agregador fora degrada com `stale`; 2º dialeto passa no mesmo contrato.

## Arquitetura

`API → Service → TrackingProvider (interface) → cliente HTTP`.
O fake (`fake_server.py`) é HTTP de verdade; o mapa `raw → normalizado` mora
**só** no adapter (`provider.py`): trocar o agregador = implementar
`fetch_events` (há 2 dialetos com o mesmo contrato, `test_05`). Relógio e
repositório (em memória) também são portas, para data controlada e troca de persistência.

## Nota de IA (exigida pelo enunciado)

- **Feito com IA:** esqueleto da API, máquina de estado, adapters e testes.
- **Revisado por humano:** regra de atraso (congelamento da entregue),
  semântica de exceção (exibir + preservar último válido) e este README.
