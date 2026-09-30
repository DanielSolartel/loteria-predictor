#!/usr/bin/env python3
"""AE-78, validada localmente como trabajo preparatorio: verificador offline
y de solo lectura del expediente portable de la recepcion por objetivo.

Uso (desde `backend`):

  python -m scripts.verificar_expediente_recepcion EXPEDIENTE --politica POLITICA
         [--formato texto|json] [--salida-json RUTA]

EXPEDIENTE es un directorio `expediente-portable-recepcion/1`; POLITICA, un
directorio `politica-verificador-de-prueba/1` con las anclas y claves de
prueba que el verificador acepta (nunca se toman del expediente).

Codigos de salida (ninguno autoriza evaluacion):
  0  auditoria completada sin planos comprobables rechazados;
  1  auditoria completada con algun plano comprobable rechazado;
  2  uso incorrecto (argumentos, o salida dentro de un directorio auditado
     o ya existente);
  3  la lectura endurecida rechazo el expediente o la politica.

Lectura endurecida: el directorio no puede ser ni contener enlaces
simbolicos ni archivos no regulares; se respetan limites de numero y tamano
antes de leer; todo lo demas lo comprueba el manifiesto. Estas comprobaciones
cubren un directorio estable: no hay garantia frente a cambios concurrentes
del sistema de archivos durante la lectura (`archivo_cambio_durante_la_lectura`
solo detecta un numero de bytes distinto del consultado). Solo lee: el unico
archivo que puede escribir es el informe de `--salida-json`, fuera de los
directorios auditados y sin sobrescribir. Sin red, reloj, deserializacion
ejecutable ni secretos.
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

from app.application.ml import expediente_portable as ep


def _es_enlace(ruta: Path) -> bool:
    """Enlace simbolico o union de directorios (Windows)."""
    try:
        modo = os.lstat(ruta).st_mode
    except OSError:
        return False
    union = getattr(os.path, "isjunction", None)
    return stat.S_ISLNK(modo) or bool(union and union(ruta))


def cargar_directorio(raiz: Path, *, limites: ep.Limites = ep.LIMITES_POR_DEFECTO) -> dict:
    """{ruta relativa POSIX: bytes} de un directorio, sin seguir enlaces y
    sin leer nada fuera de el."""
    raiz = Path(raiz)
    if _es_enlace(raiz) or not raiz.is_dir():
        raise ep.ExpedienteIlegible("directorio_invalido", str(raiz))
    base = raiz.resolve(strict=True)
    archivos: dict = {}
    total = 0
    for actual, carpetas, nombres in os.walk(base, followlinks=False):
        carpetas.sort()
        for carpeta in carpetas:
            if _es_enlace(Path(actual) / carpeta):
                raise ep.ExpedienteIlegible("enlace_simbolico", carpeta)
        for nombre in sorted(nombres):
            ruta = Path(actual) / nombre
            if _es_enlace(ruta):
                raise ep.ExpedienteIlegible("enlace_simbolico", nombre)
            info = os.lstat(ruta)
            if not stat.S_ISREG(info.st_mode):
                raise ep.ExpedienteIlegible("archivo_no_regular", nombre)
            if not ruta.resolve().is_relative_to(base):
                raise ep.ExpedienteIlegible("ruta_fuera_del_directorio", nombre)
            relativa = ruta.relative_to(base).as_posix()
            if len(archivos) >= limites.archivos + 1:
                raise ep.ExpedienteIlegible("demasiados_archivos")
            es_manifiesto = relativa in (ep.NOMBRE_MANIFIESTO, ep.NOMBRE_POLITICA)
            if info.st_size > (limites.bytes_manifiesto if es_manifiesto else limites.bytes_por_archivo):
                raise ep.ExpedienteIlegible("archivo_demasiado_grande", nombre)
            total += info.st_size
            if total > limites.bytes_totales:
                raise ep.ExpedienteIlegible("expediente_demasiado_grande")
            with open(ruta, "rb") as flujo:
                datos = flujo.read(info.st_size + 1)
            if len(datos) != info.st_size:
                raise ep.ExpedienteIlegible("archivo_cambio_durante_la_lectura", nombre)
            archivos[relativa] = datos
    return archivos


def _salida(informe: dict, formato: str) -> None:
    if formato == "json":
        sys.stdout.write(ep.informe_json(informe).decode("utf-8"))
    else:
        sys.stdout.write(ep.resumen_legible(informe))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verificador offline del expediente portable (AE-78)")
    parser.add_argument("expediente")
    parser.add_argument("--politica", required=True)
    parser.add_argument("--formato", choices=("texto", "json"), default="texto")
    parser.add_argument("--salida-json")
    args = parser.parse_args(argv)

    destino = None
    if args.salida_json:
        destino = Path(args.salida_json).resolve()
        for auditado in (args.expediente, args.politica):
            auditado = Path(auditado).resolve()
            if destino == auditado or destino.is_relative_to(auditado):
                sys.stderr.write("la salida JSON debe quedar fuera del expediente y de la politica\n")
                return ep.CODIGOS_DE_SALIDA["uso_incorrecto"]
        if destino.exists():
            sys.stderr.write("la salida JSON ya existe; no se sobrescribe\n")
            return ep.CODIGOS_DE_SALIDA["uso_incorrecto"]

    objeto = "expediente"
    try:
        expediente = ep.leer_expediente(cargar_directorio(Path(args.expediente)))
        objeto = "politica"
        politica = ep.leer_politica(cargar_directorio(Path(args.politica)))
    except ep.ExpedienteIlegible as error:
        informe = ep.informe_de_lectura_rechazada(objeto, error)
    else:
        informe = ep.evaluar(expediente, politica)
    _salida(informe, args.formato)
    if destino is not None:
        with open(destino, "xb") as flujo:
            flujo.write(ep.informe_json(informe))
    return ep.codigo_de_salida(informe)


if __name__ == "__main__":
    sys.exit(main())
