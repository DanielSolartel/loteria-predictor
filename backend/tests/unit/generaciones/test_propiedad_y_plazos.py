"""E10.4 v2: primitivas nuevas de propiedad, confinamiento, plazo, identidad del codigo y recuentos sellados.

Complementan las regresiones (`test_regresiones_e104_v2.py`, `test_propiedad_y_restauracion_pg.py`): estas usan
las interfaces nuevas de la v2 y no se cuentan como regresiones que fallen sobre la v1.
"""
from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

from app.infrastructure.generaciones import archivos as ar
from app.infrastructure.generaciones import codigo
from app.infrastructure.generaciones import consultas
from app.infrastructure.generaciones.captura import Plazo, _Intento

posix = pytest.mark.skipif(sys.platform == "win32", reason="enlaces, dir_fd y modos POSIX")
INTENTO = "ab" * 16


@pytest.fixture
def fuera(tmp_path):
    carpeta = tmp_path / "fuera"
    carpeta.mkdir(mode=0o700)
    (carpeta / "dato").write_text("x")
    (carpeta / "dato").chmod(0o600)
    return carpeta


def _modos(*rutas):
    return [stat.S_IMODE(os.lstat(r).st_mode) for r in rutas]


# --- propiedad y confinamiento ------------------------------------------------------------------------------
def test_sin_marca_o_con_otro_intento_no_es_propia(tmp_path):
    (tmp_path / "x").mkdir()
    with pytest.raises(ar.NoPropia, match="sin marca"):
        ar.borrar_propia(tmp_path / "x", tmp_path)
    ar.marca_de(tmp_path / "x").write_text("cd" * 16 + "\n")  # marca de formato antiguo: no acredita nada
    with pytest.raises(ar.NoPropia, match="no valida"):
        ar.borrar_propia(tmp_path / "x", tmp_path, INTENTO)
    propia = ar.crear_propia(tmp_path / "y", "cd" * 16)
    with pytest.raises(ar.NoPropia, match="otro intento"):
        ar.borrar_propia(propia, tmp_path, INTENTO)
    assert (tmp_path / "x").is_dir() and propia.is_dir()


def test_fuera_de_la_carpeta_esperada_no_es_propia(tmp_path):
    otra = tmp_path / "otra"
    otra.mkdir()
    propia = ar.crear_propia(otra / "p", INTENTO)
    with pytest.raises(ar.NoPropia, match="fuera"):
        ar.borrar_propia(propia, tmp_path, INTENTO)


def test_crear_propia_no_toca_la_marca_de_una_carpeta_existente(tmp_path):
    propia = ar.crear_propia(tmp_path / "p", INTENTO)
    with pytest.raises(FileExistsError):
        ar.crear_propia(propia, "cd" * 16)
    assert ar.intento_de(propia, tmp_path) == INTENTO


@posix
def test_la_propia_enlazada_no_se_sigue(tmp_path, fuera):
    (tmp_path / "p").symlink_to(fuera, target_is_directory=True)
    # marca falsificada con las identidades reales del padre y del destino del enlace
    ar.marca_de(tmp_path / "p").write_bytes(ar._texto_marca(INTENTO, ar._identidad(os.stat(tmp_path)),
                                                           ar._identidad(os.stat(fuera))))
    with pytest.raises(ar.NoPropia, match="no es una carpeta real"):
        ar.borrar_propia(tmp_path / "p", tmp_path, INTENTO)
    assert (fuera / "dato").read_text() == "x" and _modos(fuera, fuera / "dato") == [0o700, 0o600]


