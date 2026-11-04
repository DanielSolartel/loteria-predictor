"""Paquete de generacion SINTETICO y valido (sin base de datos) para probar verificacion, respaldo y perfil privado.

Usa el mismo identificador (`captura.id_de`), JSON canonico y firma que la captura real; el contenido de los
archivos es arbitrario (la coherencia cruzada con artefactos reales se prueba en `test_captura_c1_c10`)."""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.infrastructure.generaciones import codigo as _codigo
from app.infrastructure.generaciones import firma
from app.infrastructure.generaciones.captura import id_de
from app.infrastructure.generaciones.formato import FORMATO, canonico

COHERENCIA = {"artefactos": [], "ilegibles": {}, "rechazos": [],
              "resumen": {"artefactos": 0, "por_familia_y_historico": {}, "ilegibles": 0, "rechazos": 0,
                          "objetivos_posteriores_al_ultimo_sorteo": 0}}


HUELLA_APP = _codigo.huella_app(_codigo.raiz_de_esta_app())[0]  # el codigo de app/ que ejecuta la prueba


def construir(raiz: Path, claves: tuple[Path, Path] | None = None, *, archivos: dict[str, bytes] | None = None,
              filas: dict[str, list[str]] | None = None, alcance: str = "publicacion") -> tuple[Path, Path, Path]:
    """Devuelve (carpeta del paquete, clave privada, clave publica)."""
    if claves is None:
        claves = (raiz / "firma.pem", raiz / "firma.pub")
        firma.generar(*claves)
    archivos = archivos if archivos is not None else {
        "archivos/pronosticos/BALOTO/2193-" + "a" * 64 + ".json": b'{"x":1}\n',
        "archivos/laboratorio/modelos/BALOTO/estimadores/" + "b" * 64 + ".pkl": b"\x80\x05bytes-no-deserializados",
        "archivos/carteras/carteras/BALOTO/l-v1-n5-libre-s1/2193-" + "c" * 64 + ".json": b'{"y":2}\n'}
    filas = filas if filas is not None else {"juegos": ['{"codigo":"BALOTO","id":"1"}'], "sorteos": []}
    trabajo = raiz / "trabajo"
    contenido: dict[str, bytes] = dict(archivos)
    for tabla, lineas in filas.items():
        contenido[f"base/{tabla}.jsonl"] = "".join(l + "\n" for l in lineas).encode("utf-8")
    contenido["coherencia.json"] = canonico(COHERENCIA)
    for ruta, datos in contenido.items():
        destino = trabajo / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
    tablas = {t: {"filas": len(l), "sha256_contenido": hashlib.sha256(contenido[f"base/{t}.jsonl"]).hexdigest()}
              for t, l in filas.items()}
    clave = firma.cargar_privada(claves[0])
    manifiesto = {"formato": FORMATO, "alcance": alcance, "creada_en": "2026-11-04T00:00:00+00:00",
                  "captura": {"metodo": "sintetico"}, "codigo": {"revision_alembic": "0006", "huella_fuentes": "0",
                                                         "huella_app": HUELLA_APP},
                  "esquema": {"revision_alembic": "0006", "huella": "0" * 64}, "base": {"tablas": tablas},
                  "juegos": {"BALOTO": {"sorteos": 0, "ultimo_sorteo": None, "ultima_fecha": None}},
                  "almacenes": {}, "coherencia": COHERENCIA["resumen"], "clave_firma": firma.id_de_privada(clave),
                  "archivos": {r: {"bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()}
                               for r, d in sorted(contenido.items())}}
    manifiesto["id"] = id_de(manifiesto)
    datos = canonico(manifiesto)
    (trabajo / "manifiesto.json").write_bytes(datos)
    (trabajo / "manifiesto.firma").write_text(firma.firmar(clave, datos) + "\n", encoding="ascii")
    carpeta = raiz / manifiesto["id"]
    trabajo.rename(carpeta)
    return carpeta, claves[0], claves[1]


def refirmar(carpeta: Path, privada: Path, cambio) -> Path:
    """Aplica `cambio(manifiesto)` y vuelve a firmar con la clave VALIDA (simula una generacion autentica pero
    de otro codigo o mal formada). Renombra la carpeta al nuevo id."""
    import json

    m = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    cambio(m)
    m["id"] = id_de(m)
    datos = canonico(m)
    (carpeta / "manifiesto.json").write_bytes(datos)
    (carpeta / "manifiesto.firma").write_text(firma.firmar(firma.cargar_privada(privada), datos) + "\n",
                                              encoding="ascii")
    nueva = carpeta.with_name(m["id"])
    carpeta.rename(nueva)
    return nueva
