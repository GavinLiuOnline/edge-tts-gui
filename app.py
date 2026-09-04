#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Edge TTS 语音工作台 - 跨平台桌面应用 (Windows exe / macOS dmg / Linux deb & AppImage)

用法:
    python app.py           # 启动桌面窗口
    python app.py --web     # 仅启动本地服务, 用浏览器访问 (调试用)
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from pathlib import Path

import edge_tts
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------- 路径
# 缓存目录可用 TTS_UI_CACHE 覆盖; 工程默认位置可用 TTS_UI_HOME 覆盖(可在应用内更改)
CACHE_DIR = Path(os.environ.get("TTS_UI_CACHE", str(Path.home() / ".tts_ui_cache" / "previews")))
CONFIG_PATH = Path(os.environ.get("TTS_UI_CONFIG", str(Path.home() / ".tts_ui_config.json")))
DEFAULT_PROJECTS_ROOT = Path(os.environ.get("TTS_UI_HOME", str(Path.home() / "tts-projects")))
if getattr(sys, "frozen", False):  # PyInstaller 打包后 static 在解包目录内
    STATIC_DIR = Path(getattr(sys, "_MEIPASS", "")) / "static"
else:
    STATIC_DIR = Path(__file__).resolve().parent / "static"

APP_NAME = "Edge TTS 语音工作台"
APP_VERSION = "1.1.0"

# ---------------------------------------------------------------- 配置与工程
def load_config() -> dict:
    cfg = {}
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text("utf-8"))
        except Exception:
            cfg = {}
    cfg.setdefault("projects_root", str(DEFAULT_PROJECTS_ROOT))
    cfg.setdefault("projects", [])   # 外部工程: [{"name": ..., "path": ...}]
    cfg.setdefault("first_run", not CONFIG_PATH.exists())
    return cfg


def save_config(cfg: dict):
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(CONFIG_PATH)


def projects_root() -> Path:
    return Path(load_config()["projects_root"])


def ensure_dirs():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    root = projects_root()
    root.mkdir(parents=True, exist_ok=True)
    if not any(root.iterdir()):
        (root / "默认工程").mkdir(exist_ok=True)


def list_projects() -> list[dict]:
    """工程注册表: 默认位置下的子目录自动注册 + 配置中的外部工程。"""
    cfg = load_config()
    root = projects_root()
    reg: dict[str, dict] = {}
    if root.is_dir():
        for d in sorted(root.iterdir()):
            if d.is_dir():
                reg[d.name] = {"name": d.name, "path": str(d), "external": False}
    for p in cfg.get("projects", []):
        if Path(p["path"]).is_dir():
            reg[p["name"]] = {"name": p["name"], "path": p["path"], "external": True}
    return sorted(reg.values(), key=lambda x: x["name"].lower())


def resolve_project(name: str) -> Path:
    """按名称定位工程目录, 防止越权访问。"""
    for p in list_projects():
        if p["name"] == name:
            return Path(p["path"]).resolve()
    raise HTTPException(404, "工程不存在")


def safe_path(project: str, file: str = "") -> Path:
    """只允许访问已注册工程目录内的文件。"""
    base = resolve_project(project)
    if file:
        if not re.fullmatch(r"[^/\\]{1,200}", file) or file in {".", ".."}:
            raise HTTPException(400, "非法的文件名")
        p = (base / file).resolve()
        if not str(p).startswith(str(base)):
            raise HTTPException(400, "非法的文件名")
        return p
    return base

