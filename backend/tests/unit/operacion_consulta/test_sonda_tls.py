"""TLS/mTLS real en loopback y PKI efímera de archivo; sin almacenes del sistema."""
from __future__ import annotations

import json
import ssl
import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from despliegue.operacion_consulta.docker import Docker


def emitir(raiz, nombre, ca=None, *, servidor=None):
    llave = ec.generate_private_key(ec.SECP256R1())
    sujeto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nombre)])
    ahora = datetime.now(timezone.utc)
    identificador = x509.SubjectKeyIdentifier.from_public_key(llave.public_key())
    emisor = ca[1].extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value if ca else identificador
    b = (x509.CertificateBuilder().subject_name(sujeto).issuer_name(ca[1].subject if ca else sujeto)
         .public_key(llave.public_key()).serial_number(x509.random_serial_number())
         .not_valid_before(ahora - timedelta(minutes=1)).not_valid_after(ahora + timedelta(hours=1))
         .add_extension(x509.BasicConstraints(ca=ca is None, path_length=0 if ca is None else None), critical=True)
         .add_extension(identificador, critical=False)
         .add_extension(x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(emisor), critical=False)
         .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                                     data_encipherment=False, key_agreement=False, key_cert_sign=ca is None,
                                     crl_sign=ca is None, encipher_only=None, decipher_only=None), critical=True))
    if servidor:
        b = b.add_extension(x509.SubjectAlternativeName([x509.DNSName(servidor)]), critical=False)
    if ca:
        b = b.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH if servidor
                                                 else ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
    cert = b.sign(ca[0] if ca else llave, hashes.SHA256())
    (raiz / (nombre + ".crt")).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (raiz / (nombre + ".key")).write_bytes(llave.private_bytes(serialization.Encoding.PEM,
          serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return llave, cert


@pytest.fixture
def servidor_tls(tmp_path, plan):
    carpeta = tmp_path / "tls"
    carpeta.mkdir(mode=0o700)
    ca = emitir(carpeta, "ca-servidor")
    emitir(carpeta, "servidor", ca, servidor=plan.host)
    emitir(carpeta, "cliente", ca)

    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/api/v1/estado"
            assert self.headers["Host"] == plan.host + ":" + str(self.server.server_port)
            assert self.connection.getpeercert()
            cerrado = (carpeta / "mantenimiento").exists()
            b = json.dumps({"base": "disponible", "solicitudes": 1}).encode()
            self.send_response(503 if cerrado else 200)
            if cerrado:
                self.send_header("Retry-After", "30")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def log_message(self, *args):
            pass

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.load_cert_chain(str(carpeta / "servidor.crt"), str(carpeta / "servidor.key"))
    contexto.load_verify_locations(str(carpeta / "ca-servidor.crt"))
    contexto.verify_mode = ssl.CERT_REQUIRED
    contexto.verify_flags |= ssl.VERIFY_X509_STRICT
    servidor.socket = contexto.wrap_socket(servidor.socket, server_side=True)
    hilo = threading.Thread(target=servidor.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    hilo.start()
    yield replace(plan, puerto=servidor.server_port, pki_sonda=str(carpeta)), carpeta
    servidor.shutdown()
    servidor.server_close()
    hilo.join(2)
    assert not hilo.is_alive()


def test_sonda_real_mtls_preserva_sni_y_host(almacen, servidor_tls):
    plan, _ = servidor_tls
    d = Docker(almacen, "a" * 32)._tls(plan, time.monotonic() + 5)
    assert d == {"base": "disponible", "solicitudes": 1}


def test_sonda_no_desactiva_validacion_del_nombre(almacen, servidor_tls):
    plan, _ = servidor_tls
    with pytest.raises(ssl.SSLCertVerificationError) as error:
        Docker(almacen, "a" * 32)._tls(replace(plan, host="otro.ensayo.invalid"), time.monotonic() + 5)
    assert error.value.verify_code == 62  # X509_V_ERR_HOSTNAME_MISMATCH; la cadena es valida.


def test_sonda_no_acepta_cliente_de_otra_ca(almacen, servidor_tls):
    plan, carpeta = servidor_tls
    otra = emitir(carpeta, "otra-ca")
    emitir(carpeta, "cliente", otra)
    with pytest.raises(ssl.SSLError):
        Docker(almacen, "a" * 32)._tls(plan, time.monotonic() + 5)


def test_confirmacion_mantenimiento_exige_503_y_retry_after(almacen, servidor_tls):
    from despliegue.operacion_consulta.modelo import Rechazo
    plan, carpeta = servidor_tls
    op = Docker(almacen, "a" * 32)
    with pytest.raises(Rechazo, match="mantenimiento_no_confirmado"):
        op._cierre(plan, time.monotonic() + 5)
    (carpeta / "mantenimiento").write_bytes(b"1")
    assert op._cierre(plan, time.monotonic() + 5) is None
