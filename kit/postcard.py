"""Plantilla «Petra Postcard» v4: cifras contador detrás de la persona, íconos 3D con rebote,
tarjetas tipo app y tarjeta final. Lee un video 1080x1920 sin audio y escribe otro con los gráficos.

Claves del trabajo:
  big:   [{text:"$50.000", t0, t1, y, size, label:"por cada visita"}]  la cifra cuenta desde 0
  icons: [{name, t0, t1, side:left|right|center}]   usa icons3d/<name>.png (si no existe, icons/)
  cards: [{t0, t1, icon, title, sub, estilo:"app"|"notif", y}]  tarjetas tipo app / notificación Petra
  end:   {t0, title, sub}
"""
import json, os, re, subprocess, sys, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from rembg import new_session, remove

W, H, FPS = 1080, 1920, 30
KIT = os.path.dirname(os.path.abspath(__file__))
F = KIT + "/fonts/"
ROSA, ROSA_OSC, VERDE = (255, 92, 147), (190, 30, 95), (46, 204, 113)
cfg = json.load(open(sys.argv[1]))
src, out = cfg["input"], cfg["output"]
session = new_session("u2net_human_seg") if cfg.get("big") else None

def font(name, size):
    p = F + f"Poppins-{name}.ttf"
    return ImageFont.truetype(p if os.path.exists(p) else F + "Poppins-Bold.ttf", size)

def load_icons(d):
    p = f"{KIT}/{d}"
    return {os.path.splitext(n)[0]: Image.open(f"{p}/{n}").convert("RGBA") for n in os.listdir(p)} if os.path.isdir(p) else {}
ICON2D, ICON3D = load_icons("icons"), load_icons("icons3d")
def icon(name):
    return ICON3D.get(name) or ICON2D.get(name) or ICON3D["sparkles"]

def clamp(x): return max(0.0, min(1.0, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def back(x, s=1.9):  # entra pasándose un poco y vuelve (rebote)
    x = clamp(x); x -= 1; return x * x * ((s + 1) * x + s) + 1

def shadow(img, r=18, off=(0, 14), a=0.45):
    """Devuelve img con sombra suave debajo (lienzo más grande)."""
    pad = r * 3
    can = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 255)); sh.putalpha(img.getchannel("A").point(lambda p: int(p * a)))
    can.alpha_composite(sh, (pad + off[0], pad + off[1])); can = can.filter(ImageFilter.GaussianBlur(r))
    can.alpha_composite(img, (pad, pad)); return can, pad

def fade(img, a):
    if a >= 1: return img
    img = img.copy(); img.putalpha(img.getchannel("A").point(lambda p: int(p * a))); return img

# ---------- cifra contador ----------
def fmt_count(text, k):
    m = re.search(r"\d[\d\.]*", text)
    if not m: return text
    val = int(m.group().replace(".", ""))
    cur = int(round(val * k / 1000.0)) * 1000 if val >= 10000 else int(round(val * k))
    s = f"{cur:,}".replace(",", ".")
    return text[:m.start()] + s + text[m.end():]

