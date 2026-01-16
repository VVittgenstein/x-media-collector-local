@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: 获取日期 (格式: YYYYMMDD)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set DATE=%datetime:~0,8%

set RELEASE_NAME=x-media-collector-local-%DATE%
set RELEASE_DIR=release\%RELEASE_NAME%

echo ========================================
echo  X Media Collector - 发布包构建
echo ========================================
echo.

echo [1/4] 清理旧构建...
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
if not exist "release" mkdir "release"

echo [2/4] 复制文件...
mkdir "%RELEASE_DIR%"
xcopy /e /i /q "src" "%RELEASE_DIR%\src"
copy /y "requirements.txt" "%RELEASE_DIR%\" >nul
copy /y "README.md" "%RELEASE_DIR%\" >nul
copy /y "start.bat" "%RELEASE_DIR%\" >nul
mkdir "%RELEASE_DIR%\data"

echo [3/4] 清理缓存文件...
for /d /r "%RELEASE_DIR%" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
del /s /q "%RELEASE_DIR%\*.pyc" 2>nul

echo [4/4] 打包...
if exist "release\%RELEASE_NAME%.zip" del /q "release\%RELEASE_NAME%.zip"
powershell -Command "Compress-Archive -Path '%RELEASE_DIR%' -DestinationPath 'release\%RELEASE_NAME%.zip' -Force"
rmdir /s /q "%RELEASE_DIR%"

echo.
echo ========================================
echo  完成！
echo  输出文件: release\%RELEASE_NAME%.zip
echo ========================================
pause
