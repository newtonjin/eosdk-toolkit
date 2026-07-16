@echo off
:: EOSLANKit - Made By: n3sec (https://n3sec.com)
title EOSLANKit - Universal EOS LAN Tool
cd /d "%~dp0"

:: Prefere o .exe empacotado se existir; senao roda direto via Python.
if exist "%~dp0dist\EOSLANKit\EOSLANKit.exe" (
    start "" "%~dp0dist\EOSLANKit\EOSLANKit.exe"
    goto :eof
)
if exist "%~dp0EOSLANKit.exe" (
    start "" "%~dp0EOSLANKit.exe"
    goto :eof
)

py gui\launcher.py
if errorlevel 1 (
    echo.
    echo Python 3 necessario. Instale em https://python.org
    echo Ou gere o .exe com: powershell -File build-exe.ps1
    pause
)
