"""
Producto 4 -identidad, informes, pronosticos y seguimiento del laboratorio.

ESQUEMAS NUEVOS (no cambian los de Productos 1-3):
- `laboratorio-experimento/1`: informe de una comparacion. Lleva la
  instantanea canonica del historico usado (suficiente para reconstruirlo
  sin la base) y su huella.
- `laboratorio-pronostico/1`: pronostico generado con un candidato de un
  experimento. Su forma de `pronostico`, `datos` y `superbalota` es la que
  ya leen `resultados_observados` y `rendimiento_observado`, asi que el
  seguimiento reutiliza esas funciones.

IDENTIDAD DETERMINISTA (`clave`): SHA-256 canonico (AE-52) de juego,
reglas, paleta del corte, corte, huella del historico, version de las
variables, identidad/version/parametros de los candidatos, protocolo,
transformaciones de probabilidad, version de la implementacion y entorno
(Python, sistema, NumPy, SciPy, scikit-learn). La fecha de ejecucion, el
progreso y los tiempos van en `ejecucion`/`generacion`, fuera del cuerpo
reproducible y de la huella. Repetir la misma entrada devuelve lo ya
guardado; cambiar corte, historico, modelo, receta o protocolo da otra
clave. Un entorno distinto (p. ej. Windows frente a Linux, u otra version
de scikit-learn) tambien da otra clave: no se promete identidad bit a bit
entre entornos.

INTEGRIDAD. `huella_de_reproduccion` cubre el cuerpo; `sello` cubre todo
el archivo salvo el propio sello. Se distinguen tres comprobaciones:
integridad del archivo, reproduccion con la instantanea guardada y
coincidencia de ese historico con la base actual.

Modulo puro.
"""
from __future__ import annotations

import platform
from collections import Counter
from collections.abc import Sequence
from importlib import metadata

import numpy as np

from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import pronostico_colorloto as pcl
from app.application.ml import rendimiento_observado as rmet
from app.application.ml import resultados_observados as ro
from app.application.ml.propuesta_inferencia_prospectiva import AUTORIZA_EVALUACION
from app.application.ml.pronostico_experimental import ESTADO_DE_USO
from app.application.ml.registro_prospectivo import (
    EntradaRegistroInvalidaError,
    hash_entrada,
    serializar_entrada,
)

ESQUEMA_EXPERIMENTO = "laboratorio-experimento/1"
ESQUEMA_PRONOSTICO = "laboratorio-pronostico/1"
VERSION_IMPLEMENTACION = "producto4-2"
"""producto4-2: ajustes y predicciones en un proceso trabajador dedicado (con
`HILOS` fijado solo alli) y rechazo de probabilidades crudas infinitas antes
del ajuste de cardinalidad. Las recetas no cambian; la version cambia porque
una salida antes aceptada ahora puede quedar `salida_invalida`. Los informes y
pronosticos `producto4-1` se siguen leyendo sin reescribirse."""
VOLATILES_EXPERIMENTO = ("huella_de_reproduccion", "ejecucion", "sello")
VOLATILES_PRONOSTICO = ("huella_de_reproduccion", "generacion", "sello")


class ArtefactoLaboratorioError(ValueError):
    pass


def _version(paquete: str) -> str:
    try:
        return metadata.version(paquete)
    except metadata.PackageNotFoundError:
        return "desconocida"


def entorno() -> dict:
    return {"python": platform.python_version(), "sistema": platform.system(), "numpy": _version("numpy"),
            "scipy": _version("scipy"), "scikit-learn": _version("scikit-learn")}


def entorno_ml(entradas=()) -> dict:
    """Solo las nuevas recetas incluyen sus bibliotecas pertinentes.
    entorno() permanece intacto para preservar las identidades historicas.
    Leer metadata no importa bibliotecas nativas ni modifica sus hilos.
    """
    actual = entorno()
    familias = {e.familia for e in entradas}
    if "xgboost" in familias:
        actual["xgboost"] = _version("xgboost-cpu")
        if actual["xgboost"] == "desconocida":
            actual["xgboost"] = _version("xgboost")
    if "lightgbm" in familias:
        actual["lightgbm"] = _version("lightgbm")
    return actual


