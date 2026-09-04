@echo off
rem Windows 打包: 产出 dist\tts-ui.exe (需在本机装有 Python 3.10+)
cd /d %~dp0

echo ==^> 安装依赖
pip install -r requirements.txt pyinstaller pillow || goto :err

echo ==^> 生成图标
python tools\make_icon.py || goto :err

echo ==^> PyInstaller 打包
pyinstaller --noconfirm --clean --onefile --noconsole --name tts-ui ^
  --add-data "static;static" ^
  --icon build\icon.ico ^
  --collect-all webview ^
  --hidden-import webview.platforms.edgechromium ^
  --hidden-import webview.platforms.winforms ^
  --exclude-module PyQt5 --exclude-module PyQt6 ^
  --exclude-module cefpython3 --exclude-module numpy ^
  app.py || goto :err

echo.
echo 完成! 产物: dist\tts-ui.exe
exit /b 0
:err
echo 打包失败, 请检查上方错误信息
exit /b 1
