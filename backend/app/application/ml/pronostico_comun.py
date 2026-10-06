"""
Piezas comunes de los pronosticos experimentales de Producto 2 (MiLoto y
ColorLoto), esquema `pronostico-experimental/2`.

El esquema 2 conserva los nombres de nivel superior que el almacen y las
pantallas ya usan con el esquema 1 (`clave_de_entrada`, `juego`,
`pronostico.objetivo`, `datos.corte`, `generacion`, huella y sello),
asi que el almacen no cambia. El esquema 1 (Baloto y Revancha,
`app.application.ml.pronostico_experimental`) se conserva intacto.

Modulo puro: sin reloj, red, base de datos ni escritura.
"""
from __future__ import annotations

import math
from types import MappingProxyType

from app.application.ml.propuesta_inferencia_prospectiva import AUTORIZA_EVALUACION
from app.application.ml.pronostico_experimental import ESTADO_DE_USO, PronosticoExperimentalError

ESQUEMA_ARTEFACTO_V2 = "pronostico-experimental/2"

DECISIONES_PREVIAS = MappingProxyType({
    "MILOTO": "AE-35: NO-GO temporal para MiLoto por muestra corta; no se reabre con este uso experimental",
    "COLORLOTO": "AE-35: ColorLoto pospuesto (objetivo de representacion distinto); no se reabre con este uso "
                 "experimental",
})


class DatosInsuficientesError(PronosticoExperimentalError):
    """El historico hasta el corte no alcanza los minimos declarados."""

    def __init__(self, codigo_juego: str, disponibles: int, requeridos: int, detalle: str):
        self.disponibles = disponibles
        self.requeridos = requeridos
        super().__init__(f"Datos insuficientes para {codigo_juego}: {disponibles} sorteos hasta el corte; hacen falta "
                         f"al menos {requeridos} ({detalle})")


def contrato_de_uso(nombre_juego: str) -> dict:
    return {
        "estado": ESTADO_DE_USO,
        "autorizado_por": "propietario del proyecto, Producto 2",
        "permite": [
            f"entrenar con el historico real de {nombre_juego} hasta un corte",
            "evaluar walk-forward frente a una referencia uniforme valida para el juego",
            "generar, conservar y consultar un pronostico experimental del siguiente sorteo",
            "comparar en lectura el pronostico guardado con el resultado observado",
        ],
        "no_permite": [
            "presentar el pronostico como ventaja predictiva acreditada ni como recomendacion de apuesta",
            "modificar el NO-GO de AE-39, el estado operativo de AE-41 ni los bloqueos R0",
            "cambiar AUTORIZA_EVALUACION, que sigue en False",
            "contar el pronostico como evidencia prospectiva o prerregistro de AE-52",
        ],
        "consecuencias": [
            "el historico usado puede incluir sorteos reservados como holdout; su uso exploratorio no los convierte "
            "en evidencia confirmatoria",
            "la fecha de generacion es la del reloj local de quien genera y no prueba anterioridad",
        ],
    }


def contexto(codigo_juego: str) -> dict:
    if AUTORIZA_EVALUACION is not False:
        raise PronosticoExperimentalError("AUTORIZA_EVALUACION debe seguir en False")
    return {"decision_previa": DECISIONES_PREVIAS[codigo_juego], "AUTORIZA_EVALUACION": AUTORIZA_EVALUACION,
            "no_go_ae39": "vigente para Baloto y Revancha; este uso no lo modifica",
            "estado_operativo_ae41": "sin cambios", "resultado_acreditado": False}


def redondear(valor: float, decimales: int) -> float:
    if not math.isfinite(valor):
        raise PronosticoExperimentalError("metrica no finita")
    return round(float(valor), decimales)


def comparar(modelo: dict, referencia: dict, menor_es_mejor: dict) -> dict:
    """`menor_es_mejor`: {metrica: bool}. Las dos primeras metricas son las
    principales del veredicto (en MiLoto y en ColorLoto, Log Loss y
    Brier de su propio objetivo). Descripcion sin prueba de significancia."""
    resultado = {}
    for metrica, menor in menor_es_mejor.items():
        a, b = modelo[metrica], referencia[metrica]
        resultado[metrica] = "empate" if a == b else ("modelo" if (a < b) == menor else "referencia_uniforme")
    principales = [resultado[m] for m in list(menor_es_mejor)[:2]]
    resultado["veredicto"] = ("el_modelo_supera_a_la_referencia_en_log_loss_y_brier"
                              if principales == ["modelo", "modelo"] else "el_modelo_no_supera_a_la_referencia_uniforme")
    return resultado


def procedencia(numeros_sorteo: list[int], fechas: list, corte: int, sha256_historico: str) -> dict:
    presentes = set(numeros_sorteo)
    huecos = [n for n in range(numeros_sorteo[0], numeros_sorteo[-1] + 1) if n not in presentes]
    return {"total_sorteos": len(numeros_sorteo), "primer_sorteo": numeros_sorteo[0],
            "primera_fecha": fechas[0].isoformat(), "ultimo_sorteo": numeros_sorteo[-1],
            "ultima_fecha": fechas[-1].isoformat(), "corte": corte,
            "huecos": {"cantidad": len(huecos), "primeros": huecos[:20]}, "sha256_historico": sha256_historico}


def bloques_consecutivos(objetivos: list[int], tamano: int) -> list[list[int]]:
    """Bloques cronologicos de `tamano` objetivos; el ultimo puede ser menor."""
    return [objetivos[i:i + tamano] for i in range(0, len(objetivos), tamano)]
