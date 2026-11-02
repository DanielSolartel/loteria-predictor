"""E10.1 v2 (E101-SEC-01): ensayo NATIVO de ACL de Windows. Solo se ejecuta en Windows; en Linux se omite.

Usa carpetas temporales nuevas de pytest (nunca `backend/privado/` ni carpetas ajenas). Las ACE amplias se
añaden solo al archivo temporal de la prueba, con `icacls`, y se retiran al terminar.
"""
from __future__ import annotations

import os
import subprocess

import pytest

from app.seguridad_consola import almacen as al
from app.seguridad_consola import permisos as pe
from tests import consola_sesion as cs

pytestmark = pytest.mark.skipif(os.name != "nt", reason="ensayo nativo de ACL: requiere Windows")


def _icacls(*argumentos):
    r = subprocess.run(["icacls", *map(str, argumentos)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def test_nativo_crear_deja_propietario_y_dacl_solo_del_usuario(tmp_path):
    s = cs.almacen_de_prueba(tmp_path)
    usuario = pe.sid_actual()
    for ruta, directorio in ((s.archivo, False), (s.archivo.parent, True)):
        d = pe.leer_descriptor(ruta)
        assert d.propietario == usuario and d.dacl_presente
        assert {a.sid for a in d.aces if a.tipo == pe.ACCESS_ALLOWED_ACE_TYPE} == {usuario}
        assert pe.evaluar_descriptor(d, usuario) is None
        pe.verificar(ruta, directorio=directorio)
    s.comprobar()


def test_nativo_ace_amplia_posterior_cierra_y_al_retirarla_vuelve(tmp_path):
    s = cs.almacen_de_prueba(tmp_path)
    _icacls(s.archivo, "/grant", "*S-1-1-0:(R)")
    try:
        with pytest.raises(al.ConsolaNoDisponible) as e:
            s.comprobar()
        assert e.value.motivo == "permisos"
    finally:
        _icacls(s.archivo, "/remove:g", "*S-1-1-0")
    s.comprobar()


def test_nativo_directorio_preexistente_no_se_modifica(tmp_path):
    existente = tmp_path / "preexistente"
    existente.mkdir()  # hereda la ACL de la carpeta temporal (normalmente con Administradores y SYSTEM)
    antes = pe.leer_descriptor(existente)
    if pe.evaluar_descriptor(antes, pe.sid_actual()) is None:
        pytest.skip("la carpeta temporal ya es exclusiva del usuario; el caso no es aplicable aquí")
    with pytest.raises(al.OperacionRechazada, match="no se modifica"):
        al.AlmacenSeguridad.crear(existente / "seguridad.sqlite3", parametros=cs.PARAMETROS_PRUEBA)
    assert pe.leer_descriptor(existente) == antes and list(existente.iterdir()) == []
