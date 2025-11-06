# MDB2SQL - Conversor MDB/ACCDB para DuckDB

Conversor de arquivos Microsoft Access (MDB/ACCDB) para DuckDB, preservando estrutura de tabelas e metadados temporais.

## Características

- Converte arquivos MDB (Access 97-2003) e ACCDB (Access 2007+) para DuckDB
- Preserva estrutura completa das tabelas
- Extrai data do arquivo a partir do nome e armazena como metadado
- Otimizado para análise de grandes volumes (~30GB+)
- Suporta comparações entre múltiplas versões temporais

## Requisitos

### macOS

```bash
brew install python3
brew install mdbtools
```

### Debian/Ubuntu Linux

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv mdbtools
```

### Windows 11

1. Instale Python 3.10+ de [python.org](https://www.python.org/downloads/)
2. Instale Microsoft Access Database Engine:
   - [64-bit](https://www.microsoft.com/en-us/download/details.aspx?id=54920)

## Instalação

```bash
git clone https://github.com/SEU_USUARIO/mdb2sql.git
cd mdb2sql

python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

## Uso

### Converter um único arquivo

```bash
python convert.py --input import_folder/DB2_01_08_2019.accdb --output database.duckdb
```

### Processar múltiplos arquivos (batch)

```bash
python convert.py --input import_folder --output database.duckdb --batch
```

### Opções

- `--input`: Arquivo MDB/ACCDB de entrada ou diretório (para batch)
- `--output`: Arquivo DuckDB de saída (padrão: database.duckdb)
- `--batch`: Processar todos os arquivos MDB/ACCDB do diretório

## Estrutura do Banco

Cada tabela importada mantém:
- Nome original da tabela + data (ex: `Clientes_20190801`)
- Tabela `_metadata` com informações de importação
- Data de extração (do nome do arquivo)
- Timestamp de importação
- Contagem de linhas

## Performance

- Arquivos de 100MB: ~2-5 minutos
- Compressão: ~40-60% do tamanho original
- Queries analíticas: 10-100x mais rápidas que SQLite
- 300 arquivos (~30GB): processamento em ~10-15 horas

## Exemplos de Queries

```sql
-- Ver metadados de importações
SELECT * FROM _metadata ORDER BY file_date;

-- Comparar contagem entre duas datas
SELECT 
    a.table_name,
    a.row_count as count_2019,
    b.row_count as count_2020,
    b.row_count - a.row_count as diff
FROM _metadata a
JOIN _metadata b ON REPLACE(a.table_name, '_20190801', '') = REPLACE(b.table_name, '_20201204', '')
WHERE a.file_date = '2019-08-01' AND b.file_date = '2020-12-04';
```

## Licença

MIT
