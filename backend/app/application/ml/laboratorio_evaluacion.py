"""
Producto 4 -evaluador temporal comun del laboratorio.

UNIDAD TEMPORAL: el sorteo. Todas las filas de un objetivo (candidatos o
pares) estan siempre en la misma particion. El tiempo es la secuencia de
sorteos de la instantanea (con sus huecos y fechas reales), no un
calendario igualmente espaciado.

PROTOCOLO (fijado antes de evaluar):
- ventana creciente; objetivos evaluables desde la posicion
  `calentamiento + minimo_ajuste` (20 + 30 = 50): asi los modelos nuevos
  tienen 20 sorteos de calentamiento y al menos 30 objetivos de ajuste
  anteriores (20 base + 10 de calibracion para los binarios);
- los ultimos `bloques x tamano_bloque` (6 x 10) objetivos evaluables, en
  bloques consecutivos de 10; el ultimo puede ser parcial. Hacen falta al
  menos `minimo_evaluables` (10) objetivos para presentar una comparacion;
- al inicio de cada bloque se reentrena cada candidato SOLO con objetivos
  anteriores al bloque (ajuste base anterior a la calibracion, calibracion
  anterior al bloque). Parametros del modelo y del calibrador, y el estado
  de las estrategias de frecuencia (conteos), quedan FIJOS durante el
  bloque;
- ACTUALIZACION SECUENCIAL dentro del bloque: las variables de cada
  objetivo usan los resultados ya observados antes de el (tambien los de
  objetivos anteriores del mismo bloque), nunca su propio resultado ni uno
  posterior. Es una medicion nueva del laboratorio: no reutiliza ni cambia
  la evaluacion guardada en los pronosticos de Productos 1-3.

MUESTRA COMUN. El conjunto ordenado de objetivos evaluables y sus
exclusiones se decide con reglas de dominio antes de calcular perdidas
(ColorLoto: un objetivo con un color ausente de la paleta del corte de
ajuste de su bloque se excluye, con su motivo; ningun objetivo se excluye
por la perdida de un modelo). Todos los candidatos se miden sobre esa
muestra y con la misma referencia uniforme. Un candidato que no se puede
ajustar en algun bloque (p. ej. la receta de AE-36, que exige 50 sorteos de
calentamiento y 100 objetivos de ajuste) queda `parcial` con su incidencia:
sus cifras parciales se pueden consultar, pero no entra en el resumen
principal, que solo ordena candidatos con evaluacion completa.

METRICAS por objetivo y agregadas desde las observaciones (todos los
objetivos pesan lo mismo y tienen las mismas filas: los bloques desiguales
no se promedian sin ponderar):
- numeros: Log Loss y Brier binarios por fila candidato-objetivo
  (`metricas.py`), aciertos del top-5 por sorteo, diferencia emparejada de
  Log Loss frente a la uniforme por objetivo y agregada; superbalota aparte;
- ColorLoto: Log Loss y Brier por balota, Log Loss del multiconjunto y
  coincidencias con multiplicidad (0..6) de `pronostico_colorloto`, frente
  a la uniforme sobre la misma paleta.
Diferencia negativa: el candidato tuvo menor perdida en ESTOS objetivos.
No hay pruebas de significancia ni intervalos: las filas candidato no son
observaciones independientes.

Modulo puro salvo el entrenamiento local de los candidatos.
"""
from __future__ import annotations

import time
from collections import namedtuple
from collections.abc import Callable
from dataclasses import asdict, dataclass

import numpy as np

from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import pronostico_colorloto as pcl
from app.application.ml import rendimiento_observado as rmet
from app.application.ml.metricas import calcular_brier_score, calcular_log_loss

MAXIMO_BLOQUES = 6
MUESTRA_PEQUENA = 30
INTERVALOS_NUMEROS = (0.0, 0.08, 0.10, 0.11, 0.12, 0.13, 0.14, 0.16, 1.0)
"""Intervalos fijos alrededor de las uniformes 5/43 = 0.116 y 5/39 = 0.128."""
INTERVALOS_PARES = (0.0, 0.015, 0.02, 0.0225, 0.025, 0.0275, 0.03, 0.04, 1.0)
"""Intervalos fijos alrededor de la uniforme de pares 1/42 = 0.024 (6 colores)."""


