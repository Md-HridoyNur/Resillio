@echo off
cd /d "%~dp0"
echo Stop your old RESILIO server with Ctrl+C before continuing.
echo This updater preserves your database, secret, virtual environment and accounts.
set /p "resilio_target=Paste the OLD RESILIO folder path containing manage.py: "
if not defined resilio_target goto :eof
py tools\upgrade_existing.py --target "%resilio_target%"
if errorlevel 1 echo Upgrade did not finish. Check the message above; a backup may be available beside the old folder.
pause
