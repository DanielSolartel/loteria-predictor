"""Fase 8: autenticacion por clave, configuracion cerrada por defecto, CORS,
ausencia de filtraciones (respuestas y registro) y comando de claves."""
from __future__ import annotations

import io
import logging

import pytest

from app.api.publica import aplicacion
from app.api.publica.configuracion import (
    HUELLA_VACIA,
    ConfiguracionNoValida,
    ConfiguracionPublica,
    desde_settings,
    leer_claves,
    leer_origenes,
)
from app.api.publica.seguridad import generar_clave, huella, identificar
from app.core.config import Settings
from scripts import api_publica_claves as cli
from tests.unit.api_publica import fixtures_api_publica as fa

H = "ab" * 32


@pytest.mark.parametrize("texto", [
    "", "   ", "pruebas", f"pruebas:{H}", f"pruebas:md5:{H}", f"Pruebas:sha256:{H}", f"pruebas:sha256:{H.upper()}",
    f"pruebas:sha256:{H[:-1]}", f"pruebas:sha256:{HUELLA_VACIA}", f"a:sha256:{H},a:sha256:{'2' * 64}",
    f"a:sha256:{H},b:sha256:{H}", f"a:sha256:{H},roto", f"{'x' * 33}:sha256:{H}"])
def test_configuracion_ausente_o_no_valida_no_admite_ninguna_clave(texto):
    assert leer_claves(texto) == ()
    assert not ConfiguracionPublica(claves=leer_claves(texto)).abierta


def test_configuracion_valida_y_valores_predeterminados_cerrados():
    claves = leer_claves(f"frontend:sha256:{H}, operador:sha256:{'2' * 64}")
    assert [c.identificador for c in claves] == ["frontend", "operador"]
    predeterminada = Settings(_env_file=None)
    assert predeterminada.api_publica_claves == "" and predeterminada.api_publica_cors_origenes == ""
    assert not ConfiguracionPublica(claves=leer_claves(predeterminada.api_publica_claves)).abierta


def test_sin_claves_configuradas_toda_consulta_protegida_responde_503(tmp_path):
    a = fa.api(tmp_path)
    a.app.state.configuracion = ConfiguracionPublica(claves=())
    c = a.cliente()
    for cabeceras in ({}, a.cabeceras(), {"X-API-Key": generar_clave()}):
        r = c.get("/api/v1/juegos", headers=cabeceras)
        assert r.status_code == 503 and r.json()["error"]["codigo"] == "no_configurada"
    assert c.get("/api/v1/salud").status_code == 200 and c.get("/api/v1/openapi.json").status_code == 200


def test_sin_variables_ni_env_la_aplicacion_queda_cerrada(monkeypatch, tmp_path):
    for nombre in ("API_PUBLICA_CLAVES", "API_PUBLICA_CORS_ORIGENES"):
        monkeypatch.delenv(nombre, raising=False)
    app = aplicacion.crear_app(desde_settings(Settings(_env_file=None)))
    assert not app.state.configuracion.abierta and app.state.configuracion.cors_origenes == ()
    r = fa.TestClient(app).get("/api/v1/juegos", headers={"X-API-Key": generar_clave()})
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "no_configurada"


def test_clave_ausente_o_no_valida_responde_401_igual(tmp_path):
    a = fa.api(tmp_path)
    c = a.cliente()
    cuerpos = []
    for cabeceras in ({}, {"X-API-Key": ""}, {"X-API-Key": "corta"}, {"X-API-Key": generar_clave()},
                      {"X-API-Key": a.claves["pruebas"] + "x"}, {"X-API-Key": a.claves["pruebas"].upper()}):
        r = c.get("/api/v1/juegos", headers=cabeceras)
        assert r.status_code == 401 and r.headers["WWW-Authenticate"] == 'ApiKey header="X-API-Key"'
        cuerpos.append({k: v for k, v in r.json()["error"].items() if k != "solicitud"})
    assert all(x == cuerpos[0] for x in cuerpos) and cuerpos[0]["codigo"] == "no_autenticado"
    assert a.app.state.limitador_por_clave.identidades == 0  # las claves rechazadas no crean estado de cuota


def test_la_clave_solo_se_admite_en_la_cabecera(tmp_path):
    a = fa.api(tmp_path)
    c = a.cliente()
    clave = a.claves["pruebas"]
    for params in ({"api_key": clave}, {"X-API-Key": clave}, {"clave": clave}):
        assert c.get("/api/v1/juegos", params=params).status_code == 401
    assert c.get("/api/v1/juegos", headers={"Authorization": f"Bearer {clave}"}).status_code == 401
    assert c.get("/api/v1/juegos", headers={"X-API-Key": clave}).status_code == 200
    con_cookie = a.cliente()
    con_cookie.cookies.set("X-API-Key", clave)
    assert con_cookie.get("/api/v1/juegos").status_code == 401


