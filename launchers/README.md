# Launchers

Objetivo: atalhos de duplo clique para iniciar a web app e gerar report minimo.

Arquivos:
- `nmr5dbweb_web_mac.command`
- `nmr5dbweb_web_linux.sh`
- `nmr5dbweb_web_debian.desktop`
- `nmr5dbweb_web_windows.bat`
- `nmr5dbweb_web_windows.ps1`
- `nmr5dbweb_report_min_mac.command`
- `nmr5dbweb_report_min_linux.sh`
- `nmr5dbweb_report_min_debian.desktop`
- `nmr5dbweb_report_min_windows.bat`
- `nmr5dbweb_report_min_windows.ps1`

## Como usar

### macOS
1. Copie o `.command` para qualquer pasta.
2. Clique duas vezes.
3. Na primeira execucao, se o repo nao for encontrado automaticamente, informe o caminho do repo.

### Debian/Linux
1. Copie `nmr5dbweb_web_linux.sh` e o `.desktop` para a mesma pasta.
2. Torne executavel:
```bash
chmod +x nmr5dbweb_web_linux.sh nmr5dbweb_report_min_linux.sh
chmod +x nmr5dbweb_web_debian.desktop nmr5dbweb_report_min_debian.desktop
```
3. Clique duas vezes no `.desktop`.

### Windows
1. Copie os pares `.bat` + `.ps1` para a mesma pasta.
2. Clique duas vezes no `.bat`.
3. Se necessario, ajuste politica local para permitir script PowerShell.

## Resolucao de repo

Os launchers tentam localizar o repo em:
1. variavel `NMR5DBWEB_REPO`
2. arquivo salvo no usuario (`~/.nmr5dbweb_repo` no unix, `%USERPROFILE%\\.nmr5dbweb_repo.txt` no windows)
3. pasta do launcher e pais
4. pasta atual

Se nao achar, pedem o caminho e salvam para a proxima execucao.

## Navegador

Launcher web pergunta:
- `[1]` navegador padrao
- `[2]` navegador custom por caminho informado

Recomendacao: usar navegador padrao.
Nao embutir Chromium no repo.