def huella(objeto: dict) -> str:
    try:
        return hash_entrada(serializar_entrada(objeto))
    except EntradaRegistroInvalidaError as error:
        raise ArtefactoLaboratorioError(str(error)) from error


def contexto() -> dict:
    if AUTORIZA_EVALUACION is not False:
        raise ArtefactoLaboratorioError("AUTORIZA_EVALUACION debe seguir en False")
    return {"AUTORIZA_EVALUACION": AUTORIZA_EVALUACION, "no_go_ae39": "vigente; el laboratorio no lo modifica",
            "resultado_acreditado": False,
            "uso": "comparacion exploratoria y pronosticos experimentales; no es evidencia prospectiva ni "
                   "ventaja predictiva acreditada"}


# ---------------------------------------------------------------------------
# Experimentos
# ---------------------------------------------------------------------------

def identidad_del_experimento(instantanea: lv.Instantanea, entradas: Sequence[lm.EntradaCatalogo],
                              protocolo: le.Protocolo) -> dict:
    return {"esquema": ESQUEMA_EXPERIMENTO, "implementacion": VERSION_IMPLEMENTACION, "juego": instantanea.codigo,
            "reglas": instantanea.reglas.como_dict(), "paleta_del_corte": list(instantanea.paleta()),
            "corte": instantanea.corte, "sha256_historico": instantanea.huella(),
            "version_de_variables": lv.VERSION_VARIABLES,
            "candidatos": [{"id": e.id, "version": e.version, "parametros": lm.parametros_de(e, protocolo.perfil)}
                           for e in entradas],
            "protocolo": protocolo.como_dict(),
            "transformaciones": {"cardinalidad": {"epsilon": lm.EPSILON, "tolerancia": lm.TOLERANCIA_CARDINALIDAD,
                                                  "metodo": "desplazamiento comun de logits por biseccion"},
                                 "poisson": {"delta": lm.DELTA_POISSON, "metodo": "normalizacion de intensidades"}},
            "semilla": lm.SEMILLA, "hilos": lm.HILOS, "entorno": entorno_ml(entradas)}


def clave_del_experimento(identidad: dict) -> str:
    return huella(identidad)


def cuerpo_del_experimento(instantanea: lv.Instantanea, identidad: dict, evaluacion: dict) -> dict:
    return {"esquema": ESQUEMA_EXPERIMENTO, "clave": clave_del_experimento(identidad), "identidad": identidad,
            "estado_de_uso": ESTADO_DE_USO, "contexto": contexto(), "juego": instantanea.codigo,
            "datos": {**instantanea.procedencia(), "paleta_del_corte": list(instantanea.paleta())},
            "historico": {"formato": "sorteos canonicos (numero, fecha, numeros/superbalota o pares ordenados)",
                          "sorteos": lv.sorteos_canonicos(instantanea)},
            **evaluacion}


def componer(cuerpo: dict, volatil: str, datos_volatiles: dict) -> dict:
    artefacto = {**cuerpo, "huella_de_reproduccion": huella(cuerpo), volatil: datos_volatiles}
    return {**artefacto, "sello": huella(artefacto)}


def cuerpo_de(artefacto: dict) -> dict:
    volatiles = VOLATILES_EXPERIMENTO if artefacto.get("esquema") == ESQUEMA_EXPERIMENTO else VOLATILES_PRONOSTICO
    return {k: v for k, v in artefacto.items() if k not in volatiles}


def integro(artefacto: dict) -> bool:
    try:
        return (artefacto.get("sello") == huella({k: v for k, v in artefacto.items() if k != "sello"})
                and artefacto.get("huella_de_reproduccion") == huella(cuerpo_de(artefacto)))
    except (ArtefactoLaboratorioError, AttributeError, TypeError):
        return False


def instantanea_del_experimento(informe: dict) -> lv.Instantanea:
    instantanea = lv.instantanea_desde_canonicos(informe["juego"], informe["historico"]["sorteos"])
    if instantanea.huella() != informe["datos"]["sha256_historico"]:
        raise ArtefactoLaboratorioError("la instantanea guardada no corresponde a su huella")
    return instantanea


