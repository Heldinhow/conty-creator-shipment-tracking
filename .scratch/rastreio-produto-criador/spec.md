# Spec — Rastreio do produto enviado ao criador

Status: ready-for-agent

## Problem Statement

Parte das campanhas da Conty depende de um produto físico na mão do criador: o prazo de entrega do conteúdo só faz sentido depois que o pacote chega. Cada transportadora fala um dialeto diferente, o agregador de rastreio entrega eventos repetidos e fora de ordem, e hoje não há uma leitura estável (postado / em trânsito / saiu para entrega / entregue / exceção) nem um sinal confiável de atraso para a operação decidir quando cobrar o criador.

## Solution

Uma API mínima que cadastra códigos de rastreio, consulta um agregador fictício atrás de uma interface trocável, normaliza qualquer dialeto para 5 estados estáveis com máquina de estado monotônica, deduplica reconsultas, detecta atraso via relógio injetável sem marcar entrega no prazo como atraso, e documenta tudo no README com exemplo bruto vs normalizado + nota de IA/revisão.

## User Stories

1. Como operador de campanha, quero cadastrar um código de rastreio com SLA opcional, para que o pacote do criador entre em acompanhamento.
2. Como operador de campanha, quero recadastrar o mesmo código e receber o estado atual sem duplicar nada, para que retries sejam seguros.
3. Como operador de campanha, quero consultar um código e ver status, delayed, t0 e histórico, para que eu saiba se cobro conteúdo ou espero o pacote.
4. Como operador de campanha, quero que a consulta sincronize com o agregador e volte degradada (stale) se ele falhar, para que a operação não pare.
5. Como operador de campanha, quero que status inventado da transportadora vire exceção visível sem nunca virar entregue, para que dado sujo não libere prazo de conteúdo.
6. Como operador de campanha, quero que a exceção preserve o último status válido, para que a tela não perca o contexto quando chegar sujeira.
7. Como operador de campanha, quero que um evento válido posterior destrave a exceção, para que recuperação da transportadora se reflita.
8. Como operador de campanha, quero que evento antigo que chega depois não regrida o status, para que o progresso do pacote seja monotônico.
9. Como operador de campanha, quero que reconsulta não duplique o histórico, para que o timeline seja auditável.
10. Como operador de campanha, quero ver o histórico ordenado por occurred_at com bruto + normalizado lado a lado, para que eu audite o que a transportadora disse.
11. Como operador de campanha, quero que atraso só marque pacotes em curso (postado, em trânsito, saiu para entrega) com tempo em trânsito acima do SLA, para que alerta signifique ação.
12. Como operador de campanha, quero que exceção sozinha nunca marque atraso, para que eu não receba duplo alerta.
13. Como operador de campanha, quero que entrega no prazo nunca apareça como atraso mesmo se o SLA estourou no meio do caminho, para que criador pontual não seja cobrado.
14. Como operador de campanha, quero que entrega após o SLA congele delayed como true, para que o atraso fique registrado.
15. Como operador de campanha, quero cadastrar código já em trânsito e ainda ter atraso detectado, para que cadastro tardio funcione.
16. Como operador de campanha, quero um SLA global configurável com override por código, para que rotas lentas tenham tolerância própria.
17. Como engenheiro da Conty, quero trocar o agregador implementando uma interface sem tocar no domínio, para que dialetos novos não vazem.
18. Como engenheiro da Conty, quero o mapa raw→normalizado confinado no adapter HTTP, para que o service só conheça o enum estável.
19. Como engenheiro da Conty, quero consultar código inexistente local e receber 404, para que cliente diferencie erro seu de falha externa.
20. Como engenheiro da Conty, quero um fake HTTP do agregador com schema congelado para testes e README, para que o contrato seja demonstrável.
21. Como avaliador do desafio, quero ver no README exemplo de payload bruto e status normalizado, para que eu confira a tradução.
22. Como avaliador do desafio, quero ler no README como o atraso é detectado sem marcar entrega normal como atraso, para que eu valide a regra.
23. Como avaliador do desafio, quero ver teste com eventos fora de ordem e com status inventado, para que eu confira as invariantes.
24. Como avaliador do desafio, quero ler a nota do que foi feito com IA e o que foi revisado, para que a entrega entre em avaliação.

