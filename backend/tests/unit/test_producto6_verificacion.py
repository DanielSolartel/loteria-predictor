"""Producto 6: verificacion de informes guardados frente a falsos positivos.

Regresiones de la revision de la entrega v1:
- un resultado observado distinto con las MISMAS perdidas (fuente uniforme:
  cualquier combinacion pierde lo mismo y el vector no tiene sugerencia
  propia) no puede verificarse como «coincide» con la consulta actual;
- la reproduccion exacta tiene que recalcular tambien los aciertos, los
  resumenes y la comparacion de las CARTERAS, con las combinaciones y el
  resultado congelados en el informe;
- un cambio actual de resultado o de estado de una cartera elegida se
  informa como cambio aunque el vector fuente no cambie.

Controles: resultado identico (tambien en otro orden), base no disponible,
ColorLoto (el orden de los pares no cambia el multiconjunto; la
multiplicidad, si) e informes del formato anterior (sin combinaciones
congeladas: sus carteras no son verificables, sin atribuirles exactitud)."""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from app.application.ml import resultados_informes as ri
from app.application.use_cases.resultados import Filtros
from tests.unit import fixtures_producto6 as f6

SOLO_CARTERAS = Filtros(procedencias=("carteras",))
DOCS = Path(__file__).resolve().parents[2] / "docs"


def _uniforme(tmp_path, juego: str):
    """Carteras con fuente uniforme (Producto 5) y el resultado del objetivo ya cargado."""
    e = f6.entorno(tmp_path)
    modelo = "uniforme_paleta" if juego == "COLORLOTO" else "uniforme"
    servicio = e.e5.carteras()
    for cantidad in (3, 2):
        r = servicio.ahora("cartera", [juego], {"modelo": modelo, "perfil": "reducido", "cantidad": cantidad,
                                                "semilla": 42, "diversidad": "libre"})["juegos"][juego]
        assert r["estado"] in ("terminado", "reutilizado"), r
    e.llega_el_resultado(juego)
    return e


def _cambiar_resultado(e, juego: str, **cambios):
    """Corrige SOLO el sorteo del objetivo (el ultimo cargado); el historico hasta el corte no cambia."""
    j = e.e4.juegos.obtener_por_codigo(juego)
    lista = e.e4.resultados.colorloto if juego == "COLORLOTO" else e.e4.resultados.numericos
    i = max(range(len(lista[j.id])), key=lambda k: lista[j.id][k].numero_sorteo)
    anterior = lista[j.id][i]
    lista[j.id][i] = dataclasses.replace(anterior, **cambios)
    return anterior


def _guardar(e, juego):
    centro = e.centro()
    clave = centro.guardar_informe(juego, SOLO_CARTERAS)["clave"]
    return centro, clave


# ---------------------------------------------------------------------------
# 1. Resultado cambiado con las mismas perdidas
# ---------------------------------------------------------------------------

def test_resultado_cambiado_con_fuente_uniforme_no_coincide(tmp_path):
    e = _uniforme(tmp_path, "MILOTO")
    centro, clave = _guardar(e, "MILOTO")
    antes = centro.consultar("MILOTO", SOLO_CARTERAS, completa=True)["emisiones_de_la_seleccion"]
    anterior = _cambiar_resultado(e, "MILOTO", numeros=(6, 7, 8, 9, 10))
    assert set(anterior.numeros) != {6, 7, 8, 9, 10}
    despues = centro.consultar("MILOTO", SOLO_CARTERAS, completa=True)["emisiones_de_la_seleccion"]
    # la premisa del falso positivo: mismo identificador, estado, historico y aciertos, y las mismas perdidas del
    # vector a la tolerancia de comparacion (solo cambia el orden de la suma en el ultimo bit)
    assert [(f["identificador"], f["estado"], f["historico"], f["aciertos"]) for f in antes] == \
        [(f["identificador"], f["estado"], f["historico"], f["aciertos"]) for f in despues]
    assert all(ri._iguales(x["metricas"], y["metricas"]) for x, y in zip(antes, despues))
    r = centro.verificar_informe(clave)
    assert r["integridad"] == "correcta" and r["reproduccion"]["exacta"] is True
    assert r["base_actual"]["estado"] == "cambio"
    motivos = {(d.get("seccion"), d["motivo"]) for d in r["base_actual"]["diferencias"]}
    assert ("emisiones", "resultado_observado_cambio") in motivos
    assert ("carteras", "resultado_observado_cambio") in motivos


