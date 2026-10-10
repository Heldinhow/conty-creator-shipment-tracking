# 01: Esqueleto — cadastro idempotente + consulta base

**What to build:** operador cadastra um código e consulta o estado atual de ponta a ponta: POST cria e já sincroniza com o agregador, GET retorna o estado, código local inexistente dá 404. O fake do agregador responde no schema congelado.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] POST /shipments com `{code, sla_hours?}` cria e retorna estado inicial (sync imediato no agregador)
- [ ] Re-POST do mesmo code retorna 200 idempotente sem duplicar nem sobrescrever SLA
- [ ] GET /shipments/{code} retorna `{code, status, delayed, stale, t0, sla_hours, history[]}`; local inexistente = 404
- [ ] code com strip + case-insensitive
- [ ] Fake do agregador no ar com schema `events[{id, status_raw, occurred_at, carrier}]`
