@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title LIOR Company - Servidor seguro

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"
if not defined PYTHON_CMD where python3 >nul 2>nul && set "PYTHON_CMD=python3"

if not defined PYTHON_CMD (
  if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
)
if not defined PYTHON_CMD (
  if exist "%ProgramFiles%\Python312\python.exe" set "PYTHON_CMD=%ProgramFiles%\Python312\python.exe"
)
if not defined PYTHON_CMD (
  if exist "%ProgramFiles(x86)%\Python312\python.exe" set "PYTHON_CMD=%ProgramFiles(x86)%\Python312\python.exe"
)

if not defined PYTHON_CMD (
  echo Python nao foi encontrado neste computador.
  echo Verifique se o Python esta instalado e adicionado ao PATH.
  echo Tente executar: python --version ou py -3 --version
  goto :python_missing
)

if not exist "server_python\.env" (
  copy /Y "server_python\.env.example" "server_python\.env" >nul
)

set "HOST=127.0.0.1"
set "PORT=3000"
set "OPEN_BROWSER=1"

echo.
echo Iniciando a LIOR em http://127.0.0.1:3000
echo O navegador sera aberto automaticamente.
echo Nao feche esta janela enquanto estiver usando a loja.
echo.
%PYTHON_CMD% "server_python\app.py"

echo.
echo O servidor da LIOR foi encerrado.
pause
exit /b 0

:python_missing
echo.
echo Nao foi possivel instalar o Python automaticamente.
echo A pagina oficial sera aberta. Instale o Python e marque "Add Python to PATH".
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1
