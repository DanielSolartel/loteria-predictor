"""
Auditoria operativa de bloqueo -Etapa AE-42, validada.

Nucleo puro, determinista, que construye el reporte de auditoria
JSON-serializable a partir de DOS `ReporteAutorizacionOperativaML`
YA CONSTRUIDOS por `EvaluarAutorizacionOperativaML` (AE-41, que a su
vez delega en `EvaluarElegibilidadReaperturaML` de AE-40) -uno por
BALOTO y otro por BALOTO_REVANCHA. Nunca reevalua la regla de
elegibilidad de AE-40: para comprobar la coherencia entre el estado
exterior de AE-41 y el reporte de elegibilidad anidado reutiliza la
unica funcion de traduccion de AE-41
(`evaluar_autorizacion_operativa_desde_elegibilidad`), sin duplicar su
mapeo, y luego traduce ambos reportes a una estructura estable,
versionada y serializable.

Nunca observa resultados historicos, nunca construye datasets,
nunca extrae features, nunca entrena modelos, nunca genera
predicciones, nunca persiste nada, nunca consulta repositorios ni
abre archivos ni conexiones. Permanece puro -no importa
scikit-learn, NumPy, SciPy, pandas, SQLAlchemy, FastAPI ni Jinja2.

El reporte JAMAS incluye: datos personales, credenciales, cadena de
conexion, UUID de juegos, filas individuales, numeros ganadores,
superbalota, color, fechas como senal, features ni targets -solo
`juego_codigo` (string autorizado), estados cerrados, y metadatos
agregados ya permitidos por AE-40/41 (conteos y numeros de sorteo).

`AUTORIZADO_PARA_PRERREGISTRO`, si aparece, nunca equivale a permiso
para ver resultados ganadores, entrenar, predecir ni desplegar -el
reporte lo distingue explicitamente de una auditoria simplemente
correcta mediante dos campos independientes: `auditoria_correcta`
(si el proceso completo se ejecuto sin errores) y
`autorizacion_para_prerregistro_detectada` (si algun juego alcanzo
ese estado) -nunca se debe confundir el primero con el segundo.

Prioridad del estado global: `bloqueado_numeracion_invalida` >
`autorizado_para_prerregistro_detectado` > `bloqueado_datos_insuficientes`.
Si un juego queda en `AUTORIZADO_PARA_PRERREGISTRO` y el otro en
`BLOQUEADO_NUMERACION_INVALIDA`, el estado global es
`bloqueado_numeracion_invalida`; `autorizacion_para_prerregistro_detectada`
puede seguir siendo `true` como dato informativo del otro juego, pero
no existe autorizacion global ni se dispara ninguna accion automatica."""
from __future__ import annotations

from app.application.ml.autorizacion_operativa import evaluar_autorizacion_operativa_desde_elegibilidad
from app.application.ml.reapertura import JUEGOS_AUTORIZADOS_AE40, PROXIMO_HOLDOUT_INICIO
from app.application.ml.tipos import EstadoAutorizacionOperativaML, ReporteAutorizacionOperativaML

VERSION_ESQUEMA_AUDITORIA_OPERATIVA = "1.0"
"""Version del esquema del JSON de auditoria -incrementar solo ante
un cambio de forma incompatible; anadir campos nuevos no
retrocompatibles requiere una version mayor."""


class ReporteAutorizacionInconsistenteError(ValueError):
    """El caso de uso de AE-41 devolvio un reporte cuyo `juego_codigo`
    no es uno de los dos juegos autorizados, o los dos reportes
    recibidos corresponden al mismo juego (mezcla de juegos a nivel
    de auditoria), o un reporte cuyo reporte de elegibilidad anidado de
    AE-40 pertenece a otro juego o tiene un estado incoherente con el
    estado exterior -la auditoria se detiene sin producir un reporte
    parcial."""


def _verificar_coherencia_con_elegibilidad(reporte: ReporteAutorizacionOperativaML) -> None:
    """Comprueba que el reporte exterior de AE-41 y su reporte de
    elegibilidad anidado de AE-40 describen el mismo juego y la misma
    decision. El estado esperado se obtiene con la unica funcion de
    traduccion de AE-41 -nunca con un mapeo duplicado aqui. Sin reporte
    anidado, el unico estado exterior coherente es
    `BLOQUEADO_NUMERACION_INVALIDA` (el gate de AE-40 no emitio un reporte
    normal); `ReporteAutorizacionOperativaML` ya lo impone al construirse
    y aqui se comprueba de nuevo como defensa en profundidad."""
    elegibilidad = reporte.reporte_elegibilidad
    if elegibilidad is None:
        if reporte.estado != EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA:
            raise ReporteAutorizacionInconsistenteError(
                f"'{reporte.juego_codigo}': estado exterior '{reporte.estado.value}' sin reporte "
                f"de elegibilidad anidado -solo BLOQUEADO_NUMERACION_INVALIDA puede carecer de el"
            )
        return
    if elegibilidad.juego_codigo != reporte.juego_codigo:
        raise ReporteAutorizacionInconsistenteError(
            f"El reporte de elegibilidad anidado corresponde a '{elegibilidad.juego_codigo}', "
            f"pero el reporte exterior corresponde a '{reporte.juego_codigo}'"
        )
    estado_esperado = evaluar_autorizacion_operativa_desde_elegibilidad(elegibilidad).estado
    if reporte.estado != estado_esperado:
        raise ReporteAutorizacionInconsistenteError(
            f"'{reporte.juego_codigo}': estado exterior '{reporte.estado.value}' incoherente con el "
            f"estado de elegibilidad de AE-40 '{elegibilidad.estado.value}' (se esperaba "
            f"'{estado_esperado.value}')"
        )


