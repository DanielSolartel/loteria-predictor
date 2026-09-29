"""
Propuesta revisable de evidencia temporal externa -Etapa AE-66,
validada (solo el expediente preparatorio y sus pruebas; no aprueba
ningun mecanismo ni acredita operativamente F1, F2 u O3).

AE-65 dejo pendientes F1 (anterioridad), F2 (correspondencia de la
filtracion) y O3 (tratamiento de omisiones). Este modulo compara
alternativas para acreditar, antes del plazo oficial de cada sorteo:

(a) la salida y su vinculo con la entrada y el codigo declarados;
(b) un conjunto de predicciones unico y completo;
(c) la ausencia de prediccion cuando hay omision, separada en dos vias:
    la omision declarada antes del plazo (via 1) y la ausencia inferida
    de una vista sin entrada (via 2);
(d) la procedencia del calendario y de la hora oficial.

Registra para cada alternativa sus supuestos, pruebas verificables,
fallos posibles, costo y lo que demostraria o no. Las garantias de RFC
3161 y RFC 9162 quedan pendientes de verificacion primaria. La
recomendacion es condicional y queda para la decision del operador:
`mecanismo_de_sellado_temporal_externo` sigue sin valor. Ningun resultado
de las funciones afirma una acreditacion operativa. F1, F2, O3, N2 y U1
siguen pendientes; el expediente sigue en `expediente_sin_eleccion` con
`AUTORIZA_EVALUACION = False`. Puro: sin red, reloj real, servicio de
sellado, datos reales, PostgreSQL ni predicciones reales.
"""
from __future__ import annotations

import hashlib
import hmac
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

REQUISITOS = ("a_salida_y_vinculo", "b_unico_y_completo", "c_ausencia_de_prediccion", "d_calendario_y_hora")
COLUMNAS_DE_LA_MATRIZ = ("a_salida_y_vinculo", "b_unico_y_completo", "c_via_1_omision_declarada",
                         "c_via_2_ausencia_inferida", "d_calendario_y_hora")
ESTADOS_DE_CELDA = ("demuestra_bajo_supuestos", "condicionado", "parcial", "no_demuestra", "pendiente")

RESULTADOS_OMISION_DECLARADA = ("omision_declarada_sujeta_a_reglas_pendientes", "conflicto_de_clave",
                                "declaracion_recibida_despues_del_plazo", "sin_declaracion")
RESULTADOS_AUSENCIA_INFERIDA = ("entrada_recibida_antes_del_plazo", "vista_no_concluyente_anterior_a_plazo_mas_margen",
                                "ausencia_inferida_pendiente_de_reloj_margen_y_revision",
                                "ausencia_inferida_pendiente_sin_margen")
"""Via 1 y via 2 tienen vocabularios disjuntos; ninguno afirma acreditacion
ni ausencia."""


@dataclass(frozen=True)
class Celda:
    estado: str
    texto: str


@dataclass(frozen=True)
class Fuente:
    id: str
    referencia: str
    acceso: str
    estado: str
    verificado: tuple[str, ...]
    atribuido_pendiente: tuple[str, ...]


@dataclass(frozen=True)
class Alternativa:
    id: str
    nombre: str
    instante: str
    precision: str
    latencia: str
    supuestos: tuple[str, ...]
    pruebas_verificables: tuple[str, ...]
    fallos_posibles: tuple[str, ...]
    costo: str
    fuentes: tuple[str, ...]
    matriz: Mapping[str, Celda]


@dataclass(frozen=True)
class Complemento:
    id: str
    nombre: str
    supuestos: tuple[str, ...]
    demuestra: str
    no_demuestra: str


# ---------------------------------------------------------------------------
# Fuentes primarias
# ---------------------------------------------------------------------------

