"""Fase 7: caso de uso comun `SimulacionesFase7` (SQLite aislado, ejecutor en el
mismo proceso salvo donde se indica). Publicacion transaccional, reutilizacion,
corte, duplicados y carreras, fallos, cerrojos, progreso, recuperacion,
verificacion y ausencia de escrituras en las lecturas."""
from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from dataclasses import replace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.application.fase7 import motor as fm
from app.application.interfaces.ejecutor_simulaciones import TiempoAgotadoError, TrabajadorFallidoError
from app.application.use_cases.operacion_diaria import EjecucionActivaError
from app.application.use_cases.simulaciones import EjecutorSimulacionesEnEsteProceso, SimulacionesError
from tests.unit.simulaciones import fixtures_fase7 as f7


class EjecutorContado(EjecutorSimulacionesEnEsteProceso):
    def __init__(self, lote=None, antes=None):
        super().__init__(lote)
        self.llamadas = 0
        self.antes = antes

    def simular(self, *a, **k):
        self.llamadas += 1
        if self.antes is not None:
            self.antes()
        return super().simular(*a, **k)


class EjecutorQueFalla:
    def __init__(self, error):
        self.error = error

    def simular(self, *a, **k):
        raise self.error


def _arbol(raiz):
    return {str(p.relative_to(raiz)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(raiz.rglob("*")) if p.is_file() and p.suffix != ".sqlite"}


def _juego(e, ejecucion, juego="MILOTO"):
    return ejecucion["juegos"][juego]


# ---------------------------------------------------------------------------
# Flujo principal y reutilizacion
# ---------------------------------------------------------------------------

def test_simular_publica_una_fila_completa_y_la_misma_entrada_la_reutiliza(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    ejecutor = EjecutorContado()
    s = e.servicio(ejecutor)
    final = s.ahora("MILOTO", 1_000, 5)
    r = _juego(e, final)
    assert final["estado"] == "exito" and r["estado"] == "terminado" and r["corte"] == e.historicos["MILOTO"][-1].numero_sorteo
    filas = e.filas()
    assert len(filas) == 1 and str(filas[0]["id"]) == r["resultado"] and filas[0]["parametros"]["clave"] == r["clave"]
    fila = s.obtener(r["resultado"])
    assert fila["integridad"] == "verificada" and fila["num_iteraciones"] == 1_000
    assert fila["resultado_resumen"]["ejecucion"]["ejecucion"] == final["id"]
    otra = s.ahora("MILOTO", 1_000, 5)
    assert _juego(e, otra)["estado"] == "reutilizado" and _juego(e, otra)["resultado"] == r["resultado"]
    assert ejecutor.llamadas == 1 and len(e.filas()) == 1
    assert s.consultar_ejecucion(final["id"])["estado"] == "exito"
    # el registro de progreso no es fuente del resultado: sin el, la fila sigue disponible y verificada
    for p in e.operacion.rglob("*.json"):
        p.unlink()
    assert s.obtener(r["resultado"])["integridad"] == "verificada" and len(s.listar("MILOTO")) == 1


@pytest.mark.parametrize("juego", f7.JUEGOS)
def test_los_cuatro_juegos_con_sus_reglas(tmp_path, juego):
    e = f7.entorno(tmp_path, cargar=(juego,))
    final = e.servicio().ahora(juego, 100, 1)
    r = final["juegos"][juego]
    assert r["estado"] == "terminado", r
    fila = e.servicio().obtener(r["resultado"])
    p = fila["parametros"]
    assert p["juego"] == juego and [x["nombre"] for x in p["estadisticas"]] == [d.nombre for d in fm.familia(juego)]
    if juego == "COLORLOTO":
        assert p["reglas"]["pares_numero_color_con_multiplicidad"] is True and len(p["reglas"]["paleta"]) == 6
    else:
        assert p["reglas"]["superbalota"] == ([1, 16] if juego.startswith("BALOTO") else None)
    assert fila["resultado_resumen"]["contenido"]["familia"]["umbral_alcanzable"] is False  # B = 100


def test_el_lote_no_cambia_contenido_ni_identidad_solo_los_metadatos(tmp_path):
    a = f7.entorno(tmp_path / "a", cargar=("BALOTO",))
    b = f7.entorno(tmp_path / "b", cargar=("BALOTO",))
    fa_ = a.servicio(EjecutorContado(lote=7)).ahora("BALOTO", 1_000, 3)
    fb_ = b.servicio(EjecutorContado(lote=None)).ahora("BALOTO", 1_000, 3)
    ra, rb = a.filas()[0], b.filas()[0]
    assert ra["parametros"] == rb["parametros"]
    assert ra["resultado_resumen"]["contenido_sha256"] == rb["resultado_resumen"]["contenido_sha256"]
    assert ra["resultado_resumen"]["ejecucion"]["lote"] == 7 != rb["resultado_resumen"]["ejecucion"]["lote"]
    assert ra["resultado_resumen"]["integridad_sha256"] != rb["resultado_resumen"]["integridad_sha256"]
    assert _juego(a, fa_, "BALOTO")["clave"] == _juego(b, fb_, "BALOTO")["clave"]


# ---------------------------------------------------------------------------
# Corte
# ---------------------------------------------------------------------------

def test_corte_aislado_los_sorteos_posteriores_no_cambian_nada(tmp_path):
    e = f7.entorno(tmp_path, {"BALOTO": 60}, cargar=())
    e.agregar("BALOTO", e.historicos["BALOTO"][:40])
    s = e.servicio(EjecutorContado())
    corte = e.historicos["BALOTO"][29].numero_sorteo
    primera = _juego(e, s.ahora("BALOTO", 100, 1, corte), "BALOTO")
    assert primera["estado"] == "terminado" and primera["corte"] == corte and primera["sorteos"] == 30
    e.agregar("BALOTO", e.historicos["BALOTO"][40:])  # llegan sorteos despues del corte
    otra = _juego(e, s.ahora("BALOTO", 100, 1, corte), "BALOTO")
    assert otra["estado"] == "reutilizado" and otra["clave"] == primera["clave"]
    sin_corte = _juego(e, s.ahora("BALOTO", 100, 1), "BALOTO")
    assert sin_corte["corte"] == e.historicos["BALOTO"][-1].numero_sorteo and sin_corte["clave"] != primera["clave"]
    p = s.obtener(primera["resultado"])["parametros"]
    assert p["historico"]["ultimo_sorteo"] == corte and p["historico"]["sorteos"] == 30


def test_corte_que_no_es_un_sorteo_cargado(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    s = e.servicio()
    ultimo = e.historicos["MILOTO"][-1].numero_sorteo
    for corte in (ultimo + 5, e.historicos["MILOTO"][0].numero_sorteo - 1):
        r = _juego(e, s.ahora("MILOTO", 100, 1, corte))
        assert r["estado"] in ("no_valido", "muestra_insuficiente") and r["resultado"] is None
    assert e.filas() == []
    for malo in (0, -3, True, "12"):
        with pytest.raises(SimulacionesError) as error:
            s.iniciar("MILOTO", 100, 1, malo)
        assert error.value.codigo == "no_valido"


# ---------------------------------------------------------------------------
# Limites y fallos explicitos
# ---------------------------------------------------------------------------

def test_parametros_no_validos_se_rechazan_antes_de_registrar(tmp_path):
    e = f7.entorno(tmp_path, cargar=())
    s = e.servicio()
    for juego, iteraciones, semilla in (("MILOTO", 5_000, 1), ("MILOTO", 100, -1), ("QUINELA", 100, 1)):
        with pytest.raises(SimulacionesError) as error:
            s.iniciar(juego, iteraciones, semilla)
        assert error.value.codigo == "no_valido"
    assert s.recientes() == []


def test_muestra_insuficiente_e_historico_vacio(tmp_path):
    e = f7.entorno(tmp_path, cargar=())
    e.agregar("MILOTO", e.historicos["MILOTO"][:1])
    s = e.servicio()
    assert _juego(e, s.ahora("MILOTO", 100, 1))["estado"] == "muestra_insuficiente"
    assert _juego(e, s.ahora("COLORLOTO", 100, 1), "COLORLOTO")["estado"] == "muestra_insuficiente"
    assert e.filas() == []


def test_base_no_disponible(tmp_path):
    e = f7.entorno(tmp_path, cargar=())

    @contextmanager
    def caida():
        raise OperationalError("SELECT 1", {}, Exception("could not connect to server"))
        yield

    s = e.servicio(abrir_lectura=caida)
    r = _juego(e, s.ahora("MILOTO", 100, 1))
    assert r["estado"] == "base_no_disponible" and "conexion" in r["mensaje"].lower()
    assert s.diagnostico("MILOTO")["estado"] == "base_no_disponible"
    for leer in (lambda: s.listar(), lambda: s.obtener("00000000-0000-0000-0000-000000000000"),
                 lambda: s.verificar("00000000-0000-0000-0000-000000000000")):
        with pytest.raises(SimulacionesError) as error:
            leer()
        assert error.value.codigo == "base_no_disponible"


def test_relectura_fallida_tras_publicar_no_oculta_la_publicacion(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    s = e.servicio()

    def caida(_identificador):
        raise SimulacionesError("base_no_disponible", "Sin conexion con la base de datos.")
    s._fila = caida
    r = _juego(e, s.ahora("MILOTO", 100, 1))
    assert r["estado"] == "terminado" and "no se pudo releer" in r["mensaje"] and len(e.filas()) == 1
    assert e.servicio().obtener(r["resultado"])["integridad"] == "verificada"


@pytest.mark.parametrize("error,estado", [(TiempoAgotadoError("supero el tiempo maximo"), "tiempo_agotado"),
                                          (TrabajadorFallidoError("termino sin resultado"), "fallo"),
                                          (RuntimeError("inesperado"), "fallo")])
def test_fallos_del_trabajador_son_explicitos_y_no_publican(tmp_path, error, estado):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    s = e.servicio(EjecutorQueFalla(error))
    final = s.ahora("MILOTO", 100, 1)
    r = _juego(e, final)
    assert final["estado"] == "fallo" and r["estado"] == estado and r["mensaje"] and r["resultado"] is None
    assert e.filas() == []
    assert _juego(e, e.servicio().ahora("MILOTO", 100, 1))["estado"] == "terminado"  # cerrojo liberado


def test_un_trabajador_que_devuelve_otro_historico_no_publica(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))

    class Tramposo(EjecutorSimulacionesEnEsteProceso):
        def simular(self, juego, sorteos, *a, **k):
            return super().simular(juego, sorteos[:-1], *a, **k)

    r = _juego(e, e.servicio(Tramposo()).ahora("MILOTO", 100, 1))
    assert r["estado"] == "fallo" and "distinto" in r["mensaje"] and e.filas() == []


# ---------------------------------------------------------------------------
# Integridad, duplicados y carreras
# ---------------------------------------------------------------------------

def _alterar(e, sql):
    with e.engine.begin() as c:
        c.execute(text(sql))


def test_fila_alterada_no_se_sobrescribe_ni_se_sirve(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    s = e.servicio(EjecutorContado())
    r = _juego(e, s.ahora("MILOTO", 100, 1))
    fila = e.filas()[0]
    resumen = json.loads(json.dumps(fila["resultado_resumen"]))
    resumen["contenido"]["estadisticas"][0]["observado"]["valor"] = 0.0
    with e.engine.begin() as c:
        c.execute(text("UPDATE simulaciones SET resultado_resumen = :r"), {"r": json.dumps(resumen)})
    with pytest.raises(SimulacionesError) as error:
        s.obtener(r["resultado"])
    assert error.value.codigo == "alterado"
    assert s.listar("MILOTO")[0]["integridad"] == "alterada"
    otra = _juego(e, s.ahora("MILOTO", 100, 1))
    assert otra["estado"] == "alterado" and "No se sobrescribe" in otra["mensaje"]
    assert len(e.filas()) == 1 and s._ejecutor.llamadas == 1
    for exportar in (s.exportar_csv, s.exportar_json):
        with pytest.raises(SimulacionesError):
            exportar(r["resultado"])


def test_fila_de_otro_juego_se_detecta(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    s = e.servicio()
    r = _juego(e, s.ahora("MILOTO", 100, 1))
    with e.sesiones() as ses:
        otro = ses.execute(text("SELECT id FROM juegos WHERE codigo = 'BALOTO'")).scalar_one()
    _alterar(e, f"UPDATE simulaciones SET juego_id = '{otro}'")
    with pytest.raises(SimulacionesError, match="juego"):
        s.obtener(r["resultado"])


def test_duplicados_externos_identicos_se_reutilizan_y_distintos_se_rechazan(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    s = e.servicio(EjecutorContado())
    r = _juego(e, s.ahora("MILOTO", 100, 1))
    with e.engine.begin() as c:  # copia externa identica, publicada despues (id nuevo, hora posterior)
        c.execute(text("INSERT INTO simulaciones (id, juego_id, num_iteraciones, parametros, resultado_resumen, "
                       "ejecutado_en, duracion_ms) SELECT :id, juego_id, num_iteraciones, parametros, "
                       "resultado_resumen, datetime(ejecutado_en, '+1 day'), duracion_ms FROM simulaciones"),
                  {"id": uuid.uuid4().hex})
    assert len(e.filas()) == 2
    otra = _juego(e, s.ahora("MILOTO", 100, 1))
    assert otra["estado"] == "reutilizado" and otra["resultado"] == r["resultado"]  # la mas antigua
    fila = e.filas()[1]
    resumen = fila["resultado_resumen"]
    resumen["contenido"]["nota"] = "otra"
    resumen["contenido_sha256"] = fm_sha(resumen["contenido"])
    cuerpo = {k: v for k, v in resumen.items() if k != "integridad_sha256"}
    resumen["integridad_sha256"] = fm_sha({"parametros": fila["parametros"], "resultado": cuerpo})
    with e.engine.begin() as c:
        c.execute(text("UPDATE simulaciones SET resultado_resumen = :r WHERE id = :i"),
                  {"r": json.dumps(resumen), "i": fila["id"].hex})
    tercera = _juego(e, s.ahora("MILOTO", 100, 1))
    assert tercera["estado"] == "alterado" and "duplicadas" in tercera["mensaje"]
    assert s._ejecutor.llamadas == 1


def fm_sha(valor):
    from app.application.fase7 import artefacto as fa

    return fa.sha256(valor)


def test_carrera_otra_ejecucion_publica_antes_y_se_conserva_su_fila(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    rival = e.servicio()
    rival._cerrojo = type(rival._cerrojo)(tmp_path / "rival")  # otro proceso con otra carpeta de cerrojos
    rival._registro = type(rival._registro)(tmp_path / "rival")
    publicadas = []
    s = e.servicio(EjecutorContado(antes=lambda: publicadas.append(rival.ahora("MILOTO", 100, 1))))
    r = _juego(e, s.ahora("MILOTO", 100, 1))
    ganador = publicadas[0]["juegos"]["MILOTO"]
    assert ganador["estado"] == "terminado"
    assert r["estado"] == "reutilizado" and r["resultado"] == ganador["resultado"] and "antes" in r["mensaje"]
    assert len(e.filas()) == 1


# ---------------------------------------------------------------------------
# Cerrojos, progreso y recuperacion
# ---------------------------------------------------------------------------

def test_una_simulacion_activa_por_juego(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 1)
    with pytest.raises(EjecucionActivaError) as error:
        s.iniciar("MILOTO", 1_000, 2)
    assert error.value.activas == {"MILOTO": inicio.ejecucion["id"]}
    otro = s.iniciar("BALOTO", 100, 1)  # otro juego: permitido
    otro.cerrojos.liberar()
    assert s.diagnostico("MILOTO")["activa"] == inicio.ejecucion["id"]
    s.ejecutar(inicio)
    assert s.diagnostico("MILOTO")["activa"] is None


def test_progreso_por_lotes_acotado_en_el_tiempo(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    escrituras = []

    def contar(s):
        original = s._registro.guardar
        s._registro.guardar = lambda ej: escrituras.append(json.loads(json.dumps(ej))) or original(ej)
        return s

    lento = contar(e.servicio(EjecutorContado(lote=10), intervalo_de_progreso=1e9))
    lento.ahora("MILOTO", 1_000, 1)
    simulando = [x["juegos"]["MILOTO"] for x in escrituras if x["juegos"]["MILOTO"].get("fase") == "simulando"]
    assert [(x["hechas"], x["de"]) for x in simulando] == [(0, 1_000), (1_000, 1_000)]
    fases = [x["juegos"]["MILOTO"]["fase"] for x in escrituras]
    assert fases[0] == "inicio" and "obteniendo_datos" in fases and "publicando" in fases and fases[-1] == "terminado"
    escrituras.clear()
    rapido = contar(e.servicio(EjecutorContado(lote=10), intervalo_de_progreso=0))
    rapido.ahora("MILOTO", 1_000, 2)
    hechas = [x["juegos"]["MILOTO"]["hechas"] for x in escrituras if x["juegos"]["MILOTO"].get("fase") == "simulando"]
    assert hechas == [0, *range(10, 1_001, 10)]
    assert all(not k.startswith("_") for x in escrituras for k in x["juegos"]["MILOTO"])


def test_ejecucion_sin_trabajador_se_informa_interrumpida_y_se_recupera(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 1)
    inicio.cerrojos.liberar()  # el proceso murio sin ejecutar
    derivada = s.consultar_ejecucion(inicio.ejecucion["id"])
    assert derivada["estado"] == "interrumpida" and "No se publico nada parcial" in derivada["mensaje"]
    assert s.recuperar() == [inicio.ejecucion["id"]]
    guardada = s._registro.obtener(inicio.ejecucion["id"])
    assert guardada["estado"] == "interrumpida" and guardada["juegos"]["MILOTO"]["estado"] == "interrumpido"
    assert s.recuperar() == []
    assert _juego(e, s.ahora("MILOTO", 100, 1))["estado"] == "terminado" and len(e.filas()) == 1


def test_abortar_libera_y_cierra(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 1)
    s.abortar(inicio, "no se pudo crear el hilo")
    assert s.consultar_ejecucion(inicio.ejecucion["id"])["estado"] == "interrumpida"
    s.iniciar("MILOTO", 100, 1).cerrojos.liberar()


def test_observador_recibe_el_progreso(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    s = e.servicio(EjecutorContado(lote=250), intervalo_de_progreso=0)
    inicio = s.iniciar("MILOTO", 1_000, 1)
    vistos = []
    inicio.observador = lambda ej: vistos.append(ej["juegos"]["MILOTO"].get("hechas"))
    s.ejecutar(inicio)
    assert [v for v in vistos if v is not None][:5] == [0, 250, 500, 750, 1_000]


# ---------------------------------------------------------------------------
# Lectura, verificacion y ausencia de escrituras
# ---------------------------------------------------------------------------

def test_lecturas_no_escriben(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO", "COLORLOTO"))
    s = e.servicio()
    r = _juego(e, s.ahora("MILOTO", 100, 1))
    antes_archivos, antes_filas = _arbol(tmp_path), e.filas()
    s.catalogo(), s.panel(), s.listar(), s.listar("MILOTO", 1), s.obtener(r["resultado"])
    s.exportar_csv(r["resultado"]), s.exportar_json(r["resultado"]), s.verificar(r["resultado"])
    s.recientes(), s.consultar_ejecucion("20261023T000000Z-00000000")
    assert _arbol(tmp_path) == antes_archivos and e.filas() == antes_filas


def test_panel_catalogo_y_listados(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO", "COLORLOTO"))
    s = e.servicio()
    s.ahora("MILOTO", 100, 1)
    panel = {d["juego"]: d for d in s.panel()}
    assert set(panel) == set(f7.JUEGOS)
    assert panel["MILOTO"]["estado"] == "disponible" and len(panel["MILOTO"]["simulaciones"]) == 1
    assert panel["BALOTO"]["estado"] == "sin_datos" and panel["COLORLOTO"]["estado"] == "disponible"
    assert "con reemplazo" in panel["COLORLOTO"]["mecanismo"]
    c = s.catalogo()
    assert c["iteraciones"] == [100, 1_000, 10_000, 100_000, 1_000_000] and set(c["juegos"]) == set(f7.JUEGOS)
    assert c["estado_de_uso"] == "experimental_no_acreditado" and "no es confirmatoria" in c["nota"].lower()
    assert s.listar("BALOTO") == [] and len(s.listar()) == 1
    with pytest.raises(SimulacionesError):
        s.listar("QUINELA")
    for malo in ("no-es-uuid", "00000000-0000-0000-0000-000000000000"):
        with pytest.raises(SimulacionesError) as error:
            s.obtener(malo)
        assert error.value.codigo == "no_encontrado"


def test_verificar_integridad_base_y_reproduccion(tmp_path):
    e = f7.entorno(tmp_path, cargar=("MILOTO",))
    s = e.servicio()
    r = _juego(e, s.ahora("MILOTO", 1_000, 9))
    v = s.verificar(r["resultado"], reproducir=True)
    assert v["integridad"] == "verificada" and v["base"]["estado"] == "coincide"
    assert v["reproduccion"]["estado"] == "reproducida"
    # se corrige un sorteo anterior al corte en la base: la fila sigue describiendo su historico
    primero = e.historicos["MILOTO"][0]
    nuevo = next(n for n in range(1, 40) if n not in primero.numeros)
    with e.engine.begin() as c:
        cambiadas = c.execute(text(
            "UPDATE sorteo_numeros SET numero = :nuevo WHERE numero = :viejo AND sorteo_id = "
            "(SELECT id FROM sorteos WHERE numero_sorteo = :n)"),
            {"nuevo": nuevo, "viejo": primero.numeros[0], "n": primero.numero_sorteo}).rowcount
    assert cambiadas == 1
    v = s.verificar(r["resultado"], reproducir=True)
    assert v["base"]["estado"] == "difiere" and v["reproduccion"]["estado"] == "no_aplicable"
    assert s.obtener(r["resultado"])["integridad"] == "verificada"
