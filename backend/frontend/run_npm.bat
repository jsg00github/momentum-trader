@echo off
set "NODE_DIR=..\\.node_bin\\node-v20.11.0-win-x64"
set "PATH=%NODE_DIR%;%PATH%"
"%NODE_DIR%\node.exe" "%NODE_DIR%\node_modules\npm\bin\npm-cli.js" %*
