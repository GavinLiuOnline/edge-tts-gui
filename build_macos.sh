#!/usr/bin/env bash
# macOS 打包: 产出 dist/Edge TTS 语音工作台.dmg (需在 macOS 上运行, 且安装了 Python 3.10+)
set -euo pipefail
cd "$(dirname "$0")"
VERSION=1.1.0

echo "==> 安装依赖"
pip3 install -r requirements.txt pyinstaller pillow

echo "==> 生成图标"
python3 tools/make_icon.py

echo "==> PyInstaller 打包 .app"
pyinstaller --noconfirm --clean --windowed --name "Edge TTS" \
  --add-data "static:static" \
  --icon build/icon.icns \
  --collect-all webview \
  --hidden-import webview.platforms.cocoa \
  --hidden-import pyobjc \
  --exclude-module PyQt5 --exclude-module PyQt6 \
  --exclude-module cefpython3 --exclude-module numpy \
  app.py

echo "==> 制作 dmg"
hdiutil create -volname "Edge TTS" -srcfolder "dist/Edge TTS.app" \
  -ov -format UDZO "dist/tts-ui-${VERSION}-macos.dmg"

echo
echo "完成! 产物在 dist/ 目录:"
ls -lh dist/ | grep -E "dmg|app"
