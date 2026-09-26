"""Caso de uso: SimularReferenciaAzarUniforme -Etapa AE-49, validada.

Orquesta la referencia Monte Carlo exploratoria de
`application/simulaciones/montecarlo_uniforme.py` para BALOTO y
BALOTO_REVANCHA, cada juego por separado y nunca mezclados:

  JuegoRepository + ResultadosHistoricosRepository (corte 2705 en SQL)
  -> verificacion estricta de 2081..2705 y de los parametros del juego
  -> huella de la entrada -> simulacion -> Bonferroni sobre 8 -> JSON

Solo lectura: no persiste nada (la tabla `simulaciones` no se toca).
La semilla y las iteraciones son las constantes fijadas de AE-49; se
pueden inyectar unicamente para las pruebas sinteticas. El resultado
es exploratorio sobre datos reutilizados y no modifica el NO-GO de
AE-39."""
from __future__ import annotations

from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.application.simulaciones.montecarlo_uniforme import (
    ITERACIONES_AE49,
    JUEGOS_AE49,
    RANGO_PRINCIPAL_AE49,
    SEMILLA_AE49,
    EntradaSimulacionInvalidaError,
    comparar_juego,
    construir_reporte,
    parametros_desde_dominio,
    semilla_por_juego,
    validar_iteraciones,
    verificar_rango_principal,
)
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame

_JUEGOS_DOMINIO = {"BALOTO": BalotoGame, "BALOTO_REVANCHA": BalotoRevanchaGame}


class SimularReferenciaAzarUniforme:
    def __init__(
        self,
        juego_repository: JuegoRepository,
        resultados_repository: ResultadosHistoricosRepository,
        *,
        semilla: int = SEMILLA_AE49,
        iteraciones: int = ITERACIONES_AE49,
    ):
        validar_iteraciones(iteraciones)
        self._juego_repository = juego_repository
        self._resultados_repository = resultados_repository
        self.semilla = semilla
        self.iteraciones = iteraciones

    def ejecutar(self, revision_alembic: str) -> dict:
        """Evalua ambos juegos antes de construir el reporte: un fallo en
        cualquiera de ellos se propaga sin reporte parcial."""
        resultados = []
        for codigo in JUEGOS_AE49:
            juego_dominio = _JUEGOS_DOMINIO[codigo]()
            juego = self._juego_repository.obtener_por_codigo(codigo)
            if juego is None:
                raise EntradaSimulacionInvalidaError(f"El juego '{codigo}' no existe en la base de datos")
            _verificar_parametros(juego, juego_dominio)
            historico = self._resultados_repository.listar_resultados_numericos(
                juego.id, hasta_numero_sorteo=RANGO_PRINCIPAL_AE49[1],
            )
            historico = verificar_rango_principal(historico, juego_dominio)
            resultados.append(comparar_juego(
                historico, parametros_desde_dominio(codigo, juego_dominio),
                semilla=semilla_por_juego(self.semilla, codigo), iteraciones=self.iteraciones,
            ))
        return construir_reporte(revision_alembic, resultados, semilla=self.semilla, iteraciones=self.iteraciones)


def _verificar_parametros(juego, juego_dominio) -> None:
    """Los parametros registrados en BD deben coincidir con el dominio,
    que es la fuente de verdad del mecanismo de sorteo simulado."""
    esperado = (
        juego_dominio.number_range, juego_dominio.numbers_to_pick, juego_dominio.has_superballot,
        juego_dominio.superballot_range,
    )
    registrado = (
        (juego.rango_min, juego.rango_max), juego.cantidad_numeros, juego.tiene_superbalota,
        (juego.superbalota_min, juego.superbalota_max),
    )
    if registrado != esperado:
        raise EntradaSimulacionInvalidaError(
            f"Los parametros de '{juego.codigo}' en la base de datos no coinciden con el dominio"
        )
