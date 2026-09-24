"""
Bloqueo operativo centralizado del desarrollo predictivo -Etapa
AE-41, validada.

Nucleo puro, determinista, que traduce el resultado del gate ya
validado de AE-40 (`ReporteElegibilidadReaperturaML`) en una
politica de autorizacion operativa explicita y comprobable -nunca
reevalua la regla de elegibilidad de AE-40, unicamente la traduce.
No existe mas que UNA fuente funcional de verdad sobre elegibilidad:
`app.application.ml.reapertura.evaluar_elegibilidad_reapertura_ml`;
este modulo nunca reimplementa esa logica.

Nunca observa resultados historicos, nunca construye datasets,
nunca extrae features, nunca entrena modelos, nunca genera
probabilidades ni predicciones, nunca persiste nada, nunca consulta
repositorios ni abre archivos. Permanece puro -no importa
scikit-learn, NumPy, SciPy, pandas, SQLAlchemy, FastAPI ni Jinja2.

`AUTORIZADO_PARA_PRERREGISTRO` nunca significa autorizacion para
entrenar, para observar resultados, para generar predicciones, ni
para desplegar -unicamente que una etapa FUTURA e INDEPENDIENTE
podria iniciar un prerregistro experimental, tras validacion humana
expresa. AE-41 nunca ejecuta automaticamente esa evaluacion futura."""
from __future__ import annotations

from app.application.ml.tipos import (
    EstadoAutorizacionOperativaML,
    EstadoElegibilidadReaperturaML,
    ReporteAutorizacionOperativaML,
    ReporteElegibilidadReaperturaML,
)


def evaluar_autorizacion_operativa_desde_elegibilidad(
    reporte_elegibilidad: ReporteElegibilidadReaperturaML,
) -> ReporteAutorizacionOperativaML:
    """Traduce un `ReporteElegibilidadReaperturaML` YA CONSTRUIDO por
    el gate de AE-40 (`evaluar_elegibilidad_reapertura_ml`, nunca
    reevaluado aqui) al estado de autorizacion operativa de AE-41.
    Cubre unicamente el camino en el que el gate de AE-40 produjo un
    reporte normal -`NO_ELEGIBLE_DATOS_INSUFICIENTES` se traduce a
    `BLOQUEADO_DATOS_INSUFICIENTES`; `ELEGIBLE_PARA_PRERREGISTRO` se
    traduce a `AUTORIZADO_PARA_PRERREGISTRO`. El tercer estado
    (`BLOQUEADO_NUMERACION_INVALIDA`) se construye en el caso de uso
    cuando el gate de AE-40 lanza `DisponibilidadHoldoutInvalidaError`
    en vez de producir un reporte -ver
    `construir_reporte_bloqueado_por_numeracion_invalida`."""
    if reporte_elegibilidad.estado == EstadoElegibilidadReaperturaML.ELEGIBLE_PARA_PRERREGISTRO:
        estado = EstadoAutorizacionOperativaML.AUTORIZADO_PARA_PRERREGISTRO
        motivo = (
            f"{reporte_elegibilidad.total_sorteos_nuevos} sorteos nuevos contiguos desde "
            f"{reporte_elegibilidad.proximo_holdout_inicio} -alcanza el minimo de "
            f"{reporte_elegibilidad.minimo_sorteos_nuevos_requeridos}. Esto NO autoriza "
            f"entrenamiento, observacion de resultados, prediccion ni despliegue -unicamente "
            f"que una etapa futura independiente podria iniciar un prerregistro tras "
            f"validacion humana expresa."
        )
    else:
        estado = EstadoAutorizacionOperativaML.BLOQUEADO_DATOS_INSUFICIENTES
        motivo = (
            f"{reporte_elegibilidad.total_sorteos_nuevos} sorteos nuevos, por debajo del "
            f"minimo requerido de {reporte_elegibilidad.minimo_sorteos_nuevos_requeridos} "
            f"-ninguna operacion predictiva nueva queda autorizada."
        )

    return ReporteAutorizacionOperativaML(
        juego_codigo=reporte_elegibilidad.juego_codigo,
        estado=estado,
        motivo=motivo,
        reporte_elegibilidad=reporte_elegibilidad,
    )


def construir_reporte_bloqueado_por_numeracion_invalida(
    juego_codigo: str, motivo_original: str,
) -> ReporteAutorizacionOperativaML:
    """Construye el reporte de bloqueo cuando el gate de AE-40 lanzo
    `DisponibilidadHoldoutInvalidaError` -nunca cuando produjo un
    reporte normal. Cubre tanto inconsistencias de numeracion
    (huecos, duplicados, inicio distinto de 2706, conteos
    incoherentes) como una discrepancia entre el juego solicitado y
    el juego devuelto por el repositorio -ambos casos representan la
    misma categoria: el gate de AE-40 detecto una inconsistencia
    estructural antes de poder emitir una decision normal, y por
    tanto AE-41 bloquea sin excepcion."""
    return ReporteAutorizacionOperativaML(
        juego_codigo=juego_codigo,
        estado=EstadoAutorizacionOperativaML.BLOQUEADO_NUMERACION_INVALIDA,
        motivo=(
            f"El gate de AE-40 detecto una inconsistencia estructural antes de poder "
            f"emitir una decision normal: {motivo_original}. Ninguna operacion predictiva "
            f"nueva queda autorizada."
        ),
        reporte_elegibilidad=None,
    )
