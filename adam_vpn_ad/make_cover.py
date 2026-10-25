#!/usr/bin/env python3
"""Обложка 1080x1920 для ролика (cover.png)."""
import os

from PIL import Image, ImageDraw, ImageFont

import make_video as mv

img = Image.new("RGB", (mv.W, mv.H), mv.C["wall"])
d = ImageDraw.Draw(img)
mv.classroom(d, 0.0)
mv.phone_frame(d)
mv.screen_gemini(d, "err", 0.0, 0, ["Gemini", "недоступен", "в вашем", "регионе"])
mv.draw_kid(d, 67, 150, "shock", 0.0)
mv.desk_front(d, "КР")
# заголовок
R = mv.R
R(d, 4, 126, 130, 148, mv.C["black"])
R(d, 6, 128, 128, 146, mv.C["red"])
mv.text(d, 67, 137, "КОНТРОЛЬНАЯ", mv.F18, mv.C["white"], mv.C["black"], "mm", 1)
# плашка-бренд
mv.shield(d, 120, 214, 9, 10, True, mv.F12)
mv.text(d, 107, 214, "АДАМ VPN", mv.F10, mv.C["green"], mv.C["black"], "rm", 1)
out = os.path.join(mv.HERE, "cover.png")
img.resize((1080, 1920), Image.NEAREST).save(out)
print(out)
