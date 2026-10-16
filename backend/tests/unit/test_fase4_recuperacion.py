"""Fase 4 (v3) - recuperacion de una generacion que no termina bien.

Reproduce, con datos sinteticos, la validacion web fallida en Windows: el
trabajador de Carteras publico la cartera y murio al registrar el progreso
(`PermissionError` al reemplazar el JSON). El registro de Carteras quedo «en
curso», el del centro tambien, y la pagina mostraba «Interrumpido» con
«cartera: en curso», «Explicacion: pendiente» y consultas cada 2 s.

Comprueba que el centro maneja la excepcion, que una ejecucion sin
trabajador se muestra terminada o interrumpida y deja de consultar (sin
escribir en un GET), que una explicacion todavia activa no se declara
interrumpida, y que repetir la misma entrada reutiliza la cartera publicada
y completa su explicacion sin reentrenar, sin reescribir el artefacto y sin
otra version. Nada es real."""
from __future__ import annotations

import io
import json
import threading

import pytest

from app.application.ml import laboratorio_modelos as lm
from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego, RegistroEjecucionesArchivo
from scripts import predicciones as cli
from tests.unit import fixtures_fase4 as f4

ID_EVIDENCIA = "20261013T135713Z-dc2deb60"
ERROR_WINDOWS = ("[WinError 5] Access is denied: '.20261013T135713Z-dc2deb60.8601c0ff.tmp' -> "
                 "'20261013T135713Z-dc2deb60.json'")


@pytest.fixture
def entorno(tmp_path):
    e = f4.entorno(tmp_path)
    yield e
    f4.limpiar()


def _baloto_registrado(e):
    """Baloto con una version registrada de Random Forest (como la configuracion real v1)."""
    lab = e.laboratorio()
    r = e.registrar(lab, "BALOTO", "random_forest_clasificador")
    e.configurar("BALOTO", "random_forest_clasificador", registrado=r["modelo_registrado"])
    carteras = e.carteras()
    centro = e.centro(carteras)
    return lab, carteras, centro, f4.cliente(e, carteras=carteras, laboratorio=lab, centro=centro)


def _miloto(e):
    e.configurar("MILOTO", "uniforme")
    carteras = e.carteras()
    centro = e.centro(carteras)
    return carteras, centro, f4.cliente(e, carteras=carteras, centro=centro)


def _falla_al_cerrar_el_juego(monkeypatch, carteras, veces: int = 1) -> None:
    """El registro de Carteras falla como en Windows al guardar el progreso con el juego ya terminado (la
    cartera ya esta publicada). Error permanente: no se reintenta."""
    real = carteras._registro.guardar
    pendientes = [veces]

    def guardar(ejecucion):
        terminado = any(j.get("estado") in ("terminado", "reutilizado") for j in ejecucion.get("juegos", {}).values())
        if pendientes[0] and ejecucion.get("estado") == "en_curso" and terminado:
            pendientes[0] -= 1
            raise PermissionError(13, ERROR_WINDOWS)
        return real(ejecucion)

    monkeypatch.setattr(carteras._registro, "guardar", guardar)


def _vivo(e, almacen: str, identificador: str) -> bool:
    return CerrojoPorJuego(e.raiz / almacen / "operacion").ejecucion_viva(identificador)


def _paginas(c, identificador: str) -> list[str]:
    return [c.get(f"/predicciones/ejecuciones/{identificador}").text,
            c.get(f"/predicciones/ejecuciones/{identificador}/estado").text]


def _sin_consultas(texto: str) -> bool:
    return "hx-get" not in texto and "hx-trigger" not in texto


def _prohibido(*args, **kwargs):
    raise AssertionError("una cartera ya publicada se reutiliza: no se reentrena ni se vuelve a inferir")


def _fuera_de_operacion(arbol: dict) -> dict:
    return {k: v for k, v in arbol.items() if not k.startswith("operacion")}


# ---------------------------------------------------------------------------
# Fallo despues de publicar la cartera (la validacion web de Windows)
# ---------------------------------------------------------------------------

