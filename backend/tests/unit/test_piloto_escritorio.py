import ctypes
import socket
import struct
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.publica import dependencias as lecturas
from app.control_piloto import ControlVisor
from app.escritorio import crear_app
from scripts import piloto_windows
from scripts.piloto_escritorio import PilotoError, _comprobar_publicacion

PUERTO = 18021
ORIGEN = f"http://127.0.0.1:{PUERTO}"
ARRANQUE = "credencial-sintetica-de-arranque"


@pytest.fixture
def aplicacion(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<main>piloto</main>", encoding="utf-8")
    return crear_app(frontend=tmp_path, automatizacion=tmp_path / "automatizacion",
                     fecha_referencia=datetime(2026, 11, 11, tzinfo=timezone.utc), puerto=PUERTO, arranque=ARRANQUE)


def test_arranque_de_un_uso_y_consultas_con_sesion(aplicacion):
    class CatalogoVacio:
        def ejecutar(self):
            return []

    aplicacion.dependency_overrides[lecturas.listar_juegos] = CatalogoVacio
    with TestClient(aplicacion, base_url=ORIGEN, client=("127.0.0.1", 12345)) as c:
        assert c.get("/api/v1/salud").status_code == 200
        assert c.get("/api/v1/juegos").status_code == 401
        cabeceras = {"Origin": ORIGEN, "X-Arranque-Escritorio": ARRANQUE}
        ajeno = c.post("/escritorio/sesion", headers={**cabeceras, "Origin": "https://ajeno.example"})
        assert ajeno.status_code == 403
        respuesta = c.post("/escritorio/sesion", headers=cabeceras)
        assert respuesta.status_code == 204
        assert "HttpOnly" in respuesta.headers["set-cookie"]
        assert "SameSite=strict" in respuesta.headers["set-cookie"]
        assert ARRANQUE not in respuesta.headers["set-cookie"]
        assert c.post("/escritorio/sesion", headers=cabeceras).status_code == 403
        assert c.get("/api/v1/juegos").json() == {"juegos": []}
        assert c.get("/api/v1/juegos", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert c.get("/api/v1/juegos", headers={"Host": "ajeno.example"}).status_code == 403
        assert c.get("/api/v1/juegos", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 403
        assert c.post("/api/v1/juegos").status_code == 405
        assert c.get("/api/v1/docs").status_code == 404
        assert c.get("/api/predicciones").status_code == 404


def test_rechaza_socket_ajeno_aunque_el_host_sea_local(aplicacion):
    with TestClient(aplicacion, base_url=ORIGEN, client=("192.0.2.5", 12345)) as c:
        assert c.get("/").status_code == 403
        assert c.get("/api/v1/salud").status_code == 403


def test_cierre_requiere_sesion_y_origen_y_agota_el_arranque(tmp_path):
    (tmp_path / "assets").mkdir()
    control = ControlVisor()
    cierres = []
    app = crear_app(frontend=tmp_path, automatizacion=tmp_path / "auto", puerto=PUERTO, arranque=ARRANQUE,
                    fecha_referencia=datetime(2026, 11, 11, tzinfo=timezone.utc), control=control,
                    cerrar=lambda: cierres.append(True))
    ruta = "/api/v1/escritorio/cerrar"
    inicio = {"Origin": ORIGEN, "X-Arranque-Escritorio": ARRANQUE}
    with TestClient(app, base_url=ORIGEN, client=("127.0.0.1", 12345)) as c:
        assert c.get("/escritorio/instancia").json() == {"instancia": control.identificador}
        assert c.post(ruta, headers={"Origin": ORIGEN}).status_code == 401
        assert c.get(ruta).status_code == 405
        assert c.post("/escritorio/sesion", headers=inicio).status_code == 204
        assert c.post(ruta).status_code == 403
        assert c.post(ruta, headers={"Origin": "https://externo.example"}).status_code == 403
        assert c.post(ruta, headers={"Origin": ORIGEN}).status_code == 204
        assert c.post("/escritorio/sesion", headers=inicio).status_code == 403
        assert c.post(ruta, headers={"Origin": ORIGEN}).status_code == 401
    assert control.cierre_solicitado and cierres == [True]


def test_sincronizacion_informa_base_no_disponible(aplicacion):
    def no_disponible():
        raise OperationalError(None, None, ValueError("detalle de conexión interno"))

    aplicacion.dependency_overrides[lecturas.sesion_de_lectura] = no_disponible
    with TestClient(aplicacion, base_url=ORIGEN, client=("127.0.0.1", 12345)) as c:
        inicio = c.post("/escritorio/sesion", headers={"Origin": ORIGEN, "X-Arranque-Escritorio": ARRANQUE})
        assert inicio.status_code == 204
        respuesta = c.get("/api/v1/escritorio/sincronizacion")
        assert respuesta.status_code == 503
        assert respuesta.json()["error"]["codigo"] == "base_no_disponible"
        assert "detalle de conexión interno" not in respuesta.text


def test_manifiesto_rechaza_archivo_alterado(tmp_path):
    publicacion = tmp_path / "publicacion"
    publicacion.mkdir()
    (publicacion / "cartera.json").write_text("alterado", encoding="utf-8")
    (tmp_path / "manifiesto-publicacion.json").write_text('{"huellas":{"cartera.json":"' + "0" * 64 + '"}}', encoding="utf-8")
    with pytest.raises(PilotoError, match="no coinciden"):
        _comprobar_publicacion(tmp_path)


def test_cierre_windows_consulta_escuchas_sin_conectar(monkeypatch):
    tabla_tcp = struct.pack("=I", 3)
    for direccion, puerto in (("127.0.0.1", 18021), ("0.0.0.0", 18022), ("192.0.2.1", 18023)):
        direccion_local = struct.unpack("=I", socket.inet_aton(direccion))[0]
        tabla_tcp += struct.pack("=6I", 2, direccion_local, socket.htons(puerto), 0, 0, 42)

    def consultar(tabla, tamano, ordenar, familia, clase, reservado):
        assert (ordenar, familia, clase, reservado) == (False, socket.AF_INET, 3, 0)
        if tabla is None:
            ctypes.cast(tamano, ctypes.POINTER(ctypes.c_uint32)).contents.value = len(tabla_tcp)
            return 122
        ctypes.memmove(tabla, tabla_tcp, len(tabla_tcp))
        return 0

    def conectar(*args, **kwargs):
        raise TimeoutError

    monkeypatch.setattr(ctypes, "WinDLL", lambda _: SimpleNamespace(GetExtendedTcpTable=consultar), raising=False)
    monkeypatch.setattr(socket, "create_connection", conectar)
    escuchas = piloto_windows._puertos_en_escucha_windows()
    assert escuchas == {18021, 18022}
    assert not piloto_windows._puerto_cerrado(18021, escuchas)
    assert piloto_windows._puerto_cerrado(18023, escuchas)


def test_fallo_de_tabla_tcp_no_confirma_cierre(monkeypatch):
    def consultar(*args):
        return 5

    monkeypatch.setattr(ctypes, "WinDLL", lambda _: SimpleNamespace(GetExtendedTcpTable=consultar), raising=False)
    with pytest.raises(PilotoError, match="código 5"):
        piloto_windows._puertos_en_escucha_windows()
