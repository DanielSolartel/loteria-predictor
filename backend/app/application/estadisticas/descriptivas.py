"""
Estadísticas descriptivas de la Fase 5: catálogo único de métricas y panel unificado por juego.

Un solo lugar describe cada métrica (título, grupo, juegos a los que aplica, parámetro) y construye
su contenido a partir del histórico YA CORTADO, con las funciones del motor
(`app/application/estadisticas/motor/`): este módulo no reimplementa fórmulas, solo las combina y
declara unidades y denominadores. Lo usan la web (`/estadisticas/{juego}/{metrica}` y
`/estadisticas/{juego}/panel`), la API (`/api/estadisticas/{codigo}/...`) y cualquier caso de uso que
necesite la misma cifra (por ejemplo, variables de ML: ver ARCHITECTURE, Fase 5).

Contenido de una métrica (diccionario serializable a JSON):
  - `estado`: "ok", "sin_datos" (sin sorteos hasta el corte), "insuficiente" (hay sorteos pero no
    bastan) o "sin_sorteos_en_el_periodo" (el año, mes o día elegido no tiene sorteos);
  - `indicadores`: cifras resumen con su unidad;
  - `tablas`: columnas con clave, etiqueta, formato y unidad, y filas con los valores;
  - `grafica`: referencia a UNA columna de una de las tablas (la gráfica y la tabla muestran los
    mismos valores por construcción);
  - `notas`, `selector` (parámetro elegido y opciones con sus sorteos).

Unidades que no se intercambian: «% de sorteos» (sorteos que contienen el valor / sorteos), «% de
números extraídos» (apariciones / (sorteos x números por sorteo)), «balotas por sorteo» (ColorLoto:
cada balota cuenta, con multiplicidad), «sorteos de distancia» (diferencia de numeración) y «puntos
porcentuales» (diferencia entre dos porcentajes).

Todo es descriptivo: frecuencias, atrasos, intervalos y pruebas describen la muestra; no son
probabilidades del próximo sorteo ni evidencia de ventaja predictiva.
"""
from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.application.estadisticas.motor import atrasos as m_atrasos
from app.application.estadisticas.motor import consecutivos as m_consecutivos
from app.application.estadisticas.motor import coocurrencia as m_coocurrencia
from app.application.estadisticas.motor import correlaciones as m_correlaciones
from app.application.estadisticas.motor import distribuciones as m_distribuciones
from app.application.estadisticas.motor import frecuencia as m_frecuencia
from app.application.estadisticas.motor import frecuencia_temporal as m_temporal
from app.application.estadisticas.motor import generales as m_generales
from app.application.estadisticas.motor import independencia as m_independencia
from app.application.estadisticas.motor import recencia as m_recencia
from app.application.estadisticas.motor import repeticiones as m_repeticiones
from app.application.estadisticas.motor.tests_estadisticos import (
    aplicar_correccion_benjamini_hochberg,
    chi_cuadrado_uniformidad,
)

DIAS_SEMANA = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
NOMBRE_DIA = {"lunes": "lunes", "martes": "martes", "miercoles": "miércoles", "jueves": "jueves",
              "viernes": "viernes", "sabado": "sábado", "domingo": "domingo"}
NOMBRE_MES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
              "octubre", "noviembre", "diciembre")
VENTANAS = (5, 10, 20, 50)
VENTANA_POR_DEFECTO = 20
ALFA = 0.05
ESPERADO_MINIMO_CHI2 = 5.0
"""Regla práctica: con frecuencias esperadas menores que 5 la aproximación chi-cuadrado es poco fiable."""
TIPO_P_ASINTOTICO = "asintotico"
ETIQUETAS_TIPO_P_VALUE = {
    TIPO_P_ASINTOTICO: "asintótico (chi-cuadrado límite)",
    m_correlaciones.CONTRASTE_EXACTO: "permutación exacta",
    m_correlaciones.CONTRASTE_MONTE_CARLO: "permutación Monte Carlo",
}
"""Cómo se obtiene un p-value: clave en el JSON (`tipo_p_value`, `contraste`) y texto en pantalla."""
FILAS_INDEPENDENCIA = 20

GRUPOS = (
    ("frecuencias", "Frecuencias"),
    ("temporales", "Patrones temporales"),
    ("atrasos", "Atrasos e intervalos"),
    ("distribuciones", "Distribuciones de la combinación"),
    ("coocurrencia", "Coocurrencia y repetición"),
    ("ventana", "Comparación con una ventana reciente"),
    ("pruebas", "Pruebas y correlaciones"),
)


@dataclass(frozen=True)
class ReglasJuego:
    """Reglas leídas del dominio (nunca constantes de Baloto)."""

    codigo: str
    nombre: str
    tipo: str  # "numeros" | "colorloto"
    rango: tuple[int, int]
    cantidad: int  # números distintos por sorteo, o balotas en ColorLoto
    superbalota: tuple[int, int] | None = None
    colores: tuple[str, ...] = ()  # ColorLoto: paleta vigente más colores observados fuera de ella
    paleta_estable: bool = True  # ColorLoto: la misma paleta vigente en todos los sorteos de la muestra

    @property
    def universo(self) -> int:
        return self.rango[1] - self.rango[0] + 1

    @property
    def es_colorloto(self) -> bool:
        return self.tipo == "colorloto"


@dataclass(frozen=True)
class Definicion:
    slug: str
    titulo: str
    grupo: str
    aplica: Callable[[ReglasJuego], bool]
    construir: Callable | None = None  # página de la Fase 5 en este módulo
    resumen: Callable | None = None  # cifra clave para el panel cuando la página es anterior
    parametro: str | None = None  # "anio" | "mes" | "dia_semana" | "ventana"
    motivo_no_aplica: Callable[[ReglasJuego], str] | None = None
    nueva_para: Callable[[ReglasJuego], bool] | None = None  # juegos con página nueva; None = todos si hay `construir`

    def es_nueva(self, reglas: ReglasJuego) -> bool:
        """True si la página la sirve la Fase 5; False si ya existía (rutas anteriores de estadísticas)."""
        if self.construir is None:
            return False
        return True if self.nueva_para is None else self.nueva_para(reglas)


# ---------------------------------------------------------------------------
# Ayudas de presentación (sin fórmulas estadísticas)
# ---------------------------------------------------------------------------

def _col(clave: str, etiqueta: str, formato: str = "entero", unidad: str = "") -> dict:
    return {"clave": clave, "etiqueta": etiqueta, "formato": formato, "unidad": unidad}


def _pct(parte: float, total: float) -> float | None:
    return None if not total else 100.0 * parte / total


def _ind(etiqueta: str, valor, unidad: str = "", formato: str = "entero") -> dict:
    return {"etiqueta": etiqueta, "valor": valor, "unidad": unidad, "formato": formato}


def _contenido(estado: str = "ok", motivo: str | None = None, **kw) -> dict:
    base = {"estado": estado, "motivo": motivo, "indicadores": [], "tablas": [], "grafica": None, "notas": [],
            "selector": None}
    base.update(kw)
    return base


def _sin_datos() -> dict:
    return _contenido("sin_datos", "No hay sorteos hasta el corte indicado.")


def _orden_valor(valor: str):
    return (0, int(valor), "") if str(valor).isdigit() else (1, 0, str(valor))


def _extremo(filas: list[dict], funcion) -> dict:
    """Fila con la diferencia máxima o mínima; empate: el valor menor."""
    return funcion(filas, key=lambda f: (f["diferencia"], -_orden_valor(f["valor"])[1] if funcion is max
                                         else _orden_valor(f["valor"])[1]))


def _fila_valor(filas: list[dict], valor: str) -> dict:
    return next(f for f in filas if f["valor"] == valor)


def _huecos(historico: Sequence) -> int:
    return len(m_generales.detectar_huecos_serie_historica([r.numero_sorteo for r in historico]).huecos)


def _nota_huecos(historico: Sequence) -> list[str]:
    h = _huecos(historico)
    return [f"La numeración de la muestra tiene {h} hueco(s): las distancias se miden en numeración y las "
            "comparaciones entre sorteos consecutivos excluyen los saltos."] if h else []


# ---------------------------------------------------------------------------
# Frecuencias por periodo (año, mes, día de la semana)
# ---------------------------------------------------------------------------

_SORTEOS_POR_PERIODO = {"anio": m_generales.calcular_frecuencia_sorteos_por_anio,
                        "mes": m_generales.calcular_frecuencia_sorteos_por_mes,
                        "dia_semana": m_generales.calcular_frecuencia_sorteos_por_dia_semana}


def etiqueta_periodo(parametro: str, valor) -> str:
    if parametro == "mes":
        return NOMBRE_MES[int(valor) - 1]
    if parametro == "dia_semana":
        return NOMBRE_DIA.get(str(valor), str(valor))
    return str(valor)


