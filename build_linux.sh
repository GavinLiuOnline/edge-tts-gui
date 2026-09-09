#!/usr/bin/env bash
# Linux 打包: PyInstaller onefile + deb + AppImage
set -euo pipefail
cd "$(dirname "$0")"
VERSION=1.1.5
APP=tts-ui

# GUI 后端依赖 python3-gi (系统包, pip 无法安装), 缺失会导致打包产物回退浏览器模式
if ! python3 -c "import gi" 2>/dev/null; then
  echo "错误: 缺少 python3-gi (PyGObject)。请先安装:"
  echo "  Ubuntu/Debian: sudo apt install python3-gi python3-gi-cairo gir1.2-webkit2-4.1"
  echo "  Fedora: sudo dnf install python3-gobject webkit2gtk4.1"
  exit 1
fi

echo "==> [1/4] 生成图标"
python3 tools/make_icon.py

echo "==> [2/4] PyInstaller 打包"
python3 -m PyInstaller --noconfirm --clean tts-ui.spec

echo "==> [3/4] 打包产物自检 (GUI 后端)"
if ! dist/$APP --selftest; then
  echo "错误: 打包产物缺少 GUI 后端 (gi/WebKit), 运行会回退浏览器模式。"
  echo "请确认构建环境已安装 python3-gi 与 gir1.2-webkit2-4.1。"
  exit 1
fi

echo "==> [4/4] 构建 deb"
DEB="packaging/deb/${APP}_${VERSION}_amd64"
rm -rf "$DEB"
mkdir -p "$DEB/DEBIAN" "$DEB/opt/$APP" "$DEB/usr/bin" \
         "$DEB/usr/share/applications" "$DEB/usr/share/icons/hicolor/512x512/apps"
cp "dist/$APP" "$DEB/opt/$APP/$APP"
cat > "$DEB/usr/bin/$APP" <<EOF
#!/bin/sh
# 规避 WebKitGTK DMABUF 渲染器在部分显卡上崩溃 (白屏/闪退)
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export WEBKIT_DISABLE_COMPOSITING_MODE=1
# 输入法修复: 让 PyInstaller 打包的 GTK 找到 immodules.cache, 详见 AppRun 段注释
if [ -z "\$GTK_IM_MODULE_FILE" ]; then
  for c in /usr/lib/x86_64-linux-gnu/gtk-3.0/3.0.0/immodules.cache \
           /usr/lib64/gtk-3.0/3.0.0/immodules.cache \
           /usr/lib/gtk-3.0/3.0.0/immodules.cache; do
    if [ -f "\$c" ]; then
      export GTK_IM_MODULE_FILE="\$c"
      break
    fi
  done
fi
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
Exec=/usr/bin/$APP
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
cat > "$APPDIR/AppRun" <<'APPRUN_EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"

# 规避 WebKitGTK DMABUF 渲染器在部分显卡上崩溃 (白屏/闪退)
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export WEBKIT_DISABLE_COMPOSITING_MODE=1

# 输入法关键修复: PyInstaller 打包的 GTK 副本找不到宿主 immodules.cache,
# 导致 im-fcitx5.so 不加载 -> 输入法不接入。tts-ui.spec 已排除 GTK 系库改用系统 GTK,
# 这里再兜底指定 cache 路径, 应对系统 GTK 自身 cache 定位异常的情况。
if [ -z "$GTK_IM_MODULE_FILE" ]; then
  for c in /usr/lib/x86_64-linux-gnu/gtk-3.0/3.0.0/immodules.cache \
           /usr/lib64/gtk-3.0/3.0.0/immodules.cache \
           /usr/lib/gtk-3.0/3.0.0/immodules.cache; do
    if [ -f "$c" ]; then
      export GTK_IM_MODULE_FILE="$c"
      break
    fi
  done
fi

# 自动检测 fcitx5/fcitx/ibus 进程并补缺 IM 环境变量
if [ -z "$GTK_IM_MODULE" ]; then
  if pgrep -x fcitx5 >/dev/null 2>&1 || pgrep -x fcitx >/dev/null 2>&1; then
    export GTK_IM_MODULE=fcitx
  elif pgrep -x ibus-daemon >/dev/null 2>&1; then
    export GTK_IM_MODULE=ibus
  fi
fi
if [ -z "$XMODIFIERS" ] && [ -n "$GTK_IM_MODULE" ]; then
  export XMODIFIERS="@im=$GTK_IM_MODULE"
fi
if [ -n "$GTK_IM_MODULE" ]; then
  export QT_IM_MODULE="${QT_IM_MODULE:-$GTK_IM_MODULE}"
fi

exec "$HERE/usr/bin/tts-ui" "$@"
APPRUN_EOF
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