# ---------------------------------------------------------------- 数据
LANG_NAMES = {
    "af": "南非荷兰语", "am": "阿姆哈拉语", "ar": "阿拉伯语", "az": "阿塞拜疆语",
    "bg": "保加利亚语", "bn": "孟加拉语", "bs": "波斯尼亚语", "ca": "加泰罗尼亚语",
    "cs": "捷克语", "cy": "威尔士语", "da": "丹麦语", "de": "德语", "el": "希腊语",
    "en": "英语", "es": "西班牙语", "et": "爱沙尼亚语", "eu": "巴斯克语",
    "fa": "波斯语", "fi": "芬兰语", "fil": "菲律宾语", "fr": "法语", "ga": "爱尔兰语",
    "gl": "加利西亚语", "gu": "古吉拉特语", "he": "希伯来语", "hi": "印地语",
    "hr": "克罗地亚语", "hu": "匈牙利语", "hy": "亚美尼亚语", "id": "印尼语",
    "is": "冰岛语", "it": "意大利语", "ja": "日语", "jv": "爪哇语", "kk": "哈萨克语",
    "km": "高棉语", "kn": "卡纳达语", "ko": "韩语", "lo": "老挝语", "lt": "立陶宛语",
    "lv": "拉脱维亚语", "mk": "马其顿语", "ml": "马拉雅拉姆语", "mn": "蒙古语",
    "mr": "马拉地语", "ms": "马来语", "mt": "马耳他语", "my": "缅甸语", "nb": "挪威语",
    "ne": "尼泊尔语", "nl": "荷兰语", "pl": "波兰语", "ps": "普什图语", "pt": "葡萄牙语",
    "ro": "罗马尼亚语", "ru": "俄语", "si": "僧伽罗语", "sk": "斯洛伐克语", "sl": "斯洛文尼亚语",
    "so": "索马里语", "sq": "阿尔巴尼亚语", "sr": "塞尔维亚语", "su": "巽他语",
    "sv": "瑞典语", "sw": "斯瓦希里语", "ta": "泰米尔语", "te": "泰卢固语", "th": "泰语",
    "tr": "土耳其语", "uk": "乌克兰语", "ur": "乌尔都语", "uz": "乌兹别克语",
    "vi": "越南语", "yue": "粤语", "zh": "中文",
}
REGION_NAMES = {
    "AE": "阿联酋", "AR": "阿根廷", "AT": "奥地利", "AU": "澳大利亚", "BE": "比利时",
    "BH": "巴林", "CA": "加拿大", "CH": "瑞士", "CL": "智利", "CN": "中国大陆",
    "CO": "哥伦比亚", "CZ": "捷克", "DE": "德国", "DK": "丹麦", "DZ": "阿尔及利亚",
    "EG": "埃及", "ES": "西班牙", "ET": "埃塞俄比亚", "FI": "芬兰", "FR": "法国",
    "GB": "英国", "GR": "希腊", "HK": "中国香港", "HR": "克罗地亚", "HU": "匈牙利",
    "ID": "印度尼西亚", "IE": "爱尔兰", "IL": "以色列", "IN": "印度", "IQ": "伊拉克",
    "IS": "冰岛", "IT": "意大利", "JO": "约旦", "JP": "日本", "KE": "肯尼亚",
    "KR": "韩国", "KW": "科威特", "LB": "黎巴嫩", "LY": "利比亚", "MA": "摩洛哥",
    "MX": "墨西哥", "MY": "马来西亚", "NG": "尼日利亚", "NL": "荷兰", "NO": "挪威",
    "NZ": "新西兰", "OM": "阿曼", "PH": "菲律宾", "PK": "巴基斯坦", "PL": "波兰",
    "PT": "葡萄牙", "QA": "卡塔尔", "RO": "罗马尼亚", "SA": "沙特", "SE": "瑞典",
    "SG": "新加坡", "SK": "斯洛伐克", "SY": "叙利亚", "TH": "泰国", "TN": "突尼斯",
    "TR": "土耳其", "TW": "中国台湾", "UA": "乌克兰", "US": "美国", "UY": "乌拉圭",
    "VN": "越南", "YE": "也门", "ZA": "南非",
}
SAMPLES = {
    "zh": "你好，这是语音试听效果。今天天气不错，希望你有美好的一天。",
    "yue": "你好，今日天气几好，希望你有个愉快嘅一日。",
    "en": "Hello! This is a voice preview. I hope you have a wonderful day.",
    "ja": "こんにちは。これは音声のプレビューです。素敵な一日をお過ごしください。",
    "ko": "안녕하세요, 이것은 음성 미리듣기입니다. 좋은 하루 보내세요.",
    "de": "Hallo! Dies ist eine Sprachvorschau. Ich wünsche dir einen schönen Tag.",
    "fr": "Bonjour ! Ceci est un aperçu de la voix. Passez une excellente journée.",
    "es": "¡Hola! Esta es una vista previa de la voz. Que tengas un buen día.",
    "ru": "Привет! Это предварительное прослушивание голоса. Хорошего дня!",
    "pt": "Olá! Esta é uma prévia da voz. Tenha um ótimo dia.",
    "it": "Ciao! Questa è un'anteprima della voce. Buona giornata!",
    "ar": "مرحبا! هذه معاينة صوتية. أتمنى لك يوما سعيدا.",
    "hi": "नमस्ते! यह आवाज़ का पूर्वावलोकन है। आपका दिन शुभ हो।",
    "th": "สวัสดีค่ะ นี่คือตัวอย่างเสียง ขอให้เป็นวันที่ดี",
    "vi": "Xin chào! Đây là bản nghe thử giọng nói. Chúc bạn một ngày tốt lành.",
    "tr": "Merhaba! Bu bir ses önizlemesidir. İyi günler dileriz.",
    "id": "Halo! Ini adalah pratinjau suara. Semoga harimu menyenangkan.",
    "nl": "Hallo! Dit is een voorbeeld van de stem. Fijne dag gewenst.",
    "pl": "Cześć! To jest podgląd głosu. Miłego dnia!",
    "sv": "Hej! Det här är en röstförhandsvisning. Ha en bra dag!",
}
SAMPLE_FALLBACK = SAMPLES["en"]

