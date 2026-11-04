"""Fase 10 (E10.3, v2): comprueba DENTRO de una imagen que no lleva datos, secretos ni estado (solo biblioteca
estandar). Lo usa el job `imagenes` y la verificacion local con el mismo comando:

    docker run --rm -i --network none --entrypoint python <imagen> -B - < despliegue/imagenes/comprobar_contenido_imagen.py

(Con un argumento, recorre esa carpeta como si fuera `/`: solo para las pruebas unitarias.)

Falla (codigo 1) si encuentra:
- el proceso ejecutandose como root;
- archivos de datos o secretos por nombre: `.env`, `*.env` privados, `*.privado.*`, SQLite (`.sqlite`,
  `.sqlite3`, `.db`), almacenes PKCS#12 (`.pfx`, `.p12`), repositorios (`.git`);
- claves privadas PEM (bloque completo con cuerpo) fuera de los certificados publicos del sistema, y archivos
  o carpetas ilegibles para el usuario de la imagen en zonas de aplicacion o de usuario (no se pueden
  inspeccionar, no se dan por limpios);
- carpetas de DATOS de la aplicacion: `/srv/pub`, `/srv/backend/storage`, `/srv/backend/privado` o cualquier
  `storage`/`privado` fuera del codigo (`/srv/backend/app`) y del entorno virtual (`/opt/venv`);
- dentro del codigo, un paquete `storage`/`privado` con algo que no sea codigo Python (`.py`, `__pycache__`):
  `app/infrastructure/storage/` es el paquete legitimo que IMPLEMENTA los almacenes y se admite como codigo.
No excluye globalmente ninguna ruta llamada `storage`. Imprime un JSON con lo encontrado (sin contenidos).
"""
import json
import os
import re
import sys

OMITIR = ("/proc", "/sys", "/dev")
CODIGO = ("/srv/backend/app/", "/opt/venv/")
DATOS = ("/srv/pub", "/srv/backend/storage", "/srv/backend/privado")
ZONAS_INSPECCIONABLES = ("/srv/", "/opt/", "/home/", "/tmp/", "/var/tmp/", "/app/", "/data/")
CERTIFICADOS_DEL_SISTEMA = ("/usr/share/ca-certificates/", "/etc/ssl/certs/")
EXTENSIONES = (".sqlite", ".sqlite3", ".db", ".pfx", ".p12")
CARPETAS_DE_DATOS = ("storage", "privado")
MAXIMO_LECTURA = 1 << 20
# Un bloque PEM completo (cabecera, cuerpo base64 y pie): la cadena de la cabecera sola, como la que contiene el
# codigo de `cryptography`, no es una clave.
_PEM = re.compile(rb"-----BEGIN ([A-Z0-9 ]*)PRIVATE KEY-----\r?\n(?:[A-Za-z0-9+/=:, -]*\r?\n)*?"
                  rb"[A-Za-z0-9+/=\r\n]{64,}-----END \1PRIVATE KEY-----")


def prohibido_por_nombre(nombre: str) -> bool:
    bajo = nombre.lower()
    return (bajo == ".env" or bajo.endswith(".env") or ".privado." in bajo or bajo.endswith(EXTENSIONES)
            or bajo == ".git")


def clave_privada(ruta: str) -> bool:
    try:
        if os.path.getsize(ruta) > MAXIMO_LECTURA:
            return False
        with open(ruta, "rb") as f:
            return _PEM.search(f.read()) is not None
    except OSError:
        return False


def revisar(raiz: str = "/", uid=None) -> list:
    """Hallazgos `(motivo, ruta)` con rutas de la imagen; `raiz` real solo cambia en las pruebas."""
    raiz = os.path.abspath(raiz)

    def imagen(real: str) -> str:
        rel = os.path.relpath(real, raiz)
        return "/" if rel == "." else "/" + rel.replace(os.sep, "/")

    hallazgos = set()
    if uid == 0:
        hallazgos.add(("se_ejecuta_como_root", "uid=0"))
    for actual, carpetas, archivos in os.walk(raiz, followlinks=False):
        carpetas[:] = [c for c in carpetas if imagen(os.path.join(actual, c)) not in OMITIR]
        for c in carpetas:
            real = os.path.join(actual, c)
            ruta = imagen(real)
            if ruta.startswith(ZONAS_INSPECCIONABLES) and not os.access(real, os.R_OK | os.X_OK):
                hallazgos.add(("carpeta_ilegible_no_inspeccionada", ruta))
            if prohibido_por_nombre(c):
                hallazgos.add(("carpeta_prohibida", ruta))
            if ruta in DATOS:
                hallazgos.add(("carpeta_de_datos", ruta))
            elif c.lower() in CARPETAS_DE_DATOS:
                if not (ruta + "/").startswith(CODIGO):
                    hallazgos.add(("carpeta_de_datos_fuera_del_codigo", ruta))
                elif ruta.startswith("/srv/backend/app/"):
                    for sub, sub_carpetas, sub_archivos in os.walk(real):
                        sub_carpetas[:] = [s for s in sub_carpetas if s != "__pycache__"]
                        for a in sub_archivos:
                            if not a.endswith(".py"):
                                hallazgos.add(("no_codigo_en_paquete_de_almacenes", imagen(os.path.join(sub, a))))
        for a in archivos:
            real = os.path.join(actual, a)
            ruta = imagen(real)
            if prohibido_por_nombre(a):
                hallazgos.add(("archivo_prohibido", ruta))
            elif not os.path.isfile(real) or os.path.islink(real):
                continue
            elif ruta.startswith(ZONAS_INSPECCIONABLES) and not os.access(real, os.R_OK):
                hallazgos.add(("archivo_ilegible_no_inspeccionado", ruta))
            elif not ruta.startswith(CERTIFICADOS_DEL_SISTEMA) and clave_privada(real):
                hallazgos.add(("clave_privada", ruta))
    return sorted(hallazgos)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    uid = os.geteuid() if hasattr(os, "geteuid") else None
    vistos = revisar(argv[0] if argv else "/", uid=uid)
    print(json.dumps({"correcto": not vistos, "uid": uid,
                      "hallazgos": [{"motivo": m, "ruta": r} for m, r in vistos]}, ensure_ascii=False, indent=1))
    return 0 if not vistos else 1


if __name__ == "__main__":
    sys.exit(main())
