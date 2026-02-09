# Cookbook — Interface de Busca DuckDB (Novo Usuário)

Guia rápido para quem vai **apenas usar a interface de pesquisa no navegador**, sem precisar entender os detalhes técnicos do restante do projeto.

---

## 1. O que você precisa ter instalado

- **Sistema operacional:** Windows 10 ou 11.
- **Python:** versão 3.10 ou superior.
  - Na instalação do Python, marque a opção **"Add python.exe to PATH"**.
- **Navegador:** Chrome, Edge ou Firefox atualizado.

> Você **não** precisa ter Microsoft Access instalado. Só é necessário ter os arquivos de banco (`.duckdb`, `.mdb`, `.accdb`) que serão usados na busca.

---

## 2. Como receber os arquivos

Você pode obter a aplicação de **duas formas**:

1. Pelo **GitHub** (branch específica da interface).
2. Recebendo um **arquivo ZIP pronto** do responsável pelo sistema.

### 2.1. Baixar direto do GitHub (opção para usuários com Git ou familiarizados com ZIP do GitHub)

- Repositório: <https://github.com/allysonalmeidaa/mdb2sql_fork>
- Branch da interface: **`minha-alteracao`**

**Opção A — baixar ZIP pelo navegador**

1. Acesse o link do repositório no navegador.
2. No seletor de branches do GitHub, escolha a branch **`minha-alteracao`**.
3. Clique em **Code → Download ZIP**.
4. Salve o ZIP e siga os passos da seção **2.2. Extrair o ZIP**.

**Opção B — clonar usando Git**

Se você tiver Git instalado e preferir clonar o repositório:

```powershell
cd C:\
git clone -b minha-alteracao --single-branch https://github.com/allysonalmeidaa/mdb2sql_fork.git
cd mdb2sql_fork
```

Depois disso, você pode usar essa pasta `C:\mdb2sql_fork` diretamente nos passos de instalação (em vez de `C:\busca_duckdb`).

### 2.2. Extrair o ZIP (ZIP do GitHub ou ZIP enviado pelo responsável)

1. Escolha uma pasta, por exemplo `C:\busca_duckdb`.
2. Clique com o botão direito no ZIP → **Extrair tudo...** → aponte para `C:\busca_duckdb`.
3. Ao final, você terá algo como:

- `C:\busca_duckdb\interface\...`
- `C:\busca_duckdb\static\...`
- `C:\busca_duckdb\requirements.txt`
- (e outros arquivos do projeto)

---

## 3. Primeira execução — só com Windows PowerShell

> Esses passos são necessários **apenas na primeira vez** em que você for usar o sistema nesta máquina.

1. Abra o **Windows PowerShell**.
2. Vá até a pasta onde você extraiu o ZIP (ajuste o caminho se for diferente):

```powershell
cd C:\busca_duckdb
```

3. Crie o ambiente virtual Python (só uma vez):

```powershell
python -m venv .venv
```

4. Ative o ambiente virtual:

```powershell
.\.venv\Scripts\Activate.ps1
```

> No prompt você verá algo como `(.venv)` aparecendo antes do caminho — isso indica que o ambiente está ativo.

5. Instale as dependências da aplicação (também só na primeira vez):

```powershell
pip install -r requirements.txt
```

Quando esse comando terminar sem erros, a aplicação está pronta para uso.

---

## 4. Como iniciar a interface de pesquisa

Sempre que você quiser **usar a interface** (no dia a dia):

1. Abra o **Windows PowerShell**.
2. Vá até a pasta do projeto:

```powershell
cd C:\busca_duckdb
```

3. Ative o ambiente virtual:

```powershell
.\.venv\Scripts\Activate.ps1
```

4. Inicie o servidor da aplicação (forma recomendada):

```powershell
python main.py
```

> Opcional (avançado): se preferir, você também pode iniciar diretamente o app Flask com:
>
> ```powershell
> python interface/app_flask_local_search.py
> ```

5. Aguarde aparecer uma mensagem parecida com:

```text
* Running on http://127.0.0.1:5000
```

6. Abra o navegador (Chrome/Edge/Firefox) e digite na barra de endereços:

```text
http://127.0.0.1:5000/
```

A interface de pesquisa vai abrir na aba **"Busca em bancos - Painel"**.

> **Importante:** deixe a janela do PowerShell aberta enquanto estiver usando a interface. Se fechar ou interromper (`Ctrl + C`), o sistema para de responder.