SPECIAL_LOCALES = {
    "zh-CN-liaoning": "中文（东北话）",
    "zh-CN-shaanxi": "中文（陕西话）",
    "iu-Cans-CA": "因纽特语（加拿大）",
    "iu-Latn-CA": "因纽特语（加拿大）",
}

# 音色人物本地化名称（各国母语文字），未收录的自动用拉丁名
VOICE_NAMES = {
    # 中文
    "zh-CN-XiaoxiaoNeural": "晓晓",
    "zh-CN-XiaoyiNeural": "晓伊",
    "zh-CN-YunjianNeural": "云健",
    "zh-CN-YunxiNeural": "云希",
    "zh-CN-YunxiaNeural": "云夏",
    "zh-CN-YunyangNeural": "云扬",
    "zh-CN-liaoning-XiaobeiNeural": "晓北",
    "zh-CN-shaanxi-XiaoniNeural": "晓妮",
    "zh-TW-HsiaoChenNeural": "曉臻",
    "zh-TW-HsiaoYuNeural": "曉雨",
    "zh-TW-YunJheNeural": "雲哲",
    "zh-HK-HiuGaaiNeural": "曉佳",
    "zh-HK-HiuMaanNeural": "曉曼",
    "zh-HK-WanLungNeural": "雲龍",
    # 日语
    "ja-JP-NanamiNeural": "七海",
    "ja-JP-KeitaNeural": "圭太",
    # 韩语
    "ko-KR-SunHiNeural": "선히",
    "ko-KR-InJoonNeural": "인준",
    "ko-KR-HyunsuMultilingualNeural": "현수",
    # 俄语
    "ru-RU-DmitryNeural": "Дмитрий",
    "ru-RU-SvetlanaNeural": "Светлана",
    # 乌克兰语
    "uk-UA-OstapNeural": "Остап",
    "uk-UA-PolinaNeural": "Поліна",
    # 保加利亚语
    "bg-BG-BorislavNeural": "Борислав",
    "bg-BG-KalinaNeural": "Калина",
    # 希腊语
    "el-GR-AthinaNeural": "Αθηνά",
    "el-GR-NestorasNeural": "Νέστορας",
    # 哈萨克语
    "kk-KZ-AigulNeural": "Айгүл",
    "kk-KZ-DauletNeural": "Дәулет",
    # 蒙古语
    "mn-MN-BataaNeural": "Батаа",
    "mn-MN-YesuiNeural": "Есүй",
}


def voice_display(short_name: str) -> str:
    """返回音色人物名称, 优先本地化名, 否则去掉前缀后缀的拉丁名。"""
    if short_name in VOICE_NAMES:
        return VOICE_NAMES[short_name]
    return re.sub(r"(Multilingual|Expressive)?Neural$", "", short_name.split("-", 2)[-1])


def locale_display(locale: str) -> str:
    if locale in SPECIAL_LOCALES:
        return SPECIAL_LOCALES[locale]
    lang, _, region = locale.partition("-")
    return f"{LANG_NAMES.get(lang, lang)}（{REGION_NAMES.get(region, region)}）"


def split_text(text: str, limit: int = 1200) -> list[str]:
    """长文本按句子边界分段。"""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    chunks, buf = [], ""
    for seg in re.split(r"(?<=[。！？!?\.\n])", text):
        if not seg:
            continue
        if len(buf) + len(seg) > limit and buf:
            chunks.append(buf)
            buf = ""
        # 单段超长时硬切
        while len(seg) > limit:
            chunks.append(seg[:limit])
            seg = seg[limit:]
        buf += seg
    if buf:
        chunks.append(buf)
    return chunks


