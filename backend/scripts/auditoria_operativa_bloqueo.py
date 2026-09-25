#!/usr/bin/env python3
"""
Auditoria operativa de bloqueo -Etapa AE-42, validada.

Comando de solo lectura, ejecutado UNICAMENTE por peticion explicita
del operador -nunca una tarea periodica, endpoint, pantalla ni
disparador automatico. Invoca los casos de uso REALES de produccion
(`EvaluarElegibilidadReaperturaML` de AE-40, `EvaluarAutorizacionOperativaML`
de AE-41) para BALOTO y BALOTO_REVANCHA por separado, dentro de una
transaccion PostgreSQL de solo lectura verificada explicitamente, y
escribe un reporte JSON externo al repositorio.

Separacion deliberada: `ejecutar_auditoria_con_sesion` es la logica
orquestadora COMPROBABLE (recibe una sesion y repositorios ya
construidos, nunca abre una conexion por su cuenta); `main()` es el
adaptador CLI/SQL que construye la sesion real, verifica la
transaccion de solo lectura y la revision Alembic, y siempre cierra
con rollback -nunca commit, flush, ni ninguna escritura.

Nunca lee numeros ganadores, superbalota, color ni fechas como
senal. Nunca construye datasets, nunca extrae features, nunca
entrena, nunca genera predicciones, nunca persiste modelos, metricas
ni predicciones. Si algun juego alcanza `AUTORIZADO_PARA_PRERREGISTRO`,
este comando UNICAMENTE lo informa en el JSON -nunca inicia un
prerregistro, nunca lee resultados, nunca entrena ni predice.

Codigos de salida (todos distintos de cero indican fallo -nunca se
confunden con una auditoria correcta de resultado negativo, que
siempre sale con codigo 0):
    0  Auditoria ejecutada correctamente (bloqueo o, si aparece,
       autorizacion para prerregistro UNICAMENTE informada).
    1  Fallo inesperado no clasificado.
    2  Fallo de conexion a PostgreSQL.
    3  Revision Alembic de la base no coincide con la esperada por
       este codigo.
    4  La transaccion no quedo confirmada como de solo lectura
       (`transaction_read_only` distinto de `on`).
    5  Estructura de reporte inconsistente (mezcla de juegos, juego
       no autorizado, reporte de elegibilidad anidado de otro juego
       o estado exterior incoherente con el de AE-40) detectada por
       `construir_reporte_auditoria_operativa`.
    6  Excepcion inesperada al evaluar la autorizacion operativa de
       alguno de los dos juegos -nunca se produce un reporte parcial
       con solo el otro juego."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.ml.auditoria_operativa_bloqueo import (
    ReporteAutorizacionInconsistenteError,
    construir_reporte_auditoria_operativa,
)
from app.application.ml.reapertura import JUEGOS_AUTORIZADOS_AE40
from app.application.ml.tipos import ReporteAutorizacionOperativaML
from app.application.use_cases.evaluar_autorizacion_operativa_ml import EvaluarAutorizacionOperativaML
from app.application.use_cases.evaluar_elegibilidad_reapertura_ml import EvaluarElegibilidadReaperturaML

EXIT_OK = 0
EXIT_FALLO_INESPERADO = 1
EXIT_FALLO_CONEXION = 2
EXIT_REVISION_ALEMBIC_INESPERADA = 3
EXIT_TRANSACCION_NO_SOLO_LECTURA = 4
EXIT_REPORTE_INCONSISTENTE = 5
EXIT_FALLO_EVALUANDO_JUEGO = 6


class FalloAuditoriaOperativaError(Exception):
    """Excepcion propia de este script, con un codigo de salida
    explicito asociado -nunca se traduce a un JSON de exito ni a
    codigo de salida 0."""

    def __init__(self, mensaje: str, codigo_salida: int):
        super().__init__(mensaje)
        self.codigo_salida = codigo_salida


def verificar_transaccion_solo_lectura(session: Session) -> None:
    """Confirma explicitamente `transaction_read_only=on` -nunca se
    asume por el simple hecho de haber ejecutado `BEGIN
    TRANSACTION READ ONLY`."""
    valor = session.execute(text("SHOW transaction_read_only")).scalar()
    if str(valor).strip().lower() != "on":
        raise FalloAuditoriaOperativaError(
            f"transaction_read_only={valor!r}, se esperaba 'on' -la auditoria "
            f"se detiene antes de cualquier consulta de negocio",
            EXIT_TRANSACCION_NO_SOLO_LECTURA,
        )


def obtener_revision_alembic_actual(session: Session) -> str | None:
    """Lee unicamente `version_num` de `alembic_version` -ninguna
    otra columna ni tabla de la aplicacion."""
    try:
        return session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception as error:
        raise FalloAuditoriaOperativaError(
            f"No se pudo leer la revision Alembic actual: {error}",
            EXIT_REVISION_ALEMBIC_INESPERADA,
        ) from error


def obtener_revision_alembic_esperada() -> str:
    """Determina el head de Alembic a partir de los scripts del
    propio repositorio -nunca hardcodeado como un numero magico
    independiente, para no desincronizarse silenciosamente si se
    agregan migraciones futuras."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    aqui = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(aqui, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(aqui, "alembic"))
    script_dir = ScriptDirectory.from_config(cfg)
    head = script_dir.get_current_head()
    if head is None:
        raise FalloAuditoriaOperativaError(
            "No se pudo determinar la revision Alembic esperada desde los scripts locales",
            EXIT_REVISION_ALEMBIC_INESPERADA,
        )
    return head


