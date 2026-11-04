"""E10.4: fotografia de arboles (cambios ABA incluidos), copia, transitorios y matriz de datos (DAT-01)."""
from __future__ import annotations

import os
import sys
import time

import pytest

from app.api.publica import perfil_privado
from app.core.config import Settings
from app.infrastructure.generaciones import archivos as ar
from app.infrastructure.generaciones import inventario as inv
from app.infrastructure.generaciones.captura import _a_copiar

posix = pytest.mark.skipif(sys.platform == "win32", reason="ctime POSIX; en Windows queda pendiente (nativo)")


@pytest.fixture
def arbol(tmp_path):
    raiz = tmp_path / "carteras"
    (raiz / "carteras" / "BALOTO").mkdir(parents=True)
    (raiz / "carteras" / "BALOTO" / ("1-" + "a" * 64 + ".json")).write_bytes(b'{"a":1}\n')
    return {"carteras": raiz}


@posix
def test_reescritura_con_el_mismo_contenido_tamano_y_mtime_se_detecta(arbol):
    archivo = next(arbol["carteras"].rglob("*.json"))
    antes = ar.fotografiar(arbol)
    s = os.stat(archivo)
    time.sleep(0.01)
    archivo.write_bytes(b'{"a":1}\n')  # mismo contenido (ABA)
    os.utime(archivo, ns=(s.st_atime_ns, s.st_mtime_ns))  # y se restaura la fecha de modificacion
    despues = ar.fotografiar(arbol)
    assert despues != antes and ar.diferencias(antes, despues)


@posix
def test_alta_y_baja_dentro_de_la_ventana_se_detecta(arbol):
    carpeta = arbol["carteras"] / "carteras" / "BALOTO"
    antes = ar.fotografiar(arbol)
    time.sleep(0.01)
    (carpeta / "temporal.json").write_bytes(b"{}")
    (carpeta / "temporal.json").unlink()
    assert ar.fotografiar(arbol) != antes  # la carpeta cambio su mtime/ctime


def test_raiz_ausente_y_enlaces_quedan_registrados(tmp_path, arbol):
    (arbol["carteras"] / "carteras" / "enlace").symlink_to(tmp_path)
    foto = ar.fotografiar({**arbol, "pronosticos": tmp_path / "no-existe"})
    assert foto["pronosticos/"] == ("ausente",) and foto["carteras/carteras/enlace"][0] == "enlace"


def test_reservas_huerfanas_y_validas(tmp_path):
    carpeta = tmp_path / "l"
    carpeta.mkdir()
    clave = "b" * 64
    (carpeta / "5-000001.secuencia").write_text(clave + "\n")
    assert ar.reserva_huerfana(carpeta / "5-000001.secuencia")
    (carpeta / f"5-{clave}.json").write_text("{}")
    assert not ar.reserva_huerfana(carpeta / "5-000001.secuencia")
    (carpeta / "m-1.version").write_text("no es una clave")
    assert ar.reserva_huerfana(carpeta / "m-1.version")


def test_copia_excluye_temporales_estado_operativo_y_clases_no_publicables():
    foto = {"carteras/carteras/X/1-a.json": ("archivo", 0, 1, 3, 0, 0, 0o644),
            "carteras/carteras/X/.publicacion.0123456789abcdef.tmp": ("archivo", 0, 2, 3, 0, 0, 0o644),
            "carteras/operacion/cerrojos/BALOTO.lock": ("archivo", 0, 3, 0, 0, 0, 0o644),
            "operacion/ejecuciones/e.json": ("archivo", 0, 4, 3, 0, 0, 0o644),
            "resultados/informes/X/c.json": ("archivo", 0, 5, 3, 0, 0, 0o644)}
    assert _a_copiar(foto, "publicacion") == ["carteras/carteras/X/1-a.json"]
    assert _a_copiar(foto, "respaldo") == ["carteras/carteras/X/1-a.json", "carteras/operacion/cerrojos/BALOTO.lock",
                                           "operacion/ejecuciones/e.json", "resultados/informes/X/c.json"]


def test_subcarpeta_nueva_en_un_almacen_publicable_no_esta_clasificada():
    assert inv.clase("laboratorio", "modelos/BALOTO/x.json") == inv.PUBLICABLE
    assert inv.clase("laboratorio", "operacion/cerrojos/x") == inv.OPERATIVO
    assert inv.clase("laboratorio", "novedad/x.json") == "no_clasificado"  # obliga a revisar la matriz
    assert inv.clase("automatizacion", "configuracion.json") == inv.OPERATIVO


def test_la_matriz_cubre_todos_los_directorios_de_la_aplicacion():
    """Un almacen nuevo (`DIRECTORIO_*`) obliga a clasificarlo en la matriz (DAT-01 mantenido con el codigo)."""
    directorios = {n for n in Settings.model_fields if n.startswith("directorio_")}
    assert directorios == {a.ajuste for a in inv.ALMACENES}
    assert set(inv.AJUSTES_DE_CONSULTA) == set(perfil_privado.ALMACENES_DE_CONSULTA)
    assert all(s in Settings.model_fields and s not in directorios for s in inv.SECRETOS)
