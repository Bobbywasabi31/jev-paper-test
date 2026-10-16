@echo off
title Jev Stock Prediction Launcher
set "PYTHON=C:\Jev\.venv\Scripts\python.exe"
set "SERVE=C:\Jev\serve.py"
set "PROJECT=C:\Jev\MarketTest\Jev_SPY_QQQ_Paper_Test"

echo ==================================
echo       JEV STOCK PREDICTOR
echo ==================================
echo.

if not exist "%PYTHON%" (
    echo ERROR: Python environment not found at %PYTHON%.
    pause
    exit /b 1
)
if not exist "%SERVE%" (
    echo ERROR: serve.py not found at %SERVE%.
    pause
    exit /b 1
)
if not exist "%PROJECT%\jev_market_test.py" (
    echo ERROR: jev_market_test.py not found in %PROJECT%.
    pause
    exit /b 1
)

echo Checking Jev server on 127.0.0.1:8013...
powershell -NoProfile -Command "$c = New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1', 8013); $c.Close(); exit 0 } catch { exit 1 }"
if not errorlevel 1 goto READY

echo Starting MiniCPM5-2B-Jev...
start "Jev AI Server" cmd /k ""%PYTHON%" "%SERVE%" --host 127.0.0.1 --port 8013"
echo Waiting for the server to accept connections...
set /a TRIES=0

:WAIT
powershell -NoProfile -Command "$c = New-Object Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1', 8013); $c.Close(); exit 0 } catch { exit 1 }"
if not errorlevel 1 goto READY
set /a TRIES+=1
if %TRIES% GEQ 60 (
    echo ERROR: server did not come up after 5 minutes. Check the "Jev AI Server" window.
    pause
    exit /b 1
)
timeout /t 5 /nobreak >nul
goto WAIT

:READY
echo Jev server responding.
echo.
echo Settling finished predictions, then running today's prediction...

cd /d "%PROJECT%"
"%PYTHON%" jev_market_test.py settle
"%PYTHON%" jev_market_test.py predict --backend minicpm
if errorlevel 1 (
    echo ERROR: Prediction step failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo ===== JEV PERFORMANCE REPORT =====
"%PYTHON%" jev_market_test.py report

echo.
echo ==================================
echo       DONE
echo ==================================
echo.
echo Results: %PROJECT%\predictions.csv
echo NOTE: predict prints SKIP before 4:30pm ET - the session isn't complete yet.
echo.
pause
