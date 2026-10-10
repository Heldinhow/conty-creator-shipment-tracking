# 03: Exceção — desconhecido, destravamento e terminal

**What to build:** status que a transportadora inventou vira exceção visível sem virar entregue, sem perder o último válido, com saída quando um evento válido chega e com entregue travando o status.

**Blocked by:** 02 (Tradução monotônica + dedup + fora de ordem).

**Status:** ready-for-agent

- [ ] raw desconhecido → status exibido `excecao`, preservando last_valid_status + rank; bruto vai ao histórico
- [ ] Evento válido com rank ≥ preservado destrava a exceção para o válido
- [ ] Desconhecidos repetidos deduplicam; distintos geram 1 entrada cada sem mover rank
- [ ] Após entregue, status congela mas histórico continua auditando (exceção tardia não regride)
- [ ] Teste com status inventado + teste de destravamento + teste pós-entregue

Decisão prototipada (do grilling):
```
on raw_event:
  normalized = adapter.map(raw)  # desconhecido -> excecao
  if normalized == excecao: status = excecao (preserva last_valid + rank)
  elif rank(normalized) >= rank_preservado and status != entregue: status = normalized
```