---

## 5. Fluxo básico de uso — aba "Busca"

A aba **Busca** é o painel principal para pesquisar em bancos DuckDB (ou derivados de Access).

### 5.1. Passo 1 — Selecionar ou enviar um banco

1. No topo da tela, clique em **"Selecionar DB"** ou use o fluxo **1. Selecionar DB**.
2. Na janela que abrir, você tem duas opções:
   - **Enviar arquivo**: escolha um arquivo `.duckdb`, `.db`, `.sqlite`, `.sqlite3` ou (se combinado com o responsável) `.mdb`/`.accdb`.
   - **Selecionar um DB já enviado**: use a lista de arquivos que já estão no sistema.
3. Após selecionar, o nome do banco ativo aparece no canto superior esquerdo da tela (e nos cartões de status).

### 5.2. Passo 2 — Índice _fulltext (se necessário)

Para buscas rápidas, o sistema usa um índice chamado **`_fulltext`**.

- Se o índice ainda **não estiver pronto**, o cartão **"Indice _fulltext"** vai mostrar que está faltando ou incompleto.
- Para criar ou atualizar o índice:
  1. Clique no botão **"Indice _fulltext"** no topo.
  2. Na janela que abrir, clique em **"Iniciar indexação"**.
  3. Aguarde terminar — os cartões de status vão indicar quando estiver **Pronto**.

Enquanto o índice está sendo criado, a busca fica temporariamente bloqueada, e a interface mostra uma mensagem avisando.

### 5.3. Passo 3 — Fazer uma busca

1. No fluxo **4. Buscar resultados**, clique em **"Ir"** ou no botão equivalente.
2. Na janela de busca:
   - Digite o termo que deseja procurar (por exemplo, parte de um nome, código, etc.).
   - Ajuste as opções se necessário (tabelas, limite de resultados, score mínimo). Em geral, os padrões já funcionam bem.
3. Clique em **"Pesquisar"**.
4. A lista de resultados será exibida na parte de baixo da tela, com:
   - Nome da tabela;
   - Colunas e valores;
   - Relevância (score) quando aplicável.

Você pode rolar, ordenar colunas e, se a interface estiver habilitada para isso, exportar os resultados em CSV.

---

## 6. Outras abas importantes

### 6.1. Aba "Rastrear registro"

Permite procurar um registro específico em **várias versões de bancos** de uma vez.

1. No topo, clique em **"Rastrear registro"**.
2. Preencha:
   - **Diretório dos bancos**: pasta onde estão os arquivos (`.duckdb`, `.mdb`, `.accdb`).
   - **Tabela (opcional)**: por exemplo, `RANGER_SOSTAT`.
   - **Filtros (obrigatório)**: exemplo `RTUNO=1,PNTNO=2304`.
3. Clique em **"Executar análise"**.
4. A tela mostrará em quais bancos o registro foi encontrado e um resumo dos dados.

### 6.2. Aba "Comparar bancos"

Permite comparar duas versões de banco **DuckDB** para ver registros:

- somente em um dos bancos;
- alterados entre as versões;
- iguais nas duas.

1. Clique em **"Comparar bancos"** no topo.
2. Escolha os dois arquivos de banco a serem comparados.
3. Defina a tabela, a chave (por exemplo, `RTUNO,PNTNO`) e, se quiser, filtros.
4. Execute a comparação para ver o diff detalhado.

---

## 7. Como parar e iniciar de novo

- Para **parar** o sistema:
  - Volte à janela do PowerShell onde ele está rodando e pressione **`Ctrl + C`**.
- Para **usar em outro dia**, repita apenas:

```powershell
cd C:\busca_duckdb
.\.venv\Scripts\Activate.ps1
python interface/app_flask_local_search.py
```

Depois, abra novamente `http://127.0.0.1:5000/` no navegador.

---

## 8. Resumo rápido para o usuário

1. Abrir PowerShell → `cd C:\busca_duckdb`.
2. Ativar ambiente → `.\.venv\Scripts\Activate.ps1`.
3. Rodar servidor → `python interface/app_flask_local_search.py`.
4. Abrir navegador em `http://127.0.0.1:5000/`.
5. Usar **Selecionar DB** e seguir o fluxo da tela para buscar.

Se tiver qualquer erro ou mensagem estranha na tela do PowerShell, tire um print e envie para o responsável pelo sistema.
