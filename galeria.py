"""
Añade los Shorts de esta noche a la web (rama `galeria`) y borra los de hace más de DIAS días.

Uso: python galeria.py <carpeta_salida> <carpeta_rama_galeria>
"""
import datetime as dt
import json
import pathlib
import shutil
import sys
from zoneinfo import ZoneInfo

DIAS = 30  # lo que se guarda en la web; GitHub Pages admite hasta 1 GB
ZONA = ZoneInfo("Europe/Madrid")


def main(salida, galeria):
    salida, galeria = pathlib.Path(salida), pathlib.Path(galeria)
    noches = galeria / "noches"
    noches.mkdir(parents=True, exist_ok=True)

    # 1. La noche de hoy
    meta = salida / "meta.json"
    fichas = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else []
    if fichas:
        ahora = dt.datetime.now(ZONA)
        carpeta = noches / ahora.strftime("%Y-%m-%d_%H%M")
        carpeta.mkdir(parents=True, exist_ok=True)
        for f in fichas:
            for clave in ("archivo", "portada"):
                if f.get(clave) and (salida / f[clave]).exists():
                    shutil.copy2(salida / f[clave], carpeta / f[clave])
        (carpeta / "meta.json").write_text(json.dumps(fichas, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. Limpieza de noches antiguas
    limite = (dt.datetime.now(ZONA) - dt.timedelta(days=DIAS)).strftime("%Y-%m-%d")
    for c in noches.iterdir():
        if c.is_dir() and c.name[:10] < limite:
            shutil.rmtree(c)

    # 3. Índice que lee la web
    indice = []
    for c in sorted((c for c in noches.iterdir() if c.is_dir()), reverse=True):
        m = c / "meta.json"
        if not m.exists():
            continue
        for f in json.loads(m.read_text(encoding="utf-8")):
            f["url"] = f"noches/{c.name}/{f['archivo']}"
            if f.get("portada"):
                f["portada"] = f"noches/{c.name}/{f['portada']}"
            f["noche"] = c.name
            indice.append(f)
    (galeria / "videos.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. La página
    shutil.copy2(pathlib.Path(__file__).parent / "web" / "index.html", galeria / "index.html")
    (galeria / ".nojekyll").touch()
    print(f"Galería: {len(indice)} Shorts en {len({f['noche'] for f in indice})} noches")


if __name__ == "__main__":
    main(*sys.argv[1:3])
