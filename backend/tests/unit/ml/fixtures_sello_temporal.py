"""FIXTURES DE PRUEBA de la Etapa AE-75 -NO OPERATIVAS.

Construye respuestas RFC 3161 de prueba con campos controlados usando solo
bibliotecas mantenidas: `cryptography` 50.0.1 para claves, certificados
X.509 y firmas, y su codificador DER declarativo `cryptography.hazmat.asn1`
para TSTInfo, SignedData y los atributos firmados. No hay codificacion DER
escrita a mano.

Nada de este archivo es una autoridad de sellado operativa ni evidencia
fuera de las pruebas:

- claves generadas en cada ejecucion;
- certificados con nombres «... (fixture, no operativa)»;
- politicas en el arco de ejemplos `2.999`;
- instantes fijados por cada prueba, sin leer el reloj.

Una cadena correcta frente a la CA de este archivo no es una TSA aprobada.

Las manipulaciones (firma, impronta, certificado, politica, precision,
identificador del certificado, atributos firmados) se aplican al construir,
para que cada una sea independiente de las demas.
"""
from __future__ import annotations

import base64
import functools
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Literal

from cryptography import x509
from cryptography.hazmat import asn1
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

O = x509.ObjectIdentifier

OID_SIGNED_DATA = "1.2.840.113549.1.7.2"
OID_TSTINFO = "1.2.840.113549.1.9.16.1.4"
OID_DATA = "1.2.840.113549.1.7.1"
OID_CONTENT_TYPE = "1.2.840.113549.1.9.3"
OID_MESSAGE_DIGEST = "1.2.840.113549.1.9.4"
OID_SIGNING_CERTIFICATE = "1.2.840.113549.1.9.16.2.12"
OID_SIGNING_CERTIFICATE_V2 = "1.2.840.113549.1.9.16.2.47"
OID_RSA = "1.2.840.113549.1.1.1"
OID_SHA256_RSA = "1.2.840.113549.1.1.11"
OID_HASH = {"sha1": "1.3.14.3.2.26", "sha256": "2.16.840.1.101.3.4.2.1", "sha384": "2.16.840.1.101.3.4.2.2",
            "sha512": "2.16.840.1.101.3.4.2.3"}
_HASHLIB = {"sha1": hashlib.sha1, "sha256": hashlib.sha256, "sha384": hashlib.sha384, "sha512": hashlib.sha512}

POLITICA_DE_PRUEBA = "2.999.75.1"
POLITICA_NO_ADMITIDA = "2.999.75.2"
"""OID del arco de ejemplos {joint-iso-itu-t(2) example(999)}: solo pruebas."""

INICIO = datetime(2026, 1, 1, tzinfo=timezone.utc)
FIN = datetime(2036, 1, 1, tzinfo=timezone.utc)
_MARCA = "Fixture AE-75 (no operativa)"


# ---------------------------------------------------------------------------
# Esquemas ASN.1 de codificacion (RFC 3161 2.4.2, RFC 5652, RFC 5035)
# ---------------------------------------------------------------------------

@asn1.sequence
class _Alg:
    algorithm: O
    parameters: asn1.Null | None


@asn1.sequence
class _Impronta:
    hash_algorithm: _Alg
    hashed_message: bytes


@asn1.sequence
class _Precision:
    seconds: int | None
    millis: Annotated[int | None, asn1.Implicit(0)]
    micros: Annotated[int | None, asn1.Implicit(1)]


_NombreGeneral = (Annotated[asn1.Variant[x509.Name, Literal["directorio"]], asn1.Explicit(4)]
                  | Annotated[asn1.Variant[asn1.IA5String, Literal["dns"]], asn1.Implicit(2)])


@asn1.sequence
class _Extension:
    extn_id: O
    critical: Annotated[bool, asn1.Default(False)]
    extn_value: bytes


