"""Editor de Soy Petra: arma un video terminado a partir de un trabajo JSON.

Uso:  python3 editar.py trabajo.json

El trabajo (ver ejemplo_trabajo.json) trae:
  segmentos   lista de {clip, inicio, dur}: tomas de Del Mar en orden (archivos ya descargados)
  voz         mp3 de la narración (voz IA de Del Mar o audio real)
  palabras    JSON de palabras con tiempos [{text, start, end}] (transcripción de la voz)
  gancho      {texto, t1}: texto grande arriba durante los primeros segundos ("\\N" = salto de línea)
  ocultar     [[t0, t1], ...] tramos con cifra gigante: ahí el subtítulo omite la cifra
  subs_fin    segundo desde el cual ya no hay subtítulos (antes de la tarjeta final)
  big, icons, cards, end   gráficos Postcard v4 (ver postcard.py): cifra contador con etiqueta,
              íconos 3D (icons3d/), tarjetas tipo app o notificación Petra, tarjeta final
  musica      mp3 de música con licencia; vol_musica (0.30 por defecto)
  salida      ruta del video final
  estilo      "v3" (por defecto) o "v2". v3: color cálido, zoom en cada corte, gancho en caja rosada,
              subtítulos palabra por palabra con la palabra activa en amarillo y efectos de sonido
Pasos: montaje 1080x1920 con corrección de HDR → efectos Postcard → subtítulos → mezcla
(voz + música con ducking) normalizada a -14 LUFS.
"""
import json, os, subprocess, sys, tempfile

KIT = os.path.dirname(os.path.abspath(__file__))
FONTS = KIT + "/fonts"
job = json.load(open(sys.argv[1]))
tmp = tempfile.mkdtemp(prefix="petra_")

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("Falló: " + " ".join(cmd[:6]) + "\n" + r.stderr[-1500:])
    return r.stdout

def transfer(path):
    return run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                "stream=color_transfer", "-of", "default=nw=1:nk=1", path]).strip().split("\n")[0].strip(",")

ESTILO = job.get("estilo", "v3")
CROP = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=saturation=1.08:contrast=1.03,fps=30,setsar=1"
if ESTILO == "v3":
    CROP = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1,"
            "eq=contrast=1.05:saturation=1.18:brightness=0.02:gamma_r=1.03:gamma_b=0.97")

def zoom(i, d):
    """v3: el primer plano entra con un golpe de zoom; los demás alternan acercar y alejar suave."""
    if ESTILO != "v3":
        return ""
    if i == 0:
        z = "(1+0.14*max(0,1-t/0.4))"
    elif i % 2:
        z = f"(1+0.07*t/{d})"
    else:
        z = f"(1.07-0.07*t/{d})"
    return (f",scale=w='trunc(1080*{z}/2)*2':h='trunc(1920*{z}/2)*2':eval=frame:flags=bicubic:in_range=tv:out_range=tv,crop=1080:1920,format=yuv420p")
TONE = "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"

# 1. Montaje
parts = []
for i, s in enumerate(job["segmentos"]):
    tr = transfer(s["clip"])
    pre = TONE if tr == "smpte2084" else (TONE.replace("zscale=t=linear", "zscale=tin=arib-std-b67:t=linear", 1) if tr == "arib-std-b67" else "")
    out = f"{tmp}/s{i:02d}.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["inicio"]), "-t", str(s["dur"]), "-i", s["clip"],
         "-vf", pre + CROP + zoom(i, s["dur"]) + ",setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv",
         "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv", out])
    parts.append(out)
with open(f"{tmp}/lista.txt", "w") as f:
    f.writelines(f"file '{p}'\n" for p in parts)
mont = f"{tmp}/montaje.mp4"
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/lista.txt", "-c", "copy", mont])
total = sum(s["dur"] for s in job["segmentos"])