def opts_str(rate: int, volume: int, pitch: int) -> dict:
    return {"rate": f"{rate:+d}%", "volume": f"{volume:+d}%", "pitch": f"{pitch:+d}Hz"}


def make_filename(voice: str, text: str) -> str:
    snippet = re.sub(r"[\s\\/:*?\"<>|]+", "", text)[:12] or "audio"
    return f"{time.strftime('%H%M%S')}_{voice.split('-')[-2]}_{snippet}.mp3"


# ---------------------------------------------------------------- 后端
app = FastAPI(title=APP_NAME)
_voice_cache = None
_tasks: dict = {}


@app.get("/api/voices")
async def api_voices():
    global _voice_cache
    if _voice_cache is None:
        _voice_cache = await edge_tts.list_voices()
    countries: dict = {}
    for v in _voice_cache:
        countries.setdefault(v["Locale"], []).append({
            "name": v["ShortName"],
            "display": voice_display(v["ShortName"]),
            "gender": "女" if v["Gender"] == "Female" else "男",
        })
    out = [{
        "locale": loc,
        "country": locale_display(loc),
        "voices": vs,
    } for loc, vs in countries.items()]
    # 简体中文在最前, 粤语/台湾/方言次之, 其余按国家名排序
    def sort_key(c):
        loc = c["locale"]
        if loc == "zh-CN":
            return (0, "", "")
        if loc.startswith(("zh", "yue")):
            return (1, "", loc)
        return (2, c["country"], loc)

    out.sort(key=sort_key)
    return out


@app.get("/api/preview")
async def api_preview(voice: str):
    if not re.fullmatch(r"[\w\-]+", voice):
        raise HTTPException(400, "非法音色")
    path = CACHE_DIR / f"{voice}.mp3"
    if not path.exists():
        lang = voice.split("-")[0]
        text = SAMPLES.get(lang, SAMPLE_FALLBACK)
        try:
            await edge_tts.Communicate(text, voice).save(str(path))
        except Exception as e:
            raise HTTPException(502, f"试听生成失败: {e}")
    return FileResponse(path, media_type="audio/mpeg", filename=f"{voice}.mp3")


class SynthBody(BaseModel):
    text: str
    voice: str
    project: str = "默认工程"
    rate: int = 0
    volume: int = 0
    pitch: int = 0


async def _run_task(task_id: str, body: "SynthBody"):
    t = _tasks[task_id]
    try:
        out = safe_path(body.project) / make_filename(body.voice, body.text)
        chunks = split_text(body.text)
        t["total"] = len(chunks)
        o = opts_str(body.rate, body.volume, body.pitch)
        parts = []
        for i, chunk in enumerate(chunks):
            part = out.with_name(f"{out.stem}__p{i}.mp3")
            await edge_tts.Communicate(chunk, body.voice, **o).save(str(part))
            parts.append(part)
            t["done"] = i + 1
        with open(out, "wb") as f:
            for p in parts:
                f.write(p.read_bytes())
        for p in parts:
            p.unlink(missing_ok=True)
        t["status"] = "done"
        t["file"] = out.name
    except Exception as e:
        t["status"] = "error"
        t["error"] = str(e)


@app.post("/api/synthesize")
async def api_synthesize(body: SynthBody):
    if not body.text.strip():
        raise HTTPException(400, "文本不能为空")
    safe_path(body.project)  # 校验工程存在
    task_id = uuid.uuid4().hex
    _tasks[task_id] = {"status": "running", "done": 0, "total": 0,
                       "file": None, "error": None, "ts": time.time()}
    asyncio.get_event_loop().create_task(_run_task(task_id, body))
    return {"task_id": task_id}


@app.get("/api/progress/{task_id}")
async def api_progress(task_id: str):
    t = _tasks.get(task_id)
    if not t:
        raise HTTPException(404, "任务不存在")
    return {k: t[k] for k in ("status", "done", "total", "file", "error")}


@app.get("/api/config")
def api_get_config():
    ensure_dirs()
    cfg = load_config()
    return {
        "projects_root": cfg["projects_root"],
        "first_run": cfg["first_run"],
        "version": APP_VERSION,
    }


class ConfigBody(BaseModel):
    projects_root: str | None = None
    first_run: bool | None = None