def entradas_del_experimento(informe: dict) -> list[lm.EntradaCatalogo]:
    """Recetas del catalogo actual con la misma identidad y version que las del
    experimento; si alguna cambio, no se puede reproducir con este codigo."""
    entradas = []
    for c in informe["identidad"]["candidatos"]:
        entrada = lm.CATALOGO.get(c["id"])
        if entrada is None or entrada.version != c["version"] or \
                lm.parametros_de(entrada, informe["identidad"]["protocolo"]["perfil"]) != c["parametros"]:
            raise ArtefactoLaboratorioError(f"la receta {c['id']} v{c['version']} no esta en este catalogo")
        entradas.append(entrada)
    return entradas


def protocolo_del_experimento(informe: dict) -> le.Protocolo:
    p = informe["identidad"]["protocolo"]
    return le.Protocolo(**{k: p[k] for k in ("bloques", "tamano_bloque", "calentamiento", "minimo_ajuste",
                                              "minimo_evaluables", "perfil", "decimales")})


def comparar_reproduccion(guardado: dict, recalculado: dict) -> dict:
    """Huella exacta y, si difiere, la mayor diferencia en las perdidas por
    objetivo de cada candidato; `None` si los objetivos evaluados no son los
    mismos (no comparables; nunca un infinito, que no es JSON valido)."""
    exacta = huella(cuerpo_de(guardado)) == huella(recalculado)
    diferencia = 0.0
    a = {c["id"]: {f["objetivo"]: f["log_loss"] for f in c.get("por_objetivo", [])} for c in guardado.get("candidatos", [])}
    b = {c["id"]: {f["objetivo"]: f["log_loss"] for f in c.get("por_objetivo", [])}
         for c in recalculado.get("candidatos", [])}
    for cid, valores in a.items():
        otros = b.get(cid, {})
        if set(valores) != set(otros):
            diferencia = None
            break
        diferencia = max([diferencia, *(abs(valores[o] - otros[o]) for o in valores)])
    return {"huella_exacta": exacta, "maxima_diferencia_de_log_loss": diferencia}


# ---------------------------------------------------------------------------
# Pronosticos del laboratorio
# ---------------------------------------------------------------------------

def linea_de(juego: str, entrada: lm.EntradaCatalogo, perfil: str) -> dict:
    sufijo = "" if perfil == "predeterminado" else f"-{perfil}"
    return {"id": f"{entrada.id}-v{entrada.version}{sufijo}", "modelo": entrada.id, "version": entrada.version,
            "perfil": perfil, "tipo": entrada.tipo, "juego": juego}


def identidad_del_pronostico(informe: dict, entrada: lm.EntradaCatalogo) -> dict:
    perfil = informe["identidad"]["protocolo"]["perfil"]
    return {"esquema": ESQUEMA_PRONOSTICO, "implementacion": VERSION_IMPLEMENTACION, "juego": informe["juego"],
            "experimento": informe["clave"], "corte": informe["datos"]["corte"],
            "sha256_historico": informe["datos"]["sha256_historico"], "version_de_variables": lv.VERSION_VARIABLES,
            "modelo": {"id": entrada.id, "version": entrada.version, "parametros": lm.parametros_de(entrada, perfil)},
            "ajuste": "todos los objetivos disponibles de la instantanea del experimento",
            "transformaciones": informe["identidad"]["transformaciones"], "semilla": lm.SEMILLA,
            "entorno": entorno_ml((entrada,))}


def _r(valor: float, d: int) -> float:
    return round(float(valor), d)


