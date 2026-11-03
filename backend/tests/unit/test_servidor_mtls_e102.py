"""Fase 10 (E10.2, v2, F1023-WIN-01): servidor mTLS del ensayo focal, ejecutado DE VERDAD en un subproceso con una
CA SINTETICA efimera. Acredita el servidor en esta plataforma (Linux en la verificacion de Claude); no acredita
Windows, PowerShell ni Brave."""
from __future__ import annotations

import datetime as dt
import http.client
import json
import os
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

SERVIDOR = Path(__file__).resolve().parents[3] / "despliegue" / "consulta-privada" / "windows" / "servidor_mtls_e102.py"
CONTRASENA = b"solo-prueba-efimera"


def _nombre(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _pki(d: Path):
    ahora = dt.datetime.now(dt.timezone.utc)

    def ca(cn):
        k = ec.generate_private_key(ec.SECP256R1())
        c = (x509.CertificateBuilder().subject_name(_nombre(cn)).issuer_name(_nombre(cn)).public_key(k.public_key())
             .serial_number(x509.random_serial_number()).not_valid_before(ahora - dt.timedelta(minutes=1))
             .not_valid_after(ahora + dt.timedelta(hours=2))
             .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
             .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True)
             .add_extension(x509.SubjectKeyIdentifier.from_public_key(k.public_key()), False)
             .sign(k, hashes.SHA256()))
        return k, c

    def hoja(cn, autoridad, uso, san=False):
        ca_k, ca_c = autoridad
        k = ec.generate_private_key(ec.SECP256R1())
        b = (x509.CertificateBuilder().subject_name(_nombre(cn)).issuer_name(ca_c.subject).public_key(k.public_key())
             .serial_number(x509.random_serial_number()).not_valid_before(ahora - dt.timedelta(minutes=1))
             .not_valid_after(ahora + dt.timedelta(hours=2))
             .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
             .add_extension(x509.ExtendedKeyUsage([uso]), False)
             .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_k.public_key()), False)
             .add_extension(x509.SubjectKeyIdentifier.from_public_key(k.public_key()), False))
        if san:
            b = b.add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), False)
        return k, b.sign(ca_k, hashes.SHA256())

    propia, ajena = ca("CA ensayo"), ca("CA ajena")
    sk, sc = hoja("localhost", propia, ExtendedKeyUsageOID.SERVER_AUTH, san=True)
    (d / "servidor.pfx").write_bytes(pkcs12.serialize_key_and_certificates(
        b"s", sk, sc, None, serialization.BestAvailableEncryption(CONTRASENA)))
    (d / "ca.pem").write_bytes(propia[1].public_bytes(serialization.Encoding.PEM))
    for nombre, cn, autoridad in (("cliente", "invitado-brave", propia), ("otro", "otra-persona", propia),
                                  ("ajeno", "invitado-brave", ajena)):
        k, c = hoja(cn, autoridad, ExtendedKeyUsageOID.CLIENT_AUTH)
        (d / f"{nombre}.crt").write_bytes(c.public_bytes(serialization.Encoding.PEM))
        (d / f"{nombre}.key").write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                          serialization.NoEncryption()))