@posix
def test_sustitucion_concurrente_por_un_enlace_durante_el_borrado(tmp_path, fuera, monkeypatch):
    """Entre listar la carpeta y entrar en una subcarpeta, otro proceso la sustituye por un enlace a `fuera`."""
    propia = ar.crear_propia(tmp_path / "p", INTENTO)
    (propia / "sub").mkdir()
    (propia / "sub" / "a").write_text("a")
    real = os.scandir
    hecho = []

    def scandir(objetivo=None):
        entradas = list(real(objetivo))
        if not hecho and any(e.name == "sub" for e in entradas):
            hecho.append(1)
            os.unlink(propia / "sub" / "a")
            os.rmdir(propia / "sub")
            (propia / "sub").symlink_to(fuera, target_is_directory=True)
        return iter(entradas)

    monkeypatch.setattr(ar.os, "scandir", scandir)
    ar.borrar_propia(propia, tmp_path, INTENTO)
    assert hecho and not os.path.lexists(propia)
    assert (fuera / "dato").read_text() == "x" and _modos(fuera, fuera / "dato") == [0o700, 0o600]


@posix
def test_solo_lectura_rechaza_enlaces_y_enlaces_duros(tmp_path, fuera):
    propia = ar.crear_propia(tmp_path / "p", INTENTO)
    os.link(fuera / "dato", propia / "duro")
    with pytest.raises(ar.NoPropia, match="unico nombre"):
        ar.solo_lectura(propia)
    assert _modos(fuera / "dato") == [0o600]
    (propia / "duro").unlink()
    (propia / "blando").symlink_to(fuera / "dato")
    with pytest.raises(ar.NoPropia, match="enlace"):
        ar.solo_lectura(propia)
    assert _modos(fuera / "dato") == [0o600]


@posix
def test_borrar_una_propia_de_solo_lectura(tmp_path):
    propia = ar.crear_propia(tmp_path / "p", INTENTO)
    (propia / "a" / "b").mkdir(parents=True)
    (propia / "a" / "b" / "f").write_text("f")
    ar.solo_lectura(propia)
    ar.borrar_propia(propia, tmp_path, INTENTO)
    assert not os.path.lexists(propia) and not os.path.lexists(ar.marca_de(propia))


# --- plazo ----------------------------------------------------------------------------------------------------
def test_plazo_comprueba_con_su_reloj():
    ahora = [0.0]
    p = Plazo(5.0, lambda: ahora[0])
    p.comprobar("inicio")
    ahora[0] = 5.01
    assert p.restante() < 0
    with pytest.raises(_Intento) as error:
        p.comprobar("antes de sellar")
    assert error.value.motivo == "plazo_total_agotado" and not error.value.reintentable


def test_copia_verificada_comprueba_el_plazo_por_bloque(tmp_path):
    origen = tmp_path / "o"
    origen.write_bytes(b"x" * (3 * 1024 * 1024))
    llamadas = []

    def comprobar(donde):
        llamadas.append(donde)
        if len(llamadas) == 2:
            raise TimeoutError(donde)
    with pytest.raises(TimeoutError):
        ar.copiar_verificado(origen, tmp_path / "d", comprobar=comprobar)
    assert len(llamadas) == 2


def test_conectar_con_el_plazo_vencido_no_abre_conexion():
    from app.infrastructure.generaciones import base_logica as bl
    with pytest.raises(TimeoutError):
        bl.conectar("postgresql://u:p@127.0.0.1:1/x", limite=0)


# --- identidad del codigo (E104-GEN-02) -----------------------------------------------------------------------
def test_la_revision_exigida_es_la_cabeza_de_alembic():
    """La imagen de la API no lleva `alembic/`: la constante debe ser la cabeza de las migraciones del repo."""
    import re

    versiones = Path(__file__).resolve().parents[3] / "alembic" / "versions"
    revisiones, anteriores = set(), set()
    for ruta in versiones.glob("*.py"):
        texto = ruta.read_text(encoding="utf-8")
        revisiones.add(re.search(r'^revision\s*=\s*"([^"]+)"', texto, re.M).group(1))
        anterior = re.search(r'^down_revision\s*=\s*"([^"]+)"', texto, re.M)
        if anterior:
            anteriores.add(anterior.group(1))
    assert revisiones - anteriores == {codigo.REVISION_ESQUEMA}