@app.post("/api/config")
def api_set_config(body: ConfigBody):
    cfg = load_config()
    if body.projects_root:
        p = Path(body.projects_root).expanduser().resolve()
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(400, f"无法创建目录: {e}")
        if not os.access(p, os.W_OK):
            raise HTTPException(400, "该目录没有写入权限")
        old_root = Path(cfg["projects_root"]).resolve()
        if p != old_root:
            # 旧默认位置下的工程注册为外部工程, 切换后仍可见
            registered = {pr["path"] for pr in cfg["projects"]}
            for d in sorted(old_root.iterdir()) if old_root.is_dir() else []:
                if d.is_dir() and str(d) not in registered:
                    cfg["projects"].append({"name": d.name, "path": str(d)})
        cfg["projects_root"] = str(p)
    if body.first_run is not None:
        cfg["first_run"] = body.first_run
    save_config(cfg)
    return api_get_config()


@app.get("/api/projects")
def api_projects():
    return list_projects()


class ProjectBody(BaseModel):
    name: str
    dir: str | None = None  # 存储位置, 缺省为默认位置


@app.post("/api/projects")
def api_create_project(body: ProjectBody):
    name = body.name.strip()
    if not re.fullmatch(r"[\w\u4e00-\u9fff\- ]{1,50}", name):
        raise HTTPException(400, "工程名只能包含中文、字母、数字、空格、- 或 _")
    cfg = load_config()
    root = Path(cfg["projects_root"]).resolve()
    if body.dir:
        parent = Path(body.dir).expanduser().resolve()
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(400, f"无法创建目录: {e}")
        if not os.access(parent, os.W_OK):
            raise HTTPException(400, "该目录没有写入权限")
    else:
        parent = root
    target = parent / name
    target.mkdir(parents=True, exist_ok=True)
    # 非默认位置下的工程需注册, 才会出现在工程列表中
    if parent != root and not any(p["path"] == str(target) for p in cfg["projects"]):
        cfg["projects"].append({"name": name, "path": str(target)})
        save_config(cfg)
    return {"ok": True, "name": name, "path": str(target)}


@app.get("/api/files")
def api_files(project: str):
    d = safe_path(project)
    files = []
    for f in sorted(d.glob("*.mp3"), key=lambda x: x.stat().st_mtime, reverse=True):
        if re.search(r"__p\d+\.mp3$", f.name):  # 跳过合成中的临时分片
            continue
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "mtime": int(f.stat().st_mtime),
        })
    return files


@app.get("/api/audio")
def api_audio(project: str, file: str):
    p = safe_path(project, file)
    if not p.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(p, media_type="audio/mpeg")


@app.delete("/api/file")
def api_delete_file(project: str, file: str):
    p = safe_path(project, file)
    if p.is_file():
        p.unlink()
    return {"ok": True}


@app.post("/api/open-folder")
def api_open_folder(project: str):
    d = safe_path(project)
    try:
        if sys.platform == "win32":
            os.startfile(d)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(d)])
        else:
            subprocess.Popen(["xdg-open", str(d)])
    except Exception as e:
        raise HTTPException(500, f"无法打开文件夹: {e}")
    return {"ok": True}


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


# ---------------------------------------------------------------- 桥接 (JS -> Python)
class Bridge:
    """暴露给前端 window.pywebview.api 的方法。"""

    def pick_folder(self):
        """打开系统原生的文件夹选择对话框, 返回所选路径或 None。"""
        import webview
        result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else result


# ---------------------------------------------------------------- 依赖自检
def _pip_install_missing():
    """源码运行时, 缺少的 Python 包自动安装 (打包版已内置, 跳过)。"""
    if getattr(sys, "frozen", False):
        return
    need = {"edge_tts": "edge-tts", "fastapi": "fastapi",
            "uvicorn": "uvicorn", "webview": "pywebview"}
    missing = [pkg for mod, pkg in need.items() if not _importable(mod)]
    if missing:
        print(f"正在安装缺少的依赖: {', '.join(missing)} …", flush=True)
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", *missing])
        except subprocess.CalledProcessError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