def _valor_del_periodo(parametro: str, r):
    return {"anio": r.fecha.year, "mes": r.fecha.month, "dia_semana": r.dia_semana}[parametro]


def _selector_periodo(parametro: str, historico: Sequence, elegido) -> dict:
    filas = _SORTEOS_POR_PERIODO[parametro](historico)
    if parametro == "dia_semana":
        filas = sorted(filas, key=lambda f: DIAS_SEMANA.index(f.valor) if f.valor in DIAS_SEMANA else 99)
    opciones = [{"valor": f.valor, "etiqueta": etiqueta_periodo(parametro, f.valor), "sorteos": f.apariciones}
                for f in filas]
    return {"parametro": parametro, "valor": str(elegido), "etiqueta": etiqueta_periodo(parametro, elegido),
            "opciones": opciones}


_TEMPORAL = {
    ("numeros", "anio"): m_temporal.calcular_frecuencia_numeros_por_anio,
    ("numeros", "mes"): m_temporal.calcular_frecuencia_numeros_por_mes,
    ("numeros", "dia_semana"): m_temporal.calcular_frecuencia_numeros_por_dia_semana,
    ("superbalota", "anio"): m_temporal.calcular_frecuencia_superbalota_por_anio,
    ("superbalota", "mes"): m_temporal.calcular_frecuencia_superbalota_por_mes,
    ("superbalota", "dia_semana"): m_temporal.calcular_frecuencia_superbalota_por_dia_semana,
    ("colorloto", "anio"): m_temporal.calcular_frecuencia_numeros_colorloto_por_anio,
    ("colorloto", "mes"): m_temporal.calcular_frecuencia_numeros_colorloto_por_mes,
    ("colorloto", "dia_semana"): m_temporal.calcular_frecuencia_numeros_colorloto_por_dia_semana,
}


def _frecuencia_total(pool: str, reglas: ReglasJuego, historico: Sequence) -> list:
    lo, hi = reglas.rango
    if pool == "superbalota":
        return m_frecuencia.calcular_frecuencia_superbalota(historico, *reglas.superbalota)
    if pool == "colorloto":
        return m_frecuencia.calcular_frecuencia_numeros_colorloto(historico, lo, hi)
    return m_frecuencia.calcular_frecuencia_numeros(historico, lo, hi)


def _por_periodo(pool: str, parametro: str):
    def construir(reglas: ReglasJuego, historico: Sequence, parametros: dict) -> dict:
        if not historico:
            return _sin_datos()
        elegido = parametros.get(parametro)
        if elegido is None:
            elegido = _valor_del_periodo(parametro, historico[-1])
        selector = _selector_periodo(parametro, historico, elegido)
        rango = reglas.superbalota if pool == "superbalota" else reglas.rango
        filas_periodo = _TEMPORAL[(pool, parametro)](historico, rango[0], rango[1], elegido)
        sorteos_periodo = filas_periodo[0].total_sorteos if filas_periodo else 0
        nombre = selector["etiqueta"]
        if sorteos_periodo == 0:
            return _contenido("sin_sorteos_en_el_periodo",
                              f"No hay sorteos en {nombre} dentro de la muestra; elige otro valor.", selector=selector)
        total = {f.valor: f for f in _frecuencia_total(pool, reglas, historico)}
        etiqueta_valor = "Superbalota" if pool == "superbalota" else "Número"
        if pool == "colorloto":
            esperado = reglas.cantidad / reglas.universo
            columnas = [_col("valor", etiqueta_valor, "texto"), _col("apariciones", "Balotas en el periodo"),
                        _col("por_sorteo", "Balotas por sorteo (periodo)", "dec3", "balotas por sorteo"),
                        _col("por_sorteo_muestra", "Balotas por sorteo (muestra)", "dec3", "balotas por sorteo"),
                        _col("diferencia", "Diferencia", "dec3", "balotas por sorteo")]
            filas = [{"valor": f.valor, "apariciones": f.apariciones, "por_sorteo": f.frecuencia_relativa,
                      "por_sorteo_muestra": total[f.valor].frecuencia_relativa,
                      "diferencia": f.frecuencia_relativa - total[f.valor].frecuencia_relativa} for f in filas_periodo]
            grafica = {"titulo": f"Balotas por sorteo en {nombre}", "tabla": "frecuencia", "etiqueta": "valor",
                       "valor": "por_sorteo", "unidad": "balotas por sorteo", "referencia": esperado,
                       "etiqueta_referencia": f"esperado bajo azar uniforme ({reglas.cantidad}/{reglas.universo})"}
            nota_unidad = ("Cada balota cuenta (con repetición): «balotas por sorteo» es un promedio que puede "
                           "superar 1; no es una proporción de sorteos.")
        else:
            k = 1 if pool == "superbalota" else reglas.cantidad
            n = rango[1] - rango[0] + 1
            columnas = [_col("valor", etiqueta_valor, "texto"), _col("apariciones", "Sorteos con el valor (periodo)"),
                        _col("pct_periodo", "% de sorteos del periodo", "pct", "% de sorteos"),
                        _col("pct_muestra", "% de sorteos de la muestra", "pct", "% de sorteos"),
                        _col("diferencia", "Diferencia", "pp", "puntos porcentuales")]
            filas = [{"valor": f.valor, "apariciones": f.apariciones,
                      "pct_periodo": 100.0 * f.frecuencia_relativa,
                      "pct_muestra": 100.0 * total[f.valor].frecuencia_relativa,
                      "diferencia": 100.0 * (f.frecuencia_relativa - total[f.valor].frecuencia_relativa)}
                     for f in filas_periodo]
            grafica = {"titulo": f"% de sorteos en {nombre}", "tabla": "frecuencia", "etiqueta": "valor",
                       "valor": "pct_periodo", "unidad": "% de sorteos", "referencia": 100.0 * k / n,
                       "etiqueta_referencia": f"esperado bajo azar uniforme ({k}/{n})"}
            nota_unidad = "Sin repetición dentro del sorteo: «% de sorteos» es la proporción de sorteos que contienen el valor."
        notas = [nota_unidad]
        if parametro == "mes":
            notas.append("El mes es calendario y agrega todos los años de la muestra (marzo de 2024 y de 2025 juntos).")
        if sorteos_periodo < 30:
            notas.append(f"Solo {sorteos_periodo} sorteo(s) en el periodo: con tan pocos sorteos las diferencias son "
                         "esperables por azar.")
        return _contenido(
            indicadores=[_ind("Periodo", nombre, "", "texto"),
                         _ind("Sorteos en el periodo", sorteos_periodo, "sorteos"),
                         _ind("% de la muestra", _pct(sorteos_periodo, len(historico)), "% de sorteos", "dec1")],
            tablas=[{"id": "frecuencia", "titulo": f"Frecuencia en {nombre} frente a toda la muestra",
                     "columnas": columnas, "filas": filas, "nota": None}],
            grafica=grafica, notas=notas, selector=selector)
    return construir


# ---------------------------------------------------------------------------
# Atrasos e intervalos
# ---------------------------------------------------------------------------

def _intervalos(pool: str):
    def construir(reglas: ReglasJuego, historico: Sequence, parametros: dict) -> dict:
        if not historico:
            return _sin_datos()
        if pool == "superbalota":
            lo, hi = reglas.superbalota
            filas_motor = m_atrasos.calcular_intervalos_historicos_superbalota(historico, lo, hi)
            k, etiqueta = 1, "Superbalota"
        else:
            lo, hi = reglas.rango
            filas_motor = m_atrasos.calcular_intervalos_historicos_numeros(historico, lo, hi)
            k, etiqueta = reglas.cantidad, "Número"
        n = hi - lo + 1
        filas = [{"valor": f.valor, "apariciones": f.cantidad_apariciones, "intervalos": f.cantidad_intervalos,
                  "minimo": f.intervalo_minimo, "maximo": f.intervalo_maximo, "promedio": f.intervalo_promedio,
                  "mediana": f.intervalo_mediana} for f in filas_motor]
        con_intervalos = [f for f in filas if f["promedio"] is not None]
        if not con_intervalos:
            return _contenido("insuficiente", "Ningún valor aparece en 2 o más sorteos: no hay intervalos que medir.",
                              tablas=[{"id": "intervalos", "titulo": "Intervalos por valor", "columnas": [],
                                       "filas": [], "nota": None}])
        columnas = [_col("valor", etiqueta, "texto"), _col("apariciones", "Sorteos con el valor", "entero", "sorteos"),
                    _col("intervalos", "Intervalos"), _col("minimo", "Mínimo", "entero", "sorteos de distancia"),
                    _col("maximo", "Máximo", "entero", "sorteos de distancia"),
                    _col("promedio", "Promedio", "dec1", "sorteos de distancia"),
                    _col("mediana", "Mediana", "dec1", "sorteos de distancia")]
        return _contenido(
            indicadores=[_ind("Intervalo promedio esperado bajo azar uniforme", n / k, "sorteos de distancia", "dec1"),
                         _ind("Mayor intervalo observado", max(f["maximo"] for f in con_intervalos),
                              "sorteos de distancia")],
            tablas=[{"id": "intervalos", "titulo": "Intervalos entre apariciones consecutivas", "columnas": columnas,
                     "filas": filas, "nota": "«—»: el valor apareció en menos de 2 sorteos (sin intervalo)."}],
            grafica={"titulo": "Intervalo promedio por valor", "tabla": "intervalos", "etiqueta": "valor",
                     "valor": "promedio", "unidad": "sorteos de distancia", "referencia": n / k,
                     "etiqueta_referencia": f"esperado bajo azar uniforme ({n}/{k})"},
            notas=["Intervalo = diferencia de numeración entre dos sorteos consecutivos con el valor. Un intervalo "
                   "largo en el pasado no hace más probable que el valor salga ahora."] + _nota_huecos(historico))
    return construir


