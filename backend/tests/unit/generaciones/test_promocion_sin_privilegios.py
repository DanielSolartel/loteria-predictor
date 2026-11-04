"""CI110-PER-01: importacion y promocion con permisos POSIX efectivos, sin PostgreSQL.

Las dos regresiones llaman al importador real con un paquete firmado y archivos reales; solo se sustituyen
PostgreSQL, la coherencia de sus datos y las consultas. No acreditan esas tres capas. En Linux, las pruebas
de PostgreSQL y la demostracion del workflow siguen siendo necesarias para la validacion integrada.
"""
from __future__ import annotations

import copy
import os
import stat
from unittest.mock import MagicMock

import pytest

from app.infrastructure.generaciones import archivos as ar
from app.infrastructure.generaciones import importacion as im
from tests.unit.generaciones import paquete_sintetico as ps

pytestmark = pytest.mark.skipif(not ar._SEGURO, reason="promocion POSIX con dir_fd")
INTENTO = "ab" * 16


def _modo(ruta):
    return stat.S_IMODE(ruta.stat().st_mode)


@pytest.fixture
def importacion_sintetica(tmp_path, monkeypatch):
    paquete, privada, publica = ps.construir(tmp_path)
    paquete = ps.refirmar(paquete, privada, lambda m: m.update(codigo=im.huella_del_codigo()))
    conexion = MagicMock()
    conexion.__enter__.return_value = conexion
    conexion.execute.return_value.fetchone.return_value = (True,)
    conexion.execute.return_value.fetchall.return_value = []
    monkeypatch.setattr(im.bl, "conectar", lambda *_a, **_k: conexion)
    monkeypatch.setattr(im.bl, "huella_esquema", lambda _c: "0" * 64)
    monkeypatch.setattr(im.bl, "tablas", lambda _c: {})
    monkeypatch.setattr(im.bl, "restaurar", lambda *_a: None)
    monkeypatch.setattr(im, "_existe_base", lambda *_a: False)
    monkeypatch.setattr(im, "_oid", lambda *_a: 123)
    monkeypatch.setattr(im, "_migrar", lambda *_a: None)
    monkeypatch.setattr(im, "_historico_de", lambda _u: (lambda _j: [], lambda: None))
    monkeypatch.setattr(im.co, "evaluar", lambda *_a, **_k: copy.deepcopy(ps.COHERENCIA))
    borradas = []
    monkeypatch.setattr(im, "borrar_base_propia", lambda _c, nombre, *_a: borradas.append(nombre) or True)
    raiz = tmp_path / "servidor"
    vistas = []

    def humo(_url, carpeta, _salida, **_k):
        vistas.append(carpeta)
        assert _modo(carpeta.parent) == 0o555
        assert all(_modo(p) == (0o555 if p.is_dir() else 0o444) for p in carpeta.parent.rglob("*"))
        assert not (raiz / "generaciones" / paquete.name).exists()
        return {"total": 1, "fallos": [], "contenido": {}, "lecturas": {"fuera_de_lo_declarado": []}, "rutas": []}

    monkeypatch.setattr(im, "consultas_en_proceso_aparte", humo)
    destino = im.Destino(raiz, "postgresql://sintetico@127.0.0.1:1/postgres",
                         "postgresql://lector@127.0.0.1:1/postgres")
    return paquete, publica, destino, borradas, vistas


def test_importacion_acepta_preparacion_sellada_con_permisos_efectivos(importacion_sintetica):
    paquete, publica, destino, borradas, vistas = importacion_sintetica
    informe = im.importar(paquete, publica, destino)
    final = destino.raiz / "generaciones" / paquete.name
    assert informe["resultado"] == "aceptada" and len(vistas) == 1 and borradas == []
    assert _modo(final) == 0o555
    assert all(_modo(p) == (0o555 if p.is_dir() else 0o444) for p in final.rglob("*"))
    assert (final / "manifiesto.json").read_bytes() == (paquete / "manifiesto.json").read_bytes()
    assert list((destino.raiz / "preparacion").iterdir()) == []


def test_fallo_de_rename_limpia_la_preparacion_sin_perder_su_marca(importacion_sintetica, monkeypatch):
    paquete, publica, destino, borradas, vistas = importacion_sintetica
    renombrar = os.rename
    armada = []

    def fase(nombre):
        if nombre == "base_aceptada":
            armada.append(True)

    def fallo(origen, final, *a, **k):
        if armada and str(origen) in (paquete.name, str(destino.raiz / "preparacion" / paquete.name)):
            raise PermissionError("traslado denegado sintetico")
        return renombrar(origen, final, *a, **k)

    monkeypatch.setattr(ar.os, "rename", fallo)
    with pytest.raises(im.ImportacionRechazada, match="traslado denegado sintetico"):
        im.importar(paquete, publica, destino, fase=fase)
    assert len(vistas) == 1 and borradas == [f"pub_{paquete.name}"]
    assert list((destino.raiz / "preparacion").iterdir()) == []
    assert list((destino.raiz / "generaciones").iterdir()) == []


