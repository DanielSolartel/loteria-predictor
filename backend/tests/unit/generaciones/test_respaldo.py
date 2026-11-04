"""E10.4: respaldo cifrado (X25519 + HKDF + AES-256-GCM por bloques), verificacion y retencion (sin base)."""
from __future__ import annotations

import datetime as dt
import json
import struct

import pytest

from app.infrastructure.generaciones import respaldo
from app.infrastructure.generaciones.formato import GeneracionNoValida, canonico, sha256_archivo
from app.infrastructure.generaciones.verificacion import verificar
from tests.unit.generaciones import paquete_sintetico as ps


@pytest.fixture
def entorno(tmp_path):
    grande = bytes(range(256)) * (10 * 1024)  # ~2.6 MB: al menos tres bloques cifrados
    archivos = {"archivos/laboratorio/modelos/BALOTO/estimadores/" + "d" * 64 + ".pkl": grande,
                "archivos/pronosticos/BALOTO/1-" + "e" * 64 + ".json": b'{"p":1}\n'}
    paquete, _, publica_firma = ps.construir(tmp_path, archivos=archivos, alcance="respaldo")
    respaldo.generar_claves(tmp_path / "r.pem", tmp_path / "r.pub")
    catalogo = respaldo.respaldar(paquete, tmp_path / "r.pub", tmp_path / "respaldos")
    return {"paquete": paquete, "firma": publica_firma, "archivo": tmp_path / "respaldos" / catalogo["archivo"],
            "catalogo": catalogo, "tmp": tmp_path}


def test_ida_y_vuelta_exacta_y_sin_texto_en_claro(entorno):
    cifrado = entorno["archivo"].read_bytes()
    assert b"BALOTO" not in cifrado and b'{"p":1}' not in cifrado
    extraido = respaldo.descifrar(entorno["archivo"], entorno["tmp"] / "r.pem", entorno["tmp"] / "fuera")
    assert verificar(extraido, entorno["firma"], alcance="respaldo")["id"] == entorno["paquete"].name
    for ruta in entorno["paquete"].rglob("*"):
        if ruta.is_file():
            assert (extraido / ruta.relative_to(entorno["paquete"])).read_bytes() == ruta.read_bytes()
    assert respaldo.comprobar_sin_descifrar(entorno["archivo"])["sha256"] == sha256_archivo(entorno["archivo"])[1]


def _bloques(datos: bytes):
    inicio = len(respaldo.MAGIA) + 4 + struct.unpack(">I", datos[len(respaldo.MAGIA):len(respaldo.MAGIA) + 4])[0]
    cabecera, posiciones, i = datos[:inicio], [], inicio
    while i < len(datos):
        (n,) = struct.unpack(">I", datos[i:i + 4])
        posiciones.append(datos[i:i + 4 + n])
        i += 4 + n
    return cabecera, posiciones


@pytest.mark.parametrize("dano", ["bit_en_un_bloque", "bloques_intercambiados", "bloque_final_quitado",
                                  "datos_anadidos", "cabecera_alterada", "bloque_duplicado"])
def test_alteraciones_del_cifrado_se_detectan(entorno, dano):
    datos = entorno["archivo"].read_bytes()
    cabecera, bloques = _bloques(datos)
    assert len(bloques) >= 3
    if dano == "bit_en_un_bloque":
        b = bytearray(bloques[0])
        b[10] ^= 1
        bloques[0] = bytes(b)
    elif dano == "bloques_intercambiados":
        bloques[0], bloques[1] = bloques[1], bloques[0]
    elif dano == "bloque_final_quitado":
        bloques = bloques[:-1]
    elif dano == "datos_anadidos":
        bloques.append(b"\x00\x00\x00\x01x")
    elif dano == "bloque_duplicado":
        bloques.insert(1, bloques[0])
    elif dano == "cabecera_alterada":
        d = json.loads(cabecera[len(respaldo.MAGIA) + 4:])
        d["creado_en"] = "2020-01-01T00:00:00+00:00"
        nueva = canonico(d)
        cabecera = respaldo.MAGIA + struct.pack(">I", len(nueva)) + nueva
    alterado = entorno["tmp"] / "alterado.lpr"
    alterado.write_bytes(cabecera + b"".join(bloques))
    with pytest.raises(GeneracionNoValida):
        respaldo.descifrar(alterado, entorno["tmp"] / "r.pem", entorno["tmp"] / "fuera")