def verificar_revision_alembic(session: Session) -> str:
    esperada = obtener_revision_alembic_esperada()
    actual = obtener_revision_alembic_actual(session)
    if actual != esperada:
        raise FalloAuditoriaOperativaError(
            f"Revision Alembic de la base ({actual!r}) no coincide con la esperada "
            f"por este codigo ({esperada!r})",
            EXIT_REVISION_ALEMBIC_INESPERADA,
        )
    return actual


def _evaluar_juego(caso_autorizacion: EvaluarAutorizacionOperativaML, codigo_juego: str) -> ReporteAutorizacionOperativaML:
    try:
        return caso_autorizacion.ejecutar(codigo_juego)
    except Exception as error:
        raise FalloAuditoriaOperativaError(
            f"Excepcion inesperada evaluando la autorizacion operativa de '{codigo_juego}': "
            f"{type(error).__name__}: {error}",
            EXIT_FALLO_EVALUANDO_JUEGO,
        ) from error


def ejecutar_auditoria_con_sesion(
    caso_autorizacion: EvaluarAutorizacionOperativaML,
    instante_utc: str,
) -> dict:
    """Logica orquestadora COMPROBABLE: recibe un
    `EvaluarAutorizacionOperativaML` YA CONSTRUIDO (con sus propios
    repositorios reales o fakes, segun quien llame) y produce el
    reporte de auditoria completo. Una llamada por juego -BALOTO y
    BALOTO_REVANCHA, en ese orden, nunca mezclados. Nunca abre una
    conexion ni una sesion por su cuenta -eso es responsabilidad
    exclusiva de `main()`."""
    juegos_en_orden = sorted(JUEGOS_AUTORIZADOS_AE40)  # orden deterministico: BALOTO, BALOTO_REVANCHA
    reporte_baloto = _evaluar_juego(caso_autorizacion, juegos_en_orden[0])
    reporte_revancha = _evaluar_juego(caso_autorizacion, juegos_en_orden[1])

    try:
        return construir_reporte_auditoria_operativa(reporte_baloto, reporte_revancha, instante_utc)
    except ReporteAutorizacionInconsistenteError as error:
        raise FalloAuditoriaOperativaError(
            f"Estructura de reporte de auditoria inconsistente: {error}",
            EXIT_REPORTE_INCONSISTENTE,
        ) from error