class MuestraInsuficienteError(ValueError):
    def __init__(self, codigo: str, sorteos: int, evaluables: int, requeridos: int):
        self.codigo, self.sorteos, self.evaluables, self.requeridos = codigo, sorteos, evaluables, requeridos
        super().__init__(f"Muestra insuficiente para {codigo}: {sorteos} sorteos dan {evaluables} objetivos "
                         f"evaluables; hacen falta al menos {requeridos} (20 de calentamiento, 30 de ajuste y "
                         f"{requeridos} de evaluacion)")


@dataclass(frozen=True)
class Protocolo:
    bloques: int = MAXIMO_BLOQUES
    tamano_bloque: int = 10
    calentamiento: int = lv.CALENTAMIENTO
    minimo_ajuste: int = 30
    minimo_evaluables: int = 10
    perfil: str = "predeterminado"
    decimales: int = 12

    def __post_init__(self):
        if isinstance(self.bloques, bool) or not isinstance(self.bloques, int) or not 1 <= self.bloques <= MAXIMO_BLOQUES:
            raise ValueError(f"bloques debe estar entre 1 y {MAXIMO_BLOQUES}")
        if (self.tamano_bloque, self.calentamiento, self.minimo_ajuste, self.minimo_evaluables) != (10, 20, 30, 10):
            raise ValueError("tamano de bloque, calentamiento y minimos son fijos en esta version del protocolo")
        if self.perfil not in lm.PERFILES:
            raise ValueError(f"perfil admitido: {', '.join(lm.PERFILES)}")

    def como_dict(self) -> dict:
        return {**asdict(self), "ventana": "creciente", "unidad": "sorteo",
                "reentrenamiento": "al inicio de cada bloque; parametros fijos dentro del bloque",
                "actualizacion_secuencial": "las variables de un objetivo usan los resultados anteriores ya "
                                            "observados, tambien dentro del bloque; nunca el suyo ni posteriores",
                "estrategias_de_frecuencia": "conteos ajustados al inicio del bloque y fijos durante el",
                "calibracion": "modelos binarios nuevos: sigmoide con base anterior a calibracion (ultimos "
                               "max(10, 20%) objetivos de ajuste); Poisson: sin calibracion"}


def es_muestra_pequena(total: int, protocolo: Protocolo) -> bool:
    """Aviso de muestra pequena: menos de MUESTRA_PEQUENA objetivos o sin
    completar el presupuesto de bloques del protocolo."""
    return total < max(MUESTRA_PEQUENA, protocolo.bloques * protocolo.tamano_bloque)


def bloques_de_evaluacion(instantanea: lv.Instantanea, protocolo: Protocolo) -> list[list[int]]:
    """Posiciones de los objetivos de cada bloque, en orden cronologico."""
    primera = protocolo.calentamiento + protocolo.minimo_ajuste
    posiciones = list(range(primera, len(instantanea)))
    if len(posiciones) < protocolo.minimo_evaluables:
        raise MuestraInsuficienteError(instantanea.codigo, len(instantanea), len(posiciones),
                                       protocolo.minimo_evaluables)
    recientes = posiciones[-protocolo.bloques * protocolo.tamano_bloque:]
    return [recientes[i:i + protocolo.tamano_bloque] for i in range(0, len(recientes), protocolo.tamano_bloque)]