def _atrasos_superbalota(reglas: ReglasJuego, historico: Sequence, parametros: dict) -> dict:
    if not historico:
        return _sin_datos()
    lo, hi = reglas.superbalota
    atrasos = m_atrasos.calcular_atrasos_superbalota(historico, lo, hi)
    frecuencia = {f.valor: f for f in m_frecuencia.calcular_frecuencia_superbalota(historico, lo, hi)}
    filas = [{"valor": a.valor, "atraso": a.atraso, "ultimo_sorteo": a.ultimo_sorteo_aparicion,
              "apariciones": frecuencia[a.valor].apariciones,
              "pct_sorteos": 100.0 * frecuencia[a.valor].frecuencia_relativa} for a in atrasos]
    observados = [f for f in filas if f["atraso"] is not None]
    n = hi - lo + 1
    return _contenido(
        indicadores=[_ind("Sorteo de referencia", historico[-1].numero_sorteo, "número de sorteo"),
                     _ind("Mayor atraso", max((f["atraso"] for f in observados), default=None), "sorteos de distancia"),
                     _ind("Nunca observadas en la muestra", sum(1 for f in filas if f["atraso"] is None), "valores")],
        tablas=[{"id": "atrasos", "titulo": "Atraso actual de cada superbalota",
                 "columnas": [_col("valor", "Superbalota", "texto"),
                              _col("atraso", "Atraso actual", "entero", "sorteos de distancia"),
                              _col("ultimo_sorteo", "Último sorteo con el valor", "entero"),
                              _col("apariciones", "Sorteos con el valor", "entero", "sorteos"),
                              _col("pct_sorteos", "% de sorteos", "pct", "% de sorteos")],
                 "filas": filas, "nota": "«—»: no apareció en la muestra."}],
        grafica={"titulo": "Atraso actual por superbalota", "tabla": "atrasos", "etiqueta": "valor", "valor": "atraso",
                 "unidad": "sorteos de distancia", "referencia": float(n),
                 "etiqueta_referencia": f"espera media bajo azar uniforme ({n})"},
        notas=["Atraso = sorteo de referencia (el último de la muestra) menos el último sorteo con esa superbalota. "
               "La superbalota se analiza aparte de los números principales.",
               "Un atraso grande no hace más probable que la superbalota salga en el próximo sorteo."]
        + _nota_huecos(historico))


def _repeticion_superbalota(reglas: ReglasJuego, historico: Sequence, parametros: dict) -> dict:
    if not historico:
        return _sin_datos()
    filas_motor = m_repeticiones.calcular_repeticion_superbalota_entre_sorteos(historico)
    transiciones = filas_motor[0].total_sorteos if filas_motor else 0
    if transiciones == 0:
        return _contenido("insuficiente", "No hay dos sorteos con numeración consecutiva: no hay transiciones.")
    n = reglas.superbalota[1] - reglas.superbalota[0] + 1
    etiquetas = {"0": "Distinta a la del sorteo anterior", "1": "Igual a la del sorteo anterior"}
    esperado = {"0": 100.0 * (n - 1) / n, "1": 100.0 / n}
    filas = [{"valor": etiquetas[f.valor], "transiciones": f.apariciones, "pct": 100.0 * f.frecuencia_relativa,
              "esperado": esperado[f.valor]} for f in filas_motor]
    return _contenido(
        indicadores=[_ind("Igual a la del sorteo anterior", _fila_valor(filas, etiquetas["1"])["pct"], "% de transiciones",
                          "dec1"),
                     _ind("Esperado bajo azar uniforme", 100.0 / n, "% de transiciones", "dec2"),
                     _ind("Transiciones válidas (N → N+1)", transiciones, "transiciones"),
                     _ind("Excluidas por hueco de numeración", max(0, len(historico) - 1 - transiciones), "transiciones")],
        tablas=[{"id": "repeticion", "titulo": "Superbalota igual o distinta a la del sorteo anterior",
                 "columnas": [_col("valor", "Resultado", "texto"), _col("transiciones", "Transiciones", "entero", "transiciones"),
                              _col("pct", "% de transiciones", "pct", "% de transiciones"),
                              _col("esperado", "Esperado bajo azar uniforme", "pct", "% de transiciones")],
                 "filas": filas, "nota": None}],
        grafica={"titulo": "% de transiciones", "tabla": "repeticion", "etiqueta": "valor", "valor": "pct",
                 "unidad": "% de transiciones", "referencia": None},
        notas=["El denominador son las transiciones entre sorteos de numeración consecutiva, no los sorteos.",
               "Que la superbalota se repita o no en el pasado no cambia la probabilidad de que se repita ahora."])


# ---------------------------------------------------------------------------
# Distribuciones de la combinación
# ---------------------------------------------------------------------------

def _distribucion_sumas(reglas: ReglasJuego, historico: Sequence, parametros: dict) -> dict:
    if not historico:
        return _sin_datos()
    lo, hi = reglas.rango
    k = reglas.cantidad
    d = m_distribuciones.calcular_distribucion_sumas(historico)
    histograma = m_distribuciones.calcular_histograma_sumas(historico, lo, hi, k)
    media_uniforme = k * (lo + hi) / 2
    return _contenido(
        indicadores=[_ind("Media", d.media, "suma", "dec1"),
                     _ind("Mediana", d.mediana, "suma", "dec1"),
                     _ind("Desviación estándar", d.desviacion_estandar, "suma", "dec1"),
                     _ind("Media esperada bajo azar uniforme", media_uniforme, "suma", "dec1"),
                     _ind("Mínima y máxima observadas", f"{d.minimo} y {d.maximo}", "suma", "texto")],
        tablas=[{"id": "histograma", "titulo": "Sorteos por intervalo de suma",
                 "columnas": [_col("valor", "Suma", "texto"), _col("sorteos", "Sorteos", "entero", "sorteos"),
                              _col("pct", "% de sorteos", "pct", "% de sorteos")],
                 "filas": [{"valor": f.valor, "sorteos": f.apariciones, "pct": 100.0 * f.frecuencia_relativa}
                           for f in histograma], "nota": None},
                {"id": "percentiles", "titulo": "Percentiles de la suma",
                 "columnas": [_col("valor", "Percentil", "texto"), _col("suma", "Suma", "dec1", "suma")],
                 "filas": [{"valor": f"P{p}", "suma": v} for p, v in sorted(d.percentiles.items())], "nota": None}],
        grafica={"titulo": "Sorteos por intervalo de suma", "tabla": "histograma", "etiqueta": "valor",
                 "valor": "sorteos", "unidad": "sorteos", "referencia": None},
        notas=[f"Suma de los {k} números principales de cada sorteo (sin la superbalota). Posibles: de "
               f"{sum(range(lo, lo + k))} a {sum(range(hi - k + 1, hi + 1))}; media esperada bajo azar uniforme "
               f"K·(mín+máx)/2 = {media_uniforme:g}.",
               "La desviación estándar es poblacional (describe la muestra completa)."])