def test_varias_claves_sustitucion_y_revocacion(tmp_path):
    a = fa.api(tmp_path, "antigua", "nueva")
    assert a.get("/api/v1/juegos", "antigua").status_code == 200 and a.get("/api/v1/juegos", "nueva").status_code == 200
    conf = ConfiguracionPublica(claves=tuple(c for c in a.app.state.configuracion.claves if c.identificador == "nueva"),
                                fichas_por_minuto_ip=10_000)
    revocada = fa.api(tmp_path, entorno=a.entorno)
    revocada.app = aplicacion.crear_app(conf)  # al reiniciar sin la entrada antigua
    revocada.app.dependency_overrides = a.app.dependency_overrides
    revocada.claves = a.claves
    assert revocada.get("/api/v1/juegos", "antigua").status_code == 401
    assert revocada.get("/api/v1/juegos", "nueva").status_code == 200


def test_identificar_compara_huellas_y_rechaza_formatos():
    clave = generar_clave()
    claves = leer_claves(f"x:sha256:{huella(clave)}")
    assert clave.startswith("lpk_") and len(clave) >= 40 and identificar(clave, claves) == "x"
    for mala in (None, "", "a" * 31, "a" * 257, "clave con espacios " * 3, "ñ" * 40):
        assert identificar(mala, claves) is None
    assert len({generar_clave() for _ in range(200)}) == 200


def test_ninguna_respuesta_ni_registro_contiene_claves_ni_huellas(tmp_path, caplog):
    a = fa.api(tmp_path)
    clave = a.claves["pruebas"]
    otra = generar_clave()
    secretos = (clave, huella(clave), otra, huella(otra))
    c = a.cliente(raise_server_exceptions=False)
    with caplog.at_level(logging.DEBUG):
        respuestas = [c.get(u, headers=h) for u in ("/api/v1/juegos", "/api/v1/estado", "/api/v1/juegos/QUINELA",
                                                    "/api/v1/juegos/BALOTO/sorteos?pagina=abc", "/no-existe",
                                                    "/api/v1/openapi.json", "/api/v1/docs")
                      for h in ({"X-API-Key": clave}, {"X-API-Key": otra}, {})]
    for r in respuestas:
        texto = r.text + str(dict(r.headers))
        assert not any(s in texto for s in secretos)
    registro = caplog.text
    assert not any(s in registro for s in secretos)
    assert "clave=pruebas" in registro and "solicitud=" in registro


def test_cors_deshabilitado_por_defecto_y_solo_origenes_explicitos(tmp_path):
    a = fa.api(tmp_path)
    r = a.cliente().get("/api/v1/juegos", headers={**a.cabeceras(), "Origin": "https://ajeno.example"})
    assert "access-control-allow-origin" not in r.headers
    con_cors = fa.api(tmp_path / "cors", cors_origenes=("http://localhost:5173",))
    c = con_cors.cliente()
    previa = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "X-API-Key"}
    ok = c.options("/api/v1/juegos", headers={"Origin": "http://localhost:5173", **previa})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "x-api-key" in ok.headers["access-control-allow-headers"].lower()
    ajeno = c.options("/api/v1/juegos", headers={"Origin": "https://ajeno.example", **previa})
    assert "access-control-allow-origin" not in ajeno.headers
    escritura = c.options("/api/v1/juegos", headers={"Origin": "http://localhost:5173",
                                                     "Access-Control-Request-Method": "POST"})
    assert escritura.status_code == 400
    for malo in ("*", "http://*.example", "localhost:5173", "https://a.example/ruta", "ftp://a.example"):
        with pytest.raises(ConfiguracionNoValida):
            leer_origenes(malo)


@pytest.mark.parametrize("extra", [{"fichas_por_minuto": 4}, {"fichas_por_minuto_ip": 0}, {"max_clientes_ip": 1}])
def test_limites_no_validos_impiden_arrancar(extra):
    with pytest.raises(ConfiguracionNoValida):
        aplicacion.crear_app(ConfiguracionPublica(claves=(), **extra))


def _cli(*argv, entrada=""):
    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.main(list(argv), entrada=io.StringIO(entrada), salida=salida, errores=errores)
    return codigo, salida.getvalue(), errores.getvalue()


def test_comando_genera_calcula_y_comprueba_claves(monkeypatch):
    codigo, salida, _ = _cli("generar", "--id", "frontend")
    assert codigo == cli.EXIT_OK
    clave = salida.split("no se guarda): ", 1)[1].split("\n", 1)[0]
    entrada = salida.split("API_PUBLICA_CLAVES: ", 1)[1].strip()
    assert entrada == f"frontend:sha256:{huella(clave)}" and identificar(clave, leer_claves(entrada)) == "frontend"
    codigo, salida, _ = _cli("huella", "--id", "frontend", entrada=clave + "\n")
    assert codigo == cli.EXIT_OK and salida.strip().endswith(entrada) and clave not in salida
    assert _cli("huella", "--id", "frontend", entrada="corta\n")[0] == cli.EXIT_ARGUMENTOS
    assert _cli("generar", "--id", "Mayusculas")[0] == cli.EXIT_ARGUMENTOS
    monkeypatch.setenv("API_PUBLICA_CLAVES", "")
    assert _cli("comprobar")[0] == cli.EXIT_CONFIGURACION
    monkeypatch.setenv("API_PUBLICA_CLAVES", entrada)
    codigo, salida, _ = _cli("comprobar")
    assert codigo == cli.EXIT_OK and "frontend" in salida and huella(clave) not in salida
