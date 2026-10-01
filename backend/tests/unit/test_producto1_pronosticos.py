"""Producto 1: persistencia, consulta y pantallas del pronostico
experimental de Baloto y Revancha.

Almacen inmutable (nunca sobrescribe, detecta alteraciones), casos de
uso con repositorios fake, conservacion del pronostico cuando el
historico se actualiza, rutas web y REST con la aplicacion real, y el
comando `scripts.pronostico_experimental`. Historicos sinteticos."""
from __future__ import annotations

import ast
import contextlib
import dataclasses
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.application.interfaces.pronostico_experimental_store import PronosticoGuardado, PronosticoIlegible
from app.application.ml import pronostico_experimental as pe
from app.application.use_cases.pronostico_experimental import (
    ConsultarPronosticosExperimentales,
    GenerarPronosticoExperimental,
    PronosticoExperimentalNoDisponibleError,
    VerificarPronosticoExperimental,
    decisiones_ae39,
)
from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
from tests.unit import fixtures_producto1 as fx

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
CONFIG = pe.ConfiguracionExperimental(tamano_bloque=10, bloques_de_evaluacion=2, minimo_objetivos_de_entrenamiento=40)
RELOJ = lambda: datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)  # noqa: E731


@pytest.fixture
def entorno(tmp_path):
    historicos = {"BALOTO": fx.historico_numerico("BALOTO", 130),
                  "BALOTO_REVANCHA": fx.historico_numerico("BALOTO_REVANCHA", 130),
                  "MILOTO": fx.historico_numerico("MILOTO", 130, primero=1)}
    juegos, resultados, colores = fx.repositorios(historicos, colorloto=fx.historico_colorloto(10))
    almacen = PronosticoExperimentalFileStore(tmp_path / "pronosticos")
    return juegos, resultados, colores, almacen, historicos


def _generar(entorno, codigo="BALOTO", **kw):
    juegos, resultados, _, almacen, _ = entorno
    return GenerarPronosticoExperimental(juegos, resultados, almacen, reloj=RELOJ, configuracion=CONFIG).ejecutar(
        codigo, **kw)


def test_generar_guarda_un_artefacto_inmutable(entorno, tmp_path):
    guardado = _generar(entorno)
    archivos = list((tmp_path / "pronosticos" / "BALOTO").glob("*.json"))
    assert len(archivos) == 1 and archivos[0].name == f"2211-{guardado.identificador}.json"
    a = guardado.artefacto
    assert guardado.identificador == a["clave_de_entrada"] and pe.artefacto_integro(a)
    assert a["generacion"]["generado_en"] == "2026-10-01T12:00:00+00:00"
    assert a["huella_de_reproduccion"] == pe.huella_de_reproduccion(pe.cuerpo_del_artefacto(a))
    assert a["estado_de_uso"] == "experimental_no_acreditado" and a["contexto"]["AUTORIZA_EVALUACION"] is False
    with pytest.raises(FileExistsError):
        entorno[3].guardar("BALOTO", a)


def test_actualizar_el_historico_no_cambia_lo_guardado(entorno):
    juegos, resultados, _, almacen, historicos = entorno
    primero = _generar(entorno)
    bytes_antes = {p: p.read_bytes() for p in almacen._carpeta("BALOTO").iterdir()}
    # Llega un sorteo nuevo y se corrige uno antiguo.
    baloto_id = juegos.obtener_por_codigo("BALOTO").id
    nuevo = dataclasses.replace(historicos["BALOTO"][-1], numero_sorteo=2211,
                                fecha=historicos["BALOTO"][-1].fecha.replace(year=2030))
    corregido = dataclasses.replace(historicos["BALOTO"][10], numeros=(1, 2, 3, 4, 5))
    resultados.numericos[baloto_id] = [*historicos["BALOTO"][:10], corregido, *historicos["BALOTO"][11:], nuevo]
    segundo = _generar(entorno)
    assert segundo.artefacto["pronostico"]["objetivo"] == 2212
    for ruta, contenido in bytes_antes.items():
        assert ruta.read_bytes() == contenido
    consulta = ConsultarPronosticosExperimentales(almacen)
    r = consulta.resumen("BALOTO")
    assert [g.identificador for g in r.guardados] == [segundo.identificador, primero.identificador]
    assert consulta.obtener("BALOTO", primero.identificador).artefacto == primero.artefacto
    verificacion = VerificarPronosticoExperimental(juegos, resultados, almacen).ejecutar("BALOTO", primero.identificador)
    assert verificacion["mismos_datos"] is False and verificacion["huella_exacta"] is False


