@echo off
echo Stopping Azmus ERP remote access...

taskkill /FI "WINDOWTITLE eq Azmus-Cloudflare-Tunnel*" /F 2>nul

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr LISTENING') do (
  echo Stopping backend PID %%p
  taskkill /PID %%p /F 2>nul
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173" ^| findstr LISTENING') do (
  echo Stopping frontend PID %%p
  taskkill /PID %%p /F 2>nul
)

taskkill /FI "WINDOWTITLE eq Azmus-Backend*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Azmus-Frontend*" /F 2>nul

echo Done.
pause