def test_resultado_identico_y_en_otro_orden_coincide(tmp_path):
    e = _uniforme(tmp_path, "MILOTO")
    centro, clave = _guardar(e, "MILOTO")
    assert centro.verificar_informe(clave)["base_actual"]["estado"] == "coincide"
    anterior = _cambiar_resultado(e, "MILOTO", numeros=tuple(reversed(e.e4.cargados("MILOTO")[-1].numeros)))
    assert list(anterior.numeros) != list(e.e4.cargados("MILOTO")[-1].numeros)
    r = centro.verificar_informe(clave)
    assert r["base_actual"] == {"estado": "coincide", "diferencias": [], "motivo": None}


def test_base_no_disponible_no_es_coincidencia(tmp_path):
    e = _uniforme(tmp_path, "MILOTO")
    centro, clave = _guardar(e, "MILOTO")
    e.e4.base_caida = True
    r = centro.verificar_informe(clave)
    assert r["integridad"] == "correcta" and r["reproduccion"]["exacta"] is True
    assert r["base_actual"]["estado"] == "no_disponible" and r["base_actual"]["estado"] != "coincide"


def _otros_pares(pares):
    """Otros pares de la misma paleta con el MISMO patron de multiplicidades (misma perdida uniforme)."""
    return tuple(((n % 7) + 1, color) for n, color in pares)


def test_colorloto_cambio_de_pares_orden_y_multiplicidad(tmp_path):
    e = _uniforme(tmp_path, "COLORLOTO")
    centro, clave = _guardar(e, "COLORLOTO")
    original = e.e4.cargados("COLORLOTO")[-1].pares
    # otro orden de los mismos pares: el mismo multiconjunto
    _cambiar_resultado(e, "COLORLOTO", pares=tuple(reversed(original)))
    assert centro.verificar_informe(clave)["base_actual"]["estado"] == "coincide"
    # otros pares con las mismas multiplicidades: mismas perdidas uniformes, otro sorteo
    _cambiar_resultado(e, "COLORLOTO", pares=_otros_pares(original))
    r = centro.verificar_informe(clave)
    assert r["reproduccion"]["exacta"] is True and r["base_actual"]["estado"] == "cambio"
    assert any(d["motivo"] == "resultado_observado_cambio" for d in r["base_actual"]["diferencias"])
    # misma lista de pares distintos pero otra multiplicidad: tambien es otro sorteo
    repetido = (original[0], original[0], *original[2:])
    if sorted(map(tuple, repetido)) != sorted(map(tuple, original)):
        _cambiar_resultado(e, "COLORLOTO", pares=repetido)
        assert centro.verificar_informe(clave)["base_actual"]["estado"] == "cambio"


# ---------------------------------------------------------------------------
# 2. Reproduccion de los calculos de las carteras
# ---------------------------------------------------------------------------

@pytest.fixture
def con_carteras(tmp_path):
    e = f6.entorno(tmp_path)
    e.poblar(("MILOTO",))
    e.llega_el_resultado("MILOTO")
    centro = e.centro()
    a = centro.informe(centro.guardar_informe("MILOTO")["clave"])
    assert a["calculos"]["carteras"]["lineas"]
    return e, centro, a


def _recompuesto(a: dict, cambio) -> dict:
    cuerpo = ri.cuerpo_de(a)
    cambio(cuerpo["calculos"]["carteras"])
    falso = ri.componer(cuerpo, a["guardado"])
    assert ri.integro(falso)  # integro: el fallo es del calculo, no del archivo
    return falso


