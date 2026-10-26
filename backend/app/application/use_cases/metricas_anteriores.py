"""
Fase 9.2: páginas de detalle de las métricas ANTERIORES (las que antes solo tenían ruta HTMX
y, en la API pública, únicamente sus cifras clave del panel).

El cálculo es el de la ruta HTMX: la misma receta de `calcular_y_persistir_estadistica` (motor y
serialización) con los mismos `parametros_metrica`, sobre el histórico que
`ConsultarEstadisticasDescriptivas` ya cortó y validó. A diferencia de la consola, no lee ni escribe
la caché `estadisticas`: `calcular_sin_persistir` omite esos pasos. El resultado serializado se
proyecta al contenido de métrica del catálogo de la Fase 5 (`estado`, `indicadores`, `tablas` con
columnas declaradas, `notas`, `selector`) sin fórmulas nuevas: solo se renombran campos, se cambia
una proporción a porcentaje y se ordena como la consola.

Filtros: cada métrica admite como mucho uno (`anio`, `mes`, `dia_semana`, `ventana` o `color`) y la
paginación (`pagina`) solo donde el número de filas crece con el histórico (coocurrencia de tríos de
los juegos numéricos: hasta 12341 tríos en Baloto). Las demás tablas están acotadas por las reglas
del juego (p. ej. 903 pares en Baloto o 42 pares número-color en ColorLoto) y se envían completas.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.application.estadisticas import descriptivas as d
from app.application.use_cases.calcular_y_persistir_estadistica import (
    POLITICA_UNIVERSO_COLORES_ACTUAL,
    HistoricoColorLoto,
    _codigos_colores_vigentes_en_referencia,
    calcular_sin_persistir,
)

POR_PAGINA = 100
"""Filas por página: las mismas que la consola (`_TAMANO_PAGINA_COOCURRENCIA_TRIOS`)."""
FILTROS = ("anio", "mes", "dia_semana", "ventana", "color")
_PERIODOS = {"anio": "anio", "mes": "mes", "dia-semana": "dia_semana"}
_POLITICA = {"politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL}


class ParametroNoValido(ValueError):
    """Valor de filtro o página fuera de lo que admite la métrica (la API responde 422)."""


@dataclass(frozen=True)
class Receta:
    tipo: str  # `tipo_estadistica` de la receta HTMX
    parametros: Callable[[d.ReglasJuego, object], dict]
    forma: str  # frecuencia | tabla | atrasos | intervalos | asociacion | sumas | recencia
    valor: str = "numero"  # numero | color | par (número-color) | categoria
    unidad: str = "sorteos"  # sorteos | transiciones | balotas
    etiqueta: str = "Número"
    filtro: str | None = None
    paginada: bool = False


def _r(reglas):
    return {"rango_min": reglas.rango[0], "rango_max": reglas.rango[1]}


def _rk(reglas):
    return {**_r(reglas), "cantidad_numeros": reglas.cantidad}


def _k(reglas):
    return {"cantidad_numeros": reglas.cantidad}


def _numericas(reglas: d.ReglasJuego) -> dict[str, Receta]:
    R = Receta
    distribucion = {
        "distribucion-pares-impares": ("distribucion_pares_impares", _k, "Números pares en el sorteo"),
        "distribucion-altos-bajos": ("distribucion_altos_bajos", _rk, "Números bajos en el sorteo"),
        "distribucion-pares-consecutivos": ("distribucion_pares_consecutivos", _rk, "Pares consecutivos en el sorteo"),
        "distribucion-trios-consecutivos": ("distribucion_trios_consecutivos", _rk, "Tríos consecutivos en el sorteo"),
        "distribucion-racha-maxima": ("distribucion_racha_maxima", _rk, "Longitud de la racha máxima"),
    }
    recetas = {slug: R(tipo, lambda r, _, f=f: f(r), "frecuencia", "categoria", etiqueta=etiqueta)
               for slug, (tipo, f, etiqueta) in distribucion.items()}
    recetas.update({
        "frecuencia-numeros": R("frecuencia_numeros", lambda r, _: _r(r), "frecuencia"),
        "frecuencia-observada-esperada": R("tabla_frecuencia_numeros", lambda r, _: _rk(r), "tabla"),
        "atrasos-numeros": R("atrasos_numeros", lambda r, _: _r(r), "atrasos"),
        "repeticiones-entre-sorteos": R("distribucion_repeticiones_entre_sorteos", lambda r, _: _rk(r), "frecuencia",
                                        "categoria", "transiciones", "Números repetidos del sorteo anterior"),
        "coocurrencia-pares": R("coocurrencia_pares", lambda r, _: _rk(r), "asociacion"),
        "coocurrencia-trios": R("coocurrencia_trios", lambda r, _: _rk(r), "asociacion", paginada=True),
    })
    if reglas.superbalota is not None:
        recetas["frecuencia-superbalota"] = R(
            "frecuencia_superbalota", lambda r, _: {"rango_min": r.superbalota[0], "rango_max": r.superbalota[1]},
            "frecuencia", etiqueta="Superbalota")
    return recetas


def _colorloto() -> dict[str, Receta]:
    R = Receta
    recetas = {
        "frecuencia-numeros": R("frecuencia_numeros_colorloto", lambda r, _: _rk(r), "frecuencia", unidad="balotas"),
        "frecuencia-colores": R("frecuencia_colores_colorloto", lambda r, _: {**_rk(r), **_POLITICA}, "frecuencia",
                                "color", "balotas", "Color"),
        "frecuencia-pares-numero-color": R("frecuencia_pares_colorloto", lambda r, _: {**_rk(r), **_POLITICA},
                                           "frecuencia", "par", "balotas"),
        "atrasos-numeros": R("atrasos_numeros_colorloto", lambda r, _: _rk(r), "atrasos"),
        "atrasos-colores": R("atrasos_colores_colorloto", lambda r, _: {**_rk(r), **_POLITICA}, "atrasos", "color",
                             etiqueta="Color"),
        "atrasos-pares-numero-color": R("atrasos_pares_colorloto", lambda r, _: {**_rk(r), **_POLITICA}, "atrasos",
                                        "par"),
        "intervalos-historicos-numeros": R("intervalos_historicos_numeros_colorloto", lambda r, _: _r(r),
                                           "intervalos"),
        "intervalos-historicos-colores": R("intervalos_historicos_colores_colorloto", lambda r, _: dict(_POLITICA),
                                           "intervalos", "color", etiqueta="Color"),
        "intervalos-historicos-pares-numero-color": R("intervalos_historicos_pares_numero_color_colorloto",
                                                      lambda r, _: {**_r(r), **_POLITICA}, "intervalos", "par"),
        "distribucion-pares-impares": R("distribucion_pares_impares_colorloto", lambda r, _: _k(r), "frecuencia",
                                        "categoria", etiqueta="Balotas pares en el sorteo"),
        "distribucion-altos-bajos": R("distribucion_altos_bajos_colorloto", lambda r, _: _rk(r), "frecuencia",
                                      "categoria", etiqueta="Balotas bajas en el sorteo"),
        "distribucion-sumas": R("distribucion_sumas_colorloto", lambda r, _: {}, "sumas"),
        "distribucion-pares-consecutivos": R("distribucion_pares_consecutivos_colorloto", lambda r, _: _k(r),
                                             "frecuencia", "categoria", etiqueta="Pares consecutivos en el sorteo"),
        "distribucion-racha-maxima": R("distribucion_racha_maxima_colorloto", lambda r, _: _k(r), "frecuencia",
                                       "categoria", etiqueta="Longitud de la racha máxima"),
        "distribucion-trios-consecutivos": R("distribucion_trios_consecutivos_colorloto", lambda r, _: _k(r),
                                             "frecuencia", "categoria", etiqueta="Tríos consecutivos en el sorteo"),
        "maximo-repeticion-color": R("maximo_repeticion_color_por_sorteo_colorloto", lambda r, _: _k(r), "frecuencia",
                                     "categoria", etiqueta="Balotas del color más repetido"),
        "distribucion-conteo-color": R("distribucion_conteo_color_colorloto",
                                       lambda r, color: {"color_objetivo": color, "cantidad_balotas": r.cantidad},
                                       "frecuencia", "categoria", etiqueta="Balotas del color en el sorteo",
                                       filtro="color"),
        "repeticiones-entre-sorteos": R("repeticiones_entre_sorteos_colorloto", lambda r, _: _rk(r), "frecuencia",
                                        "categoria", "transiciones", "Números repetidos del sorteo anterior"),
        "coocurrencia-pares": R("coocurrencia_pares_colorloto", lambda r, _: {}, "asociacion"),
        "coocurrencia-trios": R("coocurrencia_trios_colorloto", lambda r, _: {}, "asociacion"),
        "coocurrencia-pares-colores": R("coocurrencia_pares_colores_colorloto", lambda r, _: {}, "asociacion", "color"),
        "coocurrencia-trios-colores": R("coocurrencia_trios_colores_colorloto", lambda r, _: {}, "asociacion", "color"),
        "comparacion-frecuencia-numeros-por-ventana": R(
            "comparacion_frecuencia_numeros_por_ventana_colorloto", lambda r, v: {"ventana": v, **_r(r)}, "recencia",
            unidad="balotas", filtro="ventana"),
        "comparacion-frecuencia-colores-por-ventana": R(
            "comparacion_frecuencia_colores_por_ventana_colorloto", lambda r, v: {"ventana": v, **_POLITICA},
            "recencia", "color", "balotas", "Color", filtro="ventana"),
        "comparacion-frecuencia-pares-numero-color-por-ventana": R(
            "comparacion_frecuencia_pares_numero_color_por_ventana_colorloto",
            lambda r, v: {"ventana": v, **_r(r), **_POLITICA}, "recencia", "par", "balotas", filtro="ventana"),
    }
    for sufijo, clave in _PERIODOS.items():
        recetas[f"frecuencia-colores-por-{sufijo}"] = R(
            f"frecuencia_colores_por_{clave}_colorloto", lambda r, v, c=clave: {c: v, **_POLITICA}, "frecuencia",
            "color", "balotas", "Color", filtro=clave)
        recetas[f"frecuencia-pares-numero-color-por-{sufijo}"] = R(
            f"frecuencia_pares_numero_color_por_{clave}_colorloto", lambda r, v, c=clave: {c: v, **_r(r), **_POLITICA},
            "frecuencia", "par", "balotas", filtro=clave)
    return recetas


_COLORLOTO = _colorloto()


def receta(reglas: d.ReglasJuego, slug: str) -> Receta | None:
    """Receta de la página anterior `slug` en ese juego; None si no es anterior o no aplica."""
    definicion = d.POR_SLUG.get(slug)
    if definicion is None or not definicion.aplica(reglas) or definicion.es_nueva(reglas):
        return None
    return (_COLORLOTO if reglas.es_colorloto else _numericas(reglas)).get(slug)


def paginas(reglas: d.ReglasJuego) -> list[dict]:
    """Índice: todas las métricas aplicables con página (Fase 5 y anteriores), en el orden del catálogo."""
    salida = []
    for m in d.CATALOGO:
        if not m.aplica(reglas):
            continue
        if m.es_nueva(reglas):
            salida.append({"metrica": m.slug, "titulo": m.titulo, "grupo": m.grupo, "origen": "fase5",
                           "parametro": m.parametro, "paginada": False})
        elif (r := receta(reglas, m.slug)) is not None:
            salida.append({"metrica": m.slug, "titulo": m.titulo, "grupo": m.grupo, "origen": "anterior",
                           "parametro": r.filtro, "paginada": r.paginada})
    return salida


# ---------------------------------------------------------------------------
# Proyección del resultado serializado (sin fórmulas nuevas)
# ---------------------------------------------------------------------------

def _columnas_de_valor(r: Receta) -> list[dict]:
    if r.valor == "par":
        return [d._col("numero", "Número"), d._col("color", "Color", "color")]
    if r.valor == "color":
        return [d._col("color", r.etiqueta, "color")]
    return [d._col("valor", r.etiqueta, "texto")]


def _celdas_de_valor(r: Receta, valor: str) -> dict:
    if r.valor == "par":  # contrato del motor `f"{numero}-{color}"`: el número precede al PRIMER guion
        numero, color = str(valor).split("-", 1)
        return {"numero": int(numero), "color": color}
    if r.valor == "color":
        return {"color": valor}
    return {"valor": valor}


def _orden_numerico(r: Receta, filas: list[dict]) -> list[dict]:
    """Como la consola: números y categorías por su valor numérico; colores y pares, en el orden del motor."""
    if r.valor in ("numero", "categoria") and all(str(f["valor"]).lstrip("-").isdigit() for f in filas):
        return sorted(filas, key=lambda f: int(f["valor"]))
    return filas


def _unidad(r: Receta) -> tuple[str, str, str, float]:
    """(clave, etiqueta, formato, factor) de la columna relativa; ColorLoto cuenta cada balota."""
    if r.unidad == "balotas":
        return "por_sorteo", "Balotas por sorteo", "dec3", 1.0
    if r.unidad == "transiciones":
        return "pct", "% de transiciones", "pct", 100.0
    return "pct", "% de sorteos", "pct", 100.0


def _frecuencia(r: Receta, filas: list[dict]) -> dict:
    clave, etiqueta, formato, factor = _unidad(r)
    conteo = {"balotas": "Balotas", "transiciones": "Transiciones"}.get(r.unidad, "Sorteos")
    unidad = {"balotas": "balotas por sorteo", "transiciones": "% de transiciones"}.get(r.unidad, "% de sorteos")
    columnas = [*_columnas_de_valor(r), d._col("apariciones", conteo), d._col(clave, etiqueta, formato, unidad)]
    return {"columnas": columnas,
            "filas": [{**_celdas_de_valor(r, f["valor"]), "apariciones": f["apariciones"],
                       clave: factor * f["frecuencia_relativa"]} for f in _orden_numerico(r, filas)]}


def _tabla(r: Receta, filas: list[dict]) -> dict:
    columnas = [d._col("valor", "Número", "texto"), d._col("apariciones", "Sorteos"),
                d._col("pct_observado", "% observado", "pct", "% de sorteos"),
                d._col("pct_teorico", "% teórico (K/N)", "pct", "% de sorteos"),
                d._col("diferencia", "Diferencia", "pp", "puntos porcentuales")]
    return {"columnas": columnas,
            "filas": [{"valor": f["valor"], "apariciones": f["apariciones"],
                       "pct_observado": 100.0 * f["frecuencia_observada"]["frecuencia_relativa"],
                       "pct_teorico": 100.0 * f["probabilidad_teorica"]["probabilidad"],
                       "diferencia": 100.0 * f["diferencia"]} for f in _orden_numerico(r, filas)]}


def _atrasos(r: Receta, filas: list[dict]) -> dict:
    columnas = [*_columnas_de_valor(r), d._col("atraso", "Atraso", "entero", "sorteos de distancia"),
                d._col("ultimo_sorteo", "Último sorteo con el valor")]
    return {"columnas": columnas,
            "filas": [{**_celdas_de_valor(r, f["valor"]), "atraso": f["atraso"],
                       "ultimo_sorteo": f["ultimo_sorteo_aparicion"]} for f in _orden_numerico(r, filas)]}


def _intervalos(r: Receta, filas: list[dict]) -> dict:
    distancia = "sorteos de distancia"
    columnas = [*_columnas_de_valor(r), d._col("apariciones", "Sorteos con el valor"),
                d._col("intervalos", "Intervalos"), d._col("minimo", "Mínimo", "entero", distancia),
                d._col("maximo", "Máximo", "entero", distancia), d._col("promedio", "Promedio", "dec1", distancia),
                d._col("mediana", "Mediana", "dec1", distancia)]
    return {"columnas": columnas,
            "filas": [{**_celdas_de_valor(r, f["valor"]), "apariciones": f["cantidad_apariciones"],
                       "intervalos": f["cantidad_intervalos"], "minimo": f["intervalo_minimo"],
                       "maximo": f["intervalo_maximo"], "promedio": f["intervalo_promedio"],
                       "mediana": f["intervalo_mediana"]} for f in _orden_numerico(r, filas)]}


def _asociacion(r: Receta, filas: list[dict]) -> dict:
    """Orden de la consola (soporte descendente y elementos ascendentes)."""
    ordenadas = sorted(filas, key=lambda f: (-f["soporte"], *f["elementos"]))
    k = len(ordenadas[0]["elementos"]) if ordenadas else 0
    prefijo, etiqueta, formato = ("color", "Color", "color") if r.valor == "color" else ("numero", "Número", "entero")
    columnas = [d._col(f"{prefijo}_{i}", f"{etiqueta} {i}", formato) for i in range(1, k + 1)]
    columnas += [d._col("soporte", "Sorteos con la combinación"),
                 d._col("pct", "% de sorteos", "pct", "% de sorteos"),
                 d._col("pct_esperado", "% esperado (independencia)", "pct", "% de sorteos"),
                 d._col("lift", "Lift", "dec2", "observado / esperado")]
    return {"columnas": columnas,
            "filas": [{**{f"{prefijo}_{i}": e for i, e in enumerate(f["elementos"], 1)}, "soporte": f["soporte"],
                       "pct": 100.0 * f["frecuencia_relativa"],
                       "pct_esperado": None if f["frecuencia_esperada"] is None else 100.0 * f["frecuencia_esperada"],
                       "lift": f["lift"]} for f in ordenadas]}


def _recencia(r: Receta, filas: list[dict]) -> dict:
    unidad = "balotas por sorteo"
    columnas = [*_columnas_de_valor(r), d._col("apariciones_muestra", "Balotas (muestra)"),
                d._col("por_sorteo_muestra", "Balotas por sorteo (muestra)", "dec3", unidad),
                d._col("apariciones_ventana", "Balotas (ventana)"),
                d._col("por_sorteo_ventana", "Balotas por sorteo (ventana)", "dec3", unidad),
                d._col("diferencia", "Diferencia", "dec3", unidad)]
    return {"columnas": columnas,
            "filas": [{**_celdas_de_valor(r, f["valor"]),
                       "apariciones_muestra": f["frecuencia_historica"]["apariciones"],
                       "por_sorteo_muestra": f["frecuencia_historica"]["frecuencia_relativa"],
                       "apariciones_ventana": f["frecuencia_reciente"]["apariciones"],
                       "por_sorteo_ventana": f["frecuencia_reciente"]["frecuencia_relativa"],
                       "diferencia": f["diferencia"]} for f in _orden_numerico(r, filas)]}


_FORMAS = {"frecuencia": _frecuencia, "tabla": _tabla, "atrasos": _atrasos, "intervalos": _intervalos,
           "asociacion": _asociacion, "recencia": _recencia}

_NOTA_BALOTAS = ("Cada balota cuenta (con repetición): «balotas por sorteo» es un promedio que puede superar 1; no es "
                 "una proporción de sorteos.")
_NOTA_COLORES = ("Colores: los vigentes en la fecha del último sorteo de la muestra más los observados en ella, como en "
                 "la consola. Un color sin estilo conocido se muestra con su código.")
_NOTA_RECETA = ("Misma receta y parámetros que la página de la consola; se calcula al consultar, sin leer ni guardar la "
                "caché de estadísticas.")


def _paginar(tabla: dict, pagina: int | None, paginada: bool) -> dict:
    if not paginada:
        if pagina is not None:
            raise ParametroNoValido("Esta métrica no está paginada: no admite «pagina».")
        return {**tabla, "paginacion": None}
    pagina = 1 if pagina is None else pagina
    total = len(tabla["filas"])
    paginas_ = max(1, math.ceil(total / POR_PAGINA))
    if pagina < 1 or pagina > paginas_:
        raise ParametroNoValido(f"La página {pagina} no existe: hay {paginas_}.")
    inicio = (pagina - 1) * POR_PAGINA
    return {**tabla, "filas": tabla["filas"][inicio:inicio + POR_PAGINA],
            "paginacion": {"pagina": pagina, "por_pagina": POR_PAGINA, "total_filas": total, "total_paginas": paginas_}}


def _historico(reglas: d.ReglasJuego, muestra: Sequence, catalogo_colores):
    return HistoricoColorLoto(pares=muestra, catalogo_colores=list(catalogo_colores)) if reglas.es_colorloto else muestra


def _elegir(r: Receta, reglas: d.ReglasJuego, historico, muestra: Sequence, parametros: dict):
    """(valor elegido, selector) del filtro de la métrica; ParametroNoValido si el valor no se admite."""
    if r.filtro is None:
        return None, None
    elegido = parametros.get(r.filtro)
    if r.filtro in ("anio", "mes", "dia_semana"):
        if elegido is None:
            elegido = d._valor_del_periodo(r.filtro, muestra[-1])
        return elegido, d._selector_periodo(r.filtro, muestra, elegido)
    if r.filtro == "ventana":
        elegido = d.VENTANA_POR_DEFECTO if elegido is None else int(elegido)
        if elegido not in d.VENTANAS:
            raise ParametroNoValido(f"ventana debe ser una de {list(d.VENTANAS)}")
        return elegido, {"parametro": "ventana", "valor": str(elegido), "etiqueta": f"últimos {elegido} sorteos",
                         "opciones": [{"valor": str(v), "etiqueta": f"últimos {v}", "sorteos": min(v, len(muestra))}
                                      for v in d.VENTANAS]}
    # color: los vigentes en la referencia más los observados, como la consola; exacto, sin normalizar
    seleccionables = sorted(set(_codigos_colores_vigentes_en_referencia(historico))
                            | {c for s in muestra for _, c in s.pares})
    if not seleccionables:
        raise ParametroNoValido("No hay colores vigentes ni observados en la muestra.")
    elegido = seleccionables[0] if elegido is None else elegido
    if elegido not in seleccionables:
        raise ParametroNoValido(f"color debe ser uno de {seleccionables}")
    return elegido, {"parametro": "color", "valor": elegido, "etiqueta": elegido,
                     "opciones": [{"valor": c, "etiqueta": c, "sorteos": None} for c in seleccionables]}


def construir(slug: str, reglas: d.ReglasJuego, muestra: Sequence, catalogo_colores=(), parametros: dict | None = None,
              pagina: int | None = None) -> dict:
    """Contenido de la página anterior `slug` sobre `muestra` (ya cortada, ordenada y validada).
    KeyError si no es una página anterior del juego; ParametroNoValido si un filtro o la página no se admiten."""
    r = receta(reglas, slug)
    if r is None:
        raise KeyError(slug)
    parametros = dict(parametros or {})
    ajenos = sorted(k for k, v in parametros.items() if v is not None and k != r.filtro)
    if ajenos:
        raise ParametroNoValido(f"Parámetros no admitidos por esta métrica: {', '.join(ajenos)}")
    if pagina is not None and not r.paginada:
        raise ParametroNoValido("Esta métrica no está paginada: no admite «pagina».")
    definicion = d.POR_SLUG[slug]
    cabecera = {"slug": slug, "titulo": definicion.titulo, "grupo": definicion.grupo, "parametro": r.filtro,
                "origen": "anterior"}
    if not muestra:
        return {**cabecera, **d._sin_datos()}
    historico = _historico(reglas, muestra, catalogo_colores)
    elegido, selector = _elegir(r, reglas, historico, muestra, parametros)
    resultado = calcular_sin_persistir(r.tipo, historico, r.parametros(reglas, elegido))
    notas = [_NOTA_RECETA]
    if reglas.es_colorloto and r.unidad == "balotas":
        notas.append(_NOTA_BALOTAS)
    if reglas.es_colorloto and r.valor in ("color", "par"):
        notas.append(_NOTA_COLORES)
    if r.forma == "sumas":
        indicadores = [d._ind("Sorteos analizados", resultado["total_sorteos"], "sorteos"),
                       d._ind("Mínimo", resultado["minimo"], "suma"), d._ind("Máximo", resultado["maximo"], "suma"),
                       d._ind("Media", resultado["media"], "suma", "dec2"),
                       d._ind("Mediana", resultado["mediana"], "suma", "dec1"),
                       d._ind("Desviación típica (poblacional)", resultado["desviacion_estandar"], "suma", "dec2")]
        tabla = {"id": "percentiles", "titulo": "Percentiles de la suma de las balotas",
                 "columnas": [d._col("percentil", "Percentil", "texto"), d._col("valor", "Suma", "dec1", "suma")],
                 "filas": [{"percentil": p, "valor": v} for p, v in resultado["percentiles"].items()], "nota": None,
                 "paginacion": None}
        return {**cabecera, **d._contenido(indicadores=indicadores, tablas=[tabla],
                                           notas=notas + d._nota_huecos(muestra), selector=selector)}
    filas = resultado["filas"]
    total = filas[0]["total_sorteos"] if filas and "total_sorteos" in filas[0] else (
        filas[0]["frecuencia_observada"]["total_sorteos"] if filas and "frecuencia_observada" in filas[0] else len(muestra))
    if r.filtro in ("anio", "mes", "dia_semana") and total == 0:
        return {**cabecera, **d._contenido(
            "sin_sorteos_en_el_periodo", f"No hay sorteos en {selector['etiqueta']} dentro de la muestra; elige otro valor.",
            selector=selector)}
    proyectada = _FORMAS[r.forma](r, filas)
    tabla = _paginar({"id": "datos", "titulo": definicion.titulo, **proyectada, "nota": None}, pagina, r.paginada)
    if tabla["paginacion"]:
        notas.append(f"Tabla paginada: {POR_PAGINA} filas por página, ordenadas por sorteos con la combinación "
                     "(de mayor a menor) y por sus valores; el total de filas está en la paginación.")
    if r.forma == "intervalos":
        notas.append("La lista completa de intervalos de cada valor no se envía; se muestran su cantidad, mínimo, "
                     "máximo, promedio y mediana (como la consola).")
    if r.forma == "tabla" and filas:
        notas.append(f"Probabilidad teórica: {filas[0]['probabilidad_teorica']['metodo']}.")
    if r.unidad == "transiciones":
        etiqueta_total = "Transiciones analizadas"
    elif r.filtro in ("anio", "mes", "dia_semana"):
        etiqueta_total = "Sorteos en el periodo"
    else:
        etiqueta_total = "Sorteos analizados"
    indicadores = [d._ind(etiqueta_total, total, "transiciones" if r.unidad == "transiciones" else "sorteos")]
    if r.forma == "asociacion":
        indicadores.append(d._ind("Combinaciones observadas", len(filas), "combinaciones"))
    if selector is not None:
        indicadores.insert(0, d._ind("Filtro", selector["etiqueta"], "", "texto"))
    return {**cabecera, **d._contenido(indicadores=indicadores, tablas=[tabla], notas=notas + d._nota_huecos(muestra),
                                       selector=selector)}
