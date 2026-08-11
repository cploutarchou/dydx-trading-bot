@echo off
REM Bootstrap shared infra and the supervised Celery worker (Windows host).
make -C "%~dp0..\.." bot-runtime-up
exit /b %ERRORLEVEL%