FUENTES_PRIMARIAS = MappingProxyType({
    "rfc_3161": Fuente(
        "rfc_3161", "Adams, Cain, Pinkas y Zuccherato (2001), RFC 3161, Time-Stamp Protocol (TSP), IETF",
        "bloqueado desde el sandbox (rfc-editor.org, ietf.org, datatracker.ietf.org)",
        "pendiente_de_verificacion_primaria", (),
        ("instante declarado por la autoridad en el token (genTime)", "precision declarada (accuracy)",
         "fuente de tiempo fiable de la autoridad", "la autoridad sella un hash sin examinar el contenido")),
    "rfc_9162": Fuente(
        "rfc_9162", "Laurie, Messeri y Stradling (2021), RFC 9162, Certificate Transparency Version 2.0, IETF",
        "bloqueado desde el sandbox (rfc-editor.org, ietf.org, datatracker.ietf.org)",
        "pendiente_de_verificacion_primaria", (),
        ("puntos de control firmados", "pruebas de inclusion y de consistencia", "retraso maximo de incorporacion",
         "necesidad de monitorizacion o gossip frente a vistas divididas")),
    "opentimestamps_autores": Fuente(
        "opentimestamps_autores", "documentacion de los autores: opentimestamps-client y opentimestamps-server "
                                  "(GitHub)",
        "accesible", "verificada_en_documentacion_de_los_autores",
        ("Pending confirmation in Bitcoin blockchain",
         "It takes a few hours for the timestamp to get confirmed by the Bitcoin blockchain; we're not doing one "
         "transaction per timestamp",
         "Bitcoin block ... attests existence as of",
         "aggregation, Bitcoin timestamping, and remote calendar services"),
        ("precision del tiempo de bloque",)),
})
"""Ninguna garantia sin verificar se usa como hecho."""

# ---------------------------------------------------------------------------
# Alternativas y complementos
# ---------------------------------------------------------------------------

_C = Celda
_PEND_V2 = _C("pendiente", "inferir la ausencia de una vista sin entrada sigue pendiente mientras no esten fijados y "
                           "verificados el reloj de recepcion, el margen de incorporacion y la revision completa")


def _matriz(**celdas):
    return MappingProxyType({**celdas, "c_via_2_ausencia_inferida": _PEND_V2})


