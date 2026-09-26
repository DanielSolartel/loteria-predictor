#!/usr/bin/env python3
"""AE-45, validada; ampliada en AE-47, validada: consulta manual del
estado bloqueado de AE-44 con el diagnostico de AE-46 (JSON esquema 1.1).

Solo lee metadatos agregados de sorteos en una transaccion PostgreSQL
de solo lectura verificada. No se ejecuta al iniciar la aplicacion,
no tiene ruta web/API, no observa numeros ganadores y no persiste.
AE-41 se consulta una sola vez por juego y ese mismo reporte alimenta
el estado (AE-44) y el diagnostico (AE-46). Publica un JSON por stdout
solamente si ambos juegos se evaluaron, sus reportes son coherentes y
el diagnostico coincide en estado y motivos con el reporte. Un bloqueo
valido termina con codigo 0.

AE-48, validada: dos flags opcionales, validados antes de abrir la
conexion. `--salida RUTA` guarda los bytes exactos del JSON (publicacion
exclusiva, nunca sobrescribe), los mismos bytes van a stdout y la huella
SHA-256 se informa solo en stderr. `--comparar RUTA` valida un reporte
anterior 1.1/1.2 y anade una comparacion descriptiva (esquema 1.2). Sin
flags, la salida es identica a la de AE-47.

Ejecutar desde backend: python -m scripts.consultar_estado_prediccion
"""
from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.ml.diagnostico_bloqueo import (
    CONDICIONES_SIN_MECANISMO_AE46,
    CondicionDesbloqueoML,
    DiagnosticoBloqueoJuego,
)
from app.application.ml.reapertura import JUEGOS_AUTORIZADOS_AE40
from app.application.ml.tipos import EstadoPrediccionML, ReporteAutorizacionOperativaML, ReportePrediccionJuego
from app.application.use_cases.diagnosticar_estado_prediccion import DiagnosticarEstadoPrediccion
from app.application.use_cases.evaluar_autorizacion_operativa_ml import EvaluarAutorizacionOperativaML
from app.application.use_cases.evaluar_elegibilidad_reapertura_ml import EvaluarElegibilidadReaperturaML
from app.application.use_cases.resolver_estado_prediccion import ResolverEstadoPrediccion
from app.infrastructure.repositories.disponibilidad_holdout_repository_sqlalchemy import (
    DisponibilidadHoldoutRepositorySQLAlchemy,
)
from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
from scripts import comparacion_estado_prediccion
from scripts.comparacion_estado_prediccion import (
    CatalogoEstados,
    EscrituraEvidenciaError,
    ReporteAnteriorInvalidoError,
    RutaSalidaNoPermitidaError,
    serializar_reporte,
)
from scripts.auditoria_operativa_bloqueo import (
    FalloAuditoriaOperativaError,
    verificar_revision_alembic,
    verificar_transaccion_solo_lectura,
)

EXIT_OK = 0
EXIT_FALLO_INESPERADO = 1
EXIT_FALLO_CONEXION = 2
EXIT_REVISION_ALEMBIC_INESPERADA = 3
EXIT_TRANSACCION_NO_SOLO_LECTURA = 4
EXIT_REPORTE_INCONSISTENTE = 5
EXIT_FALLO_EVALUANDO_JUEGO = 6
EXIT_ARCHIVO_ANTERIOR_INVALIDO = 7
EXIT_FALLO_ESCRITURA_SALIDA = 8
EXIT_RUTA_SALIDA_NO_PERMITIDA = 9
ESTADOS_BLOQUEADOS_AE45 = frozenset({
    EstadoPrediccionML.BLOQUEADO_NUMERACION_INVALIDA,
    EstadoPrediccionML.BLOQUEADO_DATOS_INSUFICIENTES,
    EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO,
    EstadoPrediccionML.BLOQUEADO_SIN_EVALUACION_HOLDOUT,
})
ESQUEMA_JSON = "1.1"
"""AE-47: 1.0 (AE-45) + `progreso`, `condiciones_pendientes` y
`desbloqueable` por juego. Nunca campos predictivos."""