@pytest.fixture
def preparacion(tmp_path):
    padre, destino = tmp_path / "preparacion", tmp_path / "generaciones"
    padre.mkdir()
    destino.mkdir()
    propia = ar.crear_propia(padre / "p", INTENTO)
    (propia / "sub").mkdir()
    (propia / "sub" / "dato").write_text("propio")
    ar.solo_lectura(propia, padre, INTENTO)
    return propia, padre, destino / "p"


@pytest.mark.parametrize("fallo", ["retirar_marca", "restaurar_modo"])
def test_fallo_posterior_al_rename_devuelve_la_misma_preparacion_sellada(preparacion, monkeypatch, fallo):
    propia, padre, final = preparacion
    inodo = propia.stat().st_ino
    quitar, chmod = os.unlink, os.fchmod
    ejercido = []

    def unlink(ruta, *a, **k):
        if fallo == "retirar_marca" and str(ruta) == ar.marca_de(propia).name:
            ejercido.append(True)
            raise OSError("marca sintetica ocupada")
        return quitar(ruta, *a, **k)

    def fchmod(fd, modo):
        if fallo == "restaurar_modo" and modo == 0o555 and final.exists() and not ejercido:
            ejercido.append(True)
            raise OSError("fallo sintetico de chmod")
        return chmod(fd, modo)

    with monkeypatch.context() as m:
        m.setattr(ar.os, "unlink", unlink)
        m.setattr(ar.os, "fchmod", fchmod)
        with pytest.raises(OSError, match="sintetic"):
            ar.promover_propia(propia, padre, final, INTENTO)
    assert ejercido and propia.stat().st_ino == inodo and _modo(propia) == 0o555
    assert not final.exists() and ar.intento_de(propia, padre) == INTENTO
    ar.borrar_propia(propia, padre, INTENTO)
    assert list(padre.iterdir()) == []


@pytest.mark.parametrize("tipo", ["carpeta", "archivo", "enlace"])
def test_no_sobrescribe_un_destino_existente(preparacion, tipo):
    propia, padre, final = preparacion
    if tipo == "carpeta":
        final.mkdir()
    elif tipo == "archivo":
        final.write_text("ajeno")
    else:
        final.symlink_to(propia, target_is_directory=True)
    antes = final.lstat()
    with pytest.raises(FileExistsError):
        ar.promover_propia(propia, padre, final, INTENTO)
    assert final.lstat() == antes and _modo(propia) == 0o555
    assert ar.intento_de(propia, padre) == INTENTO


def test_otro_intento_no_cambia_permisos_ni_traslada(preparacion):
    propia, padre, final = preparacion
    with pytest.raises(ar.NoPropia, match="otro intento"):
        ar.promover_propia(propia, padre, final, "cd" * 16)
    assert _modo(propia) == 0o555 and not final.exists()
    assert ar.intento_de(propia, padre) == INTENTO


def test_carpeta_sustituida_no_se_mueve_ni_cambia_permisos(preparacion, monkeypatch):
    propia, padre, final = preparacion
    ajena = padre / "ajena"
    ajena.mkdir(mode=0o700)
    (ajena / "dato").write_text("ajeno")
    abrir = os.open
    ejercido = []

    def carrera(ruta, flags, *a, **k):
        if not ejercido and str(ruta) == propia.name and k.get("dir_fd") is not None:
            ejercido.append(True)
            # Los dos cambios de nombre mantienen el mismo padre; no necesitan modificar `..`.
            propia.rename(padre / "apartada")
            ajena.rename(propia)
        return abrir(ruta, flags, *a, **k)

    monkeypatch.setattr(ar.os, "open", carrera)
    with pytest.raises(ar.NoPropia, match="sustituida"):
        ar.promover_propia(propia, padre, final, INTENTO)
    assert ejercido and _modo(propia) == 0o700 and not final.exists()
    assert (propia / "dato").read_text() == "ajeno" and _modo(padre / "apartada") == 0o555


def test_sin_dir_fd_no_cambia_nada(preparacion, monkeypatch):
    propia, padre, final = preparacion
    monkeypatch.setattr(ar, "_SEGURO", False)
    with pytest.raises(ar.NoPropia, match="sin dir_fd"):
        ar.promover_propia(propia, padre, final, INTENTO)
    assert _modo(propia) == 0o555 and not final.exists() and ar.marca_de(propia).exists()


def test_sustitucion_tras_abrir_no_aplica_chmod_a_la_carpeta_ajena(preparacion, monkeypatch):
    propia, padre, final = preparacion
    ajena = padre / "ajena"
    ajena.mkdir(mode=0o700)
    (ajena / "dato").write_text("ajeno")
    chmod = os.fchmod
    ejercido = []

    def carrera(fd, modo):
        if modo == 0o755 and not ejercido:
            ejercido.append(True)
            propia.rename(padre / "apartada")
            ajena.rename(propia)
        return chmod(fd, modo)

    monkeypatch.setattr(ar.os, "fchmod", carrera)
    with pytest.raises(ar.NoPropia, match="sustituida antes del traslado"):
        ar.promover_propia(propia, padre, final, INTENTO)
    assert ejercido and _modo(propia) == 0o700 and (propia / "dato").read_text() == "ajeno"
    assert _modo(padre / "apartada") == 0o555 and not final.exists()