def test_un_fallo_al_registrar_tras_publicar_conserva_la_cartera_y_repetir_la_reutiliza(entorno, monkeypatch):
    lab, carteras, centro, c = _baloto_registrado(entorno)
    _falla_al_cerrar_el_juego(monkeypatch, carteras)
    token = f4.token(c)
    r = c.post("/predicciones/baloto/generar", data={"token_local": token, "cantidad": "configuracion"},
               follow_redirects=False)
    assert r.status_code == 303  # el hilo (aqui sincrono) no propaga la excepcion
    identificador = r.headers["location"].rsplit("/", 1)[1]
    p = centro.ejecucion(identificador)["prediccion"]
    assert (p["estado"], p["fase"], p["codigo"]) == ("fallo", "terminado", "almacen_no_disponible")
    assert p["finalizada_en"] and "Access is denied" in p["mensaje"] and "repetir la misma entrada" in p["mensaje"]
    assert p["explicacion"]["estado"] == "no_aplica"
    clave = p["cartera"]["clave"]
    assert p["cartera"]["publicada"] is True and p["cartera"]["linea"].startswith("random_forest_clasificador-v1-reg1")
    guardada = carteras.cartera(clave)  # disponible y verificada por el almacen
    assert guardada.juego == "BALOTO" and guardada.linea == p["cartera"]["linea"]
    assert not _vivo(entorno, "carteras", identificador) and not _vivo(entorno, "predicciones", identificador)
    vista = centro.ejecucion(identificador)
    assert vista["cartera"]["estado"] == "interrumpida"
    juego = vista["cartera"]["juegos"]["BALOTO"]
    assert juego["estado"] == "interrumpido" and juego["cartera_verificada"] is True and juego["resultado"] == clave
    antes = f4.arbol(entorno.raiz)
    for texto in _paginas(c, identificador):
        assert _sin_consultas(texto)
        assert "No se generó la predicción." in texto and "Access is denied" in texto
        assert "cartera: interrumpida" in texto and "cartera: en curso" not in texto
        assert "Explicación: pendiente" not in texto and "se publicó y se verificó" in texto
        assert f'href="/predicciones/baloto?cartera={clave}"' in texto
    assert f4.arbol(entorno.raiz) == antes  # los GET no escriben

    # Repetir la misma entrada: se reutiliza la cartera publicada y se completa su explicacion
    monkeypatch.setattr(lm, "ajustar_candidato", _prohibido)
    monkeypatch.setattr(carteras._ejecutor, "fuente_registrada", _prohibido)
    cartera_antes = _fuera_de_operacion(f4.arbol(entorno.raiz / "carteras"))
    laboratorio_antes = f4.arbol(entorno.raiz / "laboratorio")
    r = c.post("/predicciones/baloto/generar", data={"token_local": token, "cantidad": "configuracion"},
               follow_redirects=False)
    assert r.status_code == 303
    nuevo = r.headers["location"].rsplit("/", 1)[1]
    vista = centro.ejecucion(nuevo)
    assert vista["cartera"]["juegos"]["BALOTO"]["estado"] == "reutilizado"
    assert vista["cartera"]["juegos"]["BALOTO"]["resultado"] == clave
    assert vista["prediccion"]["estado"] == "exito" and vista["prediccion"]["explicacion"]["estado"] == "guardada"
    assert _fuera_de_operacion(f4.arbol(entorno.raiz / "carteras")) == cartera_antes  # ni se reescribe ni hay otra
    assert f4.arbol(entorno.raiz / "laboratorio") == laboratorio_antes  # sin reentrenar ni otra version
    assert carteras.cartera(clave).version == guardada.version
    assert centro.ejecucion(identificador)["prediccion"] == p  # el intento fallido se conserva tal cual
    assert _sin_consultas(c.get(f"/predicciones/ejecuciones/{nuevo}/estado").text)


# ---------------------------------------------------------------------------
# Ejecuciones sin trabajador y explicacion activa
# ---------------------------------------------------------------------------

