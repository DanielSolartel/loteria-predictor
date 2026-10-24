"""Fase 7: la tarjeta de cada juego es coherente con el estado global de la
ejecucion (F7-VIS-01). El caso de uso deriva `interrumpida` en lectura, sin
escribir; la pagina y el fragmento HTMX no deben seguir anunciando actividad
de un juego que se quedo `pendiente` o `en_curso`, ni tocar los juegos ya
cerrados. Datos sinteticos y SQLite aislado."""
from __future__ import annotations

import hashlib
import re

import pytest

from tests.unit.simulaciones import fixtures_fase7 as f7

VISTAS = ("", "/estado")
IDS = ["pagina", "fragmento"]


@pytest.fixture
def e(tmp_path):
    entorno = f7.entorno(tmp_path, cargar=("MILOTO",))
    yield entorno
    f7.limpiar()
    entorno.engine.dispose()


def _registros(e):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (e.operacion / "ejecuciones").glob("*.json")}


def _ver(e, s, eid, vista):
    """GET de la pagina o del fragmento; ninguna lectura reescribe registros."""
    antes = _registros(e)
    r = f7.cliente(e, servicio=s).get(f"/simulaciones/ejecuciones/{eid}{vista}")
    assert r.status_code == 200 and _registros(e) == antes
    return r.text


def _tarjeta(html, codigo="miloto"):
    inicio = html.index(f'id="progreso-{codigo}"')
    fin = html.find('id="progreso-', inicio + 1)
    return html[inicio:fin if fin != -1 else len(html)]


def _badge(tarjeta):
    return re.search(r'<span class="badge [^"]*">([^<]*)</span>', tarjeta).group(1)


def _con_avance(s):
    """Registro tal como lo deja el trabajador al 40 % de un millon."""
    inicio = s.iniciar("MILOTO", 1_000_000, 20261024)
    inicio.ejecucion["juegos"]["MILOTO"].update(estado="en_curso", fase="simulando", hechas=400_000, de=1_000_000)
    s._registro.guardar(inicio.ejecucion)
    return inicio


@pytest.mark.parametrize("vista", VISTAS, ids=IDS)
def test_interrumpida_con_avance_no_anuncia_actividad(e, vista):
    s = e.servicio()
    inicio = _con_avance(s)
    inicio.cerrojos.liberar()  # el trabajador desaparece tras registrar avance
    html = _ver(e, s, inicio.ejecucion["id"], vista)
    t = _tarjeta(html)
    assert "Interrumpida." in html and "hx-get" not in html
    assert _badge(t) == "interrumpido"
    assert "Simulando" not in t and 'role="progressbar"' not in t and "en curso" not in t
    assert "Último avance registrado antes de la interrupción: 400.000 de 1.000.000 (40,0 %)" in t
    assert s._registro.obtener(inicio.ejecucion["id"])["juegos"]["MILOTO"]["estado"] == "en_curso"  # sin persistir


@pytest.mark.parametrize("vista", VISTAS, ids=IDS)
def test_interrumpida_antes_de_empezar_no_queda_pendiente(e, vista):
    s = e.servicio()
    inicio = s.iniciar("MILOTO", 100, 20261024)
    inicio.cerrojos.liberar()
    html = _ver(e, s, inicio.ejecucion["id"], vista)
    t = _tarjeta(html)
    assert "Interrumpida." in html and "hx-get" not in html
    assert _badge(t) == "interrumpido" and "pendiente" not in t and "Último avance" not in t
    assert s._registro.obtener(inicio.ejecucion["id"])["juegos"]["MILOTO"]["estado"] == "pendiente"


@pytest.mark.parametrize("vista", VISTAS, ids=IDS)
def test_trabajo_vivo_conserva_actividad_y_sondeo(e, vista):
    s = e.servicio()
    inicio = _con_avance(s)
    try:
        html = _ver(e, s, inicio.ejecucion["id"], vista)
    finally:
        inicio.cerrojos.liberar()
    t = _tarjeta(html)
    assert "hx-get" in html and "Interrumpida." not in html
    assert _badge(t) == "en curso" and 'role="progressbar"' in t
    assert "Simulando: 400.000 de 1.000.000 (40,0 %)" in t and "Último avance" not in t


@pytest.mark.parametrize("vista", VISTAS, ids=IDS)
def test_terminado_y_reutilizado_sin_cambios(e, vista):
    s = e.servicio()
    terminada, reutilizada = s.ahora("MILOTO", 100, 1), s.ahora("MILOTO", 100, 1)
    for ejecucion, texto in ((terminada, "terminada"), (reutilizada, "resultado ya existente")):
        html = _ver(e, s, ejecucion["id"], vista)
        t = _tarjeta(html)
        assert "hx-get" not in html and _badge(t) == texto and "interrumpid" not in t
        assert f'href="/simulaciones/resultados/{ejecucion["juegos"]["MILOTO"]["resultado"]}"' in t


@pytest.mark.parametrize("vista", VISTAS, ids=IDS)
def test_un_juego_cerrado_no_pasa_a_interrumpido_por_otro(e, vista):
    """Registro sintetico con dos juegos (el caso de uso lanza uno por
    ejecucion): solo comprueba la regla de la plantilla."""
    s = e.servicio()
    hecha = s.ahora("MILOTO", 100, 1)["juegos"]["MILOTO"]
    inicio = s.iniciar("BALOTO", 100, 1)
    inicio.ejecucion.update(orden=["MILOTO", "BALOTO"], juegos={
        "MILOTO": hecha, "BALOTO": {"juego": "BALOTO", "estado": "en_curso", "fase": "obteniendo_datos"}})
    s._registro.guardar(inicio.ejecucion)
    inicio.cerrojos.liberar()
    html = _ver(e, s, inicio.ejecucion["id"], vista)
    miloto, baloto = _tarjeta(html, "miloto"), _tarjeta(html, "baloto")
    assert "Interrumpida." in html and "hx-get" not in html
    assert _badge(miloto) == "terminada" and f'href="/simulaciones/resultados/{hecha["resultado"]}"' in miloto
    assert _badge(baloto) == "interrumpido" and "Obteniendo" not in baloto
