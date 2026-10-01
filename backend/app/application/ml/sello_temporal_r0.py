"""
Sello temporal RFC 3161 del compromiso R0 por objetivo -Etapa AE-75,
validada (solo como implementacion y verificacion preparatoria sobre
datos, anclas y plazos sinteticos; el plano temporal no llega a superada y
la puerta R0 final sigue rechazada).

Ruta de verificacion reproducible para un token de tiempo (RFC 3161,
actualizado por RFC 5816) sobre un compromiso canonico y versionado,
`compromiso-sello-r0-objetivo/1`. Sus bytes comprometen:

- la version del compromiso, el contrato de AE-74, la version 1.2 del
  protocolo y su regla;
- el hash del protocolo y el hash de la declaracion R0;
- el juego, el objetivo y un plazo UTC con su procedencia.

Un sello de un objetivo no sirve para otro. D8 (AE-75, aprobada por el
operador solo para el modelo sintetico):

- el corte (numero de sorteo) y el plazo (instante UTC) son variables
  distintas;
- «anterior» solo si genTime + accuracy + margen < plazo; la igualdad no
  pasa y un intervalo que cruza el plazo no es concluyente;
- sin accuracy ni precision comprobable en la politica de la TSA, el
  resultado queda pendiente; nunca se supone cero;
- en AE-75 solo se admite un plazo sintetico explicito. El plazo operativo
  y `calendario_oficial` siguen sin fijar, y sellar un plazo no prueba que
  sea oficial.

La criptografia no esta escrita aqui:

- `rfc3161-client` (OpenSSL incorporado) verifica la firma CMS, la cadena
  frente a un ancla explicita en genTime, el proposito y la impronta;
- `cryptography` comprueba certificados, firma y claves, y su decodificador
  DER declarativo lee genTime, accuracy y el identificador ESSCertIDv2;
- este modulo solo compara valores ya decodificados y calcula el intervalo
  con aritmetica racional exacta.

`HERRAMIENTAS` documenta que comprueba cada una. Con solo anclas de prueba
y sin datos de revocacion, el plano temporal nunca pasa de `pendiente`. No
prueba autenticacion de R0, recepcion de predicciones ni completitud o
unicidad del canal, y `evaluar_admision` y su puerta R0 final de AE-74 no
cambian.

R0, R9 y las ocho condiciones siguen `sin_fijar`; el expediente sigue en
`expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`. Sin red, reloj
local, fechas de archivo, datos reales ni sellos operativos.
"""
import functools
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from types import MappingProxyType, SimpleNamespace

from app.application.ml import contrato_vinculo_r0 as _contrato
from app.application.ml import registro_prospectivo as _rp

# ---------------------------------------------------------------------------
# Compromiso versionado
# ---------------------------------------------------------------------------

ESQUEMA_COMPROMISO = "compromiso-sello-r0-objetivo/1"
CLAVES_DEL_COMPROMISO = ("esquema", "contrato", "esquema_del_protocolo", "regla", "protocolo_hash",
                         "hash_declaracion", "codigo_juego", "sorteo_objetivo", "plazo_utc", "procedencia_del_plazo")
PROCEDENCIAS_DEL_PLAZO = ("sintetica_de_prueba",)
"""Unica procedencia admitida en AE-75. La fuente operativa (un calendario
oficial identificado, versionado y publicado antes del cierre) sigue
pendiente de seleccion y verificacion."""


class CompromisoInvalido(ValueError):
    """Compromiso que no puede construirse o leerse; `motivo` es la causa."""

    def __init__(self, motivo: str, detalle: str = ""):
        super().__init__(motivo, detalle)

    @property
    def motivo(self) -> str:
        return self.args[0]

    def __str__(self) -> str:
        return f"{self.args[0]}: {self.args[1]}" if self.args[1] else self.args[0]


# ---------------------------------------------------------------------------
# Instantes UTC exactos
# ---------------------------------------------------------------------------

_EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)
_PLAZO = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d*[1-9]))?Z")
_GEN_TIME = re.compile(r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?:\.(\d*[1-9]))?Z")
_DECIMAL = re.compile(r"(\d+)(?:\.(\d*[1-9]))?")


class SegundoIntercalar(ValueError):
    """genTime con segundo 60: no hay regla para compararlo con un plazo."""


def _segundos(anio, mes, dia, hora, minuto, segundo, fraccion) -> Fraction:
    base = datetime(int(anio), int(mes), int(dia), int(hora), int(minuto), int(segundo), tzinfo=timezone.utc)
    enteros = (base - _EPOCA) // timedelta(seconds=1)
    return Fraction(enteros) + (Fraction(int(fraccion), 10 ** len(fraccion)) if fraccion else 0)


def instante_de_plazo(texto: str) -> Fraction:
    """Segundos exactos desde 1970-01-01T00:00:00Z de un plazo
    'AAAA-MM-DDTHH:MM:SS[.f]Z'. Solo UTC explicito con Z, sin desfase, sin
    ceros finales en la fraccion (una sola escritura por instante) y sin
    segundo 60."""
    if not isinstance(texto, str):
        raise ValueError("el plazo debe ser texto UTC")
    m = _PLAZO.fullmatch(texto)
    if m is None:
        raise ValueError(f"plazo sin UTC explicito o con formato no canonico: {texto!r}")
    if int(m.group(6)) > 59:
        raise ValueError("el plazo no admite segundo 60")
    return _segundos(*m.groups())


def instante_de_gen_time(texto: str) -> Fraction:
    """Segundos exactos de un GeneralizedTime DER de RFC 3161 2.4.2
    ('AAAAMMDDhhmmss[.f]Z', sin ceros finales). Fracciones de cualquier
    longitud, sin truncar."""
    m = _GEN_TIME.fullmatch(texto)
    if m is None:
        raise ValueError(f"genTime fuera de la sintaxis de RFC 3161 2.4.2: {texto!r}")
    if int(m.group(6)) == 60:
        raise SegundoIntercalar(texto)
    return _segundos(*m.groups())


def segundos_decimales(texto: str) -> Fraction:
    """Duracion exacta en segundos a partir de un decimal sin signo."""
    m = _DECIMAL.fullmatch(texto) if isinstance(texto, str) else None
    if m is None:
        raise ValueError(f"duracion decimal no canonica: {texto!r}")
    entero, fraccion = m.groups()
    return Fraction(int(entero)) + (Fraction(int(fraccion), 10 ** len(fraccion)) if fraccion else 0)


def texto_utc(instante: Fraction) -> str:
    """Escritura canonica 'AAAA-MM-DDTHH:MM:SS[.f]Z' de un instante exacto
    con fraccion decimal finita."""
    enteros = instante.numerator // instante.denominator
    resto = instante - enteros
    base = (_EPOCA + timedelta(seconds=enteros)).strftime("%Y-%m-%dT%H:%M:%S")
    return base + _fraccion(resto) + "Z"


def texto_segundos(duracion: Fraction) -> str:
    enteros = duracion.numerator // duracion.denominator
    return f"{enteros}{_fraccion(duracion - enteros)}"


def _fraccion(resto: Fraction) -> str:
    digitos = ""
    while resto and len(digitos) < 60:
        resto *= 10
        d = resto.numerator // resto.denominator
        digitos += str(d)
        resto -= d
    if resto:
        raise ValueError("fraccion decimal no finita")
    return f".{digitos}" if digitos else ""


# ---------------------------------------------------------------------------
# Comparacion con el plazo (D8, modelo sintetico)
# ---------------------------------------------------------------------------

RESULTADOS_TEMPORALES = ("anterior_al_plazo", "no_concluyente_intervalo_cruza_el_plazo", "posterior_al_plazo",
                         "precision_ausente_pendiente", "no_evaluable")


def comparar_con_plazo(gen_time: Fraction, precision: Fraction | None, margen: Fraction, plazo: Fraction) -> str:
    """Regla de D8: anterior solo si gen_time + precision + margen < plazo
    (estricto); posterior si gen_time - precision - margen >= plazo; si no,
    el intervalo cruza el plazo. Sin precision, pendiente: nunca cero."""
    if margen < 0 or (precision is not None and precision < 0):
        raise ValueError("precision y margen no pueden ser negativos")
    if precision is None:
        return "precision_ausente_pendiente"
    if gen_time + precision + margen < plazo:
        return "anterior_al_plazo"
    if gen_time - precision - margen >= plazo:
        return "posterior_al_plazo"
    return "no_concluyente_intervalo_cruza_el_plazo"