def test_una_ejecucion_sin_trabajador_se_muestra_interrumpida_sin_escribir_y_deja_de_consultar(entorno):
    carteras, centro, c = _miloto(entorno)
    inicio = centro.iniciar("MILOTO")
    # El proceso muere: el sistema suelta sus cerrojos y nadie escribe los cierres
    inicio.cartera.cerrojos.liberar()
    if getattr(inicio, "cerrojo", None) is not None:
        inicio.cerrojo.liberar()
    identificador = inicio.identificador
    antes = f4.arbol(entorno.raiz)
    vista = centro.ejecucion(identificador)
    assert vista["prediccion"]["estado"] == "interrumpida" and vista["cartera"]["estado"] == "interrumpida"
    assert vista["cartera"]["juegos"]["MILOTO"]["estado"] == "interrumpido"
    for texto in _paginas(c, identificador):
        assert _sin_consultas(texto) and "Interrumpido." in texto
        assert "cartera: pendiente" not in texto and "Explicación: pendiente" not in texto
    assert f4.arbol(entorno.raiz) == antes
    guardado = RegistroEjecucionesArchivo(entorno.raiz / "predicciones" / "operacion").obtener(identificador)
    assert guardado["estado"] == "en_curso"  # la derivacion es de lectura: el registro no se toca
    assert centro.ahora("MILOTO")["prediccion"]["estado"] == "exito"  # nada quedo bloqueado


def test_una_explicacion_activa_no_se_declara_interrumpida_aunque_carteras_haya_terminado(entorno, monkeypatch):
    carteras, centro, c = _miloto(entorno)
    dentro, soltar = threading.Event(), threading.Event()
    real = centro.explicar

    def explicacion_lenta(*args, **kwargs):
        dentro.set()
        assert soltar.wait(60)
        return real(*args, **kwargs)

    monkeypatch.setattr(centro, "explicar", explicacion_lenta)
    inicio = centro.iniciar("MILOTO")
    identificador = inicio.identificador
    hilo = threading.Thread(target=centro.ejecutar, args=(inicio,))
    hilo.start()
    try:
        assert dentro.wait(60)
        assert not _vivo(entorno, "carteras", identificador)  # Carteras termino y solto sus cerrojos
        assert _vivo(entorno, "predicciones", identificador)  # el centro sigue trabajando
        vista = centro.ejecucion(identificador)
        assert vista["cartera"]["estado"] == "exito"
        assert (vista["prediccion"]["estado"], vista["prediccion"]["fase"]) == ("en_curso", "explicacion")
        texto = c.get(f"/predicciones/ejecuciones/{identificador}/estado").text
        assert 'hx-trigger="every 2s"' in texto and "En curso" in texto
        assert "Interrumpido." not in texto and "Terminado." not in texto
    finally:
        soltar.set()
        hilo.join(60)
    assert centro.ejecucion(identificador)["prediccion"]["estado"] == "exito"
    texto = c.get(f"/predicciones/ejecuciones/{identificador}/estado").text
    assert _sin_consultas(texto) and "Terminado." in texto
    assert not _vivo(entorno, "predicciones", identificador)


def test_una_generacion_que_acaba_de_terminar_no_se_confunde_con_una_interrumpida(entorno, monkeypatch):
    """Carrera: la consulta lee el registro justo antes del cierre y mira el cerrojo justo despues de soltarse."""
    _, centro, c = _miloto(entorno)
    p = centro.ahora("MILOTO", origen="web")["prediccion"]
    real = centro._registro.obtener
    lecturas = []

    def obtener(identificador):
        lecturas.append(identificador)
        guardado = real(identificador)
        return {**guardado, "estado": "en_curso", "fase": "explicacion"} if len(lecturas) == 1 else guardado

    monkeypatch.setattr(centro._registro, "obtener", obtener)
    vista = centro.ejecucion(p["id"])
    assert vista["prediccion"]["estado"] == "exito" and len(lecturas) == 2


