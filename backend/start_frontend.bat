@echo off
setlocal
echo ===================================================
echo   Initializing Momentum Trader Frontend (Vite)
echo ===================================================

set "ROOT_DIR=%~dp0"
set "NODE_HOME=%ROOT_DIR%node-v20.11.0-win-x64"
set "NPM_BIN=%NODE_HOME%\node_modules\npm\bin"
set "FRONTEND_DIR=%ROOT_DIR%frontend"

:: Add Node to PATH
set "PATH=%NODE_HOME%;%PATH%"

echo [1/3] Verifying Node.js...
node -v

echo [2/3] Checking Dependencies...
cd "%FRONTEND_DIR%"
if not exist "node_modules" (
    echo Installing npm packages...
    node "%NPM_BIN%\npm-cli.js" install
) else (
    echo Dependencies found.
)

echo [3/3] Starting Dev Server...
if exist "node_modules\vite\bin\vite.js" (
    echo Starting Vite...
    "%NODE_HOME%\node.exe" "node_modules\vite\bin\vite.js"
) else (
    echo Vite executable not found!
    echo Attempting via npm...
    "%NODE_HOME%\node.exe" "%NPM_BIN%\npm-cli.js" run dev
)
pause
