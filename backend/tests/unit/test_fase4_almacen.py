"""Fase 4 - almacen de explicaciones (`PrediccionesFileStore`): inmutable,
idempotente, verificable, concurrente, dentro del presupuesto de rutas de
Windows y sin tocar los almacenes ni la configuracion anteriores; y
`CentroDeResultados.emisiones` como lectura que no cambia Producto 6. Datos
sinteticos; nada es real."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

from app.application.interfaces.predicciones_store import ExplicacionGuardada, ExplicacionIlegible
from app.application.ml import predicciones_explicacion as pe
from app.application.ml.registro_prospectivo import serializar_entrada
from app.core.config import Settings
from app.infrastructure.storage.predicciones_file_store import PrediccionesFileStore
from tests.unit import fixtures_fase4 as f4

CARTERA = "c" * 64
BACKEND = Path(__file__).resolve().parents[2]


def artefacto(juego="BALOTO", cartera=CARTERA, dato=1, origen="prueba"):
    cuerpo = {"esquema": pe.ESQUEMA, "version": pe.VERSION, "juego": juego, "cartera": {"clave": cartera},
              "dato": dato}
    return pe.componer(cuerpo, {"generado_en": "2026-10-07T01:00:00+00:00", "origen": origen})


def test_guardar_publica_una_vez_y_reutiliza_la_misma_clave(tmp_path):
    almacen = PrediccionesFileStore(tmp_path)
    a = artefacto()
    g = almacen.guardar(a)
    assert isinstance(g, ExplicacionGuardada) and not g.reutilizado and g.cartera == CARTERA
    ruta = tmp_path / "explicaciones" / "BALOTO" / f"{CARTERA[:16]}-{a['clave']}.json"
    assert ruta.read_bytes() == serializar_entrada(a)  # JSON canonico, sin nada mas
    # Otra generacion (otra fecha/origen) con el mismo cuerpo: misma clave, se reutiliza la primera.
    otra = almacen.guardar(artefacto(origen="comando"))
    assert otra.reutilizado and otra.clave == g.clave and otra.artefacto["generacion"]["origen"] == "prueba"
    assert sorted(p.name for p in ruta.parent.iterdir()) == [ruta.name]
    assert almacen.obtener(g.clave).artefacto == a and almacen.obtener("x") is None
    assert [e.clave for e in almacen.de_cartera("BALOTO", CARTERA)] == [g.clave]
    assert almacen.de_cartera("BALOTO", "d" * 64) == [] and almacen.listar("MILOTO") == []


def test_rechaza_artefactos_sin_sello_o_con_juego_no_admitido(tmp_path):
    almacen = PrediccionesFileStore(tmp_path)
    a = artefacto()
    with pytest.raises(ValueError):
        almacen.guardar({**a, "dato": 2})  # sello incoherente
    with pytest.raises(ValueError):
        almacen.guardar(artefacto(cartera="corta"))
    with pytest.raises(ValueError):
        almacen.guardar(artefacto(juego="../X"))
    assert not (tmp_path / "explicaciones").exists() or not any((tmp_path / "explicaciones").rglob("*.json"))


def test_lectura_detecta_alteraciones_y_nunca_sobrescribe(tmp_path):
    almacen = PrediccionesFileStore(tmp_path)
    g = almacen.guardar(artefacto())
    ruta = tmp_path / "explicaciones" / "BALOTO" / f"{CARTERA[:16]}-{g.clave}.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["dato"] = 2
    ruta.write_bytes(serializar_entrada(datos))
    leido = almacen.obtener(g.clave)
    assert isinstance(leido, ExplicacionIlegible) and leido.motivo == "contenido_alterado"
    alterado = ruta.read_bytes()
    with pytest.raises(FileExistsError):
        almacen.guardar(artefacto())
    assert ruta.read_bytes() == alterado
    ruta.write_text("{no es json", encoding="utf-8")
    assert almacen.obtener(g.clave).motivo == "json_no_canonico"


def test_lectura_rechaza_juego_o_cartera_que_no_coinciden_y_enlaces(tmp_path):
    almacen = PrediccionesFileStore(tmp_path)
    g = almacen.guardar(artefacto())
    origen = tmp_path / "explicaciones" / "BALOTO" / f"{CARTERA[:16]}-{g.clave}.json"
    otra = tmp_path / "explicaciones" / "MILOTO"
    otra.mkdir(parents=True)
    (otra / origen.name).write_bytes(origen.read_bytes())
    assert almacen.listar("MILOTO")[0].motivo == "juego_no_coincide"
    (tmp_path / "explicaciones" / "BALOTO" / f"{'e' * 16}-{g.clave}.json").write_bytes(origen.read_bytes())
    motivos = {e.motivo for e in almacen.listar("BALOTO") if isinstance(e, ExplicacionIlegible)}
    assert motivos == {"cartera_no_coincide"}
    enlace = tmp_path / "explicaciones" / "BALOTO" / f"{'f' * 16}-{'1' * 64}.json"
    try:
        enlace.symlink_to(origen)
    except (OSError, NotImplementedError):
        pytest.skip("este sistema no permite crear enlaces simbolicos")
    assert any(e.clave == "1" * 64 and e.motivo == "nombre_o_tipo_de_archivo_no_admitido"
               for e in almacen.listar("BALOTO") if isinstance(e, ExplicacionIlegible))


def test_temporales_se_listan_aparte_y_no_se_borran(tmp_path):
    almacen = PrediccionesFileStore(tmp_path)
    g = almacen.guardar(artefacto())
    temporal = tmp_path / "explicaciones" / "BALOTO" / ".publicacion.0123456789abcdef.tmp"
    temporal.write_bytes(b"a medias")
    assert almacen.temporales() == [os.path.join("explicaciones", "BALOTO", temporal.name)]
    assert [e.clave for e in almacen.listar("BALOTO")] == [g.clave]
    assert [e.clave for e in almacen.de_cartera("BALOTO", CARTERA)] == [g.clave]
    almacen.guardar(artefacto(dato=3))
    assert temporal.exists()


def test_escritores_concurrentes_publican_un_solo_archivo(tmp_path):
    almacen = PrediccionesFileStore(tmp_path)
    a = artefacto()
    resultados, errores = [], []
    barrera = threading.Barrier(8)

    def escribir():
        try:
            barrera.wait()
            resultados.append(PrediccionesFileStore(tmp_path).guardar(a))
        except Exception as error:  # pragma: no cover - se informa abajo
            errores.append(error)

    hilos = [threading.Thread(target=escribir) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert errores == [] and {r.clave for r in resultados} == {a["clave"]}
    assert sum(1 for r in resultados if not r.reutilizado) <= 1
    carpeta = tmp_path / "explicaciones" / "BALOTO"
    assert [p.name for p in carpeta.iterdir()] == [f"{CARTERA[:16]}-{a['clave']}.json"]
    assert almacen.temporales() == []


def test_presupuesto_de_rutas_de_windows():
    """Ruta mas larga: carpeta del almacen + 117 caracteres; el temporal es mas
    corto. Con la carpeta real de la guia de Windows queda muy por debajo de
    259 caracteres (sin rutas largas)."""
    relativa = os.path.join("explicaciones", "BALOTO_REVANCHA", f"{'a' * 16}-{'b' * 64}.json")
    temporal = os.path.join("explicaciones", "BALOTO_REVANCHA", ".publicacion.0123456789abcdef.tmp")
    assert len(relativa) + 1 == 117 and len(temporal) < len(relativa)
    carpeta = r"C:\GitHub\loteria-predictor-fase4\backend\storage\predicciones"
    assert len(carpeta) + 117 <= 200


# ---------------------------------------------------------------------------
# Compatibilidad: configuracion, ignorados por Git y Producto 6
# ---------------------------------------------------------------------------

def test_ajuste_nuevo_sin_cambiar_los_anteriores():
    defecto = {k: v.default for k, v in Settings.model_fields.items() if k.startswith("directorio_")}
    assert defecto["directorio_predicciones_modelos"] == "storage/predicciones"
    assert defecto["directorio_carteras_modelos"] == "storage/carteras"
    assert defecto["directorio_resultados_modelos"] == "storage/resultados"
    assert defecto["directorio_laboratorio_modelos"] == "storage/laboratorio"
    assert len(set(defecto.values())) == len(defecto)  # cada almacen en su carpeta
    ignorados = (BACKEND / ".gitignore").read_text(encoding="utf-8")
    assert "storage/predicciones/*" in ignorados and "!storage/predicciones/.gitkeep" in ignorados
    assert (BACKEND / "storage" / "predicciones" / ".gitkeep").exists()


def test_emisiones_de_producto_6_es_lectura_y_no_cambia_su_consulta(tmp_path):
    e = f4.entorno(tmp_path)
    e.configurar("MILOTO", "uniforme")
    carteras = e.carteras()
    centro = e.centro(carteras)
    centro.ahora("MILOTO")
    e.anadir("MILOTO", e.siguiente("MILOTO"))
    resultados = e.centro_de_resultados(carteras)
    antes_consulta = resultados.consultar("MILOTO")
    antes = f4.arbol(e.raiz)
    datos = resultados.emisiones("MILOTO")
    assert f4.arbol(e.raiz) == antes
    assert resultados.consultar("MILOTO") == antes_consulta
    assert datos["base"]["estado"] == "consultada" and set(datos) == {"base", "lineas", "filas", "procedencias"}
    assert any(f["estado"] == "incluido" and f["congelado"] for f in datos["filas"])
    f4.limpiar()
