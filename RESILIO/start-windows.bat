@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe manage.py migrate --noinput
if errorlevel 1 goto failed
echo Open http://127.0.0.1:8000/ . See README.md for demo seeding and admin setup.
.venv\Scripts\python.exe manage.py runserver
goto :eof
:failed
echo Setup failed. Check the error above and confirm Python with pip is installed.
pause