def _puerto():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _arrancar(d: Path, *, plazo=30, contrasena=CONTRASENA, extra=()):
    puerto, resultado = _puerto(), d / "resultado.json"
    proceso = subprocess.Popen([sys.executable, "-B", str(SERVIDOR), "--pfx", str(d / "servidor.pfx"), "--ca",
                                str(d / "ca.pem"), "--puerto", str(puerto), "--resultado", str(resultado),
                                "--plazo", str(plazo), "--parar", str(d / "parar"), "--plazo-handshake", "2", *extra],
                               stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proceso.stdin.write(contrasena + b"\n")
    proceso.stdin.close()
    limite = time.monotonic() + 15
    while time.monotonic() < limite and proceso.poll() is None:
        if resultado.exists() and json.loads(resultado.read_text())["estado"] == "escuchando":
            break
        time.sleep(0.05)
    return proceso, puerto, resultado


def _get(d: Path, puerto: int, cliente: str | None):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(d / "ca.pem")
    if cliente:
        ctx.load_cert_chain(d / f"{cliente}.crt", d / f"{cliente}.key")
    c = http.client.HTTPSConnection("localhost", puerto, context=ctx, timeout=5)
    try:
        c.request("GET", "/")
        r = c.getresponse()
        return r.status, r.read()
    finally:
        c.close()


def _fin(proceso, segundos=10):
    try:
        return proceso.wait(timeout=segundos)
    finally:
        if proceso.poll() is None:
            proceso.kill()
            proceso.wait(5)


@pytest.fixture()
def pki(tmp_path):
    _pki(tmp_path)
    return tmp_path


def test_exito_resultado_persistido_antes_de_responder_y_parada_cooperativa(pki):
    proceso, puerto, resultado = _arrancar(pki)
    estado, cuerpo = _get(pki, puerto, "cliente")
    assert estado == 200 and b"invitado-brave" in cuerpo
    datos = json.loads(resultado.read_text())  # ya escrito, antes de pedir el cierre
    assert datos["estado"] == "verificado" and datos["cn"] == ["invitado-brave"]
    (pki / "parar").write_text("", encoding="ascii")
    assert _fin(proceso) == 0
    final = json.loads(resultado.read_text())
    assert final["motivo_fin"] == "parada_cooperativa" and final["fin"] and final["cn"] == ["invitado-brave"]


@pytest.mark.parametrize("fin", ["terminar", "matar"])
def test_resultado_sobrevive_a_un_fin_forzado_tras_el_get(pki, fin):
    proceso, puerto, resultado = _arrancar(pki)
    assert _get(pki, puerto, "cliente")[0] == 200
    proceso.terminate() if fin == "terminar" else proceso.kill()
    _fin(proceso)
    assert json.loads(resultado.read_text())["cn"] == ["invitado-brave"]


def test_sin_interaccion_vence_el_plazo_sin_resultado(pki):
    proceso, _, resultado = _arrancar(pki, plazo=1.5)
    assert _fin(proceso) == 2
    datos = json.loads(resultado.read_text())
    assert datos["estado"] == "sin_resultado" and datos["motivo_fin"] == "plazo" and datos["cn"] == []


def test_cn_incorrecto_recibe_403_y_no_verifica(pki):
    proceso, puerto, resultado = _arrancar(pki)
    assert _get(pki, puerto, "otro")[0] == 403
    (pki / "parar").write_text("", encoding="ascii")
    assert _fin(proceso) == 2
    datos = json.loads(resultado.read_text())
    assert datos["rechazos_cn"] == ["otra-persona"] and datos["cn"] == []


@pytest.mark.parametrize("cliente", [None, "ajeno"])
def test_sin_certificado_o_de_otra_ca_falla_el_handshake(pki, cliente):
    proceso, puerto, resultado = _arrancar(pki)
    with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
        _get(pki, puerto, cliente)
    time.sleep(0.3)
    (pki / "parar").write_text("", encoding="ascii")
    assert _fin(proceso) == 2
    datos = json.loads(resultado.read_text())
    assert datos["handshakes_fallidos"] >= 1 and datos["cn"] == []


def test_un_cliente_que_no_completa_tls_no_bloquea_a_otros(pki):
    proceso, puerto, resultado = _arrancar(pki)
    colgado = socket.create_connection(("127.0.0.1", puerto))  # nunca envia el ClientHello
    try:
        assert _get(pki, puerto, "cliente")[0] == 200
    finally:
        colgado.close()
    (pki / "parar").write_text("", encoding="ascii")
    assert _fin(proceso) == 0


def test_arranque_fallido_con_contrasena_erronea(pki):
    proceso, _, resultado = _arrancar(pki, contrasena=b"otra")
    assert _fin(proceso) == 3
    assert json.loads(resultado.read_text())["estado"] == "arranque_fallido"


def test_el_resultado_nunca_queda_a_medias():
    texto = SERVIDOR.read_text(encoding="utf-8")
    assert "os.replace(temporal, self.ruta)" in texto and "os.fsync" in texto
