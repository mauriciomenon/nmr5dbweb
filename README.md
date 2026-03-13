# MDB2SQL – Toolkit para Access/ACCDB → DuckDB

Converte arquivos de banco de dados Microsoft Access (MDB/ACCDB) para DuckDB e
fornece uma interface web para busca e comparação de dados.

Pensado para cenários de auditoria, análise histórica e migração de bases.

## Requisitos

- Python **3.13.12** (fallback: **3.13.11**)
- `uv` para criar o ambiente e sincronizar dependências
- Acesso à internet para baixar dependências Python e, opcionalmente, JARs/SDKs
![alt text](image.png)

## Funcionalidades principais

- Extrai automaticamente a data a partir do nome do arquivo
- Preserva a estrutura das tabelas
- Cria tabelas “carimbadas” com data (histórico por dia/mês/ano)
- Mantém tabela de metadados com todos os imports
- Suporta processamento em lote (vários arquivos de uma vez)
- Interface web para busca e comparação em DuckDB
- Quatro estratégias de conversão (scripts de linha de comando em `converters/`)

---

## Visão geral da estrutura do projeto

- `main.py` – ponto de entrada da **interface web** (Flask)
- `interface/` – backend Flask (upload, conversão, busca, índice `_fulltext`)
- `static/` – arquivos estáticos da interface (HTML/JS/CSS)
- `access_convert.py` – conversão Access → DuckDB usada pela interface
- `converters/` – **conversores de linha de comando** (uso direto no terminal)
- `artifacts/` – arquivos gerados em tempo de execução (bancos `.duckdb`, logs, JSONs)
- `tools/` – scripts auxiliares (análises, organização de artefatos etc.)
- `tests/` – testes automatizados

Os conversores de CLI ficam em `converters/` para manter a raiz focada na
aplicação web e na documentação principal.

---

## Interface web (busca e comparação)

### Início rápido – interface web

No diretorio do projeto (primeira vez):

```bash
# 1) criar ambiente virtual (recomendado)
uv venv --python 3.13.12 .venv || uv venv --python 3.13.11 .venv

# 2) ativar o ambiente virtual
# Windows (PowerShell)
./.venv/Scripts/Activate.ps1
# Windows (Prompt de Comando)
./.venv/Scripts/activate.bat
# macOS / Linux
source .venv/bin/activate

# 3) sincronizar dependencias (runtime + dev) via pyproject.toml
uv sync --python .venv/bin/python --all-groups

# 4) iniciar a interface Flask
python main.py
```

Nas execuções seguintes, basta reativar o ambiente virtual e rodar o `main.py`:

```bash
./.venv/Scripts/Activate.ps1  # ou equivalente para seu sistema
python main.py
```

Depois acesse no navegador:

- http://127.0.0.1:5000/

Fluxo típico na interface:

- Fazer upload de um banco (`.mdb`, `.accdb` ou `.duckdb`)
- Se for Access, o sistema converte para DuckDB
- O índice `_fulltext` é criado/atualizado
- Você pode buscar termos, ver contagens por tabela e comparar bases

Os detalhes da interface estão descritos em mais profundidade em
`interface/README.md`.

### Instaladores por SO

- `install_windows.bat`: wrapper para `tools/windows_access_setup.ps1` (usa `uv`, `.venv`, `pyproject.toml`, check de pyodbc/driver).
- `install_macos.sh` e `install_linux.sh`: setup padrao do projeto com `uv`, `.venv` e `pyproject.toml`.

Fonte canonica de dependencias Python:
- `pyproject.toml` (runtime + grupo `dev`)
- `requirements.txt` e `requirements-dev.txt` ficam como compatibilidade legada

Compatibilidade de dependencias por plataforma:
- `pyodbc` e `win_unicode_console` sao instalados apenas em Windows.
- Em macOS/Linux, o fluxo principal usa conversao para DuckDB sem depender de ODBC.

---

## Conversores de linha de comando (`converters/`)

Todos os conversores de linha de comando ficam em `converters/`.
Eles **não** dependem da interface web: são scripts que você pode chamar
diretamente no terminal.

### 1. converters/convert_mdbtools.py (recomendado em Linux/macOS)

Usa o utilitário de linha de comando **mdbtools**.

**Vantagens:**
- Instalação simples
- Funciona bem em Linux/macOS
- Não precisa de Java

**Desvantagens:**
- Usa CSV intermediário (texto)
- Pode ter problemas de codificação em alguns arquivos
- Pode ser mais lento em bases muito grandes

**Instalação:**
```bash
# macOS
brew install mdbtools

# Linux
sudo apt install mdbtools
```

### 2. converters/convert_jackcess.py (recomendado pela robustez)

Usa a biblioteca Java **Jackcess**.

**Vantagens:**
- Mais robusto (melhor compatibilidade em muitos casos)
- Leitura binária direta do arquivo Access
- Lida melhor com questões de encoding
- Funciona em múltiplas plataformas

**Desvantagens:**
- Requer Java (JDK)
- Setup um pouco mais trabalhoso