def test_la_huella_de_app_cambia_con_un_byte_y_no_con_el_bytecode(tmp_path):
    copia = tmp_path / "app"
    shutil.copytree(codigo.raiz_de_esta_app(), copia, ignore=shutil.ignore_patterns("__pycache__"))
    base, n = codigo.huella_app(copia)
    assert (base, n) == codigo.huella_app(codigo.raiz_de_esta_app()) and n > 50
    (copia / "__pycache__").mkdir(exist_ok=True)
    (copia / "__pycache__" / "x.cpython-314.pyc").write_bytes(b"\0")
    (copia / "notas.txt").write_text("no es codigo")
    assert codigo.huella_app(copia)[0] == base
    objetivo = copia / "api" / "publica" / "perfil_privado.py"
    objetivo.write_bytes(objetivo.read_bytes() + b"\n")
    assert codigo.huella_app(copia)[0] != base


# --- recuentos sellados (E104-DAT-06): perdidas estrictas -----------------------------------------------------
def _api_completa(sorteos=3, carteras=2, modelos=1, emisiones=1, prediccion=True):
    from urllib.parse import parse_qs, urlsplit

    def get(url):
        ruta = urlsplit(url).path
        if ruta.startswith("/api/v1/simulaciones/"):
            return 404, {"error": {"codigo": "no_encontrado"}}
        if ruta.endswith("/sorteos"):
            return 200, {"total": sorteos, "sorteos": [{"numero_sorteo": sorteos}] if sorteos else []}
        if ruta.endswith("/predicciones"):
            return 200, {"prediccion": {"objetivo": 4} if prediccion else None}
        if ruta.endswith("/carteras-guardadas"):
            return 200, {"total": carteras, "elementos": [{"clave": "c" * 64}] if carteras else []}
        if ruta.endswith("/modelos-guardados"):
            return 200, {"total": modelos, "elementos": [{"clave": "d" * 64}] if modelos else []}
        if ruta.endswith("/resultados"):
            p = parse_qs(urlsplit(url).query).get("procedencia", ["operacion"])[0]
            return 200, {"lineas": [], "resumenes": {},
                         "procedencias": {q: {"emisiones": emisiones} for q in consultas.PROCEDENCIAS}, "p": p}
        return 200, {}
    return get


ESPERADO = {"juegos": {j: {"sorteos": 3, "ultimo_sorteo": 3} for j in consultas.JUEGOS},
            "artefactos": {j: {"cartera": 2, "modelo": 1, "explicacion": 1, "pronostico_experimental": 1,
                               "pronostico_laboratorio": 1} for j in consultas.JUEGOS}}


def test_recuentos_sellados_iguales_sin_fallos():
    assert consultas.recorrer(_api_completa(), ESPERADO)["fallos"] == []


@pytest.mark.parametrize("perdida,texto", [({"sorteos": 2}, "sorteos 2"), ({"carteras": 1}, "carteras"),
                                           ({"modelos": 0}, "modelos"), ({"emisiones": 0}, "sin emisiones"),
                                           ({"prediccion": False}, "prediccion")])
def test_perdidas_frente_a_lo_sellado_fallan(perdida, texto):
    fallos = consultas.recorrer(_api_completa(**perdida), ESPERADO)["fallos"]
    assert sum(texto in f for f in fallos) >= 4, fallos[:8]  # en los cuatro juegos


def test_esperado_de_la_coherencia():
    coherencia = {"artefactos": [{"juego": "BALOTO", "familia": "cartera"}, {"juego": "BALOTO", "familia": "cartera"},
                                 {"juego": "MILOTO", "familia": "modelo"}]}
    juegos = {"BALOTO": {"sorteos": 5, "ultimo_sorteo": 9, "ultima_fecha": "x"}}
    assert consultas.esperado_de(juegos, coherencia) == {
        "juegos": {"BALOTO": {"sorteos": 5, "ultimo_sorteo": 9}},
        "artefactos": {"BALOTO": {"cartera": 2}, "MILOTO": {"modelo": 1}}}


def test_requisitos_de_la_demostracion_estan_aparte():
    vacia = consultas.recorrer(_api_completa(sorteos=0, carteras=0, modelos=0, emisiones=0, prediccion=False))
    assert vacia["fallos"] == []  # una fuente real vacia es valida
    assert consultas.requisitos_de_demostracion(vacia)  # pero no sirve como demostracion
