$ErrorActionPreference = "Stop"

$configPath = Join-Path $HOME ".nmr5dbweb_repo.txt"

function Test-RepoDir([string]$p) {
    if (-not $p) { return $false }
    return (Test-Path (Join-Path $p "main.py")) -and (Test-Path (Join-Path $p "pyproject.toml"))
}

function Find-RepoFrom([string]$start) {
    $cur = Resolve-Path $start -ErrorAction SilentlyContinue
    if (-not $cur) { return $null }
    $path = $cur.Path
    while ($true) {
        if (Test-RepoDir $path) { return $path }
        $parent = Split-Path $path -Parent
        if (-not $parent -or $parent -eq $path) { break }
        $path = $parent
    }
    return $null
}

function Resolve-Repo() {
    if ($env:NMR5DBWEB_REPO -and (Test-RepoDir $env:NMR5DBWEB_REPO)) {
        return $env:NMR5DBWEB_REPO
    }

    if (Test-Path $configPath) {
        $saved = (Get-Content $configPath -Raw).Trim()
        if (Test-RepoDir $saved) { return $saved }
    }

    $scriptDir = Split-Path -Parent $PSCommandPath
    $found = Find-RepoFrom $scriptDir
    if ($found) { return $found }

    $found = Find-RepoFrom (Get-Location).Path
    if ($found) { return $found }

    Write-Host "Repo nao encontrado automaticamente."
    $manual = Read-Host "Digite o caminho absoluto do repo nmr5dbweb"
    if (-not (Test-RepoDir $manual)) {
        throw "Caminho invalido"
    }
    Set-Content -Path $configPath -Value $manual -NoNewline
    return $manual
}

function Pick-Python([string]$repo) {
    $venvPy = Join-Path $repo ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) { return $venvPy }
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) { return "py -3" }
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    $py3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($py3) { return $py3.Source }
    throw "Python nao encontrado"
}

function Get-FreePort([string]$pythonExe) {
    $code = @'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
'@
    if ($pythonExe -eq "py -3") {
        return (& py -3 -c $code).Trim()
    }
    return (& $pythonExe -c $code).Trim()
}

$repo = Resolve-Repo
$pythonExe = Pick-Python $repo
$port = Get-FreePort $pythonExe
$url = "http://127.0.0.1:$port"

Write-Host "Repo: $repo"
Write-Host "URL: $url"
Write-Host "Escolha navegador: [1] padrao [2] custom"
$choice = Read-Host ">"
if ($choice -eq "2") {
    $browserPath = Read-Host "Caminho do navegador custom"
}

Set-Location $repo

Start-Job -ScriptBlock {
    param($Port, $Url, $Choice, $BrowserPath)
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $iar = $client.BeginConnect("127.0.0.1", [int]$Port, $null, $null)
            $ok = $iar.AsyncWaitHandle.WaitOne(500, $false)
            if ($ok -and $client.Connected) {
                try { $client.EndConnect($iar) } catch {}
                $client.Close()
                break
            }
            $client.Close()
        } catch {}
        Start-Sleep -Milliseconds 250
    }
    if ($Choice -eq "2" -and $BrowserPath -and (Test-Path $BrowserPath)) {
        Start-Process -FilePath $BrowserPath -ArgumentList $Url | Out-Null
    } else {
        Start-Process $Url | Out-Null
    }
} -ArgumentList $port, $url, $choice, $browserPath | Out-Null

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv -and $pythonExe -ne "py -3") {
    & $uv.Source run --python $pythonExe python main.py --host 127.0.0.1 --port $port --no-port-fallback
    exit $LASTEXITCODE
}
if ($pythonExe -eq "py -3") {
    py -3 main.py --host 127.0.0.1 --port $port --no-port-fallback
} else {
    & $pythonExe main.py --host 127.0.0.1 --port $port --no-port-fallback
}
exit $LASTEXITCODE
