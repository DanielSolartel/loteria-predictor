from __future__ import annotations

import copy
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from despliegue.operacion_consulta.auditoria import informe
from despliegue.operacion_consulta.exportador import crear_servidor
from despliegue.operacion_consulta.modelo import Rechazo
from despliegue.operacion_consulta.observabilidad import (
    JUEGOS, evaluar, metricas, muestra, registrar, senales_iniciales, validar_muestra,
)

AHORA = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)


def construir(a):
    with a.exclusivo():
        e = a.inicializar()
    e["acceso"] = "abierto"
    e["eventos"] = [{"tipo": "activacion_completada"}]
    m = {"id": "a" * 32, "creada_en": (AHORA - timedelta(hours=1)).isoformat(),
         "juegos": {j: {"ultima_fecha": "2026-11-04"} for j in JUEGOS}}
    s = registrar(senales_iniciales(), "contacto_pc", AHORA.isoformat(), ahora=AHORA)
    s["calendario"] = {j: {"fecha_sorteo_esperado": "2026-11-04",
                           "resultado_esperado_antes_de": "2026-11-05T10:00:00+00:00"} for j in JUEGOS}
    api = {"base": "disponible", "solicitudes": 50, "por_clase": {"2xx": 46, "4xx": 3, "5xx": 1},
           "segundos_activo": 400, "rutas": [{"latencia_maxima_ms": 20}],
           "claves_configuradas": 1, "SECRETO-NO-EXPORTAR": "valor sintético"}
    return e, m, api, s


def test_muestra_minima_no_exporta_claves_rutas_ni_configuracion(almacen):
    e, m, api, s = construir(almacen)
    v = muestra(e, m, api, s, AHORA)
    assert evaluar(v, AHORA)["alertas"] == []
    texto, sano = metricas(v, AHORA)
    assert sano and "loteria_api_solicitudes 50" in texto and "loteria_api_errores_5xx 1" in texto
    assert "SECRETO" not in str(v) + texto and "claves_configuradas" not in str(v)
    assert m["id"] not in texto


def test_captura_y_sorteo_son_senales_independientes(almacen):
    e, m, api, s = construir(almacen)
    m["creada_en"] = (AHORA - timedelta(days=3)).isoformat()
    v = muestra(e, m, api, s, AHORA)
    assert "captura_antigua" in evaluar(v, AHORA)["alertas"]
    assert "sorteo_pendiente_segun_calendario" not in evaluar(v, AHORA)["alertas"]
    m["creada_en"] = AHORA.isoformat()
    m["juegos"]["MILOTO"]["ultima_fecha"] = "2026-11-01"
    v = muestra(e, m, api, s, AHORA)
    assert "captura_antigua" not in evaluar(v, AHORA)["alertas"]
    assert evaluar(v, AHORA)["sorteos_atrasados"] == ["MILOTO"]


def test_sin_calendario_no_inventa_atraso_del_sorteo(almacen):
    e, m, api, s = construir(almacen)
    s["calendario"] = {}
    m["juegos"]["MILOTO"]["ultima_fecha"] = "2000-01-01"
    r = evaluar(muestra(e, m, api, s, AHORA), AHORA)
    assert r["sorteos_atrasados"] == [] and "calendario_incompleto" in r["alertas"]


def test_contacto_ausente_y_pc_silencioso_no_son_lo_mismo(almacen):
    e, m, api, s = construir(almacen)
    s["pc_contacto_en"] = None
    assert "contacto_pc_desconocido" in evaluar(muestra(e, m, api, s, AHORA), AHORA)["alertas"]
    s["pc_contacto_en"] = (AHORA - timedelta(days=4)).isoformat()
    r = evaluar(muestra(e, m, api, s, AHORA), AHORA)
    assert "pc_silencioso" in r["alertas"] and "contacto_pc_desconocido" not in r["alertas"]


def test_rechazos_posteriores_no_desaparecen_al_releer_la_generacion_anterior():
    s = senales_iniciales()
    for _ in range(3):
        s = registrar(s, "captura_rechazada", AHORA.isoformat(), ahora=AHORA)
    s = registrar(s, "captura_verificada", (AHORA - timedelta(hours=1)).isoformat(), ahora=AHORA)
    assert s["rechazos_consecutivos"] == 3
    despues = AHORA + timedelta(minutes=1)
    s = registrar(s, "captura_verificada", despues.isoformat(), ahora=despues)
    assert s["rechazos_consecutivos"] == 0


def test_alertas_captura_reversion_y_pendiente(almacen):
    e, m, api, s = construir(almacen)
    for _ in range(3):
        s = registrar(s, "captura_rechazada", AHORA.isoformat(), ahora=AHORA)
    e["pendiente"] = {"simulacion": True}
    e["eventos"] = [{"tipo": "activacion_revertida"}]
    r = evaluar(muestra(e, m, api, s, AHORA), AHORA)
    assert {"captura_rechazada", "generacion_no_activada", "activacion_revertida"} <= set(r["alertas"])
    assert not r["servicio_verificado"]


def test_reloj_futuro_no_da_sano(almacen):
    e, m, api, s = construir(almacen)
    v = muestra(e, m, api, s, AHORA + timedelta(hours=1))
    r = evaluar(v, AHORA)
    assert "reloj_incoherente" in r["alertas"] and not r["servicio_verificado"]


