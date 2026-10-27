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

Fase 9.3 (explicacion, clasificacion de candidatos y fiabilidad):
- BALOTO usa una version registrada sintetica (bosque aleatorio, perfil
  reducido, entrenada con corte 5 sorteos antes del ultimo): su explicacion
  tiene importancias disponibles y cortes de entrada y de entrenamiento
  distintos. Tiene tres carteras con cortes consecutivos: las dos primeras con
  su resultado observado y la ultima (la de la consulta sin `cartera`)
  pendiente;
- BALOTO_REVANCHA se genera solo con Producto 5: su cartera no tiene
  explicacion guardada;
- la fiabilidad lee Producto 6 con series SINTETICAS anadidas
  (`ResultadosConSeries`) a las lineas de la configuracion de BALOTO (vector
  fuente sobreconfiado frente a resultados uniformes: mayor perdida; y una
  retrospectiva corta: muestra insuficiente), de su version registrada
  (modelo informativo con resultados de su propia distribucion: menor perdida
  en esa muestra, con y sin intervalo que cruza 0) y de COLORLOTO (pares
  uniformes: diferencia exactamente 0). MILOTO y BALOTO_REVANCHA solo tienen
  sus emisiones reales.

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
MODELOS = {"BALOTO": "random_forest_clasificador", "BALOTO_REVANCHA": "uniforme", "MILOTO": "uniforme",
           "COLORLOTO": "uniforme_paleta"}
CARTERAS_BALOTO = 3


class ResultadosConSeries:
    """Producto 6 SINTETICO para la fiabilidad: las emisiones reales del centro de
    resultados mas `series[juego]`, filas con la forma de Producto 6 construidas
    con sus propias funciones (`congelado_de_fuente`, `metricas_de_congelado`).
    Solo cambia `emisiones`; el resto se delega sin cambios."""

    def __init__(self, real, series: dict[str, list[dict]]):
        self._real, self._series = real, series

    def emisiones(self, juego: str) -> dict:
        datos = self._real.emisiones(juego)
        return {**datos, "filas": [*datos["filas"], *self._series.get(juego, [])]}

    def __getattr__(self, nombre):
        return getattr(self._real, nombre)


def _fila(juego: str, clave_linea: str, objetivo: int, fuente: dict, resultado: dict, tipo: str,
          estado: str = "incluido", motivo: str | None = None) -> dict:
    from app.application.ml import resultados_procedencias as rp

    congelado = rp.congelado_de_fuente(juego, fuente)
    metricas, superbalota = rp.metricas_de_congelado(juego, objetivo, congelado, resultado)
    if estado != "incluido":
        metricas = superbalota = resultado = None
    return {"clave_linea": clave_linea, "tipo": tipo, "estado": estado, "motivo": motivo, "objetivo": objetivo,
            "congelado": congelado, "resultado": resultado, "metricas": metricas, "superbalota": superbalota}