# 2. Efectos Postcard
fx = mont
if job.get("big") or job.get("icons") or job.get("cards") or job.get("end"):
    fx = f"{tmp}/efectos.mp4"
    cfg = {"input": mont, "output": fx, "big": job.get("big", []), "icons": job.get("icons", []), "cards": job.get("cards", []), "end": job.get("end")}
    json.dump(cfg, open(f"{tmp}/pc.json", "w"))
    run([sys.executable, KIT + "/postcard.py", f"{tmp}/pc.json"])

# 3. Subtítulos (frases de máx. 3 palabras / 16 letras)
def ts(x):
    return f"{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}"
words = json.load(open(job["palabras"])) if job.get("palabras") else []
words = [w for w in words if w.get("type", "word") == "word" and w["text"].strip()]
hook = job.get("gancho")
ocultar = job.get("ocultar", [])
fin = job.get("subs_fin", total)
def es_cifra(t): return any(c.isdigit() for c in t)
# en los tramos de cifra gigante se quita la cifra del subtítulo (ya se ve grande)
words = [w for w in words if not (es_cifra(w["text"]) and any(a <= w["start"] < b for a, b in ocultar))]
con_etiqueta = [(b["t0"], b["t1"]) for b in job.get("big", []) if b.get("label")]  # la etiqueta ya dice la frase
words = [w for w in words if not any(a <= w["start"] < b for a, b in con_etiqueta)]
chunks, cur = [], []
for i, w in enumerate(words):
    cur.append(w)
    txt = " ".join(x["text"].strip() for x in cur)
    nxt = words[i + 1] if i + 1 < len(words) else None
    corte = nxt is None or nxt["start"] - w["end"] > 0.4
    if len(cur) >= 3 or w["text"].strip()[-1] in ".,?:!" or len(txt) > 16 or corte:
        chunks.append((cur[0]["start"], cur[-1]["end"], txt)); cur = []
ev = []
if hook:
    anim = "{\\fad(120,150)\\fscx70\\fscy70\\t(0,180,\\fscx104\\fscy104)\\t(180,260,\\fscx100\\fscy100)}" if ESTILO == "v3" else "{\\fad(150,150)}"
    ev.append(f"Dialogue: 0,{ts(0)},{ts(hook['t1'])},Hook,,0,0,0,,{anim}{hook['texto']}")
chunk_words, cur = [], []
for i, w in enumerate(words):
    cur.append(w)
    txt = " ".join(x["text"].strip() for x in cur)
    nxt = words[i + 1] if i + 1 < len(words) else None
    corte = nxt is None or nxt["start"] - w["end"] > 0.4
    if len(cur) >= 3 or w["text"].strip()[-1] in ".,?:!" or len(txt) > 16 or corte:
        chunk_words.append(cur); cur = []
for k, (a, b, txt) in enumerate(chunks):
    nxt = chunks[k + 1][0] if k + 1 < len(chunks) else b + 0.3
    b = max(b, min(nxt, b + 0.25))
    if hook and a < hook["t1"]: continue
    if a >= fin or txt.lower() in ("y", "o", "e", "a"): continue
    b = min(b, fin)
    if ESTILO != "v3":
        ev.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{txt}")
        continue
    cw = chunk_words[k]
    for j, w in enumerate(cw):
        w0 = a if j == 0 else w["start"]
        w1 = cw[j + 1]["start"] if j + 1 < len(cw) else b
        if w1 <= w0: continue
        partes = []
        for m, x in enumerate(cw):
            t = x["text"].strip()
            if m == j:
                pop = "{\\fscx100\\fscy100\\t(0,70,\\fscx114\\fscy114)\\t(70,150,\\fscx106\\fscy106)}" if m == j else ""
                partes.append("{\\c&H0000E6FF&}" + pop + t + "{\\c&H00FFFFFF&\\fscx100\\fscy100}")
            else:
                partes.append(t)
        entrada = "{\\fad(60,0)}" if j == 0 else ""
        ev.append(f"Dialogue: 0,{ts(w0)},{ts(w1)},Cap,,0,0,0,,{entrada}" + " ".join(partes))