def muestra_comun(instantanea: lv.Instantanea, protocolo: Protocolo) -> dict:
    """Bloques, objetivos evaluables y exclusiones, por reglas de dominio
    (sin mirar perdidas)."""
    bloques = []
    excluidos = []
    for k, posiciones in enumerate(bloques_de_evaluacion(instantanea, protocolo), start=1):
        inicio = posiciones[0]
        paleta = instantanea.paleta(inicio) if instantanea.reglas.colores else ()
        evaluables = []
        for i in posiciones:
            r = instantanea.sorteos[i]
            if instantanea.reglas.colores:
                nuevos = sorted({c for _, c in r.pares if c not in paleta})
                if nuevos:
                    excluidos.append({"objetivo": r.numero_sorteo, "bloque": k,
                                      "motivo": "color_fuera_de_la_paleta_del_corte",
                                      "detalle": f"colores ausentes antes del bloque: {', '.join(nuevos)}"})
                    continue
            evaluables.append(i)
        bloques.append({"indice": k, "posicion_de_ajuste": inicio, "paleta": list(paleta), "posiciones": evaluables,
                        "objetivos": [instantanea.sorteos[i].numero_sorteo for i in evaluables],
                        "todos": [instantanea.sorteos[i].numero_sorteo for i in posiciones],
                        "fechas": [instantanea.sorteos[i].fecha.isoformat() for i in evaluables]})
    total = sum(len(b["posiciones"]) for b in bloques)
    if total < protocolo.minimo_evaluables:
        raise MuestraInsuficienteError(instantanea.codigo, len(instantanea), total, protocolo.minimo_evaluables)
    return {"bloques": bloques, "excluidos": excluidos, "objetivos": [o for b in bloques for o in b["objetivos"]]}


# ---------------------------------------------------------------------------
# Metricas por objetivo
# ---------------------------------------------------------------------------

_Fila = namedtuple("_Fila", "sorteo_objetivo numero_candidato etiqueta")


def _filas_metricas(filas: lv.Filas, m):
    return [_Fila(int(filas.objetivos[i]), filas.candidatos[i], int(filas.y[i])) for i in np.flatnonzero(m)]


def _unir(lista: list[lv.Filas]) -> lv.Filas:
    return lv.Filas(np.concatenate([f.objetivos for f in lista]), np.concatenate([f.posiciones for f in lista]),
                    tuple(c for f in lista for c in f.candidatos), np.concatenate([f.X for f in lista]),
                    np.concatenate([f.y for f in lista]))


def metricas_por_objetivo(instantanea: lv.Instantanea, filas: lv.Filas, p: np.ndarray) -> dict[int, dict]:
    """{objetivo: metricas} con las probabilidades `p` de cada fila."""
    salida = {}
    for posicion in sorted(set(filas.posiciones.tolist())):
        m = filas.posiciones == posicion
        objetivo = instantanea.sorteos[posicion]
        if instantanea.reglas.colores:
            dist = {tuple(c): float(v) for c, v in zip((filas.candidatos[i] for i in np.flatnonzero(m)), p[m])}
            met = pcl.metricas_de_objetivo(dist, objetivo.pares)
            salida[objetivo.numero_sorteo] = {"log_loss": met["log_loss_por_balota"], "brier": met["brier_por_balota"],
                                              "log_loss_multiconjunto": met["log_loss_multiconjunto"],
                                              "aciertos": met["coincidencias_de_pares_por_sorteo"],
                                              "filas": int(m.sum())}
            continue
        filas_m = _filas_metricas(filas, m)
        probs = p[m].tolist()
        top = sorted(zip(filas_m, probs), key=lambda par: (-par[1], par[0].numero_candidato))[:instantanea.reglas.cantidad]
        salida[objetivo.numero_sorteo] = {"log_loss": calcular_log_loss(filas_m, probs),
                                          "brier": calcular_brier_score(filas_m, probs),
                                          "aciertos": sum(f.etiqueta for f, _ in top), "filas": len(filas_m)}
    return salida


def _media(valores) -> float:
    return float(sum(valores) / len(valores))