def _distribucion_decenas(reglas: ReglasJuego, historico: Sequence, parametros: dict) -> dict:
    from app.application.estadisticas.resumen_juego import porcentaje_de_numeros_extraidos

    if not historico:
        return _sin_datos()
    lo, hi = reglas.rango
    k, n, t = reglas.cantidad, reglas.universo, len(historico)
    filas = []
    for f in m_distribuciones.calcular_distribucion_decenas(historico, lo, hi):
        a, b = (int(x) for x in f.valor.split("-"))
        tamano = b - a + 1
        filas.append({"valor": f.valor, "numeros": tamano, "apariciones": f.apariciones,
                      "pct_extraidos": porcentaje_de_numeros_extraidos(f.apariciones, t, k),
                      "pct_esperado": 100.0 * tamano / n, "por_sorteo": f.frecuencia_relativa})
    extrema = max(filas, key=lambda f: abs(f["pct_extraidos"] - f["pct_esperado"]))
    return _contenido(
        indicadores=[_ind("Números extraídos", t * k, "números"),
                     _ind(f"Mayor diferencia con el esperado (franja {extrema['valor']})",
                          extrema["pct_extraidos"] - extrema["pct_esperado"], "puntos porcentuales", "dec1")],
        tablas=[{"id": "decenas", "titulo": "Números extraídos por franja de diez",
                 "columnas": [_col("valor", "Franja", "texto"), _col("numeros", "Números en la franja"),
                              _col("apariciones", "Apariciones", "entero", "números extraídos"),
                              _col("pct_extraidos", "% de números extraídos", "pct", "% de números extraídos"),
                              _col("pct_esperado", "Esperado bajo azar uniforme", "pct", "% de números extraídos"),
                              _col("por_sorteo", "Promedio por sorteo", "dec2", "números por sorteo")],
                 "filas": filas, "nota": None}],
        grafica={"titulo": "% de números extraídos por franja", "tabla": "decenas", "etiqueta": "valor",
                 "valor": "pct_extraidos", "unidad": "% de números extraídos", "referencia": None},
        notas=[f"Denominador: {t} sorteos × {k} números = {t * k} números extraídos. Las franjas no tienen siempre "
               "el mismo tamaño (la última puede ser más corta), por eso el esperado varía.",
               "La superbalota no entra en las franjas."])


# ---------------------------------------------------------------------------
# Comparación con una ventana reciente
# ---------------------------------------------------------------------------

def _ventana(pool: str):
    def construir(reglas: ReglasJuego, historico: Sequence, parametros: dict) -> dict:
        if not historico:
            return _sin_datos()
        ventana = int(parametros.get("ventana") or VENTANA_POR_DEFECTO)
        if ventana not in VENTANAS:
            raise ValueError(f"ventana debe ser una de {VENTANAS}")
        if pool == "superbalota":
            lo, hi = reglas.superbalota
            comp = m_recencia.comparar_frecuencia_superbalota_por_ventana(historico, lo, hi, ventana, f"ultimos_{ventana}")
            etiqueta = "Superbalota"
        else:
            lo, hi = reglas.rango
            comp = m_recencia.comparar_frecuencia_numeros_por_ventana(historico, lo, hi, ventana, f"ultimos_{ventana}")
            etiqueta = "Número"
        recientes = m_recencia.tomar_ultimos_n_sorteos(historico, ventana)
        filas = [{"valor": c.valor, "apariciones_muestra": c.frecuencia_historica.apariciones,
                  "pct_muestra": 100.0 * c.frecuencia_historica.frecuencia_relativa,
                  "apariciones_ventana": c.frecuencia_reciente.apariciones,
                  "pct_ventana": 100.0 * c.frecuencia_reciente.frecuencia_relativa,
                  "diferencia": 100.0 * c.diferencia} for c in comp]
        selector = {"parametro": "ventana", "valor": str(ventana), "etiqueta": f"últimos {ventana} sorteos",
                    "opciones": [{"valor": str(v), "etiqueta": f"últimos {v}", "sorteos": min(v, len(historico))}
                                 for v in VENTANAS]}
        notas = [f"Ventana: los {len(recientes)} sorteos más recientes de la muestra "
                 f"({recientes[0].numero_sorteo}–{recientes[-1].numero_sorteo}). Diferencia = % en la ventana − % en "
                 "toda la muestra (puntos porcentuales).",
                 "Con ventanas cortas son normales diferencias grandes; no indican una tendencia que vaya a continuar."]
        if len(recientes) < ventana:
            notas.insert(0, f"La muestra solo tiene {len(recientes)} sorteos: la ventana usa todos.")
        return _contenido(
            indicadores=[_ind("Sorteos en la ventana", len(recientes), "sorteos"),
                         _ind(f"Mayor subida ({etiqueta.lower()} {_extremo(filas, max)['valor']})",
                              _extremo(filas, max)["diferencia"], "puntos porcentuales", "dec1"),
                         _ind(f"Mayor bajada ({etiqueta.lower()} {_extremo(filas, min)['valor']})",
                              _extremo(filas, min)["diferencia"], "puntos porcentuales", "dec1")],
            tablas=[{"id": "ventana", "titulo": f"Frecuencia en los últimos {ventana} sorteos frente a toda la muestra",
                     "columnas": [_col("valor", etiqueta, "texto"),
                                  _col("apariciones_muestra", "Sorteos con el valor (muestra)", "entero", "sorteos"),
                                  _col("pct_muestra", "% de sorteos (muestra)", "pct", "% de sorteos"),
                                  _col("apariciones_ventana", "Sorteos con el valor (ventana)", "entero", "sorteos"),
                                  _col("pct_ventana", "% de sorteos (ventana)", "pct", "% de sorteos"),
                                  _col("diferencia", "Diferencia", "pp", "puntos porcentuales")],
                     "filas": filas, "nota": None}],
            grafica={"titulo": "Diferencia ventana − muestra", "tabla": "ventana", "etiqueta": "valor",
                     "valor": "diferencia", "unidad": "puntos porcentuales", "referencia": None},
            notas=notas, selector=selector)
    return construir


# ---------------------------------------------------------------------------
# Pruebas y correlaciones
# ---------------------------------------------------------------------------

def _universos_uniformidad(reglas: ReglasJuego, historico: Sequence) -> list[tuple]:
    """(id, nombre, frecuencias, extraidos por sorteo, sin reemplazo, motivo si no aplica)."""
    lo, hi = reglas.rango
    if not reglas.es_colorloto:
        universos = [("numeros", "Números principales", m_frecuencia.calcular_frecuencia_numeros(historico, lo, hi),
                      reglas.cantidad, True, None)]
        if reglas.superbalota:
            universos.append(("superbalota", "Superbalota",
                              m_frecuencia.calcular_frecuencia_superbalota(historico, *reglas.superbalota), 1, True, None))
        return universos
    universos = [("numeros", "Números (balotas)", m_frecuencia.calcular_frecuencia_numeros_colorloto(historico, lo, hi),
                  reglas.cantidad, False, None)]
    motivo = None if reglas.paleta_estable else ("la paleta de colores cambió dentro de la muestra: no hay un único "
                                                 "conjunto de colores con el que comparar")
    universos.append(("colores", "Colores (balotas)", m_frecuencia.calcular_frecuencia_colores(historico, reglas.colores),
                      reglas.cantidad, False, motivo))
    universos.append(("pares", "Pares número-color (balotas)",
                      m_frecuencia.calcular_frecuencia_pares_numero_color(historico, lo, hi, reglas.colores),
                      reglas.cantidad, False, motivo))
    return universos


