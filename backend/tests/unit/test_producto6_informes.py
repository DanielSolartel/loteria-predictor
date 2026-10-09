"""Producto 6: informes guardados (fotografias verificables).

- almacen propio: JSON canonico, clave SHA-256 del contenido, publicacion
  atomica con temporal corto en la misma carpeta, nunca sobrescribe;
- misma fotografia -> el mismo informe; una distinta -> otro, sin tocar el
  anterior (byte a byte);
- alteracion detectable; un archivo alterado no se sobrescribe;
- verificacion con tres respuestas separadas: integridad, reproduccion del
  calculo congelado y coincidencia con la consulta actual;
- informe parcial con la base caida, con sus estados y limitaciones;
- los artefactos de Productos 1-5 no cambian."""
from __future__ import annotations

import json
import os

import pytest

from app.application.interfaces.resultados_store import InformeGuardado, InformeIlegible
from app.application.ml import resultados_informes as ri
from app.application.ml.registro_prospectivo import serializar_entrada
from app.application.use_cases.resultados import ResultadosError
from tests.unit import fixtures_producto6 as f6


@pytest.fixture
def miloto(tmp_path):
    e = f6.entorno(tmp_path)
    e.poblar(("MILOTO",))
    return e


def _archivos(e) -> list:
    return sorted((e.directorio / "resultados").rglob("*"))


def test_guardar_es_atomico_canonico_e_idempotente(miloto, monkeypatch):
    enlaces = []
    real = os.link

    def espia(origen, destino):
        enlaces.append((str(origen), str(destino)))
        return real(origen, destino)

    monkeypatch.setattr(os, "link", espia)
    centro = miloto.centro()
    a = centro.guardar_informe("MILOTO")
    (origen, destino), = enlaces
    assert os.path.dirname(origen) == os.path.dirname(destino)
    assert len(os.path.basename(origen)) <= 33 and os.path.basename(origen).startswith(".publicacion.")
    ruta = miloto.directorio / "resultados" / "informes" / "MILOTO" / f"{a['clave']}.json"
    assert [p for p in _archivos(miloto) if p.is_file()] == [ruta]
    contenido = ruta.read_bytes()
    artefacto = json.loads(contenido)
    assert serializar_entrada(artefacto) == contenido and ri.integro(artefacto)
    assert artefacto["clave"] == ri.huella(ri.cuerpo_de(artefacto)) == a["clave"]
    assert artefacto["contexto"]["AUTORIZA_EVALUACION"] is False and artefacto["estado_de_uso"] == "experimental_no_acreditado"
    assert "firma externa" in artefacto["nota"]
    # misma fotografia (otro reloj): el mismo informe, sin reescribir
    b = centro.guardar_informe("MILOTO")
    assert (b["clave"], b["reutilizado"]) == (a["clave"], True)
    assert ruta.read_bytes() == contenido and len(enlaces) == 1


def test_fotografia_distinta_crea_otro_y_el_anterior_queda_intacto(miloto):
    centro = miloto.centro()
    a = centro.guardar_informe("MILOTO")
    ruta_a = miloto.directorio / "resultados" / "informes" / "MILOTO" / f"{a['clave']}.json"
    antes = ruta_a.read_bytes()
    miloto.llega_el_resultado("MILOTO")
    b = centro.guardar_informe("MILOTO")
    assert b["clave"] != a["clave"] and not b["reutilizado"]
    assert ruta_a.read_bytes() == antes
    assert [i["clave"] for i in centro.informes("MILOTO")] == [b["clave"], a["clave"]]
    # el informe antiguo: integro y reproducible, pero la consulta actual ya cambio
    r = centro.verificar_informe(a["clave"])
    assert r["integridad"] == "correcta" and r["reproduccion"]["exacta"] is True
    assert r["base_actual"]["estado"] == "cambio"
    assert any(d["motivo"] == "estado_cambio" for d in r["base_actual"]["diferencias"])
    r = centro.verificar_informe(b["clave"])
    assert (r["integridad"], r["reproduccion"]["exacta"], r["base_actual"]["estado"]) == ("correcta", True, "coincide")
    assert r["reproduccion"]["emisiones_recalculadas"] == 3


