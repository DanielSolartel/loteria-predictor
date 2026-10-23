"""Fase 6: panel de solo lectura, controles locales y trazabilidad visible.

Servicio y lanzador controlados: no proveedor, BD ni almacenes reales.
"""
from __future__ import annotations

from copy import deepcopy
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.automatizacion_dependencies import get_automatizacion, get_lanzador_automatizacion
from app.api.web.routers import automatizacion

IDENTIFICADOR = "20261020T180000Z-0123abcd"


class ServicioControlado:
    def __init__(self):
        self.acciones = []
        self.error_panel = None
        self.error_accion = None
        self.datos = {
            "estado": "pausada", "configuracion": {"activada": False, "pausada": True},
            "juegos": [{"codigo": codigo, "estado": "ok", "ultimo_sorteo": numero,
                        "ultima_comprobacion": "2026-10-20T18:00:00-05:00",
                        "ultima_actualizacion": "2026-10-20T18:00:01-05:00",
                        "proximo_evento": {"instante": "2026-10-21T04:00:00+00:00"},
                        "proxima_consulta": "2026-10-20T18:15:00-05:00",
                        "configuracion_modelo": {"modelo": {"id": modelo, "registrado": {"numero": 2, "clave": "a" * 64}}, "cantidad": 5},
                        "ejecucion": IDENTIFICADOR, "pasos": [{"paso": "sincronizacion", "estado": "ok", "resultado": {"nuevos": 1}}]}
                       for codigo, numero, modelo in [("BALOTO", 2723, "xgboost_binario"), ("BALOTO_REVANCHA", 2723, "lightgbm_binario"),
                                                      ("MILOTO", 625, "red_neuronal_binaria"), ("COLORLOTO", 228, "bayes_jerarquico_pares")]],
            "ejecuciones": [{"id": IDENTIFICADOR, "estado": "exito", "iniciada_en": "2026-10-20T18:00:00-05:00"}],
            "avisos": [{"mensaje": "ColorLoto: publicación pendiente de revisión."}],
            "revisiones": [{"clave": "b" * 64, "juego": "COLORLOTO", "numero_sorteo": 228, "estado": "pendiente_revision"}],
        }
        self.ejecuciones = {IDENTIFICADOR: {"id": IDENTIFICADOR, "estado": "interrumpida", "origen": "tarea_windows",
                                            "iniciada_en": "2026-10-20T18:00:00-05:00", "finalizada_en": None,
                                            "juegos": {"BALOTO": {"estado": "ok", "pasos": [{"paso": "publicacion", "estado": "ok"}]},
                                                       "COLORLOTO": {"estado": "interrumpido", "motivo": "El proceso terminó antes del cierre.", "pasos": []}}}}

    def panel(self):
        if self.error_panel:
            raise self.error_panel
        return deepcopy(self.datos)

    def consultar_ejecucion(self, identificador):
        return deepcopy(self.ejecuciones.get(identificador))

    def _accion(self, nombre):
        if self.error_accion:
            raise self.error_accion
        self.acciones.append(nombre)

    def pausar(self):
        self._accion("pausar")

    def reanudar(self):
        self._accion("reanudar")

    def recuperar(self):
        self._accion("recuperar")

    def ciclo(self, **kw):
        self.acciones.append(("ciclo", kw))
        return {"estado": "exito"}


@pytest.fixture
def entorno():
    servicio = ServicioControlado()
    pendientes = []
    app = FastAPI()
    app.include_router(automatizacion.router)
    app.dependency_overrides[get_automatizacion] = lambda: servicio
    app.dependency_overrides[get_lanzador_automatizacion] = lambda: pendientes.append
    return servicio, pendientes, app


def cliente(entorno, direccion="127.0.0.1"):
    return TestClient(entorno[2], base_url="http://localhost", client=(direccion, 45000))


def token(c):
    return re.search(r'name="token_local" value="([^"]+)"', c.get("/automatizacion").text).group(1)


def test_consultar_dos_veces_y_detalle_no_ejecuta_ni_escribe(entorno, tmp_path):
    marca = tmp_path / "artefacto-guardado.txt"
    marca.write_text("huella que debe conservarse\r\n", encoding="utf-8", newline="")
    before = marca.read_bytes(), marca.stat().st_mtime_ns
    servicio, pendientes, _ = entorno
    datos_antes = deepcopy(servicio.datos)
    c = cliente(entorno)
    for _ in range(2):
        assert c.get("/automatizacion").status_code == 200
        assert c.get(f"/automatizacion/ejecuciones/{IDENTIFICADOR}").status_code == 200
    assert servicio.acciones == pendientes == []
    assert servicio.datos == datos_antes
    assert (marca.read_bytes(), marca.stat().st_mtime_ns) == before