ALTERNATIVAS = MappingProxyType({
    "A1": Alternativa(
        "A1", "sello de una autoridad de tiempo (RFC 3161) sobre la cabeza o el manifiesto",
        "instante declarado por la autoridad en el token (pendiente de verificacion primaria)",
        "la que declare la autoridad (pendiente de verificacion primaria)",
        "la de una solicitud al servicio; debe completarse antes del plazo",
        ("confianza en la autoridad y en su reloj", "conservacion del token y de la cadena de certificados"),
        ("token que vincula el hash con el instante", "verificacion de la cadena de certificados"),
        ("se pueden sellar muchas cabezas en privado", "revocacion o caducidad de certificados", "perdida del token"),
        "bajo", ("rfc_3161",),
        _matriz(
            a_salida_y_vinculo=_C("parcial", "que el hash existia antes del instante acreditado; no la dependencia "
                                             "funcional"),
            b_unico_y_completo=_C("no_demuestra", "sellos privados de varias ramas (B1)"),
            c_via_1_omision_declarada=_C("no_demuestra", "un sello aislado no excluye declaraciones en otras ramas"),
            d_calendario_y_hora=_C("parcial", "instante de la autoridad, no el calendario"))),
    "A2": Alternativa(
        "A2", "anclaje agregado en un libro publico (tipo OpenTimestamps)",
        "el del bloque que confirma; la prueba pendiente es solo una promesa del calendario",
        "precision del tiempo de bloque pendiente de verificacion",
        "a few hours segun los autores; si se sella cerca del plazo el bloque puede ser posterior al plazo",
        ("seguridad del libro publico", "los calendarios publican la agregacion"),
        ("prueba de inclusion hasta un bloque con hora",),
        ("compromisos agregados y ocultos: bifurcaciones invisibles", "latencia incierta frente al plazo"),
        "bajo, con latencia incierta", ("opentimestamps_autores",),
        _matriz(
            a_salida_y_vinculo=_C("parcial", "que el hash existia antes del bloque, que puede ser posterior al plazo"),
            b_unico_y_completo=_C("no_demuestra", "compromisos ocultos: varias ramas pueden anclarse (B1)"),
            c_via_1_omision_declarada=_C("no_demuestra", "un anclaje aislado no excluye declaraciones en otras ramas"),
            d_calendario_y_hora=_C("parcial", "hora del bloque, no el calendario"))),
    "A3": Alternativa(
        "A3", "canal publico con controles de modificacion (por ejemplo, repositorio con rama protegida)",
        "hora de recepcion de la plataforma", "la de la plataforma", "la de una publicacion",
        ("el propietario no reescribe; los controles no son criptograficamente de solo anexado",
         "la plataforma registra fielmente la recepcion"),
        ("historial publico", "hora de recepcion de la plataforma", "replicas de terceros"),
        ("reescritura por el propietario", "hora controlada por la plataforma", "vista dividida no detectable sin "
                                                                                 "terceros"),
        "medio", (),
        _matriz(
            a_salida_y_vinculo=_C("parcial", "que el hash se publico antes de la hora de la plataforma"),
            b_unico_y_completo=_C("parcial", "bajo el supuesto de no reescritura; sin deteccion de vista dividida"),
            c_via_1_omision_declarada=_C("parcial", "una declaracion publicada en el canal, bajo no reescritura"),
            d_calendario_y_hora=_C("parcial", "hora de la plataforma"))),
    "A4": Alternativa(
        "A4", "bitacora de transparencia con puntos de control firmados y testigos independientes",
        "recepcion segun el reloj de la bitacora (pendiente de fijar)",
        "la del reloj de la bitacora (pendiente)", "incorporacion dentro de un margen (pendiente de fijar)",
        ("la bitacora es el unico canal que cuenta", "al menos un testigo honesto compara puntos de control",
         "reglas del protocolo fijadas: identidad, canal, clave unica, duplicados, recepcion y revision completa"),
        ("prueba de inclusion", "prueba de consistencia entre puntos de control", "cofirma de testigos"),
        ("colusion de la bitacora con los testigos", "indisponibilidad cerca del plazo", "reglas mal definidas; la "
         "consistencia sola no excluye dos predicciones para la misma clave (B2a)"),
        "medio-alto", ("rfc_9162",),
        _matriz(
            a_salida_y_vinculo=_C("parcial", "recepcion del hash segun el reloj de la bitacora"),
            b_unico_y_completo=_C("condicionado", "condicionado a las reglas pendientes; la consistencia sola no basta"),
            c_via_1_omision_declarada=_C("condicionado", "omision declarada antes del plazo y sin conflicto, bajo las "
                                                         "reglas pendientes"),
            d_calendario_y_hora=_C("parcial", "reloj de la bitacora, no el calendario"))),
    "A5": Alternativa(
        "A5", "custodio humano independiente que recibe la cabeza antes de cada plazo",
        "constancia del custodio", "la de la constancia", "la de la entrega al custodio",
        ("independencia del custodio", "registro integro del custodio"),
        ("constancias firmadas", "registro del custodio"),
        ("colusion", "error humano", "indisponibilidad"), "alto", (),
        _matriz(
            a_salida_y_vinculo=_C("parcial", "que el hash se entrego antes de la constancia"),
            b_unico_y_completo=_C("condicionado", "condicionado a la confianza en el custodio y a reglas equivalentes"),
            c_via_1_omision_declarada=_C("condicionado", "declaracion entregada al custodio antes del plazo, bajo "
                                                         "reglas equivalentes"),
            d_calendario_y_hora=_C("parcial", "constancia del custodio"))),
})

COMPLEMENTOS = MappingProxyType({
    "M": Complemento("M", "manifiesto por prediccion",
                     ("huellas de codigo, entorno, dependencias, entrada, estado_auxiliar, semillas y salida",),
                     "identifica los artefactos declarados de cada salida",
                     "no demuestra que esos artefactos fueran los unicos insumos ni su anterioridad"),
    "R": Complemento("R", "recomputacion conforme a los artefactos declarados",
                     ("entorno, dependencias, estado_auxiliar, aleatoriedad y ausencia de accesos externos no "
                      "declarados fijados; exige un contrato de inferencia, que no existe",),
                     "consistencia de la salida con los artefactos declarados",
                     "no demuestra anterioridad ni ausencia de fuga: los datos o el estado auxiliar pueden contener "
                     "y_t antes del plazo aunque el codigo se sellara antes (B6b)"),
    "C": Complemento("C", "declaracion de cierre por objetivo, anterior al plazo",
                     ("sujeta a las reglas pendientes del protocolo",),
                     "una prediccion u omision declarada para la clave, si las reglas se cumplen",
                     "no resuelve por si sola el conflicto de clave; no permite inferir ausencias (via 2)"),
    "K": Complemento("K", "calendario y hora oficiales",
                     ("fuente oficial del calendario y de la hora del sorteo", "instantaneas archivadas por terceros",
                      "tiempos conscientes de zona (America/Bogota, UTC-5, sin horario de verano)"),
                     "procedencia declarada del plazo y de la hora del sorteo",
                     "la definicion del plazo sigue pendiente"),
})