def escribir_reporte_atomico(reporte: dict, ruta: str) -> None:
    """Escribe el JSON de forma atomica: primero a un archivo
    temporal en el MISMO directorio que la ruta destino, luego
    `os.replace` -un fallo a mitad de la escritura nunca deja un
    reporte parcial en la ruta destino, porque el archivo destino
    solo se reemplaza tras completarse la escritura por completo."""
    directorio = os.path.dirname(os.path.abspath(ruta)) or "."
    os.makedirs(directorio, exist_ok=True)
    fd, ruta_temporal = tempfile.mkstemp(dir=directorio, prefix=".auditoria-ae42-", suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(ruta_temporal, ruta)
    except BaseException:
        try:
            os.remove(ruta_temporal)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Auditoria operativa de bloqueo -Etapa AE-42, PROVISIONAL. "
        "Solo lectura; invoca los casos de uso reales de AE-40/41 para BALOTO y BALOTO_REVANCHA."
    )
    parser.add_argument(
        "--salida", metavar="RUTA",
        help="Ruta del archivo JSON de salida (fuera del repositorio). Si se omite, "
        "el reporte se imprime por stdout y no se escribe a disco.",
    )
    args = parser.parse_args(argv)

    instante_utc = datetime.now(timezone.utc).isoformat()

    try:
        from app.infrastructure.db.session import engine
    except Exception as error:
        print(f"ERROR [conexion]: no se pudo preparar el motor de base de datos: {error}", file=sys.stderr)
        return EXIT_FALLO_CONEXION

    try:
        conexion = engine.connect()
    except Exception as error:
        print(f"ERROR [conexion]: no se pudo conectar a PostgreSQL: {error}", file=sys.stderr)
        return EXIT_FALLO_CONEXION

    try:
        conexion.execute(text("BEGIN TRANSACTION READ ONLY"))
        session = Session(bind=conexion)
        try:
            verificar_transaccion_solo_lectura(session)
            revision_actual = verificar_revision_alembic(session)

            from app.application.interfaces.disponibilidad_holdout_repository import DisponibilidadHoldoutRepository  # noqa: F401
            from app.infrastructure.repositories.disponibilidad_holdout_repository_sqlalchemy import (
                DisponibilidadHoldoutRepositorySQLAlchemy,
            )
            from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy

            juego_repo = JuegoRepositorySQLAlchemy(session)
            disponibilidad_repo = DisponibilidadHoldoutRepositorySQLAlchemy(session)
            caso_elegibilidad = EvaluarElegibilidadReaperturaML(juego_repo, disponibilidad_repo)
            caso_autorizacion = EvaluarAutorizacionOperativaML(caso_elegibilidad)

            reporte = ejecutar_auditoria_con_sesion(caso_autorizacion, instante_utc)
            reporte["alembic_revision"] = revision_actual
        finally:
            session.close()
            conexion.execute(text("ROLLBACK"))
    except FalloAuditoriaOperativaError as error:
        print(f"ERROR [codigo {error.codigo_salida}]: {error}", file=sys.stderr)
        return error.codigo_salida
    except Exception as error:
        print(f"ERROR [inesperado]: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_FALLO_INESPERADO
    finally:
        conexion.close()

    if args.salida:
        try:
            escribir_reporte_atomico(reporte, args.salida)
        except Exception as error:
            print(f"ERROR [inesperado]: no se pudo escribir el reporte en '{args.salida}': {error}", file=sys.stderr)
            return EXIT_FALLO_INESPERADO
        print(f"Auditoria completada. Reporte escrito en: {args.salida}", file=sys.stderr)
    else:
        print(json.dumps(reporte, indent=2, ensure_ascii=False, sort_keys=True))

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