def test_panel_muestra_cuatro_juegos_eventos_versiones_y_revisiones(entorno):
    r = cliente(entorno).get("/automatizacion")
    assert r.status_code == 200
    for codigo in automatizacion.NOMBRES:
        assert f'data-juego="{codigo}"' in r.text
    for texto in ("xgboost_binario", "lightgbm_binario", "red_neuronal_binaria", "bayes_jerarquico_pares",
                  "versión 2", "a" * 64, "Última comprobación", "Última actualización", "Próxima consulta",
                  "Siguiente evento previsto", "Resultados pendientes de revisión", "Avisos guardados",
                  "no instala ni habilita la tarea", "AUTORIZA_EVALUACION = False", "AE-39 NO-GO"):
        assert texto in r.text
    assert f'href="/automatizacion/ejecuciones/{IDENTIFICADOR}"' in r.text
    assert 'href="/predicciones/baloto-revancha"' in r.text
    assert "2026-10-20 23:00:00 · Bogotá (UTC-05:00)" in r.text


@pytest.mark.parametrize("accion", ["pausar", "reanudar", "recuperar", "comprobar"])
def test_acciones_rechazan_token_ausente_y_cliente_remoto(entorno, accion):
    c = cliente(entorno)
    t = token(c)
    assert c.post(f"/automatizacion/{accion}").status_code == 403
    remoto = cliente(entorno, "203.0.113.11")
    assert remoto.post(f"/automatizacion/{accion}", data={"token_local": t}).status_code == 403
    assert entorno[0].acciones == entorno[1] == []


@pytest.mark.parametrize("cabeceras", [{"Origin": "http://ajeno.example"}, {"Host": "ajeno.example"},
                                       {"Sec-Fetch-Site": "cross-site"}, {"Referer": "http://ajeno.example/pagina"}])
def test_accion_entre_sitios_no_inicia_trabajo(entorno, cabeceras):
    c = cliente(entorno)
    assert c.post("/automatizacion/comprobar", data={"token_local": token(c)}, headers=cabeceras).status_code == 403
    assert entorno[0].acciones == entorno[1] == []


