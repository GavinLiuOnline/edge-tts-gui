#!/usr/bin/env bash
# Linux 打包: PyInstaller onefile + deb + AppImage
set -euo pipefail
cd "$(dirname "$0")"
VERSION=1.1.0
APP=tts-ui

echo "==> [1/4] 生成图标"
python3 tools/make_icon.py

echo "==> [2/4] PyInstaller 打包"
pyinstaller --noconfirm --clean tts-ui.spec

echo "==> [3/4] 构建 deb"
DEB="packaging/deb/${APP}_${VERSION}_amd64"
rm -rf "$DEB"
mkdir -p "$DEB/DEBIAN" "$DEB/opt/$APP" "$DEB/usr/bin" \
         "$DEB/usr/share/applications" "$DEB/usr/share/icons/hicolor/512x512/apps"
cp "dist/$APP" "$DEB/opt/$APP/$APP"
cat > "$DEB/usr/bin/$APP" <<EOF
#!/bin/sh
exec /opt/$APP/$APP "\$@"
EOF
chmod +x "$DEB/usr/bin/$APP"
cat > "$DEB/DEBIAN/control" <<EOF
Package: $APP
Version: $VERSION
Section: sound
Priority: optional
Architecture: amd64
Maintainer: nuanyang <nuanyang@localhost>
Depends: libgtk-3-0, libwebkit2gtk-4.1-0 | libwebkit2gtk-4.0-37, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0
Description: Edge TTS 语音工作台
 基于微软 Edge 神经网络语音的跨平台语音合成工具,
 支持按国家选择音色、试听、长文本合成、工程化管理输出文件。
EOF
cat > "$DEB/usr/share/applications/$APP.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Edge TTS 语音工作台
Comment=微软 Edge 神经网络语音合成
Exec=/opt/$APP/$APP
Icon=$APP
Terminal=false
Categories=Audio;AudioVideo;Utility;
StartupNotify=true
EOF
cp build/icon.png "$DEB/usr/share/icons/hicolor/512x512/apps/$APP.png"
dpkg-deb --build --root-owner-group "$DEB" "dist/${APP}_${VERSION}_amd64.deb"

echo "==> [4/4] 构建 AppImage"
APPDIR="packaging/appimage/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/icons/hicolor/512x512/apps"
cp "dist/$APP" "$APPDIR/usr/bin/$APP"
cp build/icon.png "$APPDIR/$APP.png"
cp build/icon.png "$APPDIR/usr/share/icons/hicolor/512x512/apps/$APP.png"
cat > "$APPDIR/$APP.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Edge TTS 语音工作台
Comment=微软 Edge 神经网络语音合成
Exec=$APP
Icon=$APP
Terminal=false
Categories=Audio;AudioVideo;Utility;
StartupNotify=true
EOF
cat > "$APPDIR/AppRun" <<EOF
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
exec "\$HERE/usr/bin/$APP" "\$@"
EOF
chmod +x "$APPDIR/AppRun"

TOOL=packaging/appimagetool-x86_64.AppImage
RUNTIME=packaging/runtime-x86_64
if [ ! -f "$TOOL" ]; then
  echo "下载 appimagetool…"
  curl -fsSL -o "$TOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x "$TOOL"
fi
if [ ! -f "$RUNTIME" ]; then
  echo "下载 runtime…"
  curl -fsSL -o "$RUNTIME" "https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64"
fi
"$TOOL" --appimage-extract-and-run --runtime-file "$RUNTIME" "$APPDIR" "dist/${APP}-${VERSION}-x86_64.AppImage"

echo
echo "完成! 产物在 dist/ 目录:"
ls -lh dist/ | grep -E "deb|AppImage|tts-ui$"
