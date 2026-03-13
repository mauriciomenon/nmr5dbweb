# nmr5dbweb

Ferramenta web para trabalhar com bases Access (`.accdb`/`.mdb`) com foco em uso pratico:
- converter para DuckDB
- gerar SQLite derivado
- validar conversao
- buscar dados
- comparar versoes

## Objetivo

Este repo e produto, nao POC.
Fluxo principal:
1. entrada Access
2. saida DuckDB + SQLite
3. validacao obrigatoria
4. uso na UI (busca/comparacao)

## Setup rapido

Requisito:
- Python 3.13.12 (fallback 3.13.11)
- `uv`

```bash
uv venv --python 3.13.12 .venv || uv venv --python 3.13.11 .venv
source .venv/bin/activate            # mac/linux
# .venv\Scripts\Activate.ps1         # windows powershell
uv sync --all-groups
```

## Rodar a aplicacao

```bash
uv run python main.py
```

Servidor padrao:
- `http://127.0.0.1:5000`

Se a porta estiver ocupada:
- por padrao o app tenta a proxima porta livre automaticamente
- para desativar fallback: `--no-port-fallback`

Exemplo:
```bash
uv run python main.py --port 5000
```

## Fluxo de uso na UI

1. abrir `http://127.0.0.1:5000`
2. enviar `.accdb` ou `.mdb`
3. sistema converte para `.duckdb`
4. sistema gera `.sqlite`
5. sistema valida conversao (obrigatorio):
- estrutura (tabelas/colunas)
- contagem por tabela
- amostragem de conteudo
6. se validar, DB fica ativo para busca/comparacao
7. se falhar, conversao fica como erro e nao ativa DB

## Onde ficam os arquivos

Diretorio principal de dados:
- `documentos/`

Arquivos esperados por base:
- `NOME.accdb` ou `NOME.mdb`
- `NOME.duckdb`
- `NOME.sqlite`

Relatorios:
- `documentos/reports/latest_conversion_report.md`
- `documentos/reports/latest_conversion_report.json`
- `documentos/reports/latest_conversion_validation.json`
- `documentos/reports/latest_sqlite_duckdb_validation.md`
- `documentos/reports/latest_sqlite_duckdb_validation.json`

## Formatos e quando usar

- `accdb` / `mdb`:
  formato de origem
- `duckdb`:
  formato principal de operacao na ferramenta (busca e comparacao)
- `sqlite`:
  formato derivado para validacao cruzada e interoperabilidade

Regra pratica:
- para usar a ferramenta no dia a dia, trabalhe no `duckdb` gerado
- mantenha `sqlite` como prova de consistencia e troca com outros sistemas

## Conversao em lote (dados reais)

Para converter todos os Access de uma pasta para `documentos/` e gerar relatorio:

```bash
PYTHONPATH=. uv run python tools/organize_and_convert_documents.py \
  --target-dir documentos \
  --source-dir documentos
```

## Report automatizado de diferenca (POC)

Com menu interativo e selecao paginada (10 por tela), sugerindo os 2 ultimos `.accdb`:

```bash
PYTHONPATH=. uv run python tools/auto_compare_report.py
```

Modo rapido com default dos 2 ultimos `.accdb`:
1. rode o comando acima sem `--db1` e sem `--db2`
2. quando aparecer `Comandos: Enter=manter | m=alterar | q=sair` e o prompt `>`, pressione `Enter`
3. o script segue direto com os 2 ultimos e gera HTML/MD/TXT em `documentos/reports/`

Fluxo:
1. sugere 2 arquivos Access por data no nome (`YYYY-MM-DD ...`)
2. permite trocar A/B com lista paginada (`n/p`) e sair/voltar (`q/b`)
3. garante derivados `.duckdb` e `.sqlite` quando faltarem
4. compara via backend em DuckDB
5. grava report com timestamp em:
- `documentos/reports/*.html`
- `documentos/reports/*.md`
- `documentos/reports/*.txt`

Modo direto sem menu:

```bash
PYTHONPATH=. uv run python tools/auto_compare_report.py \
  --db1 "documentos/2026-01-29 DB2.accdb" \
  --db2 "documentos/2026-02-27 DB4.accdb"
```

## Qualidade local (obrigatorio no ciclo)

```bash
uv run python -m py_compile main.py interface/app_flask_local_search.py access_convert.py
uv run ruff check .
PYTHONPATH=. uv run pytest -q
pnpm exec eslint static --ext .js
```

## Estrutura minima do repo

- `main.py`: bootstrap do servidor Flask
- `interface/app_flask_local_search.py`: backend principal
- `static/`: frontend
- `access_convert.py`: conversao Access -> DuckDB
- `tools/`: scripts operacionais/relatorios
- `tests/`: testes automatizados
- `documentos/`: dados locais e derivados

## Troubleshooting rapido

### Access nao converte no mac/linux

No fluxo atual, a conversao usa fallback sem ODBC quando possivel.
Se der erro em arquivo especifico:
1. rode novamente com log
2. valide relatorio em `documentos/reports/latest_conversion_validation.json`
3. compare com o par `duckdb/sqlite`

### Windows e ODBC

No Windows, ODBC pode ser usado quando driver ACE estiver disponivel.
Se o driver nao estiver pronto, o sistema usa fallback quando suportado.

### Porta ja em uso

O app informa o processo e tenta porta seguinte.
Voce pode fixar porta com `--port` ou desativar fallback com `--no-port-fallback`.

## Nota final

README propositalmente curto.
Detalhes operacionais longos devem ficar em `docs/` e `tools/README.md`, nao aqui.
