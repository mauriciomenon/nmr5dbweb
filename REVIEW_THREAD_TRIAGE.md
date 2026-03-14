# Review Thread Triage

Objetivo: separar threads abertos em grupos claros, sem misturar bloqueante real com ruido.

Data de corte: 2026-03-14
PR: #2

## Grupo A - corrigido no ciclo atual

1. `access_convert.py` - strict consistency quando nenhuma tabela materializa
- status: corrigido
- commit: `da333a8`

2. `interface/access_parser_utils.py` - fallback de descoberta de tabelas
- status: corrigido
- commit: `c367a90`

3. `main.py` hint cross-platform e scripts de setup
- status: corrigido
- commit: `32bf079`

4. `no-undef` totalmente desligado em configs lint
- status: mitigado com visibilidade (`warn`)
- commit: `5e317ca`

## Grupo B - pequenos e reais, ja corrigidos antes deste ciclo

1. modal timer stale guard
2. auto-index toggle com tratamento de falha
3. bind drag/drop idempotente
4. mensagens de erro de select/delete no app_search

Status: ja presente no branch atual e validado em ciclos anteriores.

## Grupo C - falsos positivos ou alertas genericos de ferramenta

1. "refactor por complexidade" sem bug concreto (qlty/radarlint)
2. "many returns/many params" sem regressao funcional
3. alertas genericos de subprocess com input fixo interno

Status: nao bloqueante no estado atual.
Acao: manter monitorado e atacar so quando tocar no mesmo bloco por necessidade funcional.

## Grupo D - melhorias validas, mas fora de escopo curto

1. migrar validacao CLI string->typed errors em todos os converters
2. quebra de arquivos grandes para reduzir complexidade global
3. endurecer ainda mais mensagens/telemetria em todos os pontos de UI

Status: backlog tecnico.
Acao: executar em epicos dedicados para nao gerar refactor transversal arriscado.
