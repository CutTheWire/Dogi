@echo off
chcp 65001
SETLOCAL

SET PYTHON_PATH=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe

SET ENV_DIR=.venv

"%PYTHON_PATH%" -m venv %ENV_DIR%

IF NOT EXIST "%ENV_DIR%\Scripts\activate.ps1" (
    echo 가상 환경 생성에 실패했습니다.
    EXIT /B 1
)

echo 가상 환경 활성화 중...
powershell -NoExit -ExecutionPolicy Bypass -Command "& { .\%ENV_DIR%\Scripts\Activate.ps1 }"

ENDLOCAL