# ---------------------------------------------------------------------------
# Politica de confianza temporal (solo fixtures)
# ---------------------------------------------------------------------------

NATURALEZAS_DE_ANCLA = ("fixture_de_prueba",)
ANCLAS_OPERATIVAS_APROBADAS = ()
"""Ninguna: AE-75 no tiene ancla, politica ni TSA operativas."""
_OID = re.compile(r"[0-2](\.(0|[1-9]\d*))+")


@dataclass(frozen=True)
class AnclaDePrueba:
    """Certificado DER de una CA de fixture. No existe otra naturaleza: un
    ancla operativa exige otra decision y otra etapa."""
    certificado_der: bytes
    etiqueta: str
    naturaleza: str = "fixture_de_prueba"

    def __post_init__(self):
        if self.naturaleza not in NATURALEZAS_DE_ANCLA:
            raise ValueError(f"naturaleza de ancla no admitida en AE-75: {self.naturaleza!r}")
        if not isinstance(self.certificado_der, bytes) or not self.certificado_der:
            raise ValueError("el ancla exige el certificado DER")


@dataclass(frozen=True)
class PoliticaDeConfianzaTemporal:
    """Anclas de prueba, lista explicita de TSAPolicyId admitidos y margen
    adicional en segundos decimales (sin valor por defecto)."""
    anclas: tuple
    politicas_admitidas: tuple
    margen: str

    def __post_init__(self):
        if not all(isinstance(a, AnclaDePrueba) for a in self.anclas):
            raise ValueError("solo se admiten anclas de prueba")
        if not self.politicas_admitidas or not all(isinstance(p, str) and _OID.fullmatch(p)
                                                   for p in self.politicas_admitidas):
            raise ValueError("la lista de politicas admitidas debe ser explicita y de OID")
        segundos_decimales(self.margen)


@dataclass(frozen=True)
class EvidenciaDeSello:
    """TimeStampResp DER y bytes exactos del compromiso sellado."""
    respuesta_der: bytes
    bytes_compromiso: bytes


# ---------------------------------------------------------------------------
# Construccion y lectura del compromiso
# ---------------------------------------------------------------------------

def _estado_del_contrato(entradas: Sequence[bytes], bytes_declaracion: bytes | None):
    admision = _contrato.evaluar_admision(entradas, bytes_declaracion)
    if admision.ruta != "contrato_1_2":
        raise CompromisoInvalido("ruta_no_admitida", admision.ruta)
    if admision.puertas["vinculo_integro"].estado != "superada":
        raise CompromisoInvalido("vinculo_no_integro", ",".join(admision.puertas["vinculo_integro"].motivos))
    return admision, _rp.validar_registro(list(entradas))


def _motivo_de_objetivo(estado, codigo_juego, sorteo_objetivo) -> str | None:
    juegos = estado.protocolo["juegos"]
    if codigo_juego not in juegos:
        return "juego_fuera_del_protocolo"
    corte = juegos[codigo_juego]["ultimo_sorteo_conocido"]
    if type(sorteo_objetivo) is not int or corte is None or sorteo_objetivo <= corte:
        return "objetivo_no_posterior_al_corte"
    return None


def construir_compromiso(entradas: Sequence[bytes], bytes_declaracion: bytes, *, codigo_juego: str,
                         sorteo_objetivo: int, plazo_utc: str,
                         procedencia_del_plazo: str = "sintetica_de_prueba") -> dict:
    """Compromiso de un objetivo sobre un registro 1.2 del contrato con
    vinculo integro. El juego debe estar en el protocolo y el objetivo ser
    posterior a su corte."""
    admision, estado = _estado_del_contrato(entradas, bytes_declaracion)
    motivo = _motivo_de_objetivo(estado, codigo_juego, sorteo_objetivo)
    if motivo:
        raise CompromisoInvalido(motivo, f"{codigo_juego} {sorteo_objetivo}")
    try:
        instante_de_plazo(plazo_utc)
    except ValueError as error:
        raise CompromisoInvalido("plazo_sin_utc_explicito", str(error)) from error
    if procedencia_del_plazo not in PROCEDENCIAS_DEL_PLAZO:
        raise CompromisoInvalido("procedencia_del_plazo_no_admitida", procedencia_del_plazo)
    vinculo = estado.protocolo[_rp.CAMPO_VINCULO_R0]
    return {"esquema": ESQUEMA_COMPROMISO, "contrato": vinculo["contrato"],
            "esquema_del_protocolo": estado.protocolo["esquema"], "regla": vinculo["regla"],
            "protocolo_hash": admision.protocolo_hash, "hash_declaracion": admision.hash_declaracion,
            "codigo_juego": codigo_juego, "sorteo_objetivo": sorteo_objetivo, "plazo_utc": plazo_utc,
            "procedencia_del_plazo": procedencia_del_plazo}


def bytes_de_compromiso(compromiso: dict) -> bytes:
    """JSON canonico de AE-52 (claves ordenadas, UTF-8, LF final)."""
    return _rp.serializar_entrada(compromiso)


