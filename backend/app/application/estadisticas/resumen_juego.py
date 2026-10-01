"""
Resumen estadistico por juego -Producto 1.

Una vista de entrada por juego: ultimo sorteo disponible, cantidad y
periodo de sorteos, corte aplicado, frescura respecto de la fecha de
consulta, huecos de numeracion, frecuencias, atrasos y distribuciones.
Todo se calcula con las funciones existentes del motor
(`app/application/estadisticas/motor/`); este modulo solo las combina.

Las reglas salen de la clase de dominio de cada juego (rango, cantidad,
superbalota, colores), nunca de constantes de Baloto: MiLoto usa 1..39
sin superbalota y ColorLoto sus pares numero-color. Las frecuencias y
los atrasos son descriptivos: no son probabilidades del proximo sorteo.

Modulo puro: la fecha de consulta la aporta quien llama.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from app.application.estadisticas.motor.atrasos import (
    calcular_atrasos_colores,
    calcular_atrasos_numeros,
    calcular_atrasos_numeros_colorloto,
    calcular_atrasos_superbalota,
)
from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.motor.distribuciones import (
    calcular_distribucion_altos_bajos,
    calcular_distribucion_altos_bajos_colorloto,
    calcular_distribucion_decenas,
    calcular_distribucion_pares_impares,
    calcular_distribucion_pares_impares_colorloto,
    calcular_maximo_repeticion_color_por_sorteo,
)
from app.application.estadisticas.motor.frecuencia import (
    calcular_frecuencia_colores,
    calcular_frecuencia_numeros,
    calcular_frecuencia_numeros_colorloto,
    calcular_frecuencia_pares_numero_color,
    calcular_frecuencia_superbalota,
)
from app.application.estadisticas.motor.generales import detectar_huecos_serie_historica

DIAS_PARA_CONSIDERAR_DESACTUALIZADO = 7
"""Baloto, Revancha y ColorLoto se sortean varias veces por semana y
MiLoto con mas frecuencia: sin sorteos en una semana el historico
probablemente no esta sincronizado."""

CANTIDAD_DESTACADOS = 5


def _frecuencias(lista, destacados: int = CANTIDAD_DESTACADOS) -> dict:
    filas = [{"valor": f.valor, "apariciones": f.apariciones, "frecuencia_relativa": f.frecuencia_relativa}
             for f in lista]
    mas = sorted(filas, key=lambda f: (-f["apariciones"], _orden(f["valor"])))
    menos = sorted(filas, key=lambda f: (f["apariciones"], _orden(f["valor"])))
    return {"todas": sorted(filas, key=lambda f: _orden(f["valor"])), "mas_frecuentes": mas[:destacados],
            "menos_frecuentes": menos[:destacados]}


def _orden(valor: str):
    return (0, int(valor), "") if valor.isdigit() else (1, 0, valor)


def _atrasos(lista, destacados: int = CANTIDAD_DESTACADOS) -> dict:
    filas = [{"valor": a.valor, "atraso": a.atraso, "ultimo_sorteo": a.ultimo_sorteo_aparicion} for a in lista]
    nunca = [f["valor"] for f in filas if f["atraso"] is None]
    mayores = sorted((f for f in filas if f["atraso"] is not None), key=lambda f: (-f["atraso"], _orden(f["valor"])))
    return {"mayores": mayores[:destacados], "nunca_observados": nunca}


def _distribucion(lista) -> list[dict]:
    return [{"valor": f.valor, "sorteos": f.apariciones, "frecuencia_relativa": f.frecuencia_relativa}
            for f in lista]


def porcentaje_de_numeros_extraidos(apariciones: int, sorteos: int, numeros_por_sorteo: int) -> float | None:
    """Porcentaje de TODOS los numeros extraidos que cae en una franja:
    apariciones / (sorteos x numeros por sorteo) x 100. None sin sorteos.
    Ejemplo: 736 apariciones en 636 sorteos de 5 numeros -> 23.14 %."""
    total = sorteos * numeros_por_sorteo
    return None if total <= 0 else 100.0 * apariciones / total


def _decenas(lista, sorteos: int, numeros_por_sorteo: int) -> dict:
    """Conserva los campos existentes (`sorteos` y `frecuencia_relativa`,
    que en las decenas son apariciones y apariciones por sorteo) y anade
    el porcentaje sobre el total de numeros extraidos."""
    filas = []
    for fila in _distribucion(lista):
        filas.append({**fila, "apariciones": fila["sorteos"],
                      "porcentaje_de_numeros_extraidos": porcentaje_de_numeros_extraidos(
                          fila["sorteos"], sorteos, numeros_por_sorteo)})
    return {"filas": filas, "denominador": {"sorteos": sorteos, "numeros_por_sorteo": numeros_por_sorteo,
                                            "numeros_extraidos": sorteos * numeros_por_sorteo}}


def evaluar_frescura(ultima_fecha: date | None, hoy: date) -> dict:
    """Frescura del historico respecto de `hoy` (fecha de consulta)."""
    if ultima_fecha is None:
        return {"estado": "sin_datos", "dias_desde_el_ultimo_sorteo": None,
                "mensaje": "No hay sorteos cargados para este juego. Sincroniza desde Importación."}
    dias = (hoy - ultima_fecha).days
    if dias > DIAS_PARA_CONSIDERAR_DESACTUALIZADO:
        return {"estado": "desactualizado", "dias_desde_el_ultimo_sorteo": dias,
                "mensaje": f"El último sorteo cargado es de hace {dias} días: el histórico puede estar "
                           "desactualizado. Sincroniza desde Importación antes de sacar conclusiones."}
    return {"estado": "al_dia", "dias_desde_el_ultimo_sorteo": dias,
            "mensaje": f"Último sorteo cargado hace {dias} días."}


def _cabecera(codigo_juego, nombre, reglas, todos, filtrados, hasta_numero_sorteo, hoy) -> dict:
    ultimo = filtrados[-1] if filtrados else None
    primero = filtrados[0] if filtrados else None
    huecos = detectar_huecos_serie_historica([r.numero_sorteo for r in filtrados])
    return {
        "codigo_juego": codigo_juego,
        "nombre": nombre,
        "reglas": reglas,
        "total_sorteos": len(filtrados),
        "total_sorteos_sin_corte": len(todos),
        "corte": {"hasta_numero_sorteo": hasta_numero_sorteo,
                  "descripcion": (f"hasta el sorteo {hasta_numero_sorteo}" if hasta_numero_sorteo is not None
                                  else "todo el histórico cargado")},
        "periodo": None if ultimo is None else {
            "primer_sorteo": primero.numero_sorteo, "primera_fecha": primero.fecha.isoformat(),
            "ultimo_sorteo": ultimo.numero_sorteo, "ultima_fecha": ultimo.fecha.isoformat(),
        },
        "ultimo_sorteo_disponible": None if not todos else {
            "numero_sorteo": todos[-1].numero_sorteo, "fecha": todos[-1].fecha.isoformat()},
        "frescura": evaluar_frescura(todos[-1].fecha if todos else None, hoy),
        "huecos": {"cantidad": len(huecos.huecos), "primeros": list(huecos.huecos[:20]),
                   "cobertura": huecos.porcentaje_cobertura},
        "consultado_el": hoy.isoformat(),
    }


def resumen_juego_numerico(resultados: Sequence, *, codigo_juego: str, nombre: str, rango: tuple[int, int],
                           cantidad_numeros: int, rango_superbalota: tuple[int, int] | None, hoy: date,
                           hasta_numero_sorteo: int | None = None) -> dict:
    """MiLoto, Baloto o Revancha (`ResultadoNumerico`)."""
    todos = sorted(resultados, key=lambda r: r.numero_sorteo)
    filtrados = filtrar_por_corte_temporal(todos, hasta_numero_sorteo)
    lo, hi = rango
    reglas = {"tipo": "numeros", "rango": [lo, hi], "cantidad_numeros": cantidad_numeros,
              "superbalota": list(rango_superbalota) if rango_superbalota else None}
    resumen = _cabecera(codigo_juego, nombre, reglas, todos, filtrados, hasta_numero_sorteo, hoy)
    if not filtrados:
        resumen["estadisticas"] = None
        return resumen
    ultimo = filtrados[-1]
    resumen["ultimo_resultado"] = {"numeros": list(ultimo.numeros), "superbalota": ultimo.superbalota}
    estadisticas = {
        "frecuencia_numeros": _frecuencias(calcular_frecuencia_numeros(filtrados, lo, hi)),
        "atrasos_numeros": _atrasos(calcular_atrasos_numeros(filtrados, lo, hi)),
        "pares_impares": _distribucion(calcular_distribucion_pares_impares(filtrados, cantidad_numeros)),
        "altos_bajos": _distribucion(calcular_distribucion_altos_bajos(filtrados, lo, hi, cantidad_numeros)),
        "decenas": _distribucion(calcular_distribucion_decenas(filtrados, lo, hi)),
        "decenas_sobre_numeros_extraidos": _decenas(calcular_distribucion_decenas(filtrados, lo, hi),
                                                    len(filtrados), cantidad_numeros),
        "superbalota": None,
    }
    if rango_superbalota is not None:
        slo, shi = rango_superbalota
        con_superbalota = [r for r in filtrados if r.superbalota is not None]
        estadisticas["superbalota"] = {
            "frecuencia": _frecuencias(calcular_frecuencia_superbalota(con_superbalota, slo, shi), 3),
            "atrasos": _atrasos(calcular_atrasos_superbalota(con_superbalota, slo, shi), 3),
        }
    resumen["estadisticas"] = estadisticas
    return resumen


def resumen_juego_colorloto(resultados: Sequence, *, nombre: str, rango: tuple[int, int], cantidad_balotas: int,
                            colores: Sequence[str], hoy: date, hasta_numero_sorteo: int | None = None) -> dict:
    """ColorLoto (`ResultadoColorLoto`): numeros 1..7, colores y pares."""
    todos = sorted(resultados, key=lambda r: r.numero_sorteo)
    filtrados = filtrar_por_corte_temporal(todos, hasta_numero_sorteo)
    lo, hi = rango
    reglas = {"tipo": "colorloto", "rango": [lo, hi], "cantidad_balotas": cantidad_balotas,
              "colores": list(colores), "permite_repeticion": True}
    resumen = _cabecera("COLORLOTO", nombre, reglas, todos, filtrados, hasta_numero_sorteo, hoy)
    if not filtrados:
        resumen["estadisticas"] = None
        return resumen
    resumen["ultimo_resultado"] = {"pares": [[n, c] for n, c in filtrados[-1].pares]}
    usados = sorted({c for r in filtrados for _, c in r.pares})
    paleta = list(colores) + [c for c in usados if c not in colores]
    resumen["estadisticas"] = {
        "frecuencia_colores": _frecuencias(calcular_frecuencia_colores(filtrados, paleta), len(paleta)),
        "frecuencia_numeros": _frecuencias(calcular_frecuencia_numeros_colorloto(filtrados, lo, hi), 3),
        "frecuencia_pares": _frecuencias(calcular_frecuencia_pares_numero_color(filtrados, lo, hi, paleta)),
        "atrasos_colores": _atrasos(calcular_atrasos_colores(filtrados, paleta), len(paleta)),
        "atrasos_numeros": _atrasos(calcular_atrasos_numeros_colorloto(filtrados, lo, hi), 3),
        "pares_impares": _distribucion(calcular_distribucion_pares_impares_colorloto(filtrados, cantidad_balotas)),
        "altos_bajos": _distribucion(calcular_distribucion_altos_bajos_colorloto(filtrados, lo, hi,
                                                                                 cantidad_balotas)),
        "maximo_repeticion_color": _distribucion(calcular_maximo_repeticion_color_por_sorteo(filtrados,
                                                                                             cantidad_balotas)),
        "colores_fuera_de_la_paleta_vigente": [c for c in usados if c not in colores],
    }
    return resumen
