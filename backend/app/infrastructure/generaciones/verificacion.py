"""Verificacion de un paquete de generacion ANTES de usarlo (E10.4, DAT-04 sin base):

1. manifiesto canonico, formato conocido y alcance esperado;
2. autenticidad: firma Ed25519 del manifiesto con la clave publica configurada (y el mismo identificador);
3. identidad: el `id` es la huella del propio manifiesto y coincide con el nombre de la carpeta;
4. integridad: el conjunto EXACTO de archivos (ni de mas ni de menos, sin enlaces ni rutas raras) con su
   tamano y SHA-256; la huella de contenido de cada tabla recalculada desde sus lineas JSON;
5. coherencia interna: `coherencia.json` coincide con el resumen del manifiesto y no tiene rechazos.

La compatibilidad con el codigo y el esquema, la restauracion y la coherencia cruzada contra la base restaurada
son del importador.
"""
from __future__ import annotations

import os
from pathlib import Path

from app.infrastructure.generaciones import base_logica as bl
from app.infrastructure.generaciones import firma
from app.infrastructure.generaciones.formato import (
    COHERENCIA, FIRMA, FORMATO, MANIFIESTO, GeneracionNoValida, es_id, leer_canonico, ruta_relativa_segura,
    sha256_archivo,
)


def _contenido_real(carpeta: Path) -> set[str]:
    salida = set()
    for raiz, subcarpetas, archivos in os.walk(carpeta, followlinks=False):
        for nombre in subcarpetas + archivos:
            ruta = Path(raiz) / nombre
            if ruta.is_symlink():
                raise GeneracionNoValida(f"enlace simbolico en el paquete: {ruta.relative_to(carpeta).as_posix()}")
        for nombre in archivos:
            salida.add((Path(raiz) / nombre).relative_to(carpeta).as_posix())
    return salida


def verificar(carpeta: Path, clave_publica: Path, *, alcance: str = "publicacion") -> dict:
    try:
        return _verificar(carpeta, clave_publica, alcance)
    except (OSError, KeyError, TypeError, AttributeError) as error:  # archivo ausente o manifiesto mal formado
        raise GeneracionNoValida(f"paquete incompleto o mal formado: {type(error).__name__}") from error


def _verificar(carpeta: Path, clave_publica: Path, alcance: str) -> dict:
    if carpeta.is_symlink() or not carpeta.is_dir():
        raise GeneracionNoValida("el paquete no es una carpeta")
    manifiesto = leer_canonico(carpeta / MANIFIESTO)
    if manifiesto.get("formato") != FORMATO:
        raise GeneracionNoValida(f"formato no admitido: {manifiesto.get('formato')!r}")
    if manifiesto.get("alcance") != alcance:
        raise GeneracionNoValida(f"alcance {manifiesto.get('alcance')!r}; se esperaba {alcance!r}")
    publica, id_clave = firma.cargar_publica(clave_publica)
    if manifiesto.get("clave_firma") != id_clave:
        raise GeneracionNoValida("el manifiesto declara otra clave de firma")
    firma.verificar(publica, (carpeta / MANIFIESTO).read_bytes(), (carpeta / FIRMA).read_text(encoding="ascii"))
    from app.infrastructure.generaciones.captura import id_de

    if not es_id(manifiesto.get("id", "")) or id_de(manifiesto) != manifiesto["id"]:
        raise GeneracionNoValida("el id no corresponde al manifiesto")
    if carpeta.name != manifiesto["id"]:
        raise GeneracionNoValida("la carpeta no se llama como el id de la generacion")
    declarados = manifiesto.get("archivos")
    if not isinstance(declarados, dict):
        raise GeneracionNoValida("manifiesto sin lista de archivos")
    for ruta in declarados:
        ruta_relativa_segura(ruta)
    reales = _contenido_real(carpeta) - {MANIFIESTO, FIRMA}
    if reales != set(declarados):
        sobran, faltan = sorted(reales - set(declarados)), sorted(set(declarados) - reales)
        raise GeneracionNoValida(f"archivos distintos de los declarados (sobran {sobran[:5]}, faltan {faltan[:5]})")
    for ruta, esperado in sorted(declarados.items()):
        tam, sha = sha256_archivo(carpeta / ruta)
        if (tam, sha) != (esperado.get("bytes"), esperado.get("sha256")):
            raise GeneracionNoValida(f"{ruta}: tamano o SHA-256 distinto del manifiesto")
    tablas = manifiesto.get("base", {}).get("tablas", {})
    if {f"base/{n}.jsonl" for n in tablas} != {r for r in declarados if r.startswith("base/")}:
        raise GeneracionNoValida("las tablas declaradas no coinciden con los volcados")
    if bl.huellas_de_archivos(carpeta / "base", tablas) != tablas:
        raise GeneracionNoValida("la huella de contenido de alguna tabla no coincide")
    coherencia = leer_canonico(carpeta / COHERENCIA)
    if coherencia.get("resumen") != manifiesto.get("coherencia") or coherencia.get("rechazos"):
        raise GeneracionNoValida("la coherencia del paquete no coincide con el manifiesto o tiene rechazos")
    return manifiesto
