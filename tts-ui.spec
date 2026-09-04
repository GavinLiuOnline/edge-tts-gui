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