CONDICIONES_PENDIENTES_DEL_PROTOCOLO = MappingProxyType({
    "identidad_autorizada": "quien puede publicar entradas validas y con que firma",
    "canal_canonico_exclusivo": "solo cuenta un canal designado; lo sellado fuera no cuenta",
    "clave_unica_por_objetivo": "(protocolo_hash, juego, objetivo)",
    "regla_de_duplicados": "que ocurre si una clave tiene mas de una entrada; sin decidir",
    "recepcion_antes_del_plazo": "con que reloj y con que margen de incorporacion",
    "revision_completa": "el verificador enumera todas las entradas pertinentes hasta un punto de control que cubra "
                         "el plazo mas el margen",
})

NO_DEMUESTRA_NINGUNA = MappingProxyType({
    "fuga_anticipada_de_y_t": "los sellos acotan cuando existia la salida, no que informacion tenia",
    "integridad_del_sorteo": "la uniformidad condicional de AE-65 sigue siendo una hipotesis",
    "correccion_del_codigo": "ningun sello verifica que el codigo haga lo declarado",
    "validez_inferencial": "ninguna evidencia temporal fija una regla ni una garantia inferencial",
})

PREGUNTAS_ABIERTAS = MappingProxyType({
    "definicion_del_plazo": "cierre de ventas o inicio del sorteo, y margen",
    "reloj_de_recepcion": "reloj que fija la recepcion antes del plazo",
    "margen_de_incorporacion": "margen entre recepcion e inclusion",
    "procedimiento_de_revision_completa": "como se enumeran todas las entradas pertinentes",
    "canal": "canal designado", "identidad": "quien puede publicar y con que firma", "regla_de_duplicados": "regla de aceptacion",
    "testigos": "quien compara puntos de control", "custodia": "custodia de tokens y pruebas",
    "fuente_del_calendario": "fuente oficial y su archivo",
})
"""Ninguna se registra como decision del expediente."""

RECOMENDACION_CONDICIONAL = MappingProxyType({
    "estado": "recomendacion_condicional_para_decision_del_operador",
    "combinacion": ("A4", "C", "M", "K"),
    "texto": "si el operador acepta los supuestos de A4 y fija las reglas del protocolo, el reloj de recepcion, el "
             "margen de incorporacion y la definicion del plazo, A4 con C, M y K podria cubrir (b) bajo esos "
             "supuestos y (c) solo por la via 1, sujeta a esas reglas; la via 2 sigue pendiente. Refuerzo "
             "opcional: A1 sobre los puntos de control. Otras combinaciones podrian cubrirlos bajo supuestos "
             "distintos (A5 con reglas equivalentes, o A3 con reglas y testigos). R solo con un contrato de "
             "inferencia y los artefactos plenamente fijados. Nada deja de ser pendiente mientras las reglas y las "
             "fuentes primarias no esten fijadas y verificadas",
})
"""No asigna valor a `mecanismo_de_sellado_temporal_externo`."""

# ---------------------------------------------------------------------------
# Modelos sinteticos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntradaBitacora:
    clave: tuple[str, str, int]
    tipo: str  # "prediccion" u "omision_declarada"
    contenido_hash: str
    recibido_en: datetime
    incluido_en: datetime


@dataclass(frozen=True)
class SelloSintetico:
    hash: str
    instante: datetime
    firma: str


def _exigir_zona(instante: datetime, nombre: str) -> None:
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError(f"{nombre} debe ser un instante con zona horaria explicita")


