"""E10.4: el perfil privado de la API queda ligado a UNA generacion aceptada (o no arranca)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.api.publica import perfil_privado as pp
from app.infrastructure.generaciones import importacion as im
from app.infrastructure.generaciones.formato import sha256_archivo
from tests.unit.generaciones import paquete_sintetico as ps

VARIABLES = {"DIRECTORIO_LABORATORIO_MODELOS": "laboratorio", "DIRECTORIO_CARTERAS_MODELOS": "carteras",
             "DIRECTORIO_PREDICCIONES_MODELOS": "predicciones", "DIRECTORIO_PRONOSTICOS_EXPERIMENTALES": "pronosticos"}


@pytest.fixture
def generacion(tmp_path):
    """Una generacion ACEPTADA sintetica: el paquete sin `base/` (lo que deja el importador)."""
    paquete, _, publica = ps.construir(tmp_path / "p")
    carpeta = tmp_path / "srv" / "generaciones" / paquete.name
    shutil.copytree(paquete, carpeta, ignore=shutil.ignore_patterns("base"))
    for a in VARIABLES.values():
        (carpeta / "archivos" / a).mkdir(parents=True, exist_ok=True)
    return carpeta, publica


class _Motor:
    """Motor de PostgreSQL sustituido: responde la fila de la base y la tabla `alembic_version`."""

    def __init__(self, fila, revisiones=(("0006",),)):
        self.fila, self.revisiones = fila, list(revisiones)

    def connect(self):
        motor = self

        class _C:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, sql):
                class _R:
                    def one(self):
                        return motor.fila

                    def all(self):
                        assert "alembic_version" in str(sql)
                        return motor.revisiones
                return _R()
        return _C()


def test_sin_generacion_el_perfil_no_cambia():
    entorno = {}
    assert pp.vincular_generacion(entorno) is None and entorno == {}


def test_vincula_los_almacenes_de_consulta_a_la_generacion(generacion):
    carpeta, publica = generacion
    entorno = {pp.GENERACION: str(carpeta), pp.GENERACION_CLAVE: str(publica),
               "DIRECTORIO_OPERACION": "/srv/sin-publicar/operacion"}
    assert pp.vincular_generacion(entorno) == carpeta.resolve()
    for variable, almacen in VARIABLES.items():
        assert Path(entorno[variable]) == carpeta.resolve() / "archivos" / almacen
    assert entorno["DIRECTORIO_OPERACION"] == "/srv/sin-publicar/operacion"


@pytest.mark.parametrize("caso", ["otro_directorio_de_consulta", "operativo_dentro", "sin_clave", "no_es_carpeta"])
def test_vinculacion_cerrada_ante_el_fallo(generacion, tmp_path, caso):
    carpeta, publica = generacion
    entorno = {pp.GENERACION: str(carpeta), pp.GENERACION_CLAVE: str(publica)}
    if caso == "otro_directorio_de_consulta":
        entorno["DIRECTORIO_CARTERAS_MODELOS"] = str(tmp_path / "otra")
    elif caso == "operativo_dentro":
        entorno["DIRECTORIO_OPERACION"] = str(carpeta / "archivos" / "operacion")
    elif caso == "sin_clave":
        del entorno[pp.GENERACION_CLAVE]
    else:
        entorno[pp.GENERACION] = str(tmp_path / "no-existe")
    with pytest.raises(pp.PerfilPrivadoNoValido):
        pp.vincular_generacion(entorno)


def _fila_correcta(carpeta):
    gid = carpeta.name
    return (im.nombre_base(gid, True), im.comentario(gid, sha256_archivo(carpeta / "manifiesto.json")[1]), "on")


def test_la_base_conectada_es_la_de_la_generacion(generacion):
    carpeta, publica = generacion
    assert pp.comprobar_generacion(carpeta, publica, _Motor(_fila_correcta(carpeta)))["id"] == carpeta.name


def _otro_ultimo(nota: str) -> str:
    """Cambia SIEMPRE el ultimo caracter (hex) por otro distinto (E104-TEST-08: `nota[:-1] + "0"` era nulo si la
    nota ya terminaba en 0)."""
    otro = nota[:-1] + ("1" if nota.endswith("0") else "0")
    assert otro != nota
    return otro


def test_la_mutacion_del_comentario_nunca_es_nula():
    for final in "0123456789abcdef":
        nota = "loteria-generacion:" + "a" * 32 + ":" + "b" * 63 + final
        assert _otro_ultimo(nota) != nota and len(_otro_ultimo(nota)) == len(nota)


def _clave_fija(raiz: Path) -> tuple[Path, Path]:
    """Clave Ed25519 FIJA (semilla constante, solo de prueba): la busqueda de abajo es reproducible."""
    import os

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    clave = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    raiz.mkdir(parents=True)
    privada, publica = raiz / "fija.pem", raiz / "fija.pub"
    descriptor = os.open(privada, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as f:
        f.write(clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()))
    publica.write_text(clave.public_key().public_bytes(serialization.Encoding.Raw,
                                                       serialization.PublicFormat.Raw).hex() + "\n")
    return privada, publica


def test_comentario_correcto_terminado_en_0_se_acepta_y_su_cambio_real_se_rechaza(tmp_path):
    """Control determinista de la rama de TEST-08: con una clave fija, el primer paquete sintetico cuyo comentario
    correcto termina en 0 se acepta y el comentario con el ultimo caracter realmente cambiado se rechaza."""
    claves = _clave_fija(tmp_path / "claves")
    for i in range(256):
        paquete, _, publica = ps.construir(tmp_path / f"p{i}", claves,
                                           archivos={f"archivos/pronosticos/BALOTO/2193-{i:064x}.json": b'{"x":1}\n'})
        carpeta = tmp_path / "srv" / "generaciones" / paquete.name
        shutil.copytree(paquete, carpeta, ignore=shutil.ignore_patterns("base"))
        base, nota, ro = _fila_correcta(carpeta)
        if nota.endswith("0"):
            break
    else:
        pytest.fail("sin comentario terminado en 0 en 256 paquetes deterministas")
    for a in VARIABLES.values():
        (carpeta / "archivos" / a).mkdir(parents=True, exist_ok=True)
    assert pp.comprobar_generacion(carpeta, publica, _Motor((base, nota, ro)))["id"] == carpeta.name
    distinto = _otro_ultimo(nota)
    assert distinto.endswith("1")
    with pytest.raises(pp.PerfilPrivadoNoValido, match="no es la de la generacion"):
        pp.comprobar_generacion(carpeta, publica, _Motor((base, distinto, ro)))


@pytest.mark.parametrize("cambio", ["otra_base", "otro_comentario", "escritura_por_defecto", "base_prep"])
def test_otra_base_o_sin_solo_lectura_no_arranca(generacion, cambio):
    carpeta, publica = generacion
    base, nota, ro = _fila_correcta(carpeta)
    fila = {"otra_base": ("loteria_prueba", nota, ro), "otro_comentario": (base, _otro_ultimo(nota), ro),
            "escritura_por_defecto": (base, nota, "off"),
            "base_prep": (im.nombre_base(carpeta.name, False), nota, ro)}[cambio]
    with pytest.raises(pp.PerfilPrivadoNoValido):
        pp.comprobar_generacion(carpeta, publica, _Motor(fila))


@pytest.mark.parametrize("dano", ["archivo_alterado", "archivo_de_mas", "sin_firma"])
def test_generacion_alterada_no_arranca(generacion, dano):
    carpeta, publica = generacion
    if dano == "archivo_alterado":
        objetivo = next(carpeta.glob("archivos/pronosticos/BALOTO/*.json"))
        objetivo.write_bytes(objetivo.read_bytes().replace(b"1", b"2"))
    elif dano == "archivo_de_mas":
        (carpeta / "archivos" / "pronosticos" / "nuevo.json").write_bytes(b"{}")
    else:
        (carpeta / "manifiesto.firma").unlink()
    with pytest.raises(pp.PerfilPrivadoNoValido):
        pp.comprobar_generacion(carpeta, publica, _Motor(_fila_correcta(carpeta)))