def _pruebas_uniformidad(reglas: ReglasJuego, historico: Sequence, parametros: dict) -> dict:
    if not historico:
        return _sin_datos()
    resumen, tablas, notas = [], [], []
    for uid, nombre, frecuencias, k, sin_reemplazo, motivo in _universos_uniformidad(reglas, historico):
        n = len(frecuencias)
        esperado = len(historico) * k / n
        fila = {"valor": nombre, "categorias": n, "sorteos": len(historico), "esperado": esperado,
                "estadistico": None, "grados_libertad": None, "p_value": None,
                "metodo": "chi² con corrección sin reemplazo" if sin_reemplazo and k > 1 else "chi² de Pearson",
                "tipo_p_value": TIPO_P_ASINTOTICO, "motivo": motivo}
        if motivo is None:
            prueba = chi_cuadrado_uniformidad(frecuencias, k, sin_reemplazo=sin_reemplazo)
            fila.update(estadistico=prueba.estadistico, grados_libertad=prueba.grados_libertad, p_value=prueba.p_value)
            if esperado < ESPERADO_MINIMO_CHI2:
                fila["motivo"] = f"esperado por categoría {esperado:.1f} < {ESPERADO_MINIMO_CHI2:g}: aproximación poco fiable"
            tablas.append({"id": uid, "titulo": f"{nombre}: observado frente a esperado",
                           "columnas": [_col("valor", "Valor", "texto"), _col("observado", "Observado", "entero",
                                                                               "balotas" if reglas.es_colorloto else "sorteos"),
                                        _col("esperado", "Esperado", "dec1"),
                                        _col("residuo", "Residuo de Pearson", "dec2", "(O−E)/√E")],
                           "filas": [{"valor": f.valor, "observado": f.apariciones, "esperado": esperado,
                                      "residuo": (f.apariciones - esperado) / esperado ** 0.5}
                                     for f in sorted(frecuencias, key=lambda f: _orden_valor(f.valor))],
                           "nota": None})
        resumen.append(fila)
    tablas.insert(0, {"id": "resumen", "titulo": "Pruebas de uniformidad (chi-cuadrado)",
                      "columnas": [_col("valor", "Universo", "texto"), _col("categorias", "Categorías"),
                                   _col("esperado", "Esperado por categoría", "dec1"),
                                   _col("estadistico", "χ²", "dec2"), _col("grados_libertad", "Grados de libertad"),
                                   _col("p_value", "p-value", "p"), _col("tipo_p_value", "Tipo de p-value", "tipo_p"),
                                   _col("metodo", "Método", "texto"), _col("motivo", "Observación", "texto")],
                      "filas": resumen, "nota": None})
    notas.append("Los p-value de esta página son asintóticos: salen de la distribución chi-cuadrado con N−1 grados "
                 "de libertad, a la que el estadístico se aproxima cuando crece el número de sorteos. No son exactos "
                 f"para una muestra finita; con frecuencias esperadas menores que {ESPERADO_MINIMO_CHI2:g} la "
                 "aproximación es poco fiable y la tabla lo avisa.")
    if not reglas.es_colorloto:
        notas.append(f"Sin reemplazo ({reglas.cantidad} números distintos de {reglas.universo}), el χ² de Pearson se "
                     f"multiplica por (N−1)/(N−K) = {reglas.universo - 1}/{reglas.universo - reglas.cantidad} para que su "
                     "distribución límite sea esa chi-cuadrado; con K=1 (superbalota) el factor es 1. El factor corrige "
                     "la escala del estadístico, pero no convierte el contraste en una prueba exacta para muestras "
                     "finitas.")
    else:
        notas.append("ColorLoto: se cuentan balotas (con repetición) bajo el supuesto de balotas independientes y "
                     "uniformes, que no se ha verificado con el reglamento.")
    notas.append(f"Varias pruebas a la vez: con α = {ALFA:g} alguna puede dar p bajo por azar. Un p-value bajo no "
                 "indica qué valores saldrán; uno alto no prueba que el sorteo sea uniforme.")
    primera = next((t for t in tablas if t["id"] != "resumen"), None)
    grafica = None if primera is None else {
        "titulo": f"Residuo de Pearson — {primera['titulo'].split(':')[0]}", "tabla": primera["id"],
        "etiqueta": "valor", "valor": "residuo", "unidad": "(O−E)/√E", "referencia": None}
    indicadores = [_ind(f"p-value: {f['valor']}", f["p_value"],
                        "chi², asintótico" if f["p_value"] is not None else "no aplica", "p") for f in resumen]
    return _contenido(indicadores=indicadores, tablas=tablas, grafica=grafica,
                      notas=notas)


def _independencia(tamano: int):
    def construir(reglas: ReglasJuego, historico: Sequence, parametros: dict) -> dict:
        if not historico:
            return _sin_datos()
        lo, hi = reglas.rango
        k, n, t = reglas.cantidad, reglas.universo, len(historico)
        motor = m_independencia.calcular_independencia_pares if tamano == 2 else m_independencia.calcular_independencia_trios
        corregidos = aplicar_correccion_benjamini_hochberg(motor(historico, lo, hi, k), ALFA)
        esperado = t * m_independencia._probabilidad_teorica_coocurrencia(n, k, tamano)
        ordenados = sorted(corregidos, key=lambda r: (r.p_value, [int(e) for e in r.elementos]))
        nombre, plural = ("par", "pares") if tamano == 2 else ("trío", "tríos")
        filas = [{"valor": "-".join(r.elementos), "observado": int(r.estadistico), "esperado": esperado,
                  "p_value": r.p_value, "p_ajustado": r.p_value_ajustado}
                 for r in ordenados[:FILAS_INDEPENDENCIA]]
        return _contenido(
            indicadores=[_ind(f"Pruebas ({plural} posibles)", len(corregidos), "pruebas"),
                         _ind(f"Coocurrencias esperadas por {nombre}", esperado, "sorteos", "dec2"),
                         _ind("p-value mínimo", ordenados[0].p_value if ordenados else None, "", "p"),
                         _ind(f"Con p ajustado (BH) < {ALFA:g}", sum(1 for r in corregidos if r.significativo), "pruebas")],
            tablas=[{"id": "independencia", "titulo": f"Los {FILAS_INDEPENDENCIA} {plural} con menor p-value",
                     "columnas": [_col("valor", nombre.capitalize(), "texto"),
                                  _col("observado", "Sorteos con el " + nombre, "entero", "sorteos"),
                                  _col("esperado", "Esperado", "dec2", "sorteos"), _col("p_value", "p-value", "p"),
                                  _col("p_ajustado", "p ajustado (BH)", "p")],
                     "filas": filas, "nota": None}],
            notas=[f"Una prueba binomial exacta por cada {nombre} posible (incluidos los nunca observados): ¿sus "
                   f"números aparecen juntos en más o menos sorteos que lo esperado si el sorteo elige {k} de {n} al "
                   "azar?",
                   "Con cientos o miles de pruebas, los p-value se ajustan por Benjamini-Hochberg (tasa de falsos "
                   "descubrimientos); el p-value sin ajustar no basta para llamar significativo a nada. "
                   "Benjamini-Hochberg controla esa tasa con pruebas independientes o con dependencia positiva; "
                   f"entre {plural} que comparten números no se ha verificado.",
                   "Un " + nombre + " con p bajo no tiene más probabilidad de salir en el próximo sorteo."])
    return construir


def _como_p_value(c) -> str:
    if c.contraste == m_correlaciones.CONTRASTE_EXACTO:
        return f"Permutación exacta, {c.permutaciones} ordenaciones"
    if c.contraste == m_correlaciones.CONTRASTE_MONTE_CARLO:
        return f"Permutación Monte Carlo, B = {c.permutaciones}, semilla {m_correlaciones.SEMILLA_MONTE_CARLO}"
    return "No se calcula"


def _observacion(c) -> str:
    """Límites del p-value en pantalla, sin repetir el método (columna «Cómo se obtiene el p-value»)."""
    if c.motivo:
        return f"{c.motivo[0].upper()}{c.motivo[1:]}. Sin coeficiente no hay p-value."
    if c.contraste == m_correlaciones.CONTRASTE_EXACTO:
        return "Supone que, bajo H0, todas las ordenaciones son igual de probables."
    if c.contraste == m_correlaciones.CONTRASTE_MONTE_CARLO:
        return "p = (1 + k)/(1 + B); desviación típica ≤ 0,005 frente a la exacta."
    return f"{c.motivo_p_value[0].upper()}{c.motivo_p_value[1:]}."


def _filas_correlacion(pregunta: str, pearson, spearman, unidad_n: str) -> list[dict]:
    """Una fila por método. `motivo`: por qué no hay coeficiente; `motivo_p_value`: cómo se obtuvo el
    p-value y sus límites, o por qué no hay (texto completo del motor); `como_p_value` y `observacion`
    lo resumen para la pantalla."""
    return [{"valor": pregunta, "metodo": c.metodo.capitalize(), "coeficiente": c.coeficiente, "p_value": c.p_value,
             "contraste": c.contraste, "permutaciones": c.permutaciones, "como_p_value": _como_p_value(c),
             "n": c.n, "pares": f"{c.n} {unidad_n}", "motivo": c.motivo, "motivo_p_value": c.motivo_p_value,
             "observacion": _observacion(c)}
            for c in (pearson, spearman)]


