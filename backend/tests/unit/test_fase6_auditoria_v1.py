"""Regresiones de la auditoría de la entrega 9.2 v1 (Fase 6, horario). Fallan sobre v1 por el
comportamiento señalado y pasan con la corrección v2. No necesitan PowerShell: las baterías del
controlador con PowerShell real están en `test_fase6_tarea_windows.py`.

- F92-HOR-01: la admisión programada se confirma en el borde real de la consulta al proveedor. Si la
  preparación (recursos, instantánea, configuración) cruza el fin del slot admitido (cierre de la franja,
  de la recuperación o paso al slot siguiente), no se inicia `sincronizar`, no se consume otro slot y se
  conservan la espera y los fallos anteriores.
- F92-PS-01, guarda estática: ninguna función del controlador asigna una variable cuyo nombre solo
  difiere en mayúsculas de un valor del script que esa misma función lee (PowerShell no las distingue).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.application import operacion_horario as h
from tests.unit.test_fase6_horario import MAXIMO, POLITICA, _programado, _servicio, bogota

BACKEND = Path(__file__).resolve().parents[2]
CONTROLADORES = (BACKEND / "scripts/windows/fase6_tarea.ps1", BACKEND / "tests/ensayar_tarea_fase6_windows.ps1")


def _demorar(proveedor, reloj, despues, paso="configuracion"):
    """La preparación termina en `despues`: el reloj avanza en el paso indicado, antes de consultar."""
    consultas = []

    def hook(juego, nombre):
        if nombre == paso:
            reloj.ahora = despues
        if nombre == "sincronizar":
            consultas.append(reloj.ahora)
    proveedor.hook = hook
    return consultas


@pytest.mark.parametrize("caso, admision, fin_preparacion, juego", [
    ("fin_de_franja", bogota(30, 1, 59), bogota(30, 2, 1), "MILOTO"),  # franja del jueves hasta 02:00
    ("fin_de_recuperacion", bogota(30, 9, 14, 59), bogota(30, 9, 15, 1), "MILOTO"),  # 09:00-09:15
    ("cambio_de_slot", bogota(26, 23, 44, 59), bogota(26, 23, 45, 1), "BALOTO"),  # slot 23:30 -> 23:45
])
def test_la_preparacion_que_cruza_el_fin_del_slot_no_inicia_la_consulta(tmp_path, caso, admision,
                                                                       fin_preparacion, juego):
    op, almacen, p, reloj = _servicio(tmp_path, admision)
    almacen.actualizar_configuracion({"juegos": [juego]})
    consultas = _demorar(p, reloj, fin_preparacion)
    e = _programado(op)
    assert consultas == [], f"{caso}: la consulta empezó después del cierre del slot admitido"
    assert (juego, "sincronizar") not in p.llamadas and (juego, "configuracion") in p.llamadas
    r = e["juegos"][juego]
    assert r["estado"] == "omitido_horario" and r["horario"]["consulta"] == "no_iniciada"
    assert r["horario"]["motivo"] == "cierre_antes_de_consultar"
    assert r["horario"]["oportunidad"] == h.decidir(POLITICA, juego, admision, {}, max_reintentos=MAXIMO
                                                    ).oportunidad.isoformat()
    assert e["estado"] == "sin_consultas_debidas"
    assert almacen.estado(juego)["estado"] == "omitido_horario"


def test_el_slot_siguiente_no_queda_consumido_por_la_demora(tmp_path):
    op, almacen, p, reloj = _servicio(tmp_path, bogota(26, 23, 44, 59))
    almacen.actualizar_configuracion({"juegos": ["BALOTO"]})
    _demorar(p, reloj, bogota(26, 23, 45, 1))
    _programado(op)
    p.hook, p.llamadas[:] = None, []
    reloj.ahora = bogota(26, 23, 45, 30)  # el disparo del slot 23:45
    e = _programado(op)
    assert ("BALOTO", "sincronizar") in p.llamadas
    assert almacen.estado("BALOTO")["horario"]["oportunidad"] == bogota(26, 23, 45).isoformat()
    assert e["juegos"]["BALOTO"]["estado"] != "omitido_horario"


def test_tras_el_cierre_el_evento_sigue_pendiente_para_la_recuperacion(tmp_path):
    op, almacen, p, reloj = _servicio(tmp_path, bogota(30, 1, 59))
    almacen.actualizar_configuracion({"juegos": ["MILOTO"]})
    _demorar(p, reloj, bogota(30, 2, 1))
    _programado(op)
    p.hook, p.llamadas[:] = None, []
    reloj.ahora = bogota(30, 9, 0)
    e = _programado(op)
    assert ("MILOTO", "sincronizar") in p.llamadas and e["juegos"]["MILOTO"]["estado"] == "correcto"


def test_la_omision_en_el_borde_conserva_la_espera_y_los_fallos_anteriores(tmp_path):
    op, almacen, p, reloj = _servicio(tmp_path, bogota(30, 1, 59))
    almacen.actualizar_configuracion({"juegos": ["MILOTO"]})
    error = {"paso": "sincronizacion", "tipo": "ConnectionError", "mensaje": "sin conexion"}
    almacen.guardar_estado("MILOTO", {"codigo": "MILOTO", "estado": "fallo_consulta", "error": error,
                                      "fallos_consecutivos": 2, "proxima_consulta": bogota(30, 1, 30).isoformat(),
                                      "ultima_comprobacion": bogota(30, 1, 20).isoformat()})
    _demorar(p, reloj, bogota(30, 2, 1))
    _programado(op)
    estado = almacen.estado("MILOTO")
    assert ("MILOTO", "sincronizar") not in p.llamadas
    assert estado["fallos_consecutivos"] == 2 and estado["error"] == error
    assert estado["proxima_consulta"] == bogota(30, 1, 30).isoformat()


def test_una_demora_dentro_del_mismo_slot_si_consulta(tmp_path):
    op, almacen, p, reloj = _servicio(tmp_path, bogota(30, 1, 50))
    almacen.actualizar_configuracion({"juegos": ["MILOTO"]})
    consultas = _demorar(p, reloj, bogota(30, 1, 59, 59))
    e = _programado(op)
    assert consultas == [bogota(30, 1, 59, 59)] and e["juegos"]["MILOTO"]["estado"] == "correcto"


def test_la_comprobacion_manual_no_depende_del_horario(tmp_path):
    op, almacen, p, reloj = _servicio(tmp_path, bogota(30, 1, 59))
    almacen.actualizar_configuracion({"juegos": ["MILOTO"]})
    consultas = _demorar(p, reloj, bogota(30, 2, 1))
    op.ciclo(juegos=["MILOTO"], forzar=True, origen="comando")
    assert consultas == [bogota(30, 2, 1)]


def test_confirmar_solo_admite_el_mismo_slot_abierto():
    admitida = h.decidir(POLITICA, "MILOTO", bogota(30, 1, 59), {}, max_reintentos=MAXIMO)
    assert admitida.admitido
    mismo = h.confirmar(POLITICA, admitida, bogota(30, 1, 59, 59), {}, max_reintentos=MAXIMO)
    assert mismo.admitido and mismo.oportunidad == admitida.oportunidad
    cerrado = h.confirmar(POLITICA, admitida, bogota(30, 2, 0), {}, max_reintentos=MAXIMO)
    assert not cerrado.admitido and cerrado.motivo == "cierre_antes_de_consultar"
    otro = h.decidir(POLITICA, "BALOTO", bogota(26, 23, 44), {}, max_reintentos=MAXIMO)
    siguiente = h.confirmar(POLITICA, otro, bogota(26, 23, 45), {}, max_reintentos=MAXIMO)
    assert not siguiente.admitido and siguiente.motivo == "cierre_antes_de_consultar"
    with pytest.raises(ValueError):
        h.confirmar(POLITICA, cerrado, bogota(30, 1, 59), {}, max_reintentos=MAXIMO)


# ---------------------------------------------------------------------------
# F92-PS-01: guarda estática contra variables que solo difieren en mayúsculas
# ---------------------------------------------------------------------------

_VARIABLE = re.compile(r"\$(?:(?:script|global|local):)?([A-Za-z_][A-Za-z0-9_]*)")
_ASIGNACION = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)\s*[+-]?=(?!=)")


def _funciones(texto):
    """Cuerpos de las funciones de nivel superior y el resto del script (llaves equilibradas por línea)."""
    lineas, funciones, fuera, i = texto.split("\n"), {}, [], 0
    while i < len(lineas):
        m = re.match(r"function ([A-Za-z-]+)", lineas[i])
        if not m:
            fuera.append(lineas[i])
            i += 1
            continue
        profundidad, cuerpo = 0, []
        while True:
            cuerpo.append(lineas[i])
            profundidad += lineas[i].count("{") - lineas[i].count("}")
            i += 1
            if profundidad == 0 and "{" in "".join(cuerpo):
                break
        funciones[m.group(1)] = "\n".join(cuerpo)
    return funciones, "\n".join(fuera)


def _sombras(texto):
    funciones, fuera = _funciones(texto)
    del_script = {}
    parametros = re.search(r"param\((.*?)\n\)", texto, re.S)
    for nombre in _ASIGNACION.findall(fuera) + _VARIABLE.findall(parametros.group(1) if parametros else ""):
        del_script.setdefault(nombre.lower(), set()).add(nombre)
    sombras = []
    for funcion, cuerpo in funciones.items():
        leidas = set(_VARIABLE.findall(cuerpo))
        for local in set(_ASIGNACION.findall(cuerpo)):
            sombras += [(funcion, local, s) for s in del_script.get(local.lower(), ()) if s != local and s in leidas]
    return funciones, sombras


@pytest.mark.parametrize("ruta", CONTROLADORES, ids=lambda p: p.name)
def test_ninguna_funcion_sombrea_un_valor_del_script_que_tambien_lee(ruta):
    funciones, sombras = _sombras(ruta.read_text(encoding="utf-8-sig"))
    assert funciones, "el analizador no encontró funciones"
    assert sombras == [], f"variables que PowerShell confunde (función, local, del script): {sombras}"


def test_el_analizador_detecta_la_colision_de_la_v1():
    """Control negativo: el patrón exacto de v1 (`$NS` del script y `$ns` local en la misma función)."""
    v1 = ("$NS = 'urn:x'\nfunction Assert-Hijos([xml]$Documento) {\n"
          "    $ns = New-Object Xml.XmlNamespaceManager($Documento.NameTable); $ns.AddNamespace('t',$NS)\n}\n")
    assert _sombras(v1)[1] == [("Assert-Hijos", "ns", "NS")]
    assert "Assert-DocumentoPropio" in _funciones(CONTROLADORES[0].read_text(encoding="utf-8-sig"))[0]