**Instalação:**
```bash
# Requer Java JDK
# macOS
brew install openjdk

# Linux
sudo apt install default-jdk

# Os JARs são baixados automaticamente para a pasta temp/
```

### 3. converters/convert_pyaccess_parser.py (100% Python)

Usa a biblioteca **access-parser** (implementação pura em Python).

**Vantagens:**
- Sem dependências nativas externas
- 100% Python
- Instalação simples via pip
- Portável entre sistemas

**Desvantagens:**
- Mais lento do que implementações nativas
- Pode ter incompatibilidades com alguns formatos de MDB/ACCDB

**Instalação:**
```bash
pip install access-parser
```

### 4. converters/convert_pyodbc.py (Windows somente)

Usa **pypyodbc** + driver ODBC do Microsoft Access.

**Vantagens:**
- Nativo no Windows
- Em geral é rápido quando o driver está bem instalado

**Desvantagens:**
- Depende do **Microsoft Access Database Engine**
- Restrito a Windows (ou Wine em Linux/macOS)
- Setup complicado fora do Windows

**Instalação (Windows):**
1. Instalar Microsoft Access Database Engine:
     https://www.microsoft.com/en-us/download/details.aspx?id=54920
2. Instalar o pacote Python:
     ```bash
     pip install pypyodbc
     ```

---

## Comparativo de desempenho (benchmarks)

Baseado em testes com 5 arquivos (~90 MB cada) em macOS:

| Implementação        | Sucesso | Tempo médio/arquivo | Tempo total | Observações       |
|----------------------|---------|---------------------|------------|-------------------|
| **mdbtools**         | 100%    | 53,80s              | 268,98s    | Mais rápida       |
| **pyaccess_parser**  | 100%    | 165,08s             | 825,41s    | Puro Python       |
| **jackcess**         | 100%    | 252,80s             | 1264,01s   | Mais robusta      |
| **pypyodbc**         | 0%      | N/A                 | N/A        | Windows‑only      |

**Recomendações gerais:**
- **macOS / Linux:**
    - Preferir `convert_mdbtools.py` (mais rápido) ou
    - `convert_pyaccess_parser.py` (100% Python, sem binários externos)
- **Windows:**
    - Preferir `convert_pyodbc.py` (nativo) ou
    - `convert_jackcess.py` (multiplataforma com Java)
- **Máxima robustez:**
    - `convert_jackcess.py` (funciona em vários cenários com menor chance de erro)

---

## Inicio rapido – conversores (CLI)

```bash
# Clonar repositório
git clone <repository-url>
cd nmr5dbweb

# Criar ambiente virtual (recomendado)
uv venv --python 3.13.12 .venv || uv venv --python 3.13.11 .venv

# Ativar ambiente virtual
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell ou Prompt):
.venv\Scripts\activate

# Instalar dependencias Python
uv sync --python .venv/bin/python --all-groups

# Instalar dependências de sistema (escolha a que você for usar)
brew install mdbtools            # Para convert_mdbtools.py (macOS)
brew install openjdk             # Para convert_jackcess.py (macOS)
# Ou instale o Access Engine     # Para convert_pyodbc.py no Windows
```

### Pipeline local de validacao (dados reais em `documentos/`)

Use um comando unico para:
- preparar artefatos canonicos (`DuckDB` e `SQLite`),
- gerar manifesto do dataset,
- rodar benchmark de fluxo (opcional),
- gerar resumo operacional em Markdown.

```bash
# pipeline completo (prepare + benchmark + resumo)
uv run python tools/run_validation_pipeline.py \
  --input-dir documentos \
  --out-root artifacts/validation

# pipeline rapido (sem benchmark)
uv run python tools/run_validation_pipeline.py \
  --input-dir output/smoke \
  --out-root artifacts/validation_smoke \
  --skip-benchmark
```

Observacao operacional:
- por padrao, logs detalhados do `access_parser` ficam reduzidos para evitar ruido em conversoes grandes.
- para habilitar log completo temporariamente:

```bash
NMR5DBWEB_ACCESS_PARSER_VERBOSE=1 \
uv run python tools/run_validation_pipeline.py --input-dir documentos --out-root artifacts/validation --skip-benchmark
```

### Organizacao padrao dos bancos (documentos)

Para centralizar bancos de trabalho em uma pasta visivel no root do repo, use:

```bash
uv run python tools/organize_and_convert_documents.py
```

Esse comando:
- move `.accdb/.mdb` de `output/` e `interface/uploads/` para `documentos/`,
- gera `.duckdb` e `.sqlite` para cada base Access,
- mede tempos por etapa e grava relatorio em `documentos/reports/latest_conversion_report.{json,md,csv}`.

---

## Uso (CLI)

### Arquivo único

```bash
# Usando mdbtools
python converters/convert_mdbtools.py --input file.mdb --output database.duckdb

# Usando Jackcess
python converters/convert_jackcess.py --input file.mdb --output database.duckdb

# Usando pyaccess_parser
python converters/convert_pyaccess_parser.py --input file.mdb --output database.duckdb

# Usando pypyodbc (Windows)
python converters/convert_pyodbc.py --input file.mdb --output database.duckdb
```

