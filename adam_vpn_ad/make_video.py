#!/usr/bin/env python3
"""Пиксельный рекламный ролик «Адам VPN» для TikTok (9:16, 1080x1920).

Запуск:  python3 make_video.py
Нужны: Python 3, Pillow, numpy, ffmpeg, espeak-ng.
Результат: adam_vpn_ad.mp4 (+ voice.wav, music.wav, mix.wav для замены озвучки).

Если хотите свою озвучку: положите файлы voice_1.wav ... voice_8.wav рядом со скриптом
(по одному на реплику из LINES) и запустите с флагом --keep-voice.
"""
import math
import os
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 135, 240, 30  # логический холст, х8 = 1080x1920
SR = 44100

FONT_PATH = "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"
F10 = ImageFont.truetype(FONT_PATH, 10)
F12 = ImageFont.truetype(FONT_PATH, 12)
F18 = ImageFont.truetype(FONT_PATH, 18)
F24 = ImageFont.truetype(FONT_PATH, 24)

# ---------------------------------------------------------------- сценарий
# (текст на экране/субтитры, текст для синтеза речи, сцена)
LINES = [
    ("Контрольная по математике. А ты вообще не готов?",
     "Контрольная по математике. А ты вообще не готов?", "class"),
    ("Но у тебя есть план: нейросеть Gemini.",
     "Но у тебя есть план: нейросеть Джемини.", "plan"),
    ("Ой. Недоступно в твоём регионе.",
     "Ой. Недоступно в твоём регионе.", "err1"),
    ("Включаешь обычный VPN, а Gemini и его не пускает.",
     "Включаешь обычный вэ пэ эн, а Джемини и его не пускает.", "err2"),
    ("Учительница уже смотрит на тебя!",
     "Учительница уже смотрит на тебя!", "panic"),
    ("Но у тебя есть Адам VPN. Одно нажатие, и всё работает!",
     "Но у тебя есть Адам вэ пэ эн. Одно нажатие, и всё работает!", "adam"),
    ("Даже там, где обычные VPN сдаются.",
     "Даже там, где обычные вэ пэ эн сдаются.", "win"),
    ("Адам VPN. Скачай по ссылке в профиле!",
     "Адам вэ пэ эн. Скачай по ссылке в профиле!", "end"),
]
HILITE = ("gemini", "vpn", "адам", "нейросеть", "недоступно", "регионе", "всё", "работает!", "скачай")

# палитра
C = dict(
    wall=(74, 54, 118), wall2=(62, 44, 104), floor=(46, 32, 78), floor2=(38, 26, 66),
    board=(28, 96, 76), frame=(150, 96, 52), desk=(176, 112, 62), desk2=(138, 84, 44),
    skin=(255, 208, 164), hair=(96, 54, 30), hood=(242, 124, 44), hood2=(200, 94, 30),
    black=(16, 12, 28), white=(250, 250, 255), red=(236, 64, 72), green=(70, 240, 150),
    yellow=(255, 222, 70), blue=(86, 150, 255), purple=(150, 90, 255), gray=(130, 130, 150),
    tgray=(150, 150, 160), dress=(206, 66, 96), thair=(176, 176, 190),
)


# ---------------------------------------------------------------- озвучка
def synth_voice():
    paths, durs = [], []
    for i, (_, speak, _) in enumerate(LINES, 1):
        p = os.path.join(HERE, f"voice_{i}.wav")
        if "--keep-voice" not in sys.argv or not os.path.exists(p):
            subprocess.run(["espeak-ng", "-v", "ru+m3", "-s", "178", "-p", "42", "-a", "190",
                            "-w", p, speak], check=True)
        with wave.open(p) as w:
            durs.append(w.getnframes() / w.getframerate())
        paths.append(p)
    return paths, durs


def read_wav_mono(path):
    with wave.open(path) as w:
        sr, n = w.getframerate(), w.getnframes()
        a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
        if w.getnchannels() > 1:
            a = a.reshape(-1, w.getnchannels()).mean(1)
    if sr != SR:
        x = np.linspace(0, len(a) - 1, int(len(a) * SR / sr))
        a = np.interp(x, np.arange(len(a)), a)
    return a


