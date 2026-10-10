# 04: Atraso com clock fixo + t0 em cascata

**What to build:** o campo delayed diz com precisão se o pacote estourou o SLA, com tempo controlado nos testes, sem marcar entrega no prazo como atraso e funcionando mesmo para cadastro tardio.

**Blocked by:** 02 (Tradução monotônica + dedup + fora de ordem).

**Status:** resolved

**Resolution:** done on integration/rastreio-produto (948a508), 19 testes verdes

- [ ] delayed só para postado / em trânsito / saiu para entrega com now(clock) − t0 > sla
- [ ] t0 em cascata: occurred_at do 1º postado → menor occurred_at conhecido → created_at local provisório
- [ ] excecao sozinha nunca marca delayed
- [ ] entregue congela delayed = delivered_at − t0 > sla (no prazo = false, atrasada = true)
- [ ] SLA global via env (default 72h) + override por shipment; testes com clock fixo nos 4 casos
