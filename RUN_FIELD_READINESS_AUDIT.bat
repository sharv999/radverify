@echo off
setlocal
cd /d "%~dp0"
if not exist "field_audits" mkdir "field_audits"
if exist ".venv\Scripts\python.exe" (
  set "RV_PYTHON=.venv\Scripts\python.exe"
) else (
  set "RV_PYTHON=python"
)
"%RV_PYTHON%" -m radverify.deployment --output "field_audits\radverify_field_readiness_audit.md"
if errorlevel 1 (
  echo.
  echo Automated audit FAILED. Review field_audits\radverify_field_readiness_audit.md
) else (
  echo.
  echo Automated audit PASSED; manual field acceptance is still NOT CLEARED.
)
echo.
pause
