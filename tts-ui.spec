# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: 单文件 Linux 版, 过滤掉巨大的 GTK 主题/图标资源
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('static', 'static')],
    hiddenimports=[
        'webview.platforms.gtk',
        'gi.repository.Gtk',
        'gi.repository.Gdk',
        'gi.repository.GdkPixbuf',
        'gi.repository.GObject',
        'gi.repository.GLib',
        'gi.repository.Gio',
        'gi.repository.WebKit2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PyQt6', 'numpy', 'cefpython3',
        'webview.platforms.qt', 'webview.platforms.cef',
        'webview.platforms.winforms', 'webview.platforms.edgechromium',
        'webview.platforms.cocoa',
    ],
    noarchive=False,
)
# 过滤运行时不需要的 GUI 主题资源 (图标主题 ~200MB, GTK themes ~46MB, 各语言翻译)
a.datas = [d for d in a.datas
           if not d[0].startswith(('share/icons', 'share/themes', 'share/locale'))]

# 排除 GTK/GLib 栈, 强制使用系统库。
# 原因: WebKit2GTK 本身来自系统 (/usr/lib/.../libwebkit2gtk-4.1.so), 若同时加载
# _MEI 目录里打包的 GTK 副本会造成两份 GTK 混用 -> 白屏; 而且打包副本的编译期
# prefix 指向构建机, 找不到 immodules.cache -> fcitx5/ibus 输入法完全不接入。
# 运行前提 (python3-gi + gir1.2-webkit2-4.1) 已保证这些库在目标机存在。
_SYS_GTK_PREFIXES = (
    'libgtk-3.', 'libgdk-3.', 'libgdk_pixbuf-2.0.',
    'libglib-2.0.', 'libgobject-2.0.', 'libgio-2.0.',
    'libgmodule-2.0.', 'libgthread-2.0.', 'libgirepository-1.0.',
    'libpango-1.0.', 'libpangocairo-1.0.', 'libpangoft2-1.0.',
    'libcairo.', 'libcairo-gobject.',
    'libatk-1.0.', 'libatk-bridge-2.0.', 'libatspi.',
    'libepoxy.', 'libharfbuzz.', 'libfribidi.', 'libpixman-1.',
    'librsvg-2.', 'libsoup-', 'libwebkit2gtk-', 'libjavascriptcore',
)
a.binaries = [b for b in a.binaries
              if not b[0].split('/')[-1].startswith(_SYS_GTK_PREFIXES)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='tts-ui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
