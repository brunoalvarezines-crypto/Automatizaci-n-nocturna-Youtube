"""
Turno Nocturno - fabrica Shorts verticales a partir de guiones.

Entrada: JSON {"videos": [{"titulo", "descripcion", "etiquetas", "escenas": [{"texto", "busqueda"}]}]}
  - texto:    lo que dice la voz en esa escena (español)
  - busqueda: palabras clave EN INGLÉS para buscar el clip en Pexels

Por cada vídeo: voz (Azure) + clips verticales (Pexels) + subtítulos -> MP4 1080x1920,
y lo envía a Telegram con su título y descripción.
"""
import html
import json
import os
import pathlib
import subprocess
import sys
import traceback

import requests

W, H = 1080, 1920
SALIDA = pathlib.Path("salida")
CLIPS_RESERVA = ["person thinking", "city night", "people walking", "abstract light", "nature calm"]

VOZ = os.environ.get("VOZ", "es-ES-AlvaroNeural")
VELOCIDAD = os.environ.get("VELOCIDAD", "+8%")


# ---------- entrada ----------
def cargar_videos():
    raw = (os.environ.get("PAYLOAD") or "").strip()
    if not raw or raw == "null":
        raw = pathlib.Path("ejemplo.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, str):  # por si llega como texto doblemente codificado
        data = json.loads(data)
    videos = data["videos"]
    if isinstance(videos, str):  # Make a veces manda el array como texto
        videos = json.loads(videos)
    return videos


# ---------- utilidades ----------
def ff(*args, cwd=None):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True, cwd=cwd)


def duracion(ruta):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(ruta)]
    )
    return float(out)


# ---------- voz ----------
def tts(texto, destino):
    idioma = VOZ[:5]
    ssml = (
        f"<speak version='1.0' xml:lang='{idioma}'><voice name='{VOZ}'>"
        f"<prosody rate='{VELOCIDAD}'>{html.escape(texto)}</prosody></voice></speak>"
    )
    r = requests.post(
        f"https://{os.environ['AZURE_SPEECH_REGION']}.tts.speech.microsoft.com/cognitiveservices/v1",
        headers={
            "Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"],
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
            "User-Agent": "turno-nocturno",
        },
        data=ssml.encode("utf-8"),
        timeout=60,
    )
    r.raise_for_status()
    destino.write_bytes(r.content)


# ---------- clips ----------
_usados = set()


def buscar_clip(consulta, destino):
    for q in [consulta, *CLIPS_RESERVA]:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": os.environ["PEXELS_API_KEY"]},
            params={"query": q, "orientation": "portrait", "per_page": 15},
            timeout=30,
        )
        r.raise_for_status()
        for v in r.json().get("videos", []):
            if v["id"] in _usados:
                continue
            files = [
                f for f in v.get("video_files", [])
                if f.get("width") and f.get("height") and f["height"] >= f["width"] and f["height"] >= 1280
            ]
            if not files:
                continue
            elegido = min(files, key=lambda f: abs(f["height"] - 1920))
            _usados.add(v["id"])
            with requests.get(elegido["link"], stream=True, timeout=180) as d:
                d.raise_for_status()
                with open(destino, "wb") as fh:
                    for trozo in d.iter_content(1 << 20):
                        fh.write(trozo)
            return
    raise RuntimeError(f"No encontré clip vertical para: {consulta}")


# ---------- subtítulos ----------
def _t(seg):
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def subtitulos_ass(escenas_con_tiempo, destino, palabras_por_linea=4):
    cab = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Base,DejaVu Sans,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        "-1,0,0,0,100,100,0,0,1,7,2,2,80,80,620,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lineas = []
    for texto, inicio, dur in escenas_con_tiempo:
        palabras = texto.split()
        grupos = [" ".join(palabras[i:i + palabras_por_linea]) for i in range(0, len(palabras), palabras_por_linea)]
        total = sum(len(g) for g in grupos) or 1
        t = inicio
        for g in grupos:
            d = dur * len(g) / total
            lineas.append(f"Dialogue: 0,{_t(t)},{_t(t + d)},Base,,0,0,0,,{g.replace('{', '(').replace('}', ')')}")
            t += d
    destino.write_text(cab + "\n".join(lineas) + "\n", encoding="utf-8")


