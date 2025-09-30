@echo off
setlocal
REM 打包后端为单文件 exe（需已安装 requirements 和 pyinstaller）

REM 切到 backend 目录
cd /d %~dp0

REM 清理上次构建
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist EasyTunerBackend.spec del /f /q EasyTunerBackend.spec

REM 通过 PyInstaller 打包（包含 app.* 动态导入的收集）
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --name EasyTunerBackend ^
  --onefile ^
  --console ^
  --paths . ^
  --collect-submodules app ^
  --collect-submodules google.protobuf ^
  --hidden-import google.protobuf.internal ^
  serve.py

echo.
echo 打包完成：backend\dist\EasyTunerBackend.exe
echo 运行时请确保旁挂 runtime\ 与 workspace\ 目录。
endlocal

