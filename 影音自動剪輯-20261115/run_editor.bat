@echo off
chcp 65001 >nul
echo ========================================================
echo     教學影片自動剪輯工作流 (Auto Video Editor)
echo ========================================================
echo.

if "%~1"=="" (
    echo [提示] 請直接將要剪輯的 MP4 影片拖曳到此批次檔上執行，
    echo 或在命令列輸入: run_editor.bat ^<影片路徑.mp4^>
    echo.
    pause
    exit /b 1
)

set INPUT_VIDEO=%~1
echo 正在處理影片: %INPUT_VIDEO%
echo.

python "%~dp0scripts\auto_pipeline.py" "%INPUT_VIDEO%"

echo.
echo ========================================================
echo 執行完畢！
echo ========================================================
pause