def big_layer(b, t):
    t0, t1 = b["t0"], b["t1"]
    kc = ease((t - t0) / 0.7)                       # conteo 0.7 s
    pop = 1 + 0.10 * math.sin(math.pi * clamp((t - t0 - 0.7) / 0.22))  # golpe al terminar
    ins = back((t - t0) / 0.35)
    out_a = ease((t1 - t) / 0.18)
    txt = fmt_count(b["text"], kc)
    size = int(b.get("size", 300) * (0.7 + 0.3 * ins) * pop)
    f = font("Black", size)
    full = font("Black", b.get("size", 300)); fw = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), b["text"], font=full)
    if fw[2] - fw[0] > W - 150: f = font("Black", int(size * (W - 150) / (fw[2] - fw[0])))
    d0 = ImageDraw.Draw(Image.new("L", (1, 1))); bb = d0.textbbox((0, 0), txt, font=f, stroke_width=0)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    depth = max(6, size // 22)
    can = Image.new("RGBA", (tw + 80, th + 80 + depth), (0, 0, 0, 0)); d = ImageDraw.Draw(can)
    ox, oy = 40 - bb[0], 40 - bb[1]
    for i in range(depth, 0, -1):                   # volumen rosado oscuro
        d.text((ox, oy + i), txt, font=f, fill=ROSA_OSC + (255,))
    face = Image.new("RGBA", can.size, (0, 0, 0, 0)); ImageDraw.Draw(face).text((ox, oy), txt, font=f, fill=(255, 255, 255, 255))
    grad = Image.new("RGBA", can.size)               # degradado blanco → rosa claro
    gd = ImageDraw.Draw(grad)
    for y in range(can.height):
        k = clamp((y - oy) / max(1, th)); gd.line([(0, y), (can.width, y)], fill=(255, int(255 - 45 * k), int(255 - 25 * k), 255))
    grad.putalpha(face.getchannel("A")); can.alpha_composite(grad)
    can, pad = shadow(can, r=22, off=(0, 18), a=0.5)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = int(H * b.get("y", 0.05))
    lay.alpha_composite(fade(can, out_a), ((W - can.width) // 2, y - pad - 40))
    front = None
    if b.get("label"):
        la = ease((t - t0 - 0.6) / 0.3) * out_a
        if la > 0:
            p = pill(b["label"], 50)
            front = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fs = b.get("size", 300) * 0.80
            front.alpha_composite(fade(p, la), ((W - p.width) // 2, y + int(fs) + int((1 - la) * 30)))
    return lay, front

def pill(text, size):
    f = font("ExtraBold", size); bb = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f)
    w, h = bb[2] - bb[0] + 70, bb[3] - bb[1] + 44
    p = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(p)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=ROSA + (255,))
    d.text((35 - bb[0], 22 - bb[1]), text, font=f, fill=(255, 255, 255, 255))
    return shadow(p, r=12, off=(0, 8), a=0.35)[0]

# ---------- íconos 3D ----------
_icache = {}
def icon_layer(ic, t):
    t0, t1 = ic["t0"], ic["t1"]
    if t < t0 or t > t1: return None
    s_in, a_out = back((t - t0) / 0.32), ease((t1 - t) / 0.18)
    bob = math.sin((t - t0) * 4.0) * 10
    rot = math.sin((t - t0) * 3.0) * 4
    key = ic["name"]
    if key not in _icache: _icache[key] = shadow(icon(key).resize((340, 340), Image.LANCZOS), r=16, off=(0, 18), a=0.4)[0]
    base = _icache[key]
    sc = max(0.05, s_in * (0.9 + 0.1 * a_out))
    im = base.resize((max(2, int(base.width * sc)), max(2, int(base.height * sc))), Image.BICUBIC).rotate(rot, Image.BICUBIC, expand=True)
    im = fade(im, a_out)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cx = {"left": 240, "right": W - 240, "center": W // 2}[ic.get("side", "right")]
    lay.alpha_composite(im, (cx - im.width // 2, int(H * ic.get("y", 0.36) + bob) - im.height // 2))
    return lay

# ---------- tarjetas tipo app ----------
_ccache = {}
def make_card(c):
    estilo = c.get("estilo", "app")
    title, sub = c.get("title", ""), c.get("sub", "")
    if estilo == "notif":
        cw, ch = 900, 210
        card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); d = ImageDraw.Draw(card)
        d.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=46, fill=(250, 250, 252, 245))
        d.rounded_rectangle((30, 30, 80, 80), radius=14, fill=ROSA + (255,))
        d.text((44, 33), "P", font=font("Black", 36), fill=(255, 255, 255, 255))
        d.text((96, 36), "PETRA", font=font("SemiBold", 28), fill=(120, 120, 130, 255))
        d.text((cw - 110, 36), "ahora", font=font("Regular", 28), fill=(140, 140, 150, 255))
        d.text((30, 96), title, font=font("Bold", 44), fill=(25, 25, 30, 255))
        d.text((30, 150), sub, font=font("Regular", 34), fill=(70, 70, 80, 255))
        ic = c.get("icon")
        if ic:
            i3 = icon(ic).resize((120, 120), Image.LANCZOS); card.alpha_composite(i3, (cw - 150, 78))
    else:
        tf, sf = font("Bold", 50), font("Medium", 36)
        d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
        tw = max(d0.textlength(title, font=tf), d0.textlength(sub, font=sf))
        cw, ch = int(min(980, 200 + tw + 60)), 170
        card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); d = ImageDraw.Draw(card)
        d.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=ch // 2, fill=(28, 28, 36, 235))
        d.ellipse((20, 20, 150, 150), fill=(255, 255, 255, 255))
        i3 = icon(c.get("icon", "sparkles")).resize((96, 96), Image.LANCZOS); card.alpha_composite(i3, (37, 37))
        d.text((175, 30 if sub else 55), title, font=tf, fill=(255, 255, 255, 255))
        if sub: d.text((176, 92), sub, font=sf, fill=(255, 170, 200, 255))
    return shadow(card, r=20, off=(0, 16), a=0.45)[0]

def card_layer(c, t):
    t0, t1 = c["t0"], c["t1"]
    if t < t0 or t > t1: return None
    k = back((t - t0) / 0.4, 1.4); a_out = ease((t1 - t) / 0.2)
    key = json.dumps(c, sort_keys=True)
    if key not in _ccache: _ccache[key] = make_card(c)
    im = _ccache[key]
    estilo = c.get("estilo", "app")
    y_fin = int(H * c.get("y", 0.21 if estilo == "notif" else 0.42))
    y = int(y_fin + (1 - k) * (-260 if estilo == "notif" else 200))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lay.alpha_composite(fade(im, min(clamp(k * 1.5), a_out)), ((W - im.width) // 2, y))
    return lay

def end_card(t0, t, title, sub):
    k = back((t - t0) / 0.45, 1.3)
    cw, ch = 760, 150
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=75, fill=(30, 30, 38, 230))
    d.ellipse((22, 25, 122, 125), fill=ROSA + (255,))
    hi = ICON2D["heart"].resize((60, 60)); white = Image.new("RGBA", hi.size, (255, 255, 255, 255)); white.putalpha(hi.getchannel("A"))
    card.alpha_composite(white, (42, 45))
    d.text((150, 30), title, font=font("Bold", 46), fill=(255, 255, 255, 255))
    d.text((150, 84), sub, font=font("Regular", 34), fill=(210, 210, 220, 255))
    d.ellipse((cw - 125, 25, cw - 25, 125), fill=VERDE + (255,))
    si = ICON2D["send"].resize((56, 56)); w2 = Image.new("RGBA", si.size, (255, 255, 255, 255)); w2.putalpha(si.getchannel("A"))
    card.alpha_composite(w2, (cw - 103, 47))
    card, pad = shadow(card, r=18, off=(0, 14), a=0.45)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = int(H * 0.66 + (1 - k) * 140) - pad
    lay.alpha_composite(fade(card, clamp(k * 1.5)), ((W - card.width) // 2, y))
    return lay

dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                        "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", out], stdin=subprocess.PIPE)
i, last_mask, last_mask_i = 0, None, -99
while True:
    raw = dec.stdout.read(W * H * 3)
    if len(raw) < W * H * 3: break
    t = i / FPS
    fr = Image.frombytes("RGB", (W, H), raw).convert("RGBA")
    for b in cfg.get("big", []):
        if b["t0"] <= t <= b["t1"]:
            if i - last_mask_i >= 2 or last_mask is None:
                last_mask = remove(fr.convert("RGB").resize((540, 960)), session=session, only_mask=True).resize((W, H)).filter(ImageFilter.GaussianBlur(2))
                last_mask_i = i
            person = fr.copy(); person.putalpha(last_mask)
            back_l, front_l = big_layer(b, t)
            base = fr.copy(); base.alpha_composite(back_l); base.alpha_composite(person)
            if front_l: base.alpha_composite(front_l)
            fr = base
    for ic in cfg.get("icons", []):
        lay = icon_layer(ic, t)
        if lay: fr.alpha_composite(lay)
    for c in cfg.get("cards", []):
        lay = card_layer(c, t)
        if lay: fr.alpha_composite(lay)
    ec = cfg.get("end")
    if ec and t >= ec["t0"]: fr.alpha_composite(end_card(ec["t0"], t, ec["title"], ec["sub"]))
    enc.stdin.write(fr.convert("RGB").tobytes()); i += 1
enc.stdin.close(); enc.wait(); print("frames", i)
