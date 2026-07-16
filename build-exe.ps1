# Build script para EOSLANKit.exe (PyInstaller onedir).
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File build-exe.ps1

param(
    [switch]$Clean,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

Write-Host "EOSLANKit - build .exe" -ForegroundColor Cyan
Write-Host "Made By: n3sec  |  https://n3sec.com" -ForegroundColor DarkGray

# Verifica Python
try {
    $pyv = & py -3 -V 2>&1
} catch {
    Write-Host "ERRO: Python 3 nao encontrado no PATH (py -3)." -ForegroundColor Red
    exit 1
}
Write-Host "Python: $pyv"

# Instala PyInstaller se preciso
if (-not $SkipInstall) {
    Write-Host "Instalando/atualizando PyInstaller..." -ForegroundColor Yellow
    & py -3 -m pip install --upgrade pyinstaller | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERRO: pip install pyinstaller falhou." -ForegroundColor Red
        exit 1
    }
}

function Stop-EOSLANKitProcess {
    $procs = Get-Process -Name EOSLANKit -ErrorAction SilentlyContinue
    if ($procs) {
        Write-Host "Encerrando EOSLANKit.exe em execucao ($($procs.Count))..." -ForegroundColor Yellow
        $procs | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
    }
}

function Remove-PathWithRetry {
    param([string]$Path, [int]$Retries = 5)
    if (-not (Test-Path $Path)) { return $true }
    for ($i = 0; $i -lt $Retries; $i++) {
        try {
            Remove-Item -Recurse -Force -ErrorAction Stop $Path
            return $true
        } catch {
            Stop-EOSLANKitProcess
            Start-Sleep -Milliseconds 400
        }
    }
    Write-Host "AVISO: nao consegui remover $Path (arquivo travado?)." -ForegroundColor Yellow
    return $false
}

# Sempre encerra processo antes de qualquer coisa (evita lock em dist\EOSLANKit\EOSLANKit.exe).
Stop-EOSLANKitProcess

if ($Clean) {
    Write-Host "Limpando build/ e dist/..." -ForegroundColor Yellow
    [void](Remove-PathWithRetry "$repoRoot\dist")
    [void](Remove-PathWithRetry "$repoRoot\build\pyinstaller")
    [void](Remove-PathWithRetry "$repoRoot\__pycache__")
} else {
    # Mesmo sem -Clean o PyInstaller vai tentar limpar dist\EOSLANKit\; garante que nao esta locked.
    [void](Remove-PathWithRetry "$repoRoot\dist\EOSLANKit")
}

Write-Host "Rodando PyInstaller..." -ForegroundColor Green
& py -3 -m PyInstaller --noconfirm --workpath "$repoRoot\build\pyinstaller" `
    "$repoRoot\EOSLANKit.spec"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: PyInstaller falhou." -ForegroundColor Red
    exit 1
}

$outExe = Join-Path $repoRoot "dist\EOSLANKit\EOSLANKit.exe"
if (Test-Path $outExe) {
    Write-Host "`nOK -> $outExe" -ForegroundColor Green
    Write-Host "Distribua toda a pasta 'dist\EOSLANKit\' (contem _internal + EOSLANKit.exe)."
    Write-Host "Na primeira execucao, config/build/src sao extraidos ao lado do .exe."
} else {
    Write-Host "AVISO: $outExe nao encontrado apos build." -ForegroundColor Yellow
    exit 2
}
