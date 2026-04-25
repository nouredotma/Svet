@echo off
echo Stopping Dexter...

powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'uvicorn app.main:app' -or $_.CommandLine -match 'desktop.main') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo Dexter stopped.
