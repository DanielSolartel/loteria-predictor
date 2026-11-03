"""Backend de ENSAYO de E10.1 para el recorrido manual (Windows/Brave). No es el arranque operativo.

- Usa la aplicación real `app.main:app` con su límite local, su dependencia global y sus plantillas.
- El almacén de seguridad es el que indique `--directorio` (temporal, creado antes con la CLI y cuentas de
  prueba); se abre con los parámetros scrypt de producción.
- Servicios SUSTITUIDOS: base de datos, juegos, sorteos y colores en memoria; automatización con un servicio
  controlado que solo registra; lanzador que NO ejecuta (cero ciclos reales de Fase 6). No toca PostgreSQL,
  la tarea `LP6-01023009031fcabd`, los almacenes operativos ni las fuentes externas.
- Escucha solo en 127.0.0.1 y sin confiar en cabeceras de reenvío.

Uso, desde backend/:  python -m tests.ensayo_consola_e101 --directorio "<carpeta temporal>" [--puerto 8765]
"""
from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from pathlib import Path


class AutomatizacionDeEnsayo:
    """Solo registra las acciones; los datos del panel son sintéticos."""

    def __init__(self):
        self.acciones: list[str] = []
        self.datos = {
            "estado": "pausada", "configuracion": {"activada": False, "pausada": True},
            "juegos": [{"codigo": c, "estado": "ok", "ultimo_sorteo": n, "ultima_comprobacion": None,
                        "ultima_actualizacion": None, "proximo_evento": None, "proxima_consulta": None,
                        "configuracion_modelo": None, "ejecucion": None, "pasos": []}
                       for c, n in (("BALOTO", 1), ("BALOTO_REVANCHA", 1), ("MILOTO", 1), ("COLORLOTO", 1))],
            "ejecuciones": [], "avisos": [{"mensaje": "Backend de ensayo E10.1: servicios sustituidos."}], "revisiones": [],
        }

    def panel(self):
        return deepcopy(self.datos)

    def consultar_ejecucion(self, identificador):
        return None

    def _registrar(self, nombre):
        self.acciones.append(nombre)
        print(f"[ensayo] acción de automatización SUSTITUIDA registrada: {nombre}", flush=True)

    def pausar(self):
        self._registrar("pausar")

    def reanudar(self):
        self._registrar("reanudar")

    def recuperar(self):
        self._registrar("recuperar")


def preparar(directorio: Path):
    from app.api import dependencies as dep
    from app.api.automatizacion_dependencies import get_automatizacion, get_lanzador_automatizacion
    from app.application.use_cases.consultar_juegos import ListarJuegos
    from app.application.use_cases.gestionar_paleta_colores import GestionarPaletaColores
    from app.application.use_cases.obtener_resumen_sistema import ObtenerResumenSistema
    from app.infrastructure.db.session import get_db
    from app.main import app
    from app.seguridad_consola.almacen import AlmacenSeguridad, ruta_predeterminada
    from tests.unit import fixtures_producto1 as fx
    from tests.unit.fakes import FakeEstadisticaRepository, FakeSorteoRepository

    almacen = AlmacenSeguridad(ruta_predeterminada(directorio))
    almacen.comprobar()  # fallo cerrado también aquí: sin almacén válido no arranca el ensayo
    juegos, _resultados, colores = fx.repositorios()
    sorteos, estadisticas = FakeSorteoRepository(), FakeEstadisticaRepository()
    automatizacion = AutomatizacionDeEnsayo()

    def lanzador():
        def lanzar(funcion, *args):
            print(f"[ensayo] lanzamiento SUSTITUIDO (no se ejecuta): {getattr(funcion, '__name__', funcion)}", flush=True)
        return lanzar

    app.state.almacen_seguridad = almacen
    app.dependency_overrides.update({
        get_db: lambda: fx._SesionFalsa(True),
        dep.get_listar_juegos: lambda: ListarJuegos(juego_repository=juegos),
        dep.get_resumen_sistema: lambda: ObtenerResumenSistema(juego_repository=juegos, sorteo_repository=sorteos),
        dep.get_gestionar_paleta_colores: lambda: GestionarPaletaColores(color_repository=colores,
                                                                         estadistica_repository=estadisticas),
        get_automatizacion: lambda: automatizacion,
        get_lanzador_automatizacion: lanzador,
    })
    return app


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--directorio", required=True, help="Carpeta TEMPORAL del almacén de cuentas de prueba")
    p.add_argument("--puerto", type=int, default=8765)
    a = p.parse_args(argv)
    import uvicorn

    app = preparar(Path(a.directorio))
    print(f"[ensayo] consola de ensayo en http://127.0.0.1:{a.puerto}/ (servicios sustituidos)", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=a.puerto, proxy_headers=False, access_log=False, workers=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
