@echo off
cd /d "%~dp0"
echo Copy the generated value into Vercel's DJANGO_SECRET_KEY setting.
echo Keep it private. Do not paste it into chat or commit it to GitHub.
py -c "import secrets; print(secrets.token_urlsafe(64))"
pause
