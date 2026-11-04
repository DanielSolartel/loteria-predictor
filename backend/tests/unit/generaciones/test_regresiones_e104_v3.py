"""E10.4 v3: regresiones de E104-LIM-07 (carreras de sustitucion tras validar), POSIX reales, sin PostgreSQL.

Solo usan interfaces que ya tenia la v2 (`crear_propia`, `borrar_propia`, `solo_lectura`, `capturar`) para que
FALLEN sobre la v2 por el borrado (o el cambio de permisos) concreto de datos ajenos. La carrera se inyecta en el
instante exacto en que la limpieza abre su descriptor, como la sonda de Codex; el caso de captura no inyecta
nada en la primitiva: otro proceso del mismo usuario sustituye la preparacion durante el intento.
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from app.infrastructure.generaciones import archivos as ar
from app.infrastructure.generaciones import captura as ca
from app.infrastructure.generaciones import firma

pytestmark = pytest.mark.skipif(sys.platform == "win32" or not ar._SEGURO, reason="carreras POSIX con dir_fd")
INTENTO = "ab" * 16
_ABRIR = os.open


def _ajena(carpeta: Path) -> Path:
    carpeta.mkdir(parents=True)
    centinela = carpeta / "NO_BORRAR.txt"
    centinela.write_text("ajeno sintetico")
    centinela.chmod(0o600)
    return centinela


def test_lim07_padre_sustituido_tras_validar_no_borra_la_carpeta_ajena(tmp_path):
    """Un alias del padre apunta a A al validar y a B al abrir: B/p (sin marca) no se borra."""
    buena, alias = tmp_path / "raiz-propia", tmp_path / "alias"
    buena.mkdir()
    alias.symlink_to(buena, target_is_directory=True)
    propia = ar.crear_propia(alias / "p", INTENTO)
    (propia / "propio").write_text("propio")
    centinela = _ajena(tmp_path / "raiz-ajena" / "p")
    hecho = []

    def abrir(ruta, flags, *a, **k):
        if not hecho and Path(ruta) == alias and k.get("dir_fd") is None:
            hecho.append(True)
            alias.unlink()
            alias.symlink_to(tmp_path / "raiz-ajena", target_is_directory=True)
        return _ABRIR(ruta, flags, *a, **k)

    with patch.object(ar.os, "open", side_effect=abrir):
        try:
            ar.borrar_propia(propia, alias, INTENTO)
        except ar.NoPropia:
            pass
    assert hecho, "la carrera no se ejercio"
    assert centinela.read_text() == "ajeno sintetico"  # v2: borrada
    assert (buena / "p" / "propio").read_text() == "propio"


def test_lim07_carpeta_sustituida_por_otra_real_del_mismo_usuario_no_se_borra(tmp_path):
    """Tras validar la marca se aparta la propia y se pone otra carpeta real en su nombre."""
    padre = tmp_path / "padre"
    padre.mkdir()
    propia = ar.crear_propia(padre / "p", INTENTO)
    (propia / "propio").write_text("propio")
    _ajena(padre / "ajena")
    hecho = []

    def abrir(ruta, flags, *a, **k):
        if not hecho and str(ruta) == "p" and k.get("dir_fd") is not None:
            hecho.append(True)
            propia.rename(padre / "propia-apartada")
            (padre / "ajena").rename(propia)
        return _ABRIR(ruta, flags, *a, **k)

    with patch.object(ar.os, "open", side_effect=abrir):
        try:
            ar.borrar_propia(propia, padre, INTENTO)
        except ar.NoPropia:
            pass
    assert hecho, "la carrera no se ejercio"
    assert (propia / "NO_BORRAR.txt").read_text() == "ajeno sintetico"  # v2: borrada
    assert (padre / "propia-apartada" / "propio").read_text() == "propio"


def test_lim07_solo_lectura_no_cambia_permisos_de_una_carpeta_sustituida(tmp_path):
    padre = tmp_path / "padre"
    padre.mkdir()
    propia = ar.crear_propia(padre / "p", INTENTO)
    centinela = _ajena(padre / "ajena")
    hecho = []

    def abrir(ruta, flags, *a, **k):
        if not hecho and str(ruta) == "p" and k.get("dir_fd") is not None:
            hecho.append(True)
            propia.rename(padre / "propia-apartada")
            (padre / "ajena").rename(propia)
        return _ABRIR(ruta, flags, *a, **k)

    with patch.object(ar.os, "open", side_effect=abrir):
        try:
            ar.solo_lectura(propia)
        except ar.NoPropia:
            pass
    assert hecho, "la carrera no se ejercio"
    movida = propia / "NO_BORRAR.txt"
    assert stat.S_IMODE(movida.stat().st_mode) == 0o600  # v2: 0444
    assert stat.S_IMODE(propia.stat().st_mode) != 0o555


def test_lim07_preparacion_de_captura_sustituida_durante_el_intento_no_se_borra(tmp_path):
    """Sin inyeccion en la primitiva: durante el intento otro proceso del mismo usuario aparta la preparacion y
    coloca en su nombre una carpeta real con datos. La limpieza de la captura no debe borrarlos."""
    privada, publica = tmp_path / "f.pem", tmp_path / "f.pub"
    firma.generar(privada, publica)
    destino = tmp_path / "capturas"
    _ajena(tmp_path / "otra")

    def intento(_fuente, prep, *_a, **_k):
        prep.rename(tmp_path / "apartada")
        (tmp_path / "otra").rename(prep)
        raise OSError("fallo sintetico tras la sustitucion")

    with patch.object(ca, "_intento", side_effect=intento):
        with pytest.raises(ca.CapturaRechazada):
            ca.capturar(ca.Fuente("postgresql://modelo/prueba_e104", {}), destino, privada, intentos=1)
    restos = list(destino.glob(".preparando-*"))
    assert restos and all((r / "NO_BORRAR.txt").read_text() == "ajeno sintetico" for r in restos)  # v2: borrada


# --- controles positivos (deben seguir funcionando) --------------------------------------------------------
def test_control_borrado_propio_con_subcarpetas_de_solo_lectura_y_enlaces(tmp_path):
    fuera = tmp_path / "fuera"
    fuera.mkdir(mode=0o700)
    (fuera / "dato").write_text("x")
    propia = ar.crear_propia(tmp_path / "p", INTENTO)
    (propia / "a" / "b").mkdir(parents=True)
    (propia / "a" / "b" / "f").write_text("f")
    ar.solo_lectura(propia)
    os.chmod(propia, 0o700)
    (propia / "enlace").symlink_to(fuera, target_is_directory=True)
    os.chmod(propia, 0o555)
    ar.borrar_propia(propia, tmp_path, INTENTO)
    assert not os.path.lexists(propia) and not os.path.lexists(ar.marca_de(propia))
    assert (fuera / "dato").read_text() == "x" and stat.S_IMODE(fuera.stat().st_mode) == 0o700


def test_control_recuperacion_de_restos_propios_de_una_captura(tmp_path):
    destino = tmp_path / "capturas"
    destino.mkdir()
    resto = ar.crear_propia(destino / ".preparando-0123456789abcdef", INTENTO)
    (resto / "base").mkdir()
    (resto / "base" / "t.jsonl").write_text("{}\n")
    ar.solo_lectura(resto)
    ca._descartar_restos(destino)
    assert not os.path.lexists(resto) and not os.path.lexists(ar.marca_de(resto))