@pytest.mark.parametrize("accion", ["pausar", "reanudar", "recuperar"])
def test_control_local_protegido_aplica_solo_la_accion_pedida(entorno, accion):
    c = cliente(entorno)
    r = c.post(f"/automatizacion/{accion}", data={"token_local": token(c)}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/automatizacion"
    assert entorno[0].acciones == [accion] and entorno[1] == []


@pytest.mark.parametrize("juego,esperados", [("todos", None), ("BALOTO_REVANCHA", ["BALOTO_REVANCHA"])])
def test_comprobacion_puntual_se_lanza_sin_programar_ni_ejecutar_en_get(entorno, juego, esperados):
    c = cliente(entorno)
    r = c.post("/automatizacion/comprobar", data={"juego": juego, "token_local": token(c)}, follow_redirects=False)
    assert r.status_code == 303
    assert entorno[0].acciones == [] and len(entorno[1]) == 1
    assert c.get("/automatizacion").status_code == 200
    assert entorno[0].acciones == []
    entorno[1].pop()()
    assert entorno[0].acciones == [("ciclo", {"juegos": esperados, "forzar": True, "origen": "web"})]


@pytest.mark.parametrize("accion,juego", [("instalar", "todos"), ("comprobar", "QUINA")])
def test_accion_o_juego_desconocidos_no_escriben(entorno, accion, juego):
    c = cliente(entorno)
    r = c.post(f"/automatizacion/{accion}", data={"juego": juego, "token_local": token(c)})
    assert r.status_code == 422
    assert entorno[0].acciones == entorno[1] == []


def test_detalle_distingue_interrupcion_de_juegos_ya_terminados(entorno):
    texto = cliente(entorno).get(f"/automatizacion/ejecuciones/{IDENTIFICADOR}").text
    assert "Interrumpida" in texto and "Completado" in texto
    assert "El proceso terminó antes del cierre." in texto
    assert "hx-trigger" not in texto
    assert entorno[0].acciones == entorno[1] == []


@pytest.mark.parametrize("identificador", ["no-valido", "20261020T180000Z-deadbeef"])
def test_ejecucion_ajena_o_inexistente_es_404(entorno, identificador):
    assert cliente(entorno).get(f"/automatizacion/ejecuciones/{identificador}").status_code == 404


def test_registro_caido_no_filtra_error_de_conexion_o_secretos(entorno):
    entorno[0].error_panel = ConnectionError("postgresql://usuario:SECRETO@servidor/bd")
    r = cliente(entorno).get("/automatizacion")
    assert r.status_code == 503
    assert "No se pudo leer" in r.text and "SECRETO" not in r.text and "postgresql" not in r.text


@pytest.mark.parametrize("error,codigo", [(ValueError("ruta externa"), 422), (OSError("disco"), 503)])
def test_error_de_control_conserva_la_consulta_y_no_asegura_exito(entorno, error, codigo):
    c = cliente(entorno)
    t = token(c)
    entorno[0].error_accion = error
    assert c.post("/automatizacion/reanudar", data={"token_local": t}, follow_redirects=False).status_code == codigo
    assert entorno[0].acciones == entorno[1] == []
    assert c.get("/automatizacion").status_code == 200


def test_control_con_recurso_ocupado_informa_conflicto_sin_cambiarlo(entorno):
    from app.application.exceptions import OperacionConcurrenteError

    c = cliente(entorno)
    t = token(c)
    entorno[0].error_accion = OperacionConcurrenteError("cerrojo retenido por otra ejecución")
    r = c.post("/automatizacion/reanudar", data={"token_local": t}, follow_redirects=False)
    assert r.status_code == 409
    assert "Otro proceso conserva este recurso" in r.text
    assert entorno[0].acciones == entorno[1] == []


def test_consulta_web_con_almacen_real_no_crea_directorios_ni_artefactos(tmp_path):
    from app.application.use_cases.operacion_automatica import OperacionAutomatica
    from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion

    class AdaptadorNoInvocable:
        def por_juego(self, codigo):
            pytest.fail("Un GET no debe abrir dependencias de consulta o generación.")

    raiz = tmp_path / "almacén sintético con espacios"
    servicio = OperacionAutomatica(AlmacenAutomatizacion(raiz), AdaptadorNoInvocable())
    app = FastAPI()
    app.include_router(automatizacion.router)
    app.dependency_overrides[get_automatizacion] = lambda: servicio
    c = TestClient(app, base_url="http://localhost")
    for _ in range(2):
        r = c.get("/automatizacion")
        assert r.status_code == 200
        assert "Sin comprobación" in r.text
    assert not raiz.exists()


def test_get_con_registro_real_conserva_bytes_y_mtime_de_cada_archivo(tmp_path):
    from app.application.use_cases.operacion_automatica import OperacionAutomatica
    from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion

    raiz = tmp_path / "almacén sintético con espacios"
    almacen = AlmacenAutomatizacion(raiz)
    almacen.guardar_estado("MILOTO", {"estado": "resultado_retrasado", "ultimo_sorteo": 624,
                                      "motivo": "El horario del objetivo ya se alcanzó."})
    almacen.guardar_ejecucion({"id": IDENTIFICADOR, "estado": "parcial", "juegos": {}})
    before = {p.relative_to(raiz).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
              for p in raiz.rglob("*") if p.is_file()}
    servicio = OperacionAutomatica(almacen, object())
    app = FastAPI()
    app.include_router(automatizacion.router)
    app.dependency_overrides[get_automatizacion] = lambda: servicio
    c = TestClient(app, base_url="http://localhost")
    assert c.get("/automatizacion").status_code == 200
    assert c.get(f"/automatizacion/ejecuciones/{IDENTIFICADOR}").status_code == 200
    after = {p.relative_to(raiz).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
             for p in raiz.rglob("*") if p.is_file()}
    assert after == before


def test_falta_de_zona_iana_muestra_el_offset_guardado_sin_inventar_conversion(monkeypatch):
    def sin_zona(_):
        raise automatizacion.ZoneInfoNotFoundError("sin IANA")

    monkeypatch.setattr(automatizacion, "ZoneInfo", sin_zona)
    assert automatizacion.fecha_operativa("2026-10-21T04:00:00+00:00") == (
        "2026-10-21T04:00:00+00:00 (offset guardado; zona Bogotá no disponible)")


def test_fecha_sin_zona_no_se_presenta_como_hora_de_bogota():
    assert automatizacion.fecha_operativa("2026-10-20T23:00:00") == "2026-10-20T23:00:00 (zona no registrada)"


def test_estado_vacio_no_inventa_actividad_o_versiones(entorno):
    entorno[0].datos = {"estado": "sin_configurar", "juegos": [], "ejecuciones": [], "avisos": [], "revisiones": []}
    r = cliente(entorno).get("/automatizacion")
    assert r.status_code == 200
    assert "Sin configurar" in r.text and "Sin ejecuciones guardadas." in r.text
    assert "versión 2" not in r.text


def test_texto_guardado_se_escapa_y_hay_navegacion_movil(entorno):
    entorno[0].datos["juegos"][0]["motivo"] = '<script>alert("ajeno")</script>'
    r = cliente(entorno).get("/automatizacion")
    assert '<script>alert("ajeno")</script>' not in r.text
    assert "&lt;script&gt;" in r.text
    assert 'href="/automatizacion"' in r.text and 'd-md-none' in r.text
