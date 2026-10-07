"""FIXTURES SINTETICAS de Producto 3, solo para pruebas: operacion diaria
con repositorios en memoria, un importador falso (sin Internet) y un reloj
fijo. Ningun dato es un sorteo real."""
from __future__ import annotations

import contextlib
import dataclasses
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.application.ml import pronostico_colorloto as pc
from app.application.ml import pronostico_experimental as pe
from app.application.ml import pronostico_miloto as pm
from app.application.use_cases.operacion_diaria import DependenciasDeJuego, OperacionDiaria
from app.domain.entities.sincronizacion import EjecucionSincronizacion
from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego, RegistroEjecucionesArchivo
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
from tests.unit import fixtures_producto1 as fx

CONFIGS = {"BALOTO": pe.ConfiguracionExperimental(tamano_bloque=10, bloques_de_evaluacion=2,
                                                   minimo_objetivos_de_entrenamiento=40),
           "BALOTO_REVANCHA": pe.ConfiguracionExperimental(tamano_bloque=10, bloques_de_evaluacion=2,
                                                           minimo_objetivos_de_entrenamiento=40),
           "MILOTO": pm.ConfiguracionMiLoto(), "COLORLOTO": pc.ConfiguracionColorLoto()}
RELOJ = lambda: datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)  # noqa: E731


class Reloj:
    """Reloj que avanza un segundo en cada lectura (ordena los registros)."""

    def __init__(self, inicio=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)):
        self.ahora = inicio

    def __call__(self):
        self.ahora += timedelta(seconds=1)
        return self.ahora


class ImportadorFalso:
    """Sustituye a `SincronizarSorteos.ejecutar`: anade los sorteos
    preparados en `pendientes[codigo]` y devuelve un reporte con la misma
    entidad `EjecucionSincronizacion`. `fallar` simula un origen caido."""

    def __init__(self, entorno):
        self.entorno = entorno
        self.pendientes: dict[str, list] = {}
        self.fallar: dict[str, str] = {}
        self.llamadas: list[str] = []

    def __call__(self, codigo: str):
        self.llamadas.append(codigo)
        if codigo in self.fallar:
            raise ConnectionError(self.fallar[codigo])
        juego = self.entorno.juegos.obtener_por_codigo(codigo)
        nuevos = self.pendientes.pop(codigo, [])
        destino = self.entorno.resultados.colorloto if codigo == "COLORLOTO" else self.entorno.resultados.numericos
        destino[juego.id] = [*destino.get(juego.id, []), *nuevos]
        e = EjecucionSincronizacion(id=None, juego_id=juego.id, conector="Falso", iniciado_en=RELOJ(),
                                    estado="en_progreso")
        e.marcar_completada(sorteos_nuevos=len(nuevos), errores=[], duracion_ms=1,
                            ultimo_sorteo_importado=max((r.numero_sorteo for r in nuevos), default=None),
                            finalizado_en=RELOJ())
        return SimpleNamespace(ejecucion=e, advertencias_parseo=[])


@dataclasses.dataclass
class Entorno:
    juegos: object
    resultados: object
    colores: object
    almacen: PronosticoExperimentalFileStore
    historicos: dict
    directorio_operacion: object
    importador: ImportadorFalso = None
    abiertos: list = dataclasses.field(default_factory=list)
    base_caida: set = dataclasses.field(default_factory=set)

    @contextlib.contextmanager
    def abrir(self, codigo: str, modo: str):
        self.abiertos.append((codigo, modo))
        if codigo in self.base_caida:
            raise ConnectionError("connection to server failed: Connection refused")
        yield DependenciasDeJuego(self.juegos, self.resultados, self.importador if modo == "actualizar" else None)

    def operacion(self, reloj=None) -> OperacionDiaria:
        return OperacionDiaria(self.almacen, RegistroEjecucionesArchivo(self.directorio_operacion),
                               CerrojoPorJuego(self.directorio_operacion), self.abrir, reloj=reloj or Reloj(),
                               configuraciones=CONFIGS)

    def siguiente(self, codigo: str, numero_extra: int = 1):
        """Sorteo(s) sinteticos posteriores al ultimo cargado."""
        base = self.historicos[codigo][-1]
        salida = []
        for i in range(1, numero_extra + 1):
            fecha = base.fecha + timedelta(days=3 * i)
            if codigo == "COLORLOTO":
                salida.append(dataclasses.replace(base, numero_sorteo=base.numero_sorteo + i, fecha=fecha,
                                                  pares=((1, "ROJO"), (2, "AZUL"), (3, "VERDE"), (4, "ROJO"),
                                                         (5, "AMARILLO"), (6, "BLANCO"))))
            else:
                salida.append(dataclasses.replace(base, numero_sorteo=base.numero_sorteo + i, fecha=fecha,
                                                  numeros=(1, 2, 3, 4, 5)))
        return salida


def entorno(tmp_path, colorloto: int = 60, miloto: int = 84) -> Entorno:
    historicos = {"BALOTO": fx.historico_numerico("BALOTO", 130), "BALOTO_REVANCHA": fx.historico_numerico(
        "BALOTO_REVANCHA", 130), "MILOTO": fx.historico_numerico("MILOTO", miloto, primero=1)}
    color = fx.historico_colorloto(colorloto)
    juegos, resultados, colores = fx.repositorios(historicos, colorloto=color)
    e = Entorno(juegos, resultados, colores, PronosticoExperimentalFileStore(tmp_path / "pronosticos"),
                {**historicos, "COLORLOTO": color}, tmp_path / "operacion")
    e.importador = ImportadorFalso(e)
    return e


LOCAL = ("127.0.0.1", 50000)


def lanzar_ya(funcion, inicio):
    """Lanzador sincrono para pruebas: ejecuta en el mismo hilo."""
    funcion(inicio)


def cliente(e: Entorno, *, client=LOCAL, lanzador=lanzar_ya, conectada: bool = True, reloj=None):
    """TestClient con las dependencias de Productos 1-3 sustituidas por las
    del entorno sintetico (sin PostgreSQL, sin Internet)."""
    from app.api import dependencies as dep
    from app.application.use_cases.panel_diario import ConsultarPanelDiario
    from app.application.use_cases.rendimiento import ConsultarRendimiento
    from app.main import app

    c = fx.cliente(e.juegos, e.resultados, e.colores, e.almacen, conectada=conectada, reloj=f3_reloj(reloj),
                   configuraciones=CONFIGS, client=client)
    operacion = e.operacion(reloj)
    app.dependency_overrides.update({
        dep.get_operacion_diaria: lambda: operacion,
        dep.get_lanzador_de_operacion: lambda: lanzador,
        dep.get_consultar_panel: lambda: ConsultarPanelDiario(e.almacen, e.juegos, e.resultados, operacion,
                                                              hoy=lambda: RELOJ().date()),
        dep.get_consultar_rendimiento: lambda: ConsultarRendimiento(e.almacen, e.juegos, e.resultados),
    })
    return c


def f3_reloj(reloj):
    return reloj or RELOJ


def limpiar():
    from app.main import app
    app.dependency_overrides = {}