def _correlaciones(reglas: ReglasJuego, historico: Sequence, parametros: dict) -> dict:
    if not historico:
        return _sin_datos()
    lo, hi = reglas.rango
    if reglas.es_colorloto:
        serial = m_correlaciones.calcular_correlacion_serial_sumas_colorloto(historico)
        mitades = m_correlaciones.calcular_estabilidad_frecuencia_numeros_colorloto(historico, lo, hi)
    else:
        serial = m_correlaciones.calcular_correlacion_serial_sumas(historico)
        mitades = m_correlaciones.calcular_estabilidad_frecuencia_numeros(historico, lo, hi)
    filas = (_filas_correlacion("Suma del sorteo frente a la del sorteo anterior", serial.pearson, serial.spearman,
                                "transiciones")
             + _filas_correlacion("Apariciones por número: primera mitad frente a segunda", mitades.pearson,
                                  mitades.spearman, "números"))
    tablas = [{"id": "correlaciones", "titulo": "Correlaciones de Pearson y Spearman",
               "columnas": [_col("valor", "Pregunta", "texto"), _col("metodo", "Método", "texto"),
                            _col("coeficiente", "Coeficiente", "dec3"), _col("p_value", "p-value", "p"),
                            _col("como_p_value", "Cómo se obtiene el p-value", "texto"),
                            _col("pares", "Pares usados", "texto"),
                            _col("observacion", "Observación", "texto")],
               "filas": filas, "nota": None}]
    indicadores = [_ind("Pearson, suma frente a la del sorteo anterior", serial.pearson.coeficiente, "coeficiente", "dec3"),
                   _ind("Spearman, apariciones primera frente a segunda mitad", mitades.spearman.coeficiente,
                        "coeficiente", "dec3"),
                   _ind("Transiciones N → N+1", serial.transiciones, "transiciones")]
    notas = ["Suma: pares (suma del sorteo N, suma del sorteo N+1) solo entre sorteos de numeración consecutiva."
             + (" ColorLoto suma los 6 números con repetición." if reglas.es_colorloto else " Sin la superbalota."),
             (f"Mitades: sorteos {mitades.primera[0]}–{mitades.primera[1]} ({mitades.sorteos_primera}) frente a "
              f"{mitades.segunda[0]}–{mitades.segunda[1]} ({mitades.sorteos_segunda}); se correlacionan las "
              "apariciones de cada número." if mitades.primera else "Mitades: la muestra no alcanza para dos mitades."),
             "Coeficientes: descriptivos (SciPy). p-value: no se usa el de SciPy, que en spearmanr es una "
             "aproximación para muestras grandes y en pearsonr supone pares independientes y normales.",
             "Suma: el p-value no se calcula. Las transiciones comparten sorteos (el sorteo N+1 de un par es el N "
             "del siguiente), así que los pares no son independientes y ningún contraste de pares independientes "
             "está justificado; el coeficiente sigue siendo descriptivo.",
             (f"Mitades: p-value por permutación de las apariciones de la segunda mitad entre los {mitades.categorias} "
              "números; la muestra son los números, no los sorteos. Bajo H0 (sorteos independientes y simétricos "
              "respecto de los números) esas apariciones son independientes de la primera mitad y todas sus "
              "ordenaciones son igual de probables. "
              + (f"Con {mitades.categorias} números se enumeran todas: permutación exacta."
                 if mitades.categorias <= m_correlaciones.MAXIMO_PERMUTACION_EXACTA else
                 f"Con {mitades.categorias} números no se enumeran todas: Monte Carlo con "
                 f"{m_correlaciones.PERMUTACIONES_MONTE_CARLO} ordenaciones y semilla fija "
                 f"{m_correlaciones.SEMILLA_MONTE_CARLO}, p = (1 + k)/(1 + B); reproducible, aproxima la permutación "
                 "exacta con desviación típica ≤ 0,005.")),
             "Bajo un sorteo uniforme e independiente se esperan coeficientes cercanos a 0. Un coeficiente distinto "
             "de 0 en una muestra no permite anticipar el próximo sorteo."]
    if reglas.es_colorloto:
        ind = m_correlaciones.calcular_independencia_numero_color(historico, lo, hi, reglas.colores)
        if ind.resultado is not None:
            indicadores += [_ind("χ² número × color", ind.resultado.estadistico, "", "dec2"),
                            _ind("Grados de libertad", ind.resultado.grados_libertad),
                            _ind("p-value número × color (asintótico)", ind.resultado.p_value, "chi-cuadrado límite", "p"),
                            _ind("Esperado mínimo por celda", ind.esperado_minimo, "balotas", "dec1")]
            tablas.append({"id": "contingencia", "titulo": "Balotas por número y color (observado / esperado)",
                           "columnas": [_col("valor", "Número", "texto")]
                           + [_col(c, c.capitalize(), "texto") for c in ind.colores],
                           "filas": [{"valor": numero, **{c: f"{ind.observado[i][j]} / {ind.esperado[i][j]:.1f}"
                                                          for j, c in enumerate(ind.colores)}}
                                     for i, numero in enumerate(ind.numeros)],
                           "nota": "Chi-cuadrado de independencia sin corrección de Yates; p-value asintótico, no "
                                   "exacto para una muestra finita."})
            if ind.esperado_minimo is not None and ind.esperado_minimo < ESPERADO_MINIMO_CHI2:
                notas.append(f"Alguna celda espera menos de {ESPERADO_MINIMO_CHI2:g} balotas: la aproximación "
                             "chi-cuadrado es poco fiable.")
        else:
            notas.append(f"Número × color: no se calcula ({ind.motivo}).")
        if ind.excluidos:
            notas.append("Sin balotas en la muestra (fuera de la tabla): " + ", ".join(ind.excluidos) + ".")
        notas.append("Número × color supone balotas independientes, supuesto no verificado con el reglamento.")
    estado = "ok"
    motivo = None
    if all(f["coeficiente"] is None for f in filas) and len(tablas) == 1:
        estado, motivo = "insuficiente", "La muestra no alcanza para calcular ninguna correlación."
    return _contenido(estado, motivo, indicadores=indicadores, tablas=tablas, notas=notas + _nota_huecos(historico))


# ---------------------------------------------------------------------------
# Cifras clave de las métricas ya existentes (para el panel)
# ---------------------------------------------------------------------------

def _top(frecuencias: Sequence, cantidad: int = 3, unidad: str = "% de sorteos", factor: float = 100.0,
         menores: bool = False) -> str:
    filas = sorted(frecuencias, key=lambda f: ((f.apariciones if menores else -f.apariciones), _orden_valor(f.valor)))
    decimales = 1 if factor == 100.0 else 3  # «balotas por sorteo» de ColorLoto: diferencias en milésimas
    return ", ".join(f"{f.valor} ({factor * f.frecuencia_relativa:.{decimales}f})" for f in filas[:cantidad]) + f" [{unidad}]"


def _moda(dist: Sequence, etiqueta: str) -> list[dict]:
    if not dist or not dist[0].total_sorteos:
        return []
    f = max(dist, key=lambda x: (x.apariciones, -_orden_valor(x.valor)[1]))
    return [_ind(f"Más frecuente ({f.valor} {etiqueta})", 100.0 * f.frecuencia_relativa, "% de sorteos", "dec1")]


def _al_menos_uno(dist: Sequence, etiqueta: str, unidad: str = "% de sorteos") -> list[dict]:
    if not dist or not dist[0].total_sorteos:
        return []
    total = dist[0].total_sorteos
    return [_ind(etiqueta, _pct(sum(f.apariciones for f in dist if f.valor != "0"), total), unidad, "dec1")]


def _r_frecuencia_numeros(reglas, historico):
    lo, hi = reglas.rango
    if reglas.es_colorloto:
        f = m_frecuencia.calcular_frecuencia_numeros_colorloto(historico, lo, hi)
        return [_ind("Más frecuentes", _top(f, unidad="balotas por sorteo", factor=1.0), "", "texto"),
                _ind("Menos frecuentes", _top(f, unidad="balotas por sorteo", factor=1.0, menores=True), "", "texto")]
    f = m_frecuencia.calcular_frecuencia_numeros(historico, lo, hi)
    return [_ind("Más frecuentes", _top(f, 5), "", "texto"), _ind("Menos frecuentes", _top(f, 5, menores=True), "", "texto")]


def _r_frecuencia_superbalota(reglas, historico):
    f = m_frecuencia.calcular_frecuencia_superbalota(historico, *reglas.superbalota)
    return [_ind("Más frecuentes", _top(f), "", "texto"), _ind("Menos frecuentes", _top(f, menores=True), "", "texto")]


def _r_observada_esperada(reglas, historico):
    lo, hi = reglas.rango
    filas = m_frecuencia.construir_tabla_frecuencia(m_frecuencia.calcular_frecuencia_numeros(historico, lo, hi),
                                                    reglas.cantidad, reglas.universo)
    mayor = max(filas, key=lambda f: f.diferencia)
    menor = min(filas, key=lambda f: f.diferencia)
    return [_ind(f"Mayor exceso sobre K/N (número {mayor.valor})", 100.0 * mayor.diferencia, "puntos porcentuales", "dec1"),
            _ind(f"Mayor defecto bajo K/N (número {menor.valor})", 100.0 * menor.diferencia, "puntos porcentuales", "dec1")]


def _r_mayor_atraso(atrasos):
    observados = [a for a in atrasos if a.atraso is not None]
    if not observados:
        return [_ind("Mayor atraso", None, "sorteos de distancia")]
    a = max(observados, key=lambda x: (x.atraso, -_orden_valor(x.valor)[1]))
    return [_ind(f"Mayor atraso ({a.valor})", a.atraso, "sorteos de distancia"),
            _ind("Nunca observados", sum(1 for x in atrasos if x.atraso is None), "valores")]


def _r_atrasos_numeros(reglas, historico):
    lo, hi = reglas.rango
    if reglas.es_colorloto:
        return _r_mayor_atraso(m_atrasos.calcular_atrasos_numeros_colorloto(historico, lo, hi))
    return _r_mayor_atraso(m_atrasos.calcular_atrasos_numeros(historico, lo, hi))


def _r_coocurrencia(filas, etiqueta):
    if not filas:
        return [_ind(etiqueta, "ninguna observada", "", "texto")]
    f = max(filas, key=lambda x: (x.soporte, [-_orden_valor(e)[1] for e in x.elementos]))
    return [_ind(f"{etiqueta} ({'-'.join(f.elementos)})", f.soporte, "sorteos")]


