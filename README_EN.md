# Edge TTS Voice Studio

[中文](README.md) | English

A **cross-platform desktop app** built on Microsoft Edge neural voices (edge-tts), available for Windows (exe), macOS (dmg), and Linux (deb / AppImage).

No API key required, completely free, runs locally, with a clean and easy-to-use interface.

## Features

- **Voice selection**: voices grouped by country/region (142 locales, Chinese pinned on top); voice personas shown in their native names (e.g. "晓晓" for zh-CN, "七海" for ja-JP, "선히" for ko-KR)
- **Preview**: one-click preview for every voice, cached locally for instant replay
- **Text to speech**: adjustable rate / volume / pitch; long text is automatically split at sentence boundaries, synthesized per chunk, and merged into a single MP3
- **Project management**: create project folders — output files are saved into the project automatically; supports external projects with custom storage locations and easy switching
- **First-run wizard**: choose the default projects storage location on first launch
- **Dependency self-check**: missing dependencies are detected at startup and installed automatically (WebKit2GTK via the system package manager on Linux; WebView2 Runtime via Microsoft's official bootstrapper on Windows; falls back to browser mode only as a last resort)

## Screenshot

![Main window](doc/image.png)

## Download

Grab the artifact for your platform from the [Releases](https://github.com/GavinLiuOnline/edge-tts-gui/releases) page:

| Platform | Artifact | Notes |
|----------|----------|-------|
| Windows | `tts-ui.exe` | Single-file portable build; requires WebView2 (bundled with Win10/11, auto-installed if missing) |
| Linux | `tts-ui_x.y.z_amd64.deb` | Install with `sudo apt install ./tts-ui_*.deb`; WebKit2GTK dependencies are pulled automatically |
| Linux | `tts-ui-x.y.z-x86_64.AppImage` | No install needed: `chmod +x` and run (requires system WebKit2GTK; the launcher guides installation if missing) |
| macOS | `tts-ui-x.y.z-macos.dmg` | Mount and drag the .app into Applications |

On first run, a native dialog asks for the projects storage location. After that, you are good to go.

## Run from Source

Requires Python 3.10+.

```bash
pip install -r requirements.txt   # edge-tts / fastapi / uvicorn / pywebview
python app.py                     # launch the desktop window
python app.py --web               # local server only, open in a browser (debugging)
```

Missing Python packages are installed automatically via pip when running from source.

> The desktop window on Linux requires WebKit2GTK:
> - Ubuntu/Debian: `sudo apt install python3-gi python3-gi-cairo gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0`
> - Fedora: `sudo dnf install python3-gobject webkit2gtk4.1`
> - Arch: `sudo pacman -S webkit2gtk`

## Building

Packaging must be done on the target platform (no cross-compilation).

### Linux (deb + AppImage)

```bash
./build_linux.sh
```

Prerequisites: `python3-gi`, `gir1.2-webkit2-4.1`, `libwebkit2gtk-4.1-0`, `pyinstaller`, `dpkg-deb`.
Artifacts in `dist/`: the single-file binary `tts-ui`, `tts-ui_x.y.z_amd64.deb`, and `tts-ui-x.y.z-x86_64.AppImage`.
The script runs a post-build self-test (fails the build if the GUI backend is missing from the bundle).

### Windows (exe)

On a Windows machine with Python 3.10+:

```bat
build_windows.bat
```

Artifact: `dist\tts-ui.exe` (single file, no console window).

### macOS (dmg)

```bash
./build_macos.sh
```

Artifact: `dist/tts-ui-x.y.z-macos.dmg`.

### Cloud builds (GitHub Actions)

The repo ships with [`.github/workflows/build.yml`](.github/workflows/build.yml):

- Pushing a `v*` tag (e.g. `git tag v1.1.1 && git push origin v1.1.1`) triggers the three-platform matrix build and publishes to Releases
- Manual runs are supported via workflow_dispatch

## Troubleshooting

- **Cannot type Chinese (Linux desktop mode)**: on startup the app detects the running input method framework (fcitx/ibus) and injects `GTK_IM_MODULE`. If it still fails, make sure the GTK3 frontend of your IME is installed and launch with the variables set manually:
  ```bash
  # fcitx5 users
  sudo apt install fcitx5-frontend-gtk3   # Fedora: fcitx5-gtk
  GTK_IM_MODULE=fcitx XMODIFIERS=@im=fcitx tts-ui
  # ibus users
  GTK_IM_MODULE=ibus XMODIFIERS=@im=ibus tts-ui
  ```
- **Dropdowns not clickable / rendering issues (Linux)**: WebKit2GTK versions older than 2.40 have a known native dropdown popup bug; the app now uses a custom-rendered dropdown to avoid it. If issues persist, upgrade the system package: `sudo apt install libwebkit2gtk-4.1-0`.

## Configuration

Settings live in `~/.tts_ui_config.json` (projects storage location, project registry, etc.). Default paths can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_UI_HOME` | `~/tts-projects` | Default projects root (changeable in-app) |
| `TTS_UI_CACHE` | `~/.tts_ui_cache/previews` | Preview cache directory |
| `TTS_UI_CONFIG` | `~/.tts_ui_config.json` | Config file path |

## Project Structure

```
tts-ui/
├── app.py                     # Backend: local FastAPI service + pywebview window + dependency self-check
├── static/                    # Frontend: plain static HTML/CSS/JS
│   ├── index.html
│   ├── app.js
│   └── style.css
├── tts-ui.spec                # PyInstaller spec (filters GTK icon/theme assets to control size)
├── build_linux.sh             # Linux packaging: PyInstaller + deb + AppImage + self-test
├── build_windows.bat          # Windows packaging: PyInstaller onefile
├── build_macos.sh             # macOS packaging: PyInstaller + dmg
├── tools/make_icon.py         # App icon generator (png / ico / icns)
├── requirements.txt
└── .github/workflows/build.yml  # Cloud three-platform build + auto release
```

## Tech Stack

- **Backend**: Python · FastAPI + uvicorn (local HTTP service) · edge-tts (Microsoft Edge neural voices)
- **Frontend**: vanilla HTML / CSS / JavaScript, no build tooling
- **Desktop window**: pywebview (reuses the OS web view: WebKit2GTK on Linux, WebView2 on Windows, WKWebView on macOS)
- **Packaging**: PyInstaller (onefile) · dpkg-deb · AppImage · hdiutil
