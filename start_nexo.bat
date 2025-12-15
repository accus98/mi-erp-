@echo off
echo Starting Nexo ERP...

:: Start Backend (Server)
echo Launching Backend...
start "Nexo Server (Python)" cmd /k "python bin/server.py"

:: Wait for Server to wake up
timeout /t 2 /nobreak >nul

:: Start Frontend (Client)
echo Launching Web Client...
cd addons/web/static
start "Nexo Client (Vue)" cmd /k "npm run dev"

:: Open Browser
timeout /t 4 /nobreak >nul
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start chrome http://localhost:5173
) else (
    start http://localhost:5173
)

echo.
echo Nexo ERP is running!
echo Don't close the black windows (Server/Client) while using the app.
pause
