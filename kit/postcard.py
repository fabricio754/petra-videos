"""Plantilla «Petra Postcard»: cifras detrás de la persona, íconos que aparecen con palabras clave
y tarjeta final tipo notificación. Lee un video 1080x1920 sin audio y escribe otro con los gráficos."""
import json, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from rembg import new_session, remove

W, H, FPS = 1080, 1920, 30
import os
KIT = os.path.dirname(os.path.abspath(__file__))
F = KIT + "/fonts/"
cfg = json.load(open(sys.argv[1]))
src, out = cfg["input"], cfg["output"]
session = new_session("u2net_human_seg")
icons = {os.path.splitext(n)[0]: Image.open(f"{KIT}/icons/{n}").convert("RGBA") for n in os.listdir(KIT + "/icons")}

def ease(x): x = max(0, min(1, x)); return 1 - (1 - x) ** 3

def big_text_layer(text, t0, t, color, ypos=0.17, base=330):
    """Capa con la cifra gigante, entra con escala."""
    k = ease((t - t0) / 0.35)
    size = int(base * (0.75 + 0.25 * k))
    font = ImageFont.truetype(F + "Poppins-Bold.ttf", size)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    bb = d.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    if tw > W - 40:  # que quepa
        font = ImageFont.truetype(F + "Poppins-Bold.ttf", int(size * (W - 40) / tw))
        bb = d.textbbox((0, 0), text, font=font); tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x, y = (W - tw) // 2 - bb[0], int(H * ypos) - bb[1]
    d.text((x, y), text, font=font, fill=color + (int(255 * k),))
    return lay

def icon_layer(name, t0, t1, t, side="right"):
    if t < t0 or t > t1: return None
    a_in, a_out = ease((t - t0) / 0.25), ease((t1 - t) / 0.2)
    a = min(a_in, a_out)
    sc = 0.6 + 0.4 * a_in
    ic = icons[name].resize((int(300 * sc), int(300 * sc)), Image.LANCZOS)
    alpha = ic.getchannel("A").point(lambda p: int(p * a)); ic.putalpha(alpha)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cx = {"left": 230, "right": W - 230, "center": W // 2}[side]
    lay.alpha_composite(ic, (cx - ic.width // 2, int(H * 0.37) - ic.height // 2))
    return lay

def end_card(t0, t, title, sub):
    k = ease((t - t0) / 0.4)
    cw, ch = 760, 150
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=75, fill=(30, 30, 38, 225))
    d.ellipse((22, 25, 122, 125), fill=(255, 92, 147, 255))
    hi = icons["heart"].resize((60, 60)); hi = Image.eval(hi, lambda p: p)
    white = Image.new("RGBA", hi.size, (255, 255, 255, 255)); white.putalpha(hi.getchannel("A"))
    card.alpha_composite(white, (42, 45))
    d.text((150, 30), title, font=ImageFont.truetype(F + "Poppins-Bold.ttf", 46), fill=(255, 255, 255, 255))
    d.text((150, 84), sub, font=ImageFont.truetype(F + "Poppins-Regular.ttf", 34), fill=(210, 210, 220, 255))
    d.ellipse((cw - 125, 25, cw - 25, 125), fill=(46, 204, 113, 255))
    si = icons["send"].resize((56, 56)); w2 = Image.new("RGBA", si.size, (255, 255, 255, 255)); w2.putalpha(si.getchannel("A"))
    card.alpha_composite(w2, (cw - 103, 47))
    card.putalpha(card.getchannel("A").point(lambda p: int(p * k)))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = int(H * 0.66 + (1 - k) * 120)
    lay.alpha_composite(card, ((W - cw) // 2, y))
    return lay

dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                        "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
i, last_mask, last_mask_i = 0, None, -99
while True:
    raw = dec.stdout.read(W * H * 3)
    if len(raw) < W * H * 3: break
    t = i / FPS
    fr = Image.frombytes("RGB", (W, H), raw).convert("RGBA")
    for b in cfg.get("big", []):
        if b["t0"] <= t <= b["t1"]:
            if i - last_mask_i >= 2 or last_mask is None:  # máscara cada 2 cuadros
                last_mask = remove(fr.convert("RGB").resize((540, 960)), session=session, only_mask=True).resize((W, H)).filter(ImageFilter.GaussianBlur(2))
                last_mask_i = i
            person = fr.copy(); person.putalpha(last_mask)
            base = fr.copy(); base.alpha_composite(big_text_layer(b["text"], b["t0"], t, tuple(b.get("color", [108, 76, 245])), b.get("y", 0.17), b.get("size", 330)))
            base.alpha_composite(person); fr = base
    for ic in cfg.get("icons", []):
        lay = icon_layer(ic["name"], ic["t0"], ic["t1"], t, ic.get("side", "right"))
        if lay: fr.alpha_composite(lay)
    ec = cfg.get("end")
    if ec and t >= ec["t0"]: fr.alpha_composite(end_card(ec["t0"], t, ec["title"], ec["sub"]))
    enc.stdin.write(fr.convert("RGB").tobytes()); i += 1
enc.stdin.close(); enc.wait(); print("frames", i)
