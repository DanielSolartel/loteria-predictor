"""FIXTURES SINTETICAS de Producto 1, solo para pruebas.

Historicos generados con `random.Random(semilla)` y reglas de cada juego;
no son sorteos reales ni deben usarse como tales. Incluye un repositorio
de resultados en memoria y la aplicacion FastAPI con sus dependencias
sustituidas por fakes (sin PostgreSQL)."""
from __future__ import annotations

import random
import uuid
from datetime import date, timedelta

from app.application.estadisticas.tipos import ResultadoColorLoto, ResultadoNumerico
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.domain.entities.juego import Juego
from app.domain.value_objects.color import Color
from tests.unit.fakes import FakeColorRepository, FakeJuegoRepository

COLORES = ("AMARILLO", "AZUL", "ROJO", "VERDE", "BLANCO", "NEGRO")
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")


def juego(codigo: str) -> Juego:
    reglas = {
        "BALOTO": ("Baloto", 1, 43, 5, True, 1, 16, False, False),
        "BALOTO_REVANCHA": ("Baloto Revancha", 1, 43, 5, True, 1, 16, False, False),
        "MILOTO": ("MiLoto", 1, 39, 5, False, None, None, False, False),
        "COLORLOTO": ("ColorLoto", 1, 7, 6, False, None, None, True, True),
    }[codigo]
    nombre, lo, hi, k, sb, slo, shi, color, rep = reglas
    return Juego(id=uuid.uuid5(uuid.NAMESPACE_DNS, codigo), codigo=codigo, nombre=nombre, rango_min=lo, rango_max=hi,
                 cantidad_numeros=k, tiene_superbalota=sb, superbalota_min=slo, superbalota_max=shi,
                 tiene_color=color, permite_repeticion=rep)


def _fecha(i: int, inicio: date) -> tuple[date, str]:
    f = inicio + timedelta(days=3 * i)
    return f, DIAS[f.weekday()]


def historico_numerico(codigo: str, n: int, *, primero: int = 2081, semilla: int = 1,
                       inicio: date = date(2021, 1, 2)) -> list[ResultadoNumerico]:
    j = juego(codigo)
    rng = random.Random(f"{codigo}-{semilla}")
    salida = []
    for i in range(n):
        fecha, dia = _fecha(i, inicio)
        numeros = tuple(sorted(rng.sample(range(j.rango_min, j.rango_max + 1), j.cantidad_numeros)))
        sb = rng.randint(j.superbalota_min, j.superbalota_max) if j.tiene_superbalota else None
        salida.append(ResultadoNumerico(primero + i, fecha, dia, numeros, sb))
    return salida


def historico_colorloto(n: int, *, primero: int = 1, semilla: int = 1,
                        inicio: date = date(2024, 8, 6)) -> list[ResultadoColorLoto]:
    rng = random.Random(f"COLORLOTO-{semilla}")
    salida = []
    for i in range(n):
        fecha, dia = _fecha(i, inicio)
        pares = tuple((rng.randint(1, 7), rng.choice(COLORES)) for _ in range(6))
        salida.append(ResultadoColorLoto(primero + i, fecha, dia, pares))
    return salida


class FakeResultadosRepository(ResultadosHistoricosRepository):
    """Filtra por `hasta_numero_sorteo` como la consulta SQL real."""

    def __init__(self, numericos: dict | None = None, colorloto: dict | None = None):
        self.numericos = numericos or {}
        self.colorloto = colorloto or {}
        self.consultas: list = []

    def listar_resultados_numericos(self, juego_id, hasta_numero_sorteo=None):
        self.consultas.append((juego_id, hasta_numero_sorteo))
        datos = sorted(self.numericos.get(juego_id, []), key=lambda r: r.numero_sorteo)
        return [r for r in datos if hasta_numero_sorteo is None or r.numero_sorteo <= hasta_numero_sorteo]

    def listar_resultados_colorloto(self, juego_id, hasta_numero_sorteo=None):
        datos = sorted(self.colorloto.get(juego_id, []), key=lambda r: r.numero_sorteo)
        return [r for r in datos if hasta_numero_sorteo is None or r.numero_sorteo <= hasta_numero_sorteo]


def repositorios(numericos: dict[str, list] | None = None, colorloto: list | None = None,
                 juegos=("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")):
    entidades = [juego(c) for c in juegos]
    por_codigo = {j.codigo: j for j in entidades}
    juegos_repo = FakeJuegoRepository(entidades)
    resultados = FakeResultadosRepository(
        {por_codigo[c].id: h for c, h in (numericos or {}).items()},
        {por_codigo["COLORLOTO"].id: colorloto} if colorloto is not None and "COLORLOTO" in por_codigo else {})
    colores = FakeColorRepository({por_codigo["COLORLOTO"].id: [Color(c, c.title()) for c in COLORES]}
                                  if "COLORLOTO" in por_codigo else {})
    return juegos_repo, resultados, colores


class _SesionFalsa:
    def __init__(self, conectada: bool = True):
        self.conectada = conectada

    def execute(self, *args, **kwargs):
        if not self.conectada:
            raise RuntimeError("sin base de datos")


def cliente(juegos_repo, resultados, colores, almacen, *, conectada: bool = True, reloj=None, configuracion=None,
            client=("testclient", 50000), configuraciones=None):
    """TestClient de la aplicacion real con las dependencias sustituidas."""
    from fastapi.testclient import TestClient

    from app.api import dependencies as dep
    from app.application.use_cases.consultar_resumen_juego import ConsultarResumenJuego
    from app.application.use_cases.pronostico_experimental import (
        CompararConResultadosObservados,
        ConsultarPronosticosExperimentales,
        GenerarPronosticoExperimental,
        VerificarPronosticoExperimental,
    )
    from app.infrastructure.db.session import get_db
    from app.main import app

    kwargs = {} if reloj is None else {"reloj": reloj}
    kwargs_reloj = dict(kwargs)
    if configuracion is not None:
        kwargs["configuracion"] = configuracion
    if configuraciones is not None:
        kwargs["configuraciones"] = configuraciones
    app.dependency_overrides = {
        get_db: lambda: _SesionFalsa(conectada),
        dep.get_consultar_resumen_juego: lambda: ConsultarResumenJuego(juegos_repo, resultados, colores),
        dep.get_consultar_pronosticos: lambda: ConsultarPronosticosExperimentales(almacen, juegos_repo, resultados,
                                                                                  **kwargs_reloj),
        dep.get_generar_pronostico: lambda: GenerarPronosticoExperimental(juegos_repo, resultados, almacen, **kwargs),
        dep.get_verificar_pronostico: lambda: VerificarPronosticoExperimental(juegos_repo, resultados, almacen),
        dep.get_comparar_resultados: lambda: CompararConResultadosObservados(almacen, juegos_repo, resultados),
    }
    return TestClient(app, base_url="http://localhost:8000", client=client)
