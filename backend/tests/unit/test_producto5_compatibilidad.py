"""Producto 5: compatibilidad, configuracion por entorno e impresion.

- Productos 1-4 no cambian: sus archivos quedan byte a byte, una copia del
  almacen de Producto 4 se lee y verifica igual, el rendimiento de Producto 3
  y el seguimiento del laboratorio eligen la misma primera emision, y una
  configuracion de carteras no cambia los modelos de Producto 3;
- variables de entorno: valores por defecto (limpiando solo las pertinentes)
  y prioridad real frente a `.env`;
- CSS de impresion limitado a las clases `carteras-*` de las paginas nuevas,
  sin tocar las reglas anteriores; la primera pagina de una cartera muestra
  juego, objetivo, combinaciones y un aviso breve."""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

import pytest

from app.application.ml import laboratorio_evaluacion as le
from app.application.ml.registro_prospectivo import serializar_entrada
from app.application.ml import carteras_artefactos as ca
from app.application.use_cases.rendimiento import ConsultarRendimiento
from app.core.config import Settings
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from tests.unit import fixtures_producto3 as f3
from tests.unit import fixtures_producto4 as f4
from tests.unit import fixtures_producto5 as f5

RAIZ = Path(__file__).resolve().parents[2]
VARIABLES = ("DIRECTORIO_CARTERAS_MODELOS", "TIEMPO_MAXIMO_TRABAJADOR_CARTERAS")


def _huellas(directorio):
    return {str(p.relative_to(directorio)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(directorio).rglob("*")) if p.is_file()}


@pytest.fixture
def productos(tmp_path):
    """Pronosticos de Productos 1-3 (operacion diaria con fixtures), un
    laboratorio de Producto 4 con un pronostico y carteras de Producto 5, todo
    sobre los mismos repositorios en memoria."""
    e3 = f3.entorno(tmp_path / "p3")
    assert e3.operacion().ejecutar_ahora(["BALOTO", "MILOTO", "COLORLOTO"], "local", "prueba")["estado"] == "exito"
    e4 = f4.Entorno(e3.juegos, e3.resultados, e3.historicos, tmp_path / "laboratorio")
    lab = e4.laboratorio()
    r = lab.comparar_ahora(["MILOTO"], le.Protocolo(bloques=1, perfil="reducido"))["juegos"]["MILOTO"]
    lab.generar(r["experimento"], "logistica_regularizada")
    e5 = f5.Entorno(e3.juegos, e3.resultados, e3.historicos, tmp_path / "carteras")
    yield e3, e4, lab, e5
    f3.limpiar()


def _usar_producto5(e5):
    s = e5.carteras()
    s.ahora("comparacion", ["MILOTO"], {"protocolo": {"bloques": 1, "perfil": "reducido"}})
    for juego, modelo in (("BALOTO", "logistica_regularizada"), ("MILOTO", "ensemble_temporal"),
                          ("COLORLOTO", "uniforme_paleta")):
        r = s.ahora("cartera", [juego], {"modelo": modelo, "perfil": "reducido", "cantidad": 5, "semilla": 42,
                                         "diversidad": "libre"})["juegos"][juego]
        assert r["estado"] == "terminado", f5.detalle(r)
        s.ahora("simulacion", [juego], {"cartera": r["resultado"], "simulaciones": 1000, "semilla": 1})
    s.configurar("BALOTO", "ensemble_temporal", 5, "limitada", 42)
    s.configurar("MILOTO", "hgb_clasificador", 3, "libre", 7)
    return s


def test_productos_1_a_4_quedan_byte_a_byte(productos):
    e3, e4, lab, e5 = productos
    antes = {"p1_p2": _huellas(e3.almacen._directorio), "operacion": _huellas(e3.directorio_operacion),
             "laboratorio": _huellas(e4.directorio)}
    assert all(antes.values())
    _usar_producto5(e5)
    assert _huellas(e3.almacen._directorio) == antes["p1_p2"]
    assert _huellas(e3.directorio_operacion) == antes["operacion"]
    assert _huellas(e4.directorio) == antes["laboratorio"]
    for juego in ("BALOTO", "MILOTO", "COLORLOTO"):
        for g in e3.almacen.listar(juego):
            assert g.artefacto["esquema"] in ("pronostico-experimental/1", "pronostico-experimental/2")
    for ruta in Path(e5.directorio).rglob("*.json"):  # todo lo nuevo esta en el almacen propio
        assert ruta.is_relative_to(e5.directorio)