def leer_compromiso(datos: bytes) -> dict:
    """Lee bytes de compromiso: JSON canonico exacto, version conocida y
    claves exactas. Otra version no se reinterpreta."""
    try:
        compromiso = json.loads(datos.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise CompromisoInvalido("compromiso_ilegible", str(error)) from error
    if not isinstance(compromiso, dict):
        raise CompromisoInvalido("compromiso_ilegible", "no es un objeto")
    if compromiso.get("esquema") != ESQUEMA_COMPROMISO:
        raise CompromisoInvalido("version_de_compromiso_desconocida", str(compromiso.get("esquema")))
    if set(compromiso) != set(CLAVES_DEL_COMPROMISO):
        raise CompromisoInvalido("compromiso_ilegible", "claves distintas de las de la version 1")
    try:
        canonicos = bytes_de_compromiso(compromiso)
    except _rp.EntradaRegistroInvalidaError as error:
        # NaN, Infinity y 1e999 (correccion incluida en AE-80).
        raise CompromisoInvalido("compromiso_ilegible", "constante JSON no estandar") from error
    if canonicos != datos:
        raise CompromisoInvalido("compromiso_no_canonico")
    return compromiso


# ---------------------------------------------------------------------------
# Comprobaciones, herramientas y estados
# ---------------------------------------------------------------------------

ESTADOS_DE_COMPROBACION = ("superada", "rechazada", "pendiente", "no_evaluable")
COMPROBACIONES_DEL_VINCULO = ("compromiso_legible", "compromiso_corresponde_al_registro", "objetivo_corresponde",
                              "plazo_utc_explicito", "impronta_coincide")
COMPROBACIONES_CRIPTOGRAFICAS = (
    "respuesta_decodificada", "estado_concedido", "estructura_del_token", "atributos_firmados", "firma_del_token",
    "identificador_del_certificado", "proposito_de_sellado", "algoritmos_y_claves_del_perfil",
    "extensiones_criticas", "politica_admitida", "nombre_de_la_tsa", "vigencia_en_gen_time",
    "cadena_hasta_el_ancla", "verificacion_integral", "gen_time_coherente", "revocacion",
)
_RFC3161 = "rfc3161-client 1.0.9 (Trail of Bits; OpenSSL incorporado)"
_CRYPTO = "cryptography 50.0.1 (PyCA)"
_ASN1 = ("cryptography.hazmat.asn1 50.0.1 (decodificador DER declarativo de PyCA) con esquemas transcritos de "
         "RFC 3161, RFC 5652 y RFC 5035")
_PROPIO = "este modulo: comparacion de valores ya decodificados por las bibliotecas"

HERRAMIENTAS = MappingProxyType({
    "compromiso_legible": (_PROPIO, "JSON canonico de AE-52, version y claves exactas"),
    "compromiso_corresponde_al_registro": (
        _PROPIO, "protocolo_hash, hash de la declaracion, contrato, regla y version frente al registro 1.2 y a "
                 "evaluar_admision de AE-74"),
    "objetivo_corresponde": (_PROPIO, "juego y objetivo pedidos iguales a los sellados; juego en el protocolo y "
                                      "objetivo posterior a su corte"),
    "plazo_utc_explicito": (_PROPIO, "plazo canonico con Z y procedencia sintetica"),
    "impronta_coincide": (_ASN1 + "; hashlib", "algoritmo admitido (SHA-256, SHA-384, SHA-512) e impronta igual al "
                                               "hash de los bytes del compromiso"),
    "respuesta_decodificada": (_RFC3161 + "; " + _ASN1, "TimeStampResp DER decodificable por ambas"),
    "estado_concedido": (_RFC3161, "PKIStatus granted (0); grantedWithMods no se admite"),
    "estructura_del_token": (_ASN1, "ContentInfo signedData, eContentType id-ct-TSTInfo, un solo SignerInfo con "
                                    "issuerAndSerialNumber y atributos firmados, TSTInfo version 1"),
    "atributos_firmados": (_ASN1 + "; hashlib", "content-type id-ct-TSTInfo y message-digest igual al hash del "
                                                "eContent"),
    "firma_del_token": (_CRYPTO, "firma del SignerInfo sobre el DER de los atributos firmados con la clave publica del "
                                 "certificado identificado por el SignerInfo"),
    "identificador_del_certificado": (_ASN1 + "; hashlib",
                                      "SigningCertificateV2 (RFC 5816 2.2.1) con SHA-256 o superior cuyo certHash "
                                      "coincide con el certificado firmante"),
    "proposito_de_sellado": (_CRYPTO, "extendedKeyUsage critica con un unico proposito id-kp-timeStamping (RFC 3161 "
                                      "2.3); keyUsage con digitalSignature o nonRepudiation"),
    "algoritmos_y_claves_del_perfil": (_CRYPTO, "RSA de al menos 2048 bits o EC P-256/P-384/P-521; firmas de "
                                                "certificados con SHA-256 o superior"),
    "extensiones_criticas": (_CRYPTO + "; " + _ASN1, "ninguna extension critica desconocida en certificados ni en "
                                                     "TSTInfo"),
    "politica_admitida": (_RFC3161, "TSAPolicyId en la lista explicita de la politica de confianza"),
    "nombre_de_la_tsa": (_RFC3161 + "; " + _CRYPTO, "si hay campo tsa, nombre de directorio igual al sujeto del "
                                                    "firmante (RFC 3161 2.4.2)"),
    "vigencia_en_gen_time": (_CRYPTO, "periodo de validez de los certificados incluidos y del ancla en el genTime "
                                     "decodificado; nunca el reloj local"),
    "cadena_hasta_el_ancla": (_CRYPTO, "diagnostico: por nombre de emisor, cada firma comprobada con "
                                       "verify_directly_issued_by hasta un ancla configurada"),
    "verificacion_integral": (_RFC3161, "VerifierBuilder con solo las anclas configuradas: firma PKCS#7 y cadena "
                                        "construida por OpenSSL en genTime, proposito de sellado, unico firmante e "
                                        "impronta"),
    "gen_time_coherente": (_ASN1 + "; " + _RFC3161,
                           "genTime exacto leido del DER; rfc3161-client 1.0.9 lo entrega sin fraccion de segundo y "
                           "debe coincidir con su truncado"),
    "revocacion": ("ninguna", "sin CRL ni OCSP: RFC 3161 2.2 recomienda comprobarla; queda pendiente"),
})
"""Que comprueba realmente cada herramienta. La construccion y validacion
autoritativa de la ruta de certificacion la hace OpenSSL dentro de
rfc3161-client; `cadena_hasta_el_ancla` solo aporta la causa especifica y
debe coincidir con ella."""

ESTADOS_DEL_PLANO = ("sin_evidencia", "rechazada", "no_concluyente", "pendiente", "no_evaluable")
"""Estados del plano `sello_temporal_de_r0`. `superada` no existe en
AE-75: exigiria ancla y politica operativas aprobadas, revocacion
comprobada y un plazo de calendario oficial."""

LIMITES_OPERATIVOS = ("ancla_de_prueba_no_operativa", "revocacion_sin_comprobar",
                      "plazo_sintetico_sin_calendario_oficial")
NO_PRUEBA = ("autenticacion_de_r0", "recepcion_de_predicciones", "completitud_y_unicidad_del_canal",
             "calendario_oficial", "aptitud_inferencial")
"""Lo que el sello del compromiso no prueba, con cualquier resultado."""

MOTIVOS = (
    # vinculo del compromiso
    "compromiso_ilegible", "version_de_compromiso_desconocida", "compromiso_no_canonico",
    "compromiso_no_corresponde_al_registro", "ruta_no_admitida", "vinculo_no_integro", "registro_invalido",
    "protocolo_hash_no_coincide", "hash_de_declaracion_no_coincide", "contrato_o_regla_no_coincide",
    "objetivo_no_coincide", "juego_fuera_del_protocolo", "objetivo_no_posterior_al_corte", "plazo_sin_utc_explicito",
    "procedencia_del_plazo_no_admitida", "algoritmo_de_impronta_no_admitido", "impronta_no_coincide",
    "estructura_del_token_no_disponible",
    # criptografia
    "respuesta_ilegible", "estado_pki_no_concedido", "estructura_fuera_del_perfil", "precision_mal_formada",
    "atributo_content_type_incorrecto", "message_digest_no_coincide", "certificado_del_firmante_ausente",
    "firma_del_token_no_coincide", "identificador_de_certificado_ausente", "identificador_de_certificado_solo_sha1",
    "identificador_de_certificado_no_coincide", "uso_extendido_ausente", "uso_extendido_no_critico",
    "uso_extendido_no_exclusivo", "uso_de_clave_sin_firma", "algoritmo_no_soportado", "algoritmo_debil",
    "clave_fuera_del_perfil", "extension_critica_desconocida", "politica_no_admitida", "nombre_de_la_tsa_no_coincide",
    "nombre_de_la_tsa_no_comparable", "gen_time_no_canonico", "segundo_intercalar_sin_regla",
    "gen_time_incoherente_entre_herramientas", "gen_time_no_disponible", "certificado_no_vigente_en_gen_time",
    "cadena_sin_ancla", "firma_de_certificado_no_coincide", "sin_ancla_configurada",
    "verificacion_integral_no_superada", "dependencia_criptografica_ausente",
    "no_evaluable_por_dependencia",
    # conclusion temporal y plano
    "precision_ausente", "intervalo_cruza_el_plazo", "sello_posterior_al_plazo", *LIMITES_OPERATIVOS,
    "objetivo_sin_sello",
)


@dataclass(frozen=True)
class ResultadoDeComprobacion:
    estado: str
    motivos: tuple = ()
    detalle: str = ""


@dataclass(frozen=True)
class ConclusionTemporal:
    resultado: str
    plazo_utc: str | None = None
    procedencia_del_plazo: str | None = None
    gen_time_utc: str | None = None
    precision_segundos: str | None = None
    margen_segundos: str | None = None
    limite_inferior_utc: str | None = None
    limite_superior_utc: str | None = None
    condicionada_a: tuple = ()


@dataclass(frozen=True)
class InformeDeSello:
    objetivo: tuple
    vinculo_del_compromiso: dict
    comprobaciones_criptograficas: dict
    conclusion_temporal: ConclusionTemporal
    estado_del_plano: str
    motivos_del_plano: tuple
    limites_operativos: tuple = LIMITES_OPERATIVOS
    no_prueba: tuple = NO_PRUEBA


# ---------------------------------------------------------------------------
# Fuentes primarias: lo que dice el estandar y lo que elige esta aplicacion
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Cita:
    id: str
    fuente: str
    seccion: str
    lineas: tuple
    cita: str
    alcance: str


FUENTES_PRIMARIAS = (
    Cita("E1", "rfc_3161", "2", (94, 95), "The TSA is a TTP that creates time-stamp tokens in order to indicate that a "
                                          "datum existed at a particular point in time.",
         "el token es una afirmacion de la autoridad sobre la existencia de un dato (su impronta) en un instante"),
    Cita("E2", "rfc_3161", "1", (84, 90), "This standard does not establish overall security requirements for TSA "
                                          "operation",
         "la confianza en el reloj y la operacion depende de la politica de la autoridad que el cliente acepta"),
    Cita("E3", "rfc_3161", "2.1", (137, 138), "not to include any identification of the requesting entity in the "
                                              "time-stamp tokens.",
         "el token no identifica a quien lo pidio"),
    Cita("E4", "rfc_3161", "2.2", (158, 183), "it SHALL verify that what was time-stamped corresponds to what was "
                                              "requested to be time-stamped.",
         "comprobar estado, campos, firma, impronta e identificador del certificado"),
    Cita("E5", "rfc_3161", "2.2", (185, 187), "the status of the certificate SHOULD be checked (e.g., by checking the "
                                              "appropriate CRL)",
         "la revocacion se recomienda, no se exige"),
    Cita("E6", "rfc_3161", "2.2", (189, 191), "the client application SHOULD check the policy field to determine "
                                              "whether or not the policy under which the token was issued is "
                                              "acceptable for the application.",
         "la aceptabilidad de la politica la decide la aplicacion"),
    Cita("E7", "rfc_3161", "2.3", (195, 211), "The corresponding certificate MUST contain only one instance of the "
                                              "extended key usage field extension ... id-kp-timeStamping. This "
                                              "extension MUST be critical.",
         "proposito de sellado exclusivo y critico"),
    Cita("E8", "rfc_3161", "2.4.2", (411, 414), "The time-stamp token MUST NOT contain any signatures other than the "
                                                "signature of the TSA.",
         "un solo firmante"),
    Cita("E9", "rfc_3161", "2.4.2", (478, 484), "genTime is the time at which the time-stamp token has been created by "
                                                "the TSA. It is expressed as UTC time",
         "genTime es la creacion del token en UTC, no la solicitud"),
    Cita("E10", "rfc_3161", "2.4.2", (491, 519), "The encoding MUST terminate with a \"Z\" ... fractional-seconds "
                                                 "elements, if present, MUST omit all trailing 0's",
         "sintaxis DER de genTime"),
    Cita("E11", "rfc_3161", "2.4.2", (538, 542), "By adding the accuracy value to the GeneralizedTime, an upper limit "
                                                 "of the time at which the time-stamp token has been created by the "
                                                 "TSA can be obtained.",
         "accuracy acota el instante de creacion"),
    Cita("E12", "rfc_3161", "2.4.2", (547, 548), "When the accuracy optional field is not present, then the accuracy "
                                                 "may be available through other means, e.g., the TSAPolicyId.",
         "sin accuracy, la precision no es cero: puede venir de la politica"),
    Cita("E13", "rfc_3161", "2.4.2", (575, 582), "The purpose of the tsa field is to give a hint in identifying the "
                                                 "name of the TSA.",
         "el campo tsa es una pista; la identificacion es el identificador del certificado"),
    Cita("E14", "rfc_5816", "2.2.1", (157, 177), "The certificate identifier (either ESSCertID [ESS] or ESSCertIDv2 "
                                                 "[ESSV2]) of the TSA certificate MUST be included as a signerInfo "
                                                 "attribute inside a SigningCertificate attribute.",
         "ESSCertID o ESSCertIDv2; SigningCertificateV2 obligatorio con algoritmos distintos de SHA-1"),
    Cita("E15", "rfc_5816", "2.2.2", (198, 208), "the actual identification of the entity that signed the response "
                                                 "will always occur through the use of the certificate identifier",
         "la identidad del firmante sale del identificador del certificado"),
    Cita("E16", "rfc_3161", "4", (791, 803), "Two time-stamp tokens from two different TSAs is another way to address "
                                             "this issue.",
         "compromiso de la clave de la autoridad; dos autoridades independientes"),
    Cita("E17", "rfc_3161", "4", (805, 812), "any token signed by the TSA SHOULD be time-stamped again (if authentic "
                                             "copies of old CRLs are available) or notarized",
         "conservacion a largo plazo"),
)
"""Citas de los TXT oficiales aportados por el operador (RFC 3161 y RFC
5816), por seccion y lineas del archivo, como en AE-67. Dicen lo que exige
o recomienda el estandar; lo que elige esta aplicacion esta en
`POLITICA_ELEGIDA`."""

POLITICA_ELEGIDA = MappingProxyType({id_: MappingProxyType({"texto": texto, "base": base})
                                     for id_, texto, base in (
    ("P1", "un compromiso por objetivo con juego, objetivo y plazo en los bytes sellados", "ajuste 1 del operador"),
    ("P2", "solo plazo sintetico explicito; la fuente operativa sera un calendario oficial identificado, versionado y "
           "publicado antes del cierre, sin la hora real del sorteo; su seleccion y verificacion siguen pendientes",
     "ajuste 2 del operador"),
    ("P3", "anterior solo si genTime + accuracy + margen < plazo; la igualdad no pasa; cruzar el plazo no es "
           "concluyente; aritmetica racional exacta y UTC explicito", "ajuste 3 del operador; E9, E11"),
    ("P4", "sin accuracy queda pendiente: AE-75 no tiene una politica de TSA publicada de la que tomar una precision "
           "comprobable", "E12; ajuste 3 del operador"),
    ("P5", "politica obligatoria: solo TSAPolicyId de la lista explicita", "E6 (SHOULD); ajuste 5 del operador"),
    ("P6", "solo SigningCertificateV2 con SHA-256 o superior", "E14 admite tambien ESSCertID con SHA-1"),
    ("P7", "revocacion sin datos: pendiente", "E5 (SHOULD); ajuste 5 del operador"),
    ("P8", "validez de certificados en el genTime decodificado, nunca con el reloj local", "E9"),
    ("P9", "solo codificacion DER: rfc3161-client rechaza conjuntos no ordenados, que CMS admite en BER",
     "limite de la herramienta aceptado como politica"),
    ("P10", "solo PKIStatus granted (0)", "E4"),
    ("P11", "RSA de al menos 2048 bits o EC P-256/P-384/P-521, y SHA-256 o superior", "politica de la aplicacion"),
    ("P12", "anclas solo de fixture; ninguna ruta llega a superada", "ajuste 5 del operador"),
    ("P13", "genTime exacto desde el DER: rfc3161-client 1.0.9 descarta la fraccion de segundo", "E10"),
)})

REQUISITOS_PARA_USO_OPERATIVO = (
    "una o dos autoridades de sellado independientes aprobadas por el operador y declaradas en R0 (E16)",
    "su CA raiz obtenida por un canal con autenticacion, con huella SHA-256 registrada, como ancla explicita",
    "los TSAPolicyId admitidos con su politica publicada y la precision que declara (E2, E12)",
    "CRL u OCSP de toda la cadena obtenidos despues de genTime y archivados con el token, y plan de renovacion "
    "(E5, E17)",
    "un calendario oficial identificado, versionado y publicado antes del cierre, con su verificacion "
    "(calendario_oficial)",
    "los otros dos elementos de AUTENTICACION_DE_R0: publicacion fuera de banda y reconocimiento del operador",
    "un protocolo real no sintetico, que exige otra decision y otra etapa",
    "prueba de recepcion de cada prediccion y completitud y unicidad del canal, que un sello de R0 no aporta",
)


# ---------------------------------------------------------------------------
# Bibliotecas y esquemas ASN.1 de lectura (carga diferida)
# ---------------------------------------------------------------------------

OID_SIGNED_DATA = "1.2.840.113549.1.7.2"
OID_TSTINFO = "1.2.840.113549.1.9.16.1.4"
OID_CONTENT_TYPE = "1.2.840.113549.1.9.3"
OID_MESSAGE_DIGEST = "1.2.840.113549.1.9.4"
OID_SIGNING_CERTIFICATE = "1.2.840.113549.1.9.16.2.12"
OID_SIGNING_CERTIFICATE_V2 = "1.2.840.113549.1.9.16.2.47"
ALGORITMOS_DE_HASH = MappingProxyType({"2.16.840.1.101.3.4.2.1": "sha256", "2.16.840.1.101.3.4.2.2": "sha384",
                                       "2.16.840.1.101.3.4.2.3": "sha512"})
_FIRMAS_RSA = MappingProxyType({"1.2.840.113549.1.1.1": None, "1.2.840.113549.1.1.11": "sha256",
                                "1.2.840.113549.1.1.12": "sha384", "1.2.840.113549.1.1.13": "sha512"})
_FIRMAS_EC = MappingProxyType({"1.2.840.10045.4.3.2": "sha256", "1.2.840.10045.4.3.3": "sha384",
                               "1.2.840.10045.4.3.4": "sha512"})


@functools.lru_cache(maxsize=1)
def _bibliotecas():
    """Carga diferida: si falta una dependencia, las comprobaciones quedan
    pendientes con causa especifica en lugar de fallar al importar."""
    from typing import Annotated, Literal

    import rfc3161_client
    from cryptography import exceptions, x509
    from cryptography.hazmat import asn1
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

    O = x509.ObjectIdentifier

    @asn1.sequence
    class Alg:
        algorithm: O
        parameters: asn1.Null | None

    @asn1.sequence
    class Impronta:
        hash_algorithm: Alg
        hashed_message: bytes

    @asn1.sequence
    class Precision:
        seconds: int | None
        millis: Annotated[int | None, asn1.Implicit(0)]
        micros: Annotated[int | None, asn1.Implicit(1)]

    NombreGeneral = (Annotated[asn1.Variant[x509.Name, Literal["directorio"]], asn1.Explicit(4)]
                     | Annotated[asn1.Variant[asn1.IA5String, Literal["correo"]], asn1.Implicit(1)]
                     | Annotated[asn1.Variant[asn1.IA5String, Literal["dns"]], asn1.Implicit(2)]
                     | Annotated[asn1.Variant[asn1.IA5String, Literal["uri"]], asn1.Implicit(6)])

    @asn1.sequence
    class Extension:
        extn_id: O
        critical: Annotated[bool, asn1.Default(False)]
        extn_value: bytes

    @asn1.sequence
    class TSTInfo:
        version: int
        policy: O
        message_imprint: Impronta
        serial_number: int
        gen_time: asn1.TLV
        accuracy: Precision | None
        ordering: Annotated[bool, asn1.Default(False)]
        nonce: int | None
        tsa: Annotated[NombreGeneral | None, asn1.Explicit(0)]
        extensions: Annotated[list[Extension] | None, asn1.Implicit(1)]

    @asn1.sequence
    class Atributo:
        attr_type: O
        attr_values: asn1.SetOf[asn1.TLV]

    @asn1.sequence
    class EmisorYSerie:
        issuer: x509.Name
        serial: int

    @asn1.sequence
    class SignerInfo:
        version: int
        sid: EmisorYSerie
        digest_algorithm: Alg
        signed_attrs: Annotated[asn1.SetOf[Atributo] | None, asn1.Implicit(0)]
        signature_algorithm: Alg
        signature: bytes
        unsigned_attrs: Annotated[asn1.SetOf[Atributo] | None, asn1.Implicit(1)]

    @asn1.sequence
    class Encap:
        e_content_type: O
        e_content: Annotated[bytes | None, asn1.Explicit(0)]

    @asn1.sequence
    class SignedData:
        version: int
        digest_algorithms: asn1.SetOf[Alg]
        encap: Encap
        certificates: Annotated[asn1.SetOf[asn1.TLV] | None, asn1.Implicit(0)]
        crls: Annotated[asn1.SetOf[asn1.TLV] | None, asn1.Implicit(1)]
        signer_infos: asn1.SetOf[SignerInfo]

    @asn1.sequence
    class ContentInfo:
        content_type: O
        content: Annotated[SignedData, asn1.Explicit(0)]

    @asn1.sequence
    class EstadoPKI:
        status: int
        status_string: list[str] | None
        fail_info: asn1.BitString | None

    @asn1.sequence
    class Respuesta:
        status: EstadoPKI
        token: ContentInfo | None

    @asn1.sequence
    class IssuerSerial:
        issuer: list[NombreGeneral]
        serial: int

    @asn1.sequence
    class ESSCertIDv2:
        hash_algorithm: Alg | None
        cert_hash: bytes
        issuer_serial: IssuerSerial | None

    @asn1.sequence
    class SigningCertificateV2:
        certs: list[ESSCertIDv2]
        policies: list[asn1.TLV] | None

    return SimpleNamespace(
        rfc3161_client=rfc3161_client, x509=x509, asn1=asn1, hashes=hashes, serialization=serialization, ec=ec,
        padding=padding, rsa=rsa, InvalidSignature=exceptions.InvalidSignature,
        UnsupportedAlgorithm=exceptions.UnsupportedAlgorithm, Respuesta=Respuesta, TSTInfo=TSTInfo,
        SigningCertificateV2=SigningCertificateV2)


# ---------------------------------------------------------------------------
# Verificacion de un sello
# ---------------------------------------------------------------------------

_OK = ResultadoDeComprobacion("superada")


def _r(estado: str, *motivos: str, detalle: str = "") -> ResultadoDeComprobacion:
    return ResultadoDeComprobacion(estado, tuple(motivos), detalle[:300])


def _comprobar_vinculo(compromiso, entradas, bytes_declaracion, objetivo) -> tuple[dict, object]:
    resultado = {}
    try:
        admision, estado = _estado_del_contrato(entradas, bytes_declaracion)
    except (CompromisoInvalido, _rp.RegistroProspectivoError) as error:
        motivo = getattr(error, "motivo", "registro_invalido")
        resultado["compromiso_corresponde_al_registro"] = _r("rechazada", "compromiso_no_corresponde_al_registro",
                                                            motivo)
        resultado["objetivo_corresponde"] = _r("no_evaluable", "compromiso_no_corresponde_al_registro")
        estado = None
    else:
        vinculo = estado.protocolo[_rp.CAMPO_VINCULO_R0]
        motivos = []
        if compromiso["protocolo_hash"] != admision.protocolo_hash:
            motivos.append("protocolo_hash_no_coincide")
        if compromiso["hash_declaracion"] != admision.hash_declaracion:
            motivos.append("hash_de_declaracion_no_coincide")
        if (compromiso["contrato"], compromiso["regla"], compromiso["esquema_del_protocolo"]) != (
                vinculo["contrato"], vinculo["regla"], estado.protocolo["esquema"]):
            motivos.append("contrato_o_regla_no_coincide")
        resultado["compromiso_corresponde_al_registro"] = (
            _r("rechazada", "compromiso_no_corresponde_al_registro", *motivos) if motivos else _OK)
        motivos = []
        if (compromiso["codigo_juego"], compromiso["sorteo_objetivo"]) != objetivo:
            motivos.append("objetivo_no_coincide")
        motivo = _motivo_de_objetivo(estado, *objetivo)
        if motivo:
            motivos.append(motivo)
        resultado["objetivo_corresponde"] = _r("rechazada", *motivos) if motivos else _OK
    try:
        instante_de_plazo(compromiso["plazo_utc"])
        plazo = _OK
    except ValueError as error:
        plazo = _r("rechazada", "plazo_sin_utc_explicito", detalle=str(error))
    if plazo.estado == "superada" and compromiso["procedencia_del_plazo"] not in PROCEDENCIAS_DEL_PLAZO:
        plazo = _r("rechazada", "procedencia_del_plazo_no_admitida")
    resultado["plazo_utc_explicito"] = plazo
    return resultado, estado


def _hash(nombre: str, datos: bytes) -> bytes:
    return hashlib.new(nombre, datos).digest()


def _segundos_de(instante: datetime) -> Fraction:
    delta = instante - _EPOCA
    return Fraction(delta // timedelta(seconds=1)) + Fraction(delta.microseconds, 10 ** 6)


def _criptografia(b, evidencia: EvidenciaDeSello, politica: PoliticaDeConfianzaTemporal) -> tuple[dict, object]:
    """Comprobaciones criptograficas con las bibliotecas. Devuelve los
    resultados y los valores decodificados que necesita el resto."""
    r = {}
    extraido = {"tst": None, "gen_time": None, "precision": None}

    def resto(motivo):
        for clave in COMPROBACIONES_CRIPTOGRAFICAS:
            r.setdefault(clave, _r("no_evaluable", motivo))
        return {clave: r[clave] for clave in COMPROBACIONES_CRIPTOGRAFICAS}, SimpleNamespace(**extraido)

    datos = evidencia.respuesta_der
    try:
        respuesta_rc = b.rfc3161_client.decode_timestamp_response(datos)
    except Exception as error:  # noqa: BLE001 - la biblioteca lanza ValueError con la causa DER
        r["respuesta_decodificada"] = _r("rechazada", "respuesta_ilegible", detalle=str(error))
        return resto("respuesta_ilegible")
    try:
        cruda = b.asn1.decode_der(b.Respuesta, datos)
    except Exception as error:  # noqa: BLE001
        r["respuesta_decodificada"] = _r("pendiente", "estructura_fuera_del_perfil", detalle=str(error))
        return resto("estructura_fuera_del_perfil")
    r["respuesta_decodificada"] = _OK
    if respuesta_rc.status != 0 or cruda.token is None:
        r["estado_concedido"] = _r("rechazada", "estado_pki_no_concedido", detalle=str(respuesta_rc.status))
        return resto("estado_pki_no_concedido")
    r["estado_concedido"] = _OK

    token = cruda.token
    sd = token.content
    firmantes = sd.signer_infos.as_list()
    problemas = []
    if token.content_type.dotted_string != OID_SIGNED_DATA:
        problemas.append("contentType distinto de id-signedData")
    if sd.encap.e_content_type.dotted_string != OID_TSTINFO or sd.encap.e_content is None:
        problemas.append("eContentType distinto de id-ct-TSTInfo o sin eContent")
    if len(firmantes) != 1:
        problemas.append("el token debe tener un solo SignerInfo (RFC 3161 2.4.2)")
    elif firmantes[0].signed_attrs is None:
        problemas.append("SignerInfo sin atributos firmados")
    tst = None
    if not problemas:
        try:
            tst = b.asn1.decode_der(b.TSTInfo, sd.encap.e_content)
        except Exception as error:  # noqa: BLE001
            problemas.append(f"TSTInfo no decodificable con el perfil: {error}")
        else:
            if tst.version != 1:
                problemas.append("TSTInfo version distinta de 1")
            precision = tst.accuracy
            if precision is not None and (
                    (precision.seconds is not None and precision.seconds < 0)
                    or any(v is not None and not 1 <= v <= 999 for v in (precision.millis, precision.micros))):
                r["estructura_del_token"] = _r("rechazada", "precision_mal_formada")
                return resto("precision_mal_formada")
    if problemas:
        r["estructura_del_token"] = _r("rechazada", "estructura_fuera_del_perfil", detalle="; ".join(problemas))
        return resto("estructura_fuera_del_perfil")
    r["estructura_del_token"] = _OK
    extraido["tst"] = tst
    si = firmantes[0]

    try:
        certificados = [b.x509.load_der_x509_certificate(c) for c in sorted(respuesta_rc.signed_data.certificates)]
    except ValueError as error:
        r["estructura_del_token"] = _r("rechazada", "estructura_fuera_del_perfil", detalle=str(error))
        return resto("estructura_fuera_del_perfil")
    hoja = next((c for c in certificados if c.issuer == si.sid.issuer and c.serial_number == si.sid.serial), None)

    # atributos firmados (RFC 5652 5.3 y 11)
    atributos = {}
    for atributo in si.signed_attrs.as_list():
        atributos.setdefault(atributo.attr_type.dotted_string, []).append(atributo.attr_values.as_list())
    digest = ALGORITMOS_DE_HASH.get(si.digest_algorithm.algorithm.dotted_string)
    r["atributos_firmados"] = _atributos(b, atributos, digest, sd.encap.e_content)

    if hoja is None:
        r["firma_del_token"] = _r("rechazada", "certificado_del_firmante_ausente")
        for clave in ("identificador_del_certificado", "proposito_de_sellado", "nombre_de_la_tsa",
                      "cadena_hasta_el_ancla"):
            r[clave] = _r("no_evaluable", "certificado_del_firmante_ausente")
    else:
        r["firma_del_token"] = _firma(b, si, hoja, digest)
        r["identificador_del_certificado"] = _identificador(b, atributos, hoja)
        r["proposito_de_sellado"] = _proposito(b, hoja)

    r["algoritmos_y_claves_del_perfil"] = _algoritmos(b, certificados)
    criticas = [c for c in certificados
                if any(e.critical and isinstance(e.value, b.x509.UnrecognizedExtension) for e in c.extensions)]
    if criticas or any(e.critical for e in (tst.extensions or ())):
        r["extensiones_criticas"] = _r("rechazada", "extension_critica_desconocida")
    else:
        r["extensiones_criticas"] = _OK
    politica_token = respuesta_rc.tst_info.policy.dotted_string
    r["politica_admitida"] = (_OK if politica_token in politica.politicas_admitidas
                              else _r("rechazada", "politica_no_admitida", detalle=politica_token))
    if hoja is not None:
        if tst.tsa is None:
            r["nombre_de_la_tsa"] = _OK
        elif tst.tsa.tag == "directorio":
            r["nombre_de_la_tsa"] = _OK if tst.tsa.value == hoja.subject else _r("rechazada",
                                                                                  "nombre_de_la_tsa_no_coincide")
        else:
            r["nombre_de_la_tsa"] = _r("pendiente", "nombre_de_la_tsa_no_comparable", detalle=tst.tsa.tag)

    # genTime exacto (RFC 3161 2.4.2) y coherencia con rfc3161-client
    gen_time = None
    if tst.gen_time.tag_bytes != b"\x18":
        r["gen_time_coherente"] = _r("rechazada", "gen_time_no_canonico",
                                     detalle="etiqueta distinta de GeneralizedTime")
    else:
        texto = bytes(tst.gen_time.data).decode("ascii", errors="replace")
        try:
            gen_time = instante_de_gen_time(texto)
        except SegundoIntercalar:
            r["gen_time_coherente"] = _r("pendiente", "segundo_intercalar_sin_regla", detalle=texto)
        except ValueError as error:
            r["gen_time_coherente"] = _r("rechazada", "gen_time_no_canonico", detalle=str(error))
        else:
            truncado = Fraction(gen_time.numerator // gen_time.denominator)
            if _segundos_de(respuesta_rc.tst_info.gen_time) != truncado:
                r["gen_time_coherente"] = _r("rechazada", "gen_time_incoherente_entre_herramientas")
                gen_time = None
            else:
                r["gen_time_coherente"] = _OK
    extraido["gen_time"] = gen_time
    if tst.accuracy is not None:
        a = tst.accuracy
        extraido["precision"] = (Fraction(a.seconds or 0) + Fraction(a.millis or 0, 10 ** 3)
                                 + Fraction(a.micros or 0, 10 ** 6))

    anclas = [b.x509.load_der_x509_certificate(a.certificado_der) for a in politica.anclas]
    ruta = None
    if hoja is not None:
        if not anclas:
            r["cadena_hasta_el_ancla"] = _r("pendiente", "sin_ancla_configurada")
        else:
            r["cadena_hasta_el_ancla"], ruta = _cadena(b, hoja, certificados, anclas)
    if hoja is None:
        r["vigencia_en_gen_time"] = _r("no_evaluable", "certificado_del_firmante_ausente")
    elif gen_time is None:
        r["vigencia_en_gen_time"] = _r("no_evaluable", "gen_time_no_disponible")
    else:
        revisados = ruta if ruta is not None else [hoja]
        fuera = [c for c in revisados
                 if not _segundos_de(c.not_valid_before_utc) <= gen_time <= _segundos_de(c.not_valid_after_utc)]
        r["vigencia_en_gen_time"] = _r("rechazada", "certificado_no_vigente_en_gen_time") if fuera else _OK
    if not anclas:
        r["verificacion_integral"] = _r("pendiente", "sin_ancla_configurada")
    else:
        constructor = b.rfc3161_client.VerifierBuilder()
        for ancla in anclas:
            constructor = constructor.add_root_certificate(ancla)
        try:
            constructor.build().verify_message(respuesta_rc, evidencia.bytes_compromiso)
            r["verificacion_integral"] = _OK
        except Exception as error:  # noqa: BLE001 - VerificationError con la causa de OpenSSL
            r["verificacion_integral"] = _r("rechazada", "verificacion_integral_no_superada", detalle=str(error))
    r["revocacion"] = _r("pendiente", "revocacion_sin_comprobar")
    return resto("no_evaluable_por_dependencia")


def _unico(atributos, oid):
    valores = atributos.get(oid, [])
    return valores[0][0] if len(valores) == 1 and len(valores[0]) == 1 else None


def _atributos(b, atributos, digest, contenido) -> ResultadoDeComprobacion:
    if digest is None:
        return _r("pendiente", "algoritmo_no_soportado", detalle="digestAlgorithm")
    tipo, resumen = _unico(atributos, OID_CONTENT_TYPE), _unico(atributos, OID_MESSAGE_DIGEST)
    try:
        tipo = tipo.parse(b.x509.ObjectIdentifier).dotted_string if tipo is not None else None
        resumen = resumen.parse(bytes) if resumen is not None else None
    except Exception as error:  # noqa: BLE001 - valor de atributo con otra estructura
        return _r("rechazada", "estructura_fuera_del_perfil", detalle=str(error))
    if tipo != OID_TSTINFO:
        return _r("rechazada", "atributo_content_type_incorrecto")
    if resumen != _hash(digest, contenido):
        return _r("rechazada", "message_digest_no_coincide")
    return _OK


def _firma(b, si, hoja, digest) -> ResultadoDeComprobacion:
    algoritmo = si.signature_algorithm.algorithm.dotted_string
    if digest is None:
        return _r("pendiente", "algoritmo_no_soportado", detalle="digestAlgorithm")
    datos = b.asn1.encode_der(si.signed_attrs)
    clave = hoja.public_key()
    funcion = {"sha256": b.hashes.SHA256, "sha384": b.hashes.SHA384, "sha512": b.hashes.SHA512}[digest]()
    try:
        rsa_admitida = algoritmo in _FIRMAS_RSA and _FIRMAS_RSA[algoritmo] in (None, digest)
        if isinstance(clave, b.rsa.RSAPublicKey) and rsa_admitida:
            clave.verify(si.signature, datos, b.padding.PKCS1v15(), funcion)
        elif isinstance(clave, b.ec.EllipticCurvePublicKey) and _FIRMAS_EC.get(algoritmo) == digest:
            clave.verify(si.signature, datos, b.ec.ECDSA(funcion))
        else:
            return _r("pendiente", "algoritmo_no_soportado", detalle=algoritmo)
    except b.InvalidSignature:
        return _r("rechazada", "firma_del_token_no_coincide")
    return _OK


def _identificador(b, atributos, hoja) -> ResultadoDeComprobacion:
    valores = atributos.get(OID_SIGNING_CERTIFICATE_V2, [])
    if not valores:
        if atributos.get(OID_SIGNING_CERTIFICATE):
            return _r("rechazada", "identificador_de_certificado_solo_sha1")
        return _r("rechazada", "identificador_de_certificado_ausente")
    if len(valores) != 1 or len(valores[0]) != 1:
        return _r("rechazada", "identificador_de_certificado_no_coincide", detalle="atributo repetido")
    try:
        sc = valores[0][0].parse(b.SigningCertificateV2)
    except Exception as error:  # noqa: BLE001
        return _r("pendiente", "estructura_fuera_del_perfil", detalle=str(error))
    primero = sc.certs[0] if sc.certs else None
    if primero is None:
        return _r("rechazada", "identificador_de_certificado_ausente")
    oid = primero.hash_algorithm.algorithm.dotted_string if primero.hash_algorithm else "2.16.840.1.101.3.4.2.1"
    nombre = ALGORITMOS_DE_HASH.get(oid)
    if nombre is None:
        return _r("rechazada", "identificador_de_certificado_solo_sha1", detalle=oid)
    der = hoja.public_bytes(b.serialization.Encoding.DER)
    if primero.cert_hash != _hash(nombre, der):
        return _r("rechazada", "identificador_de_certificado_no_coincide")
    serie = primero.issuer_serial
    if serie is not None and (serie.serial != hoja.serial_number or not any(
            n.tag == "directorio" and n.value == hoja.issuer for n in serie.issuer)):
        return _r("rechazada", "identificador_de_certificado_no_coincide", detalle="issuerSerial")
    return _OK


def _proposito(b, hoja) -> ResultadoDeComprobacion:
    try:
        eku = hoja.extensions.get_extension_for_class(b.x509.ExtendedKeyUsage)
    except b.x509.ExtensionNotFound:
        return _r("rechazada", "uso_extendido_ausente")
    if not eku.critical:
        return _r("rechazada", "uso_extendido_no_critico")
    if list(eku.value) != [b.x509.ExtendedKeyUsageOID.TIME_STAMPING]:
        return _r("rechazada", "uso_extendido_no_exclusivo")
    try:
        uso = hoja.extensions.get_extension_for_class(b.x509.KeyUsage).value
    except b.x509.ExtensionNotFound:
        return _OK
    return _OK if (uso.digital_signature or uso.content_commitment) else _r("rechazada", "uso_de_clave_sin_firma")


def _algoritmos(b, certificados) -> ResultadoDeComprobacion:
    for c in certificados:
        clave = c.public_key()
        if isinstance(clave, b.rsa.RSAPublicKey):
            if clave.key_size < 2048:
                return _r("rechazada", "clave_fuera_del_perfil", detalle=f"RSA {clave.key_size}")
        elif isinstance(clave, b.ec.EllipticCurvePublicKey):
            if clave.curve.name not in ("secp256r1", "secp384r1", "secp521r1"):
                return _r("rechazada", "clave_fuera_del_perfil", detalle=clave.curve.name)
        else:
            return _r("pendiente", "algoritmo_no_soportado", detalle=type(clave).__name__)
        try:
            funcion = c.signature_hash_algorithm
        except b.UnsupportedAlgorithm:
            return _r("pendiente", "algoritmo_no_soportado", detalle=c.signature_algorithm_oid.dotted_string)
        if funcion is None:
            return _r("pendiente", "algoritmo_no_soportado", detalle=c.signature_algorithm_oid.dotted_string)
        if funcion.name not in ("sha256", "sha384", "sha512"):
            return _r("rechazada", "algoritmo_debil", detalle=funcion.name)
    return _OK


def _cadena(b, hoja, certificados, anclas):
    """Diagnostico por nombre de emisor con verify_directly_issued_by; la
    validacion autoritativa es la de OpenSSL en `verificacion_integral`."""
    ruta = [hoja]
    actual = hoja
    for _ in range(8):
        for ancla in anclas:
            if ancla.subject == actual.issuer:
                try:
                    actual.verify_directly_issued_by(ancla)
                except (ValueError, TypeError, b.InvalidSignature):
                    return _r("rechazada", "firma_de_certificado_no_coincide"), None
                return _OK, [*ruta, ancla]
        emisor = next((c for c in certificados if c.subject == actual.issuer and c not in ruta), None)
        if emisor is None:
            return _r("rechazada", "cadena_sin_ancla"), None
        try:
            actual.verify_directly_issued_by(emisor)
        except (ValueError, TypeError, b.InvalidSignature):
            return _r("rechazada", "firma_de_certificado_no_coincide"), None
        ruta.append(emisor)
        actual = emisor
    return _r("rechazada", "cadena_sin_ancla", detalle="ruta demasiado larga"), None


def _impronta(tst, datos: bytes) -> ResultadoDeComprobacion:
    """Impronta del TSTInfo decodificado frente a los bytes sellados."""
    if tst is None:
        return _r("no_evaluable", "estructura_del_token_no_disponible")
    impronta = tst.message_imprint
    nombre = ALGORITMOS_DE_HASH.get(impronta.hash_algorithm.algorithm.dotted_string)
    if nombre is None:
        return _r("rechazada", "algoritmo_de_impronta_no_admitido",
                  detalle=impronta.hash_algorithm.algorithm.dotted_string)
    if impronta.hashed_message != _hash(nombre, datos):
        return _r("rechazada", "impronta_no_coincide")
    return _OK


@dataclass(frozen=True)
class TokenVerificado:
    """Resultado de `verificar_token_sobre_bytes`: comprobaciones
    criptograficas, impronta y, solo si se pudieron leer, genTime exacto y
    precision. No contiene conclusion temporal ni vinculo con ningun
    compromiso concreto."""
    comprobaciones_criptograficas: dict
    impronta: ResultadoDeComprobacion
    gen_time: Fraction | None
    precision: Fraction | None


def verificar_token_sobre_bytes(respuesta_der: bytes, datos: bytes,
                                politica: PoliticaDeConfianzaTemporal) -> TokenVerificado:
    """AE-77: la misma verificacion criptografica que `verificar_sello`
    aplica a un token, sobre bytes arbitrarios. Quien la usa decide que
    compromiso son esos bytes y como se vincula; aqui no se interpreta."""
    try:
        b = _bibliotecas()
    except ImportError as error:
        cripto = {c: _r("pendiente", "dependencia_criptografica_ausente", detalle=str(error))
                  for c in COMPROBACIONES_CRIPTOGRAFICAS}
        return TokenVerificado(cripto, _r("pendiente", "dependencia_criptografica_ausente"), None, None)
    cripto, extraido = _criptografia(b, EvidenciaDeSello(respuesta_der, datos), politica)
    return TokenVerificado(cripto, _impronta(extraido.tst, datos), extraido.gen_time, extraido.precision)


def verificar_sello(entradas: Sequence[bytes], bytes_declaracion: bytes | None, evidencia: EvidenciaDeSello,
                    politica: PoliticaDeConfianzaTemporal, *, codigo_juego: str,
                    sorteo_objetivo: int) -> InformeDeSello:
    """Verifica un sello de un objetivo y separa vinculo de bytes,
    comprobaciones criptograficas, conclusion temporal y limites
    operativos. genTime solo se usa si todas las comprobaciones que no son
    la revocacion estan superadas."""
    objetivo = (codigo_juego, sorteo_objetivo)
    vinculo = {}
    compromiso = None
    try:
        compromiso = leer_compromiso(evidencia.bytes_compromiso)
        vinculo["compromiso_legible"] = _OK
    except CompromisoInvalido as error:
        vinculo["compromiso_legible"] = _r("rechazada", error.motivo)
    if compromiso is not None:
        parciales, _ = _comprobar_vinculo(compromiso, entradas, bytes_declaracion, objetivo)
        vinculo.update(parciales)
    try:
        b = _bibliotecas()
    except ImportError as error:
        cripto = {c: _r("pendiente", "dependencia_criptografica_ausente", detalle=str(error))
                  for c in COMPROBACIONES_CRIPTOGRAFICAS}
        extraido = None
        vinculo["impronta_coincide"] = _r("pendiente", "dependencia_criptografica_ausente")
    else:
        cripto, extraido = _criptografia(b, evidencia, politica)
        vinculo["impronta_coincide"] = _impronta(extraido.tst, evidencia.bytes_compromiso)
    vinculo = {clave: vinculo.get(clave, _r("no_evaluable", "compromiso_ilegible"))
               for clave in COMPROBACIONES_DEL_VINCULO}

    todas = [*vinculo.values(), *cripto.values()]
    rechazos = tuple(dict.fromkeys(m for c in todas if c.estado == "rechazada" for m in c.motivos))
    en_espera = tuple(dict.fromkeys(m for c in todas if c.estado in ("pendiente", "no_evaluable")
                                    for m in c.motivos if m != "revocacion_sin_comprobar"))
    if rechazos:
        return InformeDeSello(objetivo, vinculo, cripto, ConclusionTemporal("no_evaluable"), "rechazada", rechazos)
    if en_espera:
        return InformeDeSello(objetivo, vinculo, cripto, ConclusionTemporal("no_evaluable"), "pendiente",
                              (*en_espera, *LIMITES_OPERATIVOS))

    plazo = instante_de_plazo(compromiso["plazo_utc"])
    margen = segundos_decimales(politica.margen)
    g, a = extraido.gen_time, extraido.precision
    resultado = comparar_con_plazo(g, a, margen, plazo)
    limites = {} if a is None else {"limite_inferior_utc": texto_utc(g - a - margen),
                                    "limite_superior_utc": texto_utc(g + a + margen)}
    conclusion = ConclusionTemporal(
        resultado, plazo_utc=compromiso["plazo_utc"], procedencia_del_plazo=compromiso["procedencia_del_plazo"],
        gen_time_utc=texto_utc(g), precision_segundos=None if a is None else texto_segundos(a),
        margen_segundos=texto_segundos(margen), condicionada_a=LIMITES_OPERATIVOS, **limites)
    estado, motivos = {
        "anterior_al_plazo": ("pendiente", LIMITES_OPERATIVOS),
        "no_concluyente_intervalo_cruza_el_plazo": ("no_concluyente", ("intervalo_cruza_el_plazo",)),
        "posterior_al_plazo": ("rechazada", ("sello_posterior_al_plazo",)),
        "precision_ausente_pendiente": ("pendiente", ("precision_ausente", *LIMITES_OPERATIVOS)),
    }[resultado]
    return InformeDeSello(objetivo, vinculo, cripto, conclusion, estado, motivos)


def resumen_en_capas(informe: InformeDeSello) -> dict:
    """Separacion para la demostracion: comprobaciones criptograficas,
    vinculo de bytes, conclusion temporal y limites operativos."""
    return {
        "comprobaciones_criptograficas": {k: (v.estado, v.motivos)
                                          for k, v in informe.comprobaciones_criptograficas.items()},
        "vinculo_del_compromiso": {k: (v.estado, v.motivos) for k, v in informe.vinculo_del_compromiso.items()},
        "conclusion_temporal": informe.conclusion_temporal,
        "limites_operativos": informe.limites_operativos,
        "no_prueba": informe.no_prueba,
        "estado_del_plano": (informe.estado_del_plano, informe.motivos_del_plano),
    }


# ---------------------------------------------------------------------------
# Plano temporal separado del contrato de AE-74
# ---------------------------------------------------------------------------

PLANO_TEMPORAL = "sello_temporal_de_r0"


@dataclass(frozen=True)
class InformeConPlanoTemporal:
    admision: object
    sellos: dict
    plano_temporal: str
    motivos_del_plano: tuple
    planos: dict = field(default_factory=dict)


def evaluar_admision_con_plano_temporal(entradas: Sequence[bytes], bytes_declaracion: bytes | None,
                                        evidencias: Mapping, politica: PoliticaDeConfianzaTemporal, *,
                                        protocolo_hash_esperado: str | None = None,
                                        objetivos_esperados: Sequence[tuple[str, int]] = ()) -> InformeConPlanoTemporal:
    """Informe de AE-74 sin cambios mas el plano `sello_temporal_de_r0`.
    Las puertas, incluida R0 final, salen de `evaluar_admision` y ninguna
    evidencia temporal las modifica; los planos de autenticacion, recepcion
    y canal siguen como los deja AE-74."""
    admision = _contrato.evaluar_admision(entradas, bytes_declaracion, protocolo_hash_esperado=protocolo_hash_esperado,
                                          objetivos_esperados=objetivos_esperados)
    if admision.ruta != "contrato_1_2":
        estado, motivos, sellos = "no_evaluable", ("ruta_no_admitida",), {}
    else:
        sellos = {tuple(o): verificar_sello(entradas, bytes_declaracion, ev, politica, codigo_juego=o[0],
                                            sorteo_objetivo=o[1]) for o, ev in evidencias.items()}
        faltan = tuple(tuple(o) for o in objetivos_esperados if tuple(o) not in sellos)
        estados = [s.estado_del_plano for s in sellos.values()]
        if not sellos and not faltan:
            estado, motivos = "sin_evidencia", ()
        elif "rechazada" in estados:
            estado = "rechazada"
            motivos = tuple(dict.fromkeys(m for s in sellos.values() if s.estado_del_plano == "rechazada"
                                          for m in s.motivos_del_plano))
        elif "no_concluyente" in estados:
            estado = "no_concluyente"
            motivos = tuple(dict.fromkeys(m for s in sellos.values() if s.estado_del_plano == "no_concluyente"
                                          for m in s.motivos_del_plano))
        else:
            estado = "pendiente"
            motivos = tuple(dict.fromkeys([*(m for s in sellos.values() for m in s.motivos_del_plano),
                                           *(("objetivo_sin_sello",) if faltan else ())]))
    planos = {**admision.planos, PLANO_TEMPORAL: estado}
    return InformeConPlanoTemporal(admision, sellos, estado, motivos, planos)