def _importable(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def _linux_webkit_ok() -> bool:
    try:
        import gi
        for ver in ("4.1", "4.0"):
            try:
                gi.require_version("WebKit2", ver)
                from gi.repository import WebKit2  # noqa: F401
                return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _linux_install_webkit() -> bool:
    """用系统包管理器安装 WebKit2GTK, 返回是否成功。"""
    distro_pkgs = [
        ("apt-get", ["gir1.2-webkit2-4.1", "libwebkit2gtk-4.1-0"],
                     ["gir1.2-webkit2-4.0", "libwebkit2gtk-4.0-37"]),
        ("dnf", ["webkit2gtk4.1"], ["webkit2gtk3"]),
        ("pacman", ["webkit2gtk"], []),
        ("zypper", ["libwebkit2gtk-4_1-0"], []),
    ]
    for pm, pkgs1, pkgs2 in distro_pkgs:
        if not _importable("shutil") or not shutil.which(pm):
            continue
        for pkgs in (pkgs1, pkgs2):
            if not pkgs:
                continue
            if pm == "apt-get":
                cmd = ["apt-get", "install", "-y", *pkgs]
            elif pm == "dnf":
                cmd = ["dnf", "install", "-y", *pkgs]
            elif pm == "pacman":
                cmd = ["pacman", "-S", "--noconfirm", *pkgs]
            else:
                cmd = ["zypper", "install", "-y", *pkgs]
            # 图形环境无终端时用 pkexec 弹出授权窗口, 终端里用 sudo
            if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
                if shutil.which("pkexec"):
                    full = ["pkexec", *cmd]
                elif sys.stdin.isatty():
                    full = ["sudo", *cmd]
                else:
                    continue
            elif sys.stdin.isatty():
                full = ["sudo", *cmd]
            else:
                continue
            print(f"正在通过 {pm} 安装依赖 {pkgs} …", flush=True)
            try:
                subprocess.check_call(full)
                if _linux_webkit_ok():
                    return True
            except Exception:
                continue
            break  # 第一组包已装上但校验失败, 不再试旧版
    return False


def _win_webview2_ok() -> bool:
    import winreg
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    ]
    for hive, path in keys:
        try:
            with winreg.OpenKey(hive, path) as k:
                pv, _ = winreg.QueryValueEx(k, "pv")
                if pv and pv != "0.0.0.0":
                    return True
        except OSError:
            continue
    return False


def _win_install_webview2():
    """下载微软官方 WebView2 引导程序并静默安装 (触发 UAC)。"""
    import ctypes
    import tempfile
    import urllib.request
    url = "https://go.microsoft.com/fwlink/?linkid=2124701"
    exe = Path(tempfile.gettempdir()) / "MicrosoftEdgeWebview2Setup.exe"
    print("正在下载 WebView2 Runtime …", flush=True)
    urllib.request.urlretrieve(url, exe)
    print("正在安装 WebView2 Runtime, 请在弹窗中允许 …", flush=True)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", str(exe), "/silent /install", None, 1)
    for _ in range(120):  # 最多等 2 分钟
        time.sleep(1)
        if _win_webview2_ok():
            return True
    return False


def check_and_install_deps():
    """启动前依赖自检: 缺失自动安装, 无法安装时给出提示。"""
    _pip_install_missing()
    if "--web" in sys.argv or os.environ.get("TTS_UI_NO_GUI"):
        return None
    if sys.platform.startswith("linux") and not _linux_webkit_ok():
        if not _linux_install_webkit():
            print("缺少 WebKit2GTK (libwebkit2gtk), 界面无法启动。\n"
                  "  Ubuntu/Debian: sudo apt install gir1.2-webkit2-4.1\n"
                  "  Fedora: sudo dnf install webkit2gtk4.1\n"
                  "  Arch:   sudo pacman -S webkit2gtk\n"
                  "已回退到浏览器模式。", flush=True)
            return "web"
    if sys.platform == "win32" and not _win_webview2_ok():
        try:
            _win_install_webview2()
        except Exception as e:
            print(f"WebView2 Runtime 安装失败: {e}\n"
                  "请到 https://developer.microsoft.com/microsoft-edge/webview2 手动安装。", flush=True)
    return None


# ---------------------------------------------------------------- 启动
def start_server(port: int = 0) -> tuple[int, uvicorn.Server]:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1] if port == 0 else port
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return port, server


def run_gui(port: int):
    import webview
    try:  # 新版 pywebview 支持允许下载
        webview.settings["ALLOW_DOWNLOADS"] = True
    except Exception:
        pass
    webview.create_window(APP_NAME, f"http://127.0.0.1:{port}",
                          js_api=Bridge(), width=1180, height=820, min_size=(960, 640))
    webview.start()


def main():
    fallback = check_and_install_deps()
    ensure_dirs()
    if "--web" in sys.argv or fallback == "web":
        port, _ = start_server()
        print(f"Edge TTS 语音工作台: http://127.0.0.1:{port}", flush=True)
        if "--no-browser" not in sys.argv:
            webbrowser.open(f"http://127.0.0.1:{port}")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    else:
        port, _ = start_server()
        run_gui(port)


if __name__ == "__main__":
    main()