def agregar(por_objetivo: dict, uniforme: dict, objetivos: list[int], d: int, colores: bool) -> dict:
    """Agregado desde las observaciones de `objetivos` (mismos objetivos para
    el candidato y la uniforme)."""
    claves = ["log_loss", "brier", "aciertos"] + (["log_loss_multiconjunto"] if colores else [])
    salida = {k: round(_media([por_objetivo[o][k] for o in objetivos]), d) for k in claves}
    salida["uniforme"] = {k: round(_media([uniforme[o][k] for o in objetivos]), d) for k in claves}
    salida["diferencia_log_loss"] = round(_media([por_objetivo[o]["log_loss"] - uniforme[o]["log_loss"]
                                                  for o in objetivos]), d)
    salida["diferencia_brier"] = round(_media([por_objetivo[o]["brier"] - uniforme[o]["brier"] for o in objetivos]), d)
    salida["sorteos"] = len(objetivos)
    salida["filas"] = int(sum(por_objetivo[o]["filas"] for o in objetivos))
    if colores:
        salida["balotas"] = pcl.BALOTAS * len(objetivos)
    return salida


def metricas_secundarias(candidato: dict, colores: bool, cantidad: int, decimales: int = 6) -> dict | None:
    """Metricas secundarias (Fase 3) DERIVADAS de los aciertos por objetivo ya
    guardados en el informe (no cambian ningun artefacto). Regla de decision:
    los k primeros del ranking (k = 5 numeros; ColorLoto: el multiconjunto mas
    probable de 6 balotas, con multiplicidad). Con k igual al tamano del sorteo
    la precision, la exhaustividad y F1 coinciden (aciertos / k). La exactitud
    por fila (solo numeros) esta dominada por las ausencias: la uniforme ya
    obtiene una exactitud alta. Se comparan con las de la uniforme del mismo
    informe."""
    filas = candidato.get("por_objetivo") or []
    if not filas:
        return None
    k = pcl.BALOTAS if colores else cantidad
    n = len(filas)
    aciertos = sum(f["aciertos"] for f in filas)
    proporcion = round(aciertos / (k * n), decimales)
    salida = {"regla": f"top-{k}", "k": k, "objetivos": n, "aciertos": aciertos,
              "aciertos_por_sorteo": round(aciertos / n, decimales), "precision_en_k": proporcion,
              "exhaustividad_en_k": proporcion, "f1_en_k": proporcion, "exactitud": None}
    if not colores:
        total = sum(f["filas"] for f in filas)
        salida["exactitud"] = round(sum(f["filas"] - 2 * k + 2 * f["aciertos"] for f in filas) / total, decimales)
    return salida


def diagnostico_de_calibracion(filas: lv.Filas, p: np.ndarray, colores: bool) -> list[dict]:
    """Intervalos fijos: probabilidad media frente a frecuencia observada.
    ColorLoto: probabilidad normalizada del par frente a su proporcion de
    balotas (conteo / 6). Descriptivo; no acredita calibracion."""
    bordes = INTERVALOS_PARES if colores else INTERVALOS_NUMEROS
    observado = filas.y / pcl.BALOTAS if colores else filas.y
    salida = []
    for a, b in zip(bordes, bordes[1:]):
        m = (p >= a) & ((p < b) if b < 1.0 else (p <= b))
        if not m.any():
            salida.append({"intervalo": [a, b], "filas": 0, "sorteos": 0, "probabilidad_media": None,
                           "frecuencia_observada": None})
            continue
        salida.append({"intervalo": [a, b], "filas": int(m.sum()), "sorteos": int(len(set(filas.objetivos[m].tolist()))),
                       "probabilidad_media": round(float(p[m].mean()), 6),
                       "frecuencia_observada": round(float(observado[m].mean()), 6)})
    return salida


def _veredicto(diferencia: float, es_uniforme: bool) -> str:
    if es_uniforme:
        return "referencia"
    if diferencia < 0:
        return "menor_perdida_que_la_uniforme_en_esta_evaluacion"
    return "la_uniforme_fue_mejor" if diferencia > 0 else "empate"


# ---------------------------------------------------------------------------
# Evaluacion completa
# ---------------------------------------------------------------------------