def test_firma_no_verificada_no_da_consulta_verificada_aunque_api_responda(almacen):
    e, _, api, s = construir(almacen)
    r = evaluar(muestra(e, None, api, s, AHORA), AHORA)
    assert "captura_sin_verificar" in r["alertas"] and not r["servicio_verificado"]


def test_colector_guarda_muestra_no_sana_si_respuesta_api_es_invalida(almacen, plan, monkeypatch):
    from app.infrastructure.generaciones import importacion
    from despliegue.operacion_consulta import __main__ as cli
    with almacen.exclusivo():
        e = almacen.inicializar()
        almacen.guardar_plan(plan)
        e.update(activa=plan.id, acceso="abierto")
        almacen.escribir("estado.json", e)
    m = {"id": plan.generacion, "creada_en": AHORA.isoformat(), "juegos": {},
         "codigo": {"huella_app": plan.huella_app}}
    monkeypatch.setattr(importacion, "verificar_publicada", lambda *_: {
        "manifiesto": m, "sha256_manifiesto": plan.manifiesto_sha256})
    class RespuestaInvalida:
        def __init__(self, *args):
            self.ultimo_estado = {"base": "disponible", "solicitudes": float("nan"), "segundos_activo": 1}
        def sonda(self, *args):
            pass
    monkeypatch.setattr(cli, "Docker", RespuestaInvalida)
    r = cli.observar(almacen, AHORA)
    assert r["codigo"] == 0 and not r["servicio_verificado"]
    assert almacen.leer("observacion.json")["servicio"]["disponible"] is False


@pytest.mark.parametrize("valor", [float("inf"), float("nan"), -1, True, "50", 10**40])
def test_rechaza_metricas_ambiguas(almacen, valor):
    e, m, api, s = construir(almacen)
    api["solicitudes"] = valor
    with pytest.raises(Rechazo):
        muestra(e, m, api, s, AHORA)


@pytest.mark.parametrize("campo,valor", [("observado_en", "2026-11-05T12:00:00"),
                                         ("acceso", "cualquier-cadena"), ("generacion", "x\nmetrica 1"),
                                         ("transaccion_pendiente", "false")])
def test_exportador_no_acepta_cadenas_para_inyectar_metricas(almacen, campo, valor):
    v = muestra(*construir(almacen), AHORA)
    v[campo] = valor
    with pytest.raises(Rechazo):
        validar_muestra(v)


def test_auditoria_no_promueve_ensayo_a_produccion(almacen):
    e, m, api, s = construir(almacen)
    r = informe(e, muestra(e, m, api, s, AHORA), AHORA)
    assert r["codigo"] == 3 and not r["produccion_autorizada"] and r["ensayo_con_servicio_verificado"]
    assert "D11_activacion_real" in r["pendientes"] and "restauracion_RW_Windows" in r["pendientes"]


def test_exportador_http_fresco_vencido_ausente_y_solo_lectura(almacen):
    v = muestra(*construir(almacen), AHORA)
    with almacen.exclusivo():
        almacen.escribir("observacion.json", v)
    reloj = [AHORA]
    servidor = crear_servidor(almacen, 0, ahora=lambda: reloj[0])
    hilo = threading.Thread(target=servidor.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    hilo.start()
    url = "http://127.0.0.1:" + str(servidor.server_port)
    abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
    try:
        with abrir(url + "/metricas", timeout=2) as r:
            assert r.status == 200 and b"loteria_consulta_verificada 1" in r.read()
            assert r.headers["Cache-Control"] == "no-store"
        with abrir(url + "/salud", timeout=2) as r:
            assert json.load(r) == {"estado": "verificado"}
        reloj[0] += timedelta(seconds=121)
        with pytest.raises(urllib.error.HTTPError) as fallo:
            abrir(url + "/salud", timeout=2)
        assert fallo.value.code == 503
        with abrir(url + "/metricas", timeout=2) as r:
            b = r.read()
            assert b"loteria_consulta_verificada 0" in b and b"observacion_obsoleta" in b
        for ruta, metodo, codigo in (("/api/v1/estado", "GET", 404), ("/metricas?secreto=x", "GET", 404),
                                      ("/metricas", "POST", 405)):
            with pytest.raises(urllib.error.HTTPError) as fallo:
                abrir(urllib.request.Request(url + ruta, method=metodo), timeout=2)
            assert fallo.value.code == codigo
        # Una muestra corrupta nunca se sustituye por una anterior marcada sana.
        with almacen.exclusivo():
            almacen.escribir("observacion.json", {"dato": "SECRETO-SINTETICO"})
        with abrir(url + "/metricas", timeout=2) as r:
            b = r.read()
            assert b"observacion_ausente" in b and b"SECRETO" not in b
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(2)
    assert not hilo.is_alive()


@pytest.mark.parametrize("host", ["0.0.0.0", "localhost", "::1", "192.168.1.1"])
def test_exportador_no_se_publica_en_otras_interfaces(almacen, host):
    with pytest.raises(Rechazo, match="solo_loopback"):
        crear_servidor(almacen, 0, host=host)