def cuerpo_del_pronostico(informe: dict, entrada: lm.EntradaCatalogo) -> dict:
    """Ajusta el candidato con TODA la instantanea congelada del experimento y
    pronostica el objetivo corte + 1. Lanza `CandidatoNoDisponible` si no se
    puede ajustar."""
    if not entrada.genera_pronostico:
        raise ArtefactoLaboratorioError(f"{entrada.nombre} es una referencia sin pronostico propio")
    instantanea = instantanea_del_experimento(informe)
    perfil = informe["identidad"]["protocolo"]["perfil"]
    d = informe["identidad"]["protocolo"]["decimales"]
    variables = lv.Variables(instantanea)
    n = len(instantanea)
    ajustado = lm.ajustar_candidato(entrada, instantanea, variables, n, perfil)
    filas = variables.filas([n])
    p = ajustado.predecir(filas)
    identidad = identidad_del_pronostico(informe, entrada)
    evaluacion = next((c for c in informe["candidatos"] if c["id"] == entrada.id), None)
    pronostico, superbalota = contenido_del_pronostico(instantanea, filas.candidatos, p, d)
    return {"esquema": ESQUEMA_PRONOSTICO, "clave_de_entrada": huella(identidad), "identidad": identidad,
            "linea": linea_de(informe["juego"], entrada, perfil), "estado_de_uso": ESTADO_DE_USO,
            "contexto": contexto(), "juego": informe["juego"], "experimento": informe["clave"],
            "modelo": entrada.como_dict(perfil),
            "datos": {"corte": instantanea.corte, "sha256_historico": instantanea.huella(), "sorteos": n,
                      "ultima_fecha": instantanea.sorteos[-1].fecha.isoformat()},
            "ajuste_final": ajustado.detalle, "pronostico": pronostico, "superbalota": superbalota,
            "evaluacion_del_experimento": evaluacion_resumida(evaluacion)}


def evaluacion_resumida(evaluacion: dict | None) -> dict | None:
    return None if evaluacion is None else {
        "estado": evaluacion["estado"], "agregado": evaluacion["agregado"], "veredicto": evaluacion.get("veredicto"),
        "nota": "comparacion exploratoria del experimento; no acredita ventaja futura"}


def contenido_del_pronostico(instantanea: lv.Instantanea, candidatos: Sequence, p: np.ndarray,
                             d: int) -> tuple[dict, dict | None]:
    """(pronostico, superbalota) del objetivo corte + 1 con las probabilidades
    `p` de `candidatos` (numeros o pares). Comun a los pronosticos que reajustan
    (Producto 4) y a los de un modelo registrado congelado (Fase 3)."""
    reglas = instantanea.reglas
    pronostico = {"objetivo": instantanea.corte + 1, "calculado_hasta_sorteo": instantanea.corte}
    if reglas.colores:
        dist = {tuple(c): float(v) for c, v in zip(candidatos, p)}
        sugeridos = pcl.multiconjunto_mas_probable(dist)
        m = len(dist)
        pronostico.update({
            "paleta": list(instantanea.paleta()),
            "pares": [{"numero": a, "color": b, "probabilidad": _r(dist[(a, b)], d)} for a, b in sugeridos],
            "probabilidad_del_multiconjunto": _r(pcl.probabilidad_multiconjunto(dist, sugeridos), d),
            "probabilidad_uniforme_por_par": _r(1 / m, d),
            "ranking_de_pares": [{"numero": a, "color": b, "probabilidad": _r(dist[(a, b)], d),
                                  "probabilidad_uniforme": _r(1 / m, d)}
                                 for a, b in sorted(dist, key=lambda k: (-dist[k], k))],
            "suposicion": "6 balotas independientes e identicamente distribuidas condicionadas a la distribucion de "
                          "pares estimada (multinomial); no demostrada por el modelo y distinta de una predictiva "
                          "Dirichlet-multinomial",
            "nota": "multiconjunto mas probable (6 pares, con repeticion); no es una garantia"})
    else:
        marginal = dict(zip(candidatos, p.tolist()))
        orden = sorted(marginal, key=lambda c: (-marginal[c], c))
        uniforme = reglas.cantidad / len(reglas.candidatos)
        pronostico.update({
            "numeros_sugeridos": sorted(orden[:reglas.cantidad]),
            "ranking": [{"numero": c, "probabilidad": _r(marginal[c], d), "probabilidad_uniforme": _r(uniforme, d)}
                        for c in orden],
            "suma_de_marginales": _r(sum(marginal.values()), 9),
            "nota": "probabilidad marginal de aparicion de cada numero; el producto de cinco marginales no es la "
                    "probabilidad del premio mayor"})
    superbalota = None
    if reglas.superbalota:
        sb = lm.probabilidades_superbalota(instantanea.sorteos, reglas.superbalota)
        superbalota = {"estrategia": "frecuencia_con_suavizado_de_laplace",
                       "nota": "estrategia separada; el modelo de los numeros no aprende la superbalota",
                       "pronostico": {"ranking": [{"superbalota": c, "probabilidad": _r(sb[c], d),
                                                   "probabilidad_uniforme": _r(1 / len(sb), d)}
                                                  for c in sorted(sb, key=lambda c: (-sb[c], c))],
                                      "sugerida": min(sb, key=lambda c: (-sb[c], c))}}
    return pronostico, superbalota