def evaluar(instantanea: lv.Instantanea, entradas: list[lm.EntradaCatalogo], protocolo: Protocolo,
            avance: Callable[..., None] | None = None) -> tuple[dict, dict]:
    """(resultado determinista, tiempos medidos). `avance(fase, **datos)`
    informa del progreso; no forma parte del resultado."""
    avance = avance or (lambda *a, **k: None)
    d = protocolo.decimales
    colores = instantanea.reglas.colores
    muestra = muestra_comun(instantanea, protocolo)
    variables = lv.Variables(instantanea)
    uniforme_entrada = next(e for e in entradas if e.familia == "uniforme")
    filas_por_bloque = []
    for b in muestra["bloques"]:
        filas_por_bloque.append(variables.filas(b["posiciones"], paleta=tuple(b["paleta"]) if colores else None)
                                if b["posiciones"] else None)
    uniforme = {}
    for b, f in zip(muestra["bloques"], filas_por_bloque):
        if f is not None:
            ajuste = lm.ajustar_candidato(uniforme_entrada, instantanea, variables, b["posicion_de_ajuste"])
            uniforme.update(metricas_por_objetivo(instantanea, f, ajuste.predecir(f)))
    resultados, tiempos = [], {}
    for entrada in entradas:
        inicio = time.perf_counter()
        por_objetivo, incidencias, bloques, filas_eval, probs_eval = {}, [], [], [], []
        for b, f in zip(muestra["bloques"], filas_por_bloque):
            avance("modelo", candidato=entrada.id, bloque=b["indice"], bloques=len(muestra["bloques"]))
            if f is None:
                bloques.append({"indice": b["indice"], "estado": "sin_objetivos_evaluables", "objetivos": []})
                continue
            try:
                ajustado = lm.ajustar_candidato(entrada, instantanea, variables, b["posicion_de_ajuste"],
                                                protocolo.perfil)
                p = ajustado.predecir(f)
            except lm.CandidatoNoDisponible as error:
                incidencias.append({"bloque": b["indice"], "estado": error.estado, "motivo": error.motivo})
                bloques.append({"indice": b["indice"], "estado": error.estado, "motivo": error.motivo,
                                "objetivos": b["objetivos"]})
                continue
            met = metricas_por_objetivo(instantanea, f, p)
            por_objetivo.update(met)
            filas_eval.append(f)
            probs_eval.append(p)
            bloques.append({"indice": b["indice"], "estado": "evaluado", "objetivos": b["objetivos"],
                            "ajuste": ajustado.detalle,
                            "metricas": agregar(met, uniforme, b["objetivos"], d, colores)})
        evaluados = [o for o in muestra["objetivos"] if o in por_objetivo]
        estado = ("completo" if len(evaluados) == len(muestra["objetivos"]) else
                  "parcial" if evaluados else "no_disponible")
        resultado = {**entrada.como_dict(protocolo.perfil), "estado": estado, "incidencias": incidencias,
                     "bloques": bloques, "objetivos_evaluados": len(evaluados),
                     "agregado": agregar(por_objetivo, uniforme, evaluados, d, colores) if evaluados else None,
                     "por_objetivo": [{"objetivo": o, **{k: round(v, d) if isinstance(v, float) else v
                                                          for k, v in por_objetivo[o].items()},
                                       "diferencia_log_loss": round(por_objetivo[o]["log_loss"]
                                                                    - uniforme[o]["log_loss"], d)}
                                      for o in evaluados]}
        if evaluados and entrada.familia != "uniforme":
            resultado["calibracion"] = diagnostico_de_calibracion(_unir(filas_eval), np.concatenate(probs_eval),
                                                                  colores)
        if estado == "completo":
            resultado["veredicto"] = _veredicto(resultado["agregado"]["diferencia_log_loss"],
                                                entrada.familia == "uniforme")
        resultados.append(resultado)
        tiempos[entrada.id] = round(time.perf_counter() - inicio, 3)
    cuerpo = {"muestra_comun": {**muestra, "bloques": [{k: v for k, v in b.items() if k != "posiciones"}
                                                      for b in muestra["bloques"]],
                                "total_objetivos": len(muestra["objetivos"]),
                                "muestra_pequena": es_muestra_pequena(len(muestra["objetivos"]), protocolo)},
              "candidatos": resultados, "resumen": resumen(resultados)}
    if instantanea.reglas.superbalota:
        cuerpo["superbalota"] = evaluar_superbalota(instantanea, muestra, d)
    return cuerpo, tiempos