class FalloConsultaEstadoError(Exception):
    def __init__(self, mensaje: str, codigo_salida: int):
        super().__init__(mensaje)
        self.codigo_salida = codigo_salida


class _AutorizacionUnaVezPorJuego:
    """AE-47: envuelve el caso de uso real de AE-41 para que cada juego
    se consulte una sola vez y el MISMO reporte se comparta entre
    `ResolverEstadoPrediccion` y `DiagnosticarEstadoPrediccion`. Un
    fallo no se guarda: se propaga tal cual."""

    def __init__(self, caso_uso_autorizacion: EvaluarAutorizacionOperativaML):
        self._caso_uso_autorizacion = caso_uso_autorizacion
        self._reportes: dict[str, ReporteAutorizacionOperativaML] = {}

    def ejecutar(self, codigo_juego: str) -> ReporteAutorizacionOperativaML:
        if codigo_juego not in self._reportes:
            self._reportes[codigo_juego] = self._caso_uso_autorizacion.ejecutar(codigo_juego)
        return self._reportes[codigo_juego]


def _progreso_json(diagnostico: DiagnosticoBloqueoJuego) -> dict:
    progreso = diagnostico.progreso
    return {
        "evaluable": progreso.evaluable,
        "desde_numero_sorteo": progreso.desde_numero_sorteo,
        "total_sorteos_nuevos": progreso.total_sorteos_nuevos,
        "minimo_requerido": progreso.minimo_requerido,
        "faltantes": progreso.faltantes,
        "numero_sorteo_objetivo_minimo": progreso.numero_sorteo_objetivo_minimo,
    }


def _validar_diagnostico(codigo: str, reporte: ReportePrediccionJuego, diagnostico) -> DiagnosticoBloqueoJuego:
    if not isinstance(diagnostico, DiagnosticoBloqueoJuego):
        raise FalloConsultaEstadoError(
            f"Diagnostico inconsistente para '{codigo}': tipo inesperado", EXIT_REPORTE_INCONSISTENTE,
        )
    if diagnostico.juego_codigo != codigo:
        raise FalloConsultaEstadoError(
            f"Diagnostico inconsistente: '{diagnostico.juego_codigo}' devuelto para '{codigo}'",
            EXIT_REPORTE_INCONSISTENTE,
        )
    if (diagnostico.estado, diagnostico.motivos) != (reporte.estado, reporte.motivos):
        raise FalloConsultaEstadoError(
            f"Diagnostico inconsistente para '{codigo}': estado o motivos distintos del reporte",
            EXIT_REPORTE_INCONSISTENTE,
        )
    if diagnostico.desbloqueable is not False:
        raise FalloConsultaEstadoError(
            f"Diagnostico inconsistente para '{codigo}': desbloqueable", EXIT_REPORTE_INCONSISTENTE,
        )
    return diagnostico