def test_verificar_reproduce_con_los_mismos_datos(entorno):
    juegos, resultados, _, almacen, _ = entorno
    g = _generar(entorno, hasta_numero_sorteo=2200)
    assert resultados.consultas[-1][1] == 2200
    r = VerificarPronosticoExperimental(juegos, resultados, almacen).ejecutar("BALOTO", g.identificador)
    assert r["huella_exacta"] and r["mismos_datos"] and r["mismos_numeros_sugeridos"]
    assert r["maxima_diferencia_de_probabilidad"] == 0.0
    assert g.artefacto["datos"]["corte"] == 2200 and g.artefacto["pronostico"]["objetivo"] == 2201


def test_almacen_detecta_alteraciones_y_nombres_ajenos(entorno):
    almacen = entorno[3]
    g = _generar(entorno)
    carpeta = almacen._carpeta("BALOTO")
    ruta = next(carpeta.glob("*.json"))
    datos = json.loads(ruta.read_bytes())
    datos["pronostico"]["numeros_sugeridos"] = [1, 2, 3, 4, 5]
    ruta.write_bytes(json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode() + b"\n")
    (carpeta / "otro.json").write_bytes(b"{}")
    r = ConsultarPronosticosExperimentales(almacen).resumen("BALOTO")
    assert r.ultimo is None and {e.motivo for e in r.ilegibles} == {"contenido_alterado",
                                                                     "nombre_o_tipo_de_archivo_no_admitido"}
    assert isinstance(almacen.obtener("BALOTO", g.identificador), PronosticoIlegible)
    assert almacen.obtener("BALOTO", "../../etc") is None
    with pytest.raises(ValueError):
        almacen.listar("../BALOTO")


def test_almacen_vacio_y_juegos_no_admitidos(entorno):
    consulta = ConsultarPronosticosExperimentales(entorno[3])
    assert consulta.resumen("BALOTO_REVANCHA").ultimo is None
    for codigo in ("MILOTO", "COLORLOTO"):
        with pytest.raises(PronosticoExperimentalNoDisponibleError):
            consulta.resumen(codigo)
        with pytest.raises(PronosticoExperimentalNoDisponibleError):
            _generar(entorno, codigo)


def test_historico_insuficiente_es_error_claro(entorno):
    with pytest.raises(PronosticoExperimentalNoDisponibleError, match="Historico insuficiente"):
        _generar(entorno, hasta_numero_sorteo=2150)


def test_no_go_se_conserva():
    d = decisiones_ae39()
    assert d["decisiones"] == {"BALOTO": "no_go_sin_evidencia_suficiente",
                               "BALOTO_REVANCHA": "no_go_sin_evidencia_suficiente"}
    assert "NO-GO" in d["procedencia"]


# ---------------------------------------------------------------------------
# Pantallas y REST
# ---------------------------------------------------------------------------

@pytest.fixture
def cliente(entorno):
    juegos, resultados, colores, almacen, _ = entorno
    c = fx.cliente(juegos, resultados, colores, almacen, reloj=RELOJ, configuracion=CONFIG, client=("127.0.0.1", 50000))
    yield c
    from app.main import app
    app.dependency_overrides = {}


def _token(c, slug="baloto"):
    import re
    return re.search(r'name="token_local" value="([^"]+)"', c.get(f"/pronosticos/{slug}").text).group(1)