def test_el_trabajador_que_termina_tras_observarlo_vivo_no_se_declara_interrumpido(entorno, monkeypatch):
    """Lee en_curso; observa vivo; el trabajador real cierra y libera antes de devolver la observacion."""
    _, centro, _ = _miloto(entorno)
    dentro, soltar = threading.Event(), threading.Event()
    explicar = centro.explicar
    comprobar = centro._cerrojo.ejecucion_viva
    observaciones, resultados, errores = [], [], []

    def explicacion_pausada(*args, **kwargs):
        dentro.set()
        assert soltar.wait(60)
        return explicar(*args, **kwargs)

    monkeypatch.setattr(centro, "explicar", explicacion_pausada)
    inicio = centro.iniciar("MILOTO")

    def trabajar():
        try:
            resultados.append(centro.ejecutar(inicio))
        except BaseException as error:
            errores.append(error)

    hilo = threading.Thread(target=trabajar)

    def observar_y_terminar(identificador):
        viva = comprobar(identificador)
        observaciones.append(viva)
        if len(observaciones) == 1:
            assert viva  # captura el cerrojo ocupado antes de dejar terminar al trabajador
            soltar.set()
            hilo.join(60)
            assert not hilo.is_alive() and not errores
            assert resultados[0]["prediccion"]["estado"] == "exito"
        return viva

    hilo.start()
    try:
        assert dentro.wait(60)
        assert centro._registro.obtener(inicio.identificador)["estado"] == "en_curso"
        monkeypatch.setattr(centro._cerrojo, "ejecucion_viva", observar_y_terminar)
        vista = centro.ejecucion(inicio.identificador)
        guardada = centro._registro.obtener(inicio.identificador)
        assert guardada["estado"] == "exito" and not comprobar(inicio.identificador)
        assert observaciones[0] is True and all(viva is False for viva in observaciones[1:])
        assert vista["prediccion"]["estado"] in ("en_curso", "exito"), (
            f"consulta={vista['prediccion']['estado']}, persistido={guardada['estado']}, "
            f"observaciones_del_cerrojo={observaciones}; un cierre valido no es una interrupcion")
    finally:
        soltar.set()
        hilo.join(60)


def test_una_excepcion_de_carteras_antes_de_terminar_cierra_la_prediccion_y_suelta_los_cerrojos(entorno, monkeypatch):
    carteras, centro, c = _miloto(entorno)
    real = carteras.ejecutar

    def roto(inicio):
        raise RuntimeError("fallo simulado del trabajador")

    monkeypatch.setattr(carteras, "ejecutar", roto)
    inicio = centro.iniciar("MILOTO")
    p = centro.ejecutar(inicio)["prediccion"]
    assert (p["estado"], p["fase"], p["codigo"]) == ("fallo", "terminado", "fallo_inesperado")
    assert "RuntimeError" in p["mensaje"] and p["cartera"]["publicada"] is False
    assert not _vivo(entorno, "carteras", p["id"]) and not _vivo(entorno, "predicciones", p["id"])
    assert all(_sin_consultas(t) for t in _paginas(c, p["id"]))
    monkeypatch.setattr(carteras, "ejecutar", real)
    assert centro.ahora("MILOTO")["prediccion"]["estado"] == "exito"


def test_si_el_lanzador_falla_tambien_se_suelta_el_cerrojo_del_centro(entorno):
    carteras, centro, _ = _miloto(entorno)

    def falla(funcion, inicio):
        raise RuntimeError("can't start new thread")

    c = f4.cliente(entorno, lanzador=falla, centro=centro, carteras=carteras)
    r = c.post("/predicciones/miloto/generar", data={"token_local": f4.token(c), "cantidad": "configuracion"})
    assert r.status_code == 500
    (propio,) = RegistroEjecucionesArchivo(entorno.raiz / "predicciones" / "operacion").listar()
    assert propio["estado"] == "interrumpida"
    assert not _vivo(entorno, "predicciones", propio["id"]) and not _vivo(entorno, "carteras", propio["id"])


# ---------------------------------------------------------------------------
# Registros con la forma exacta de la validacion fallida (creados por la v2)
# ---------------------------------------------------------------------------

