@echo off
set "TARGET=%CD%"

for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PYTHONPATH 2^>nul') do set "OLD=%%B"

if defined OLD (
    setx PYTHONPATH "%OLD%;%TARGET%"
) else (
    setx PYTHONPATH "%TARGET%"
)

echo.
echo Added "%TARGET%" to user PYTHONPATH.
echo Restart terminals / IDEs / programs for the change to take effect.
echo.
pause