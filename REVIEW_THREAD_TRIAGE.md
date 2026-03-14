# Review Thread Triage

Objetivo: separar threads abertos em grupos claros, sem misturar bloqueante real com ruido.

Data de corte: 2026-03-14
PR: #2

## Escopo desta rodada
- alvo: 22 threads ativos de `codereviewbot-ai` (nao outdated, nao resolved)
- regra: corrigir risco real pequeno agora; evitar refactor amplo transversal

## Matriz item a item (22/22)

1. `access_convert.py:489` (complexidade try_access_parser)
- classe: refactor amplo
- decisao: nao aplicar agora
- motivo: comentario generico de manutencao, sem bug funcional novo

2. `converters/common.py:29` (date parse fragil)
- classe: corrigido antes
- evidencia: validacao por `datetime.date` ja implementada

3. `converters/common.py:45` (validate_cli_input string errors)
- classe: refactor amplo
- decisao: nao aplicar agora
- motivo: mudanca de contrato em 3 CLIs e testes derivados

4. `converters/convert_jackcess.py:267` (list_access_files sem try)
- classe: corrigido antes
- evidencia: `batch_import` ja envolve `list_access_files` em try/except

5. `converters/convert_mdbtools.py:198` (string status em main)
- classe: refactor amplo
- decisao: nao aplicar agora
- motivo: sem bug aberto de execucao; melhoria estrutural

6. `converters/convert_pyodbc.py:230` (erro generico em main)
- classe: refactor amplo
- decisao: nao aplicar agora
- motivo: mesmo racional do item 5

7. `interface/access_parser_utils.py:205` (`to_dict` com catch amplo)
- classe: corrigido antes
- evidencia: hoje registra warning com detalhe de excecao

8. `interface/access_parser_utils.py:67` (import parser com pouca rastreabilidade)
- classe: corrigido neste slice
- evidencia: log debug adicionado para ambas tentativas de import

9. `interface/compare_dbs.py:461` (except Exception amplo)
- classe: corrigido antes
- evidencia: separacao entre excecoes esperadas e `logger.exception` para inesperadas

10. `interface/find_record_across_dbs.py:556` (erro de tabela interrompia varredura)
- classe: corrigido antes
- evidencia: loop atual agrega `table_errors` e continua nas demais tabelas

11. `interface/find_record_across_dbs.py:283` (diagnostico connect_access)
- classe: corrigido neste slice
- evidencia: coleta de erros por tentativa e mensagem agregada de fallback

12. `main.py:28` (race em check de porta)
- classe: falso positivo parcial
- decisao: manter
- motivo: corrida TOCTOU e conhecida por natureza; startup ja trata bind error real

13. `static/app_bootstrap_actions.js:214` (erro API start_index)
- classe: corrigido neste slice
- evidencia: mensagem ao operador sanitizada; detalhe mantido em log

14. `static/app_priority.js:60` (robustez de escapeHtml)
- classe: mitigado neste slice
- evidencia: `escapeHtml` global reforcado para aspas simples/duplas

15. `static/app_results.js:911` (feedback export CSV insuficiente)
- classe: corrigido neste slice
- evidencia: banner de erro + log com detalhe + texto de alerta explicito

16. `static/app_search.js:73` (deleteUpload sem erro explicito)
- classe: corrigido antes
- evidencia: fluxo atual mostra erro de backend em `setSearchMeta`

17. `static/app_search.js:125` (selectDbFromTab erro generico)
- classe: corrigido antes
- evidencia: fluxo atual mostra `j.error` quando presente

18. `static/compare_dbs.html:673` (validacao de upload ausente)
- classe: corrigido neste slice
- evidencia: validacao de extensao `.duckdb/.db` no handler de upload

19. `static/compare_dbs.html:845` (sem loading/feedback export)
- classe: corrigido antes
- evidencia: botoes usam `setButtonBusy` + status/flow de sucesso/erro

20. `static/compare_dbs.js:219` (postJson sem tratamento de rede)
- classe: corrigido neste slice
- evidencia: `fetch` agora em try/catch com erro `status=0`

21. `static/compare_dbs_actions.js:427` (risco de memoria em export)
- classe: corrigido neste slice
- evidencia: limite `MAX_EXPORT_PAGES` e erro explicito para recorte grande

22. `static/compare_dbs_actions.js:120` (estado UI em loadTables)
- classe: mitigado neste slice
- evidencia: painel overview nao abre sem cache apos falha de geracao

## Resumo da separacao (sem ambiguidade)
- corrigido antes: 8
- corrigido neste slice: 8
- mitigado neste slice: 2
- falso positivo parcial: 1
- refactor amplo (nao aplicar agora): 3