def con_orden(artefacto: dict, secuencia: int, version_anterior: str | None) -> dict:
    """Orden de emision dentro de la linea y el objetivo, sellado."""
    sin_sello = {k: v for k, v in artefacto.items() if k != "sello"}
    sin_sello["generacion"] = {**artefacto["generacion"], "secuencia_en_la_linea": secuencia,
                               "version_anterior": version_anterior}
    return {**sin_sello, "sello": huella(sin_sello)}


def comparar_pronostico(guardado: dict, recalculado: dict) -> dict:
    exacta = huella(cuerpo_de(guardado)) == huella(recalculado)
    if guardado["juego"] == "COLORLOTO":
        clave, ranking = (lambda f: (f["numero"], f["color"])), "ranking_de_pares"
    else:
        clave, ranking = (lambda f: f["numero"]), "ranking"
    a = {clave(f): f["probabilidad"] for f in guardado["pronostico"][ranking]}
    b = {clave(f): f["probabilidad"] for f in recalculado["pronostico"][ranking]}
    return {"huella_exacta": exacta,
            "maxima_diferencia_de_probabilidad": max(abs(a[k] - b[k]) for k in a) if set(a) == set(b) else None}


# ---------------------------------------------------------------------------
# Seguimiento por linea de modelo
# ---------------------------------------------------------------------------

TIPOS = {"pronostico_sobre_el_ultimo_dato_disponible": "seguimiento",
         "simulacion_retrospectiva": "retrospectiva",
         "objetivo_no_cargado_con_sorteos_posteriores": "retrospectiva"}
NOTA_SEGUIMIENTO = ("«El objetivo no estaba cargado al generar» describe la base local; no acredita que la emision "
                    "precediera al sorteo real.")


def _metricas(artefacto: dict, observado: dict) -> dict:
    if artefacto["juego"] == "COLORLOTO":
        m = rmet.metricas_colorloto(artefacto, observado["pares"])
    else:
        m = rmet.metricas_numeros(artefacto, observado["numeros"])
        sb = rmet.metricas_superbalota(artefacto, observado.get("superbalota"))
        if sb:
            m["superbalota"] = sb
    return m