def resumen(resultados: list[dict]) -> dict:
    """Orden de los candidatos COMPLETOS por Log Loss agregado (menor primero;
    empate por identificador). Los parciales se listan aparte."""
    completos = sorted((r for r in resultados if r["estado"] == "completo"),
                       key=lambda r: (r["agregado"]["log_loss"], r["id"]))
    incompletos = [{"id": r["id"], "estado": r["estado"], "incidencias": r["incidencias"]}
                   for r in resultados if r["estado"] != "completo"]
    modelos = [r for r in completos if r["familia"] != "uniforme"]
    if not modelos or not any(r["familia"] == "uniforme" for r in completos):
        estado = "comparacion_incompleta"
    else:
        mejor = completos[0]
        empatados = [r for r in completos if r["agregado"]["log_loss"] == mejor["agregado"]["log_loss"]]
        if len(empatados) > 1 and any(r["familia"] == "uniforme" for r in empatados):
            estado = "empate"
        elif mejor["familia"] == "uniforme":
            estado = "la_uniforme_fue_mejor"
        else:
            estado = "menor_perdida_en_esta_evaluacion"
    return {"estado": estado, "criterio": "Log Loss agregado sobre la muestra comun (menor es mejor)",
            "ranking": [{"posicion": i, "id": r["id"], "nombre": r["nombre"], "tipo": r["tipo"],
                         "log_loss": r["agregado"]["log_loss"], "diferencia_log_loss": r["agregado"]["diferencia_log_loss"],
                         "veredicto": r["veredicto"]} for i, r in enumerate(completos, start=1)],
            "incompletos": incompletos,
            "nota": "Comparacion exploratoria sobre objetivos ya usados como historico: elegir un candidato despues "
                    "de verla no acredita ventaja futura."}


def evaluar_superbalota(instantanea: lv.Instantanea, muestra: dict, d: int) -> dict:
    """Estrategia separada de Producto 1, con su estado fijado al inicio de cada
    bloque, sobre los mismos objetivos. Ningun modelo nuevo la aprende."""
    rango = instantanea.reglas.superbalota
    filas = []
    for b in muestra["bloques"]:
        p = lm.probabilidades_superbalota(instantanea.sorteos[:b["posicion_de_ajuste"]], rango)
        u = {c: 1 / len(p) for c in p}
        ganadora = min(p, key=lambda c: (-p[c], c))
        for i in b["posiciones"]:
            sb = instantanea.sorteos[i].superbalota
            m, mu = rmet.metricas_multiclase(p, sb), rmet.metricas_multiclase(u, sb)
            filas.append({"objetivo": instantanea.sorteos[i].numero_sorteo, "log_loss": m["log_loss"],
                          "brier": m["brier"], "acierto": ganadora == sb, "log_loss_uniforme": mu["log_loss"],
                          "brier_uniforme": mu["brier"]})
    n = len(filas)
    return {"estrategia": "frecuencia_con_suavizado_de_laplace", "rango": list(rango),
            "nota": "objetivo separado de los numeros principales; los modelos nuevos no aprenden la superbalota",
            "sorteos": n,
            "log_loss": round(_media([f["log_loss"] for f in filas]), d),
            "log_loss_uniforme": round(_media([f["log_loss_uniforme"] for f in filas]), d),
            "brier": round(_media([f["brier"] for f in filas]), d),
            "brier_uniforme": round(_media([f["brier_uniforme"] for f in filas]), d),
            "aciertos": sum(f["acierto"] for f in filas)}
