@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ========================================
echo   飞猪MCP — FlyAI 旅行查询与攻略
echo ========================================
echo.

where node >nul 2>&1
if errorlevel 1 (
    echo [提示] 未检测到 Node.js，请先安装：
    echo   https://nodejs.org/  选 LTS 版本
    echo 安装后在本目录双击 scripts\安装依赖.bat
    echo.
    pause
    exit /b 1
)

if not exist "node_modules\@fly-ai\flyai-cli" (
    echo [提示] 首次使用请先运行 scripts\安装依赖.bat
    echo.
)

:menu
echo 请选择：
echo   1. 探测连接（probe）
echo   2. AI 语义搜索
echo   3. 生成旅行攻略
echo   4. 查看命令帮助
echo   0. 退出
echo.
set /p choice=输入数字：

if "%choice%"=="1" goto probe
if "%choice%"=="2" goto ai
if "%choice%"=="3" goto guide
if "%choice%"=="4" goto help
if "%choice%"=="0" exit /b 0
goto menu

:probe
python main.py probe
pause
goto menu

:ai
set /p q=输入查询（例：五一杭州三日游预算2000）：
python main.py ai "%q%"
pause
goto menu

:guide
set /p dest=目的地（例：杭州）：
set /p days=天数（例：3）：
set /p origin=出发城市（可留空）：
set /p budget=人均预算元（可留空）：
if "%budget%"=="" (
    python main.py guide "%dest%" %days% --origin "%origin%" --print
) else (
    python main.py guide "%dest%" %days% --origin "%origin%" --budget %budget% --print
)
pause
goto menu

:help
python main.py --help
pause
goto menu