def _r_intervalos(filas):
    medias = [f.intervalo_promedio for f in filas if f.intervalo_promedio is not None]
    return [_ind("Promedio de los intervalos medios", statistics.mean(medias) if medias else None,
                 "sorteos de distancia", "dec1")]


def _r_ventana_colorloto(reglas, historico):
    return [_ind("Ventana por defecto", f"últimos {VENTANA_POR_DEFECTO} sorteos", "", "texto")]


def _r_periodo(reglas, historico):
    ultimo = historico[-1]
    return [_ind("Último periodo de la muestra", f"{ultimo.fecha.year}, {NOMBRE_MES[ultimo.fecha.month - 1]}, "
                 f"{NOMBRE_DIA.get(ultimo.dia_semana, ultimo.dia_semana)}", "", "texto")]


def _numerico(reglas: ReglasJuego) -> bool:
    return not reglas.es_colorloto


def _con_superbalota(reglas: ReglasJuego) -> bool:
    return not reglas.es_colorloto and reglas.superbalota is not None


def _colorloto(reglas: ReglasJuego) -> bool:
    return reglas.es_colorloto


def _todos(reglas: ReglasJuego) -> bool:
    return True


def _sin_superbalota(reglas: ReglasJuego) -> str:
    return (f"{reglas.nombre} no tiene superbalota." if not reglas.es_colorloto
            else "ColorLoto no tiene superbalota: cada sorteo son 6 balotas número-color.")


def _solo_numericos(motivo: str):
    return lambda reglas: motivo


def _segun_juego(numerico: Callable, colorloto: Callable) -> Callable:
    return lambda reglas, historico, parametros: (colorloto if reglas.es_colorloto else numerico)(
        reglas, historico, parametros)


def _r_sumas_colorloto(reglas, historico):
    return [_ind("Media de la suma", m_distribuciones.calcular_distribucion_sumas_colorloto(historico).media,
                 "suma", "dec1")]


def _r_intervalos_numeros_colorloto(reglas, historico):
    return _r_intervalos(m_atrasos.calcular_intervalos_historicos_numeros_colorloto(historico, *reglas.rango))


_MOTIVO_COLORLOTO_INDEPENDENCIA = (
    "ColorLoto permite repetir números dentro del sorteo y la probabilidad de coocurrencia bajo azar depende de "
    "una combinatoria con repetición no verificada con el reglamento (ver motor/independencia.py); su relación "
    "número-color se prueba en «Correlaciones».")
_MOTIVO_DECENAS = ("ColorLoto usa números de 1 a 7: cabe en una sola franja de diez y la distribución por decenas "
                   "no aporta información (ver «Bajos y altos»).")


def _definiciones() -> tuple[Definicion, ...]:
    d = Definicion
    lista = [
        # --- Frecuencias ---
        d("frecuencia-numeros", "Frecuencia de números", "frecuencias", _todos, resumen=_r_frecuencia_numeros),
        d("frecuencia-superbalota", "Frecuencia de superbalota", "frecuencias", _con_superbalota,
          resumen=_r_frecuencia_superbalota, motivo_no_aplica=_sin_superbalota),
        d("frecuencia-observada-esperada", "Observada frente a esperada", "frecuencias", _numerico,
          resumen=_r_observada_esperada,
          motivo_no_aplica=_solo_numericos("En ColorLoto lo observado frente a lo esperado está en «Pruebas de "
                                           "uniformidad», con balotas (con repetición).")),
        d("frecuencia-colores", "Frecuencia de colores", "frecuencias", _colorloto,
          resumen=lambda r, h: [_ind("Más frecuentes", _top(m_frecuencia.calcular_frecuencia_colores(h, r.colores),
                                                             unidad="balotas por sorteo", factor=1.0), "", "texto")]),
        d("frecuencia-pares-numero-color", "Frecuencia de pares número-color", "frecuencias", _colorloto,
          resumen=lambda r, h: [_ind("Más frecuentes", _top(m_frecuencia.calcular_frecuencia_pares_numero_color(
              h, *r.rango, r.colores), unidad="balotas por sorteo", factor=1.0), "", "texto")]),
        # --- Patrones temporales ---
        d("frecuencia-numeros-por-anio", "Frecuencia de números por año", "temporales", _todos, parametro="anio",
          construir=_segun_juego(_por_periodo("numeros", "anio"), _por_periodo("colorloto", "anio"))),
        d("frecuencia-numeros-por-mes", "Frecuencia de números por mes", "temporales", _todos, parametro="mes",
          construir=_segun_juego(_por_periodo("numeros", "mes"), _por_periodo("colorloto", "mes"))),
        d("frecuencia-numeros-por-dia-semana", "Frecuencia de números por día de la semana", "temporales", _todos,
          parametro="dia_semana",
          construir=_segun_juego(_por_periodo("numeros", "dia_semana"), _por_periodo("colorloto", "dia_semana"))),
        d("frecuencia-superbalota-por-anio", "Frecuencia de superbalota por año", "temporales", _con_superbalota,
          parametro="anio", construir=_por_periodo("superbalota", "anio"), motivo_no_aplica=_sin_superbalota),
        d("frecuencia-superbalota-por-mes", "Frecuencia de superbalota por mes", "temporales", _con_superbalota,
          parametro="mes", construir=_por_periodo("superbalota", "mes"), motivo_no_aplica=_sin_superbalota),
        d("frecuencia-superbalota-por-dia-semana", "Frecuencia de superbalota por día de la semana", "temporales",
          _con_superbalota, parametro="dia_semana", construir=_por_periodo("superbalota", "dia_semana"),
          motivo_no_aplica=_sin_superbalota),
        d("frecuencia-colores-por-anio", "Frecuencia de colores por año", "temporales", _colorloto, resumen=_r_periodo),
        d("frecuencia-colores-por-mes", "Frecuencia de colores por mes", "temporales", _colorloto, resumen=_r_periodo),
        d("frecuencia-colores-por-dia-semana", "Frecuencia de colores por día de la semana", "temporales", _colorloto,
          resumen=_r_periodo),
        d("frecuencia-pares-numero-color-por-anio", "Pares número-color por año", "temporales", _colorloto,
          resumen=_r_periodo),
        d("frecuencia-pares-numero-color-por-mes", "Pares número-color por mes", "temporales", _colorloto,
          resumen=_r_periodo),
        d("frecuencia-pares-numero-color-por-dia-semana", "Pares número-color por día de la semana", "temporales",
          _colorloto, resumen=_r_periodo),
        # --- Atrasos e intervalos ---
        d("atrasos-numeros", "Atrasos de números", "atrasos", _todos, resumen=_r_atrasos_numeros),
        d("atrasos-superbalota", "Atrasos de superbalota", "atrasos", _con_superbalota, construir=_atrasos_superbalota,
          motivo_no_aplica=_sin_superbalota),
        d("atrasos-colores", "Atrasos de colores", "atrasos", _colorloto,
          resumen=lambda r, h: _r_mayor_atraso(m_atrasos.calcular_atrasos_colores(h, r.colores))),
        d("atrasos-pares-numero-color", "Atrasos de pares número-color", "atrasos", _colorloto,
          resumen=lambda r, h: _r_mayor_atraso(m_atrasos.calcular_atrasos_pares_numero_color(h, *r.rango, r.colores))),
        d("intervalos-historicos-numeros", "Intervalos históricos de números", "atrasos", _todos,
          construir=_intervalos("numeros"), nueva_para=_numerico, resumen=_r_intervalos_numeros_colorloto),
        d("intervalos-historicos-superbalota", "Intervalos históricos de superbalota", "atrasos", _con_superbalota,
          construir=_intervalos("superbalota"), motivo_no_aplica=_sin_superbalota),
        d("intervalos-historicos-colores", "Intervalos históricos de colores", "atrasos", _colorloto,
          resumen=lambda r, h: _r_intervalos(m_atrasos.calcular_intervalos_historicos_colores(h, r.colores))),
        d("intervalos-historicos-pares-numero-color", "Intervalos históricos de pares número-color", "atrasos",
          _colorloto, resumen=lambda r, h: _r_intervalos(
              m_atrasos.calcular_intervalos_historicos_pares_numero_color(h, *r.rango, r.colores))),
        # --- Distribuciones ---
        d("distribucion-pares-impares", "Pares e impares", "distribuciones", _todos,
          resumen=lambda r, h: _moda(m_distribuciones.calcular_distribucion_pares_impares_colorloto(h, r.cantidad)
                                     if r.es_colorloto else
                                     m_distribuciones.calcular_distribucion_pares_impares(h, r.cantidad), "pares")),
        d("distribucion-altos-bajos", "Bajos y altos", "distribuciones", _todos,
          resumen=lambda r, h: _moda(
              m_distribuciones.calcular_distribucion_altos_bajos_colorloto(h, *r.rango, r.cantidad) if r.es_colorloto
              else m_distribuciones.calcular_distribucion_altos_bajos(h, *r.rango, r.cantidad), "bajos")),
        d("distribucion-sumas", "Distribución de sumas", "distribuciones", _todos, construir=_distribucion_sumas,
          nueva_para=_numerico, resumen=_r_sumas_colorloto),
        d("distribucion-decenas", "Números por decena", "distribuciones", _numerico, construir=_distribucion_decenas,
          motivo_no_aplica=_solo_numericos(_MOTIVO_DECENAS)),
        d("distribucion-pares-consecutivos", "Pares consecutivos", "distribuciones", _todos,
          resumen=lambda r, h: _al_menos_uno(
              m_consecutivos.calcular_distribucion_pares_consecutivos_colorloto(h, *r.rango, r.cantidad)
              if r.es_colorloto else m_consecutivos.calcular_distribucion_pares_consecutivos(h, *r.rango, r.cantidad),
              "Sorteos con al menos un par consecutivo")),
        d("distribucion-racha-maxima", "Racha máxima de consecutivos", "distribuciones", _todos,
          resumen=lambda r, h: _moda(
              m_consecutivos.calcular_distribucion_racha_maxima_colorloto(h, *r.rango, r.cantidad) if r.es_colorloto
              else m_consecutivos.calcular_distribucion_racha_maxima(h, *r.rango, r.cantidad), "de racha")),
        d("distribucion-trios-consecutivos", "Tríos consecutivos", "distribuciones", _todos,
          resumen=lambda r, h: _al_menos_uno(
              m_consecutivos.calcular_distribucion_trios_consecutivos_colorloto(h, *r.rango, r.cantidad)
              if r.es_colorloto else m_consecutivos.calcular_distribucion_trios_consecutivos(h, *r.rango, r.cantidad),
              "Sorteos con al menos un trío consecutivo")),
        d("maximo-repeticion-color", "Máximo color repetido", "distribuciones", _colorloto,
          resumen=lambda r, h: _moda(m_distribuciones.calcular_maximo_repeticion_color_por_sorteo(h, r.cantidad),
                                     "balotas del mismo color")),
        d("distribucion-conteo-color", "Conteo por color", "distribuciones", _colorloto,
          resumen=lambda r, h: [_ind("Colores en la paleta", len(r.colores), "colores")]),
        # --- Coocurrencia y repetición ---
        d("repeticiones-entre-sorteos", "Repeticiones entre sorteos", "coocurrencia", _todos,
          resumen=lambda r, h: _al_menos_uno(
              m_repeticiones.calcular_repeticiones_entre_sorteos_colorloto(h, *r.rango, r.cantidad) if r.es_colorloto
              else m_repeticiones.calcular_repeticiones_entre_sorteos(h, *r.rango, r.cantidad),
              "Transiciones con al menos un número repetido", "% de transiciones")),
        d("repeticion-superbalota", "Repetición de superbalota", "coocurrencia", _con_superbalota,
          construir=_repeticion_superbalota, motivo_no_aplica=_sin_superbalota),
        d("coocurrencia-pares", "Coocurrencia de pares", "coocurrencia", _todos,
          resumen=lambda r, h: _r_coocurrencia(
              m_coocurrencia.calcular_coocurrencia_pares_colorloto(h, *r.rango, r.cantidad) if r.es_colorloto
              else m_coocurrencia.calcular_coocurrencia_pares(h, *r.rango, r.cantidad), "Par más frecuente")),
        d("coocurrencia-trios", "Coocurrencia de tríos", "coocurrencia", _todos,
          resumen=lambda r, h: _r_coocurrencia(
              m_coocurrencia.calcular_coocurrencia_trios_colorloto(h, *r.rango, r.cantidad) if r.es_colorloto
              else m_coocurrencia.calcular_coocurrencia_trios(h, *r.rango, r.cantidad), "Trío más frecuente")),
        d("coocurrencia-pares-colores", "Coocurrencia de pares de colores", "coocurrencia", _colorloto,
          resumen=lambda r, h: _r_coocurrencia(m_coocurrencia.calcular_coocurrencia_pares_colores(h),
                                               "Par más frecuente")),
        d("coocurrencia-trios-colores", "Coocurrencia de tríos de colores", "coocurrencia", _colorloto,
          resumen=lambda r, h: _r_coocurrencia(m_coocurrencia.calcular_coocurrencia_trios_colores(h),
                                               "Trío más frecuente")),
        # --- Ventana reciente ---
        d("comparacion-frecuencia-numeros-por-ventana", "Números: ventana reciente", "ventana", _todos,
          parametro="ventana", construir=_ventana("numeros"), nueva_para=_numerico, resumen=_r_ventana_colorloto),
        d("comparacion-frecuencia-superbalota-por-ventana", "Superbalota: ventana reciente", "ventana",
          _con_superbalota, parametro="ventana", construir=_ventana("superbalota"), motivo_no_aplica=_sin_superbalota),
        d("comparacion-frecuencia-colores-por-ventana", "Colores: ventana reciente", "ventana", _colorloto,
          resumen=_r_ventana_colorloto),
        d("comparacion-frecuencia-pares-numero-color-por-ventana", "Pares número-color: ventana reciente", "ventana",
          _colorloto, resumen=_r_ventana_colorloto),
        # --- Pruebas y correlaciones ---
        d("pruebas-uniformidad", "Pruebas de uniformidad (chi-cuadrado)", "pruebas", _todos,
          construir=_pruebas_uniformidad),
        d("independencia-pares", "Independencia de pares", "pruebas", _numerico, construir=_independencia(2),
          motivo_no_aplica=_solo_numericos(_MOTIVO_COLORLOTO_INDEPENDENCIA)),
        d("independencia-trios", "Independencia de tríos", "pruebas", _numerico, construir=_independencia(3),
          motivo_no_aplica=_solo_numericos(_MOTIVO_COLORLOTO_INDEPENDENCIA)),
        d("correlaciones", "Correlaciones", "pruebas", _todos,
          construir=_correlaciones),
    ]
    return tuple(lista)


