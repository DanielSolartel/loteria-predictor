"""
Verificacion primaria de RFC 3161, RFC 5816 y RFC 9162 frente a AE-66
-Etapa AE-67, validada (solo el expediente preparatorio de verificacion
primaria y sus pruebas; no acredita la aplicacion operativa al repositorio).

AE-66 dejo las garantias de RFC 3161 y RFC 9162 como atribuidas y
pendientes de verificacion primaria. Este modulo las contrasta con los
archivos oficiales recibidos del operador: RFC 3161 y RFC 5816 en TXT,
citados por seccion y lineas del archivo fuente, y RFC 9162 en PDF,
citado por seccion y pagina con comprobacion visual. Las impresiones PDF
previas de los TXT solo son apoyo de lectura, no fuente.

Separa lo que sostiene el estandar de las ocho condiciones del repositorio,
que siguen sin fijar: identidad autorizada, canal canonico, unicidad por
objetivo, regla de duplicados, reloj de recepcion, margen de incorporacion,
revision completa y calendario oficial. Las funciones del intervalo del
sello dependen solo de T2 (accuracy de RFC 3161); C4 (incorporacion en la
bitacora) se verifica aparte. No elige proveedor ni mecanismo, no cambia
decisiones ni estados: F1, F2, O3, N2 y U1 siguen pendientes y el
expediente sigue en `expediente_sin_eleccion` con
`AUTORIZA_EVALUACION = False`. Puro: sin red, reloj real, servicio de
sellado, datos reales, PostgreSQL ni predicciones reales.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType

_ALCANCE_DEL_HASH = ("el SHA-256 identifica la copia recibida; se atribuye a la procedencia declarada por el "
                     "operador y no autentica por si solo su origen")


@dataclass(frozen=True)
class Procedencia:
    rfc: str
    archivo: str
    formato: str
    bytes: int
    sha256: str
    url_declarada: str
    via: str
    cabecera: MappingProxyType
    lectura: str
    paginas: int | None
    paginas_comprobadas_visualmente: tuple[int, ...]
    relaciones: MappingProxyType
    apoyo_renderizado: tuple
    erratas: str
    alcance_del_hash: str = _ALCANCE_DEL_HASH


_VIA = "archivo_oficial_aportado_por_el_operador_leido_por_claude"

PROCEDENCIA_RFC = MappingProxyType({
    "rfc_3161": Procedencia(
        "3161", "rfc3161.txt", "txt", 54585, "39fd17644ff2d654bc83814a78b1c5b5e7517f496741f34ead5064943eb98240",
        "https://www.rfc-editor.org/rfc/rfc3161.txt", _VIA,
        MappingProxyType({"rfc": "3161", "categoria": "Standards Track", "fecha": "August 2001",
                          "lineas": "7-19"}),
        "texto_fuente_txt", None, (),
        MappingProxyType({"actualizado_por": "rfc_5816 (relacion derivada de la cabecera de RFC 5816, linea 9; "
                                             "RFC 3161 es anterior y no la declara)"}),
        (MappingProxyType({"archivo": "rfc-editor.org_rfc_rfc3161.txt_utm_sourcechatgpt.com.pdf",
                           "formato": "pdf_impreso_desde_el_navegador", "bytes": 103342,
                           "sha256": "53c70b023529d0ac0331fc7da68503d8af9c18288171d71eac98c250d3a2bdd4",
                           "uso": "apoyo_de_lectura_no_fuente"}),),
        "no_consultadas"),
    "rfc_5816": Procedencia(
        "5816", "rfc5816.txt", "txt", 10216, "9a3eba6ecf14afc7820c51034a608d54d188344a43e9189b0e023d4a6a98f649",
        "https://www.rfc-editor.org/rfc/rfc5816.txt", _VIA,
        MappingProxyType({"rfc": "5816", "updates": "3161", "categoria": "Standards Track", "fecha": "March 2010",
                          "lineas": "7-14"}),
        "texto_fuente_txt", None, (), MappingProxyType({"actualiza": "rfc_3161"}),
        (MappingProxyType({"archivo": "rfc-editor.org_rfc_rfc5816.txt_utm_sourcechatgpt.com.pdf",
                           "formato": "pdf_impreso_desde_el_navegador", "bytes": 53766,
                           "sha256": "591addd4e5dcbee3150533f8a4188b83c14503fbaef47f1700ede07fc77de508",
                           "uso": "apoyo_de_lectura_no_fuente"}),),
        "no_consultadas"),
    "rfc_9162": Procedencia(
        "9162", "rfc9162.pdf", "pdf", 665522, "f0fafb9ef6f0555fc9ea5a65fb3552dea5957999aeb04162b2e8d0a748b1a89d",
        "https://www.rfc-editor.org/rfc/rfc9162.pdf", _VIA,
        MappingProxyType({"rfc": "9162", "obsoletes": "6962", "categoria": "Experimental",
                          "fecha": "December 2021", "pagina": "1"}),
        "pdf_visual", 53, (1, 5, 6, 9, 10, 15, 16, 20, 21, 22, 38, 46, 47),
        MappingProxyType({"deja_obsoleto": "rfc_6962"}), (), "no_consultadas"),
})
"""Ningun archivo recibido se anade al repositorio."""

ESTADOS_AFIRMACION = ("verificada_en_texto_oficial", "matizada_por_el_texto_oficial", "no_en_la_fuente",
                      "pendiente_de_texto_oficial")


@dataclass(frozen=True)
class Referencia:
    fuente: str
    seccion: str
    cita: str
    comprobacion: str
    lineas: tuple[int, int] | None = None
    pagina: int | None = None


@dataclass(frozen=True)
class Afirmacion:
    id: str
    origen_ae66: tuple[str, ...]
    referencias: tuple[Referencia, ...]
    estado: str
    lo_que_sostiene: str
    condicion_del_repositorio: str


def _txt(fuente, seccion, lineas, cita):
    return Referencia(fuente, seccion, cita, "texto_fuente_txt", lineas=lineas)


def _pdf(seccion, pagina, cita):
    return Referencia("rfc_9162", seccion, cita, "pdf_visual", pagina=pagina)


_V, _M, _N = "verificada_en_texto_oficial", "matizada_por_el_texto_oficial", "no_en_la_fuente"

# ---------------------------------------------------------------------------
# RFC 3161 (y RFC 5816 para la identificacion del certificado del firmante)
# ---------------------------------------------------------------------------

AFIRMACIONES_RFC_3161 = (
    Afirmacion(
        "T1", ("instante declarado por la autoridad en el token (genTime)",),
        (_txt("rfc_3161", "2.4.2", (478, 480), "genTime is the time at which the time-stamp token has been created by "
                                                "the TSA. It is expressed as UTC time"),
         _txt("rfc_3161", "1", (42, 43), "A time-stamping service supports assertions of proof that a datum existed "
                                         "before a particular time.")),
        _V, "genTime es el instante UTC en que la autoridad crea el token, no el de la solicitud",
        "que ese instante sea anterior al plazo oficial depende del calendario_oficial y de la definicion del plazo"),
    Afirmacion(
        "T2", ("precision declarada (accuracy)",),
        (_txt("rfc_3161", "2.4.2", (426, 426), "accuracy Accuracy OPTIONAL,"),
         _txt("rfc_3161", "2.4.2", (527, 528), "accuracy represents the time deviation around the UTC time contained "
                                               "in GeneralizedTime."),
         _txt("rfc_3161", "2.4.2", (535, 536), "If either seconds, millis or micros is missing, then a value of zero "
                                               "MUST be taken for the missing field."),
         _txt("rfc_3161", "2.4.2", (538, 542), "By adding the accuracy value to the GeneralizedTime, an upper limit of "
                                               "the time at which the time-stamp token has been created by the TSA can "
                                               "be obtained."),
         _txt("rfc_3161", "2.4.2", (547, 548), "When the accuracy optional field is not present, then the accuracy may "
                                               "be available through other means, e.g., the TSAPolicyId.")),
        _V, "accuracy es opcional; genTime mas y menos accuracy acotan el instante de creacion; su ausencia no "
            "equivale a precision cero",
        "como trata el protocolo un sello cuyo intervalo cruza el plazo sigue sin decidir; calendario_oficial sin "
        "fijar"),
    Afirmacion(
        "T3", ("fuente de tiempo fiable de la autoridad", "confianza en la autoridad y en su reloj"),
        (_txt("rfc_3161", "2.1", (103, 107), "The TSA is REQUIRED: 1. to use a trustworthy source of time. 2. to "
                                             "include a trustworthy time value for each time-stamp token."),
         _txt("rfc_3161", "1", (84, 90), "This standard does not establish overall security requirements for TSA "
                                         "operation")),
        _M, "el estandar exige una fuente de tiempo fiable, pero no establece requisitos generales de seguridad de la "
            "operacion: la confianza descansa en la politica de la autoridad que el cliente acepta",
        "la confianza en una autoridad concreta es una eleccion no hecha; identidad_autorizada sin fijar"),
    Afirmacion(
        "T4", ("la autoridad sella un hash sin examinar el contenido",),
        (_txt("rfc_3161", "2.1", (126, 138), "to only time-stamp a hash representation of the datum ... not to "
                                             "examine the imprint being time-stamped in any way ... not to include "
                                             "any identification of the requesting entity in the time-stamp tokens."),
         _txt("rfc_3161", "2.4.1", (298, 302), "The time-stamp request does not identify the requester, as this "
                                               "information is not validated by the TSA")),
        _V, "la autoridad sella un hash sin examinarlo y el token no identifica al solicitante",
        "quien pide el sello no queda fijado por el sello: identidad_autorizada sin fijar"),
    Afirmacion(
        "T5", ("revocacion o caducidad de certificados", "conservacion del token y de la cadena de certificados",
               "verificacion de la cadena de certificados"),
        (_txt("rfc_3161", "2.3", (195, 203), "The TSA MUST sign each time-stamp message with a key reserved "
                                             "specifically for that purpose. ... id-kp-timeStamping. This extension "
                                             "MUST be critical."),
         _txt("rfc_3161", "2.2", (185, 187), "since the TSA's certificate may have been revoked, the status of the "
                                             "certificate SHOULD be checked"),
         _txt("rfc_3161", "4", (791, 797), "When the TSA private key has been compromised, then the corresponding "
                                           "certificate SHALL be revoked. ... Any token signed by the TSA using that "
                                           "private key cannot be trusted anymore."),
         _txt("rfc_3161", "4", (805, 810), "The TSA signing key MUST be of a sufficient length to allow for a "
                                           "sufficiently long lifetime. Even if this is done, the key will have a "
                                           "finite lifetime."),
         _txt("rfc_5816", "2.2.1", (159, 163), "The certificate identifier (either ESSCertID [ESS] or ESSCertIDv2 "
                                               "[ESSV2]) of the TSA certificate MUST be included as a signerInfo "
                                               "attribute inside a SigningCertificate attribute."),
         _txt("rfc_5816", "2.2.2", (203, 208), "the actual identification of the entity that signed the response will "
                                               "always occur through the use of the certificate identifier (ESSCertID "
                                               "inside a SigningCertificate attribute or ESSCertIDv2 inside a "
                                               "SigningCertificateV2 attribute)")),
        _V, "el token se firma con una clave reservada y un certificado con id-kp-timeStamping critico; el firmante se "
            "identifica por ESSCertID o ESSCertIDv2; la revocacion por compromiso invalida los tokens y la clave tiene "
            "vida finita",
        "la custodia de tokens y de la cadena de certificados, y la eleccion de la autoridad, siguen sin fijar "
        "(identidad_autorizada)"),
    Afirmacion(
        "T6", ("se pueden sellar muchas cabezas en privado",),
        (_txt("rfc_3161", "4", (824, 829), "If different entities obtain time-stamp tokens on the same data object "
                                           "using the same hash algorithm, or a single entity obtains multiple "
                                           "time-stamp tokens on the same object"),
         _txt("rfc_3161", "2.4.2", (471, 476), "The serialNumber field is an integer assigned by the TSA to each "
                                               "TimeStampToken. It MUST be unique for each TimeStampToken issued by a "
                                               "given TSA"),
         _txt("rfc_3161", "2.4.2", (462, 465), "The availability of a time-stamp token log, to allow later "
                                               "verification that a time-stamp token is authentic.")),
        _M, "el estandar admite varios tokens y solo exige un numero de serie unico por token; la publicacion de un "
            "registro de tokens es informacion opcional de la politica: no ofrece publicidad ni unicidad del contenido "
            "sellado; que se sellen muchas cabezas distintas sigue siendo inferencia propia de AE-66",
        "canal_canonico, unicidad_por_objetivo y regla_de_duplicados siguen sin fijar"),
    Afirmacion(
        "T7", ("la de una solicitud al servicio; debe completarse antes del plazo",),
        (_txt("rfc_3161", "3", (592, 594), "There is no mandatory transport mechanism for TSA messages in this "
                                           "document."),
         _txt("rfc_3161", "3.3", (721, 723), "The \"time-to-check-back\" parameter ... is the time in seconds "
                                             "indicating the minimum interval after which the client SHOULD check the "
                                             "status again."),
         _txt("rfc_3161", "2.4.2", (333, 333), "waiting (3),"),
         _txt("rfc_3161", "4", (814, 818), "A client application using only a nonce and no local clock SHOULD be "
                                           "concerned about the amount of time it is willing to wait for a response.")),
        _M, "el estandar no fija la latencia: admite respuestas diferidas y sondeo, y genTime es la creacion del token; "
            "una solicitud anterior al plazo no implica un genTime anterior",
        "el margen frente al plazo (margen_de_incorporacion) sigue sin fijar"),
)

# ---------------------------------------------------------------------------
# RFC 9162 (Experimental)
# ---------------------------------------------------------------------------

AFIRMACIONES_RFC_9162 = (
    Afirmacion(
        "C1", ("puntos de control firmados",),
        (_pdf("4.9", 22, "tree_size is the number of entries currently in the log's Merkle Tree."),
         _pdf("4.10", 22, "When a client requests a log's latest STH (see Section 5.2), the log MUST return an STH "
                          "that is no older than the log's MMD."),
         _pdf("4.10", 22, "The timestamp in tree_head MUST be at least as recent as the most recent SCT timestamp in "
                          "the tree.")),
        _V, "el STH firma tamano, raiz y marca de tiempo; el ultimo STH servido puede tener hasta un MMD de antiguedad",
        "que un punto de control cubra el plazo mas el margen depende de margen_de_incorporacion, sin fijar"),
    Afirmacion(
        "C2", ("pruebas de inclusion y de consistencia",),
        (_pdf("2.1.3", 9, "If the root computed from the inclusion proof matches the true root, then the inclusion "
                          "proof proves that the leaf exists in the tree."),),
        _V, "una prueba de inclusion muestra que una hoja esta en el arbol de ese tamano",
        "no dice nada de las demas entradas: revision_completa sin fijar"),
    Afirmacion(
        "C3", ("pruebas de inclusion y de consistencia",),
        (_pdf("2.1.4", 10, "Merkle consistency proofs prove the append-only property of the tree."),
         _pdf("1", 6, "The append-only property of each log is achieved using Merkle Trees, which can be used to "
                      "efficiently prove that any particular instance of the log is a superset of any particular "
                      "previous instance")),
        _V, "las pruebas de consistencia muestran la propiedad de solo anexado entre dos STH",
        "la consistencia no implica unicidad_por_objetivo (B2a de AE-66)"),
    Afirmacion(
        "C4", ("retraso maximo de incorporacion",),
        (_pdf("4", 16, "Upon producing an SCT, the log MUST fulfill this promise by performing the following actions "
                       "within a fixed amount of time known as the Maximum Merge Delay (MMD)"),
         _pdf("4.1", 16, "This document deliberately does not specify any limits on the value to allow for "
                         "experimentation."),
         _pdf("4.7", 20, "timestamp is the date and time at which the certificate or precertificate was accepted by "
                         "the log"),
         _pdf("4.8", 21, "timestamp is equal to the timestamp from the corresponding TimestampedCertificateEntryDataV2 "
                         "structure."),
         _pdf("11.1", 46, "the maximum period of time during which a misissued certificate can be used without being "
                          "available for audit is twice the MMD.")),
        _V, "el SCT promete incorporar la entrada dentro del MMD, cuyo valor el estandar no limita; la marca de tiempo "
            "es la de aceptacion segun el registro",
        "el reloj_de_recepcion (el del registro) y el margen_de_incorporacion siguen sin fijar"),
    Afirmacion(
        "C5", ("necesidad de monitorizacion o gossip frente a vistas divididas",),
        (_pdf("1", 6, "The log auditing mechanisms described in this document can be circumvented by a misbehaving "
                      "log that shows different, inconsistent views of itself to different clients. Therefore, it is "
                      "necessary to treat each log as a trusted third party."),
         _pdf("8.3", 38, "Checking of the consistency of the log view presented to all entities is more difficult to "
                         "perform because it requires a way to share log responses among a set of CT-using entities"),
         _pdf("11.3", 47, "This technique, known as \"gossip\", is an active area of research and not defined here.")),
        _M, "el estandar reconoce la vista dividida, no la resuelve y exige tratar el registro como tercero de "
            "confianza; el gossip no esta definido",
        "la comparacion entre partes independientes es una condicion del protocolo; revision_completa sin fijar"),
    Afirmacion(
        "C6", ("al menos un testigo honesto compara puntos de control", "cofirma de testigos"),
        (_pdf("11.3", 47, "This technique, known as \"gossip\", is an active area of research and not defined here."),
         _pdf("1", 6, "such mechanisms are outside the scope of this document.")),
        _N, "el estandar no define testigos ni su cofirma; el mecanismo de comparacion queda fuera de su alcance",
        "la eleccion de testigos es una condicion del protocolo sin fijar (canal_canonico, revision_completa)"),
    Afirmacion(
        "C7", ("reglas mal definidas; la consistencia sola no excluye dos predicciones para la misma clave (B2a)",),
        (_pdf("1", 5, "Each log contains certificate chains, which can be submitted by anyone."),
         _pdf("4", 15, "If the log has previously seen this valid submission, it SHOULD return the same SCT as it "
                       "returned before ... If different SCTs are produced for the same submission, multiple log "
                       "entries will have to be created"),
         _pdf("11.3", 47, "producing no more than one SCT for each distinct submission and no more than one STH for "
                          "each distinct tree_size.")),
        _M, "el estandar trata el reenvio de un mismo envio, que puede dar varias entradas; no ofrece unicidad por una "
            "clave de la aplicacion",
        "unicidad_por_objetivo y regla_de_duplicados siguen sin fijar"),
)

CONDICIONES_DEL_REPOSITORIO = MappingProxyType({c: "sin_fijar" for c in (
    "identidad_autorizada", "canal_canonico", "unicidad_por_objetivo", "regla_de_duplicados", "reloj_de_recepcion",
    "margen_de_incorporacion", "revision_completa", "calendario_oficial")})
"""Condiciones del repositorio; ninguna afirmacion del estandar las fija."""

_NO_SE_MODIFICA = "se registra aqui; el modulo de AE-66 no se modifica"

DISCREPANCIAS_CON_AE66 = (
    MappingProxyType({"afirmacion": "T3", "texto_ae66": "confianza en la autoridad y en su reloj",
                      "texto_oficial": "RFC 3161 1, lineas 84-90: no establece requisitos generales de seguridad de la "
                                       "operacion; la confianza depende de la politica que el cliente acepta",
                      "tratamiento": _NO_SE_MODIFICA}),
    MappingProxyType({"afirmacion": "T7", "texto_ae66": "la de una solicitud al servicio; debe completarse antes del "
                                                        "plazo",
                      "texto_oficial": "RFC 3161 3 y 3.3: sin transporte obligatorio, respuestas diferidas y sondeo; "
                                       "genTime es la creacion del token",
                      "tratamiento": _NO_SE_MODIFICA}),
    MappingProxyType({"afirmacion": "C5", "texto_ae66": "necesidad de monitorizacion o gossip frente a vistas "
                                                        "divididas",
                      "texto_oficial": "RFC 9162 1, p. 6: hay que tratar el registro como tercero de confianza; 11.3, "
                                       "p. 47: gossip no definido",
                      "tratamiento": _NO_SE_MODIFICA}),
    MappingProxyType({"afirmacion": "C6", "texto_ae66": "al menos un testigo honesto compara puntos de control",
                      "texto_oficial": "RFC 9162 no define testigos; la comparacion queda fuera de su alcance",
                      "tratamiento": "los testigos de A4 son una condicion del protocolo, no del estandar; "
                                     + _NO_SE_MODIFICA}),
    MappingProxyType({"afirmacion": "C7", "texto_ae66": "la consistencia sola no excluye dos predicciones para la "
                                                        "misma clave",
                      "texto_oficial": "RFC 9162 4, p. 15: un mismo envio puede dar varias entradas; no hay unicidad "
                                       "por clave de la aplicacion",
                      "tratamiento": "coincide con B2a de AE-66; " + _NO_SE_MODIFICA}),
    MappingProxyType({"afirmacion": "categoria_rfc_9162", "texto_ae66": "RFC 9162 citado sin categoria",
                      "texto_oficial": "RFC 9162, p. 1: Category: Experimental",
                      "tratamiento": "se registra la categoria; " + _NO_SE_MODIFICA}),
)

DERIVACION_MARGEN_RFC_9162 = MappingProxyType({
    "clase": "derivacion_propia",
    "base": "RFC 9162 11.1, p. 46 (twice the MMD) y 4.10, p. 22 (STH no mas antiguo que el MMD)",
    "texto": "si el registro opera correctamente, una entrada aceptada antes del plazo esta incorporada a mas tardar "
             "en plazo + MMD, y un STH servido puede tener hasta un MMD de antiguedad; una vista basada en un STH "
             "servido solo cubre esa entrada si se obtiene despues de plazo + 2 MMD",
    "estado_en_el_repositorio": "margen_de_incorporacion_sin_fijar",
})

# ---------------------------------------------------------------------------
# Intervalo del sello (depende de T2)
# ---------------------------------------------------------------------------

RESULTADOS_SELLO = ("anterior_con_margen_de_precision", "no_concluyente_por_precision",
                    "posterior_al_plazo_con_margen_de_precision", "precision_ausente_pendiente")


@dataclass(frozen=True)
class PrecisionSello:
    """Accuracy de RFC 3161 2.4.2: campos ausentes valen cero; millis y
    micros entre 1 y 999."""
    seconds: int | None = None
    millis: int | None = None
    micros: int | None = None

    def __post_init__(self):
        if self.seconds is not None and self.seconds < 0:
            raise ValueError("seconds no puede ser negativo")
        for nombre in ("millis", "micros"):
            valor = getattr(self, nombre)
            if valor is not None and not 1 <= valor <= 999:
                raise ValueError(f"{nombre} debe estar entre 1 y 999")

    def como_timedelta(self) -> timedelta:
        return timedelta(seconds=self.seconds or 0, milliseconds=self.millis or 0, microseconds=self.micros or 0)


def _exigir_zona(instante: datetime, nombre: str) -> None:
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError(f"{nombre} debe ser un instante con zona horaria explicita")


def intervalo_del_sello(gen_time: datetime, precision: PrecisionSello | None):
    """Limites inferior y superior del instante de creacion del token. Sin
    accuracy devuelve None: puede venir por otros medios y no vale cero."""
    _exigir_zona(gen_time, "gen_time")
    if precision is None:
        return None
    desviacion = precision.como_timedelta()
    return gen_time - desviacion, gen_time + desviacion


def sello_anterior_al_plazo(gen_time: datetime, precision: PrecisionSello | None, plazo: datetime) -> str:
    """Compara el intervalo del sello con el plazo. Ningun resultado afirma
    acreditacion ni unicidad."""
    _exigir_zona(plazo, "plazo")
    intervalo = intervalo_del_sello(gen_time, precision)
    if intervalo is None:
        return "precision_ausente_pendiente"
    inferior, superior = intervalo
    if superior < plazo:
        return "anterior_con_margen_de_precision"
    if inferior >= plazo:
        return "posterior_al_plazo_con_margen_de_precision"
    return "no_concluyente_por_precision"
