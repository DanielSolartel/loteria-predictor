"""
Pronostico experimental de MiLoto -Producto 2.

Dominio (`MiLotoGame`): 5 numeros distintos de 1..39, sin superbalota.

POR QUE NO SE REUTILIZA EL MODELO DE AE-36. La regresion logistica de
Producto 1 necesita 50 sorteos de calentamiento para sus ventanas de 10,
20 y 50 sorteos y, en la configuracion de Producto 1, 100 objetivos de
entrenamiento mas bloques de 20. Con los 84 sorteos de MiLoto observados
quedarian 34 objetivos y una calibracion sobre unos 7 sorteos: ni las
variables (ventana de 50) ni la validacion son apropiadas para esa
muestra.

ESTRATEGIA. Estimador de frecuencia contraido hacia la uniforme (media a
posteriori de una previa Beta por numero, con fuerza fija):

    p(n) = (c_n + beta * 5/39) / (T + beta)

donde `T` es la cantidad de sorteos anteriores al objetivo y `c_n` en
cuantos aparecio `n`. Las 39 probabilidades suman exactamente 5. Con
`beta = 39` pseudo-sorteos la previa pesa lo mismo que 39 sorteos reales:
con pocos datos el modelo queda cerca de la uniforme y se separa de ella
a medida que crece el historico. `beta` se fija de antemano; no se ajusta
mirando la evaluacion.

EVALUACION PARA MUESTRA CORTA. Ventana creciente: cada sorteo con al menos
`minimo_sorteos_de_entrenamiento` (20) sorteos anteriores es un objetivo y
se predice solo con esos anteriores. Hacen falta al menos
`minimo_objetivos_evaluados` (10) objetivos, es decir 30 sorteos; si no,
`DatosInsuficientesError`. Los objetivos se agrupan en bloques de 8 solo
para mostrarlos. Metricas del repositorio (`metricas.py`): Log Loss y
Brier sobre las 39 filas candidato-sorteo y aciertos top-5 (5 x
Precision@5, desempate por numero ascendente), frente a la referencia
uniforme 5/39 (`baselines.baseline_uniforme`).

Modulo puro: sin reloj, red, base de datos ni escritura.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml import pronostico_comun as comun
from app.application.ml.baselines import baseline_uniforme
from app.application.ml.historico_util import validar_y_ordenar_historico
from app.application.ml.metricas import evaluar
from app.application.ml.pronostico_experimental import (
    ESTADO_DE_USO,
    PronosticoExperimentalError,
    huella_del_historico,
)
from app.application.ml.registro_prospectivo import hash_entrada, serializar_entrada

DatosInsuficientesError = comun.DatosInsuficientesError
CODIGO_JUEGO = "MILOTO"
RANGO = (1, 39)
CANTIDAD = 5
ESTRATEGIA = "frecuencia_con_contraccion_a_la_uniforme"
VERSION_DE_LA_LINEA = "producto2-miloto-1"


@dataclass(frozen=True)
class ConfiguracionMiLoto:
    fuerza_previa: float = 39.0
    minimo_sorteos_de_entrenamiento: int = 20
    minimo_objetivos_evaluados: int = 10
    tamano_bloque: int = 8
    decimales: int = 12

    def __post_init__(self) -> None:
        if not (isinstance(self.fuerza_previa, (int, float)) and self.fuerza_previa > 0):
            raise PronosticoExperimentalError(f"fuerza_previa invalida: {self.fuerza_previa!r}")
        for nombre in ("minimo_sorteos_de_entrenamiento", "minimo_objetivos_evaluados", "tamano_bloque", "decimales"):
            valor = getattr(self, nombre)
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
                raise PronosticoExperimentalError(f"{nombre} invalido: {valor!r}")


@dataclass(frozen=True)
class _Fila:
    """Fila candidato-sorteo con lo que usan `metricas.py` y `baselines.py`."""

    sorteo_objetivo: int
    numero_candidato: int
    etiqueta: int


def probabilidades_de_inclusion(previos: Sequence[ResultadoNumerico], configuracion: ConfiguracionMiLoto) -> dict:
    lo, hi = RANGO
    total = len(previos)
    uniforme = CANTIDAD / (hi - lo + 1)
    beta = float(configuracion.fuerza_previa)
    conteo = {n: 0 for n in range(lo, hi + 1)}
    for r in previos:
        for n in r.numeros:
            conteo[n] += 1
    return {n: (conteo[n] + beta * uniforme) / (total + beta) for n in conteo}


def _validar(historico, hasta_numero_sorteo):
    ordenado = validar_y_ordenar_historico(historico, CODIGO_JUEGO)
    if not ordenado:
        raise DatosInsuficientesError(CODIGO_JUEGO, 0, 0, "no hay sorteos")
    if hasta_numero_sorteo is not None:
        posteriores = [r.numero_sorteo for r in ordenado if r.numero_sorteo > hasta_numero_sorteo]
        if posteriores:
            raise PronosticoExperimentalError(
                f"El historico contiene sorteos posteriores al corte {hasta_numero_sorteo}: {posteriores[:5]}")
    lo, hi = RANGO
    for r in ordenado:
        if r.superbalota is not None:
            raise PronosticoExperimentalError(f"Sorteo {r.numero_sorteo}: MiLoto no tiene superbalota")
        if len(r.numeros) != CANTIDAD or len(set(r.numeros)) != CANTIDAD:
            raise PronosticoExperimentalError(f"Sorteo {r.numero_sorteo}: se esperaban {CANTIDAD} numeros distintos")
        if any(n < lo or n > hi for n in r.numeros):
            raise PronosticoExperimentalError(f"Sorteo {r.numero_sorteo}: numeros fuera de [{lo}, {hi}]")
    return ordenado


def _minimos(ordenado, configuracion):
    requeridos = configuracion.minimo_sorteos_de_entrenamiento + configuracion.minimo_objetivos_evaluados
    if len(ordenado) < requeridos:
        raise DatosInsuficientesError(
            CODIGO_JUEGO, len(ordenado), requeridos,
            f"{configuracion.minimo_sorteos_de_entrenamiento} de entrenamiento minimo y "
            f"{configuracion.minimo_objetivos_evaluados} objetivos evaluados")


def clave_de_entrada(historico: Sequence[ResultadoNumerico], *, hasta_numero_sorteo: int | None = None,
                     configuracion: ConfiguracionMiLoto = ConfiguracionMiLoto()) -> str:
    ordenado = _validar(historico, hasta_numero_sorteo)
    return hash_entrada(serializar_entrada({
        "esquema": comun.ESQUEMA_ARTEFACTO_V2, "version_de_la_linea": VERSION_DE_LA_LINEA, "juego": CODIGO_JUEGO,
        "reglas": [RANGO[0], RANGO[1], CANTIDAD, None], "corte": ordenado[-1].numero_sorteo,
        "sha256_historico": huella_del_historico(ordenado), "configuracion": asdict(configuracion),
        "implementacion": "python puro (sin dependencias numericas)",
    }))


def _metricas(filas, probabilidades, d):
    m = evaluar(filas, probabilidades)
    return {"log_loss": comun.redondear(m.log_loss, d), "brier": comun.redondear(m.brier_score, d),
            "aciertos_top5_por_sorteo": comun.redondear(5 * m.precision_en_5, d),
            "sorteos": m.total_sorteos, "filas": m.total_filas}


def _uniforme(filas, d):
    m = baseline_uniforme(filas, RANGO[0], RANGO[1], CANTIDAD).metricas
    return {"log_loss": comun.redondear(m.log_loss, d), "brier": comun.redondear(m.brier_score, d),
            "aciertos_top5_por_sorteo": comun.redondear(5 * m.precision_en_5, d),
            "sorteos": m.total_sorteos, "filas": m.total_filas}


_PRINCIPALES = {"log_loss": True, "brier": True, "aciertos_top5_por_sorteo": False}


def generar_pronostico(historico: Sequence[ResultadoNumerico], *, hasta_numero_sorteo: int | None = None,
                       configuracion: ConfiguracionMiLoto = ConfiguracionMiLoto()) -> dict:
    """Cuerpo determinista del artefacto `pronostico-experimental/2`."""
    ordenado = _validar(historico, hasta_numero_sorteo)
    _minimos(ordenado, configuracion)
    d = configuracion.decimales
    lo, hi = RANGO
    inicio = configuracion.minimo_sorteos_de_entrenamiento
    filas_por_objetivo, probs_por_objetivo = {}, {}
    for i in range(inicio, len(ordenado)):
        objetivo = ordenado[i]
        p = probabilidades_de_inclusion(ordenado[:i], configuracion)
        filas_por_objetivo[objetivo.numero_sorteo] = [
            _Fila(objetivo.numero_sorteo, n, 1 if n in objetivo.numeros else 0) for n in range(lo, hi + 1)]
        probs_por_objetivo[objetivo.numero_sorteo] = [p[n] for n in range(lo, hi + 1)]
    objetivos = list(filas_por_objetivo)
    bloques = []
    for bloque in comun.bloques_consecutivos(objetivos, configuracion.tamano_bloque):
        filas = [f for o in bloque for f in filas_por_objetivo[o]]
        probs = [x for o in bloque for x in probs_por_objetivo[o]]
        indice = next(i for i, r in enumerate(ordenado) if r.numero_sorteo == bloque[0])
        modelo, uniforme = _metricas(filas, probs, d), _uniforme(filas, d)
        bloques.append({"objetivos": [bloque[0], bloque[-1]],
                        "entrenamiento": {"desde": ordenado[0].numero_sorteo, "hasta": ordenado[indice - 1].numero_sorteo},
                        "modelo": modelo, "referencia_uniforme": uniforme,
                        "comparacion": comun.comparar(modelo, uniforme, _PRINCIPALES)})
    filas = [f for o in objetivos for f in filas_por_objetivo[o]]
    probs = [x for o in objetivos for x in probs_por_objetivo[o]]
    agregado_modelo, agregado_uniforme = _metricas(filas, probs, d), _uniforme(filas, d)
    final = probabilidades_de_inclusion(ordenado, configuracion)
    ranking = sorted(final, key=lambda n: (-final[n], n))
    corte = ordenado[-1].numero_sorteo
    return {
        "esquema": comun.ESQUEMA_ARTEFACTO_V2,
        "clave_de_entrada": clave_de_entrada(ordenado, configuracion=configuracion),
        "estado_de_uso": ESTADO_DE_USO,
        "contrato_de_uso": comun.contrato_de_uso("MiLoto"),
        "juego": CODIGO_JUEGO,
        "version_de_la_linea": VERSION_DE_LA_LINEA,
        "estrategia": {
            "nombre": ESTRATEGIA,
            "descripcion": "p(n) = (c_n + beta*5/39) / (T + beta): frecuencia de aparicion contraida hacia la "
                           "uniforme; beta fijo de antemano",
            "referencia": "uniforme 5/39 por numero",
            "por_que_no_ae36": "la logistica de AE-36 exige 50 sorteos de calentamiento y 100 objetivos de "
                               "entrenamiento; con la muestra de MiLoto no es apropiada",
        },
        "configuracion": asdict(configuracion),
        "datos": comun.procedencia([r.numero_sorteo for r in ordenado], [r.fecha for r in ordenado], corte,
                                   huella_del_historico(ordenado)),
        "evaluacion_walk_forward": {
            "esquema": "ventana creciente: cada objetivo se predice solo con los sorteos anteriores",
            "muestra": {"sorteos": len(ordenado), "objetivos_evaluados": len(objetivos),
                        "primer_objetivo": objetivos[0], "ultimo_objetivo": objetivos[-1],
                        "minimo_sorteos_de_entrenamiento": configuracion.minimo_sorteos_de_entrenamiento,
                        "minimo_objetivos_evaluados": configuracion.minimo_objetivos_evaluados},
            "bloques": bloques,
            "agregado": {"modelo": agregado_modelo, "referencia_uniforme": agregado_uniforme,
                         "comparacion": comun.comparar(agregado_modelo, agregado_uniforme, _PRINCIPALES)},
            "definiciones": "Log Loss y Brier sobre las 39 filas candidato-sorteo de cada objetivo (menor es mejor); "
                            "aciertos top-5 = 5 * Precision@5 con desempate por numero ascendente "
                            "(app/application/ml/metricas.py); referencia uniforme 5/39",
        },
        "pronostico": {
            "objetivo": corte + 1,
            "calculado_hasta_sorteo": corte,
            "numeros_sugeridos": sorted(ranking[:CANTIDAD]),
            "ranking": [{"numero": n, "probabilidad": comun.redondear(final[n], d),
                         "probabilidad_uniforme": comun.redondear(CANTIDAD / (hi - lo + 1), d)} for n in ranking],
            "nota": "probabilidad estimada de que cada numero aparezca en el objetivo; no es una garantia",
        },
        "superbalota": None,
        "contexto": comun.contexto(CODIGO_JUEGO),
    }
