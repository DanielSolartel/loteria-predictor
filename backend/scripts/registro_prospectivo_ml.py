#!/usr/bin/env python3
"""AE-52, validada: CLI local del registro prospectivo de ML.

Sin base de datos ni red, y sin generar predicciones:

  iniciar-borrador DIRECTORIO
      Crea en un directorio existente y vacio la primera entrada
      (`000001.json`) con el protocolo en BORRADOR de la
      estrategia candidata (Regresion Logistica calibrada de AE-36):
      huella del codigo, parametros leidos del codigo validado y
      entorno. Todas las decisiones que el repositorio no fija quedan
      pendientes, asi que el registro no admite salidas ni acumula
      evidencia prospectiva.

  verificar DIRECTORIO
      Comprueba nombres, forma canonica, cadena de hashes y reglas de
      cada entrada, y publica un resumen (progreso por juego, cabeza de
      la cadena y hashes para anclarlos externamente). Solo lectura.

Cada entrada es un archivo nuevo `NNNNNN.json`, nombrado solo por su
secuencia y creado de forma exclusiva (publicacion con enlace duro de
AE-48): nunca se sobrescribe, y si dos operaciones leen la misma cabeza
solo una puede publicar esa secuencia; la otra falla sin escribir nada.
La cadena prueba el orden, no la fecha: la anterioridad frente a cada
sorteo exige un sellado temporal externo (pendiente de decision).

Uso (desde backend): python -m scripts.registro_prospectivo_ml verificar DIRECTORIO

Codigos: 0 correcto; 1 fallo inesperado; 2 argumentos invalidos;
3 registro ilegible; 4 entrada invalida o regla incumplida; 5 cadena o
nombres inconsistentes; 8 fallo al escribir; 9 directorio no permitido.
El NO-GO de AE-39 sigue vigente.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import os
import platform
import re
import sys
from pathlib import Path

from app.application.ml import registro_prospectivo as rp
from app.application.ml.dataset import PERIODO_CALENTAMIENTO_MINIMO, TAMANOS_VENTANA
from app.application.ml.modelo import (
    NOMBRES_FEATURES,
    SEMILLA_DEFECTO,
    VERSION_SKLEARN,
    construir_pipeline,
    entrenar_modelo_calibrado,
)
from scripts.comparacion_estado_prediccion import (
    EscrituraEvidenciaError,
    escribir_evidencia_atomica,
    serializar_reporte,
)

EXIT_OK = 0
EXIT_FALLO_INESPERADO = 1
EXIT_ARGUMENTOS_INVALIDOS = 2
EXIT_ILEGIBLE = 3
EXIT_ENTRADA_INVALIDA = 4
EXIT_CADENA_INCONSISTENTE = 5
EXIT_FALLO_ESCRITURA = 8
EXIT_RUTA_NO_PERMITIDA = 9

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
ARCHIVOS_ESTRATEGIA_AE36 = (
    "app/application/ml/baselines.py",
    "app/application/ml/dataset.py",
    "app/application/ml/features.py",
    "app/application/ml/historico_util.py",
    "app/application/ml/metricas.py",
    "app/application/ml/modelo.py",
    "app/application/ml/tipos.py",
)
"""Codigo del que depende la estrategia candidata, su salida y su
comparacion con el azar. Cualquier cambio en estos archivos cambia la
version registrada."""
_NOMBRE_ENTRADA = re.compile(r"(\d{6})\.json")
"""La secuencia es el nombre completo: la exclusividad de la publicacion
por nombre es tambien exclusividad por secuencia."""
_TEMPORAL_AE48 = re.compile(r"\.evidencia-ae48-[A-Za-z0-9_]+\.tmp")
"""Temporal de `escribir_evidencia_atomica` mientras otra operacion
publica: nunca es una entrada (la entrada aparece de golpe con el
enlace), asi que la lectura lo ignora."""
serializar_informe = serializar_reporte


class SecuenciaOcupadaError(rp.RegistroProspectivoError):
    """Otra operacion publico antes esa misma secuencia: esta operacion
    no avanza la cadena y no escribe nada."""
    codigo_salida = EXIT_FALLO_ESCRITURA


class _ArgumentosInvalidosError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _ArgumentosInvalidosError(message)


def _error(etiqueta: str, mensaje) -> None:
    print(f"ERROR [{etiqueta}]: {mensaje}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Version exacta de la estrategia candidata
# ---------------------------------------------------------------------------

def huella_codigo(raiz: Path, archivos) -> str:
    """SHA-256 del codigo de la estrategia: ruta y SHA-256 de cada
    archivo con los fines de linea normalizados a LF (la misma version
    da la misma huella en Linux y en Windows con autocrlf)."""
    lineas = ["ae52-codigo-v1"]
    for ruta in sorted(archivos):
        contenido = (Path(raiz) / ruta).read_bytes().replace(b"\r\n", b"\n")
        lineas.append(f"{ruta}:{hashlib.sha256(contenido).hexdigest()}")
    return hashlib.sha256(("\n".join(lineas) + "\n").encode("utf-8")).hexdigest()


def estrategia_candidata_ae36() -> dict:
    """Parametros leidos del codigo validado, nunca copiados a mano."""
    parametros = construir_pipeline().get_params()
    return {
        "nombre": "regresion_logistica_calibrada_ae36",
        "descripcion": (
            "Candidata no aprobada: Regresion Logistica L2 calibrada de AE-36, unica configuracion fija existente "
            "(AE-37 y AE-38 eligen su configuracion por bloque). Salida: probabilidad de aparicion de cada numero "
            "del rango en el sorteo siguiente."
        ),
        "huella_codigo": huella_codigo(RAIZ_BACKEND, ARCHIVOS_ESTRATEGIA_AE36),
        "archivos_codigo": list(ARCHIVOS_ESTRATEGIA_AE36),
        "parametros": {
            "semilla": SEMILLA_DEFECTO, "nombres_features": list(NOMBRES_FEATURES),
            "C": parametros["clf__C"], "solver": parametros["clf__solver"], "max_iter": parametros["clf__max_iter"],
            "proporcion_calibracion": inspect.signature(entrenar_modelo_calibrado).parameters[
                "proporcion_calibracion"].default,
            "periodo_calentamiento_minimo": PERIODO_CALENTAMIENTO_MINIMO, "tamanos_ventana": list(TAMANOS_VENTANA),
            "salida": "probabilidad_de_aparicion_por_numero_del_rango",
        },
        "entorno": {"python": platform.python_version(), "scikit_learn": VERSION_SKLEARN},
    }


# ---------------------------------------------------------------------------
# Lectura y anexado del registro (un archivo por entrada)
# ---------------------------------------------------------------------------

def _leer_contenidos(directorio: Path) -> list[bytes]:
    directorio = Path(directorio)
    if not directorio.is_dir():
        raise rp.RegistroIlegibleError(f"'{directorio}' no es un directorio de registro legible")
    nombres = sorted(n for n in os.listdir(directorio) if not _TEMPORAL_AE48.fullmatch(n))
    for posicion, nombre in enumerate(nombres, start=1):
        coincidencia = _NOMBRE_ENTRADA.fullmatch(nombre)
        if coincidencia is None:
            raise rp.CadenaRegistroInconsistenteError(f"Archivo ajeno al registro: '{nombre}'")
        if int(coincidencia.group(1)) != posicion:
            raise rp.CadenaRegistroInconsistenteError(f"'{nombre}' rompe la secuencia de archivos (se esperaba {posicion})")
    contenidos = []
    for nombre in nombres:
        try:
            contenido = (directorio / nombre).read_bytes()
        except OSError as error:
            raise rp.RegistroIlegibleError(f"No se pudo leer '{nombre}': {error}") from error
        entrada = rp.leer_entrada(contenido)
        if entrada.get("secuencia") != int(_NOMBRE_ENTRADA.fullmatch(nombre).group(1)):
            raise rp.CadenaRegistroInconsistenteError(f"'{nombre}' no coincide con la secuencia de su contenido")
        contenidos.append(contenido)
    return contenidos


def leer_registro(directorio) -> rp.EstadoRegistro:
    return rp.validar_registro(_leer_contenidos(Path(directorio)))


def anexar_entrada(directorio, entrada: dict) -> Path:
    """Valida el registro completo con la entrada nueva y la escribe en
    un archivo nuevo de forma exclusiva. Si algo falla, no escribe nada.
    Si otra operacion ya publico esa secuencia (leyeron la misma
    cabeza), lanza `SecuenciaOcupadaError` sin sobrescribir: solo una
    operacion avanza la cadena."""
    directorio = Path(directorio)
    existentes = _leer_contenidos(directorio)
    contenido = rp.serializar_entrada(entrada)
    rp.validar_registro(existentes + [contenido])
    ruta = directorio / f"{entrada['secuencia']:06d}.json"
    try:
        escribir_evidencia_atomica(contenido, str(ruta))
    except EscrituraEvidenciaError as error:
        if isinstance(error.__cause__, FileExistsError):
            raise SecuenciaOcupadaError(
                f"La secuencia {entrada['secuencia']} ya fue publicada por otra operacion; no se sobrescribe. "
                "Vuelva a leer el registro antes de reintentar."
            ) from error
        raise
    return ruta


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _iniciar_borrador(directorio: Path) -> int:
    if not directorio.is_dir() or any(directorio.iterdir()):
        _error(f"codigo {EXIT_RUTA_NO_PERMITIDA}", f"'{directorio}' debe ser un directorio existente y vacio")
        return EXIT_RUTA_NO_PERMITIDA
    protocolo = rp.construir_protocolo_borrador(estrategia_candidata_ae36())
    contenido = rp.serializar_entrada(protocolo)
    rp.validar_registro([contenido])
    ruta = directorio / "000001.json"
    try:
        huella = escribir_evidencia_atomica(contenido, str(ruta))
    except EscrituraEvidenciaError as error:
        _error(f"codigo {EXIT_FALLO_ESCRITURA}", error)
        return EXIT_FALLO_ESCRITURA
    sys.stdout.flush()
    sys.stdout.buffer.write(contenido)
    sys.stdout.buffer.flush()
    print(f"SHA-256 {huella}  {ruta}  ({len(contenido)} bytes)", file=sys.stderr)
    return EXIT_OK


def _verificar(directorio: Path) -> int:
    estado = leer_registro(directorio)
    sys.stdout.flush()
    sys.stdout.buffer.write(serializar_informe(rp.resumir_registro(estado)))
    sys.stdout.buffer.flush()
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description="Registro prospectivo de ML AE-52 (local, sin base de datos)")
    comandos = parser.add_subparsers(dest="comando", required=True)
    comandos.add_parser("iniciar-borrador").add_argument("directorio")
    comandos.add_parser("verificar").add_argument("directorio")
    try:
        argumentos = parser.parse_args([] if argv is None else argv)
    except _ArgumentosInvalidosError as error:
        _error(f"codigo {EXIT_ARGUMENTOS_INVALIDOS}", error)
        return EXIT_ARGUMENTOS_INVALIDOS
    directorio = Path(argumentos.directorio)
    try:
        if argumentos.comando == "iniciar-borrador":
            return _iniciar_borrador(directorio)
        return _verificar(directorio)
    except rp.RegistroProspectivoError as error:
        _error(f"codigo {error.codigo_salida}", error)
        return error.codigo_salida
    except Exception as error:
        _error("inesperado", f"{type(error).__name__}: {error}")
        return EXIT_FALLO_INESPERADO


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
