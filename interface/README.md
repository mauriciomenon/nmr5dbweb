# Interface — Visão Geral e Relações

Este diretório contém o backend Flask e utilitários para busca local em bases DuckDB (com fallback opcional para Access via ODBC) e a construção do índice `_fulltext`.

## Atualizacao rapida (2026-03-13)

- O contexto de PR ativo para este produto e `mauriciomenon/nmr5dbweb` PR `#2` (`codex/dev` -> `master`).
- O cliente de comparacao agora trata resposta de upload invalida (nao JSON) sem quebrar o fluxo de erro na UI.
- O smoke Windows de conversao Access remove arquivo temporario de saida quando a conversao falha ou nao gera tabelas de usuario.

## Componentes

- `app_flask_local_search.py`: Backend Flask completo para operação local.
  - Upload/seleção/remoção de arquivos: `/admin/upload`, `/admin/select`, `/admin/delete`, `/admin/list_uploads`.
  - Conversão Access→DuckDB (se existir `access_convert.convert_access_to_duckdb`).
  - Status consolidado: `/admin/status` (progresso de conversao, contagem `_fulltext`, top tabelas, sinais de validacao da conversao e backend usado).
  - Iniciar indexação `_fulltext`: `/admin/start_index` (usa `create_fulltext.create_or_resume_fulltext`).
  - Definir prioridade de tabelas: `/admin/set_priority` (afeta ordenação de resultados na UI).
  - Comparacao principal:
    - `/api/compare_db_tables`
    - `/api/compare_db_table_content`
    - `/api/compare_db_overview`
    - `/api/compare_db_rows`
    - contrato atual: comparacao direta somente em DuckDB para o caminho rapido
  - Validacoes de payload de compare:
    - rejeita `change_types` vazio/invalido
    - rejeita colunas duplicadas em `key_columns` e `compare_columns`
    - rejeita filtros/chaves inconsistentes
  - Busca principal `/api/search`:
    - Com `.duckdb`: usa `_fulltext` e ranking `RapidFuzz` (mais rápido e tolerante).
    - Com `.sqlite/.sqlite3/.db` compatíveis com SQLite: busca textual leve sem `_fulltext`.
    - Com `.mdb/.accdb`: fallback via `pyodbc` (se instalado), faz LIKE e ranking em Python.
    - Resposta inclui marcador de engine (`db_engine`) para feedback de UI.
  - Lê/atualiza `config.json` com `db_path`, `priority_tables` e `auto_index_after_convert`.

- `create_fulltext.py`: Indexador seguro de `_fulltext`.
  - Ignora tabelas de sistema e a própria `_fulltext`.
  - Suporta `drop` para reindex do zero e resume a partir do que já foi indexado.
  - Normaliza texto com `utils.normalize_text` e serializa com `utils.serialize_value`.
  - Pode ser usado via CLI: `python interface/create_fulltext.py --db <arquivo.duckdb> [--drop] [--chunk N] [--batch N]`.

- `check_progress.py`: Diagnóstico de progresso.
  - Compara linhas por tabela com o que já está em `_fulltext`.
  - Lista quais tabelas ainda não estão totalmente indexadas.

- `utils.py`: Funções utilitárias comuns.
  - `normalize_text(s)`: remove acentos, lowercase, normaliza pontuação/underscores/hífens e colapsa espaços.
  - `serialize_value(v)`: converte tipos (datas, decimals, bytes etc.) para valores JSON-compatíveis.

## Relações entre arquivos

- UI (`static/index.html`) → chama endpoints do `app_flask_local_search.py`:
  - Estado inicial: `/admin/list_uploads`.
  - Estado consolidado: `/admin/status`.
  - Listar tabelas: `/api/tables`.
  - Busca: `/api/search` (usa `_fulltext` em DuckDB; fallback Access com `pyodbc`).
  - Indexação `_fulltext`: `/admin/start_index`.
  - Prioridade de tabelas: `/admin/set_priority`.
  - Upload/seleção/remoção: `/admin/upload`, `/admin/select`, `/admin/delete`.

- `app_flask_local_search.py` chama:
  - `create_fulltext.create_or_resume_fulltext` para construir/retomar o índice `_fulltext`.
  - `utils.normalize_text` e `utils.serialize_value` (normalização/serialização).
  - Opcional `access_convert.convert_access_to_duckdb` para conversão.

- O backend simples legado foi retirado do caminho principal do produto; para consulta de historico, use o log de commits e o historico git do repositorio.

## Quando precisam estar juntos?

- Para a app completa (uploads, conversão, indexação `_fulltext`, prioridade, compare e rastreio):
  - Necessarios: `app_flask_local_search.py`, `compare_dbs.py`, `find_record_across_dbs.py`, `create_fulltext.py`, `utils.py` e os assets em `static/`.
  - O `check_progress.py` é opcional (diagnóstico).
  - `access_convert.py` é opcional, porém necessário para conversão de `.mdb/.accdb` para `.duckdb` via UI.
  - `pyodbc` é opcional (apenas para fallback Access).

## Dependências

- Obrigatórias (app completa DuckDB): `flask`, `duckdb`, `rapidfuzz`.
- Opcionais: `pyodbc` (fallback Access), `pandas` (se for usar scripts auxiliares), `matplotlib` (gráficos em ferramentas).
- Sistema (para Access): driver ODBC Microsoft Access (Windows) ou configuração equivalente.

## Como rodar

- Produto principal:
```
python interface/app_flask_local_search.py
```
Acesse `http://127.0.0.1:5000/`.

Selecione um DB em "Configurar/Upload"; para `.duckdb`, a busca usa `_fulltext` quando disponível. Para `.mdb/.accdb`, se `pyodbc` estiver instalado, o fallback faz a busca direta.

## Observações

- Apos converter Access->DuckDB, a indexacao automatica pode ser acionada (se `auto_index_after_convert` estiver habilitado).
- O status de conversao inclui validacao por tabela com hashes de amostra (`sample_hash_duckdb` / `sample_hash_sqlite`) para detectar divergencias reais.
- A prioridade de tabelas influencia a ordem de exibição dos resultados.
- Use `check_progress.py` para verificar se `_fulltext` já cobre todas as tabelas.
- A interface principal do produto não depende mais de um backend Flask alternativo/simplificado.