def seguimiento_de_linea(elementos: list[dict], historico_completo: Sequence | None) -> dict:
    """`elementos`: [{"objetivo", "secuencia", "identificador", "artefacto" | None, "ilegible": motivo | None}]
    de UNA linea. Una emision por objetivo: la primera por secuencia sellada.
    Si un archivo ilegible impide saber cual fue la primera, el objetivo se
    excluye por ambiguedad; nunca se avanza a otra version mas favorable."""
    por_objetivo: dict = {}
    sin_objetivo = [e for e in elementos if e.get("objetivo") is None]
    for e in elementos:
        if e.get("objetivo") is not None:
            por_objetivo.setdefault(e["objetivo"], []).append(e)
    filas = []
    for objetivo in sorted(por_objetivo):
        grupo = por_objetivo[objetivo]
        legibles = sorted((e for e in grupo if e.get("artefacto") is not None), key=lambda e: e["secuencia"])
        base = {"objetivo": objetivo, "versiones": len(grupo)}
        if any(e.get("ilegible") for e in grupo) or sin_objetivo:
            filas.append({**base, "estado": "excluido", "motivo": "orden_ambiguo_por_archivo_ilegible",
                          "tipo": None})
            continue
        primero = legibles[0]
        artefacto = primero["artefacto"]
        clasificacion = (artefacto.get("generacion") or {}).get("clasificacion_temporal") or {}
        tipo = TIPOS.get(clasificacion.get("tipo"), "sin_clasificacion")
        fila = {**base, "identificador": primero["identificador"], "tipo": tipo,
                "generado_en": artefacto["generacion"]["generado_en"], "secuencia": primero["secuencia"]}
        if historico_completo is None:
            filas.append({**fila, "estado": "sin_base", "motivo": "base de datos no disponible"})
            continue
        comparacion = ro.comparar_con_resultado(artefacto, historico_completo)
        fila["historico_hasta_el_corte"] = comparacion["historico_hasta_el_corte"]["estado"]
        fila["resultado"] = comparacion["resultado"]
        fila["coincidencias"] = comparacion["coincidencias"]
        if comparacion["estado"] != "observado":
            filas.append({**fila, "estado": comparacion["estado"], "motivo": comparacion["motivo"]})
            continue
        if fila["historico_hasta_el_corte"] != "coincide":
            filas.append({**fila, "estado": "excluido",
                          "motivo": "historico_hasta_el_corte_" + fila["historico_hasta_el_corte"]})
            continue
        try:
            fila["metricas"] = _metricas(artefacto, comparacion["resultado"])
        except rmet.ObjetivoNoEvaluableError as error:
            filas.append({**fila, "estado": "excluido", "motivo": str(error)})
            continue
        filas.append({**fila, "estado": "incluido"})
    por_tipo = {}
    for tipo in ("seguimiento", "retrospectiva"):
        de_tipo = [f for f in filas if f["tipo"] == tipo]
        incluidos = [f for f in de_tipo if f["estado"] == "incluido"]
        por_tipo[tipo] = {"objetivos": len(de_tipo), "incluidos": len(incluidos),
                          "pendientes": sum(f["estado"] == "pendiente" for f in de_tipo),
                          "excluidos": sum(f["estado"] == "excluido" for f in de_tipo),
                          "motivos_de_exclusion": dict(Counter(f["motivo"] for f in de_tipo if f["estado"] == "excluido")),
                          "agregado": agregado_de(incluidos)}
    ambiguos = sum(1 for f in filas if f.get("motivo") == "orden_ambiguo_por_archivo_ilegible")
    return {"filas": filas, "por_tipo": por_tipo, "ilegibles_sin_objetivo": len(sin_objetivo),
            "objetivos_ambiguos": ambiguos, "nota": NOTA_SEGUIMIENTO,
            "politica": "una emision por objetivo y linea: la primera segun la secuencia sellada; si no es evaluable "
                        "se excluye sin sustituirla"}


def agregado_de(incluidos: list[dict]) -> dict | None:
    if not incluidos:
        return None
    m = [f["metricas"] for f in incluidos]
    salida = {"objetivos": len(m), "log_loss": float(np.mean([x["log_loss"] for x in m])),
              "log_loss_uniforme": float(np.mean([x["log_loss_uniforme"] for x in m])),
              "brier": float(np.mean([x["brier"] for x in m])),
              "brier_uniforme": float(np.mean([x["brier_uniforme"] for x in m]))}
    salida["diferencia_log_loss"] = salida["log_loss"] - salida["log_loss_uniforme"]
    clave = "pares" if "pares" in (incluidos[0]["coincidencias"] or {}) else "numeros"
    salida["aciertos"] = sum(f["coincidencias"][clave] for f in incluidos)
    salida["muestra_pequena"] = len(m) < 10
    return salida


def comparacion_entre_lineas(seguimientos: dict[str, dict], tipo: str = "seguimiento") -> dict:
    """Comparacion directa solo sobre la interseccion de objetivos incluidos
    del tipo; tambien los totales individuales de cada linea."""
    incluidos = {linea: {f["objetivo"]: f for f in s["filas"] if f["tipo"] == tipo and f["estado"] == "incluido"}
                 for linea, s in seguimientos.items()}
    con_datos = {k: v for k, v in incluidos.items() if v}
    comunes = sorted(set.intersection(*(set(v) for v in con_datos.values()))) if len(con_datos) >= 2 else []
    return {"tipo": tipo, "totales": {k: len(v) for k, v in incluidos.items()}, "objetivos_comunes": comunes,
            "por_linea": {k: agregado_de([v[o] for o in comunes]) for k, v in con_datos.items()} if comunes else {},
            "nota": "solo la interseccion de objetivos incluidos se compara directamente"}
