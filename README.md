# Conty. Rastreio do produto ao criador

API que acompanha o pacote físico até a mão do criador e responde **chegou? atrasou?** Cada transportadora fala um dialeto; o agregador traduz tudo para 5 estados estáveis (`postado`, `em_transito`, `saiu_para_entrega`, `entregue`, `excecao`), com atraso medido contra um SLA em horas.

## Regras principais

- Progresso monotônico `postado < em_transito < saiu_para_entrega < entregue`: evento antigo que chega depois não regride; `entregue` trava o status (o histórico continua auditando).
- Status desconhecido vira `excecao` — nunca `entregue` — preservando `last_valid_status`; um evento válido posterior destrava.
- Reconsulta não duplica: dedup por `event_id` (fallback hash de `carrier|raw|occurred_at`); histórico sempre ordenado por `occurred_at`.
- `delayed` só em curso com `agora − t0 > SLA`; `excecao` sozinha nunca atrasa; `entregue` congela `delivered_at − t0 > SLA`. `t0` = primeiro `postado` → menor `occurred_at` → cadastro.
- Agregador fora = `200` com `stale: true` e último estado; o mapa `raw → normalizado` mora só no adapter.

## Como rodar

Runtime: Python 3.14, `venv`, sem banco.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python fake_server.py --port 8100 &   # agregador fictício
TRANSIT_SLA_HOURS=72 FAKE_BASE_URL=http://127.0.0.1:8100 .venv/bin/uvicorn app:app --port 8000
.venv/bin/python -m pytest tests/ -q   # 21 testes; o fake HTTP sobe sozinho
```

Fluxo copiável (com o fake e a API no ar):

```bash
curl -X POST localhost:8000/shipments -H 'Content-Type: application/json' -d '{"code":"AB123"}'
curl localhost:8000/shipments/AB123
curl localhost:8000/shipments/AB123/events
```

Sem seed fixo: os testes semeiam o fake via `Store.seed`. Os testes descrevem o comportamento esperado.

## Contrato da API

| Método | Rota | Sucesso | Erros |
|---|---|---|---|
| POST | `/shipments` `{"code": "AB123", "sla_hours": 48}` (`sla_hours` opcional) | `201` novo, `200` duplicata idempotente (mantém o SLA original) | `422` `code` vazio ou `sla_hours <= 0` |
| GET | `/shipments/{code}` | `200` `{code, status, last_valid_status, delayed, stale, t0, sla_hours, history[]}` | `404` código não cadastrado |
| GET | `/shipments/{code}/events` | `200` `{code, events[]}` com bruto × normalizado | `404` código não cadastrado |
| GET | `/health` | `200` `{"ok": true}` | — |

Precedência de erros: `404` (código inexistente local) > `422` (validação) > `200` com `stale: true` (agregador fora/timeout/500 — degrada, não quebra). `code` com strip + case-insensitive (`" ab123 "` = `"AB123"`).

## Exemplos

Sucesso com sujeira da transportadora — o agregador entrega (repetido, fora de ordem, dialeto próprio):

```json
[
  {"id": "e2", "status_raw": "IN_TRANSIT", "occurred_at": "2026-01-05T10:00:00+00:00", "carrier": "agregador-fake"},
  {"id": "e1", "status_raw": "POSTED", "occurred_at": "2026-01-05T07:00:00+00:00", "carrier": "agregador-fake"},
  {"id": "e2", "status_raw": "IN_TRANSIT", "occurred_at": "2026-01-05T10:00:00+00:00", "carrier": "agregador-fake"},
  {"id": "e9", "status_raw": "ZBLORP_INVENTADO", "occurred_at": "2026-01-05T11:00:00+00:00", "carrier": "agregador-fake"}
]
```

`GET /shipments/AB123` responde:

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

O repetido entra 1 vez; o desconhecido vira `excecao`, nunca `entregue`.

Erro — código nunca cadastrado:

```
GET /shipments/NOPE → 404 {"detail": "código não cadastrado"}
```

Degradação — agregador fora do ar, último estado preservado:

```json
{"code": "AB123", "status": "em_transito", "delayed": false, "stale": true, "history": []}
```

## Fora de escopo

Sem banco durável (repositório em memória atrás de interface), sem auth, sem webhook/push ("avisar" = campo `delayed`), sem UI, sem concorrência com locks, sem múltiplos agregadores simultâneos.

## Uso de IA

### Feito com IA

Esqueleto da API, máquina de estado monotônica, cliente HTTP + 2 dialetos, fake HTTP e os 21 testes.

### Revisado por humano

Regra de atraso (congelamento da entregue), semântica de exceção (exibir + preservar último válido), degradação `stale` e este README. Comandos rodados: `pytest tests/ -q` (21 passed).

O contrato é este README e os testes.
