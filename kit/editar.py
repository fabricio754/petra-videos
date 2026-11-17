"""Editor de Soy Petra: arma un video terminado a partir de un trabajo JSON.

Uso:  python3 editar.py trabajo.json

El trabajo (ver ejemplo_trabajo.json) trae:
  segmentos   lista de {clip, inicio, dur}: tomas de Del Mar en orden (archivos ya descargados)
  voz         mp3 de la narración (voz IA de Del Mar o audio real)
  palabras    JSON de palabras con tiempos [{text, start, end}] (transcripción de la voz)
  gancho      {texto, t1}: texto grande arriba durante los primeros segundos ("\\N" = salto de línea)
  ocultar     [[t0, t1], ...] tramos con cifra gigante: ahí el subtítulo omite la cifra
  subs_fin    segundo desde el cual ya no hay subtítulos (antes de la tarjeta final)
  big, icons, end   efectos de la plantilla Postcard (ver postcard.py)
  musica      mp3 de música con licencia; vol_musica (0.30 por defecto)
  salida      ruta del video final
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
                "stream=color_transfer", "-of", "csv=p=0", path]).strip()

CROP = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=saturation=1.08:contrast=1.03,fps=30,setsar=1"
TONE = "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"

# 1. Montaje
parts = []
for i, s in enumerate(job["segmentos"]):
    tr = transfer(s["clip"])
    pre = TONE if tr == "smpte2084" else ("zscale=tin=arib-std-b67:" + TONE if tr == "arib-std-b67" else "")
    out = f"{tmp}/s{i:02d}.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["inicio"]), "-t", str(s["dur"]), "-i", s["clip"],
         "-vf", pre + CROP, "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", out])
    parts.append(out)
with open(f"{tmp}/lista.txt", "w") as f:
    f.writelines(f"file '{p}'\n" for p in parts)
mont = f"{tmp}/montaje.mp4"
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/lista.txt", "-c", "copy", mont])
total = sum(s["dur"] for s in job["segmentos"])

# 2. Efectos Postcard
fx = mont
if job.get("big") or job.get("icons") or job.get("end"):
    fx = f"{tmp}/efectos.mp4"
    cfg = {"input": mont, "output": fx, "big": job.get("big", []), "icons": job.get("icons", []), "end": job.get("end")}
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
    ev.append(f"Dialogue: 0,{ts(0)},{ts(hook['t1'])},Hook,,0,0,0,,{{\\fad(150,150)}}{hook['texto']}")
for k, (a, b, txt) in enumerate(chunks):
    nxt = chunks[k + 1][0] if k + 1 < len(chunks) else b + 0.3
    b = max(b, min(nxt, b + 0.25))
    if hook and a < hook["t1"]: continue
    if a >= fin or txt.lower() in ("y", "o", "e", "a"): continue
    ev.append(f"Dialogue: 0,{ts(a)},{ts(min(b, fin))},Cap,,0,0,0,,{txt}")
ass = f"{tmp}/subs.ass"
open(ass, "w").write("""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Poppins,120,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,10,3,2,70,70,520,1
Style: Hook,Poppins,175,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,14,4,8,60,60,230,1

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
run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[vv]", "-map", "[a]", "-t", f"{total:.2f}",
     "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
     "-movflags", "+faststart", job["salida"]])
print("Listo:", job["salida"], f"{total:.1f}s")
