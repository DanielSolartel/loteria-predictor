"""
Caso de uso: EvaluarRobustezMLProbabilidadNumeros -Etapa AE-37,
validada.

Unico punto de union entre infraestructura (repositorios reales) y
el nucleo puro `application/ml/` para la evaluacion temporal anidada
de AE-37. Aplica el corte de desarrollo real
(`CORTE_DESARROLLO_AE37 = 2590`) exclusivamente en la consulta SQL
existente -nunca trae el historico completo para filtrarlo despues
en Python. Solo Baloto y Baloto Revancha estan autorizados, igual
que AE-36; MiLoto y ColorLoto se rechazan explicitamente antes de
consultar cualquier repositorio."""
from __future__ import annotations

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.exceptions import DominioError, JuegoNoEncontradoError
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.application.ml.evaluacion_anidada import SEMILLA_AE37, evaluar_bloques_externos
from app.application.ml.historico_util import validar_y_ordenar_historico
from app.application.ml.dataset import construir_dataset_binario
from app.application.ml.modelo import VERSION_SKLEARN
from app.application.ml.tipos import CorteDesarrollo, PoliticaProximoHoldout, ReporteRobustezJuego
from app.application.ml.evaluacion_anidada import CANDIDATOS_PREREGISTRADOS
from app.application.use_cases.evaluar_baseline_ml_probabilidad_numeros import JUEGOS_AUTORIZADOS_AE36
from app.application.use_cases.game_factory import GameFactory

CORTE_DESARROLLO_AE37 = 2590
"""Corte de desarrollo real de AE-37 -especifico de esta etapa y
estos datos, nunca una constante general del motor. El intervalo
`2591..2705` ya fue consumido como test final de AE-36 y esta
etapa lo excluye por completo de su ruta de ejecucion."""

HOLDOUT_CONSUMIDO_INICIO = 2591
HOLDOUT_CONSUMIDO_FIN = 2705
PROXIMO_HOLDOUT_INICIO = 2706
MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT = 100


class JuegoNoAutorizadoParaMLError(DominioError):
    """Etapa AE-37: mismo criterio exacto que AE-36 -MiLoto (NO-GO
    temporal) y ColorLoto (pospuesto) nunca deben entrar a este
    pipeline."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)


class ResultadoPosteriorAlCorteError(DominioError):
    """Fallo explicito -nunca silencioso- si el repositorio devuelve
    algun resultado con `numero_sorteo > CORTE_DESARROLLO_AE37`. El
    filtro ya se solicita en SQL (`hasta_numero_sorteo`), pero esta
    es una segunda capa defensiva: si por cualquier motivo llegara un
    resultado posterior, la ejecucion se detiene en vez de continuar
    con datos potencialmente contaminados."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)