def test_el_informe_conserva_lo_necesario_para_comprobar_sin_reentrenar(miloto):
    miloto.llega_el_resultado("MILOTO")
    centro = miloto.centro()
    a = centro.informe(centro.guardar_informe("MILOTO")["clave"])
    assert a["filtros"]["lineas"] == a["seleccion"] and len(a["seleccion"]) == 3
    assert a["politica"] and a["procedencias"] and a["base"]["ultimo_sorteo"] == 85
    assert {o["procedencia"] for o in a["artefactos_de_origen"]} == {"operacion", "laboratorio", "carteras"}
    for e in a["emisiones"]:
        assert e["estado"] == "incluido" and e["resultado"]["numeros"] and e["congelado"]["probabilidad"]
    # se recalcula sin la base: aunque caiga, la reproduccion es exacta
    miloto.e4.base_caida = True
    r = centro.verificar_informe(a["clave"])
    assert r["reproduccion"]["exacta"] is True and r["base_actual"]["estado"] == "no_disponible"


def test_reproduccion_detecta_un_calculo_que_no_corresponde(miloto):
    miloto.llega_el_resultado("MILOTO")
    centro = miloto.centro()
    a = centro.informe(centro.guardar_informe("MILOTO")["clave"])
    cuerpo = ri.cuerpo_de(a)
    cuerpo["emisiones"][0]["metricas"]["log_loss"] += 0.01  # sellado de nuevo: integro pero no reproducible
    falso = ri.componer(cuerpo, a["guardado"])
    assert ri.integro(falso)
    r = ri.reproducir(falso)
    assert r["exacta"] is False and {"parte": "emisiones", "motivo": "metricas_distintas", "objetivo": 85,
                                     "linea": cuerpo["emisiones"][0]["clave_linea"]} in r["diferencias"]


def test_alteracion_detectable_y_nunca_sobrescrita(miloto):
    centro = miloto.centro()
    a = centro.guardar_informe("MILOTO")
    ruta = miloto.directorio / "resultados" / "informes" / "MILOTO" / f"{a['clave']}.json"
    alterado = ruta.read_bytes().replace(b'"seguimiento"', b'"retrospectiva"', 1)
    ruta.write_bytes(alterado)
    assert isinstance(miloto.informes.obtener(a["clave"]), InformeIlegible)
    r = centro.verificar_informe(a["clave"])
    assert r["integridad"] == "alterado" and r["reproduccion"]["exacta"] is None
    with pytest.raises(ResultadosError) as error:
        centro.informe(a["clave"])
    assert error.value.codigo == "alterado"
    with pytest.raises(ResultadosError) as error:
        centro.guardar_informe("MILOTO")  # la misma fotografia: no se sobrescribe el archivo alterado
    assert error.value.codigo == "alterado" and ruta.read_bytes() == alterado
    assert centro.informes("MILOTO") == [{"clave": a["clave"], "estado": "ilegible", "integridad": "contenido_alterado"}]


def test_informe_en_la_carpeta_de_otro_juego(miloto):
    a = miloto.centro().guardar_informe("MILOTO")
    origen = miloto.directorio / "resultados" / "informes" / "MILOTO" / f"{a['clave']}.json"
    otro = miloto.directorio / "resultados" / "informes" / "BALOTO"
    otro.mkdir(parents=True)
    (otro / origen.name).write_bytes(origen.read_bytes())
    origen.unlink()
    leido = miloto.informes.obtener(a["clave"])
    assert isinstance(leido, InformeIlegible) and leido.motivo == "juego_no_coincide"


def test_almacen_rechaza_un_informe_sin_sello(tmp_path):
    from app.infrastructure.storage.resultados_file_store import ResultadosFileStore

    with pytest.raises(ValueError):
        ResultadosFileStore(tmp_path).guardar({"clave": "0" * 64, "juego": "MILOTO", "esquema": ri.ESQUEMA_INFORME})
    assert not (tmp_path / "informes").exists()


def test_informe_parcial_con_la_base_caida(miloto):
    miloto.e4.base_caida = True
    centro = miloto.centro()
    r = centro.guardar_informe("MILOTO")
    assert r["estado"] == "parcial" and any("base de datos no disponible" in l for l in r["limitaciones"])
    a = centro.informe(r["clave"])
    assert all(e["estado"] == "sin_base" for e in a["emisiones"])
    assert isinstance(miloto.informes.obtener(r["clave"]), InformeGuardado)


def test_los_artefactos_de_productos_1_a_5_no_cambian(miloto):
    carpetas = [miloto.directorio / d for d in ("p3", "laboratorio", "carteras")]
    antes = {str(c): f6.foto(c) for c in carpetas}
    centro = miloto.centro()
    centro.indice()
    a = centro.guardar_informe("MILOTO")
    miloto.llega_el_resultado("MILOTO")
    centro.consultar("MILOTO")
    centro.exportar_csv("MILOTO")
    centro.guardar_informe("MILOTO")
    centro.verificar_informe(a["clave"])
    assert {str(c): f6.foto(c) for c in carpetas} == antes
