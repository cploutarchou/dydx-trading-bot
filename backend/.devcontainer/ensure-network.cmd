@echo off
REM Ensure the shared infra network exists (Windows host).
REM Idempotent: succeeds whether or not the network already exists.
docker network create dydx-infra 2>NUL
exit /b 0

