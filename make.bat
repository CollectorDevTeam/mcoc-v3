@ECHO OFF
IF [%1] == [] (
    GOTO help
)
IF EXIST "%~dp0.venv\" (
    SET "VENV_PYTHON=%~dp0.venv\Scripts\python"
) ELSE (
    SET VENV_PYTHON=py
)

GOTO %1

:newenv
py -3.8 -m venv --clear .venv
"%VENV_PYTHON%" -m pip install -U setuptools wheel
GOTO syncenv

:syncenv
"%VENV_PYTHON%" -m pip install -Ur requirements.txt
GOTO:EOF

:reformat
CALL "%~dp0.venv\Scripts\activate.bat"
"%VENV_PYTHON%" -m black --line-length 99 .
"%VENV_PYTHON%" -m isort -l 99 .
GOTO:EOF

:activateenv
CALL "%~dp0.venv\Scripts\activate.bat"
GOTO:EOF

:help
ECHO Create and format with make. Usage `make <command>`
ECHO.
ECHO reformat
ECHO    Reformat the files tracked by git
ECHO newenv
ECHO    Create a new virtual env
ECHO syncenv
ECHO    Sync the virtual environment
ECHO help
ECHO    Shows this message