def test_reproduccion_detecta_un_resumen_de_cartera_incoherente(con_carteras):
    _, _, a = con_carteras
    assert ri.reproducir(a)["exacta"] is True

    def cambio(carteras):
        linea = sorted(carteras["lineas"])[0]
        carteras["lineas"][linea]["resumen"]["maximo_medio"] = 999
    r = ri.reproducir(_recompuesto(a, cambio))
    assert r["exacta"] is False
    assert any(d["motivo"] == "resumen_de_cartera_distinto" for d in r["diferencias"]), r["diferencias"]


def test_reproduccion_detecta_un_acierto_de_cartera_incoherente(con_carteras):
    _, _, a = con_carteras

    def cambio(carteras):
        linea = sorted(carteras["lineas"])[0]
        fila = next(f for f in carteras["lineas"][linea]["filas"] if f["estado"] == "incluido")
        fila["aciertos"]["maximo"] += 1
    r = ri.reproducir(_recompuesto(a, cambio))
    assert r["exacta"] is False
    assert any(d["motivo"] == "aciertos_de_cartera_distintos" for d in r["diferencias"]), r["diferencias"]


def test_reproduccion_detecta_una_comparacion_de_carteras_incoherente(con_carteras):
    _, _, a = con_carteras

    def cambio(carteras):
        carteras["comparacion"]["grupos"][0]["estado"] = "con_muestra_comun"
    r = ri.reproducir(_recompuesto(a, cambio))
    assert r["exacta"] is False
    assert any(d["motivo"] == "comparacion_de_carteras_distinta" for d in r["diferencias"]), r["diferencias"]


def test_el_informe_congela_lo_necesario_para_recalcular_las_carteras(con_carteras):
    e, centro, a = con_carteras
    for linea, c in a["calculos"]["carteras"]["lineas"].items():
        for f in c["filas"]:
            if f["estado"] == "incluido":
                assert f["congelado"]["combinaciones"] and f["resultado"]["numeros"]
    # sin base ni almacenes de Producto 5: la reproduccion sigue siendo exacta
    import shutil
    shutil.rmtree(e.directorio / "carteras")
    e.e4.base_caida = True
    r = centro.verificar_informe(a["clave"])
    assert r["reproduccion"]["exacta"] is True and r["reproduccion"]["partes"]["carteras"] == "exacta"
    # sin base (y con las carteras fijadas ya inexistentes) nunca hay coincidencia
    assert r["base_actual"]["estado"] in ("no_disponible", "no_comparable")


def test_cambio_actual_de_estado_de_una_cartera_se_informa(tmp_path):
    e = f6.entorno(tmp_path)
    e.poblar(("MILOTO",))
    centro = e.centro()
    clave = centro.guardar_informe("MILOTO")["clave"]  # objetivo pendiente
    e.llega_el_resultado("MILOTO")
    r = centro.verificar_informe(clave)
    carteras = [d for d in r["base_actual"]["diferencias"] if d.get("seccion") == "carteras"]
    assert r["base_actual"]["estado"] == "cambio" and carteras
    assert {d["motivo"] for d in carteras} == {"estado_cambio"}


def test_carteras_ilegibles_ahora_no_son_coincidencia(con_carteras):
    e, centro, a = con_carteras

    class CarterasCaidas:
        def lineas(self, juego):
            raise OSError("disco no disponible")

        def carteras(self, juego, linea):
            raise OSError("disco no disponible")

    otro = f6.CentroDeResultados(e.e3.almacen, e.e4.almacen, CarterasCaidas(), e.informes, e.e4.abrir)
    r = otro.verificar_informe(a["clave"])
    assert r["reproduccion"]["exacta"] is True
    assert r["base_actual"]["estado"] in ("no_comparable", "cambio") and r["base_actual"]["estado"] != "coincide"