# ---------- montaje ----------
def fabricar(video, n):
    carpeta = SALIDA / f"v{n}"
    carpeta.mkdir(parents=True, exist_ok=True)
    escenas = video["escenas"]
    segmentos, audios, tiempos = [], [], []
    t = 0.0
    for i, esc in enumerate(escenas):
        audio = carpeta / f"a{i}.mp3"
        clip = carpeta / f"c{i}.mp4"
        seg = carpeta / f"s{i}.mp4"
        tts(esc["texto"], audio)
        d = duracion(audio) + 0.15
        buscar_clip(esc.get("busqueda") or "person thinking", clip)
        ff("-stream_loop", "-1", "-i", str(clip), "-t", f"{d:.3f}",
           "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps=30",
           "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(seg))
        # el audio se alarga con el mismo silencio final para que no se desincronice
        ff("-i", str(audio), "-af", "apad=pad_dur=0.15", "-t", f"{d:.3f}", "-ar", "48000", "-ac", "2",
           str(carpeta / f"a{i}.wav"))
        segmentos.append(f"s{i}.mp4")
        audios.append(f"a{i}.wav")
        tiempos.append((esc["texto"], t, d))
        t += d

    (carpeta / "videos.txt").write_text("".join(f"file '{s}'\n" for s in segmentos))
    (carpeta / "audios.txt").write_text("".join(f"file '{a}'\n" for a in audios))
    ff("-f", "concat", "-safe", "0", "-i", "videos.txt", "-c", "copy", "imagen.mp4", cwd=carpeta)
    ff("-f", "concat", "-safe", "0", "-i", "audios.txt", "-c:a", "aac", "-b:a", "160k", "voz.m4a", cwd=carpeta)
    subtitulos_ass(tiempos, carpeta / "subs.ass")
    final = SALIDA / f"short_{n}.mp4"
    ff("-i", "imagen.mp4", "-i", "voz.m4a", "-vf", "ass=subs.ass",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
       "-c:a", "copy", "-shortest", "-movflags", "+faststart", f"../{final.name}", cwd=carpeta)
    return final, t


# ---------- telegram ----------
def tg(metodo, **kw):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", data={"chat_id": chat, **kw.pop("data", {})},
                      timeout=300, **kw)
    r.raise_for_status()


def enviar(video, ruta, seg, n):
    titulo = video.get("titulo", f"Short {n}")
    with open(ruta, "rb") as fh:
        tg("sendVideo", data={"caption": f"🎬 {n}. {titulo} ({seg:.0f} s)"[:1000], "supports_streaming": "true"},
           files={"video": fh})
    etiquetas = " ".join("#" + e.lstrip("#").replace(" ", "") for e in video.get("etiquetas", []))
    texto = f"TÍTULO:\n{titulo}\n\nDESCRIPCIÓN:\n{video.get('descripcion', '')}\n\n{etiquetas}".strip()
    tg("sendMessage", data={"text": texto[:4000]})


def main():
    SALIDA.mkdir(exist_ok=True)
    videos = cargar_videos()
    fallos = 0
    for n, video in enumerate(videos, 1):
        try:
            ruta, seg = fabricar(video, n)
            print(f"OK {ruta} ({seg:.1f} s)")
            enviar(video, ruta, seg, n)
        except Exception as e:  # un vídeo roto no para a los demás
            fallos += 1
            traceback.print_exc()
            try:
                tg("sendMessage", data={"text": f"⚠️ El Short {n} falló: {e}"[:4000]})
            except Exception:
                pass
    hechos = len(videos) - fallos
    try:
        tg("sendMessage", data={"text": f"🌙 Turno nocturno terminado: {hechos} de {len(videos)} Shorts listos."})
    except Exception:
        pass
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