def test_pantalla_sin_pronosticos_y_generacion(cliente):
    r = cliente.get("/pronosticos")
    assert r.status_code == 200 and "Pronóstico experimental, no acreditado" in r.text
    assert "no_go_sin_evidencia_suficiente" in r.text and "AUTORIZA_EVALUACION = False" in r.text
    assert "Todavía no hay pronósticos guardados" in r.text
    r = cliente.post("/pronosticos/baloto/generar", data={"hasta_numero_sorteo": "", "token_local": _token(cliente)},
                     follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/pronosticos/baloto?id=")
    detalle = cliente.get(r.headers["location"])
    assert detalle.status_code == 200
    for texto in ("Objetivo: sorteo 2211", "Ranking de números", "Rendimiento histórico frente a la referencia uniforme",
                  "Log Loss", "Brier", "Aciertos top-5", "logistica_calibrada_ae36", "producto1-1",
                  "Corte de datos", "Entrenamiento final", "2026-10-01T12:00:00+00:00", "no prueba anterioridad",
                  "Superbalota (objetivo separado)", "experimental"):
        assert texto in detalle.text, texto
    indice = cliente.get("/pronosticos")
    assert "Objetivo: sorteo 2211" in indice.text


def test_pantalla_muestra_si_el_modelo_pierde(cliente, entorno):
    g = _generar(entorno)
    detalle = cliente.get(f"/pronosticos/baloto?id={g.identificador}").text
    veredicto = g.artefacto["evaluacion_walk_forward"]["agregado"]["comparacion"]["veredicto"]
    if veredicto == "el_modelo_no_supera_a_la_referencia_uniforme":
        assert "no supera</strong> a la referencia uniforme" in detalle
    else:
        assert "no acredita ventaja predictiva" in detalle


def test_generar_con_corte_e_historico_insuficiente(cliente):
    token = _token(cliente)
    r = cliente.post("/pronosticos/baloto-revancha/generar", data={"hasta_numero_sorteo": "2150", "token_local": token})
    assert r.status_code == 422 and "Historico insuficiente" in r.text
    assert cliente.post("/pronosticos/baloto/generar",
                        data={"hasta_numero_sorteo": "abc", "token_local": token}).status_code == 422
    r = cliente.post("/pronosticos/baloto/generar", data={"hasta_numero_sorteo": "2200", "token_local": token},
                     follow_redirects=False)
    assert r.status_code == 303
    assert "Objetivo: sorteo 2201" in cliente.get(r.headers["location"]).text


def test_juegos_sin_pronostico_404(cliente):
    for slug in ("miloto", "colorloto", "quina"):
        assert cliente.get(f"/pronosticos/{slug}").status_code == 404
        assert cliente.post(f"/pronosticos/{slug}/generar", data={}).status_code == 404
    assert cliente.get("/pronosticos/baloto?id=" + "0" * 64).status_code == 404


def test_verificar_y_rest(cliente, entorno):
    g = _generar(entorno, "BALOTO_REVANCHA")
    r = cliente.post("/pronosticos/baloto-revancha/verificar",
                     data={"id": g.identificador, "token_local": _token(cliente, "baloto-revancha")})
    assert r.status_code == 200 and "Huella de reproducción idéntica: <strong>sí" in r.text
    j = cliente.get("/api/pronosticos/BALOTO_REVANCHA").json()
    assert j["estado_de_uso"] == "experimental_no_acreditado" and j["ultimo"]["identificador"] == g.identificador
    assert j["no_go_historico"]["decisiones"]["BALOTO_REVANCHA"] == "no_go_sin_evidencia_suficiente"
    detalle = cliente.get(f"/api/pronosticos/BALOTO_REVANCHA/{g.identificador}").json()
    assert detalle["pronostico"] == g.artefacto["pronostico"]
    assert cliente.get("/api/pronosticos/MILOTO").status_code == 404
    assert cliente.get("/api/pronosticos/BALOTO/" + "f" * 64).status_code == 404


def test_consultar_sin_base_de_datos(entorno, tmp_path):
    juegos, resultados, colores, almacen, _ = entorno
    g = _generar(entorno)
    c = fx.cliente(juegos, resultados, colores, almacen, conectada=False)
    try:
        r = c.get(f"/pronosticos/baloto?id={g.identificador}")
        assert r.status_code == 200 and "se pueden consultar los pronósticos guardados" in r.text
        assert "Objetivo: sorteo 2211" in r.text
    finally:
        from app.main import app
        app.dependency_overrides = {}


# ---------------------------------------------------------------------------
# Comando
# ---------------------------------------------------------------------------

def _comando(entorno, argv):
    from scripts import pronostico_experimental as cli
    juegos, resultados, _, almacen, _ = entorno

    @contextlib.contextmanager
    def repos():
        yield juegos, resultados

    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.ejecutar(argv, repositorios=repos, almacen_factory=lambda: almacen, reloj=RELOJ,
                          configuracion=CONFIG, salida=salida, errores=errores)
    return codigo, salida.getvalue(), errores.getvalue()


def test_comando_entrenar_listar_y_verificar(entorno):
    codigo, out, err = _comando(entorno, ["entrenar", "--juego", "todos"])
    assert codigo == 0 and err == ""
    datos = json.loads(out)
    assert [d["juego"] for d in datos] == ["BALOTO", "BALOTO_REVANCHA"]
    assert all(d["estado_de_uso"] == "experimental_no_acreditado" and d["objetivo"] == 2211 for d in datos)
    assert datos[0]["walk_forward"]["veredicto"] in ("el_modelo_no_supera_a_la_referencia_uniforme",
                                                     "el_modelo_supera_a_la_referencia_en_log_loss_y_brier")
    codigo, out, _ = _comando(entorno, ["listar", "--juego", "BALOTO"])
    assert codigo == 0 and len(json.loads(out)["guardados"]) == 1
    identificador = datos[0]["identificador"]
    codigo, out, _ = _comando(entorno, ["verificar", "--juego", "BALOTO", "--id", identificador])
    assert codigo == 0 and json.loads(out)["huella_exacta"] is True


def test_comando_codigos_de_error(entorno):
    assert _comando(entorno, ["entrenar", "--juego", "MILOTO"])[0] == 2
    assert _comando(entorno, ["entrenar", "--juego", "BALOTO", "--hasta-sorteo", "0"])[0] == 2
    codigo, _, err = _comando(entorno, ["entrenar", "--juego", "BALOTO", "--hasta-sorteo", "2150"])
    assert codigo == 4 and "Historico insuficiente" in err
    codigo, _, err = _comando(entorno, ["verificar", "--juego", "BALOTO", "--id", "0" * 64])
    assert codigo == 4

    from scripts import pronostico_experimental as cli

    @contextlib.contextmanager
    def caida():
        raise ConnectionError("sin PostgreSQL")
        yield  # pragma: no cover

    salida, errores = io.StringIO(), io.StringIO()
    assert cli.ejecutar(["entrenar", "--juego", "BALOTO"], repositorios=caida, almacen_factory=lambda: entorno[3],
                        salida=salida, errores=errores) == 3
    assert "ConnectionError" in errores.getvalue()


def test_comando_solo_lee_postgresql():
    texto = (RAIZ_BACKEND / "scripts" / "pronostico_experimental.py").read_text(encoding="utf-8")
    assert "BEGIN TRANSACTION READ ONLY" in texto and 'text("ROLLBACK")' in texto
    arbol = ast.parse(texto)
    llamadas = {n.func.attr for n in ast.walk(arbol) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not llamadas & {"commit", "add", "delete", "merge", "flush"}


def test_estructura_respeta_las_restricciones_previas():
    """Ninguna ruta, plantilla ni script nuevo nombra modulos que las
    etapas anteriores reservaron fuera de la web; el estado operativo y
    el gate no se importan desde la API."""
    archivos = [RAIZ_BACKEND / "app" / "api" / "web" / "routers" / "producto.py",
                RAIZ_BACKEND / "app" / "api" / "rest" / "routers" / "producto.py",
                RAIZ_BACKEND / "app" / "api" / "dependencies.py",
                RAIZ_BACKEND / "app" / "api" / "web" / "proteccion_local.py",
                RAIZ_BACKEND / "scripts" / "pronostico_experimental.py",
                *(RAIZ_BACKEND / "app" / "templates" / "producto").glob("*.html")]
    for ruta in archivos:
        texto = ruta.read_text(encoding="utf-8")
        for prohibido in ("resolver_estado_prediccion", "diagnostico_bloqueo", "registro_prospectivo",
                          "autorizacion_operativa", "reapertura", "prediccion_bloqueada", "app.application.simulaciones"):
            assert prohibido not in texto, (ruta, prohibido)


def test_resultado_guardado_es_pronostico_guardado(entorno):
    assert isinstance(_generar(entorno), PronosticoGuardado)
