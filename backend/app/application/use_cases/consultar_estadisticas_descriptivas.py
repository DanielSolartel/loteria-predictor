"""
Caso de uso: estadísticas descriptivas de la Fase 5 (métricas nuevas y panel unificado por juego).

Solo lectura: lee el histórico con `ResultadosHistoricosRepository` (una consulta por juego, sin corte,
y aplica el corte en memoria) y calcula en memoria con `app.application.estadisticas.descriptivas`.
No escribe la caché `estadisticas` ni nada en la base: el resultado depende solo del histórico y del
corte, y recalcularlo cuesta milisegundos.

Antes de calcular valida la integridad de la muestra cortada con los mismos validadores que las
recetas existentes (cantidad, duplicados, rango, superbalota y colores vigentes en la fecha); un
histórico inconsistente rechaza el cálculo completo (`ResultadoHistoricoInconsistenteError`), nunca
se descartan sorteos en silencio.

Las reglas salen del dominio (`GameFactory`, `ColorLotoGame`) y la paleta de ColorLoto de la tabla
`colores`: la de la muestra si fue la misma en todos sus sorteos, y si cambió, la vigente hoy más los
colores observados fuera de ella (`paleta_estable=False`).
"""
from __future__ import annotations

from datetime import date

from app.application.estadisticas.descriptivas import ReglasJuego, construir_metrica, construir_panel
from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.resumen_juego import _cabecera
from app.application.exceptions import JuegoNoEncontradoError
from app.application.interfaces.color_repository import ColorRepository
from app.application.interfaces.juego_repository import JuegoRepository
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.application.use_cases.calcular_y_persistir_estadistica import (
    _validar_historico_colorloto_consistente,
    _validar_historico_consistente,
    _validar_historico_superbalota_consistente,
)
from app.application.use_cases.game_factory import GameFactory
from app.domain.games.colorloto import BALLS_TO_PICK, NUMBER_RANGE


class ConsultarEstadisticasDescriptivas:
    def __init__(self, juego_repository: JuegoRepository, resultados_repository: ResultadosHistoricosRepository,
                 color_repository: ColorRepository):
        self._juegos = juego_repository
        self._resultados = resultados_repository
        self._colores = color_repository

    def reglas(self, codigo_juego: str) -> ReglasJuego:
        """Reglas del juego sin leer el histórico (para decidir qué métricas aplican)."""
        juego = self._juego(codigo_juego)
        return self._reglas(juego, [])

    def metrica(self, codigo_juego: str, slug: str, *, hoy: date, hasta_numero_sorteo: int | None = None,
                parametros: dict | None = None) -> dict:
        juego, reglas, todos, muestra = self._cargar(codigo_juego, hasta_numero_sorteo)
        return {"juego": self._juego_dict(juego, reglas),
                "muestra": self._muestra(juego, reglas, todos, muestra, hasta_numero_sorteo, hoy),
                "metrica": construir_metrica(slug, reglas, muestra, parametros)}

    def panel(self, codigo_juego: str, *, hoy: date, hasta_numero_sorteo: int | None = None) -> dict:
        juego, reglas, todos, muestra = self._cargar(codigo_juego, hasta_numero_sorteo)
        return {"juego": self._juego_dict(juego, reglas),
                "muestra": self._muestra(juego, reglas, todos, muestra, hasta_numero_sorteo, hoy),
                "grupos": construir_panel(reglas, muestra)}

    # ------------------------------------------------------------------

    def _juego(self, codigo_juego: str):
        juego = self._juegos.obtener_por_codigo(codigo_juego)
        if juego is None:
            raise JuegoNoEncontradoError(codigo_juego)
        return juego

    def _cargar(self, codigo_juego: str, hasta_numero_sorteo: int | None):
        juego = self._juego(codigo_juego)
        if codigo_juego == "COLORLOTO":
            todos = sorted(self._resultados.listar_resultados_colorloto(juego.id), key=lambda r: r.numero_sorteo)
            muestra = filtrar_por_corte_temporal(todos, hasta_numero_sorteo)
            _validar_historico_colorloto_consistente(muestra, self._colores.listar_todos(juego.id), BALLS_TO_PICK,
                                                     NUMBER_RANGE[0], NUMBER_RANGE[1])
        else:
            todos = sorted(self._resultados.listar_resultados_numericos(juego.id), key=lambda r: r.numero_sorteo)
            muestra = filtrar_por_corte_temporal(todos, hasta_numero_sorteo)
        reglas = self._reglas(juego, muestra)
        if not reglas.es_colorloto:
            _validar_historico_consistente(muestra, reglas.cantidad, rango_min=reglas.rango[0], rango_max=reglas.rango[1])
            if reglas.superbalota is not None:
                _validar_historico_superbalota_consistente(muestra, *reglas.superbalota)
        return juego, reglas, todos, muestra

    def _reglas(self, juego, muestra) -> ReglasJuego:
        if juego.codigo == "COLORLOTO":
            vigentes = [c.codigo for c in self._colores.listar_vigentes(juego.id)]
            catalogo = self._colores.listar_todos(juego.id)
            paletas = {frozenset(c.codigo for c in catalogo if c.esta_vigente_en(r.fecha)) for r in muestra}
            if len(paletas) == 1:
                paleta, estable = sorted(next(iter(paletas))), True
            else:  # sin sorteos (paleta vigente hoy) o paleta cambiante dentro de la muestra
                usados = sorted({c for r in muestra for _, c in r.pares})
                paleta, estable = vigentes + [c for c in usados if c not in vigentes], len(paletas) == 0
            return ReglasJuego(codigo="COLORLOTO", nombre=juego.nombre, tipo="colorloto", rango=tuple(NUMBER_RANGE),
                               cantidad=BALLS_TO_PICK, colores=tuple(paleta), paleta_estable=estable)
        dominio = GameFactory(self._colores).crear(juego)
        return ReglasJuego(codigo=juego.codigo, nombre=juego.nombre, tipo="numeros", rango=tuple(dominio.number_range),
                           cantidad=dominio.numbers_to_pick,
                           superbalota=tuple(dominio.superballot_range) if dominio.has_superballot else None)

    @staticmethod
    def _juego_dict(juego, reglas: ReglasJuego) -> dict:
        return {"codigo": juego.codigo, "nombre": juego.nombre, "tipo": reglas.tipo, "rango": list(reglas.rango),
                "cantidad": reglas.cantidad, "superbalota": list(reglas.superbalota) if reglas.superbalota else None,
                "colores": list(reglas.colores), "paleta_estable": reglas.paleta_estable}

    @staticmethod
    def _muestra(juego, reglas: ReglasJuego, todos, muestra, hasta_numero_sorteo, hoy) -> dict:
        reglas_cabecera = ({"tipo": "colorloto", "rango": list(reglas.rango), "cantidad_balotas": reglas.cantidad,
                            "colores": list(reglas.colores), "permite_repeticion": True} if reglas.es_colorloto else
                           {"tipo": "numeros", "rango": list(reglas.rango), "cantidad_numeros": reglas.cantidad,
                            "superbalota": list(reglas.superbalota) if reglas.superbalota else None})
        return _cabecera(juego.codigo, juego.nombre, reglas_cabecera, todos, muestra, hasta_numero_sorteo, hoy)
