@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "PROJECT_PYTHON=%PROJECT_ROOT%.venv\Scripts\python.exe"

REM Forwards --smoke-test --camera-index --seconds to v2_runtime.launcher.
if not exist "%PROJECT_PYTHON%" (
    echo Runtime error: .venv\Scripts\python.exe is missing. 1>&2
    exit /b 3
)

pushd "%PROJECT_ROOT%"
"%PROJECT_PYTHON%" -m v2_runtime.launcher %*
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