CATALOGO: tuple[Definicion, ...] = _definiciones()
POR_SLUG: dict[str, Definicion] = {m.slug: m for m in CATALOGO}


def metricas_nuevas(reglas: ReglasJuego) -> list[Definicion]:
    """Métricas con página de este módulo para el juego (las que la Fase 5 añadió)."""
    return [m for m in CATALOGO if m.aplica(reglas) and m.es_nueva(reglas)]


def construir_metrica(slug: str, reglas: ReglasJuego, historico: Sequence, parametros: dict | None = None) -> dict:
    """Contenido de una métrica NUEVA sobre `historico` ya cortado y ordenado por numero_sorteo.
    KeyError si el slug no existe; ValueError si no es una métrica nueva para ese juego."""
    definicion = POR_SLUG[slug]
    if not (definicion.aplica(reglas) and definicion.es_nueva(reglas)):
        raise ValueError(f"'{slug}' no es una métrica de la Fase 5 para {reglas.codigo}")
    contenido = definicion.construir(reglas, historico, dict(parametros or {}))
    return {"slug": slug, "titulo": definicion.titulo, "grupo": definicion.grupo, "parametro": definicion.parametro,
            **contenido}


def construir_panel(reglas: ReglasJuego, historico: Sequence) -> list[dict]:
    """Todas las métricas del juego en una sola vista, agrupadas, sobre la MISMA muestra (`historico`
    ya cortado): cifras clave de cada una, si su página es nueva o anterior, y las que no aplican al
    juego con su motivo. Las métricas nuevas usan su construcción completa con los parámetros por
    defecto; las anteriores, las mismas funciones del motor que sus recetas."""
    grupos = []
    for clave, titulo in GRUPOS:
        entradas = []
        for m in CATALOGO:
            if m.grupo != clave:
                continue
            if not m.aplica(reglas):
                if m.motivo_no_aplica is not None:
                    entradas.append({"slug": m.slug, "titulo": m.titulo, "aplica": False, "nueva": False,
                                     "motivo": m.motivo_no_aplica(reglas), "estado": "no_aplica", "indicadores": []})
                continue
            nueva = m.es_nueva(reglas)
            if not historico:
                estado, indicadores = "sin_datos", []
            elif nueva:
                contenido = m.construir(reglas, historico, {})
                estado, indicadores = contenido["estado"], contenido["indicadores"][:4]
            else:
                estado, indicadores = "ok", (m.resumen(reglas, historico) if m.resumen else [])
            entradas.append({"slug": m.slug, "titulo": m.titulo, "aplica": True, "nueva": nueva, "motivo": None,
                             "estado": estado, "indicadores": indicadores})
        grupos.append({"clave": clave, "titulo": titulo, "metricas": entradas})
    return grupos