def series_sinteticas(centro) -> dict[str, list[dict]]:
    """Series deterministas (generador con semilla fija) en las lineas de la configuracion."""
    import numpy as np

    from app.application.ml import resultados_procedencias as rp
    from app.application.use_cases.predicciones import linea_de_modelo

    rng = np.random.default_rng(20261027)
    numeros, superbalotas = list(range(1, 44)), list(range(1, 17))
    sobreconfiado = [0.3] * 10 + [2 / 33] * 33
    informativo = [0.25] * 10 + [2.5 / 33] * 33
    leve = [5 / 43 * 1.15] * 10 + [(5 - 10 * 5 / 43 * 1.15) / 33] * 33
    sesgada = [0.2, 0.2] + [0.6 / 14] * 14

    def sorteo(p=None):
        pesos = None if p is None else np.asarray(p) / sum(p)
        return sorted(int(x) for x in rng.choice(numeros, 5, replace=False, p=pesos))

    def fuente(p, sb):
        return {"candidatos": numeros, "probabilidades": p, "masa": 5,
                "superbalota": {"candidatos": superbalotas, "probabilidades": sb}}

    conf = centro._configuracion("BALOTO")["artefacto"]
    registrado = centro._registrado(conf)
    carteras = rp.clave_de_linea("carteras", linea_de_modelo(conf))
    laboratorio = rp.clave_de_linea("laboratorio", registrado["linea_de_laboratorio"])
    baloto = [_fila("BALOTO", carteras, 2121 + k, fuente(sobreconfiado, sesgada),
                    {"numeros": sorteo(), "superbalota": int(rng.integers(1, 17))}, "seguimiento") for k in range(40)]
    baloto += [_fila("BALOTO", carteras, 2161 + k, fuente(sobreconfiado, sesgada), {"numeros": sorteo()}, "seguimiento",
                     "excluido", "vectores_fuente_distintos_en_el_objetivo") for k in range(2)]
    baloto += [_fila("BALOTO", carteras, 2151 + k, fuente(sobreconfiado, [1 / 16] * 16),
                     {"numeros": sorteo(), "superbalota": int(rng.integers(1, 17))}, "retrospectiva") for k in range(12)]
    baloto += [_fila("BALOTO", laboratorio, 2121 + k, fuente(informativo, [1 / 16] * 16),
                     {"numeros": sorteo(informativo), "superbalota": int(rng.integers(1, 17))}, "seguimiento")
               for k in range(36)]
    baloto += [_fila("BALOTO", laboratorio, 2131 + k, fuente(leve, [1 / 16] * 16),
                     {"numeros": sorteo(leve if rng.random() < 0.5 else None), "superbalota": int(rng.integers(1, 17))},
                     "retrospectiva") for k in range(36)]
    prediccion = centro.consultar("COLORLOTO")["prediccion"]  # pares de la paleta de su corte
    pares = sorted(tuple(f["candidato"]) for f in prediccion["rankings"]["pares"]["todos"])
    uniforme = {"candidatos": [list(p) for p in pares], "probabilidades": [1 / len(pares)] * len(pares)}
    linea_colores = rp.clave_de_linea("carteras", linea_de_modelo(centro._configuracion("COLORLOTO")["artefacto"]))
    colorloto = [_fila("COLORLOTO", linea_colores, prediccion["datos"]["corte"] - 40 + k, uniforme,
                       {"pares": [list(pares[int(i)]) for i in rng.integers(0, len(pares), size=6)]}, "seguimiento")
                 for k in range(31)]
    return {"BALOTO": baloto, "COLORLOTO": colorloto}


def preparar(raiz: Path) -> dict:
    """Crea los datos sinteticos en `raiz` (vacia o inexistente) y devuelve los proveedores."""
    from tests.unit import fixtures_fase4 as f4
    from tests.unit.simulaciones import fixtures_fase7 as f7

    raiz.mkdir(parents=True, exist_ok=True)
    e7 = f7.entorno(raiz / "datos")
    e4 = f4.entorno(raiz / "f4")
    registrado = e4.registrar(e4.laboratorio(), "BALOTO", MODELOS["BALOTO"])
    e4.configurar("BALOTO", MODELOS["BALOTO"], registrado=registrado["modelo_registrado"])
    for k in range(CARTERAS_BALOTO):  # cortes consecutivos; la ultima queda pendiente
        e4.centro().ahora("BALOTO")
        if k < CARTERAS_BALOTO - 1:
            e4.anadir("BALOTO", e4.siguiente("BALOTO", semilla=400 + k))
    e4.configurar("BALOTO_REVANCHA", MODELOS["BALOTO_REVANCHA"])
    e4.carteras().ahora("carteras_configuradas", ["BALOTO_REVANCHA"])  # cartera sin explicacion guardada
    for juego in ("MILOTO", "COLORLOTO"):
        e4.configurar(juego, MODELOS[juego])
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
    return {"e7": e7, "e4": e4, "alterada": ident, "series": series_sinteticas(e4.centro())}


def centro_sintetico(datos: dict):
    """Centro de predicciones real de la Fase 4 sobre los almacenes de `datos`, con Producto 6 sintetico."""
    centro = datos["e4"].centro()
    centro._resultados = ResultadosConSeries(centro._resultados, datos["series"])
    return centro


def crear(raiz: Path, configuracion=None, *, preparada: dict | None = None):
    """La aplicacion publica real con los proveedores sinteticos de `raiz`."""
    from app.api.publica import aplicacion
    from app.api.publica import dependencias as d
    from app.api.publica.configuracion import ConfiguracionPublica, leer_claves

    datos = preparada or preparar(raiz)
    e7 = datos["e7"]
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

    centro = centro_sintetico(datos)
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