def construir_reporte(
    resolver: ResolverEstadoPrediccion,
    diagnosticador: DiagnosticarEstadoPrediccion,
    revision_alembic: str,
) -> dict:
    """Consulta ambos juegos antes de construir el JSON, sin salida parcial."""
    juegos = []
    for codigo in sorted(JUEGOS_AUTORIZADOS_AE40):
        try:
            reporte = resolver.ejecutar(codigo)
            diagnostico = diagnosticador.ejecutar(codigo)
        except Exception as error:
            raise FalloConsultaEstadoError(
                f"Error evaluando '{codigo}': {type(error).__name__}: {error}",
                EXIT_FALLO_EVALUANDO_JUEGO,
            ) from error

        if not isinstance(reporte, ReportePrediccionJuego):
            raise FalloConsultaEstadoError(
                f"Reporte inconsistente para '{codigo}': tipo inesperado",
                EXIT_REPORTE_INCONSISTENTE,
            )
        if reporte.juego_codigo != codigo:
            raise FalloConsultaEstadoError(
                f"Reporte inconsistente: '{reporte.juego_codigo}' devuelto para '{codigo}'",
                EXIT_REPORTE_INCONSISTENTE,
            )
        if reporte.estado not in ESTADOS_BLOQUEADOS_AE45 or any(
            motivo not in ESTADOS_BLOQUEADOS_AE45 for motivo in reporte.motivos
        ):
            raise FalloConsultaEstadoError(
                f"Reporte inconsistente para '{codigo}': estado no bloqueado",
                EXIT_REPORTE_INCONSISTENTE,
            )
        if (
            reporte.combinaciones or reporte.numeros_fuertes or reporte.numeros_debiles
            or reporte.probabilidades or reporte.nivel_confianza is not None
            or reporte.resultados_observados or reporte.modelos_entrenados
            or reporte.predicciones_generadas or reporte.holdout_consumido
        ):
            raise FalloConsultaEstadoError(
                f"Reporte inconsistente para '{codigo}': contiene salida predictiva",
                EXIT_REPORTE_INCONSISTENTE,
            )
        diagnostico = _validar_diagnostico(codigo, reporte, diagnostico)
        juegos.append({
            "codigo": codigo,
            "estado": reporte.estado.value,
            "motivos": [motivo.value for motivo in reporte.motivos],
            "explicacion": reporte.explicacion,
            "disclaimer": reporte.disclaimer,
            "progreso": _progreso_json(diagnostico),
            "condiciones_pendientes": [condicion.value for condicion in diagnostico.condiciones_pendientes],
            "desbloqueable": diagnostico.desbloqueable,
        })

    return {"esquema": ESQUEMA_JSON, "alembic_revision": revision_alembic, "juegos": juegos}


def _abrir_conexion():
    from app.infrastructure.db.session import engine

    return engine.connect()


def _crear_consultas_desde(
    caso_uso_autorizacion: EvaluarAutorizacionOperativaML,
) -> tuple[ResolverEstadoPrediccion, DiagnosticarEstadoPrediccion]:
    """Ambos casos de uso comparten un unico adaptador de AE-41: una sola
    consulta agregada por juego."""
    autorizacion = _AutorizacionUnaVezPorJuego(caso_uso_autorizacion)
    return ResolverEstadoPrediccion(autorizacion), DiagnosticarEstadoPrediccion(autorizacion)


def _crear_consultas(session: Session) -> tuple[ResolverEstadoPrediccion, DiagnosticarEstadoPrediccion]:
    elegibilidad = EvaluarElegibilidadReaperturaML(
        JuegoRepositorySQLAlchemy(session),
        DisponibilidadHoldoutRepositorySQLAlchemy(session),
    )
    return _crear_consultas_desde(EvaluarAutorizacionOperativaML(elegibilidad))


def _catalogo_estados() -> CatalogoEstados:
    """Catalogo para validar reportes anteriores, construido desde los
    enums reales de AE-43/AE-46 -nunca una copia manual."""
    return CatalogoEstados(
        estados=tuple(estado.value for estado in EstadoPrediccionML),
        condiciones=tuple(condicion.value for condicion in CondicionDesbloqueoML),
        condiciones_sin_mecanismo=frozenset(c.value for c in CONDICIONES_SIN_MECANISMO_AE46),
        condicion_numeracion=CondicionDesbloqueoML.NUMERACION_HOLDOUT_VALIDA.value,
        condicion_minimo=CondicionDesbloqueoML.MINIMO_SORTEOS_NUEVOS.value,
        condicion_evidencia=CondicionDesbloqueoML.EVIDENCIA_CIENTIFICA_AE39.value,
        estado_no_go=EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO.value,
    )


