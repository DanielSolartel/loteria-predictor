#!/usr/bin/env python3
"""AE-79, validada localmente como trabajo preparatorio: auditoria
cruzada offline y de solo lectura de expedientes portables AE-78 y
capturas de observadores de prueba.

Uso (desde `backend`):

  python -m scripts.auditar_expedientes_cruzados EXPEDIENTE EXPEDIENTE [...]
         --politica POLITICA --politica-auditoria POLITICA_AUDITORIA
         [--capturas CAPTURAS ...] [--huella-politica SHA256]
         [--huella-politica-auditoria SHA256] [--huella-manifiesto SHA256 ...]
         [--huella-captura SHA256 ...] [--formato texto|json]
         [--salida-json RUTA]

Entre 2 y 8 directorios `expediente-portable-recepcion/1`; POLITICA es la
politica de prueba del verificador de AE-78; POLITICA_AUDITORIA, la de quien
audita (`politica-auditoria-cruzada-de-prueba/1`: capturadores admitidos y
cortes sinteticos admitidos); cada CAPTURAS, un directorio
`capturas-de-observador/1` (hasta 8). Las huellas esperadas las aporta quien
audita desde fuera de los expedientes (la de una captura es el SHA-256 de
su `datos.json`); una huella copiada de los propios archivos no es una
publicacion independiente.

Codigos de salida (ninguno autoriza evaluacion):
  0  sin contradiccion detectable en lo presentado;
  1  contradiccion comprobada entre bytes firmados presentados;
  2  uso incorrecto (argumentos, numero de entradas, un directorio repetido,
     huella mal formada, o salida dentro de un directorio auditado o ya
     existente);
  3  la lectura endurecida rechazo al menos una entrada (o el limite
     agregado);
  4  firmas, hashes, vinculos, politicas o huellas esperadas no coinciden.

Cada directorio se lee con la lectura endurecida de AE-78
(`cargar_directorio`): sin enlaces ni archivos no regulares y con limites por
directorio. Ademas se limitan los bytes y archivos agregados de toda la
auditoria. Las comprobaciones en disco cubren directorios estables; no hay
garantia frente a cambios concurrentes durante la lectura. Solo lee: el
unico archivo que puede escribir es el informe de `--salida-json`, fuera de
todos los directorios auditados y sin sobrescribir. El informe no contiene
rutas absolutas, hora local ni secretos. Sin red, reloj ni deserializacion
ejecutable.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.application.ml import auditoria_cruzada as ac
from app.application.ml import expediente_portable as ep
from scripts.verificar_expediente_recepcion import cargar_directorio


class _LimiteAgregado(Exception):
    pass


class _Cargador:
    """Carga directorios descontando un presupuesto agregado de bytes y
    archivos; los limites de AE-78 por directorio siguen valiendo."""

    def __init__(self):
        self.bytes = ac.BYTES_AGREGADOS
        self.archivos = ac.ARCHIVOS_AGREGADOS

    def __call__(self, ruta: Path):
        base = ep.LIMITES_POR_DEFECTO
        bytes_ = min(base.bytes_totales, self.bytes)
        archivos = min(base.archivos, self.archivos - 1)
        if archivos < 0:
            raise _LimiteAgregado()
        limites = ep.Limites(bytes_por_archivo=base.bytes_por_archivo, bytes_totales=bytes_,
                             archivos=archivos, bytes_manifiesto=base.bytes_manifiesto)
        try:
            contenido = cargar_directorio(ruta, limites=limites)
        except ep.ExpedienteIlegible as error:
            agregado = ((error.motivo == "expediente_demasiado_grande" and bytes_ < base.bytes_totales)
                        or (error.motivo == "demasiados_archivos" and archivos < base.archivos))
            if agregado:
                raise _LimiteAgregado() from error
            return error
        self.bytes -= sum(len(d) for d in contenido.values())
        self.archivos -= len(contenido)
        return contenido


def _huella(valor: str) -> str:
    if not ac.es_huella(valor):
        raise argparse.ArgumentTypeError("huella SHA-256 en hexadecimal minuscula")
    return valor


def _salida(informe: dict, formato: str) -> None:
    if formato == "json":
        sys.stdout.write(ac.informe_json(informe).decode("utf-8"))
    else:
        sys.stdout.write(ac.resumen_legible(informe))


def _uso(mensaje: str) -> int:
    sys.stderr.write(mensaje + "\n")
    return ac.CODIGOS_DE_SALIDA["uso_incorrecto"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auditoria cruzada offline de expedientes portables (AE-79)")
    parser.add_argument("expedientes", nargs="+")
    parser.add_argument("--politica", required=True)
    parser.add_argument("--politica-auditoria", required=True)
    parser.add_argument("--capturas", action="append", default=[])
    parser.add_argument("--huella-politica", type=_huella)
    parser.add_argument("--huella-politica-auditoria", type=_huella)
    parser.add_argument("--huella-manifiesto", type=_huella, action="append", default=[])
    parser.add_argument("--huella-captura", type=_huella, action="append", default=[])
    parser.add_argument("--formato", choices=("texto", "json"), default="texto")
    parser.add_argument("--salida-json")
    args = parser.parse_args(argv)

    if not ac.MINIMO_DE_EXPEDIENTES <= len(args.expedientes) <= ac.MAXIMO_DE_EXPEDIENTES:
        return _uso(f"hacen falta entre {ac.MINIMO_DE_EXPEDIENTES} y {ac.MAXIMO_DE_EXPEDIENTES} expedientes")
    if len(args.capturas) > ac.MAXIMO_DE_CONJUNTOS_DE_CAPTURAS:
        return _uso(f"como maximo {ac.MAXIMO_DE_CONJUNTOS_DE_CAPTURAS} directorios de capturas")
    auditados = [Path(p).resolve() for p in (*args.expedientes, args.politica, args.politica_auditoria,
                                             *args.capturas)]
    if len(auditados) != len(set(auditados)):
        return _uso("un mismo directorio aparece dos veces")
    destino = None
    if args.salida_json:
        destino = Path(args.salida_json).resolve()
        if any(destino == d or destino.is_relative_to(d) for d in auditados):
            return _uso("la salida JSON debe quedar fuera de todos los directorios auditados")
        if destino.exists():
            return _uso("la salida JSON ya existe; no se sobrescribe")
    referencias = ac.ReferenciasExternas(
        politica_del_verificador=args.huella_politica, politica_de_auditoria=args.huella_politica_auditoria,
        manifiestos=frozenset(args.huella_manifiesto), capturas=frozenset(args.huella_captura))

    cargar = _Cargador()
    try:
        politica = cargar(Path(args.politica))
        politica_auditoria = cargar(Path(args.politica_auditoria))
        expedientes = [(Path(p).name, cargar(Path(p))) for p in args.expedientes]
        capturas = [(Path(p).name, cargar(Path(p))) for p in args.capturas]
    except _LimiteAgregado:
        informe = ac.informe_de_lectura_rechazada("entradas", "limite_agregado_superado", len(args.expedientes),
                                                  len(args.capturas))
    else:
        informe = ac.auditar(expedientes=expedientes, politica_del_verificador=politica,
                             politica_de_auditoria=politica_auditoria, capturas=capturas, referencias=referencias)
    _salida(informe, args.formato)
    if destino is not None:
        with open(destino, "xb") as flujo:
            flujo.write(ac.informe_json(informe))
    return ac.codigo_de_salida(informe)


if __name__ == "__main__":
    sys.exit(main())
