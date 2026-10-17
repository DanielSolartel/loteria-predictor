"""
Fase 4: fiabilidad observada de probabilidades YA EMITIDAS. Modulo puro: no
lee la base, no entrena, no recalibra y no escribe ni modifica artefactos.

TRES CANTIDADES QUE NUNCA SE MEZCLAN:
1. la probabilidad que EMITIO el modelo (congelada en su artefacto);
2. el RENDIMIENTO OBSERVADO de una linea o version sobre los sorteos ya
   ocurridos (perdidas frente a la uniforme del mismo artefacto y objetivo,
   y aciertos observados frente a los esperados en sus extremos);
3. la INCERTIDUMBRE de esas cifras por ser una muestra finita y dependiente
   (intervalo bootstrap por bloques). No hay una «puntuacion de confianza»
   ni etiquetas alta/media/baja.

CONTRATO ESTADISTICO (version `VERSION`):
- Unidad de observacion: el SORTEO (objetivo). Las filas de un sorteo (43,
  39 o ~42 candidatos y la superbalota) se resumen en UNA cifra por sorteo
  antes de remuestrear: no son ensayos independientes.
- Series por linea, tipo de evaluacion y componente (numeros, pares de
  ColorLoto y superbalota, siempre por separado), ordenadas por objetivo:
  * `diferencia_log_loss` y `diferencia_brier`: perdida del modelo menos
    perdida de la uniforme del MISMO artefacto y objetivo (negativa = menor
    perdida en ese sorteo). Numeros: Log Loss y Brier binarios medios por
    candidato; ColorLoto: por balota; superbalota: multiclase.
  * `fuertes_observado_menos_esperado` / `debiles_...`: en los `EXTREMO`
    candidatos de mayor (menor) probabilidad emitida, aciertos observados
    menos aciertos esperados por el propio modelo. Numeros: esperado = suma
    de sus marginales, observado = cuantos salieron. ColorLoto: esperado =
    6 x suma de la probabilidad por balota de esos pares, observado = suma
    de sus multiplicidades en el resultado (se conserva la interpretacion de
    multiplicidad / 6; nunca «aparecer al menos una vez»). Superbalota:
    esperado = suma de las probabilidades de esas clases, observado = 1 si
    salio una de ellas.
- Estimacion: la media de la serie. Incertidumbre: intervalo de percentiles
  al `NIVEL` con bootstrap de BLOQUES MOVILES (Kunsch 1989) sobre la serie
  temporal de sorteos, longitud de bloque fija `ceil(n^(1/3))` (orden de
  Hall, Horowitz y Jing 1995 para varianza y sesgo; regla declarada de
  antemano, no ajustada a los datos), `REMUESTREOS` remuestras y semilla
  derivada de la identidad de la serie y de los objetivos incluidos (la
  misma muestra da el mismo intervalo, se pida con `hasta` o sin el). Las
  diferencias de perdida por periodo siguen el enfoque de Diebold y Mariano
  (1995) para comparar pronosticos con errores dependientes; aqui no se
  hace un contraste de hipotesis.
- Solo con `MINIMO_SORTEOS` o mas sorteos se calcula el intervalo. Es un
  umbral operativo de calculo, NO una validacion: un intervalo calculado no
  acredita ventaja futura, y con muestras pequenas la cobertura real puede
  quedar por debajo de la nominal.
- Supuestos: estacionariedad debil y dependencia de corto alcance. NO cubre
  la seleccion de un modelo despues de ver una comparacion (sesgo de
  seleccion), cambios de regimen, ni las emisiones excluidas.

ESTADOS (siempre con su motivo): `estimable` (n >= minimo),
`muestra_insuficiente` (1 <= n < minimo: media sin intervalo),
`sin_resultados` (hay emisiones pero ningun resultado observado todavia),
`sin_base` (la base no respondio: no se sabe), `excluidas` (hay resultados
pero ninguna emision se pudo admitir), `sin_datos` (no hay emisiones de esa
linea y tipo), `no_disponible` (el artefacto no guarda la serie necesaria)
y `fallo_de_calculo`.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Sequence

import numpy as np

VERSION = "fase4-fiabilidad-1"
VERSION_CLASIFICACION_RECETA = "fase4-componentes-receta-2"
# Criterio exclusivamente de PRESENTACION, no de equivalencia ni de contraste.
# Los datos y los limites bootstrap conservan su precision y signo originales.
UMBRAL_PRESENTACION_CERO = 1e-12
NIVEL = 0.95
REMUESTREOS = 2000
MINIMO_SORTEOS = 30
EXTREMO = {"numeros": 10, "pares": 10, "superbalota": 4}
METRICAS = ("diferencia_log_loss", "diferencia_brier", "fuertes_observado_menos_esperado",
            "debiles_observado_menos_esperado")
ETIQUETAS = {
    "diferencia_log_loss": "Δ Log Loss (modelo − uniforme) por sorteo",
    "diferencia_brier": "Δ Brier (modelo − uniforme) por sorteo",
    "fuertes_observado_menos_esperado": "aciertos observados − esperados en los candidatos más probables",
    "debiles_observado_menos_esperado": "aciertos observados − esperados en los candidatos menos probables",
}
ESTADOS = ("estimable", "muestra_insuficiente", "sin_resultados", "sin_base", "excluidas", "sin_datos",
           "no_disponible", "fallo_de_calculo")
SIN_TIPO = (None, "sin_clasificacion")  # mismo criterio que `resultados_procedencias.de_tipo`
TIPOS_DE_EVALUACION = {
    "seguimiento": "Seguimiento: emisiones cuyo objetivo no estaba cargado en la base local al emitir.",
    "retrospectiva": ("Retrospectiva: emisiones cuyo objetivo ya estaba en la base al emitir (reconstrucción con "
                      "datos hasta el corte)."),
    "evaluacion_de_receta": ("Evaluación de la receta en su informe del laboratorio: reajustes por bloque antes de "
                             "cada bloque de objetivos (walk-forward). Mide la receta, no un estimador congelado."),
}
FUENTES = (
    {"cita": "Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. "
             "The Annals of Statistics, 17(3), 1217-1241.", "doi": "10.1214/aos/1176347265",
     "uso": "bootstrap de bloques móviles para la media de una serie estacionaria con dependencia"},
    {"cita": "Hall, P., Horowitz, J. L. y Jing, B.-Y. (1995). On blocking rules for the bootstrap with dependent "
             "data. Biometrika, 82(3), 561-574.", "doi": "10.1093/biomet/82.3.561",
     "uso": "orden de magnitud de la longitud de bloque (n^(1/3) para varianza y sesgo)"},
    {"cita": "Diebold, F. X. y Mariano, R. S. (1995). Comparing predictive accuracy. Journal of Business & "
             "Economic Statistics, 13(3), 253-263.", "doi": None,
     "uso": "comparar dos pronósticos con la serie de diferencias de pérdida por periodo, con dependencia serial"},
    {"cita": "Gneiting, T. y Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. "
             "Journal of the American Statistical Association, 102(477), 359-378.",
     "doi": "10.1198/016214506000001437", "uso": "Log Loss y Brier como reglas de puntuación propias"},
)
METODO = {
    "version": VERSION, "unidad": "sorteo (una cifra por sorteo; los candidatos de un sorteo no son independientes)",
    "estimacion": "media de la serie de sorteos",
    "incertidumbre": (f"intervalo de percentiles al {NIVEL:.0%} con bootstrap de bloques móviles; bloque "
                      f"ceil(n^(1/3)); {REMUESTREOS} remuestras; semilla derivada de la línea, el tipo, el "
                      "componente, la cifra y los objetivos incluidos (la misma muestra da el mismo intervalo)"),
    "minimo_para_intervalo": MINIMO_SORTEOS,
    "supuestos": "estacionariedad débil y dependencia de corto alcance de la serie de sorteos",
    "limitaciones": [
        "Con muestras pequeñas la cobertura real del intervalo puede quedar por debajo de la nominal.",
        "No corrige la selección de un modelo después de ver una comparación (sesgo de selección).",
        "No cubre cambios de régimen ni las emisiones excluidas o pendientes.",
        f"El umbral de {MINIMO_SORTEOS} sorteos solo decide si se calcula el intervalo: no es una validación.",
        "Ninguna cifra acredita ventaja futura: siguen experimental_no_acreditado, el NO-GO de AE-39 y "
        "AUTORIZA_EVALUACION = False.",
    ],
    "extremos": dict(EXTREMO),
    "presentacion": {
        "umbral_absoluto_proximo_a_cero": UMBRAL_PRESENTACION_CERO,
        "criterio": ("Una media con magnitud hasta 1e-12 se describe como próxima a 0, solo para su lectura. "
                     "El umbral se declara siete órdenes por debajo del paso decimal 0.00001; no diagnostica "
                     "el origen de la diferencia ni sustituye valores por cero. "
                     "No afirma igualdad matemática ni relevancia estadística. Media e intervalo originales "
                     "se conservan; la inclusión de 0 se decide con los límites originales."),
        "formato": ("Cinco decimales; todo valor no nulo de magnitud menor que 0.00005 se muestra en "
                    "notación científica con cinco cifras significativas, incluidos los límites del intervalo."),
    },
    "fuentes": [dict(f) for f in FUENTES],
}


class FalloDeCalculo(ValueError):
    pass


# ---------------------------------------------------------------------------
# Bootstrap de bloques moviles
# ---------------------------------------------------------------------------

def longitud_de_bloque(n: int) -> int:
    return max(1, math.ceil(n ** (1 / 3) - 1e-12))


def semilla_de(*partes) -> int:
    texto = json.dumps(partes, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return int(hashlib.sha256(texto.encode("utf-8")).hexdigest()[:15], 16)


def bootstrap_por_bloques(valores: Sequence[float], semilla: int, *, remuestreos: int = REMUESTREOS,
                          nivel: float = NIVEL, bloque: int | None = None) -> dict:
    """Media de `valores` (en orden temporal) e intervalo de percentiles por
    bootstrap de bloques moviles: cada remuestra concatena bloques de
    longitud `bloque` que empiezan en posiciones uniformes 0..n-bloque y se
    recorta a n."""
    x = np.asarray(valores, dtype=float)
    n = len(x)
    if n == 0:
        raise FalloDeCalculo("serie vacia")
    if not np.all(np.isfinite(x)):
        raise FalloDeCalculo("la serie tiene valores no finitos")
    l = min(bloque or longitud_de_bloque(n), n)
    k = math.ceil(n / l)
    rng = np.random.Generator(np.random.PCG64(semilla))
    inicios = rng.integers(0, n - l + 1, size=(remuestreos, k))
    indices = (inicios[:, :, None] + np.arange(l)).reshape(remuestreos, k * l)[:, :n]
    medias = x[indices].mean(axis=1)
    alfa = (1 - nivel) / 2
    inferior, superior = np.quantile(medias, [alfa, 1 - alfa])
    return {"media": float(x.mean()), "intervalo": [float(inferior), float(superior)], "bloque": l,
            "remuestreos": remuestreos, "semilla": semilla, "nivel": nivel,
            "error_estandar_bootstrap": float(medias.std(ddof=1)) if remuestreos > 1 else None}


def formatear_cifra(valor: float | None) -> str:
    """Formato comun para perdidas y aciertos, sin redondear un no-cero a 0.

    Solo devuelve texto: nunca modifica la media ni los limites de la API.
    El umbral de lectura no se usa para sustituir numeros por cero.
    """
    if valor is None:
        return "—"
    if 0 < abs(valor) < 0.00005:
        return format(valor, ".4e")
    return format(0.0 if valor == 0 else valor, ".5f")


def _lectura(metrica: str, media: float, intervalo: list[float] | None) -> str:
    if metrica.startswith("diferencia"):
        menor, mayor = "menor pérdida que la uniforme", "mayor pérdida que la uniforme"
    else:
        menor, mayor = "menos aciertos que los esperados por el modelo", "más aciertos que los esperados por el modelo"
    if 0 < abs(media) <= UMBRAL_PRESENTACION_CERO:
        signo = "positiva" if media > 0 else "negativa"
        texto = (f"Media original {signo}, de magnitud próxima a 0 (|media| ≤ 1e-12; "
                 "criterio de presentación, no igualdad matemática).")
    elif media == 0:
        texto = "Media numérica 0 en esta muestra."
    else:
        texto = f"Media en esta muestra: {menor if media < 0 else mayor}."
    if intervalo is None:
        return f"{texto} Muestra insuficiente para un intervalo."
    a, b = intervalo
    if b < 0:
        detalle = "El intervalo numérico no incluye 0: está por debajo."
    elif a > 0:
        detalle = "El intervalo numérico no incluye 0: está por encima."
    else:
        detalle = "El intervalo numérico incluye 0."
    return f"{texto} {detalle} No acredita ventaja futura ni relevancia estadística por sí solo."


def _no_disponible(metrica: str, motivo: str) -> dict:
    """Cifra que la fuente no permite calcular (misma forma que `estimar`)."""
    return {"estado": "no_disponible", "n": None, "media": None, "intervalo": None, "motivo": motivo,
            "etiqueta": ETIQUETAS[metrica]}


def estimar(valores: Sequence[float], identidad: tuple, metrica: str) -> dict:
    n = len(valores)
    if n == 0:
        return {"estado": "sin_datos", "n": 0, "media": None, "intervalo": None,
                "motivo": "no hay sorteos con este valor"}
    try:
        if n < MINIMO_SORTEOS:
            media = float(np.mean(np.asarray(valores, dtype=float)))
            if not math.isfinite(media):
                raise FalloDeCalculo("media no finita")
            return {"estado": "muestra_insuficiente", "n": n, "media": media, "intervalo": None,
                    "motivo": f"{n} sorteos; el intervalo se calcula desde {MINIMO_SORTEOS}",
                    "lectura": _lectura(metrica, media, None)}
        b = bootstrap_por_bloques(valores, semilla_de(VERSION, *identidad, metrica))
    except FalloDeCalculo as error:
        return {"estado": "fallo_de_calculo", "n": n, "media": None, "intervalo": None, "motivo": str(error)}
    return {"estado": "estimable", "n": n, **b, "motivo": None, "lectura": _lectura(metrica, b["media"], b["intervalo"])}


# ---------------------------------------------------------------------------
# Series por sorteo desde emisiones congeladas (filas de Producto 6)
# ---------------------------------------------------------------------------

def _extremos(candidatos: list, probabilidades: list, k: int) -> tuple[list[int], list[int]]:
    """Indices de los k de mayor y de menor probabilidad (empates por orden del candidato)."""
    orden = sorted(range(len(candidatos)), key=lambda i: (-probabilidades[i], str(candidatos[i])))
    k = min(k, len(orden) // 2) if len(orden) > 1 else len(orden)
    return orden[:k], orden[len(orden) - k:]


def valores_de_emision(fila: dict) -> dict[str, dict[str, float]]:
    """{componente: {metrica: valor}} de una emision INCLUIDA, con sus
    probabilidades congeladas y su resultado observado."""
    congelado, resultado, m = fila["congelado"], fila["resultado"], fila["metricas"]
    salida: dict[str, dict] = {}
    principal = "pares" if congelado["tipo"] == "pares" else "numeros"
    v = {"diferencia_log_loss": m["log_loss"] - m["log_loss_uniforme"], "diferencia_brier": m["brier"] - m["brier_uniforme"]}
    candidatos, p = congelado["candidatos"], congelado["probabilidad"]
    fuertes, debiles = _extremos(candidatos, p, EXTREMO[principal])
    if principal == "pares":
        multiplicidad = Counter(tuple(x) for x in resultado["pares"])
        balotas = len(resultado["pares"])

        def observado(indices):
            return sum(multiplicidad.get(tuple(candidatos[i]), 0) for i in indices)

        def esperado(indices):
            return balotas * sum(p[i] for i in indices)
    else:
        salieron = set(resultado["numeros"])

        def observado(indices):
            return sum(1 for i in indices if candidatos[i] in salieron)

        def esperado(indices):
            return sum(p[i] for i in indices)
    v["fuertes_observado_menos_esperado"] = observado(fuertes) - esperado(fuertes)
    v["debiles_observado_menos_esperado"] = observado(debiles) - esperado(debiles)
    v["_fuertes"] = (observado(fuertes), esperado(fuertes), len(fuertes))
    v["_debiles"] = (observado(debiles), esperado(debiles), len(debiles))
    salida[principal] = v
    sb, sbm = congelado.get("superbalota"), fila.get("superbalota")
    if sb and sbm and resultado.get("superbalota") is not None:
        c, q = sb["candidatos"], sb["probabilidad"]
        f, d = _extremos(c, q, EXTREMO["superbalota"])
        sale = resultado["superbalota"]
        w = {"diferencia_log_loss": sbm["log_loss"] - sbm["log_loss_uniforme"],
             "diferencia_brier": sbm["brier"] - sbm["brier_uniforme"],
             "fuertes_observado_menos_esperado": sum(1 for i in f if c[i] == sale) - sum(q[i] for i in f),
             "debiles_observado_menos_esperado": sum(1 for i in d if c[i] == sale) - sum(q[i] for i in d),
             "_fuertes": (sum(1 for i in f if c[i] == sale), sum(q[i] for i in f), len(f)),
             "_debiles": (sum(1 for i in d if c[i] == sale), sum(q[i] for i in d), len(d))}
        salida["superbalota"] = w
    return salida


def _huella(objetivos: Sequence[int]) -> str:
    """Identifica la MUESTRA efectiva (objetivos incluidos, en orden): la misma
    muestra da la misma semilla y el mismo intervalo, se pida con `hasta` o sin
    el."""
    return hashlib.sha256(",".join(str(o) for o in objetivos).encode("ascii")).hexdigest()[:16]


def _resumen_extremo(datos: list[tuple]) -> dict | None:
    if not datos:
        return None
    observado = sum(o for o, _, _ in datos)
    esperado = sum(e for _, e, _ in datos)
    return {"candidatos_por_sorteo": datos[0][2], "observado": observado, "esperado": esperado,
            "razon_observado_esperado": (observado / esperado) if esperado > 0 else None}


def _muestra(vista: list[dict], incluidas: list[dict], hasta: int | None) -> dict:
    excluidas = Counter((f["estado"], f.get("motivo") or "-") for f in vista if f["estado"] != "incluido")
    objetivos = [f["objetivo"] for f in incluidas]
    return {"emisiones": len(vista), "sorteos": len(objetivos),
            "periodo": [min(objetivos), max(objetivos)] if objetivos else None,
            "pendientes": sum(1 for f in vista if f["estado"] == "pendiente"),
            "sin_base": sum(1 for f in vista if f["estado"] == "sin_base"),
            "exclusiones": [{"estado": e, "motivo": m, "emisiones": n} for (e, m), n in sorted(excluidas.items())],
            "hasta": hasta}


def _estado_global(vista: list[dict], incluidas: list[dict]) -> tuple[str, str | None]:
    if not vista:
        return "sin_datos", "no hay emisiones de esta línea y tipo"
    if incluidas:
        return ("estimable" if len(incluidas) >= MINIMO_SORTEOS else "muestra_insuficiente"), None
    if any(f["estado"] == "sin_base" for f in vista):
        return "sin_base", "la base no respondió: no se sabe si hay resultados"
    if any(f["estado"] == "pendiente" for f in vista):
        return "sin_resultados", "las emisiones aún no tienen resultado observado"
    return "excluidas", "ninguna emisión con resultado se pudo admitir (ver exclusiones)"


def evaluar_emisiones(filas: Sequence[dict], tipo: str, identidad: tuple, hasta: int | None = None) -> dict:
    """Fiabilidad de UNA linea (procedencia:linea) y UN tipo (`seguimiento` o
    `retrospectiva`) con las filas de Producto 6. `hasta`: solo objetivos <=
    hasta (evidencia disponible en ese corte). Como en Producto 6, las
    emisiones sin clasificacion temporal entran en los dos tipos, siempre
    excluidas: cuentan en las exclusiones y no desaparecen en silencio."""
    vista = sorted((f for f in filas if f.get("tipo") in (tipo, *SIN_TIPO)
                    and (hasta is None or f["objetivo"] <= hasta)), key=lambda f: f["objetivo"])
    incluidas = [f for f in vista if f["estado"] == "incluido" and f.get("tipo") == tipo and f.get("metricas")
                 and f.get("congelado") and f.get("resultado")]
    estado, motivo = _estado_global(vista, incluidas)
    salida = {"tipo": tipo, "descripcion": TIPOS_DE_EVALUACION[tipo], "estado": estado, "motivo": motivo,
              "muestra": _muestra(vista, incluidas, hasta), "componentes": {}}
    if not incluidas:
        return salida
    series: dict[str, dict[str, list]] = {}
    extremos: dict[str, dict[str, list]] = {}
    objetivos: dict[str, list] = {}
    try:
        for f in incluidas:
            for componente, valores in valores_de_emision(f).items():
                objetivos.setdefault(componente, []).append(f["objetivo"])
                s = series.setdefault(componente, {m: [] for m in METRICAS})
                for m in METRICAS:
                    s[m].append(valores[m])
                e = extremos.setdefault(componente, {"fuertes": [], "debiles": []})
                e["fuertes"].append(valores["_fuertes"])
                e["debiles"].append(valores["_debiles"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        return {**salida, "estado": "fallo_de_calculo", "motivo": f"no se pudieron calcular las series: {error}"}
    for componente, s in series.items():
        salida["componentes"][componente] = {
            "sorteos": len(s["diferencia_log_loss"]),
            "metricas": {m: {**estimar(s[m], (*identidad, tipo, componente, _huella(objetivos[componente])), m),
                             "etiqueta": ETIQUETAS[m]} for m in METRICAS},
            "extremos": {"fuertes": _resumen_extremo(extremos[componente]["fuertes"]),
                         "debiles": _resumen_extremo(extremos[componente]["debiles"])}}
    if "superbalota" not in salida["componentes"] and any((f.get("congelado") or {}).get("superbalota")
                                                          for f in incluidas):
        salida["componentes"]["superbalota"] = {"estado": "no_disponible",
                                                "motivo": "sin superbalota observada en las emisiones incluidas"}
    return salida


# ---------------------------------------------------------------------------
# Evaluacion de la receta en un informe del laboratorio (reajustes por bloque)
# ---------------------------------------------------------------------------

def evaluar_informe(informe: dict, modelo: str, identidad: tuple, hasta: int | None = None) -> dict:
    """Serie por objetivo de la evaluacion walk-forward guardada en el informe
    (diferencias de Log Loss y de Brier frente a la uniforme del mismo
    informe). El informe no guarda probabilidades por candidato ni perdidas
    por objetivo de la superbalota: esas cifras quedan `no_disponible`."""
    candidatos = {c["id"]: c for c in informe.get("candidatos", [])}
    salida = {"tipo": "evaluacion_de_receta", "descripcion": TIPOS_DE_EVALUACION["evaluacion_de_receta"],
              "informe": informe.get("clave"), "corte_del_informe": (informe.get("datos") or {}).get("corte"),
              "componentes": {}}
    c = candidatos.get(modelo)
    uniforme = next((x for x in candidatos.values() if x.get("familia") == "uniforme"), None)
    if c is None:
        return {**salida, "estado": "sin_datos", "motivo": f"el informe no evalúa {modelo}",
                "muestra": {"sorteos": 0, "periodo": None, "hasta": hasta}}
    filas = [f for f in (c.get("por_objetivo") or []) if hasta is None or f["objetivo"] <= hasta]
    u = {f["objetivo"]: f for f in ((uniforme or {}).get("por_objetivo") or [])}
    if not filas:
        estado = "sin_datos" if c.get("estado") == "completo" else "excluidas"
        return {**salida, "estado": estado, "motivo": f"sin objetivos evaluados ({c.get('estado')})",
                "muestra": {"sorteos": 0, "periodo": None, "hasta": hasta}}
    filas = sorted(filas, key=lambda f: f["objetivo"])
    objetivos = [f["objetivo"] for f in filas]
    reglas = (informe.get("identidad") or {}).get("reglas", {})
    principal = "pares" if reglas.get("multiconjunto_de_pares_numero_color") else "numeros"
    # v1 consultaba `colores`, ausente en ReglasDelJuego.como_dict(): los
    # informes reales de ColorLoto se clasificaban como numeros. Corregir la
    # etiqueta no debe cambiar su secuencia bootstrap solo por renombrarla.
    # Se conserva ese token historico, con identidad explicita, sin alterar
    # las series, VERSION, ni las semillas de emisiones o de otros juegos.
    componente_semilla = "numeros" if principal == "pares" else principal
    salida["clasificacion_componentes"] = {
        "version": VERSION_CLASIFICACION_RECETA,
        "contrato_reglas": "multiconjunto_de_pares_numero_color",
    }
    dll = [f["diferencia_log_loss"] for f in filas]
    dbr = [f["brier"] - u[f["objetivo"]]["brier"] for f in filas if f["objetivo"] in u]
    muestra = _huella(objetivos)
    metricas = {"diferencia_log_loss": {**estimar(dll, (*identidad, "informe", componente_semilla, muestra), "diferencia_log_loss"),
                                        "etiqueta": ETIQUETAS["diferencia_log_loss"]}}
    metricas["diferencia_brier"] = (
        {**estimar(dbr, (*identidad, "informe", componente_semilla, muestra), "diferencia_brier"),
         "etiqueta": ETIQUETAS["diferencia_brier"]} if len(dbr) == len(filas) else
        _no_disponible("diferencia_brier", "el informe no tiene la uniforme en todos los objetivos"))
    for m in ("fuertes_observado_menos_esperado", "debiles_observado_menos_esperado"):
        metricas[m] = _no_disponible(m, "el informe no guarda las probabilidades por candidato de cada objetivo")
    salida.update(estado="estimable" if len(filas) >= MINIMO_SORTEOS else "muestra_insuficiente", motivo=None,
                  muestra={"sorteos": len(filas), "periodo": [objetivos[0], objetivos[-1]], "hasta": hasta,
                           "estado_del_candidato": c.get("estado"),
                           "excluidos_de_la_muestra_comun": len((informe.get("muestra_comun") or {}).get("excluidos")
                                                                or [])})
    salida["componentes"][principal] = {
        "sorteos": len(filas), "metricas": metricas, "extremos": None,
        "identidad_remuestreo": {
            "version_metodo": VERSION, "componente_semilla": componente_semilla,
            "motivo": ("Se conserva el token histórico numeros de la semilla de los informes serializados de "
                       "ColorLoto; pares corrige su clasificación, no los datos ni los intervalos."
                       if principal == "pares" else "El componente y su token de semilla no cambian."),
        },
    }
    if informe.get("superbalota"):
        salida["componentes"]["superbalota"] = {
            "estado": "no_disponible",
            "motivo": "el informe solo guarda agregados de la superbalota, no la serie por objetivo"}
    return salida


__all__ = ["VERSION", "NIVEL", "REMUESTREOS", "MINIMO_SORTEOS", "EXTREMO", "METODO", "FUENTES", "ESTADOS",
           "bootstrap_por_bloques", "longitud_de_bloque", "estimar", "evaluar_emisiones", "evaluar_informe",
           "valores_de_emision", "formatear_cifra", "VERSION_CLASIFICACION_RECETA", "UMBRAL_PRESENTACION_CERO",
           "FalloDeCalculo"]