class EvaluarRobustezMLProbabilidadNumeros:
    def __init__(
        self,
        juego_repository: JuegoRepository,
        resultados_historicos_repository: ResultadosHistoricosRepository,
        game_factory: GameFactory,
    ):
        self._juegos = juego_repository
        self._resultados = resultados_historicos_repository
        self._game_factory = game_factory

    def ejecutar(self, codigo_juego: str, semilla: int = SEMILLA_AE37) -> ReporteRobustezJuego:
        if codigo_juego not in JUEGOS_AUTORIZADOS_AE36:
            raise JuegoNoAutorizadoParaMLError(
                f"'{codigo_juego}' no esta autorizado para Machine Learning en AE-37 -"
                f"unicamente {sorted(JUEGOS_AUTORIZADOS_AE36)} recibieron GO en AE-35"
            )

        juego = self._juegos.obtener_por_codigo(codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(codigo_juego)

        juego_dominio = self._game_factory.crear(juego)
        rango_min, rango_max = juego_dominio.number_range
        cantidad_numeros = juego_dominio.numbers_to_pick

        historico: list[ResultadoNumerico] = self._resultados.listar_resultados_numericos(
            juego.id, hasta_numero_sorteo=CORTE_DESARROLLO_AE37,
        )

        for r in historico:
            if r.numero_sorteo > CORTE_DESARROLLO_AE37:
                raise ResultadoPosteriorAlCorteError(
                    f"El repositorio devolvio el sorteo {r.numero_sorteo} de {codigo_juego}, "
                    f"posterior al corte de desarrollo {CORTE_DESARROLLO_AE37} -ejecucion detenida"
                )

        historico_ordenado = validar_y_ordenar_historico(historico, codigo_juego)
        dataset = construir_dataset_binario(historico_ordenado, rango_min, rango_max, cantidad_numeros, codigo_juego)

        for f in dataset.filas:
            if f.sorteo_objetivo > CORTE_DESARROLLO_AE37:
                raise ResultadoPosteriorAlCorteError(
                    f"Una fila del dataset de {codigo_juego} tiene sorteo_objetivo {f.sorteo_objetivo}, "
                    f"posterior al corte de desarrollo {CORTE_DESARROLLO_AE37} -ejecucion detenida"
                )

        bloques_externos = evaluar_bloques_externos(dataset, historico_ordenado, semilla=semilla)

        for bloque in bloques_externos:
            if bloque.frontera_externa.bloque_externo_fin > CORTE_DESARROLLO_AE37:
                raise ResultadoPosteriorAlCorteError(
                    f"Un bloque externo de {codigo_juego} llega hasta el sorteo "
                    f"{bloque.frontera_externa.bloque_externo_fin}, posterior al corte {CORTE_DESARROLLO_AE37}"
                )

        corte_desarrollo = CorteDesarrollo(
            hasta_numero_sorteo=CORTE_DESARROLLO_AE37,
            sorteos_originales_recibidos=len(historico_ordenado),
            primer_sorteo=historico_ordenado[0].numero_sorteo if historico_ordenado else None,
            ultimo_sorteo=historico_ordenado[-1].numero_sorteo if historico_ordenado else None,
        )
        politica_holdout = PoliticaProximoHoldout(
            holdout_consumido_inicio=HOLDOUT_CONSUMIDO_INICIO,
            holdout_consumido_fin=HOLDOUT_CONSUMIDO_FIN,
            holdout_consumido_confirmado_no_utilizado=True,
            proximo_holdout_inicio=PROXIMO_HOLDOUT_INICIO,
            minimo_sorteos_nuevos_requeridos=MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT,
        )

        ganados = sum(1 for b in bloques_externos if b.diferencia_vs_uniforme.resultado == "gano")
        perdidos = sum(1 for b in bloques_externos if b.diferencia_vs_uniforme.resultado == "perdio")
        empatados = sum(1 for b in bloques_externos if b.diferencia_vs_uniforme.resultado == "empato")
        resumen = (
            f"Evaluacion exploratoria sobre {len(bloques_externos)} bloques externos: {ganados} bloques con "
            f"mejora frente al uniforme en ambas metricas principales, {perdidos} con peor desempeno, "
            f"{empatados} mixtos. Resultado exploratorio, no confirmatorio -no constituye evidencia de "
            f"capacidad predictiva ni autoriza ninguna recomendacion."
        )

        return ReporteRobustezJuego(
            codigo_juego=codigo_juego,
            corte_desarrollo=corte_desarrollo,
            total_sorteos_elegibles=len(dataset.sorteos_objetivo),
            total_filas=len(dataset.filas),
            rango_min=rango_min,
            rango_max=rango_max,
            cantidad_numeros=cantidad_numeros,
            candidatos_preregistrados=CANDIDATOS_PREREGISTRADOS,
            bloques_externos=bloques_externos,
            politica_proximo_holdout=politica_holdout,
            semilla=semilla,
            version_sklearn=VERSION_SKLEARN,
            resumen=resumen,
        )
