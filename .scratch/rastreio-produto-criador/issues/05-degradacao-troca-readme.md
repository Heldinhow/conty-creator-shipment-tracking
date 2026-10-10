# 05: Degradação + prova de troca + README

**What to build:** a API sobrevive ao agregador fora, prova que o agregador é trocável com um segundo dialeto, e o README entrega os 4 elementos exigidos pelo enunciado.

**Blocked by:** 03 (Exceção), 04 (Atraso com clock fixo).

**Status:** resolved

**Resolution:** done on integration/rastreio-produto (948a508), 19 testes verdes

- [ ] Agregador fora/timeout/500 ou código inexistente lá → 200 com último estado + stale:true (só local inexistente dá 404)
- [ ] Segundo adapter com dialeto distinto passa no mesmo teste de contrato sem tocar no domínio/service
- [ ] GET /shipments/{code}/events debug com bruto + normalizado
- [ ] README com exemplo de payload bruto vs normalizado, como o atraso é detectado sem marcar entrega normal como atraso, testes citados e nota IA (feito com IA × revisado)
- [ ] Diff sem AGENTS.md, regras de editor ou textos para assistente/agente
