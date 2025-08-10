@echo off
setlocal enabledelayedexpansion

rem Allow overriding via environment variables; fallback to defaults
if not defined CONDA_ENV_PATH set "CONDA_ENV_PATH=D:\miniconda\envs\py39"
if not defined PROJECT_DIR set "PROJECT_DIR=d:\PythonProjects\garmentcode_project"

rem Basic validation
if not exist "%CONDA_ENV_PATH%\python.exe" (
  echo [ERROR] Python not found in "%CONDA_ENV_PATH%"
  exit /b 9001
)
if not exist "%PROJECT_DIR%\pattern_sampler.py" (
  echo [ERROR] pattern_sampler.py not found in "%PROJECT_DIR%"
  exit /b 9002
)

rem Explicit PATH to avoid relying on interactive conda activation
set "PATH=%CONDA_ENV_PATH%\Library\mingw-w64\bin;%CONDA_ENV_PATH%\Library\usr\bin;%CONDA_ENV_PATH%\Library\bin;%CONDA_ENV_PATH%\Scripts;%CONDA_ENV_PATH%;%PATH%"
set "CONDA_PREFIX=%CONDA_ENV_PATH%"
set "CONDA_DEFAULT_ENV=py39"

rem Force UTF-8 to prevent codepage issues
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=UTF-8"

rem Ensure relative paths work from project dir
cd /d "%PROJECT_DIR%"

set "PATH=%PROJECT_DIR%\pygarment\pattern\cairo_dlls;%PATH%"

"%CONDA_ENV_PATH%\python.exe" "pattern_sampler.py" %*
exit /b %errorlevel%
