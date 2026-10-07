"""
Pronostico experimental de ColorLoto -Producto 2.

Dominio (`ColorLotoGame`): 6 balotas, cada una un par (numero 1..7,
color); se permite repetir numero, color y par. El dominio declara que el
orden no importa para el premio mayor, asi que el objetivo es el
MULTICONJUNTO de 6 pares: la posicion de extraccion no se modela.

PALETA. Para cada corte, la paleta es la de los colores observados en los
sorteos anteriores al objetivo (nunca la tabla `colores` actual ni el
futuro). Un objetivo que trae un color ausente de esa paleta no puede
recibir probabilidad positiva de un modelo ni de la referencia definidos
sobre la paleta del corte: se EXCLUYE de la evaluacion, se cuenta y se
informa con su motivo. El pronostico nunca usa colores no observados.

MODELO. Multinomial con probabilidades suavizadas: las 6 balotas son
independientes e identicamente distribuidas sobre los 7 x K pares de la
paleta del corte, con probabilidades puntuales obtenidas por suavizado
aditivo `alfa` de los conteos previos (para pares escasos o nunca
observados):

    p(n, c) = (conteo(n, c) + alfa) / (6 T + alfa * 7 K)

Es la media a posteriori de una Dirichlet(alfa) simetrica, usada como
estimacion puntual. La probabilidad de un multiconjunto es la multinomial
con esas probabilidades: 6! / prod(m!) * prod p^m. NO es la distribucion
predictiva Dirichlet-multinomial (que integraria la incertidumbre sobre p
y daria otras probabilidades a los multiconjuntos con repeticion); es una
eleccion de diseno, fijada por una prueba. La combinacion sugerida es el multiconjunto mas
probable, calculado de forma exacta con un algoritmo voraz (el logaritmo
de la probabilidad es separable y concavo en las multiplicidades). La
`muestra_con_semilla` es una combinacion extraida del modelo con
`random.Random` y la semilla declarada: es reproducible.

REFERENCIA. Uniforme sobre los 7 x K pares de la misma paleta del corte;
su combinacion de referencia es la de menor orden (numero, color), el
mismo desempate determinista que usa `metricas.py`.

METRICAS (por objetivo evaluado y luego promedio):
- log_loss_por_balota: -(1/6) sum log p(balota); menor es mejor;
- brier_por_balota: (1/6) sum_balota sum_pares (p - 1[par = balota])^2;
- log_loss_multiconjunto: -log P(multiconjunto observado);
- coincidencias_de_pares_por_sorteo: tamano de la interseccion con
  repeticion entre la combinacion sugerida y la observada (0..6).
No comparten escala con las metricas de los numeros de Baloto o MiLoto.

Modulo puro: sin reloj, red, base de datos ni escritura.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from app.application.estadisticas.tipos import ResultadoColorLoto
from app.application.ml import pronostico_comun as comun
from app.application.ml.historico_util import validar_y_ordenar_historico
from app.application.ml.pronostico_experimental import ESTADO_DE_USO, PronosticoExperimentalError
from app.application.ml.registro_prospectivo import hash_entrada, serializar_entrada

DatosInsuficientesError = comun.DatosInsuficientesError
CODIGO_JUEGO = "COLORLOTO"
NUMEROS = (1, 7)
BALOTAS = 6
ESTRATEGIA = "pares_multinomial_con_suavizado_aditivo"
VERSION_DE_LA_LINEA = "producto2-colorloto-1"


@dataclass(frozen=True)
class ConfiguracionColorLoto:
    alfa: float = 1.0
    minimo_sorteos_de_entrenamiento: int = 20
    minimo_objetivos_evaluados: int = 10
    tamano_bloque: int = 20
    semilla: int = 42
    decimales: int = 12

    def __post_init__(self) -> None:
        if not (isinstance(self.alfa, (int, float)) and self.alfa > 0):
            raise PronosticoExperimentalError(f"alfa invalido: {self.alfa!r}")
        for nombre in ("minimo_sorteos_de_entrenamiento", "minimo_objetivos_evaluados", "tamano_bloque", "decimales"):
            valor = getattr(self, nombre)
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
                raise PronosticoExperimentalError(f"{nombre} invalido: {valor!r}")
        if isinstance(self.semilla, bool) or not isinstance(self.semilla, int) or self.semilla < 0:
            raise PronosticoExperimentalError(f"semilla invalida: {self.semilla!r}")


# ---------------------------------------------------------------------------
# Piezas del modelo
# ---------------------------------------------------------------------------

def paleta_del_corte(previos: Sequence[ResultadoColorLoto]) -> tuple[str, ...]:
    return tuple(sorted({c for r in previos for _, c in r.pares}))


def distribucion_de_pares(previos: Sequence[ResultadoColorLoto], configuracion: ConfiguracionColorLoto) -> dict:
    paleta = paleta_del_corte(previos)
    pares = [(n, c) for n in range(NUMEROS[0], NUMEROS[1] + 1) for c in paleta]
    conteo = Counter(par for r in previos for par in r.pares)
    total = BALOTAS * len(previos) + configuracion.alfa * len(pares)
    return {par: (conteo[par] + configuracion.alfa) / total for par in pares}


def probabilidad_multiconjunto(distribucion: dict, pares: Sequence) -> float:
    conteo = Counter(tuple(p) for p in pares)
    log = math.lgamma(len(pares) + 1)
    for par, m in conteo.items():
        p = distribucion.get(par, 0.0)
        if p <= 0:
            return 0.0
        log += m * math.log(p) - math.lgamma(m + 1)
    return math.exp(log)


def multiconjunto_mas_probable(distribucion: dict, k: int = BALOTAS) -> list:
    """Exacto: en cada paso se anade el par con mayor p / (m + 1); empate
    por orden (numero, color)."""
    multiplicidad: Counter = Counter()
    for _ in range(k):
        par = min(sorted(distribucion), key=lambda q: -distribucion[q] / (multiplicidad[q] + 1))
        multiplicidad[par] += 1
    return sorted(multiplicidad.elements())


def coincidencias(a: Sequence, b: Sequence) -> int:
    """Tamano de la interseccion con repeticion de dos multiconjuntos."""
    return sum((Counter(tuple(x) for x in a) & Counter(tuple(x) for x in b)).values())


def _metricas_objetivo(distribucion: dict, objetivo: Sequence) -> dict:
    suma_cuadrados = sum(p * p for p in distribucion.values())
    return {"log_loss_por_balota": sum(-math.log(distribucion[tuple(b)]) for b in objetivo) / len(objetivo),
            "brier_por_balota": sum(suma_cuadrados - 2 * distribucion[tuple(b)] + 1 for b in objetivo) / len(objetivo),
            "log_loss_multiconjunto": -math.log(probabilidad_multiconjunto(distribucion, objetivo)),
            "coincidencias_de_pares_por_sorteo": coincidencias(multiconjunto_mas_probable(distribucion), objetivo)}


def metricas_de_objetivo(distribucion: dict, objetivo: Sequence) -> dict:
    """Metricas de un objetivo ColorLoto con una distribucion de pares dada
    (la misma definicion que usa la evaluacion walk-forward). Producto 3 la
    usa con las probabilidades guardadas en el artefacto."""
    return _metricas_objetivo(distribucion, objetivo)


# ---------------------------------------------------------------------------
# Historico, identidad y linea completa
# ---------------------------------------------------------------------------

def huella_del_historico(ordenado: Sequence[ResultadoColorLoto]) -> str:
    """SHA-256 canonico (AE-52) de numero, fecha y multiconjunto de pares
    de cada sorteo; el orden de las balotas no interviene."""
    return hash_entrada(serializar_entrada({"sorteos": [
        [r.numero_sorteo, r.fecha.isoformat(), sorted([n, c] for n, c in r.pares)] for r in ordenado]}))


def _validar(historico, hasta_numero_sorteo):
    ordenado = validar_y_ordenar_historico(historico, CODIGO_JUEGO)
    if not ordenado:
        raise DatosInsuficientesError(CODIGO_JUEGO, 0, 0, "no hay sorteos")
    if hasta_numero_sorteo is not None:
        posteriores = [r.numero_sorteo for r in ordenado if r.numero_sorteo > hasta_numero_sorteo]
        if posteriores:
            raise PronosticoExperimentalError(
                f"El historico contiene sorteos posteriores al corte {hasta_numero_sorteo}: {posteriores[:5]}")
    for r in ordenado:
        if len(r.pares) != BALOTAS:
            raise PronosticoExperimentalError(f"Sorteo {r.numero_sorteo}: se esperaban {BALOTAS} balotas")
        for n, c in r.pares:
            if not NUMEROS[0] <= n <= NUMEROS[1]:
                raise PronosticoExperimentalError(f"Sorteo {r.numero_sorteo}: numero fuera de [1, 7]: {n}")
            if not isinstance(c, str) or not c:
                raise PronosticoExperimentalError(f"Sorteo {r.numero_sorteo}: color no valido: {c!r}")
    return ordenado


def clave_de_entrada(historico: Sequence[ResultadoColorLoto], *, hasta_numero_sorteo: int | None = None,
                     configuracion: ConfiguracionColorLoto = ConfiguracionColorLoto()) -> str:
    ordenado = _validar(historico, hasta_numero_sorteo)
    return hash_entrada(serializar_entrada({
        "esquema": comun.ESQUEMA_ARTEFACTO_V2, "version_de_la_linea": VERSION_DE_LA_LINEA, "juego": CODIGO_JUEGO,
        "reglas": [NUMEROS[0], NUMEROS[1], BALOTAS, "con_repeticion", "multiconjunto"],
        "corte": ordenado[-1].numero_sorteo, "sha256_historico": huella_del_historico(ordenado),
        "configuracion": asdict(configuracion), "implementacion": "python puro (sin dependencias numericas)",
    }))


_PRINCIPALES = {"log_loss_por_balota": True, "brier_por_balota": True, "coincidencias_de_pares_por_sorteo": False,
                "log_loss_multiconjunto": True}


def _promedios(filas: list[dict], d: int) -> dict:
    claves = ("log_loss_por_balota", "brier_por_balota", "log_loss_multiconjunto", "coincidencias_de_pares_por_sorteo")
    return {**{k: comun.redondear(sum(f[k] for f in filas) / len(filas), d) for k in claves},
            "sorteos": len(filas), "balotas": BALOTAS * len(filas)}


def generar_pronostico(historico: Sequence[ResultadoColorLoto], *, hasta_numero_sorteo: int | None = None,
                       configuracion: ConfiguracionColorLoto = ConfiguracionColorLoto()) -> dict:
    """Cuerpo determinista del artefacto `pronostico-experimental/2`."""
    ordenado = _validar(historico, hasta_numero_sorteo)
    requeridos = configuracion.minimo_sorteos_de_entrenamiento + configuracion.minimo_objetivos_evaluados
    if len(ordenado) < requeridos:
        raise DatosInsuficientesError(
            CODIGO_JUEGO, len(ordenado), requeridos,
            f"{configuracion.minimo_sorteos_de_entrenamiento} de entrenamiento minimo y "
            f"{configuracion.minimo_objetivos_evaluados} objetivos evaluados")
    d = configuracion.decimales
    modelo_por_objetivo, uniforme_por_objetivo, excluidos = {}, {}, []
    for i in range(configuracion.minimo_sorteos_de_entrenamiento, len(ordenado)):
        previos, objetivo = ordenado[:i], ordenado[i]
        paleta = set(paleta_del_corte(previos))
        if any(c not in paleta for _, c in objetivo.pares):
            excluidos.append(objetivo.numero_sorteo)
            continue
        dist = distribucion_de_pares(previos, configuracion)
        uniforme = {par: 1 / len(dist) for par in dist}
        modelo_por_objetivo[objetivo.numero_sorteo] = _metricas_objetivo(dist, objetivo.pares)
        uniforme_por_objetivo[objetivo.numero_sorteo] = _metricas_objetivo(uniforme, objetivo.pares)
    objetivos = list(modelo_por_objetivo)
    if len(objetivos) < configuracion.minimo_objetivos_evaluados:
        raise DatosInsuficientesError(
            CODIGO_JUEGO, len(ordenado), requeridos,
            f"solo {len(objetivos)} objetivos evaluables; {len(excluidos)} excluidos por traer un color ausente de "
            "la paleta de su corte")
    posicion = {r.numero_sorteo: i for i, r in enumerate(ordenado)}
    bloques = []
    for bloque in comun.bloques_consecutivos(objetivos, configuracion.tamano_bloque):
        modelo = _promedios([modelo_por_objetivo[o] for o in bloque], d)
        uniforme = _promedios([uniforme_por_objetivo[o] for o in bloque], d)
        previo = ordenado[posicion[bloque[0]] - 1].numero_sorteo
        bloques.append({"objetivos": [bloque[0], bloque[-1]],
                        "entrenamiento": {"desde": ordenado[0].numero_sorteo, "hasta": previo},
                        "modelo": modelo, "referencia_uniforme": uniforme,
                        "comparacion": comun.comparar(modelo, uniforme, _PRINCIPALES)})
    agregado_modelo = _promedios([modelo_por_objetivo[o] for o in objetivos], d)
    agregado_uniforme = _promedios([uniforme_por_objetivo[o] for o in objetivos], d)

    paleta = paleta_del_corte(ordenado)
    final = distribucion_de_pares(ordenado, configuracion)
    sugeridos = multiconjunto_mas_probable(final)
    corte = ordenado[-1].numero_sorteo
    generador = random.Random(f"{configuracion.semilla}-{corte + 1}")
    claves = sorted(final)
    muestra = sorted(generador.choices(claves, weights=[final[k] for k in claves], k=BALOTAS))
    m = len(final)
    return {
        "esquema": comun.ESQUEMA_ARTEFACTO_V2,
        "clave_de_entrada": clave_de_entrada(ordenado, configuracion=configuracion),
        "estado_de_uso": ESTADO_DE_USO,
        "contrato_de_uso": comun.contrato_de_uso("ColorLoto"),
        "juego": CODIGO_JUEGO,
        "version_de_la_linea": VERSION_DE_LA_LINEA,
        "estrategia": {
            "nombre": ESTRATEGIA,
            "descripcion": "multinomial de 6 balotas independientes sobre los pares numero-color de la paleta "
                           "del corte, con probabilidades suavizadas p(n,c) = (conteo + alfa) / (6T + alfa*7K) "
                           "(media a posteriori de una Dirichlet(alfa), usada como estimacion puntual); no es la "
                           "distribucion predictiva Dirichlet-multinomial; objetivo = multiconjunto de 6 pares",
            "referencia": f"uniforme 1/(7K) sobre los pares de la paleta del corte (hoy K={len(paleta)}: 1/{m})",
            "orden": "el orden de extraccion no forma parte del objetivo",
            "colores_nuevos": "un objetivo con un color ausente de la paleta de su corte se excluye de la "
                              "evaluacion; el pronostico solo usa colores ya observados",
        },
        "configuracion": asdict(configuracion),
        "datos": comun.procedencia([r.numero_sorteo for r in ordenado], [r.fecha for r in ordenado], corte,
                                   huella_del_historico(ordenado)),
        "evaluacion_walk_forward": {
            "esquema": "ventana creciente: cada objetivo se predice solo con los sorteos anteriores y con su paleta",
            "muestra": {"sorteos": len(ordenado), "objetivos_evaluados": len(objetivos),
                        "objetivos_excluidos_por_color_nuevo": len(excluidos),
                        "primeros_objetivos_excluidos": excluidos[:20],
                        "motivo_de_exclusion": "el objetivo trae un color ausente de la paleta observada antes de "
                                               "el; ni el modelo ni la referencia pueden asignarle probabilidad",
                        "primer_objetivo": objetivos[0], "ultimo_objetivo": objetivos[-1],
                        "minimo_sorteos_de_entrenamiento": configuracion.minimo_sorteos_de_entrenamiento,
                        "minimo_objetivos_evaluados": configuracion.minimo_objetivos_evaluados},
            "bloques": bloques,
            "agregado": {"modelo": agregado_modelo, "referencia_uniforme": agregado_uniforme,
                         "comparacion": comun.comparar(agregado_modelo, agregado_uniforme, _PRINCIPALES)},
            "definiciones": "log_loss_por_balota = -(1/6) sum log p(balota); brier_por_balota = (1/6) sum sobre "
                            "balotas de sum sobre pares (p - acierto)^2; log_loss_multiconjunto = -log P(multiconjunto "
                            "observado); coincidencias_de_pares = interseccion con repeticion entre la combinacion "
                            "sugerida y la observada (0..6). Denominadores: 6 balotas por sorteo evaluado.",
        },
        "pronostico": {
            "objetivo": corte + 1,
            "calculado_hasta_sorteo": corte,
            "paleta": list(paleta),
            "pares": [{"numero": n, "color": c, "probabilidad": comun.redondear(final[(n, c)], d)} for n, c in sugeridos],
            "probabilidad_del_multiconjunto": comun.redondear(probabilidad_multiconjunto(final, sugeridos), d),
            "probabilidad_uniforme_por_par": comun.redondear(1 / m, d),
            "muestra_con_semilla": {"semilla": configuracion.semilla,
                                    "pares": [{"numero": n, "color": c} for n, c in muestra]},
            "ranking_de_pares": [{"numero": n, "color": c, "probabilidad": comun.redondear(final[(n, c)], d),
                                  "probabilidad_uniforme": comun.redondear(1 / m, d)}
                                 for n, c in sorted(final, key=lambda k: (-final[k], k))],
            "nota": "combinacion mas probable del modelo (multiconjunto, sin orden); no es una garantia",
        },
        "superbalota": None,
        "contexto": comun.contexto(CODIGO_JUEGO),
    }