def test_copia_del_almacen_de_producto_4_se_lee_y_verifica_igual(productos, tmp_path):
    _, e4, lab, e5 = productos
    copia = tmp_path / "copia-laboratorio"
    shutil.copytree(e4.directorio, copia)
    assert _huellas(copia) == _huellas(e4.directorio)
    original, copiado = LaboratorioFileStore(e4.directorio), LaboratorioFileStore(copia)
    linea = original.lineas("MILOTO")[0]
    a, b = original.pronosticos("MILOTO", linea), copiado.pronosticos("MILOTO", linea)
    def resumen(elementos):
        return [(x.identificador, x.secuencia, x.artefacto) for x in elementos]
    assert resumen(a) == resumen(b)
    for x in b:
        ruta = next(copia.rglob(f"*-{x.identificador}.json"))
        assert ruta.read_bytes() == serializar_entrada(x.artefacto)
    _usar_producto5(e5)
    verificado = lab.verificar_pronostico(a[0].identificador)
    assert verificado["integridad"] == "correcta" and verificado["reproduccion"]["huella_exacta"] is True


def test_primeras_emisiones_de_producto_3_y_del_laboratorio_no_cambian(productos):
    e3, e4, lab, e5 = productos
    consultar = ConsultarRendimiento(e3.almacen, e3.juegos, e3.resultados)
    rendimiento = {j: consultar.ejecutar(j) for j in ("BALOTO", "MILOTO")}
    seguimiento = lab.seguimiento("MILOTO")
    _usar_producto5(e5)
    assert {j: consultar.ejecutar(j) for j in ("BALOTO", "MILOTO")} == rendimiento
    assert lab.seguimiento("MILOTO") == seguimiento


def test_una_configuracion_de_carteras_no_cambia_los_modelos_de_producto_3(productos):
    e3, _, _, e5 = productos
    antes = {j: [(g.identificador, g.artefacto) for g in e3.almacen.listar(j)] for j in ("BALOTO", "MILOTO")}
    _usar_producto5(e5)
    otra = e3.operacion().ejecutar_ahora(["BALOTO", "MILOTO"], "local", "prueba")
    assert otra["estado"] == "exito", f5.detalle(otra)
    assert all(r["pronostico"]["reutilizado"] is True for r in otra["juegos"].values())
    assert {j: [(g.identificador, g.artefacto) for g in e3.almacen.listar(j)] for j in ("BALOTO", "MILOTO")} == antes
    c = f3.cliente(e3)
    texto = c.get("/operacion").text
    assert c.get("/operacion").status_code == 200 and "Carteras y simulación" in texto
    assert 'action="/carteras/configuradas"' in texto and "Laboratorio de modelos" in texto


def test_huella_canonica_fija():
    """La identidad usa la huella canonica de AE-52 sin cambios."""
    objeto = {"b": [1, 2.5, "x"], "a": {"ñ": None}}
    assert ca.huella(objeto) == hashlib.sha256(serializar_entrada(objeto)).hexdigest()
    assert serializar_entrada(objeto) == '{"a":{"ñ":null},"b":[1,2.5,"x"]}\n'.encode("utf-8")


def test_valores_por_defecto_limpiando_solo_las_variables_pertinentes(monkeypatch):
    for variable in VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    ajustes = Settings(_env_file=None)
    assert ajustes.directorio_carteras_modelos == "storage/carteras"
    assert ajustes.tiempo_maximo_trabajador_carteras == 300
    almacenes = {ajustes.directorio_pronosticos_experimentales, ajustes.directorio_operacion,
                 ajustes.directorio_laboratorio_modelos, ajustes.directorio_carteras_modelos}
    assert len(almacenes) == 4


def test_prioridad_real_de_las_variables_de_entorno(monkeypatch, tmp_path):
    archivo = tmp_path / ".env"
    archivo.write_text("DIRECTORIO_CARTERAS_MODELOS=desde-archivo\nTIEMPO_MAXIMO_TRABAJADOR_CARTERAS=120\n",
                       encoding="utf-8")
    for variable in VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    ajustes = Settings(_env_file=archivo)
    assert ajustes.directorio_carteras_modelos == "desde-archivo" and ajustes.tiempo_maximo_trabajador_carteras == 120
    monkeypatch.setenv("DIRECTORIO_CARTERAS_MODELOS", str(tmp_path / "desde-entorno"))
    monkeypatch.setenv("TIEMPO_MAXIMO_TRABAJADOR_CARTERAS", "45")
    ajustes = Settings(_env_file=archivo)  # la variable heredada gana al archivo
    assert ajustes.directorio_carteras_modelos == str(tmp_path / "desde-entorno")
    assert ajustes.tiempo_maximo_trabajador_carteras == 45
    assert Settings(_env_file=None).directorio_carteras_modelos == str(tmp_path / "desde-entorno")  # sin archivo