def test_informe_del_formato_anterior_se_lee_sin_atribuirle_carteras_exactas(con_carteras):
    _, _, a = con_carteras
    cuerpo = ri.cuerpo_de(a)
    cuerpo["esquema"], cuerpo["implementacion"] = "resultados-informe/1", "producto6-1"
    for c in cuerpo["calculos"]["carteras"]["lineas"].values():
        for f in c["filas"]:
            f.pop("congelado", None)
    anterior = ri.componer(cuerpo, a["guardado"])
    assert ri.integro(anterior)
    r = ri.reproducir(anterior)
    assert r["partes"]["carteras"] == "no_verificable" and r["exacta"] is False
    assert r["estado"] == "parcial" and r["partes"]["emisiones"] == "exacta"


# ---------------------------------------------------------------------------
# 3. Guia de Windows sin marcadores que PowerShell rechaza
# ---------------------------------------------------------------------------

def test_guia_windows_sin_marcadores_en_los_bloques_powershell():
    texto = (DOCS / "producto6_windows.md").read_text(encoding="utf-8")
    bloques = re.findall(r"```powershell\n(.*?)```", texto, flags=re.S)
    assert bloques
    for bloque in bloques:
        assert not re.search(r"<[A-Za-z][^>\n]*>", bloque), bloque


# ---------------------------------------------------------------------------
# Comando: codigos segun el contrato; informes guardados intactos
# ---------------------------------------------------------------------------

def _cli(centro, *argv):
    import io

    from scripts import resultados_modelos as cli
    salida, errores = io.StringIO(), io.StringIO()
    return cli.ejecutar(list(argv), centro_factory=lambda: centro, salida=salida, errores=errores), errores.getvalue()


def test_comando_verificar_codigos_por_parte(con_carteras):
    from scripts import resultados_modelos as cli

    e, centro, a = con_carteras
    assert _cli(centro, "verificar", "--clave", a["clave"])[0] == cli.EXIT_OK
    # un informe integro con un calculo de cartera incoherente: reproduccion no exacta (7)
    def cambio(carteras):
        linea = sorted(carteras["lineas"])[0]
        carteras["lineas"][linea]["resumen"]["maximo_medio"] = 999
    falso = _recompuesto(a, cambio)
    e.informes.guardar(falso)
    codigo, errores = _cli(centro, "verificar", "--clave", falso["clave"])
    assert codigo == cli.EXIT_REPRODUCCION and "resumen_de_cartera_distinto" in errores
    # un informe del formato anterior: integro, carteras no verificables (5, no es una alteracion)
    cuerpo = ri.cuerpo_de(a)
    cuerpo["esquema"], cuerpo["implementacion"] = "resultados-informe/1", "producto6-1"
    for c in cuerpo["calculos"]["carteras"]["lineas"].values():
        for f in c["filas"]:
            f.pop("congelado", None)
    anterior = ri.componer(cuerpo, a["guardado"])
    e.informes.guardar(anterior)
    codigo, errores = _cli(centro, "verificar", "--clave", anterior["clave"])
    assert codigo == cli.EXIT_PARCIAL and "carteras" in errores


def test_informes_guardados_quedan_intactos_byte_a_byte(con_carteras):
    e, centro, a = con_carteras
    cuerpo = ri.cuerpo_de(a)
    cuerpo["esquema"], cuerpo["implementacion"] = "resultados-informe/1", "producto6-1"
    anterior = ri.componer(cuerpo, a["guardado"])
    e.informes.guardar(anterior)
    antes = f6.foto(e.directorio / "resultados")
    assert len(antes) == 2
    for clave in (a["clave"], anterior["clave"]):
        centro.verificar_informe(clave)
        centro.informe(clave)
    e.llega_el_resultado("MILOTO", semilla=7)
    centro.verificar_informe(anterior["clave"])
    assert [i["integridad"] for i in centro.informes("MILOTO")] == ["correcta", "correcta"]
    assert f6.foto(e.directorio / "resultados") == antes
