@echo off
echo Starting Momentum Trader in Remote Access Mode...
echo.
echo ---------------------------------------------------
echo  Local Network Access Enabled (0.0.0.0:8000)
echo  Use the 'Connect Device' button in the app to get the QR code.
echo ---------------------------------------------------
echo.
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