## Implementation Decisions

- **Seams (3 portas, 1 costura principal):** a costura principal e mais alta é a `TrackingProvider` (interface do agregador) — todo teste de tradução, fora de ordem e status inventado passa por ela com o fake. As outras duas portas são `Clock` (tempo injetável) e `ShipmentRepository` (memória atrás de interface, trocável por SQLite/Postgres). Nenhuma costura nova além dessas três.
- **Stack:** Python 3.12 + FastAPI + Pydantic + httpx + pytest; repo em memória na v1, sem banco, sem Docker, sem fila.
- **API:** `POST /shipments {code, sla_hours?}` cria + sincroniza imediatamente, duplicata retorna 200 idempotente sem sobrescrever SLA; `GET /shipments/{code}` sincroniza e retorna `{code, status, last_valid_status, delayed, stale, t0, sla_hours, history[]}`; `GET /shipments/{code}/events` debug com bruto + normalizado. `code` com strip + case-insensitive. Local inexistente = 404; falha do agregador = 200 com `stale:true` e último estado.
- **Máquina de estado:** rank `postado(1) < em trânsito(2) < saiu para entrega(3) < entregue(4)`; `excecao` lateral que nunca vira entregue e nunca regride rank; evento com rank ≤ atual não move status; `entregue` congela o status mas o histórico continua auditando.
- **Exceção (decisão prototipada):**
  ```
  on raw_event:
    normalized = adapter.map(raw)  # desconhecido -> excecao, mapa mora NO adapter
    if normalized == excecao: status = excecao (preserva last_valid_status + rank)
    elif rank(normalized) >= rank_preservado and status != entregue: status = normalized
    history.append({raw, normalized, occurred_at}) deduplicado
  ```
- **Dedup:** chave `event_id`, fallback hash `(carrier + raw_status + occurred_at)`; histórico ordenado por `occurred_at`.
- **`t0` em cascata:** `occurred_at` do primeiro `postado` → menor `occurred_at` conhecido → `created_at` local provisório, recalculado ao chegar o 1º evento.
- **Atraso:** `delayed = status in {postado, em trânsito, saiu para entrega} and (now(clock) - t0 > sla)`; `entregue` congela `delivered_at - t0 > sla`; `excecao` nunca marca atraso. SLA global via env, default 72h, override por shipment, sem PATCH na v1. "Avisar" = campo `delayed`, sem webhook/push.
- **Schema congelado do fake:** `events[{id, status_raw, occurred_at, carrier}]` — mesmo JSON no README e nos testes.
- **Higiene do diff:** nada de AGENTS.md, regras de editor ou textos para assistente/agente no diff — reprova no enunciado. Entrega = API + adapter + README + testes + nota IA.

## Testing Decisions

- O que é um bom teste aqui: só comportamento externo via HTTP + fake (status exibido, delayed, tamanho do histórico, códigos HTTP), nunca detalhes internos de implementação.
- Módulos testados (via as 3 portas, sem mocks internos): tradução/mapeamento, monotonicidade fora de ordem, dedup em reconsulta, desconhecido→exceção + destravamento, atraso com clock fixo (no prazo = false, atrasada = true, em curso estourado = true, exceção = false), degradação stale, troca de agregador (segundo adapter com dialeto distinto passando nos mesmos testes de contrato).
- Prior art: repo greenfield, sem testes existentes; pytest + httpx TestClient + fake HTTP local como padrão único.

## Out of Scope

Auth, paginação, listagem de shipments, PATCH/remoção de SLA, webhooks ou jobs de notificação, persistência durável (SQLite/Postgres), retries/backoff sofisticados, concorrência com locks, múltiplos agregadores simultâneos, rastreio de conteúdo da campanha (só o pacote).

## Further Notes

Critério de aceite = os 5 itens do enunciado (desconhecido≠entregue; sem regressão; sem duplicata; atraso com data controlada; agregador trocável) + README com os 4 elementos (payload bruto vs normalizado, regra de atraso, testes citados, nota IA/revisão). Se qualquer decisão acima conflitar com teste do avaliador, o teste do enunciado vence.
