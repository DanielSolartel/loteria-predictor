"""Fase 7: proceso trabajador REAL (`spawn`, igual en Windows y Linux):
mismo contenido que en el proceso que llama, progreso por la cola, tiempo
maximo, muerte del hijo y errores tipados. Historicos sinteticos."""
from __future__ import annotations

import pytest

from app.application.fase7 import artefacto as fa
from app.application.fase7 import motor as fm
from app.application.interfaces.ejecutor_simulaciones import TiempoAgotadoError, TrabajadorFallidoError
from app.application.ml import laboratorio_variables as lv
from app.infrastructure.simulaciones_trabajador import EjecutorSimulacionesEnProceso
from tests.unit import fixtures_producto1 as fx


def _canonicos(juego, n):
    datos = fx.historico_colorloto(n) if juego == "COLORLOTO" else fx.historico_numerico(juego, n)
    return lv.sorteos_canonicos(lv.validar_instantanea(juego, datos))


@pytest.mark.parametrize("juego", ["BALOTO", "COLORLOTO"])
def test_proceso_trabajador_da_el_mismo_contenido_que_en_el_proceso(juego):
    sorteos = _canonicos(juego, 40)
    avances = []
    ejecutor = EjecutorSimulacionesEnProceso(tiempo_maximo=300)
    remoto = ejecutor.simular(juego, sorteos, 1_000, 7, avance=lambda fase, **d: avances.append((fase, d)))
    local = fm.calcular(juego, sorteos, 1_000, 7)
    assert fa.sha256(remoto["contenido"]) == fa.sha256(local["contenido"])
    assert remoto["historico_sha256"] == local["historico_sha256"]
    assert avances and avances[-1] == ("simulando", {"hechas": 1_000, "de": 1_000})
    assert ejecutor.lanzados == 1 and ejecutor.activos == 0


def test_tiempo_maximo_detiene_el_proceso():
    ejecutor = EjecutorSimulacionesEnProceso(tiempo_maximo=1)
    with pytest.raises(TiempoAgotadoError, match="tiempo maximo de 1 s"):
        ejecutor.ejecutar_tarea({"tipo": "dormir", "segundos": 60})
    assert ejecutor.activos == 0


def test_hijo_que_muere_sin_resultado():
    with pytest.raises(TrabajadorFallidoError, match="codigo de salida 3"):
        EjecutorSimulacionesEnProceso(tiempo_maximo=60).ejecutar_tarea({"tipo": "terminar"})


def test_errores_tipados_atraviesan_el_proceso():
    ejecutor = EjecutorSimulacionesEnProceso(tiempo_maximo=120)
    with pytest.raises(fm.MuestraInsuficienteFase7):
        ejecutor.simular("MILOTO", _canonicos("MILOTO", 1), 100, 1)
    with pytest.raises(fm.SimulacionFase7NoValida):
        ejecutor.simular("MILOTO", _canonicos("MILOTO", 5), 5_000, 1)
    with pytest.raises(TrabajadorFallidoError, match="tarea no admitida"):
        ejecutor.ejecutar_tarea({"tipo": "otra"})
