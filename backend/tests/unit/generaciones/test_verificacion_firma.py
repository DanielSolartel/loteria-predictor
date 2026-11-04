"""E10.4: integridad, autenticidad e identidad de un paquete ANTES de usarlo (sin base de datos)."""
from __future__ import annotations

import os

import pytest

from app.infrastructure.generaciones import firma
from app.infrastructure.generaciones.formato import GeneracionNoValida
from app.infrastructure.generaciones.verificacion import verificar
from tests.unit.generaciones import paquete_sintetico as ps


@pytest.fixture
def paquete(tmp_path):
    return ps.construir(tmp_path)


def test_paquete_valido(paquete):
    carpeta, _, publica = paquete
    assert verificar(carpeta, publica)["id"] == carpeta.name


@pytest.mark.parametrize("dano", ["byte_alterado", "archivo_de_mas", "archivo_de_menos", "enlace_simbolico",
                                  "firma_alterada", "manifiesto_no_canonico", "carpeta_renombrada", "volcado_alterado"])
def test_cualquier_alteracion_invalida_el_paquete(paquete, dano):
    carpeta, _, publica = paquete
    estimador = next(carpeta.glob("archivos/laboratorio/modelos/BALOTO/estimadores/*.pkl"))
    if dano == "byte_alterado":
        datos = bytearray(estimador.read_bytes())
        datos[0] ^= 1
        estimador.write_bytes(bytes(datos))
    elif dano == "archivo_de_mas":
        (carpeta / "archivos" / "pronosticos" / "BALOTO" / "extra.json").write_bytes(b"{}\n")
    elif dano == "archivo_de_menos":
        estimador.unlink()
    elif dano == "enlace_simbolico":
        (carpeta / "archivos" / "enlace").symlink_to(estimador)
    elif dano == "firma_alterada":
        texto = (carpeta / "manifiesto.firma").read_text()
        (carpeta / "manifiesto.firma").write_text(("1" if texto[0] != "1" else "2") + texto[1:])
    elif dano == "manifiesto_no_canonico":
        (carpeta / "manifiesto.json").write_bytes((carpeta / "manifiesto.json").read_bytes().replace(b":", b": ", 1))
    elif dano == "carpeta_renombrada":
        carpeta = carpeta.rename(carpeta.with_name("f" * 32))
    elif dano == "volcado_alterado":
        (carpeta / "base" / "juegos.jsonl").write_bytes(b'{"codigo":"MILOTO","id":"1"}\n')
    with pytest.raises(GeneracionNoValida):
        verificar(carpeta, publica)


def test_otra_clave_publica_no_valida(paquete, tmp_path):
    carpeta, _, _ = paquete
    firma.generar(tmp_path / "otra.pem", tmp_path / "otra.pub")
    with pytest.raises(GeneracionNoValida, match="otra clave"):
        verificar(carpeta, tmp_path / "otra.pub")


def test_firma_valida_de_otra_clave_con_id_de_clave_falsificado(paquete, tmp_path):
    """Un atacante con su propia clave firma un manifiesto que declara el identificador de la clave legitima."""
    carpeta, _, publica = paquete
    firma.generar(tmp_path / "atacante.pem", tmp_path / "atacante.pub")
    legitimo = firma.cargar_publica(publica)[1]
    nueva = ps.refirmar(carpeta, tmp_path / "atacante.pem", lambda m: m.update(clave_firma=legitimo))
    with pytest.raises(GeneracionNoValida, match="firma"):
        verificar(nueva, publica)


def test_id_que_no_es_la_huella_del_manifiesto(paquete):
    carpeta, privada, publica = paquete
    nueva = ps.refirmar(carpeta, privada, lambda m: None)
    import json
    m = json.loads((nueva / "manifiesto.json").read_text())
    m["id"] = "0" * 32
    from app.infrastructure.generaciones.formato import canonico
    (nueva / "manifiesto.json").write_bytes(canonico(m))
    (nueva / "manifiesto.firma").write_text(firma.firmar(firma.cargar_privada(privada), canonico(m)) + "\n")
    with pytest.raises(GeneracionNoValida):
        verificar(nueva, publica)


def test_coherencia_con_rechazos_no_se_acepta_aunque_este_firmada(paquete):
    carpeta, privada, publica = paquete
    from app.infrastructure.generaciones.formato import canonico, sha256_bytes

    rechazo = {**ps.COHERENCIA, "rechazos": [{"motivo": "historico_de_entrada_ausente"}]}
    datos = canonico(rechazo)
    (carpeta / "coherencia.json").write_bytes(datos)
    nueva = ps.refirmar(carpeta, privada, lambda m: m["archivos"].update(
        {"coherencia.json": {"bytes": len(datos), "sha256": sha256_bytes(datos)}}))
    with pytest.raises(GeneracionNoValida, match="coherencia"):
        verificar(nueva, publica)


def test_alcance_distinto_del_esperado(paquete):
    carpeta, _, publica = paquete
    with pytest.raises(GeneracionNoValida, match="alcance"):
        verificar(carpeta, publica, alcance="respaldo")


@pytest.mark.skipif(os.name != "posix", reason="permisos POSIX")
def test_clave_privada_legible_por_otros_se_rechaza(tmp_path):
    firma.generar(tmp_path / "f.pem", tmp_path / "f.pub")
    assert os.stat(tmp_path / "f.pem").st_mode & 0o777 == 0o600
    os.chmod(tmp_path / "f.pem", 0o644)
    with pytest.raises(GeneracionNoValida, match="0600"):
        firma.cargar_privada(tmp_path / "f.pem")


def test_las_claves_nunca_se_sobrescriben(tmp_path):
    firma.generar(tmp_path / "f.pem", tmp_path / "f.pub")
    with pytest.raises(FileExistsError):
        firma.generar(tmp_path / "f.pem", tmp_path / "otra.pub")
