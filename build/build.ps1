#Requires -Version 5.1
param(
    [Parameter(Mandatory = $true)]
    [string]$EosDll,

    [Parameter(Mandatory = $false)]
    [string]$OutName = "",

    [Parameter(Mandatory = $false)]
    [string]$LibraryName = "",

    [string]$ClangPath = "",
    [string]$SdkLib = "C:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0\um\x64",

    # Override opcional: pasta gravavel para .def/.dll (frozen usa %LOCALAPPDATA%).
    [string]$BuildDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Src = Join-Path $Root "src"
$Tools = Join-Path $Root "tools"
if ($BuildDir) {
    $Build = $BuildDir
} else {
    $Build = Join-Path $Root "build"
}

New-Item -ItemType Directory -Force -Path $Build | Out-Null

if (-not (Test-Path $EosDll)) { throw "EOSSDK nao encontrada: $EosDll" }

$eosBase = [IO.Path]::GetFileNameWithoutExtension($EosDll)
if (-not $OutName) {
    if ($LibraryName) {
        $OutName = "$LibraryName.dll"
    } elseif ($eosBase -match '_orig$') {
        $OutName = ($eosBase -replace '_orig$', '-Win64-Shipping') + '.dll'
    } else {
        $OutName = [IO.Path]::GetFileName($EosDll)
    }
}
if (-not $LibraryName) {
    $LibraryName = [IO.Path]::GetFileNameWithoutExtension($OutName)
}

Write-Host "=== EOSLANKit Build ===" -ForegroundColor Cyan
Write-Host "EOSSDK ref : $EosDll"
Write-Host "Library    : $LibraryName"
Write-Host "Saida      : $Build\$OutName"

Write-Host "`n[1/3] Gerando exports..." -ForegroundColor Yellow
$defPath = Join-Path $Build "eossdk_proxy.def"
& py (Join-Path $Tools "gen_def.py") --eos-dll $EosDll --out $defPath --library-name $LibraryName
if ($LASTEXITCODE -ne 0) { throw "gen_def.py falhou" }

if ($ClangPath) { $env:PATH = "$ClangPath;$env:PATH" }
if (-not (Get-Command clang -ErrorAction SilentlyContinue)) {
    $candidates = @(
        "D:\Tools\clang+llvm-22.1.0-x86_64-pc-windows-msvc\clang+llvm-22.1.0-x86_64-pc-windows-msvc\bin",
        "C:\Program Files\LLVM\bin"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $env:PATH = "$c;$env:PATH"; break }
    }
}
if (-not (Get-Command clang -ErrorAction SilentlyContinue)) {
    throw "clang nao encontrado. Instale LLVM ou passe -ClangPath."
}

Write-Host "[2/3] Compilando proxy (zero CRT)..." -ForegroundColor Yellow
$outDll = Join-Path $Build $OutName
$srcFiles = @(
    (Join-Path $Src "proxy_util.c"),
    (Join-Path $Src "proxy_exports.c")
)

$clangArgs = @(
    "-target", "x86_64-pc-windows-msvc",
    "-shared", "-O2",
    "-I$Src"
) + $srcFiles + @(
    "-Wl,/DEF:$defPath",
    "-o", $outDll,
    "-L$SdkLib",
    "-lkernel32",
    "-fuse-ld=lld",
    "-nostdlib",
    "-Wl,/ENTRY:DllMain"
)

& clang @clangArgs
if ($LASTEXITCODE -ne 0) { throw "Compilacao falhou" }

$size = (Get-Item $outDll).Length
Write-Host "[3/3] OK: $outDll ($size bytes)" -ForegroundColor Green
