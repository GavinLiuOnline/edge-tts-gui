#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成应用图标: build/icon.png / icon.ico / icon.icns"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "build"
OUT.mkdir(exist_ok=True)

S = 512


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c1, c2 = (59, 124, 255), (99, 102, 241)
    # 圆角渐变底
    grad = Image.new("RGBA", (size, size))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        gd.line([(0, y), (size, y)], fill=lerp(c1, c2, y / size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)
    # 白色声波柱
    bars = [(0.32, 0.42, 0.58), (0.44, 0.30, 0.70), (0.56, 0.38, 0.62), (0.68, 0.46, 0.54)]
    w = int(size * 0.07)
    for cx, h1, h2 in bars:
        x = int(size * cx - w / 2)
        top = int(size * h1)
        bot = int(size * h2)
        d.rounded_rectangle([x, top, x + w, bot], radius=w // 2, fill=(255, 255, 255, 255))
    return img


icon = make(S)
icon.save(OUT / "icon.png")
icon.save(OUT / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
icon.save(OUT / "icon.icns")
print("icons written to", OUT)