def _metadatos_disponibilidad(reporte: ReporteAutorizacionOperativaML) -> dict | None:
    """`None` UNICAMENTE cuando el gate de AE-40 no llego a producir
    un reporte normal (estado `BLOQUEADO_NUMERACION_INVALIDA`).
    Nunca incluye UUID, numeros ganadores, superbalota, color ni
    fechas -solo los agregados que AE-40 ya expone."""
    re = reporte.reporte_elegibilidad
    if re is None:
        return None
    return {
        "total_sorteos_nuevos": re.total_sorteos_nuevos,
        "numero_sorteo_minimo": re.numero_sorteo_minimo,
        "numero_sorteo_maximo": re.numero_sorteo_maximo,
        "minimo_sorteos_nuevos_requeridos": re.minimo_sorteos_nuevos_requeridos,
        "numero_sorteo_objetivo_minimo": re.numero_sorteo_objetivo_minimo,
        "numeracion_contigua": re.numeracion_contigua,
    }


def _resultado_juego(reporte: ReporteAutorizacionOperativaML) -> dict:
    return {
        "juego_codigo": reporte.juego_codigo,
        "estado": reporte.estado.value,
        "motivo": reporte.motivo,
        "reporte_elegibilidad_disponible": reporte.reporte_elegibilidad is not None,
        "metadatos_disponibilidad": _metadatos_disponibilidad(reporte),
        "resultados_observados": reporte.resultados_observados,
        "modelos_entrenados": reporte.modelos_entrenados,
        "predicciones_generadas": reporte.predicciones_generadas,
        "holdout_consumido": reporte.holdout_consumido,
    }


def construir_reporte_auditoria_operativa(
    reporte_baloto: ReporteAutorizacionOperativaML,
    reporte_baloto_revancha: ReporteAutorizacionOperativaML,
    instante_utc: str,
) -> dict:
    """Unica funcion publica de este modulo. Recibe los DOS reportes
    YA CONSTRUIDOS (por el adaptador CLI, a partir de
    `EvaluarAutorizacionOperativaML` real) y produce el diccionario
    JSON-serializable del reporte de auditoria. `instante_utc` debe
    ser una cadena ISO 8601 ya construida por el llamador -este
    modulo nunca consulta el reloj del sistema, permanece
    determinista dada la misma entrada.

    Lanza `ReporteAutorizacionInconsistenteError` si algun
    `juego_codigo` no es uno de los dos autorizados, o si ambos
    reportes corresponden al mismo juego, o si algun reporte no es
    coherente con su reporte de elegibilidad anidado (ver
    `_verificar_coherencia_con_elegibilidad`) -nunca produce un reporte
    parcial o ambiguo en ese caso. El bloqueo por numeracion invalida
    tiene prioridad en `estado_global` (ver el docstring del modulo)."""
    reportes = (reporte_baloto, reporte_baloto_revancha)

    for reporte in reportes:
        if reporte.juego_codigo not in JUEGOS_AUTORIZADOS_AE40:
            raise ReporteAutorizacionInconsistenteError(
                f"'{reporte.juego_codigo}' no es uno de los juegos autorizados "
                f"{sorted(JUEGOS_AUTORIZADOS_AE40)}"
            )
        _verificar_coherencia_con_elegibilidad(reporte)

    if reporte_baloto.juego_codigo == reporte_baloto_revancha.juego_codigo:
        raise ReporteAutorizacionInconsistenteError(
            f"Ambos reportes corresponden al mismo juego "
            f"('{reporte_baloto.juego_codigo}') -se requiere exactamente un reporte "
            f"por cada uno de {sorted(JUEGOS_AUTORIZADOS_AE40)}, nunca mezclados"
        )

    resultados = {
        reporte.juego_codigo: _resultado_juego(reporte)
        for reporte in reportes
    }

    autorizacion_detectada = any(
        reporte.estado == EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO
        for reporte in reportes
    )
    numeracion_invalida_detectada = any(
        reporte.estado == EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA
        for reporte in reportes
    )

    # El bloqueo por numeracion invalida prevalece: una autorizacion detectada
    # en el otro juego nunca produce un estado global autorizado.
    if numeracion_invalida_detectada:
        estado_global = "bloqueado_numeracion_invalida"
    elif autorizacion_detectada:
        estado_global = "autorizado_para_prerregistro_detectado"
    else:
        estado_global = "bloqueado_datos_insuficientes"

    return {
        "version_esquema": VERSION_ESQUEMA_AUDITORIA_OPERATIVA,
        "instante_utc": instante_utc,
        "etapa": "AE-42",
        "proximo_holdout_inicio": PROXIMO_HOLDOUT_INICIO,
        "resultados": resultados,
        "estado_global": estado_global,
        "auditoria_correcta": True,
        "autorizacion_para_prerregistro_detectada": autorizacion_detectada,
    }
