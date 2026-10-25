"""API publica de la Fase 8 con datos SINTETICOS, para las pruebas de la Fase 9.1.

No es una prueba de PostgreSQL ni usa la base operativa. La aplicacion es la
real (`crear_app`), sin cambios; solo se sustituyen sus proveedores:
- juegos, sorteos, estadisticas y simulaciones: la base SQLite aislada de las
  fixtures de la Fase 7 (cuatro juegos, paleta e historicos generados con
  `random.Random`);
- predicciones guardadas: el centro de la Fase 4 sobre sus almacenes temporales
  y sus historicos sinteticos en memoria (no coinciden con los de la SQLite).

Escenario (todo sintetico): los cuatro juegos tienen una prediccion guardada;
la de MILOTO ya tiene su resultado observado (se anade el sorteo objetivo
despues de emitirla) y las demas siguen pendientes. BALOTO tiene una
simulacion, MILOTO dos y COLORLOTO dos, una de ellas alterada a proposito
(integridad `alterada`, 409 en su detalle); BALOTO_REVANCHA no tiene
simulaciones. Los historicos son antiguos: la frescura es `desactualizado`.

Uso como aplicacion de Uvicorn (`tests.fase9_api_sintetica:app`): lee la raiz
temporal de `F9_RAIZ` y la configuracion de `API_PUBLICA_CLAVES`,
`F9_FICHAS_POR_MINUTO` y `F9_FICHAS_POR_MINUTO_IP`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import text

ESCENARIO = "fase9-sintetico/1"
SIMULACIONES = {"BALOTO": 1, "MILOTO": 2, "COLORLOTO": 2}
MODELOS = {"BALOTO": "uniforme", "BALOTO_REVANCHA": "uniforme", "MILOTO": "uniforme", "COLORLOTO": "uniforme_paleta"}


def preparar(raiz: Path) -> dict:
    """Crea los datos sinteticos en `raiz` (vacia o inexistente) y devuelve los proveedores."""
    from tests.unit import fixtures_fase4 as f4
    from tests.unit.simulaciones import fixtures_fase7 as f7

    raiz.mkdir(parents=True, exist_ok=True)
    e7 = f7.entorno(raiz / "datos")
    e4 = f4.entorno(raiz / "f4")
    for juego, modelo in MODELOS.items():
        e4.configurar(juego, modelo)
        e4.centro().ahora(juego)
    e4.anadir("MILOTO", e4.siguiente("MILOTO"))  # el objetivo de MILOTO ya tiene resultado
    servicio = e7.servicio()
    for juego, cantidad in SIMULACIONES.items():
        for i in range(cantidad):
            servicio.ahora(juego, 100, 20261024 + i, origen="fase9_sintetico")
    with e7.engine.begin() as c:  # una simulacion de COLORLOTO alterada a proposito, como en las pruebas de Fase 7
        ident, resumen = c.execute(text(
            "SELECT s.id, s.resultado_resumen FROM simulaciones s JOIN juegos j ON j.id = s.juego_id "
            "WHERE j.codigo = 'COLORLOTO' ORDER BY s.ejecutado_en, s.id LIMIT 1")).one()
        resumen = json.loads(resumen) if isinstance(resumen, str) else resumen
        resumen["contenido"]["estadisticas"][0]["observado"]["valor"] = 0.0
        c.execute(text("UPDATE simulaciones SET resultado_resumen = :r WHERE id = :i"),
                  {"r": json.dumps(resumen), "i": ident})
    return {"e7": e7, "e4": e4, "alterada": ident}


def crear(raiz: Path, configuracion=None, *, preparada: dict | None = None):
    """La aplicacion publica real con los proveedores sinteticos de `raiz`."""
    from app.api.publica import aplicacion
    from app.api.publica import dependencias as d
    from app.api.publica.configuracion import ConfiguracionPublica, leer_claves

    datos = preparada or preparar(raiz)
    e7, e4 = datos["e7"], datos["e4"]
    if configuracion is None:
        configuracion = ConfiguracionPublica(
            claves=leer_claves(os.environ.get("API_PUBLICA_CLAVES", "")),
            fichas_por_minuto=int(os.environ.get("F9_FICHAS_POR_MINUTO", "60")),
            fichas_por_minuto_ip=int(os.environ.get("F9_FICHAS_POR_MINUTO_IP", "120")))
    app = aplicacion.crear_app(configuracion)

    def sesion():
        s = e7.sesiones()
        try:
            yield s
        finally:
            s.rollback()
            s.close()

    def estado_de_la_base():
        try:
            with e7.engine.connect() as c:
                c.execute(text("SELECT 1"))
            return "disponible"
        except Exception:  # noqa: BLE001 - mismo contrato que el proveedor real
            return "no_disponible"

    centro = e4.centro()
    app.dependency_overrides = {d.sesion_de_lectura: sesion, d.estado_de_la_base: estado_de_la_base,
                                d.simulaciones: lambda: e7.servicio(), d.centro_de_predicciones: lambda: centro}
    app.state.escenario_sintetico = ESCENARIO
    return app


def _desde_entorno():
    raiz = os.environ.get("F9_RAIZ")
    if not raiz:
        return None
    return crear(Path(raiz))


app = _desde_entorno()