def test_el_servicio_usa_el_directorio_y_el_tiempo_configurados(monkeypatch, tmp_path):
    from app.api import dependencies as dep
    from app.core import config

    monkeypatch.setenv("DIRECTORIO_CARTERAS_MODELOS", str(tmp_path / "almacen"))
    monkeypatch.setenv("TIEMPO_MAXIMO_TRABAJADOR_CARTERAS", "77")
    config.get_settings.cache_clear()
    try:
        servicio = dep.get_carteras()
        assert Path(servicio._almacen.directorio) == tmp_path / "almacen"
        assert servicio._ejecutor.tiempo_maximo == 77.0
    finally:
        config.get_settings.cache_clear()


def _bloque_de_impresion(css: str) -> str:
    inicio = css.index("@media print")
    nivel, i = 0, css.index("{", inicio)
    for j in range(i, len(css)):
        nivel += {"{": 1, "}": -1}.get(css[j], 0)
        if nivel == 0:
            return css[i:j + 1]
    raise AssertionError("bloque @media print sin cerrar")


def test_css_de_impresion_limitado_a_las_paginas_nuevas():
    css = (RAIZ / "app" / "static" / "css" / "styles.css").read_text(encoding="utf-8")
    assert css.count("@media print") == 1
    impresion = re.sub(r"/\*.*?\*/", "", _bloque_de_impresion(css), flags=re.S)
    selectores = [s.strip() for bloque in re.findall(r"([^{}]+)\{", impresion[1:]) for s in bloque.split(",")]
    nuevos = [s for s in selectores if "carteras" in s]
    assert nuevos and all(s.startswith("body.producto1-impresion ") for s in nuevos)
    assert all(re.search(r"\.carteras-[a-z]+", s) for s in nuevos)
    for anterior in ("body.producto1-impresion .stat-card.h-100 {\n        height: auto !important;",
                     "body.producto1-impresion .stat-card.impresion-fragmentable {",
                     "body.producto1-impresion .tabla-desplazable {\n        max-height: none !important;",
                     "body.producto1-impresion details.laboratorio-desplegable {", "body.producto1-impresion thead {"):
        assert anterior in impresion, anterior
    pantalla = css[:css.index("@media print")]
    assert ".carteras-solo-impresion {\n    display: none;\n}" in pantalla
    plantillas = RAIZ / "app" / "templates"
    for ruta in plantillas.rglob("*.html"):
        if re.search(r'class="[^"]*\bcarteras-', ruta.read_text(encoding="utf-8")):  # clases, no ids
            assert ruta.parent.name == "carteras", ruta


def test_la_cartera_empieza_por_juego_objetivo_combinaciones_y_aviso(tmp_path):
    e = f5.entorno(tmp_path, {"COLORLOTO": 70})
    s = e.carteras()
    r = s.ahora("cartera", ["COLORLOTO"], {"modelo": "uniforme_paleta", "cantidad": 5, "semilla": 1,
                                           "diversidad": "libre"})["juegos"]["COLORLOTO"]
    c = f5.cliente(e, carteras=s)
    try:
        html = c.get(f"/carteras/guardadas/{r['resultado']}").text
    finally:
        f5.limpiar()
    cuerpo = html[html.index('<main'):]
    titulo = cuerpo.index(f"ColorLoto · objetivo {r['objetivo']} · 5 combinación(es)")
    aviso = cuerpo.index("Experimental, no acreditado.")
    combinaciones = cuerpo.index('id="combinaciones"')
    assert titulo < aviso < combinaciones < cuerpo.index('id="observado"') < cuerpo.index("Trazabilidad")
    assert cuerpo.count("carteras-solo-impresion") == 1 and cuerpo.count("carteras-desplegable") == 1
    assert "color-swatch" in cuerpo and "amarillo" in cuerpo.lower()
