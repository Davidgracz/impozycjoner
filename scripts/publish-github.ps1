# One-time GitHub publishing assistant for Impozycjoner Studio.
# Creates a NEW repo in the user's account. Does not request or store tokens.
$ErrorActionPreference = 'Stop'
$repoFull = 'Davidgracz/impozycjoner'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

function Require-Ok([string]$message) {
    if ($LASTEXITCODE -ne 0) { throw "$message (kod: $LASTEXITCODE)" }
}
function Find-Gh {
    $cmd = Get-Command gh -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $paths = @(
        "$env:ProgramFiles\GitHub CLI\gh.exe",
        "${env:ProgramFiles(x86)}\GitHub CLI\gh.exe",
        "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe",
        "$env:USERPROFILE\scoop\apps\gh\current\bin\gh.exe"
    )
    foreach ($p in $paths) { if (Test-Path -LiteralPath $p) { return $p } }
    return $null
}

Write-Host '=== Impozycjoner Studio -> GitHub ===' -ForegroundColor Cyan
Write-Host "Docelowe repozytorium: https://github.com/$repoFull"
Write-Host 'Bez wysylania .venv, cache, build i danych logowania.'
Write-Host ''

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Brakuje Git. Zainstaluj Git for Windows: https://git-scm.com/downloads/win i uruchom skrypt ponownie.'
}

$gh = Find-Gh
if (-not $gh) {
    Write-Host 'Brakuje GitHub CLI (gh). Proba instalacji przez winget...' -ForegroundColor Yellow
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'Zainstaluj GitHub CLI z https://cli.github.com/ i uruchom skrypt ponownie.'
    }
    & winget install --id GitHub.cli --exact --source winget --accept-source-agreements --accept-package-agreements
    Require-Ok 'Instalacja GitHub CLI nie powiodla sie'
    $gh = Find-Gh
    if (-not $gh) {
        throw 'GitHub CLI zainstalowany, ale nie jest jeszcze widoczny. Zamknij okno i uruchom skrypt ponownie.'
    }
}

& $gh auth status --hostname github.com *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Zaloguj sie na konto GitHub w przegladarce...' -ForegroundColor Cyan
    & $gh auth login --hostname github.com --web --git-protocol https
    Require-Ok 'Nie udalo sie zalogowac do GitHub'
}
$account = (& $gh api user --jq '.login')
Require-Ok 'Nie mozna ustalic konta GitHub'
if ($account -ne 'Davidgracz') {
    throw "Zalogowano jako $account, ale repo ma byc na koncie Davidgracz. Uzyj: gh auth switch -h github.com"
}
& $gh auth setup-git
Require-Ok 'Nie udalo sie ustawic uwierzytelniania Git'

if (-not (Test-Path -LiteralPath '.git')) {
    & git init -b main
    Require-Ok 'Nie udalo sie wykonac git init'
}

# Only the local repository is affected; no global Git settings are changed.
$name = (& git config --get user.name)
if (-not $name) { & git config user.name 'Davidgracz'; Require-Ok 'git config user.name' }
$email = (& git config --get user.email)
if (-not $email) {
    & git config user.email '43789926+Davidgracz@users.noreply.github.com'
    Require-Ok 'git config user.email'
}
& git add -A
Require-Ok 'Nie udalo sie dodac plikow do Git'
& git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    & git commit -m 'Initial release: Impozycjoner Studio 0.1.0'
    Require-Ok 'Nie udalo sie utworzyc commita'
}
& git branch -M main
Require-Ok 'Nie udalo sie ustawic galezi main'

& $gh repo view $repoFull --json name *> $null
$exists = ($LASTEXITCODE -eq 0)
if ($exists) {
    Write-Host "Repozytorium $repoFull juz istnieje. Wykonuje bezpieczny push (bez force)." -ForegroundColor Yellow
    & git remote get-url origin *> $null
    if ($LASTEXITCODE -eq 0) {
        $url = (& git remote get-url origin).Trim()
        if ($url -notmatch '(?i)(github\.com[:/])Davidgracz/impozycjoner(?:\.git)?$') {
            throw "Istniejacy remote origin ($url) wskazuje inny projekt. Przerwano."
        }
    } else {
        & git remote add origin "https://github.com/$repoFull.git"
        Require-Ok 'Nie udalo sie dodac remote origin'
    }
    & git push -u origin main
    Require-Ok 'Push zakonczyl sie bledem (bez nadpisywania cudzej historii)'
} else {
    Write-Host ''
    Write-Host 'Wybierz widocznosc nowego repozytorium:'
    $answer = Read-Host '[Enter/P] prywatne (domyslnie), [O] publiczne'
    $visibility = '--private'
    if ($answer -match '^[Oo]$') { $visibility = '--public' }
    & $gh repo create $repoFull $visibility --description 'Desktop PDF imposition app for print production' --source . --remote origin --push
    Require-Ok 'Nie udalo sie utworzyc lub wypchnac repozytorium'
}
Write-Host ''
Write-Host "GOTOWE: https://github.com/$repoFull" -ForegroundColor Green
& $gh repo view $repoFull --web
