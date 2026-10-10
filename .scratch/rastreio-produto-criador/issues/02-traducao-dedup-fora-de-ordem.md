# 02: Tradução monotônica + dedup + fora de ordem

**What to build:** qualquer dialeto da transportadora aparece como um dos 5 estados estáveis, o progresso nunca anda para trás e reconsultar nunca duplica o timeline.

**Blocked by:** 01 (Esqueleto — cadastro idempotente + consulta base).

**Status:** ready-for-agent

- [ ] Mapa raw→normalizado confinado no adapter HTTP; service só recebe o enum estável
- [ ] Rank postado < em trânsito < saiu para entrega < entregue; evento com rank menor/igual não move o status
- [ ] Dedup por event_id com fallback hash (carrier + raw + occurred_at); reconsulta não cresce o histórico
- [ ] history[] ordenado por occurred_at com bruto + normalizado lado a lado
- [ ] Teste com lote fora de ordem não regride; teste de reconsulta não duplica