@asn1.sequence
class _TSTInfo:
    version: int
    policy: O
    message_imprint: _Impronta
    serial_number: int
    gen_time: asn1.GeneralizedTime
    accuracy: _Precision | None
    ordering: Annotated[bool, asn1.Default(False)]
    nonce: int | None
    tsa: Annotated[_NombreGeneral | None, asn1.Explicit(0)]
    extensions: Annotated[list[_Extension] | None, asn1.Implicit(1)]


@asn1.sequence
class _Atributo:
    attr_type: O
    attr_values: asn1.SetOf[asn1.TLV]


@asn1.sequence
class _EmisorYSerie:
    issuer: x509.Name
    serial: int


@asn1.sequence
class _SignerInfo:
    version: int
    sid: _EmisorYSerie
    digest_algorithm: _Alg
    signed_attrs: Annotated[asn1.SetOf[_Atributo] | None, asn1.Implicit(0)]
    signature_algorithm: _Alg
    signature: bytes


@asn1.sequence
class _Encap:
    e_content_type: O
    e_content: Annotated[bytes | None, asn1.Explicit(0)]


@asn1.sequence
class _SignedData:
    version: int
    digest_algorithms: asn1.SetOf[_Alg]
    encap: _Encap
    certificates: Annotated[asn1.SetOf[asn1.TLV] | None, asn1.Implicit(0)]
    signer_infos: asn1.SetOf[_SignerInfo]


@asn1.sequence
class _ContentInfo:
    content_type: O
    content: Annotated[_SignedData, asn1.Explicit(0)]


@asn1.sequence
class _EstadoPKI:
    status: int


@asn1.sequence
class _Respuesta:
    status: _EstadoPKI
    token: _ContentInfo | None


@asn1.sequence
class _ESSCertIDv2:
    hash_algorithm: _Alg | None
    cert_hash: bytes


@asn1.sequence
class _SigningCertificateV2:
    certs: list[_ESSCertIDv2]


@asn1.sequence
class _ESSCertID:
    cert_hash: bytes


@asn1.sequence
class _SigningCertificate:
    certs: list[_ESSCertID]


@asn1.sequence
class _PortadorTLV:
    v: asn1.TLV


@asn1.sequence
class _PortadorOID:
    v: O


@asn1.sequence
class _PortadorBytes:
    v: bytes


@asn1.sequence
class _PortadorSCv2:
    v: _SigningCertificateV2


@asn1.sequence
class _PortadorSCv1:
    v: _SigningCertificate


@asn1.sequence
class _PortadorCertificado:
    v: x509.Certificate


def _tlv(portador, valor):
    """TLV de un valor tipado, obtenido codificando y decodificando con la
    biblioteca (sin escribir cabeceras DER a mano)."""
    return asn1.decode_der(_PortadorTLV, asn1.encode_der(portador(v=valor))).v


def _alg(nombre: str, *, con_null: bool = False) -> _Alg:
    return _Alg(algorithm=O(OID_HASH[nombre]), parameters=asn1.Null() if con_null else None)