ESTILOS_V2 = """Style: Cap,Poppins,120,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,10,3,2,70,70,520,1
Style: Hook,Poppins,175,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,14,4,8,60,60,230,1"""
# v3: subtítulo más grueso con sombra; gancho blanco sobre caja rosada Petra (#FF5C93)
ESTILOS_V3 = """Style: Cap,Poppins,128,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,11,5,2,60,60,520,1
Style: Hook,Poppins,150,&H00FFFFFF,&H00FFFFFF,&H00935CFF,&H00935CFF,-1,0,0,0,100,100,0,0,3,24,0,8,70,70,250,1"""
ass = f"{tmp}/subs.ass"
open(ass, "w").write("""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
""" + (ESTILOS_V3 if ESTILO == "v3" else ESTILOS_V2) + """

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(ev) + "\n")

# 4. Mezcla final
inputs = ["-i", fx]
fc = f"[0:v]subtitles={ass}:fontsdir={FONTS}[vv];"
if job.get("voz"):
    inputs += ["-i", job["voz"]]
    if job.get("musica"):
        inputs += ["-stream_loop", "-1", "-i", job["musica"]]
        vol = job.get("vol_musica", 0.30)
        fc += (f"[1:a]aresample=44100,apad=pad_dur=2,asplit=2[v][sc];"
               f"[2:a]aresample=44100,volume={vol},afade=t=in:d=0.5,afade=t=out:st={max(total - 1.2, 0)}:d=1.2[m];"
               "[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md];"
               "[v][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=7[a]")
    else:
        fc += "[1:a]aresample=44100,apad=pad_dur=2,loudnorm=I=-14:TP=-1.5:LRA=7[a]"
elif job.get("musica"):
    inputs += ["-stream_loop", "-1", "-i", job["musica"]]
    fc += f"[1:a]aresample=44100,afade=t=out:st={max(total - 1.2, 0)}:d=1.2,loudnorm=I=-14:TP=-1.5:LRA=7[a]"
else:
    fc += "anullsrc=r=44100:cl=stereo[a]"
if ESTILO == "v3" and "[a]" in fc and job.get("voz"):
    # efectos: whoosh en cada corte y pop en cada ícono / cifra
    cortes, acc = [], 0.0
    for s_ in job["segmentos"][:-1]:
        acc += s_["dur"]; cortes.append(acc)
    pops = [x["t0"] for x in job.get("icons", [])] + [x["t0"] for x in job.get("big", [])] + [x["t0"] + 0.7 for x in job.get("big", [])] + [x["t0"] for x in job.get("cards", [])]
    if job.get("end"): pops.append(job["end"]["t0"])
    sfx = [(KIT + "/sfx/whoosh.wav", max(c - 0.22, 0), 0.35) for c in cortes] + [(KIT + "/sfx/pop.wav", p, 0.5) for p in pops]
    base = len(inputs) // 2 if "-stream_loop" not in inputs else (len(inputs) - 2) // 2
    n0 = sum(1 for x in inputs if x == "-i")
    for f_, _, _ in sfx:
        inputs += ["-i", f_]
    fc = fc.replace(",loudnorm=I=-14:TP=-1.5:LRA=7[a]", "[pre]")
    lab = []
    for k_, (_, t_, v_) in enumerate(sfx):
        ms = int(t_ * 1000)
        fc += f";[{n0 + k_}:a]aresample=44100,volume={v_},adelay={ms}|{ms}[s{k_}]"
        lab.append(f"[s{k_}]")
    fc += f";[pre]{''.join(lab)}amix=inputs={len(lab) + 1}:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=7[a]"
run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[vv]", "-map", "[a]", "-t", f"{total:.2f}",
     "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
     "-movflags", "+faststart", job["salida"]])
print("Listo:", job["salida"], f"{total:.1f}s")
