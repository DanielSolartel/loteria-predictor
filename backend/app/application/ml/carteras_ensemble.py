"""
Producto 5 -modelo combinado (ensemble temporal) y su comparacion.

QUE ES. Una mezcla convexa de las probabilidades FINALES de tres
componentes fijos de Producto 4, con su calibracion y transformacion
actuales (no se reentrenan ni se cambian sus recetas):

- Baloto, Revancha y MiLoto: uniforme + regresion logistica regularizada +
  HGB clasificador (marginales de aparicion que suman 5);
- ColorLoto: uniforme de la paleta + Poisson regularizado + HGB Poisson
  (distribucion de pares normalizada sobre la paleta del corte).

Con pesos no negativos que suman uno, la mezcla conserva marginales finitas
en (0, 1) que suman 5, o una distribucion de pares con masa 1. Nunca mezcla
juegos, reglas ni paletas distintas: los tres componentes predicen las
mismas filas. La superbalota sigue siendo un objetivo separado con la
estrategia de Producto 1; el ensemble de numeros no la aprende.

PESOS APRENDIDOS DEL PASADO. Malla fija (i/10, j/10, k/10) con enteros no
negativos e i + j + k = 10: 66 mezclas de predicciones YA CALCULADAS (no se
reentrena 66 veces ni se buscan hiperparametros). Criterio: Log Loss media
por sorteo en un bloque interno cronologico de 10 objetivos (numeros: la
definicion binaria de `metricas.py`; ColorLoto: Log Loss por balota con
multiplicidades), con las definiciones de `laboratorio_evaluacion`.
Desempate determinista: se identifica la perdida minima L; empatan solo las
mezclas con perdida <= L + `TOLERANCIA_DE_EMPATE`; entre ellas gana la de
mayor peso de la uniforme y despues la de mayor peso del componente lineal
(orden estable de componentes). Si gana el peso 1 de la uniforme, el ajuste
ELIGIO LA REFERENCIA UNIFORME: no es evidencia de que dos modelos de ML
mejoraran el pronostico.

SEPARACION TEMPORAL (unidad: el sorteo). Para un bloque exterior que empieza
en la posicion s:
1. bloque interno = las posiciones s-10 .. s-1 (los diez objetivos
   anteriores al bloque exterior);
2. los componentes se ajustan SOLO con objetivos de posicion < s-10 (en los
   binarios, su base y su calibracion tambien son anteriores al bloque
   interno: `laboratorio_modelos.ajustar_candidato`);
3. predicen el bloque interno sin usar sus etiquetas en el ajuste (las
   variables si incorporan resultados anteriores ya observados, con la
   actualizacion secuencial de Producto 4);
4. los pesos se eligen con esas predicciones internas;
5. los componentes se reajustan con los objetivos de posicion < s (mismas
   recetas y separacion de calibracion) y los pesos quedan FIJOS;
6. el bloque exterior se evalua sin usar sus etiquetas para elegir pesos,
   modelos ni parametros.
Nunca se usan predicciones de entrenamiento, perdidas de todo el historico
ni las del informe exterior como bloque interno, ni divisiones aleatorias.
El bloque interno de un bloque exterior puede coincidir con el bloque
exterior anterior: sus etiquetas ya eran pasado para el bloque siguiente, y
sus predicciones internas vienen de componentes ajustados antes de el.

PROTOCOLO de Producto 5 (`VERSION_PROTOCOLO`): 20 sorteos de calentamiento,
30 objetivos de ajuste de componentes y 10 internos para pesos; el primer
objetivo exterior es la posicion 60 y hacen falta al menos 10 objetivos
exteriores (70 sorteos) para una comparacion agregada; hasta 6 bloques
exteriores de 10 (el ultimo puede ser parcial). Generar con el ensemble
necesita 60 sorteos (el bloque interno son los 10 ultimos objetivos).

COMPARACION: el ensemble, las dos familias nuevas, la estrategia actual y la
uniforme sobre los MISMOS objetivos exteriores (muestra comun de Producto 4
aplicada desde la posicion 60). Reevaluar con este protocolo los candidatos
de Producto 4 es un informe nuevo: no cambia sus experimentos guardados ni
sus identidades. Si un componente no se puede ajustar en un bloque (interno
o exterior), ese bloque del ensemble queda no disponible con su motivo y el
ensemble pasa a parcial (fuera del ranking principal); nunca se sustituye
por la uniforme conservando su nombre.

La mezcla no hereda una acreditacion de calibracion por combinar modelos
calibrados: se evalua y diagnostica su salida final, igual que el resto.

Modulo puro salvo el entrenamiento local de los componentes. Sin reloj,
red, base de datos ni escritura; no cambia los hilos del proceso.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass

import numpy as np

from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv

ID_ENSEMBLE = "ensemble_temporal"
VERSION_ENSEMBLE = "1"
VERSION_PROTOCOLO = "producto5-protocolo-1"
PASOS_DE_MALLA = 10
TOLERANCIA_DE_EMPATE = 1e-12
"""Tolerancia absoluta sobre la Log Loss media del bloque interno: las
mezclas a esta distancia de la minima se consideran empatadas."""
TOLERANCIA_DE_MASA = 1e-9
MAXIMO_BLOQUES = 6
COMPONENTES = {
    "BALOTO": ("uniforme", "logistica_regularizada", "hgb_clasificador"),
    "BALOTO_REVANCHA": ("uniforme", "logistica_regularizada", "hgb_clasificador"),
    "MILOTO": ("uniforme", "logistica_regularizada", "hgb_clasificador"),
    "COLORLOTO": ("uniforme_paleta", "poisson_regularizado", "hgb_poisson"),
}
"""Orden estable de los componentes: (uniforme, lineal, arboles)."""
CANDIDATOS_DE_COMPARACION = {
    "BALOTO": ("uniforme", "actual_logistica_ae36", "logistica_regularizada", "hgb_clasificador"),
    "BALOTO_REVANCHA": ("uniforme", "actual_logistica_ae36", "logistica_regularizada", "hgb_clasificador"),
    "MILOTO": ("uniforme", "actual_frecuencia_contraida", "logistica_regularizada", "hgb_clasificador"),
    "COLORLOTO": ("uniforme_paleta", "actual_multinomial_suavizada", "poisson_regularizado", "hgb_poisson"),
}
"""Candidatos de Producto 4 que reevalua la comparacion de Producto 5, en su
orden. Es el catalogo de Producto 4 cuando se creo Producto 5, congelado: los
bosques de la Fase 3 se comparan en el laboratorio (Producto 4) y se pueden
usar para generar carteras, pero no cambian la identidad ni la reproduccion de
las comparaciones de Producto 5 ya guardadas."""


def candidatos_de_comparacion(codigo: str) -> list:
    return [lm.CATALOGO[i] for i in CANDIDATOS_DE_COMPARACION[codigo]]


class MuestraInsuficienteCarteras(ValueError):
    """La instantanea no alcanza el minimo de Producto 5, con los requisitos exactos."""

    def __init__(self, codigo: str, sorteos: int, disponibles: int, requeridos: int, para: str):
        self.codigo, self.sorteos, self.disponibles, self.requeridos, self.para = (codigo, sorteos, disponibles,
                                                                                   requeridos, para)
        if para == "comparacion":
            detalle = (f"{sorteos} sorteos dan {disponibles} objetivos exteriores; hacen falta al menos {requeridos} "
                       f"(20 de calentamiento, 30 de ajuste de componentes, 10 internos para los pesos y "
                       f"{requeridos} de evaluacion exterior: 70 sorteos)")
        else:
            detalle = (f"hay {sorteos} sorteos; el modelo combinado necesita {requeridos} (20 de calentamiento, 30 de "
                       f"ajuste de componentes y 10 internos para los pesos)")
        super().__init__(f"Muestra insuficiente para {codigo}: {detalle}")


class ComponenteNoDisponible(Exception):
    """Un componente del ensemble no pudo ajustarse o predecir en un bloque."""

    def __init__(self, componente: str, estado: str, motivo: str):
        self.componente, self.estado, self.motivo = componente, estado, motivo
        super().__init__(f"componente {componente} {estado}: {motivo}")


def malla(pasos: int = PASOS_DE_MALLA) -> tuple[tuple[int, int, int], ...]:
    """Numeradores (i, j, k) con i + j + k = pasos, en orden estable: peso de
    la uniforme descendente y despues peso lineal descendente."""
    return tuple((i, j, pasos - i - j) for i in range(pasos, -1, -1) for j in range(pasos - i, -1, -1))


MALLA = malla()


def pesos_de(numeradores: Sequence[int], pasos: int = PASOS_DE_MALLA) -> list[float]:
    return [n / pasos for n in numeradores]


def elegir_mezcla(perdidas: Sequence[float], numeradores: Sequence[Sequence[int]] = MALLA,
                  tolerancia: float = TOLERANCIA_DE_EMPATE) -> dict:
    """Indice de la mezcla elegida: minima perdida; entre las que estan a
    `tolerancia` o menos del minimo, mayor peso de la uniforme y despues
    mayor peso lineal. No compara por parejas segun el orden de recorrido."""
    if len(perdidas) != len(numeradores) or not perdidas:
        raise ValueError("una perdida por mezcla de la malla")
    valores = np.asarray(perdidas, dtype=float)
    if not np.all(np.isfinite(valores)):
        raise ValueError("perdidas internas no finitas")
    minimo = float(valores.min())
    empatadas = [m for m in range(len(valores)) if valores[m] <= minimo + tolerancia]
    elegida = min(empatadas, key=lambda m: (-numeradores[m][0], -numeradores[m][1], m))
    return {"indice": elegida, "minimo": minimo, "empatadas": empatadas}


def mezclar(predicciones: np.ndarray, numeradores: Sequence[int], pasos: int = PASOS_DE_MALLA) -> np.ndarray:
    """(i*p_uniforme + j*p_lineal + k*p_arboles) / pasos, fila a fila."""
    i, j, k = numeradores
    return (i * predicciones[0] + j * predicciones[1] + k * predicciones[2]) / pasos


def validar_mezcla(p: np.ndarray, filas: lv.Filas, colores: bool, cantidad: int) -> np.ndarray:
    """Finita, en (0, 1) y con masa 5 (numeros) o 1 (pares) en cada objetivo."""
    if p.shape != (len(filas),) or not np.all(np.isfinite(p)) or np.any(p <= 0) or np.any(p >= 1):
        raise lm.CandidatoNoDisponible("salida_invalida", "mezcla no finita o fuera de (0, 1)")
    masa = 1.0 if colores else float(cantidad)
    for posicion in np.unique(filas.posiciones):
        if abs(float(p[filas.posiciones == posicion].sum()) - masa) > TOLERANCIA_DE_MASA:
            raise lm.CandidatoNoDisponible("salida_invalida", f"la mezcla no conserva la masa {masa:g}")
    return p


# ---------------------------------------------------------------------------
# Protocolo y muestra comun
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProtocoloCarteras:
    bloques: int = MAXIMO_BLOQUES
    tamano_bloque: int = 10
    calentamiento: int = lv.CALENTAMIENTO
    minimo_ajuste: int = 30
    bloque_interno: int = 10
    minimo_evaluables: int = 10
    perfil: str = "predeterminado"
    decimales: int = 12

    def __post_init__(self):
        if isinstance(self.bloques, bool) or not isinstance(self.bloques, int) or not 1 <= self.bloques <= MAXIMO_BLOQUES:
            raise ValueError(f"bloques debe estar entre 1 y {MAXIMO_BLOQUES}")
        if (self.tamano_bloque, self.calentamiento, self.minimo_ajuste, self.bloque_interno,
                self.minimo_evaluables, self.decimales) != (10, 20, 30, 10, 10, 12):
            raise ValueError("tamano de bloque, calentamiento, minimos y decimales son fijos en esta version del "
                             "protocolo")
        if self.perfil not in lm.PERFILES:
            raise ValueError(f"perfil admitido: {', '.join(lm.PERFILES)}")

    @property
    def primera_exterior(self) -> int:
        return self.calentamiento + self.minimo_ajuste + self.bloque_interno

    @property
    def minimo_para_generar(self) -> int:
        return self.primera_exterior

    def como_dict(self) -> dict:
        return {**asdict(self), "version": VERSION_PROTOCOLO, "ventana": "creciente", "unidad": "sorteo",
                "primera_posicion_exterior": self.primera_exterior,
                "particiones": ("bloque interno = los 10 objetivos anteriores al bloque exterior; componentes "
                                "ajustados antes del bloque interno para aprender pesos y reajustados antes del "
                                "bloque exterior con los pesos fijos"),
                "actualizacion_secuencial": "las variables de un objetivo usan los resultados anteriores ya "
                                            "observados, tambien dentro del bloque; nunca el suyo ni posteriores",
                "malla": {"pasos": PASOS_DE_MALLA, "mezclas": len(MALLA), "tolerancia_de_empate": TOLERANCIA_DE_EMPATE,
                          "criterio": "Log Loss media por sorteo en el bloque interno (numeros: binaria por fila; "
                                      "ColorLoto: por balota con multiplicidades)",
                          "desempate": "minima perdida; entre las mezclas a la tolerancia del minimo, mayor peso de "
                                       "la uniforme y despues mayor peso del componente lineal"}}


def _evaluables(instantanea: lv.Instantanea, posiciones: Sequence[int], paleta: tuple, k: int, tipo: str):
    evaluables, excluidos = [], []
    for i in posiciones:
        r = instantanea.sorteos[i]
        if instantanea.reglas.colores:
            nuevos = sorted({c for _, c in r.pares if c not in paleta})
            if nuevos:
                excluidos.append({"objetivo": r.numero_sorteo, "bloque": k, "parte": tipo,
                                  "motivo": "color_fuera_de_la_paleta_del_corte",
                                  "detalle": f"colores ausentes antes del ajuste: {', '.join(nuevos)}"})
                continue
        evaluables.append(i)
    return evaluables, excluidos


def muestra_comun(instantanea: lv.Instantanea, protocolo: ProtocoloCarteras) -> dict:
    """Bloques exteriores (desde la posicion 60), su bloque interno y las
    exclusiones por reglas de dominio, antes de calcular ninguna perdida."""
    primera = protocolo.primera_exterior
    posiciones = list(range(primera, len(instantanea)))
    if len(posiciones) < protocolo.minimo_evaluables:
        raise MuestraInsuficienteCarteras(instantanea.codigo, len(instantanea), len(posiciones),
                                          protocolo.minimo_evaluables, "comparacion")
    recientes = posiciones[-protocolo.bloques * protocolo.tamano_bloque:]
    bloques, excluidos = [], []
    for k, i0 in enumerate(range(0, len(recientes), protocolo.tamano_bloque), start=1):
        exteriores = recientes[i0:i0 + protocolo.tamano_bloque]
        s = exteriores[0]
        paleta = instantanea.paleta(s) if instantanea.reglas.colores else ()
        evaluables, fuera = _evaluables(instantanea, exteriores, paleta, k, "exterior")
        internas = list(range(s - protocolo.bloque_interno, s))
        paleta_interna = instantanea.paleta(internas[0]) if instantanea.reglas.colores else ()
        internas_ok, fuera_internas = _evaluables(instantanea, internas, paleta_interna, k, "interno")
        excluidos.extend(fuera)
        bloques.append({"indice": k, "posicion_de_ajuste": s, "paleta": list(paleta), "posiciones": evaluables,
                        "objetivos": [instantanea.sorteos[i].numero_sorteo for i in evaluables],
                        "todos": [instantanea.sorteos[i].numero_sorteo for i in exteriores],
                        "fechas": [instantanea.sorteos[i].fecha.isoformat() for i in evaluables],
                        "interno": {"posicion_de_ajuste": internas[0], "paleta": list(paleta_interna),
                                    "posiciones": internas_ok,
                                    "objetivos": [instantanea.sorteos[i].numero_sorteo for i in internas_ok],
                                    "todos": [instantanea.sorteos[i].numero_sorteo for i in internas],
                                    "excluidos": fuera_internas}})
    total = sum(len(b["posiciones"]) for b in bloques)
    if total < protocolo.minimo_evaluables:
        raise MuestraInsuficienteCarteras(instantanea.codigo, len(instantanea), total, protocolo.minimo_evaluables,
                                          "comparacion")
    return {"bloques": bloques, "excluidos": excluidos, "objetivos": [o for b in bloques for o in b["objetivos"]]}


# ---------------------------------------------------------------------------
# Ajustes cacheados (cada candidato se ajusta una vez por posicion de corte)
# ---------------------------------------------------------------------------

class Ajustes:
    """Memoria de ajustes por (candidato, posicion de corte). Un fallo se
    recuerda tambien: el mismo ajuste no se reintenta con otro resultado."""

    def __init__(self, instantanea: lv.Instantanea, variables: lv.Variables, perfil: str,
                 avance: Callable[..., None] | None = None):
        self.instantanea, self.variables, self.perfil = instantanea, variables, perfil
        self._memo: dict = {}
        self.ajustes_realizados = 0
        self._avance = avance or (lambda *a, **k: None)

    def ajuste(self, entrada: lm.EntradaCatalogo, corte: int) -> lm.Ajustado:
        clave = (entrada.id, corte)
        if clave not in self._memo:
            self._avance("componente", candidato=entrada.id, posicion_de_corte=corte)
            try:
                self._memo[clave] = lm.ajustar_candidato(entrada, self.instantanea, self.variables, corte, self.perfil)
                self.ajustes_realizados += 1
            except lm.CandidatoNoDisponible as error:
                self._memo[clave] = error
        valor = self._memo[clave]
        if isinstance(valor, lm.CandidatoNoDisponible):
            raise valor
        return valor


def _predicciones_componentes(ajustes: Ajustes, componentes: Sequence[lm.EntradaCatalogo], corte: int,
                              filas: lv.Filas) -> tuple[np.ndarray, dict]:
    salida, detalle = [], {}
    for e in componentes:
        try:
            ajustado = ajustes.ajuste(e, corte)
            salida.append(ajustado.predecir(filas))
        except lm.CandidatoNoDisponible as error:
            raise ComponenteNoDisponible(e.id, error.estado, error.motivo) from error
        detalle[e.id] = ajustado.detalle
    return np.vstack(salida), detalle


def aprender_pesos(instantanea: lv.Instantanea, ajustes: Ajustes, componentes: Sequence[lm.EntradaCatalogo],
                   posicion_de_ajuste: int, posiciones: Sequence[int], paleta: tuple, d: int) -> dict:
    """Pesos de la malla elegidos con las predicciones del bloque interno.
    Los componentes se ajustan con objetivos de posicion < `posicion_de_ajuste`
    (el inicio del bloque interno). Lanza `ComponenteNoDisponible`."""
    if not posiciones:
        raise ComponenteNoDisponible("bloque_interno", "sin_objetivos_evaluables",
                                     "ningun objetivo del bloque interno es evaluable con la paleta del ajuste")
    colores = instantanea.reglas.colores
    filas = ajustes.variables.filas(posiciones, paleta=tuple(paleta) if colores else None)
    predicciones, detalle = _predicciones_componentes(ajustes, componentes, posicion_de_ajuste, filas)
    objetivos = [instantanea.sorteos[i].numero_sorteo for i in posiciones]
    perdidas = []
    for numeradores in MALLA:
        p = validar_mezcla(mezclar(predicciones, numeradores), filas, colores, instantanea.reglas.cantidad)
        met = le.metricas_por_objetivo(instantanea, filas, p)
        perdidas.append(float(np.mean([met[o]["log_loss"] for o in objetivos])))
    eleccion = elegir_mezcla(perdidas)
    numeradores = MALLA[eleccion["indice"]]
    return {"posicion_de_ajuste": posicion_de_ajuste, "objetivos": objetivos,
            "pesos": dict(zip((e.id for e in componentes), pesos_de(numeradores))),
            "numeradores": list(numeradores), "indice_en_la_malla": eleccion["indice"],
            "log_loss_minima": round(eleccion["minimo"], d), "mezclas_empatadas": len(eleccion["empatadas"]),
            "eligio_uniforme": numeradores[0] == PASOS_DE_MALLA,
            "perdidas": [{"numeradores": list(n), "log_loss": round(v, d)} for n, v in zip(MALLA, perdidas)],
            "ajustes_de_componentes": detalle}


def entrada_del_ensemble(juego: str) -> dict:
    """Entrada de catalogo (registro de Producto 5) del modelo combinado."""
    componentes = COMPONENTES[juego]
    colores = juego == "COLORLOTO"
    return {"id": ID_ENSEMBLE, "version": VERSION_ENSEMBLE, "nombre": "Modelo combinado (ensemble temporal)",
            "tipo": "modelo_combinado", "familia": "ensemble", "juegos": [juego],
            "salida": "distribucion_de_pares" if colores else "marginales_de_aparicion",
            "variables": "las de cada componente", "componentes": [
                {"id": c, "version": lm.CATALOGO[c].version, "nombre": lm.CATALOGO[c].nombre} for c in componentes],
            "parametros": {"malla": f"{len(MALLA)} mezclas (i/10, j/10, k/10), i + j + k = 10",
                           "tolerancia_de_empate": TOLERANCIA_DE_EMPATE, "bloque_interno": 10,
                           "criterio": "Log Loss media por sorteo del bloque interno"},
            "requisitos": {"calentamiento": 20, "objetivos_de_ajuste": 30, "objetivos_internos": 10,
                           "objetivos_exteriores_para_comparar": 10, "sorteos_para_generar": 60,
                           "sorteos_para_comparar": 70},
            "explicacion": ("Mezcla convexa de la uniforme y de las dos familias nuevas de Producto 4, con pesos "
                            "elegidos en los 10 objetivos anteriores; si gana la uniforme, lo dice."),
            "transformacion": "mezcla convexa de probabilidades finales (sin calibracion nueva)",
            "genera_pronostico": True}


# ---------------------------------------------------------------------------
# Comparacion exterior
# ---------------------------------------------------------------------------

def _resultado_de_candidato(base: dict, muestra: dict, por_objetivo: dict, uniforme: dict, incidencias: list,
                            bloques: list, filas_eval: list, probs_eval: list, d: int, colores: bool,
                            es_uniforme: bool) -> dict:
    evaluados = [o for o in muestra["objetivos"] if o in por_objetivo]
    estado = "completo" if len(evaluados) == len(muestra["objetivos"]) else "parcial" if evaluados else "no_disponible"
    resultado = {**base, "estado": estado, "incidencias": incidencias, "bloques": bloques,
                 "objetivos_evaluados": len(evaluados),
                 "agregado": le.agregar(por_objetivo, uniforme, evaluados, d, colores) if evaluados else None,
                 "por_objetivo": [{"objetivo": o, **{k: round(v, d) if isinstance(v, float) else v
                                                      for k, v in por_objetivo[o].items()},
                                   "diferencia_log_loss": round(por_objetivo[o]["log_loss"] - uniforme[o]["log_loss"], d)}
                                  for o in evaluados]}
    if evaluados and not es_uniforme:
        resultado["calibracion"] = le.diagnostico_de_calibracion(le._unir(filas_eval), np.concatenate(probs_eval),
                                                                 colores)
    if estado == "completo":
        diferencia = resultado["agregado"]["diferencia_log_loss"]
        resultado["veredicto"] = ("referencia" if es_uniforme else
                                  "menor_perdida_que_la_uniforme_en_esta_evaluacion" if diferencia < 0 else
                                  "la_uniforme_fue_mejor" if diferencia > 0 else "empate")
    return resultado


def evaluar(instantanea: lv.Instantanea, protocolo: ProtocoloCarteras,
            avance: Callable[..., None] | None = None) -> tuple[dict, dict]:
    """(cuerpo determinista, tiempos medidos) de la comparacion de Producto 5."""
    avance = avance or (lambda *a, **k: None)
    d = protocolo.decimales
    codigo = instantanea.codigo
    colores = instantanea.reglas.colores
    muestra = muestra_comun(instantanea, protocolo)
    variables = lv.Variables(instantanea)
    ajustes = Ajustes(instantanea, variables, protocolo.perfil, avance)
    entradas = candidatos_de_comparacion(codigo)
    componentes = [lm.CATALOGO[c] for c in COMPONENTES[codigo]]
    filas_ext = [variables.filas(b["posiciones"], paleta=tuple(b["paleta"]) if colores else None)
                 if b["posiciones"] else None for b in muestra["bloques"]]
    predicciones: dict = {}

    def predecir(entrada, k):
        clave = (entrada.id, k)
        if clave not in predicciones:
            b = muestra["bloques"][k]
            try:
                predicciones[clave] = ajustes.ajuste(entrada, b["posicion_de_ajuste"]).predecir(filas_ext[k])
            except lm.CandidatoNoDisponible as error:
                predicciones[clave] = error
        valor = predicciones[clave]
        if isinstance(valor, lm.CandidatoNoDisponible):
            raise valor
        return valor

    uniforme_entrada = next(e for e in entradas if e.familia == "uniforme")
    uniforme = {}
    for k, f in enumerate(filas_ext):
        if f is not None:
            uniforme.update(le.metricas_por_objetivo(instantanea, f, predecir(uniforme_entrada, k)))
    resultados, tiempos = [], {}
    for entrada in entradas:
        inicio = time.perf_counter()
        por_objetivo, incidencias, bloques, filas_eval, probs_eval = {}, [], [], [], []
        for k, (b, f) in enumerate(zip(muestra["bloques"], filas_ext)):
            avance("modelo", candidato=entrada.id, bloque=b["indice"], bloques=len(muestra["bloques"]))
            if f is None:
                bloques.append({"indice": b["indice"], "estado": "sin_objetivos_evaluables", "objetivos": []})
                continue
            try:
                p = predecir(entrada, k)
            except lm.CandidatoNoDisponible as error:
                incidencias.append({"bloque": b["indice"], "estado": error.estado, "motivo": error.motivo})
                bloques.append({"indice": b["indice"], "estado": error.estado, "motivo": error.motivo,
                                "objetivos": b["objetivos"]})
                continue
            met = le.metricas_por_objetivo(instantanea, f, p)
            por_objetivo.update(met)
            filas_eval.append(f)
            probs_eval.append(p)
            bloques.append({"indice": b["indice"], "estado": "evaluado", "objetivos": b["objetivos"],
                            "ajuste": ajustes.ajuste(entrada, b["posicion_de_ajuste"]).detalle,
                            "metricas": le.agregar(met, uniforme, b["objetivos"], d, colores)})
        resultados.append(_resultado_de_candidato(
            {**entrada.como_dict(protocolo.perfil)}, muestra, por_objetivo, uniforme, incidencias, bloques,
            filas_eval, probs_eval, d, colores, entrada.familia == "uniforme"))
        tiempos[entrada.id] = round(time.perf_counter() - inicio, 3)

    # ensemble: pesos del bloque interno de cada bloque exterior y evaluacion exterior con pesos fijos
    inicio = time.perf_counter()
    por_objetivo, incidencias, bloques, filas_eval, probs_eval, internos = {}, [], [], [], [], []
    for k, (b, f) in enumerate(zip(muestra["bloques"], filas_ext)):
        avance("pesos", candidato=ID_ENSEMBLE, bloque=b["indice"], bloques=len(muestra["bloques"]))
        interno = b["interno"]
        try:
            pesos = aprender_pesos(instantanea, ajustes, componentes, interno["posicion_de_ajuste"],
                                   interno["posiciones"], tuple(interno["paleta"]), d)
        except ComponenteNoDisponible as error:
            motivo = f"bloque interno: {error}"
            internos.append({"indice": b["indice"], "estado": error.estado, "componente": error.componente,
                             "motivo": error.motivo, "objetivos": interno["objetivos"],
                             "excluidos": interno["excluidos"]})
            incidencias.append({"bloque": b["indice"], "estado": "componente_no_disponible", "motivo": motivo})
            bloques.append({"indice": b["indice"], "estado": "componente_no_disponible", "motivo": motivo,
                            "objetivos": b["objetivos"]})
            continue
        internos.append({"indice": b["indice"], "estado": "pesos_aprendidos", "excluidos": interno["excluidos"],
                         "todos": interno["todos"], **pesos})
        if f is None:
            bloques.append({"indice": b["indice"], "estado": "sin_objetivos_evaluables", "objetivos": [],
                            "pesos": pesos["pesos"]})
            continue
        try:
            componentes_p = np.vstack([predecir(e, k) for e in componentes])
            p = validar_mezcla(mezclar(componentes_p, pesos["numeradores"]), f, colores, instantanea.reglas.cantidad)
        except lm.CandidatoNoDisponible as error:
            motivo = f"bloque exterior: {error.estado}: {error.motivo}"
            incidencias.append({"bloque": b["indice"], "estado": "componente_no_disponible", "motivo": motivo})
            bloques.append({"indice": b["indice"], "estado": "componente_no_disponible", "motivo": motivo,
                            "objetivos": b["objetivos"], "pesos": pesos["pesos"]})
            continue
        met = le.metricas_por_objetivo(instantanea, f, p)
        por_objetivo.update(met)
        filas_eval.append(f)
        probs_eval.append(p)
        bloques.append({"indice": b["indice"], "estado": "evaluado", "objetivos": b["objetivos"],
                        "pesos": pesos["pesos"], "eligio_uniforme": pesos["eligio_uniforme"],
                        "ajuste": {c.id: ajustes.ajuste(c, b["posicion_de_ajuste"]).detalle for c in componentes},
                        "metricas": le.agregar(met, uniforme, b["objetivos"], d, colores)})
    ensemble = _resultado_de_candidato(entrada_del_ensemble(codigo), muestra, por_objetivo, uniforme, incidencias,
                                       bloques, filas_eval, probs_eval, d, colores, False)
    resultados.append(ensemble)
    tiempos[ID_ENSEMBLE] = round(time.perf_counter() - inicio, 3)
    eligieron_uniforme = sum(1 for i in internos if i.get("eligio_uniforme"))
    cuerpo = {"muestra_comun": {**muestra, "bloques": [{k: v for k, v in b.items() if k not in ("posiciones",)}
                                                      | {"interno": {kk: vv for kk, vv in b["interno"].items()
                                                                     if kk != "posiciones"}}
                                                      for b in muestra["bloques"]],
                                "total_objetivos": len(muestra["objetivos"]),
                                "muestra_pequena": le.es_muestra_pequena(len(muestra["objetivos"]), protocolo)},
              "candidatos": resultados, "resumen": {**le.resumen(resultados), "nota": (
                  "Comparacion exploratoria sobre objetivos ya usados como historico: elegir un candidato despues "
                  "de verla no acredita ventaja futura. Reevaluar los candidatos de Producto 4 con este protocolo es "
                  "un informe nuevo; sus experimentos guardados no cambian.")},
              "ensemble": {"componentes": [c.id for c in componentes], "bloques_internos": internos,
                           "bloques_que_eligieron_la_uniforme": eligieron_uniforme,
                           "bloques_con_pesos": sum(1 for i in internos if i["estado"] == "pesos_aprendidos"),
                           "nota": ("La perdida del bloque interno solo sirve para elegir los pesos: no es un "
                                    "resultado exterior. Si el ajuste elige peso 1 para la uniforme, el modelo "
                                    "combinado coincide con la referencia uniforme en ese bloque.")},
              "ajustes_realizados": ajustes.ajustes_realizados}
    if instantanea.reglas.superbalota:
        cuerpo["superbalota"] = le.evaluar_superbalota(instantanea, muestra, d)
    return cuerpo, tiempos


# ---------------------------------------------------------------------------
# Vector fuente para generar (objetivo siguiente al corte)
# ---------------------------------------------------------------------------

MODELOS_DE_CARTERA_NOTA = ("La uniforme puede generar carteras en Producto 5 aunque en Producto 4 no emita un "
                           "pronostico individual; sigue siendo la referencia, no un modelo aprendido.")


def modelos_de_cartera(juego: str) -> list[str]:
    """Modelos admitidos para construir carteras: el catalogo de Producto 4 del
    juego (incluida la uniforme) y el modelo combinado."""
    return [e.id for e in lm.candidatos_del_juego(juego)] + [ID_ENSEMBLE]


def fuente(instantanea: lv.Instantanea, modelo: str, perfil: str = "predeterminado",
           avance: Callable[..., None] | None = None) -> dict:
    """Probabilidades del objetivo corte + 1 con todo el historico de la
    instantanea (vector fuente de la cartera). Lanza `CandidatoNoDisponible`,
    `ComponenteNoDisponible` o `MuestraInsuficienteCarteras`."""
    codigo = instantanea.codigo
    reglas = instantanea.reglas
    if modelo not in modelos_de_cartera(codigo):
        raise ValueError(f"modelo no admitido para {codigo}: {modelo!r}")
    d = 12
    n = len(instantanea)
    variables = lv.Variables(instantanea)
    ajustes = Ajustes(instantanea, variables, perfil, avance)
    filas = variables.filas([n])
    detalle: dict = {}
    if modelo == ID_ENSEMBLE:
        protocolo = ProtocoloCarteras(perfil=perfil)
        if n < protocolo.minimo_para_generar:
            raise MuestraInsuficienteCarteras(codigo, n, n, protocolo.minimo_para_generar, "generacion")
        componentes = [lm.CATALOGO[c] for c in COMPONENTES[codigo]]
        internas = list(range(n - protocolo.bloque_interno, n))
        paleta_interna = instantanea.paleta(internas[0]) if reglas.colores else ()
        internas_ok, excluidos = _evaluables(instantanea, internas, paleta_interna, 0, "interno")
        pesos = aprender_pesos(instantanea, ajustes, componentes, internas[0], internas_ok, paleta_interna, d)
        predicciones, detalle_final = _predicciones_componentes(ajustes, componentes, n, filas)
        p = validar_mezcla(mezclar(predicciones, pesos["numeradores"]), filas, reglas.colores, reglas.cantidad)
        detalle = {"bloque_interno": {**pesos, "excluidos": excluidos,
                                      "todos": [instantanea.sorteos[i].numero_sorteo for i in internas]},
                   "ajuste_final": detalle_final}
    else:
        entrada = lm.CATALOGO[modelo]
        ajustado = ajustes.ajuste(entrada, n)
        p = ajustado.predecir(filas)
        detalle = {"ajuste_final": ajustado.detalle}
    salida = {"modelo": modelo, "objetivo": instantanea.corte + 1, "calculado_hasta_sorteo": instantanea.corte,
              "tipo": "distribucion_de_pares" if reglas.colores else "marginales_de_aparicion",
              "candidatos": [list(c) for c in filas.candidatos] if reglas.colores else list(filas.candidatos),
              "probabilidades": [round(float(x), d) for x in p],
              "masa": 1 if reglas.colores else reglas.cantidad, "detalle": detalle}
    if reglas.colores:
        salida["paleta"] = list(instantanea.paleta())
    if reglas.superbalota:
        sb = lm.probabilidades_superbalota(instantanea.sorteos, reglas.superbalota)
        salida["superbalota"] = {"estrategia": "frecuencia_con_suavizado_de_laplace",
                                 "candidatos": sorted(sb), "probabilidades": [round(sb[c], d) for c in sorted(sb)],
                                 "nota": "objetivo separado; el modelo de los numeros no aprende la superbalota"}
    return salida
