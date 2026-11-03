"""Fase 10 (E10.3, v2, F1023-CI-01): el comprobador de contenido de las imagenes distingue el paquete de codigo
`app/infrastructure/storage` de datos y secretos. Se ejecuta sobre un arbol SINTETICO que imita la imagen
(el script recorre `/`; aqui recibe la carpeta sintetica como raiz). Las imagenes reales y sus
controles negativos se comprueban con Docker en el job `imagenes` y en la verificacion local."""
from __future__ import annotations

import base64
import importlib.util
import json
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "despliegue" / "imagenes" / "comprobar_contenido_imagen.py"
# El bloque se compone en ejecucion (cuerpo aleatorio, sin clave real) para no dejar en el arbol un literal con
# forma de clave privada, que gitleaks marcaria con razon.
_MARCA = "PRIVATE" + " KEY"
PEM = (f"-----BEGIN {_MARCA}-----\n" + "\n".join(base64.b64encode(os.urandom(48)).decode() for _ in range(3))
       + f"\n-----END {_MARCA}-----\n")


def _cargar():
    spec = importlib.util.spec_from_file_location("comprobar_contenido_imagen", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _imagen(raiz: Path, plantar=()):
    for rel, contenido in (("srv/backend/app/infrastructure/storage/__init__.py", ""),
                           ("srv/backend/app/infrastructure/storage/laboratorio_file_store.py", "x = 1\n"),
                           ("srv/backend/app/infrastructure/html_storage_adapter.py", ""),
                           ("opt/venv/lib/python3.14/site-packages/paquete/storage/__init__.py", ""),
                           ("opt/venv/lib/python3.14/site-packages/cryptography/ssh.py",
                            '_C = b"-----BEGIN OPENSSH PRIVATE KEY-----"\n'),
                           ("srv/frontend/dist/index.html", "<html></html>"), *plantar):
        destino = raiz / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")


def _correr(raiz: Path, monkeypatch, capsys):
    monkeypatch.setattr(os, "geteuid", lambda: 10001, raising=False)
    codigo = _cargar().main([str(raiz)])
    return codigo, json.loads(capsys.readouterr().out)


def test_root_es_un_hallazgo(tmp_path):
    _imagen(tmp_path)
    assert ("se_ejecuta_como_root", "uid=0") in _cargar().revisar(str(tmp_path), uid=0)


def test_imagen_limpia_con_paquete_storage_de_codigo_pasa(tmp_path, monkeypatch, capsys):
    _imagen(tmp_path)
    codigo, salida = _correr(tmp_path, monkeypatch, capsys)
    assert codigo == 0 and salida["hallazgos"] == []


@pytest.mark.parametrize("rel,contenido,motivo", [
    ("srv/backend/storage/pronosticos/p.json", "{}", "carpeta_de_datos"),
    ("srv/pub/carteras/c.json", "{}", "carpeta_de_datos"),
    ("srv/backend/app/infrastructure/storage/datos.sqlite3", "", "archivo_prohibido"),
    ("srv/backend/app/infrastructure/storage/volcado.html", "", "no_codigo_en_paquete_de_almacenes"),
    ("srv/backend/datos.sqlite", "", "archivo_prohibido"),
    ("srv/backend/cuentas.db", "", "archivo_prohibido"),
    ("srv/backend/.env", "X=1", "archivo_prohibido"),
    ("tmp/consola.privado.env", "X=1", "archivo_prohibido"),
    ("srv/backend/clave.pem", PEM, "clave_privada"),
    ("var/lib/otra/storage/x.json", "{}", "carpeta_de_datos_fuera_del_codigo"),
])
def test_datos_y_secretos_plantados_fallan(tmp_path, monkeypatch, capsys, rel, contenido, motivo):
    _imagen(tmp_path, [(rel, contenido)])
    codigo, salida = _correr(tmp_path, monkeypatch, capsys)
    assert codigo == 1 and motivo in {h["motivo"] for h in salida["hallazgos"]}