def test_otra_clave_privada_no_descifra(entorno):
    respaldo.generar_claves(entorno["tmp"] / "o.pem", entorno["tmp"] / "o.pub")
    with pytest.raises(GeneracionNoValida, match="otra clave"):
        respaldo.descifrar(entorno["archivo"], entorno["tmp"] / "o.pem", entorno["tmp"] / "fuera")


def test_catalogo_detecta_un_cambio_sin_la_clave_privada(entorno):
    datos = bytearray(entorno["archivo"].read_bytes())
    datos[-1] ^= 1
    entorno["archivo"].write_bytes(bytes(datos))
    with pytest.raises(GeneracionNoValida, match="catalogo"):
        respaldo.comprobar_sin_descifrar(entorno["archivo"])


# --- retencion -----------------------------------------------------------------------------------------------------
def _respaldos_falsos(carpeta, fechas):
    carpeta.mkdir()
    for fecha in fechas:
        nombre = f"{fecha:%Y%m%dT%H%M%S%fZ}-{'a' * 32}.lpr"
        (carpeta / nombre).write_bytes(nombre.encode())
        tam, sha = sha256_archivo(carpeta / nombre)
        (carpeta / f"{nombre}.json").write_bytes(canonico({"archivo": nombre, "bytes": tam, "sha256": sha,
                                                           "creado_en": fecha.isoformat()}))
    return carpeta


def test_politica_gfs_configurable(tmp_path):
    base = dt.datetime(2026, 11, 4, 3, tzinfo=dt.timezone.utc)
    fechas = [base - dt.timedelta(hours=12 * i) for i in range(200)]  # dos por dia durante 100 dias
    carpeta = _respaldos_falsos(tmp_path / "r", fechas)
    plan = respaldo.plan_de_retencion(carpeta, diarios=3, semanales=2, mensuales=2, minimo=1)
    conservados = sorted(dt.datetime.strptime(n[:22], "%Y%m%dT%H%M%S%fZ").replace(tzinfo=dt.timezone.utc)
                         for n in plan["conservar"])
    dias = {f.date() for f in conservados}
    assert {(base - dt.timedelta(days=i)).date() for i in range(3)} <= dias  # los 3 ultimos dias
    assert len(plan["conservar"]) <= 3 + 2 + 2 and len(plan["conservar"]) + len(plan["borrar"]) == 200
    assert base in conservados  # siempre el mas reciente
    # En seco no se borra nada; al aplicar, solo lo planificado.
    assert len(list(carpeta.glob("*.lpr"))) == 200
    borrados = respaldo.aplicar_retencion(carpeta, plan)
    assert sorted(borrados) == plan["borrar"] and sorted(p.name for p in carpeta.glob("*.lpr")) == plan["conservar"]


def test_retencion_nunca_borra_un_respaldo_alterado_o_sin_catalogo(tmp_path):
    base = dt.datetime(2026, 11, 4, tzinfo=dt.timezone.utc)
    carpeta = _respaldos_falsos(tmp_path / "r", [base - dt.timedelta(days=i) for i in range(5)])
    viejo = sorted(carpeta.glob("*.lpr"))[0]
    viejo.write_bytes(b"alterado")  # ya no coincide con su catalogo
    (carpeta / "suelto.lpr").write_bytes(b"sin catalogo")
    plan = respaldo.plan_de_retencion(carpeta, diarios=1, semanales=0, mensuales=0)
    assert viejo.name not in plan["borrar"] and set(plan["no_considerados"]) == {viejo.name, "suelto.lpr"}
    respaldo.aplicar_retencion(carpeta, plan)
    assert viejo.exists() and (carpeta / "suelto.lpr").exists()


def test_politica_no_valida(tmp_path):
    with pytest.raises(ValueError):
        respaldo.plan_de_retencion(tmp_path, diarios=-1)
    with pytest.raises(ValueError):
        respaldo.plan_de_retencion(tmp_path, minimo=0)
