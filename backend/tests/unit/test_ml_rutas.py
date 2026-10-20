"""Presupuesto Win32 portable de la disposición real; NO ejecución Windows.

Se usan las carpetas del supervisor, las fixtures y los identificadores de
versiones reales. Incluye destinos, reservas, temporales y espejo público.
TEMP/TMP y la política de rutas largas de Windows no se modifican.
"""
from pathlib import Path, PureWindowsPath

import pytest

from app.application.ml import carteras_artefactos as ca
from app.application.ml import modelos_registrados as mr
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from tests import ejecutar_ml_windows as supervisor
from tests.demostracion_ml_cinco_familias import PREFIJO_DEMOSTRACION
from tests.unit.test_ml_cinco_flujo import (CARPETA_CONCURRENCIA, JUEGOS, laboratorios, modelos)

TEMP_WINDOWS = PureWindowsPath(r"C:\Users\danie\AppData\Local\Temp")
LIMITE = 259


def raiz_pytest(usuario="danie"):
    t = TEMP_WINDOWS / (supervisor.PREFIJO_TEMPORAL + "a" * 8)
    return supervisor.rutas_temporales(t)["pytest"] / ("pytest-of-" + usuario) / "pytest-0"


def comprobar(rutas):
    assert rutas
    maximo = max(rutas, key=lambda p: len(str(p)))
    assert len(str(maximo)) <= LIMITE, (len(str(maximo)), str(maximo))
    return len(str(maximo))


@pytest.mark.parametrize("usuario", ["danie", "unknown", "usuario_de_pruebas"])
def test_ruta_concurrente_real_cabe_sin_rutas_largas(usuario):
    # Pytest trunca el nombre a 30 caracteres y añade su contador. La raíz
    # privada recién creada empieza con pytest-0; no acumulamos runs ajenos.
    funcion = "test_publicacion_nuevo_formato_con_dos_escritores_y_lectores"
    raiz = raiz_pytest(usuario) / (funcion[:30] + "0") / CARPETA_CONCURRENCIA
    assert " " in CARPETA_CONCURRENCIA
    carpeta = LaboratorioFileStore(raiz)._modelos("BALOTO")
    comprobar([carpeta / "estimadores" / ("a" * 64 + ".mljson"),
               carpeta / "estimadores" / (".publicacion." + "a" * 16 + ".tmp"),
               carpeta / "bayes_jerarquico_binario-000001.version"])


def destinos(datos, juego):
    """Rutas del código de producción y de los consumidores, no IDs abreviados."""
    e = datos["e"]
    rutas = list(p for p in e.raiz.rglob("*") if p.is_file())
    for modelo in modelos(juego):
        a = e.almacen_laboratorio.obtener_modelo(datos["versiones"][modelo]["modelo_registrado"]).artefacto
        linea_lab = mr.linea_registrada(a)["id"]
        linea_cartera = ca.linea_de(juego, modelo, "reducido", 5, "libre", 17,
                                    {"numero": 1, "clave": a["clave"]})["id"]
        carpetas = [e.almacen_laboratorio._linea(juego, linea_lab),
                    datos["carteras"]._almacen._linea(juego, linea_cartera)]
        for carpeta in carpetas:
            rutas.extend([carpeta / (str(e.corte(juego) + 1) + "-" + "a" * 64 + ".json"),
                          carpeta / (str(e.corte(juego) + 1) + "-000001.secuencia")])
    # Toda carpeta de destino conserva presupuesto para el temporal corto.
    rutas.extend(p.parent / (".publicacion." + "a" * 16 + ".tmp") for p in list(rutas))
    return [p.relative_to(e.raiz) for p in rutas]


@pytest.mark.parametrize("juego", JUEGOS)
def test_presupuesto_pronosticos_reservas_y_temporales(laboratorios, juego, record_testsuite_property):
    datos = laboratorios(juego)
    relativos = destinos(datos, juego)
    fixture = datos["e"].raiz.name
    assert " " in fixture
    pytest = [raiz_pytest() / fixture / p for p in relativos]
    demo = [TEMP_WINDOWS / (PREFIJO_DEMOSTRACION + "a" * 8) / str(JUEGOS.index(juego)) / p for p in relativos]
    record_testsuite_property(juego + "_maximo_pytest_win32", comprobar(pytest))
    record_testsuite_property(juego + "_maximo_demo_win32", comprobar(demo))
    record_testsuite_property(juego + "_rutas_comprobadas", len(relativos))


def test_presupuesto_espejo_publico_y_almacenes_del_supervisor():
    raiz = TEMP_WINDOWS / (supervisor.PREFIJO_TEMPORAL + "a" * 8)
    rutas = supervisor.rutas_temporales(raiz)
    backend = Path(__file__).resolve().parents[2]
    # Solo fuentes públicas del código: nada de .env ni almacenes.
    fuentes = [p.relative_to(backend) for p in backend.rglob("*.py") if
               "__pycache__" not in p.parts and not any(x.startswith(".") for x in p.relative_to(backend).parts)]
    comprobar([rutas["codigo"] / "backend" / p for p in fuentes])
    assert rutas["pytest"] == raiz
    comprobar([rutas["sinteticos"] / n / ("a" * 64 + ".json") for n in
               ("laboratorio", "pronosticos", "operacion", "carteras", "resultados", "predicciones")])