def write_wav(path, a):
    a = np.clip(a, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- звук
def osc(kind, f, n, duty=0.5):
    t = np.arange(n) / SR
    ph = (f * t) % 1.0
    if kind == "sq":
        return np.where(ph < duty, 1.0, -1.0)
    if kind == "tri":
        return 4 * np.abs(ph - 0.5) - 1
    return np.random.uniform(-1, 1, n)


def tone(f0, f1, dur, kind="sq", vol=0.3, duty=0.5):
    n = int(dur * SR)
    f = np.linspace(f0, f1, n)
    ph = np.cumsum(f) / SR % 1.0
    if kind == "sq":
        w = np.where(ph < duty, 1.0, -1.0)
    elif kind == "tri":
        w = 4 * np.abs(ph - 0.5) - 1
    else:
        w = np.random.uniform(-1, 1, n)
    env = np.linspace(1, 0, n) ** 1.5
    return w * env * vol


def put(buf, start, snd):
    i = int(start * SR)
    if i < 0 or i >= len(buf):
        return
    e = min(len(buf), i + len(snd))
    buf[i:e] += snd[:e - i]


def midi(n):
    return 440 * 2 ** ((n - 69) / 12)


def make_music(total):
    buf = np.zeros(int(total * SR) + SR)
    bpm = 128
    step = 60 / bpm / 4
    prog = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [48, 52, 55]), (55, [55, 59, 62])]
    n_steps = int(total / step) + 1
    for s in range(n_steps):
        t = s * step
        bar = (s // 16) % 4
        root, ch = prog[bar]
        arp = ch[s % 3] + (12 if (s // 3) % 2 else 24)
        put(buf, t, tone(midi(arp), midi(arp), step * 0.9, "sq", 0.10, 0.25))
        if s % 4 == 0:
            put(buf, t, tone(midi(root - 12), midi(root - 12), step * 3.5, "tri", 0.30))
            put(buf, t, tone(150, 45, 0.12, "tri", 0.35))
        if s % 2 == 1:
            put(buf, t, tone(0, 0, 0.04, "n", 0.07))
    return buf


def sfx_error():
    return np.concatenate([tone(300, 300, 0.12, "sq", 0.35), np.zeros(int(0.03 * SR)),
                           tone(200, 150, 0.30, "sq", 0.38)])


def sfx_blip():
    return tone(600, 1100, 0.07, "sq", 0.28)


def sfx_up():
    return np.concatenate([tone(midi(n), midi(n), 0.07, "sq", 0.28, 0.25)
                           for n in (60, 64, 67, 72, 76, 79)])


def sfx_idea():
    return np.concatenate([tone(500, 500, 0.06, "sq", 0.25), tone(750, 750, 0.06, "sq", 0.25),
                           tone(1000, 1000, 0.12, "sq", 0.25)])


def sfx_alarm():
    return np.concatenate([tone(880, 880, 0.10, "sq", 0.3), np.zeros(int(0.06 * SR)),
                           tone(880, 880, 0.10, "sq", 0.3)])


def sfx_fanfare():
    n1 = [tone(midi(n), midi(n), 0.11, "sq", 0.3, 0.25) for n in (67, 72, 76, 79)]
    chord = sum(tone(midi(n), midi(n), 0.7, "sq", 0.18, 0.25) for n in (72, 76, 79, 84))
    return np.concatenate(n1 + [chord])


def sfx_coin():
    return np.concatenate([tone(988, 988, 0.07, "sq", 0.25), tone(1319, 1319, 0.25, "sq", 0.25)])


def sfx_tick():
    return tone(1500, 1000, 0.03, "sq", 0.2)


# ---------------------------------------------------------------- рисование
def R(d, x0, y0, x1, y1, col):
    x0, x1 = sorted((int(x0), int(x1)))
    y0, y1 = sorted((int(y0), int(y1)))
    d.rectangle([x0, y0, x1, y1], fill=col)


def text(d, x, y, s, font=F12, fill=C["white"], outline=C["black"], anchor="lt", ol=1):
    d.fontmode = "1"
    if outline:
        for ox in range(-ol, ol + 1):
            for oy in range(-ol, ol + 1):
                if ox or oy:
                    d.text((x + ox, y + oy), s, font=font, fill=outline, anchor=anchor)
    d.text((x, y), s, font=font, fill=fill, anchor=anchor)


def sparkle(d, cx, cy, r, col=C["blue"], col2=C["purple"]):
    k = max(1, r // 3)
    pts = [(cx, cy - r), (cx + k, cy - k), (cx + r, cy), (cx + k, cy + k),
           (cx, cy + r), (cx - k, cy + k), (cx - r, cy), (cx - k, cy - k)]
    d.polygon(pts, fill=col)
    k2 = max(1, r // 2)
    d.polygon([(cx, cy - k2), (cx + 1, cy - 1), (cx + k2, cy), (cx + 1, cy + 1),
               (cx, cy + k2), (cx - 1, cy + 1), (cx - k2, cy), (cx - 1, cy - 1)], fill=col2)


def shield(d, cx, cy, w, h, letter=True, font=F24):
    pts = [(cx - w, cy - h), (cx + w, cy - h), (cx + w, cy + h * 0.25), (cx, cy + h), (cx - w, cy + h * 0.25)]
    d.polygon(pts, fill=C["black"])
    w2, h2 = w - 2, h - 2
    d.polygon([(cx - w2, cy - h2), (cx + w2, cy - h2), (cx + w2, cy + h2 * 0.25), (cx, cy + h2),
               (cx - w2, cy + h2 * 0.25)], fill=C["green"])
    d.polygon([(cx - w2 + 3, cy - h2 + 3), (cx + w2 - 3, cy - h2 + 3), (cx + w2 - 3, cy + h2 * 0.2),
               (cx, cy + h2 - 4), (cx - w2 + 3, cy + h2 * 0.2)], fill=(30, 40, 90))
    if letter:
        text(d, cx, cy - 1, "A", font, C["green"], None, "mm")


def clock(d, x, y, t, urgent=False):
    R(d, x - 7, y - 7, x + 7, y + 7, C["black"])
    R(d, x - 6, y - 6, x + 6, y + 6, C["white"])
    a = t * (3 if urgent else 0.5)
    d.line([x, y, x + int(5 * math.sin(a)), y - int(5 * math.cos(a))], fill=C["red"] if urgent else C["black"])
    d.line([x, y, x + int(3 * math.sin(a / 12)), y - int(3 * math.cos(a / 12))], fill=C["black"])


def draw_kid(d, cx, y, expr, t):
    b = int(round(math.sin(t * 5)))  # покачивание
    y += b
    # худи
    R(d, cx - 14, y + 17, cx + 13, y + 46, C["hood"])
    R(d, cx - 14, y + 17, cx - 12, y + 46, C["hood2"])
    R(d, cx + 12, y + 17, cx + 13, y + 46, C["hood2"])
    R(d, cx - 5, y + 17, cx + 4, y + 20, C["hood2"])
    R(d, cx - 3, y + 21, cx - 3, y + 28, C["white"])
    R(d, cx + 2, y + 21, cx + 2, y + 28, C["white"])
    # голова
    R(d, cx - 10, y + 1, cx + 9, y + 17, C["black"])
    R(d, cx - 9, y + 2, cx + 8, y + 16, C["skin"])
    R(d, cx - 10, y - 2, cx + 9, y + 4, C["hair"])
    R(d, cx - 10, y + 4, cx - 8, y + 8, C["hair"])
    R(d, cx + 7, y + 4, cx + 9, y + 8, C["hair"])
    R(d, cx - 4, y + 4, cx + 3, y + 5, C["hair"])
    ex1, ex2, ey = cx - 5, cx + 3, y + 8
    k = C["black"]
    if expr == "smirk":
        R(d, ex1, ey, ex1 + 1, ey + 1, k); R(d, ex2, ey, ex2 + 1, ey + 1, k)
        R(d, ex1 - 1, ey - 3, ex1 + 2, ey - 3, k); R(d, ex2 - 1, ey - 4, ex2 + 2, ey - 3, k)
        R(d, cx - 3, y + 13, cx + 4, y + 13, k); R(d, cx + 4, y + 12, cx + 5, y + 12, k)
    elif expr == "worry":
        R(d, ex1, ey, ex1 + 1, ey + 2, k); R(d, ex2, ey, ex2 + 1, ey + 2, k)
        R(d, ex1 - 1, ey - 3, ex1 + 2, ey - 4, k); R(d, ex2 - 1, ey - 4, ex2 + 2, ey - 3, k)
        R(d, cx - 3, y + 13, cx + 3, y + 13, k)
        R(d, cx + 8, y + 5, cx + 9, y + 7, C["blue"])
    elif expr == "shock":
        for ex in (ex1 - 1, ex2 - 1):
            R(d, ex, ey - 1, ex + 3, ey + 3, C["white"]); R(d, ex + 1, ey, ex + 2, ey + 2, k)
        R(d, cx - 2, y + 12, cx + 2, y + 15, k)
        s = (int(t * 12) % 4)
        R(d, cx + 10, y + 3 + s, cx + 11, y + 6 + s, C["blue"])
        R(d, cx - 12, y + 6 + (s + 2) % 4, cx - 11, y + 9 + (s + 2) % 4, C["blue"])
    elif expr == "happy":
        for ex in (ex1, ex2):
            R(d, ex, ey, ex + 1, ey, k); R(d, ex - 1, ey + 1, ex - 1, ey + 1, k); R(d, ex + 2, ey + 1, ex + 2, ey + 1, k)
        R(d, cx - 4, y + 12, cx + 4, y + 12, k); R(d, cx - 3, y + 13, cx + 3, y + 15, k)
        R(d, cx - 2, y + 14, cx + 2, y + 15, C["red"])
    else:  # calm
        R(d, ex1, ey, ex1 + 1, ey + 1, k); R(d, ex2, ey, ex2 + 1, ey + 1, k)
        R(d, cx - 2, y + 13, cx + 2, y + 13, k)


def draw_teacher(d, cx, y, front, t, paper=False):
    y += int(round(math.sin(t * 4) * 0.7))
    R(d, cx - 9, y + 13, cx + 8, y + 42, C["dress"])
    R(d, cx - 9, y + 13, cx - 8, y + 42, (160, 44, 70))
    R(d, cx - 3, y + 13, cx + 2, y + 16, C["white"])
    R(d, cx - 8, y + 42, cx - 3, y + 50, C["black"]); R(d, cx + 2, y + 42, cx + 7, y + 50, C["black"])
    # руки
    R(d, cx - 12, y + 16, cx - 9, y + 30, C["dress"])
    R(d, cx + 8, y + 16, cx + 11, y + 30, C["dress"])
    R(d, cx - 12, y + 30, cx - 9, y + 32, C["skin"]); R(d, cx + 8, y + 30, cx + 11, y + 32, C["skin"])
    if paper:
        R(d, cx - 14, y + 26, cx - 5, y + 36, C["white"]); R(d, cx - 13, y + 28, cx - 7, y + 28, C["gray"])
        R(d, cx - 13, y + 31, cx - 8, y + 31, C["gray"])
    # голова
    R(d, cx - 8, y + 1, cx + 7, y + 14, C["black"])
    R(d, cx - 7, y + 2, cx + 6, y + 13, C["skin"])
    R(d, cx - 4, y - 5, cx + 3, y - 1, C["thair"])  # пучок
    R(d, cx - 8, y - 1, cx + 7, y + 3, C["thair"])
    if front:
        R(d, cx - 6, y + 6, cx - 2, y + 9, C["black"]); R(d, cx + 1, y + 6, cx + 5, y + 9, C["black"])
        R(d, cx - 5, y + 7, cx - 3, y + 8, C["white"]); R(d, cx + 2, y + 7, cx + 4, y + 8, C["white"])
        R(d, cx - 2, y + 7, cx, y + 7, C["black"])
        R(d, cx - 2, y + 11, cx + 2, y + 11, C["red"])
    else:
        R(d, cx - 8, y + 1, cx + 7, y + 13, C["thair"])
        R(d, cx - 8, y + 1, cx + 7, y + 3, (150, 150, 168))


def classroom(d, t, urgent=False):
    R(d, 0, 0, W, 130, C["wall"])
    for yy in range(0, 130, 12):
        R(d, 0, yy, W, yy, C["wall2"])
    R(d, 0, 118, W, 130, C["wall2"])
    R(d, 0, 130, W, H, C["floor"])
    for yy in range(138, H, 14):
        R(d, 0, yy, W, yy, C["floor2"])
    # доска
    R(d, 9, 16, 112, 70, C["frame"]); R(d, 12, 19, 109, 67, C["board"])
    text(d, 60, 24, "x² + 4x = 21", F10, C["white"], None, "mt")
    text(d, 60, 40, "x = ?", F12, C["yellow"], None, "mt")
    # мел
    R(d, 14, 68, 108, 70, C["desk2"])
    clock(d, 124, 26, t, urgent)
    # плакат
    R(d, 114, 46, 130, 64, C["white"]); R(d, 116, 48, 128, 52, C["blue"]); R(d, 116, 55, 128, 56, C["gray"]); R(d, 116, 59, 126, 60, C["gray"])


def desk_front(d, paper=None, t=0):
    R(d, 6, 200, 128, 208, C["desk"])
    R(d, 6, 208, 128, 212, C["desk2"])
    R(d, 12, 212, 16, 232, C["desk2"]); R(d, 118, 212, 122, 232, C["desk2"])
    if paper:
        R(d, 76, 190, 108, 200, C["white"])
        R(d, 76, 190, 108, 190, C["gray"])
        if paper == "5":
            text(d, 92, 195, "5", F18, C["red"], None, "mm", 0)
        else:
            text(d, 92, 195, "КР", F10, C["black"], None, "mm", 0)


# ---------------------------------------------------------------- телефон
PX0, PY0, PX1, PY1 = 20, 8, 115, 124  # корпус
SX0, SY0, SX1, SY1 = 25, 15, 110, 117  # экран


def phone_frame(d, oy=0):
    R(d, PX0, PY0 + oy, PX1, PY1 + oy, C["black"])
    R(d, PX0 + 1, PY0 - 1 + oy, PX1 - 1, PY0 + oy, C["black"])
    R(d, SX0 - 1, SY0 - 1 + oy, SX1 + 1, SY1 + 1 + oy, (60, 60, 80))
    R(d, 58, PY0 + 2 + oy, 78, PY0 + 4 + oy, (60, 60, 80))


def screen_gemini(d, state, t, oy=0, sub=None, question=False, answer=0.0):
    R(d, SX0, SY0 + oy, SX1, SY1 + oy, (22, 24, 40))
    R(d, SX0, SY0 + oy, SX1, SY0 + 12 + oy, (36, 38, 64))
    sparkle(d, SX0 + 8, SY0 + 6 + oy, 4)
    text(d, SX0 + 15, SY0 + 1 + oy, "Gemini", F10, C["white"], None)
    mid = (SX0 + SX1) // 2
    if state == "load":
        a = t * 4
        sparkle(d, mid, 62 + oy, 11 + int(2 * math.sin(a)))
        text(d, mid, 84 + oy, "Загрузка" + "." * (int(t * 3) % 4), F10, C["tgray"], None, "mt", 0)
    elif state == "err":
        R(d, SX0 + 5, 36 + oy, SX1 - 5, 100 + oy, (70, 24, 36))
        R(d, SX0 + 5, 36 + oy, SX1 - 5, 37 + oy, C["red"]); R(d, SX0 + 5, 99 + oy, SX1 - 5, 100 + oy, C["red"])
        R(d, SX0 + 5, 36 + oy, SX0 + 6, 100 + oy, C["red"]); R(d, SX1 - 6, 36 + oy, SX1 - 5, 100 + oy, C["red"])
        R(d, mid - 6, 42 + oy, mid + 6, 54 + oy, C["red"])
        text(d, mid, 48 + oy, "!", F12, C["white"], None, "mm", 0)
        for i, ln in enumerate(sub):
            text(d, mid, 60 + i * 11 + oy, ln, F10, C["white"], None, "mt", 0)
    elif state == "chat":
        R(d, SX0 + 6, 32 + oy, SX1 - 6, 50 + oy, (50, 60, 120))
        text(d, SX0 + 9, 34 + oy, "Реши:", F10, C["tgray"], None, "lt", 0)
        text(d, SX0 + 9, 41 + oy, "x²+4x=21", F10, C["white"], None, "lt", 0)
        if answer > 0:
            R(d, SX0 + 6, 58 + oy, SX1 - 6, 100 + oy, (30, 90, 70))
            sparkle(d, SX0 + 13, 66 + oy, 4)
            full = ["x = 3", "или", "x = -7"]
            shown = int(answer * 14)
            s = "".join(full)
            lines, k = [], 0
            for ln in full:
                lines.append(ln[:max(0, shown - k)])
                k += len(ln)
            for i, ln in enumerate(lines):
                text(d, mid, 74 + i * 9 + oy, ln, F10, C["green"], None, "mt", 0)
            if answer >= 1:
                ck = SX1 - 14
                d.line([ck, 94 + oy, ck + 2, 96 + oy, ck + 6, 91 + oy], fill=C["green"], width=2)


def screen_vpn(d, kind, connected, t, press=0.0, oy=0):
    adam = kind == "adam"
    bg = (24, 20, 54) if adam else (50, 50, 56)
    R(d, SX0, SY0 + oy, SX1, SY1 + oy, bg)
    mid = (SX0 + SX1) // 2
    if adam:
        shield(d, mid, 40 + oy, 11, 12, True, F18)
        text(d, mid, 56 + oy, "АДАМ VPN", F12, C["green"], None, "mt", 0)
    else:
        R(d, mid - 11, 28 + oy, mid + 11, 50 + oy, C["gray"])
        text(d, mid, 39 + oy, "VPN", F12, C["black"], None, "mm", 0)
        text(d, mid, 56 + oy, "Обычный", F10, C["tgray"], None, "mt", 0)
    col_on = C["green"] if adam else (110, 190, 110)
    col = col_on if connected else (70, 70, 90)
    cy = 86 + oy + (1 if press > 0 else 0)
    R(d, mid - 14, cy - 14, mid + 14, cy + 14, C["black"])
    R(d, mid - 13, cy - 13, mid + 13, cy + 13, col)
    d.arc([mid - 7, cy - 7, mid + 7, cy + 7], 305, 235, fill=C["black"], width=2)
    d.line([mid, cy - 9, mid, cy - 1], fill=C["black"], width=2)
    text(d, mid, 104 + oy, "Подключено" if connected else "Нажми", F10, col_on if connected else C["tgray"],
         None, "mt", 0)


def finger(d, x, y):
    R(d, x, y, x + 5, y + 12, C["skin"]); R(d, x, y, x + 5, y, C["black"])
    R(d, x - 1, y + 1, x - 1, y + 12, C["black"]); R(d, x + 6, y + 1, x + 6, y + 12, C["black"])
    R(d, x - 4, y + 10, x + 10, y + 24, C["skin"])
    R(d, x - 5, y + 10, x - 5, y + 24, C["black"]); R(d, x + 11, y + 10, x + 11, y + 24, C["black"])


# ---------------------------------------------------------------- субтитры
def make_chunks(line, t0, dur):
    words = line.split()
    chunks, cur = [], []
    for w in words:
        if cur and (len(" ".join(cur + [w])) > 15 or len(cur) >= 3):
            chunks.append(cur); cur = []
        cur.append(w)
        if w[-1] in ".,!?:":
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    total = sum(len("".join(c)) + 2 for c in chunks)
    out, t = [], t0
    for c in chunks:
        dd = dur * (len("".join(c)) + 2) / total
        out.append((t, t + dd, c))
        t += dd
    return out


def draw_subs(d, words, t_in_chunk):
    s = " ".join(words).upper()
    y = 132
    pop = min(1.0, t_in_chunk / 0.08)
    f = F12
    wd = sum(f.getlength(w.upper()) for w in words) + f.getlength(" ") * (len(words) - 1)
    x = W / 2 - wd / 2
    yy = y + (0 if pop >= 1 else 2)
    for w in words:
        col = C["yellow"] if any(h in w.lower() for h in HILITE) else C["white"]
        text(d, x, yy, w.upper(), f, col, C["black"], "lt", 1)
        x += f.getlength(w.upper()) + f.getlength(" ")


# ---------------------------------------------------------------- рендер
def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def render(t, tl, subs):
    img = Image.new("RGB", (W, H), C["wall"])
    d = ImageDraw.Draw(img)
    name, s0, s1 = next((n, a, b) for n, a, b in tl if a <= t < b) if t < tl[-1][2] else tl[-1]
    u, dur = t - s0, s1 - s0
    p = u / dur
    shake = (0, 0)
    flash = None

    if name != "end":
        classroom(d, t, urgent=(name == "panic"))

    kid_expr = "smirk"
    paper = None
    teacher = None  # (cx, front, paper)
    panel = None    # callable drawing on screen
    panel_y = 0

    if name == "class":
        tx = -10 + 110 * ease(p * 1.1)
        teacher = (int(tx), True, p < 0.8)
        kid_expr = "smirk" if p < 0.6 else "worry"
        if p > 0.85:
            paper = "КР"
        if u < 1.4 and int(u * 5) % 2 == 0:
            pass
    elif name == "plan":
        teacher = (30, False, False)
        paper = "КР"
        kid_expr = "smirk"
    elif name == "err1":
        teacher = (30, False, False)
        paper = "КР"
        kid_expr = "worry" if p < 0.35 else "shock"
        panel = "gem1"
    elif name == "err2":
        teacher = (30, False, False)
        paper = "КР"
        kid_expr = "worry" if p < 0.55 else "shock"
        panel = "gem2"
    elif name == "panic":
        teacher = (30 + int(40 * ease(p * 1.5)), p > 0.15, False)
        paper = "КР"
        kid_expr = "shock"
    elif name == "adam":
        teacher = (30, False, False)
        paper = "КР"
        kid_expr = "worry" if p < 0.45 else "smirk"
        panel = "adam"
    elif name == "win":
        teacher = (30, False, False)
        paper = "5" if p > 0.3 else "КР"
        kid_expr = "happy"
        panel = "win"

    if name != "end":
        if teacher:
            draw_teacher(d, teacher[0], 76, teacher[1], t, teacher[2])
        # подсказка «!?» над учительницей
        if name == "panic" and p > 0.15:
            text(d, teacher[0] + 12, 62, "!?", F18, C["red"], C["white"], "mt", 1)
        draw_kid(d, 67, 150, kid_expr, t)
        # идея-пузырь
        if name == "plan" and u > 0.5:
            bx = 90 + int(2 * math.sin(t * 4))
            R(d, bx - 14, 96, bx + 14, 122, C["black"]); R(d, bx - 13, 97, bx + 13, 121, C["white"])
            sparkle(d, bx, 109, 8)
            R(d, 84, 125, 86, 127, C["white"]); R(d, 80, 147, 81, 148, C["white"])
        desk_front(d, paper, t)
        # телефон под партой (в руке) до открытия панели
        if name in ("plan", "class") and u > 0.3 and name == "plan":
            R(d, 62, 194, 72, 204, C["black"]); R(d, 63, 195, 71, 203, (60, 90, 200))

    # --- панель телефона
    if panel:
        if panel == "win":
            oy = int(120 * ease((p - 0.55) / 0.35)) if p > 0.55 else 0
        else:
            oy = int(130 * (1 - ease(u / 0.3)))
        phone_frame(d, oy)
        if panel == "gem1":
            if p < 0.35:
                screen_gemini(d, "load", t, oy)
            else:
                screen_gemini(d, "err", t, oy, ["Gemini", "недоступен", "в вашем", "регионе"])
                if p < 0.5:
                    shake = (int(2 * math.sin(t * 60)), 0)
        elif panel == "gem2":
            if p < 0.30:
                screen_vpn(d, "plain", p > 0.12 and p < 0.30 and False, t, 0, oy)
                if 0.1 < p < 0.30:
                    finger(d, 72, 80 + oy)
            elif p < 0.42:
                screen_vpn(d, "plain", True, t, 0, oy)
            elif p < 0.60:
                screen_gemini(d, "load", t, oy)
            else:
                screen_gemini(d, "err", t, oy, ["VPN", "обнаружен,", "доступ", "закрыт"])
                if p < 0.72:
                    shake = (int(2 * math.sin(t * 60)), 0)
        elif panel == "adam":
            if p < 0.30:
                screen_vpn(d, "adam", False, t, 0, oy)
                if p > 0.05:
                    fy = 130 - int(46 * ease((p - 0.05) / 0.2))
                    finger(d, 66, fy + oy)
            elif p < 0.62:
                screen_vpn(d, "adam", True, t, 1 if p < 0.36 else 0, oy)
                if p < 0.40:
                    finger(d, 66, 84 + oy)
            else:
                ans = max(0.0, min(1.0, (p - 0.70) / 0.2))
                screen_gemini(d, "chat", t, oy, None, True, ans)
        elif panel == "win":
            screen_gemini(d, "chat", t, oy, None, True, 1.0)
            if p < 0.5:
                pass

    # --- финальная карточка
    if name == "end":
        for yy in range(H):
            k = yy / H
            col = (int(30 + 40 * k), int(18 + 10 * k), int(70 + 60 * (1 - k)))
            d.line([0, yy, W, yy], fill=col)
        rnd = random.Random(7)
        for i in range(40):
            sx, sy = rnd.randint(0, W), rnd.randint(0, 200)
            if (int(t * 3) + i) % 3:
                R(d, sx, sy, sx + 1, sy + 1, C["white"])
        bob = int(2 * math.sin(t * 4))
        shield(d, 67, 52 + bob, 24, 28, True, F24 if False else ImageFont.truetype(FONT_PATH, 36))
        text(d, 67, 94, "АДАМ VPN", F18, C["green"], C["black"], "mt", 1)
        text(d, 67, 114, "работает, когда нужно", F10, C["white"], C["black"], "mt", 1)
        # кнопка
        blink = int(t * 3) % 2
        bx0, bx1, by0, by1 = 22, 113, 170, 192
        R(d, bx0, by0 + 2, bx1, by1 + 2, C["black"])
        R(d, bx0, by0, bx1, by1, C["green"] if blink else (40, 200, 120))
        R(d, bx0 + 2, by0 + 2, bx1 - 2, by0 + 3, (190, 255, 220))
        text(d, 67, 181, "СКАЧАТЬ", F18, C["black"], None, "mm", 0)
        text(d, 67, 200, "ссылка в профиле", F10, C["yellow"], C["black"], "mt", 1)
        # конфетти
        for i in range(36):
            cx = (i * 37 + 11) % W
            cy = int((t * 40 + i * 23) % 200)
            col = [C["red"], C["yellow"], C["blue"], C["green"], C["purple"]][i % 5]
            R(d, cx, cy, cx + 1, cy + 1, col)

    # --- субтитры
    cur = next(((a, b, w) for a, b, w in subs if a <= t < b), None)
    if cur:
        draw_subs(d, cur[2], t - cur[0])

    # --- хук: предупреждение
    if name == "class" and u < 1.6:
        if int(u * 6) % 2 == 0:
            R(d, 14, 84, 121, 104, C["black"]); R(d, 16, 86, 119, 102, C["red"])
            text(d, 67, 94, "КОНТРОЛЬНАЯ!", F12, C["white"], None, "mm", 0)
        flash = (C["red"], 0.18 if int(u * 6) % 2 == 0 else 0.0)
    if name == "panic":
        flash = (C["red"], 0.12 + 0.1 * math.sin(t * 14))
    if flash and flash[1] > 0:
        img = Image.blend(img, Image.new("RGB", (W, H), flash[0]), max(0.0, flash[1]))
    if shake != (0, 0):
        img = ImageChops.offset(img, shake[0], shake[1])
    return img


def main():
    paths, durs = synth_voice()
    gap = [0.4, 0.35, 0.35, 0.4, 0.3, 0.4, 0.4, 0.3]
    starts, t = [], 0.3
    for dd, g in zip(durs, gap):
        starts.append(t)
        t += dd + g
    total = round(t + 1.2, 2)
    # сцены: каждая начинается со своей реплики; первая — с нуля
    tl = []
    for i, ((_, _, scene), s) in enumerate(zip(LINES, starts)):
        a = 0.0 if i == 0 else starts[i] - 0.05
        b = total if i == len(LINES) - 1 else starts[i + 1] - 0.05
        tl.append((scene, a, b))
    subs = []
    for (line, _, _), s, dd in zip(LINES, starts, durs):
        subs += make_chunks(line, s, dd + 0.15)

    print("общая длительность: %.1f c" % total)
    for sc, a, b in tl:
        print(f"  {sc:6s} {a:5.2f} – {b:5.2f}")

    # --- аудио
    vox = np.zeros(int(total * SR) + SR)
    for pth, s in zip(paths, starts):
        put(vox, s, read_wav_mono(pth))
    vox = np.tanh(vox * 1.6) * 0.9
    music = make_music(total) * 0.55
    fx = np.zeros_like(music)
    sd = {n: (a, b) for n, a, b in tl}

    def at(name, frac):
        a, b = sd[name]
        return a + (b - a) * frac
    put(fx, 0.05, sfx_alarm()); put(fx, 0.4, sfx_alarm()); put(fx, 0.75, sfx_alarm())
    put(fx, at("plan", 0.0) + 0.3, sfx_idea())
    put(fx, at("err1", 0.0) + 0.05, sfx_blip())
    put(fx, at("err1", 0.35), sfx_error())
    put(fx, at("err2", 0.12), sfx_blip())
    put(fx, at("err2", 0.30), sfx_blip())
    put(fx, at("err2", 0.60), sfx_error())
    for k in range(6):
        put(fx, at("panic", 0.0) + k * 0.4, sfx_tick())
    put(fx, at("panic", 0.15), sfx_alarm())
    put(fx, at("adam", 0.30), sfx_blip())
    put(fx, at("adam", 0.40), sfx_up())
    put(fx, at("adam", 0.88), sfx_coin())
    put(fx, at("win", 0.0), sfx_fanfare())
    put(fx, at("end", 0.0) + 0.1, sfx_coin())
    # музыка тише под голосом
    env = np.ones_like(music)
    for pth, s in zip(paths, starts):
        n = len(read_wav_mono(pth))
        i0 = int(s * SR)
        env[i0:i0 + n] = 0.45
    mix = vox + music * env + fx * 0.8
    mix = mix / max(1.0, np.abs(mix).max() * 1.05)
    write_wav(os.path.join(HERE, "mix.wav"), mix[:int(total * SR)])
    write_wav(os.path.join(HERE, "voice.wav"), vox[:int(total * SR)])
    write_wav(os.path.join(HERE, "music.wav"), music[:int(total * SR)])

    # --- видео
    out = os.path.join(HERE, "adam_vpn_ad.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", os.path.join(HERE, "mix.wav"),
           "-vf", "scale=1080:1920:flags=neighbor", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17",
           "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-shortest", out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(total * FPS)
    for f in range(n):
        im = render(f / FPS, tl, subs)
        pr.stdin.write(im.tobytes())
        if "--preview" in sys.argv and f % 15 == 0:
            os.makedirs(os.path.join(HERE, "preview"), exist_ok=True)
            im.resize((W * 4, H * 4), Image.NEAREST).save(os.path.join(HERE, "preview", f"f{f:04d}.png"))
    pr.stdin.close()
    pr.wait()
    print("готово:", out)


if __name__ == "__main__":
    main()