def anadir_comparacion(reporte_actual: dict, anterior: dict) -> dict:
    """AE-48: esquema 1.2 = reporte 1.1 actual + comparacion descriptiva
    recalculada. Nunca copia la `comparacion` de un anterior 1.2."""
    comparacion = comparacion_estado_prediccion.comparar_reportes(anterior, reporte_actual, _catalogo_estados())
    return {**reporte_actual, "esquema": "1.2", "comparacion": comparacion}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consulta manual de bloqueo AE-45/47/48 (solo lectura)")
    parser.add_argument("--salida", help="Guarda los bytes exactos del JSON; nunca sobrescribe (AE-48)")
    parser.add_argument("--comparar", help="Reporte anterior 1.1/1.2 para una comparacion descriptiva (AE-48)")
    argumentos = parser.parse_args([] if argv is None else argv)

    anterior = None
    try:
        if argumentos.salida is not None:
            comparacion_estado_prediccion.validar_ruta_salida(argumentos.salida, argumentos.comparar)
        if argumentos.comparar is not None:
            anterior = comparacion_estado_prediccion.leer_reporte_anterior(argumentos.comparar, _catalogo_estados())
    except RutaSalidaNoPermitidaError as error:
        print(f"ERROR [codigo {EXIT_RUTA_SALIDA_NO_PERMITIDA}]: {error}", file=sys.stderr)
        return EXIT_RUTA_SALIDA_NO_PERMITIDA
    except ReporteAnteriorInvalidoError as error:
        print(f"ERROR [codigo {EXIT_ARCHIVO_ANTERIOR_INVALIDO}]: archivo anterior invalido: {error}", file=sys.stderr)
        return EXIT_ARCHIVO_ANTERIOR_INVALIDO

    try:
        conexion = _abrir_conexion()
    except Exception as error:
        print(f"ERROR [conexion]: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_FALLO_CONEXION

    try:
        conexion.execute(text("BEGIN TRANSACTION READ ONLY"))
        session = Session(bind=conexion)
        try:
            verificar_transaccion_solo_lectura(session)
            revision = verificar_revision_alembic(session)
            resolver, diagnosticador = _crear_consultas(session)
            reporte = construir_reporte(resolver, diagnosticador, revision)
        finally:
            session.close()
            conexion.execute(text("ROLLBACK"))
    except FalloAuditoriaOperativaError as error:
        print(f"ERROR [codigo {error.codigo_salida}]: {error}", file=sys.stderr)
        return error.codigo_salida
    except FalloConsultaEstadoError as error:
        print(f"ERROR [codigo {error.codigo_salida}]: {error}", file=sys.stderr)
        return error.codigo_salida
    except Exception as error:
        print(f"ERROR [inesperado]: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_FALLO_INESPERADO
    finally:
        conexion.close()

    if anterior is not None:
        reporte = anadir_comparacion(reporte, anterior)
        try:
            comparacion_estado_prediccion.validar_reporte_estado(reporte, _catalogo_estados())
        except ReporteAnteriorInvalidoError as error:
            print(f"ERROR [codigo {EXIT_REPORTE_INCONSISTENTE}]: reporte 1.2 incoherente: {error}", file=sys.stderr)
            return EXIT_REPORTE_INCONSISTENTE

    if argumentos.salida is None:
        print(json.dumps(reporte, indent=2, sort_keys=True, ensure_ascii=False))
        return EXIT_OK

    contenido = serializar_reporte(reporte)
    try:
        huella = comparacion_estado_prediccion.escribir_evidencia_atomica(contenido, argumentos.salida)
    except EscrituraEvidenciaError as error:
        print(f"ERROR [codigo {EXIT_FALLO_ESCRITURA_SALIDA}]: {error}", file=sys.stderr)
        return EXIT_FALLO_ESCRITURA_SALIDA
    sys.stdout.flush()
    sys.stdout.buffer.write(contenido)
    sys.stdout.buffer.flush()
    print(f"SHA-256 {huella}  {argumentos.salida}  ({len(contenido)} bytes)", file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