### Processamento em lote

```bash
# Processar todos os arquivos MDB/ACCDB de um diretório
python converters/convert_mdbtools.py --input import_folder --output database.duckdb --batch
```

---

## Convenção de nomes de arquivos

Os arquivos devem conter uma data em algum destes formatos:
- `DD_MM_YYYY` ou `DD-MM-YYYY`
- `YYYY_MM_DD` ou `YYYY-MM-DD`
- `DDMMYYYY`
- `YYYYMMDD`

Exemplos:
- `DB3_04_09_2013.mdb` → `2013-09-04`
- `database_20190801.accdb` → `2019-08-01`

---

## Estrutura do banco DuckDB gerado

### Tabelas de dados

Cada tabela importada recebe o nome: `{nome_original}_{YYYYMMDD}`

Exemplo:
- Original: `RANGER_SOACCU`
- Importada: `RANGER_SOACCU_20130904`

### Tabela de metadados

```sql
CREATE TABLE _metadata (
        import_id INTEGER PRIMARY KEY,
        source_file VARCHAR,
        file_date DATE,
        import_timestamp TIMESTAMP,
        table_name VARCHAR,
        row_count INTEGER
);
```

### Exemplos de consultas

```sql
-- Ver todos os imports
SELECT * FROM _metadata ORDER BY import_timestamp DESC;

-- Encontrar tabelas de uma data específica
SELECT * FROM _metadata WHERE file_date = '2013-09-04';

-- Listar versões de cada tabela
SELECT 
        SUBSTRING(table_name, 1, POSITION('_2' IN table_name)-1) AS base_table,
        file_date,
        row_count
FROM _metadata
ORDER BY base_table, file_date;

-- Consultar uma versão específica da tabela
SELECT * FROM RANGER_SOACCU_20130904 LIMIT 10;
```

---

## Pasta artifacts/ (artefatos gerados)

A pasta `artifacts/` é o local padrão para arquivos **gerados** em tempo de
execução, por exemplo:

- Bancos DuckDB criados por conversões ou pela interface (`*.duckdb`)
- Resultados de benchmark (`benchmark_results_*.json`)
- Logs de benchmark (`benchmark_run*.log`)

Esses arquivos podem ser apagados e gerados novamente.

Para mover artefatos antigos que estejam na raiz do projeto para `artifacts/`,
você pode rodar:

```bash
python -m tools.organize_artifacts
```

---

## Notas específicas por plataforma

### macOS
- Usar preferencialmente `convert_mdbtools.py` ou `convert_jackcess.py`
- mdbtools: `brew install mdbtools`
- Java: `brew install openjdk`
- Para `.accdb` sem ODBC, o backend da interface tenta fallback com `access-parser`.

### Linux
- Usar preferencialmente `convert_mdbtools.py` ou `convert_jackcess.py`
- mdbtools: `sudo apt install mdbtools`
- Java: `sudo apt install default-jdk`
- Para `.accdb` sem ODBC, o backend da interface tenta fallback com `access-parser`.

### Windows
- Usar preferencialmente `convert_pyodbc.py`
- Alternativa: `convert_jackcess.py` com Java instalado
- Necessário instalar o Access Database Engine / driver ODBC de Access

---

## Solução de problemas (troubleshooting)

### Erros de encoding com mdbtools
- Alguns arquivos podem ter problemas de codificação.
- Tente `convert_jackcess.py` ou `convert_pyaccess_parser.py` como alternativa.

### Java não encontrado
```bash
# macOS
brew install openjdk
export PATH="/usr/local/opt/openjdk/bin:$PATH"

# Linux
sudo apt install default-jdk
```

### Driver ODBC não encontrado (Windows)
- Verifique se o **Microsoft Access Database Engine** está instalado.
- Confira se o driver `Microsoft Access Driver (*.mdb, *.accdb)` aparece em `pyodbc.drivers()`.

### Porta 5000 ja ocupada
- O `main.py` agora detecta o processo na porta ocupada e tenta automaticamente a proxima porta livre.
- Para desativar esse comportamento: `python main.py --no-port-fallback`.

---

## Desenvolvimento

```bash
# Criar/atualizar ambiente de desenvolvimento
uv venv --python 3.13.12 .venv || uv venv --python 3.13.11 .venv

# Ativar o ambiente
source .venv/bin/activate

# Instalar dependencias de runtime + ferramentas de validacao
uv sync --python .venv/bin/python --all-groups

# Validacoes principais
python -m py_compile $(find . -name "*.py" -type f)
ruff check .
ty check .
pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py

# (Opcional) checar estilo de código para conversores
python -m pylint converters/convert_*.py
```

---

## Licença

MIT

---

## Histórico de versões (simplificado)

- v0.1.0-mdbtools: primeira versão com mdbtools
- v0.2.0: adicionados conversores Jackcess, pyaccess_parser e pypyodbc
