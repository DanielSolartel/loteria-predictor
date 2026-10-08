"""Producto 5: proceso trabajador dedicado con tiempo maximo.

- comparar, vector fuente y simular corren en un proceso `spawn` (igual en
  Windows) y dan exactamente lo mismo que en este proceso;
- el proceso que atiende la web no cambia sus hilos numericos;
- tiempo agotado: el trabajador se detiene, no queda vivo y no se publica
  nada; un trabajador que muere o falla se informa como fallo;
- un trabajo de varios juegos lanza un trabajador cada vez (sin
  sobresuscripcion)."""
from __future__ import annotations

import time

import pytest
from threadpoolctl import threadpool_info

from app.application.interfaces.ejecutor_carteras import TiempoAgotadoError
from app.application.interfaces.ejecutor_laboratorio import TrabajadorFallidoError
from app.application.ml import carteras_artefactos as ca
from app.application.ml import carteras_ensemble as ce
from app.application.ml import laboratorio_variables as lv
from app.infrastructure.carteras_trabajador import EjecutorCarterasEnProceso
from tests.unit import fixtures_producto4 as f4
from tests.unit import fixtures_producto5 as f5

PROTOCOLO = ce.ProtocoloCarteras(bloques=1, perfil="reducido")


def _hilos():
    return sorted((i["internal_api"], i["num_threads"]) for i in threadpool_info())


def test_el_trabajador_da_lo_mismo_que_este_proceso_sin_cambiar_sus_hilos():
    instantanea = lv.validar_instantanea("MILOTO", f4.historico("MILOTO", 70))
    instantanea = lv.instantanea_desde_canonicos("MILOTO", lv.sorteos_canonicos(instantanea))
    ejecutor = EjecutorCarterasEnProceso(tiempo_maximo=300)
    antes = _hilos()
    avances = []
    cuerpo, tiempos = ejecutor.comparar(instantanea, PROTOCOLO, avance=lambda fase, **d: avances.append(fase))
    assert cuerpo == ce.evaluar(instantanea, PROTOCOLO)[0] and ce.ID_ENSEMBLE in tiempos
    assert {"componente", "modelo", "pesos"} <= set(avances)
    fuente = ejecutor.fuente(instantanea, ce.ID_ENSEMBLE, "reducido")
    assert fuente == ce.fuente(instantanea, ce.ID_ENSEMBLE, "reducido")
    identidad = ca.identidad_de_cartera(instantanea, ce.ID_ENSEMBLE, "reducido", 5, 1, "libre")
    elegida = ca.componer(ca.cuerpo_de_cartera(instantanea, identidad, fuente), "generacion", {})
    uniforme_id = ca.identidad_de_cartera(instantanea, "uniforme", "reducido", 5, 1, "libre")
    uniforme = ca.componer(ca.cuerpo_de_cartera(instantanea, uniforme_id, ce.fuente(instantanea, "uniforme")),
                           "generacion", {})
    sim = ca.identidad_de_simulacion(elegida, uniforme, 1000, 1)
    assert ejecutor.simular(sim, elegida, uniforme) == ca.cuerpo_de_simulacion(sim, elegida, uniforme)
    assert _hilos() == antes and ejecutor.lanzados == 3 and ejecutor.activos == 0


def test_tiempo_agotado_detiene_el_trabajador():
    vivos = []
    ejecutor = EjecutorCarterasEnProceso(tiempo_maximo=1.0, al_lanzar=vivos.append)
    inicio = time.monotonic()
    with pytest.raises(TiempoAgotadoError) as error:
        ejecutor.ejecutar_tarea({"tipo": "dormir", "segundos": 60})
    assert time.monotonic() - inicio < 30 and "tiempo maximo de 1 s" in str(error.value)
    assert "sigue vivo" not in str(error.value)
    assert not vivos[0].is_alive() and ejecutor.activos == 0
    assert isinstance(error.value, TrabajadorFallidoError)


def test_trabajador_que_falla_o_muere_es_un_fallo_informado():
    ejecutor = EjecutorCarterasEnProceso(tiempo_maximo=60)
    with pytest.raises(TrabajadorFallidoError) as error:
        ejecutor.ejecutar_tarea({"tipo": "desconocida"})
    assert "tarea no admitida" in str(error.value)
    asesino = EjecutorCarterasEnProceso(tiempo_maximo=60, al_lanzar=lambda proceso: proceso.kill())
    with pytest.raises(TrabajadorFallidoError) as error:
        asesino.ejecutar_tarea({"tipo": "dormir", "segundos": 30})
    assert "termino sin resultado" in str(error.value) and asesino.activos == 0


def test_un_trabajo_de_varios_juegos_usa_un_trabajador_cada_vez(tmp_path):
    e = f5.entorno(tmp_path, {"BALOTO": 70, "MILOTO": 70})
    ejecutor = EjecutorCarterasEnProceso(tiempo_maximo=300)
    final = e.carteras(ejecutor=ejecutor).ahora("comparacion", ["BALOTO", "MILOTO"],
                                                {"protocolo": {"bloques": 1, "perfil": "reducido"}})
    # Baloto con 70 sorteos deja fuera la receta AE-36 (necesita 150): su comparacion es parcial, no un fallo
    baloto = final["juegos"]["BALOTO"]
    assert baloto["estado"] == "parcial" and "actual_logistica_ae36" in baloto["mensaje"]
    assert final["juegos"]["MILOTO"]["estado"] == "terminado"
    assert ejecutor.lanzados == 2 and ejecutor.maximo_simultaneo == 1


def test_tiempo_agotado_en_un_juego_no_publica_y_los_demas_siguen(tmp_path):
    e = f5.entorno(tmp_path, {"MILOTO": 70, "COLORLOTO": 70})
    final = e.carteras(ejecutor=EjecutorCarterasEnProceso(tiempo_maximo=0.2)).ahora(
        "comparacion", ["MILOTO"], {"protocolo": {"bloques": 1, "perfil": "reducido"}})
    assert final["juegos"]["MILOTO"]["estado"] == "tiempo_agotado" and e.almacen.comparaciones("MILOTO") == []
    s = e.carteras(ejecutor=EjecutorCarterasEnProceso(tiempo_maximo=0.2))
    s.configurar("MILOTO", "logistica_regularizada", 5, "libre", 1, perfil="reducido")
    s.configurar("COLORLOTO", "uniforme_paleta", 5, "libre", 1)  # la uniforme no necesita trabajador
    final = s.ahora("carteras_configuradas", ["MILOTO", "COLORLOTO"])
    assert final["juegos"]["MILOTO"]["estado"] == "tiempo_agotado"
    assert final["juegos"]["COLORLOTO"]["estado"] == "terminado" and final["estado"] == "parcial"
    assert e.almacen.lineas("MILOTO") == []