# ---------------------------------------------------------------------------
# Claves y certificados de prueba
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def clave(nombre: str) -> rsa.RSAPrivateKey:
    """Clave RSA-2048 de prueba generada en esta ejecucion; `nombre` solo la
    distingue en la cache."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def nombre(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, _MARCA),
                      x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def certificado(cn: str, clave_sujeto: str, *, emisor_cn: str, clave_emisor: str, serie: int, ca: bool,
                eku: tuple = (ExtendedKeyUsageOID.TIME_STAMPING,), eku_critica: bool = True,
                desde: datetime = INICIO, hasta: datetime = FIN,
                extension_critica_desconocida: bool = False) -> x509.Certificate:
    constructor = (x509.CertificateBuilder()
                   .subject_name(nombre(cn)).issuer_name(nombre(emisor_cn))
                   .public_key(clave(clave_sujeto).public_key()).serial_number(serie)
                   .not_valid_before(desde).not_valid_after(hasta))
    if ca:
        constructor = (constructor
                       .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                       .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False),
                                      critical=True))
    else:
        constructor = (constructor
                       .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                       .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False),
                                      critical=True))
        if eku:
            constructor = constructor.add_extension(x509.ExtendedKeyUsage(list(eku)), critical=eku_critica)
    if extension_critica_desconocida:
        constructor = constructor.add_extension(
            x509.UnrecognizedExtension(O("2.999.75.9"), b"\x05\x00"), critical=True)
    return constructor.sign(clave(clave_emisor), hashes.SHA256())


@dataclass(frozen=True)
class Mundo:
    """Certificados de prueba. `ca` es el ancla de las pruebas; `otra_ca`
    no se configura como ancla."""
    ca: x509.Certificate
    intermedia: x509.Certificate
    tsa: x509.Certificate
    tsa_via_intermedia: x509.Certificate
    tsa_ajena: x509.Certificate
    tsa_eku_no_critica: x509.Certificate
    tsa_eku_extra: x509.Certificate
    tsa_sin_eku: x509.Certificate
    tsa_caducada: x509.Certificate
    tsa_extension_desconocida: x509.Certificate
    otra_ca: x509.Certificate

    def clave_de(self, rol: str) -> str:
        return _CLAVE_POR_ROL[rol]


_CA = "CA de prueba AE-75 (fixture, no operativa)"
_OTRA_CA = "Otra CA de prueba AE-75 (fixture, no configurada como ancla)"
_INTERMEDIA = "CA intermedia de prueba AE-75 (fixture, no operativa)"
_CLAVE_POR_ROL = {"tsa": "tsa", "tsa_via_intermedia": "tsa", "tsa_ajena": "tsa", "tsa_eku_no_critica": "tsa",
                  "tsa_eku_extra": "tsa", "tsa_sin_eku": "tsa", "tsa_caducada": "tsa",
                  "tsa_extension_desconocida": "tsa"}


@functools.lru_cache(maxsize=None)
def mundo() -> Mundo:
    tsa_cn = "TSA de prueba AE-75 (fixture, no operativa)"

    def hoja(serie, **kw):
        emisor = kw.pop("emisor", (_CA, "ca"))
        return certificado(tsa_cn, "tsa", emisor_cn=emisor[0], clave_emisor=emisor[1], serie=serie, ca=False, **kw)

    return Mundo(
        ca=certificado(_CA, "ca", emisor_cn=_CA, clave_emisor="ca", serie=1, ca=True),
        intermedia=certificado(_INTERMEDIA, "intermedia", emisor_cn=_CA, clave_emisor="ca", serie=2, ca=True),
        tsa=hoja(10),
        tsa_via_intermedia=hoja(11, emisor=(_INTERMEDIA, "intermedia")),
        tsa_ajena=hoja(12, emisor=(_OTRA_CA, "otra_ca")),
        tsa_eku_no_critica=hoja(13, eku_critica=False),
        tsa_eku_extra=hoja(14, eku=(ExtendedKeyUsageOID.TIME_STAMPING, ExtendedKeyUsageOID.CODE_SIGNING)),
        tsa_sin_eku=hoja(15, eku=()),
        tsa_caducada=hoja(16, desde=datetime(2020, 1, 1, tzinfo=timezone.utc),
                          hasta=datetime(2021, 1, 1, tzinfo=timezone.utc)),
        tsa_extension_desconocida=hoja(17, extension_critica_desconocida=True),
        otra_ca=certificado(_OTRA_CA, "otra_ca", emisor_cn=_OTRA_CA, clave_emisor="otra_ca", serie=3, ca=True),
    )


def der(certificado_x509: x509.Certificate) -> bytes:
    return certificado_x509.public_bytes(serialization.Encoding.DER)


def pem(certificado_x509: x509.Certificate) -> bytes:
    return certificado_x509.public_bytes(serialization.Encoding.PEM)


def clave_pem(nombre_clave: str) -> bytes:
    """PEM sin cifrar de una clave de prueba, solo para el contraste con
    OpenSSL en archivos temporales de la prueba."""
    return clave(nombre_clave).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption())


# ---------------------------------------------------------------------------
# Tokens de prueba
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Opciones:
    """Cada campo controla una sola propiedad del token de prueba."""
    gen_time: datetime
    precision: tuple | None = (1, None, None)  # (seconds, millis, micros) o None: sin accuracy
    politica: str = POLITICA_DE_PRUEBA
    algoritmo_impronta: str = "sha256"
    impronta: bytes | None = None  # None: el hash de los datos
    serie: int = 1
    firmante: str = "tsa"  # rol en Mundo
    incluidos: tuple = ("firmante",)  # roles incluidos en certificates; "firmante" es el firmante
    identificador: str = "v2"  # v2, v2_sha384, v1, ninguno, v2_otro_certificado
    alterar_firma: bool = False
    alterar_contenido_tras_firmar: bool = False
    content_type_firmado: str = OID_TSTINFO
    tsa: str | None = None  # None, "propio", "ajeno"
    extension_critica_en_tstinfo: bool = False
    estado: int = 0


def _identificador(opciones: Opciones, cert: x509.Certificate) -> list:
    if opciones.identificador == "ninguno":
        return []
    if opciones.identificador == "v1":
        valor = _SigningCertificate(certs=[_ESSCertID(cert_hash=hashlib.sha1(der(cert)).digest())])
        return [_Atributo(attr_type=O(OID_SIGNING_CERTIFICATE), attr_values=asn1.SetOf([_tlv(_PortadorSCv1, valor)]))]
    if opciones.identificador == "v2_sha384":
        ess = _ESSCertIDv2(hash_algorithm=_alg("sha384"), cert_hash=hashlib.sha384(der(cert)).digest())
    elif opciones.identificador == "v2_otro_certificado":
        ess = _ESSCertIDv2(hash_algorithm=None, cert_hash=hashlib.sha256(der(mundo().tsa_ajena)).digest())
    else:
        ess = _ESSCertIDv2(hash_algorithm=None, cert_hash=hashlib.sha256(der(cert)).digest())
    valor = _SigningCertificateV2(certs=[ess])
    return [_Atributo(attr_type=O(OID_SIGNING_CERTIFICATE_V2), attr_values=asn1.SetOf([_tlv(_PortadorSCv2, valor)]))]


def _tstinfo(datos: bytes, opciones: Opciones, *, impronta: bytes | None = None) -> bytes:
    algoritmo = opciones.algoritmo_impronta
    valor_impronta = impronta if impronta is not None else (
        opciones.impronta if opciones.impronta is not None else _HASHLIB[algoritmo](datos).digest())
    precision = None if opciones.precision is None else _Precision(
        seconds=opciones.precision[0], millis=opciones.precision[1], micros=opciones.precision[2])
    firmante = getattr(mundo(), opciones.firmante)
    tsa = None
    if opciones.tsa == "propio":
        tsa = asn1.Variant(firmante.subject, "directorio")
    elif opciones.tsa == "ajeno":
        tsa = asn1.Variant(nombre("Otra TSA de prueba AE-75 (fixture)"), "directorio")
    extensiones = None
    if opciones.extension_critica_en_tstinfo:
        extensiones = [_Extension(extn_id=O("2.999.75.8"), critical=True, extn_value=b"\x05\x00")]
    return asn1.encode_der(_TSTInfo(
        version=1, policy=O(opciones.politica),
        message_imprint=_Impronta(hash_algorithm=_alg(algoritmo), hashed_message=valor_impronta),
        serial_number=opciones.serie, gen_time=asn1.GeneralizedTime(opciones.gen_time), accuracy=precision,
        ordering=False, nonce=None, tsa=tsa, extensions=extensiones))


def respuesta(datos: bytes, opciones: Opciones) -> bytes:
    """TimeStampResp DER de prueba sobre `datos` (los bytes del compromiso)."""
    m = mundo()
    firmante = getattr(m, opciones.firmante)
    contenido = _tstinfo(datos, opciones)
    atributos = [
        _Atributo(attr_type=O(OID_CONTENT_TYPE),
                  attr_values=asn1.SetOf([_tlv(_PortadorOID, O(opciones.content_type_firmado))])),
        _Atributo(attr_type=O(OID_MESSAGE_DIGEST),
                  attr_values=asn1.SetOf([_tlv(_PortadorBytes, hashlib.sha256(contenido).digest())])),
        *_identificador(opciones, firmante),
    ]
    conjunto = asn1.SetOf(atributos)
    firma = clave(m.clave_de(opciones.firmante)).sign(asn1.encode_der(conjunto), padding.PKCS1v15(),
                                                      hashes.SHA256())
    if opciones.alterar_firma:
        firma = firma[:-1] + bytes([firma[-1] ^ 0x01])
    if opciones.alterar_contenido_tras_firmar:
        contenido = _tstinfo(datos, opciones, impronta=b"\x00" * len(_HASHLIB[opciones.algoritmo_impronta]().digest()))
    incluidos = [firmante if r == "firmante" else getattr(m, r) for r in opciones.incluidos]
    certificados = asn1.SetOf([_tlv(_PortadorCertificado, c) for c in incluidos]) if incluidos else None
    firmante_info = _SignerInfo(
        version=1, sid=_EmisorYSerie(issuer=firmante.issuer, serial=firmante.serial_number),
        digest_algorithm=_alg("sha256"), signed_attrs=conjunto,
        signature_algorithm=_Alg(algorithm=O(OID_SHA256_RSA), parameters=asn1.Null()), signature=firma)
    datos_firmados = _SignedData(
        version=3, digest_algorithms=asn1.SetOf([_alg("sha256")]),
        encap=_Encap(e_content_type=O(OID_TSTINFO), e_content=contenido),
        certificates=certificados, signer_infos=asn1.SetOf([firmante_info]))
    token = _ContentInfo(content_type=O(OID_SIGNED_DATA), content=datos_firmados)
    return asn1.encode_der(_Respuesta(status=_EstadoPKI(status=opciones.estado),
                                      token=token if opciones.estado in (0, 1) else None))


def instante(texto: str) -> datetime:
    """Instante UTC de prueba a partir de 'AAAA-MM-DDTHH:MM:SS[.ffffff]Z'."""
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Contraste independiente fijado: token emitido por OpenSSL
# ---------------------------------------------------------------------------

OPENSSL_RESPUESTA_B64 = (
    "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"
    "MfWHPBnnfgz24a4aqJfZ"
)
OPENSSL_CA_B64 = (
    "MIIDWzCCAkOgAwIBAgIUBy9Eylzye2Ws3+j7z6jhveSzzzcwDQYJKoZIhvcNAQELBQAwNTEzMDEGA1UEAwwqQ0EgZGUgcHJ1ZWJh"
    "IEFFLTc1IChmaXh0dXJlLCBubyBvcGVyYXRpdmEpMB4XDTI2MDkyOTIzNTczN1oXDTM2MDkyNjIzNTczN1owNTEzMDEGA1UEAwwq"
    "Q0EgZGUgcHJ1ZWJhIEFFLTc1IChmaXh0dXJlLCBubyBvcGVyYXRpdmEpMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA"
    "o1934vMpan8XXrgF7POdugDaqb6RoHCTd5AAZ/XIJ74lRGvXn/womjXtdpyTrFH24eD/FieVT9KzYNjeCag5Zetl3beHpDn908mY"
    "Pv7F+jpMvUhSjmxkUt0CJxZTfvePiTtSfdC2XEKcKx3bB4BIeAa6WDZQ830Qg6jzsU3I8Kfs24kJkyg92RI+zxwvuXWBKttzQ7Go"
    "qvKqneQHSIMm5zLOpp4aYsgcqjUdv4G7xEynkyHY6cyB35sC2N2R/jmbgamLvCh+W0+S7K97by9djnQrPiBRcXZBuhKX3CU3ks5M"
    "Uiu2b09DIgZYmbdRAM6wWgMo6NeF0v6BoVtJNXv7TwIDAQABo2MwYTAdBgNVHQ4EFgQUnsWKw7LI9BimeguVg59dRSQnSe8wHwYD"
    "VR0jBBgwFoAUnsWKw7LI9BimeguVg59dRSQnSe8wDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMCAQYwDQYJKoZIhvcNAQEL"
    "BQADggEBAD4FIZxF3nhv0sJL+PD1bgxPGChf2aJrbDQT+iUz+KVZv3suLmv/1Lpkx5rmRKRt/Tggk9FLZ7rSlxpwYvflR/0SWEmG"
    "9Ptwj4mKg9b2PWSGOrFt0yBXxN/6Iqde6z43NceeErXGbRDkFzjvY1l3gpJIf0d3M6d6ZTv1Shb2gMw8ltYMIP/vFqq3BbDSvmru"
    "ZAmx52uoj5m1Sc6TBDvT5kA6/5l57WbFoDl7se0jwTlNy4dUWXQdXMNbMb6k3PV6jZu4tDxP+76XgrT4yGYaTiExLICF+XcFkuXE"
    "RE+wpp4f+HifWcJPK3M8MKlpqNAu1vQ0Kqv5Yg64cP3Erb7v0qE="
)
OPENSSL_COMPROMISO_B64 = (
    "eyJjb2RpZ29fanVlZ28iOiJCQUxPVE8iLCJjb250cmF0byI6ImNvbnRyYXRvLXZpbmN1bG8tcjAvMSIsImVzcXVlbWEiOiJjb21w"
    "cm9taXNvLXNlbGxvLXIwLW9iamV0aXZvLzEiLCJlc3F1ZW1hX2RlbF9wcm90b2NvbG8iOiJyZWdpc3Ryby1wcm9zcGVjdGl2by1t"
    "bC8xLjIiLCJoYXNoX2RlY2xhcmFjaW9uIjoiNWM3NWM1MDUxZDYzNDNkYzY0NjNlNzA5NDZkNzdiMjFkYjlkYTQ5YjAwMzMxOTdj"
    "ZWQ1NTg4MzI5MzNmY2VkNCIsInBsYXpvX3V0YyI6IjIwMjYtMTAtMTBUMDA6MDA6MDBaIiwicHJvY2VkZW5jaWFfZGVsX3BsYXpv"
    "Ijoic2ludGV0aWNhX2RlX3BydWViYSIsInByb3RvY29sb19oYXNoIjoiNGI1YjcyN2U3NGUzZjI4ZjhhOWU1NzRiYzk1NWFhNmNl"
    "ZDI4MzNlMGUwZDQ4NGMwZWQyYTU0ZTBjYmUwZTE4NyIsInJlZ2xhIjoiYWU3NC12aW5jdWxvLXIwLWNvbnRyYXRvLzEiLCJzb3J0"
    "ZW9fb2JqZXRpdm8iOjI3MTR9Cg=="
)
OPENSSL_ORIGEN = (
    "openssl ts -query -sha256 -cert -no_nonce -tspolicy 2.999.75.1 y openssl ts -reply (OpenSSL 3.0.13, "
    "sandbox Linux de Claude, 2026-09-30); CA y TSA de prueba RSA-2048 creadas con openssl req y x509; solo "
    "el certificado de la TSA incluido, ESSCertIDv2 con SHA-256, accuracy 1 s 500 ms 100 us; plazo sintetico "
    "2026-10-10T00:00:00Z")


def openssl_fijado() -> tuple[bytes, bytes, bytes]:
    """(respuesta, certificado de la CA, bytes del compromiso) del token
    emitido por `openssl ts -reply` en el sandbox Linux de Claude. Es una
    fixture: su genTime salio del reloj de ese sandbox y nunca cuenta como
    prueba de anterioridad."""
    return tuple(base64.b64decode(v) for v in (OPENSSL_RESPUESTA_B64, OPENSSL_CA_B64, OPENSSL_COMPROMISO_B64))