def _firma(hash_: str, instante: datetime, clave: bytes) -> str:
    mensaje = f"{hash_}|{instante.astimezone(timezone.utc).isoformat()}".encode("utf-8")
    return hmac.new(clave, mensaje, hashlib.sha256).hexdigest()


def sellar_sintetico(hash_: str, instante: datetime, clave: bytes) -> SelloSintetico:
    """Modelo de sello de una autoridad: HMAC de prueba sobre (hash, instante)."""
    _exigir_zona(instante, "instante")
    return SelloSintetico(hash_, instante, _firma(hash_, instante, clave))


def sellos_antes_del_plazo(sellos: Sequence[SelloSintetico], plazo: datetime, clave: bytes) -> tuple:
    """Sellos con firma valida e instante anterior al plazo. No dice nada
    sobre la unicidad de lo sellado."""
    _exigir_zona(plazo, "plazo")
    return tuple(s for s in sellos
                 if hmac.compare_digest(s.firma, _firma(s.hash, s.instante, clave)) and s.instante < plazo)


def es_prefijo(vista_a: Sequence, vista_b: Sequence) -> bool:
    return len(vista_a) <= len(vista_b) and tuple(vista_b[:len(vista_a)]) == tuple(vista_a)


def vistas_consistentes(vista_a: Sequence, vista_b: Sequence) -> bool:
    """Consistencia de la bitacora: una vista es prefijo de la otra. No
    implica unicidad de las predicciones."""
    return es_prefijo(vista_a, vista_b) or es_prefijo(vista_b, vista_a)


def claves_duplicadas(vista: Sequence[EntradaBitacora]) -> tuple:
    """Claves con mas de una entrada. No aplica ninguna regla de aceptacion."""
    cuenta = Counter(e.clave for e in vista)
    return tuple(sorted(c for c, n in cuenta.items() if n > 1))


def vista_publicada_en(bitacora: Sequence[EntradaBitacora], instante: datetime) -> tuple:
    """Entradas incluidas hasta el instante de publicacion del punto de control."""
    _exigir_zona(instante, "instante")
    return tuple(e for e in bitacora if e.incluido_en <= instante)


def evaluar_omision_declarada(vista: Sequence[EntradaBitacora], clave, plazo: datetime) -> str:
    """Via 1. El mejor resultado sigue sujeto a las reglas pendientes."""
    _exigir_zona(plazo, "plazo")
    entradas = [e for e in vista if e.clave == clave]
    declaraciones = [e for e in entradas if e.tipo == "omision_declarada"]
    if not declaraciones:
        return "sin_declaracion"
    if len(entradas) > 1:
        return "conflicto_de_clave"
    if declaraciones[0].recibido_en < plazo:
        return "omision_declarada_sujeta_a_reglas_pendientes"
    return "declaracion_recibida_despues_del_plazo"


def evaluar_ausencia_inferida(vista: Sequence[EntradaBitacora], clave, plazo: datetime, margen: timedelta | None,
                              publicada_en: datetime, *, reloj_de_recepcion: str | None = None) -> str:
    """Via 2. Ningun resultado afirma la ausencia: sin reloj, margen y
    revision completa fijados y verificados, queda pendiente."""
    _exigir_zona(plazo, "plazo")
    _exigir_zona(publicada_en, "publicada_en")
    if any(e.clave == clave and e.recibido_en < plazo for e in vista):
        return "entrada_recibida_antes_del_plazo"
    if margen is None or reloj_de_recepcion is None:
        return "ausencia_inferida_pendiente_sin_margen"
    if publicada_en < plazo + margen:
        return "vista_no_concluyente_anterior_a_plazo_mas_margen"
    return "ausencia_inferida_pendiente_de_reloj_margen_y_revision"


def recomputar(funcion: Callable, artefactos: Mapping):
    return funcion(artefactos)


def recomputacion_conforme(funcion: Callable, artefactos: Mapping, salida_registrada) -> bool:
    """Consistencia con los artefactos declarados; no anterioridad ni
    ausencia de fuga."""
    return tuple(recomputar(funcion, artefactos)) == tuple(salida_registrada)