def _registros_de_la_evidencia(e, clave: str, linea: str) -> None:
    """Los tres archivos conservados de Windows, con la cartera y la linea de este almacen sintetico."""
    juego = {"corte": 2720, "estado": "en_curso", "fase": "construccion", "fin": None,
             "inicio": "2026-10-13T13:57:13.369602+00:00", "juego": "MILOTO", "mensaje": None, "modelo": "uniforme",
             "objetivo": 2721, "resultado": clave, "sorteos": 640, "tipo": "cartera"}
    cartera = {"estado": "en_curso", "fase": "trabajando", "finalizada_en": None, "id": ID_EVIDENCIA,
               "iniciada_en": "2026-10-13T13:57:13.352500+00:00", "juegos": {"MILOTO": juego}, "orden": ["MILOTO"],
               "origen": "web", "tipo": "cartera",
               "parametros": {"cantidad": 3, "configuracion": {"linea": linea, "version": 1}, "diversidad": "libre",
                              "modelo": "uniforme", "perfil": "predeterminado", "semilla": 42}}
    RegistroEjecucionesArchivo(e.raiz / "carteras" / "operacion").guardar(cartera)
    temporal = {**cartera, "juegos": {"MILOTO": {**juego, "estado": "terminado", "fase": "terminado", "linea": linea,
                                                 "fin": "2026-10-13T13:57:17.729721+00:00"}}}
    (e.raiz / "carteras" / "operacion" / "ejecuciones" / f".{ID_EVIDENCIA}.8601c0ff.tmp").write_text(
        json.dumps(temporal, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    RegistroEjecucionesArchivo(e.raiz / "predicciones" / "operacion").guardar(
        {"cartera": None, "estado": "en_curso", "explicacion": None, "fase": "cartera", "finalizada_en": None,
         "id": ID_EVIDENCIA, "iniciada_en": "2026-10-13T13:57:13+00:00", "juego": "MILOTO", "origen": "web",
         "tipo": "prediccion", "solicitud": {"cantidad": "configuracion", "combinaciones": 3,
                                             "configuracion": {"cantidad": 3, "linea": linea, "version": 1}}})


def test_los_registros_de_la_validacion_fallida_se_muestran_interrumpidos_y_la_cartera_se_reutiliza(entorno):
    carteras, centro, c = _miloto(entorno)
    publicada = carteras.ahora("carteras_configuradas", ["MILOTO"])["juegos"]["MILOTO"]  # cartera sin explicacion
    clave, linea = publicada["resultado"], publicada["linea"]
    _registros_de_la_evidencia(entorno, clave, linea)
    antes = f4.arbol(entorno.raiz)
    vista = centro.ejecucion(ID_EVIDENCIA)
    assert vista["prediccion"]["estado"] == "interrumpida" and vista["cartera"]["estado"] == "interrumpida"
    assert vista["cartera"]["juegos"]["MILOTO"]["cartera_verificada"] is True
    for texto in _paginas(c, ID_EVIDENCIA):
        assert _sin_consultas(texto) and "Interrumpido." in texto and "cartera: interrumpida" in texto
        assert "Explicación: pendiente" not in texto and "Fase: construyendo" not in texto
        assert f'href="/predicciones/miloto?cartera={clave}"' in texto
    assert f4.arbol(entorno.raiz) == antes  # el temporal y los registros quedan como evidencia
    ids = [e["id"] for e in RegistroEjecucionesArchivo(entorno.raiz / "carteras" / "operacion").listar()]
    assert len(ids) == 2 and ID_EVIDENCIA in ids  # el temporal huerfano no es una ejecucion
    p = centro.ahora("MILOTO", origen="web")
    assert p["juegos"]["MILOTO"]["estado"] == "reutilizado" and p["juegos"]["MILOTO"]["resultado"] == clave
    assert p["prediccion"]["estado"] == "exito" and p["prediccion"]["explicacion"]["estado"] == "guardada"
    for relativa, huella in antes.items():
        if ID_EVIDENCIA in relativa:
            assert f4.arbol(entorno.raiz)[relativa] == huella, relativa  # la evidencia no se reescribe


def test_una_clave_registrada_sin_cartera_publicada_no_se_ofrece(entorno):
    _, centro, c = _miloto(entorno)
    _registros_de_la_evidencia(entorno, "ab" * 32, "uniforme-v1-n3-libre-s42")
    vista = centro.ejecucion(ID_EVIDENCIA)
    assert vista["cartera"]["juegos"]["MILOTO"]["cartera_verificada"] is False
    for texto in _paginas(c, ID_EVIDENCIA):
        assert _sin_consultas(texto) and "?cartera=" + "ab" * 32 not in texto
        assert "no hay una cartera publicada y verificable" in texto


# ---------------------------------------------------------------------------
# Comando: el mismo caso de uso
# ---------------------------------------------------------------------------

def test_el_comando_informa_el_almacen_no_disponible_con_su_codigo(entorno, monkeypatch):
    carteras, centro, _ = _miloto(entorno)
    _falla_al_cerrar_el_juego(monkeypatch, carteras)
    salida, errores = io.StringIO(), io.StringIO()
    codigo = cli.ejecutar(["generar", "--juego", "MILOTO"], centro_factory=lambda: centro, salida=salida,
                          errores=errores)
    assert codigo == cli.EXIT_CONEXION
    assert "almacen" in errores.getvalue() and "Access is denied" in errores.getvalue()
    assert json.loads(salida.getvalue())["prediccion"]["estado"] == "fallo"
