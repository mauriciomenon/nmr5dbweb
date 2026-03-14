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

$repo = Resolve-Repo
$pythonExe = Pick-Python $repo
Set-Location $repo

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv -and $pythonExe -ne "py -3") {
    & $uv.Source run --python $pythonExe python -m tools.run_min_compare_report
    exit $LASTEXITCODE
}
if ($pythonExe -eq "py -3") {
    py -3 -m tools.run_min_compare_report
} else {
    & $pythonExe -m tools.run_min_compare_report
}
exit $LASTEXITCODE
