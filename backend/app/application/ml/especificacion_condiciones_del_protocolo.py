"""
Especificacion verificable de las condiciones del protocolo -Etapa AE-68,
validada (solo el expediente preparatorio y sus pruebas; R0, R9 y las ocho
condiciones siguen sin fijar).

AE-66 y AE-67 dejaron sin fijar ocho condiciones del protocolo. Este modulo
las especifica de forma verificable, junto con dos requisitos previos: R0,
la declaracion previa del protocolo, que es la unica raiz de confianza, y
R9, el puente entre nuestras entradas y el canal. Separa tres planos:

(E) lo que garantiza el estandar: solo afirmaciones de AE-67; lo que
    procede de RFC 9162 cubre certificados y precertificados, no nuestras
    entradas;
(P) lo que tendria que garantizar el protocolo hipotetico;
(O) lo que exigiria evidencia operativa.

Los recibos, puntos de control y firmas son modelos sinteticos para las
pruebas; no son una implementacion conforme a RFC 9162 ni una decision
sobre el esquema real. Las hipotesis temporales H1-H5 son requisitos de
un canal sintetico, no garantias de RFC 9162 para predicciones. Las ocho
condiciones, R0 y R9 siguen `sin_fijar`; no se elige mecanismo, firma ni
regla, y ningun registro de AE-63 a AE-67 cambia. El expediente sigue en
`expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`. Puro: sin
red, relojes o servicios reales, datos reales ni PostgreSQL.
"""
from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType

from app.application.ml.propuesta_evidencia_temporal_externa import EntradaBitacora

_R0, _R9 = "declaracion_previa_del_protocolo", "puente_entrada_canal"
_SC = " solo_certificados"


@dataclass(frozen=True)
class Requisito:
    id: str
    clase: str
    definicion_verificable: str
    estandar: tuple[str, ...]
    protocolo: str
    evidencia_operativa: str
    contraejemplo: str
    verificacion_depende_de: tuple[str, ...]
    decisiones_del_operador: tuple[str, ...]
    criterio_para_mantener_pendiente: str
    estado: str = "sin_fijar"


ALCANCE_RFC_9162 = (
    "RFC 9162 describe registros de certificados y precertificados (AE-67, C1-C7); sus SCT, su MMD y sus pruebas no "
    "se atribuyen a predicciones ni a omisiones de este repositorio. El modelo sintetico de AE-68 es una analogia, "
    "no una implementacion conforme")

MODELO_DE_FIRMA = ("la verificacion de firma se inyecta como funcion; el HMAC de las pruebas solo modela firmas y no es "
                   "una decision sobre el esquema real ni evidencia operativa")

# ---------------------------------------------------------------------------
# Requisitos previos
# ---------------------------------------------------------------------------

AUTENTICACION_DE_R0 = MappingProxyType({
    "sello_externo_anterior_al_corte": MappingProxyType({
        "texto": "un sello externo del hash del protocolo con instante anterior al corte (del tipo de A1; T1, T2)",
        "estado": "pendiente"}),
    "publicacion_fuera_de_banda": MappingProxyType({
        "texto": "publicacion del hash del protocolo por el operador en un medio con copias de terceros",
        "estado": "pendiente"}),
    "reconocimiento_del_operador": MappingProxyType({
        "texto": "reconocimiento explicito del operador de que ese hash es el protocolo vigente; sin el, un sello o una "
                 "publicacion no excluyen protocolos alternativos (T6)",
        "estado": "pendiente"}),
})
"""R0 es la unica raiz: ninguna condicion la define ni la autentica."""

REQUISITOS_PREVIOS = MappingProxyType({
    _R0: Requisito(
        _R0, "requisito_previo",
        "un unico documento fijado antes del corte (el protocolo de AE-52) que declara el conjunto de claves, la "
        "identidad del canal, la clave de unicidad, la regla de duplicados, el reloj y su cota de error, el margen, "
        "la revision completa, la politica ante vistas divididas, la fuente del calendario y la definicion del plazo",
        ("AE-67:T1", "AE-67:T2", "AE-67:T6"),
        "el protocolo_hash encabeza la cadena y todo lo demas se comprueba contra lo que declara",
        "sello externo anterior al corte, publicacion fuera de banda y reconocimiento del operador",
        "dos protocolos distintos, ambos sellados antes del corte, entre los que se elige despues",
        (), ("contenido de la declaracion", "medio de publicacion"),
        "mientras falte cualquiera de los tres elementos de AUTENTICACION_DE_R0"),
    _R9: Requisito(
        _R9, "requisito_previo",
        "como se codifica una entrada del protocolo (prediccion u omision declarada, JSON canonico de AE-52) en el "
        "canal que se designe y que recibo firmado emite el canal: hash canonico, t_rec y promesa de incorporacion",
        ("AE-67:C4" + _SC, "AE-67:C7" + _SC),
        "formato del recibo, su firma y el compromiso de incorporacion del canal (H1, H2)",
        "recibos emitidos y auditados por el canal que se designe",
        "atribuir a nuestras entradas un SCT o un MMD de un registro de certificados",
        ("canal_canonico",), ("canal", "formato del recibo"),
        "mientras no exista un canal con recibos verificables para nuestro formato"),
})

# ---------------------------------------------------------------------------
# Condiciones (nombres de AE-67)
# ---------------------------------------------------------------------------

CONDICIONES_DEL_PROTOCOLO = MappingProxyType({
    "identidad_autorizada": Requisito(
        "identidad_autorizada", "condicion",
        "una entrada es admisible solo si su firma se verifica con una clave del conjunto declarado en R0 y vigente "
        "en su t_rec",
        ("AE-67:T4", "AE-67:T5", "AE-67:C7" + _SC),
        "conjunto de claves y revocacion declarados en R0",
        "custodia de claves y registro de revocaciones",
        "una entrada firmada con una clave no declarada, o revocada antes de su t_rec, cuenta",
        (_R0,), ("esquema de firma", "custodios", "revocacion"),
        "mientras R0 no fije y autentique el conjunto de claves"),
    "canal_canonico": Requisito(
        "canal_canonico", "condicion",
        "solo cuentan las entradas incluidas en el canal cuya identidad declara R0",
        ("AE-67:T6", "AE-67:C5" + _SC),
        "identidad del canal en R0; los sellos externos solo refuerzan y nunca anaden entradas",
        "operacion y disponibilidad del canal",
        "una rama sellada fuera del canal o un segundo canal no declarado (B2c de AE-66)",
        (_R0,), ("mecanismo, sin elegir",),
        "mientras R0 no declare el canal"),
    "unicidad_por_objetivo": Requisito(
        "unicidad_por_objetivo", "condicion",
        "tras la revision completa, cada clave (protocolo_hash, juego, objetivo) no tiene entradas, solo tiene "
        "reintentos identicos o tiene un conflicto registrado; la unicidad se comprueba como ausencia de conflictos "
        "registrados, no se afirma",
        ("AE-67:C3" + _SC, "AE-67:C7" + _SC),
        "composicion de la clave y registro de conflictos",
        "revision completa del canal",
        "dos contenidos incompatibles para la misma clave en una bitacora consistente (B2a de AE-66); una "
        "prediccion y una omision con la misma clave",
        ("identidad_autorizada", "regla_de_duplicados", "revision_completa"), ("composicion de la clave",),
        "mientras lo este cualquiera de sus dependencias"),
    "regla_de_duplicados": Requisito(
        "regla_de_duplicados", "condicion",
        "primero se detecta y registra cada clave con varias entradas (reintento identico o contenidos "
        "incompatibles, por hash canonico); despues se aplica una regla determinista declarada en R0 que solo usa "
        "hash, tipo, firmante y t_rec, nunca resultados ni puntuaciones; el registro se conserva",
        ("AE-67:C7" + _SC,),
        "candidatas sin elegir: primera_recibida, invalidar_objetivo, invalidar_protocolo",
        "revision completa del canal",
        "una regla que elige por puntuacion o que borra el conflicto al invalidar el objetivo",
        ("reloj_de_recepcion", "revision_completa"), ("la regla",),
        "mientras R0 no la declare"),
    "reloj_de_recepcion": Requisito(
        "reloj_de_recepcion", "condicion",
        "t_rec segun el recibo del canal, con zona, resolucion y cota declarada del error frente a UTC; la "
        "comparacion con el plazo usa el intervalo t_rec +- (cota + resolucion)",
        ("AE-67:T1", "AE-67:T2", "AE-67:C4" + _SC),
        "que reloj cuenta, su cota de error y el trato de un intervalo que cruza el plazo; orden por t_rec, nunca por "
        "indice",
        "recibos firmados y comprobacion de la cota de error del reloj",
        "ordenar por indice de hoja; un intervalo que cruza el plazo; una marca en formato UTC sin cota de error",
        ("canal_canonico", _R9, "calendario_oficial"), ("reloj", "cota de error", "trato del intervalo"),
        "mientras R0 no fije el reloj, su cota de error y el trato del intervalo"),
    "margen_de_incorporacion": Requisito(
        "margen_de_incorporacion", "condicion",
        "bajo H1, H2, H3 y H5, un punto de control con t_sth medido >= plazo + MMD + incertidumbre del reloj contiene "
        "toda entrada con recibo y t_rec < plazo; con solo la hora de consulta y H4, >= plazo + 2 MMD + incertidumbre",
        ("AE-67:C1" + _SC, "AE-67:C4" + _SC),
        "delta y MMD en R0; compromiso de incorporacion en R9",
        "auditoria de cada recibo con prueba de inclusion",
        "un punto de control reciente fechado sobre una vista antigua incompleta; un envio sin recibo",
        ("canal_canonico", _R9, "reloj_de_recepcion"), ("delta", "MMD del canal"),
        "mientras R0 no fije delta y R9 el compromiso"),
    "revision_completa": Requisito(
        "revision_completa", "condicion",
        "el verificador obtiene todas las entradas hasta un punto de control que cumple el margen, comprueba la "
        "consistencia con los anteriores y que el punto de control corresponde a las entradas obtenidas, y aplica la "
        "politica ante vistas divididas declarada en R0",
        ("AE-67:C2" + _SC, "AE-67:C5" + _SC, "AE-67:C6" + _SC),
        "procedimiento y politica ante vistas divididas",
        "copia completa, pruebas de consistencia y comparacion entre partes independientes",
        "comprobar solo la inclusion de una entrada no ve un conflicto; vista dividida (B3 de AE-66)",
        ("canal_canonico", "margen_de_incorporacion"), ("quien revisa", "con quien compara"),
        "mientras R0 no declare el procedimiento y la politica"),
    "calendario_oficial": Requisito(
        "calendario_oficial", "condicion",
        "un plazo en UTC por (juego, objetivo) derivado de la fuente y de la definicion del plazo declaradas en R0, "
        "con archivo verificable",
        ("ninguno",),
        "fuente, definicion del plazo, zona America/Bogota (UTC-5) y reprogramaciones",
        "archivo por terceros de la fuente oficial",
        "plazo definido tras ver resultados; sorteo reprogramado; confusion de zona (B7 de AE-66)",
        (_R0,), ("fuente", "definicion del plazo", "reprogramaciones"),
        "mientras R0 no fije la fuente y la definicion"),
})

CORRESPONDENCIA_CON_AE66 = MappingProxyType({
    "identidad_autorizada": ("identidad_autorizada",),
    "canal_canonico_exclusivo": ("canal_canonico",),
    "clave_unica_por_objetivo": ("unicidad_por_objetivo",),
    "regla_de_duplicados": ("regla_de_duplicados",),
    "recepcion_antes_del_plazo": ("reloj_de_recepcion", "margen_de_incorporacion"),
    "revision_completa": ("revision_completa",),
    "complemento_K_y_preguntas_abiertas": ("calendario_oficial",),
})
"""Sin renombrar nada en AE-66 ni en AE-67."""

DEPENDENCIAS_NORMATIVAS = MappingProxyType({
    _R0: (_R9, *CONDICIONES_DEL_PROTOCOLO),
})
DEPENDENCIAS_DE_VERIFICACION = MappingProxyType({
    id_: r.verificacion_depende_de for id_, r in {**REQUISITOS_PREVIOS, **CONDICIONES_DEL_PROTOCOLO}.items()})

# ---------------------------------------------------------------------------
# Instantes e hipotesis temporales
# ---------------------------------------------------------------------------

INSTANTES = MappingProxyType({
    "t_rec": "recepcion de nuestra entrada por nuestro canal, segun su recibo (R9)",
    "t_sct": "aceptacion que representa un SCT, solo para entradas de RFC 9162 (certificados)",
    "t_sth": "marca de tiempo de un punto de control",
    "t_consulta": "hora local en que el verificador obtiene un punto de control",
})

_ORIGEN = "requisito_del_canal_sintetico_no_garantia_de_rfc_9162"
HIPOTESIS_TEMPORALES = MappingProxyType({
    "H1": MappingProxyType({"texto": "el canal emite por cada entrada un recibo firmado que vincula su hash canonico "
                                     "con t_rec y promete incorporarla", "origen": _ORIGEN, "estado": "sin_fijar"}),
    "H2": MappingProxyType({"texto": "compromiso verificable: todo punto de control con t_sth >= t_rec + MMD contiene "
                                     "la entrada con recibo; se audita con el recibo", "origen": _ORIGEN,
                            "estado": "sin_fijar"}),
    "H3": MappingProxyType({"texto": "coherencia de cada punto de control: contiene toda entrada incorporada en un "
                                     "instante <= t_sth y ninguna posterior; no se puede fechar un punto reciente sobre "
                                     "una vista antigua incompleta", "origen": _ORIGEN, "estado": "sin_fijar"}),
    "H4": MappingProxyType({"texto": "un punto de control servido tiene como maximo un MMD de antiguedad respecto de "
                                     "t_consulta", "origen": _ORIGEN, "estado": "sin_fijar"}),
    "H5": MappingProxyType({"texto": "relojes con zona explicita, resolucion declarada y una cota declarada y "
                                     "comprobable del error frente a UTC; una marca en formato UTC no prueba exactitud "
                                     "temporal", "origen": _ORIGEN, "estado": "sin_fijar"}),
})

LIMITE_DE_COMPLETITUD = (
    "un punto de control reciente no acredita que el canal recibiera todas las entradas pertinentes: solo cubre las que "
    "tienen recibo; un envio rechazado o censurado sin recibo no aparece en ningun punto de control")

# ---------------------------------------------------------------------------
# Identidad
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntradaFirmada:
    entrada: EntradaBitacora
    firmante: str
    firma: str


def _exigir_zona(instante: datetime, nombre: str) -> None:
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError(f"{nombre} debe ser un instante con zona horaria explicita")


def entradas_admisibles(entradas: Sequence[EntradaFirmada], firma_valida: Callable[[EntradaFirmada], bool],
                        vigencias: Mapping[str, tuple]) -> tuple:
    """Entradas con firmante declarado, vigente en su t_rec y firma valida.
    `firma_valida` se inyecta: el modulo no fija ningun esquema."""
    admisibles = []
    for ef in entradas:
        vigencia = vigencias.get(ef.firmante)
        if vigencia is None:
            continue
        desde, hasta = vigencia
        t_rec = ef.entrada.recibido_en
        if t_rec < desde or (hasta is not None and t_rec >= hasta):
            continue
        if firma_valida(ef):
            admisibles.append(ef)
    return tuple(admisibles)

# ---------------------------------------------------------------------------
# Conflictos y regla de duplicados
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegistroDeConflicto:
    clave: tuple
    clase: str
    hashes: tuple[str, ...]
    tipos: tuple[str, ...]
    total: int
    primera_recepcion: datetime


@dataclass(frozen=True)
class Resolucion:
    clave: tuple
    entrada: EntradaBitacora | None
    efecto: str


def ordenar_por_recepcion(entradas: Sequence[EntradaBitacora]) -> tuple:
    """Orden por t_rec (y hash para desempatar), nunca por indice de hoja."""
    return tuple(sorted(entradas, key=lambda e: (e.recibido_en, e.contenido_hash)))


def _por_clave(vista: Sequence[EntradaBitacora]) -> dict:
    grupos: dict = {}
    for e in vista:
        grupos.setdefault(e.clave, []).append(e)
    return grupos


def registrar_conflictos(vista: Sequence[EntradaBitacora]) -> tuple:
    """Detecta y registra, antes de cualquier regla, cada clave con varias
    entradas: reintento identico (mismo hash canonico) o contenidos
    incompatibles."""
    registro = []
    for clave, entradas in _por_clave(vista).items():
        if len(entradas) < 2:
            continue
        hashes = tuple(sorted({e.contenido_hash for e in entradas}))
        registro.append(RegistroDeConflicto(
            clave, "reintento_identico" if len(hashes) == 1 else "contenidos_incompatibles", hashes,
            tuple(sorted({e.tipo for e in entradas})), len(entradas), min(e.recibido_en for e in entradas)))
    return tuple(registro)


def _primera_recibida(entradas, registro):
    return Resolucion(registro.clave, ordenar_por_recepcion(entradas)[0], "conservar")


def _invalidar_objetivo(entradas, registro):
    return Resolucion(registro.clave, None, "objetivo_invalidado")


def _invalidar_protocolo(entradas, registro):
    return Resolucion(registro.clave, None, "protocolo_invalidado")


REGLAS_DE_DUPLICADOS_CANDIDATAS = MappingProxyType({
    "primera_recibida": _primera_recibida,
    "invalidar_objetivo": _invalidar_objetivo,
    "invalidar_protocolo": _invalidar_protocolo,
})
"""Candidatas sin elegir; ninguna recibe resultados ni puntuaciones."""

REGLA_DE_DUPLICADOS_ELEGIDA = None

_PARAMETROS_DE_REGLA = ("entradas", "registro")


def es_regla_admisible(regla: Callable) -> bool:
    """Una regla solo puede recibir las entradas y el registro del conflicto."""
    return tuple(inspect.signature(regla).parameters) == _PARAMETROS_DE_REGLA


def aplicar_regla(vista: Sequence[EntradaBitacora], nombre: str) -> tuple:
    """Aplica una regla candidata a los conflictos de contenidos
    incompatibles. Los reintentos identicos conservan la primera copia. El
    registro de conflictos se devuelve intacto."""
    regla = REGLAS_DE_DUPLICADOS_CANDIDATAS[nombre]
    registro = registrar_conflictos(vista)
    por_clave = {r.clave: r for r in registro}
    resoluciones = []
    for clave, entradas in _por_clave(vista).items():
        conflicto = por_clave.get(clave)
        if conflicto is None or conflicto.clase == "reintento_identico":
            resoluciones.append(Resolucion(clave, ordenar_por_recepcion(entradas)[0], "conservar"))
        else:
            resoluciones.append(regla(entradas, conflicto))
    return tuple(resoluciones), registro

# ---------------------------------------------------------------------------
# Canal sintetico: recibos y puntos de control (H2 y H3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReciboSintetico:
    hash_entrada: str
    t_rec: datetime


@dataclass(frozen=True)
class PuntoDeControlSintetico:
    t_sth: datetime
    hashes: tuple[str, ...]


def punto_de_control_coherente_sintetico(incorporaciones: Mapping[str, datetime], t_sth: datetime):
    """Punto de control que cumple H3: exactamente las entradas incorporadas
    en un instante <= t_sth."""
    return PuntoDeControlSintetico(t_sth, tuple(sorted(h for h, t in incorporaciones.items() if t <= t_sth)))


def punto_de_control_es_coherente(punto: PuntoDeControlSintetico, incorporaciones: Mapping[str, datetime]) -> bool:
    """H3: detecta un punto de control fechado sobre una vista que no es la de su marca."""
    return set(punto.hashes) == {h for h, t in incorporaciones.items() if t <= punto.t_sth}


def cumple_compromiso_de_incorporacion(punto: PuntoDeControlSintetico, recibos: Sequence[ReciboSintetico],
                                       mmd: timedelta) -> bool:
    """H2: todo recibo con t_rec + MMD <= t_sth debe estar en el punto de control."""
    return all(r.hash_entrada in punto.hashes for r in recibos if r.t_rec + mmd <= punto.t_sth)

# ---------------------------------------------------------------------------
# Reloj: cota de error y resolucion (H5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RelojDeclarado:
    """Cota del error frente a UTC y resolucion. La incertidumbre total es
    su suma (conservadora); sin cota declarada no hay incertidumbre."""
    cota_error: timedelta | None
    resolucion: timedelta

    def __post_init__(self):
        if self.cota_error is not None and self.cota_error < timedelta(0):
            raise ValueError("la cota de error no puede ser negativa")
        if self.resolucion < timedelta(0):
            raise ValueError("la resolucion no puede ser negativa")

    def incertidumbre(self) -> timedelta | None:
        return None if self.cota_error is None else self.cota_error + self.resolucion


RESULTADOS_RELOJ = ("anterior_con_margen_de_reloj", "no_concluyente_por_error_de_reloj",
                    "posterior_con_margen_de_reloj", "cota_de_error_sin_declarar_pendiente")


def comparar_con_plazo(marca: datetime, plazo: datetime, reloj: RelojDeclarado) -> str:
    """Compara una marca con el plazo teniendo en cuenta la incertidumbre del
    reloj; una marca con zona UTC pero sin cota de error queda pendiente."""
    _exigir_zona(marca, "marca")
    _exigir_zona(plazo, "plazo")
    u = reloj.incertidumbre()
    if u is None:
        return "cota_de_error_sin_declarar_pendiente"
    if marca + u < plazo:
        return "anterior_con_margen_de_reloj"
    if marca - u >= plazo:
        return "posterior_con_margen_de_reloj"
    return "no_concluyente_por_error_de_reloj"


@dataclass(frozen=True)
class UmbralCondicionado:
    instante: datetime | None
    hipotesis: tuple[str, ...]
    estado: str


def umbral_de_punto_de_control(plazo: datetime, mmd: timedelta, referencia: str,
                               reloj: RelojDeclarado) -> UmbralCondicionado:
    """Umbral medido a partir del cual un punto de control cubre las entradas
    con recibo y t_rec < plazo, solo bajo las hipotesis devueltas; la
    incertidumbre es la del reloj con que se mide la referencia."""
    _exigir_zona(plazo, "plazo")
    if referencia == "marca_de_punto_de_control":
        base, hipotesis = plazo + mmd, ("H1", "H2", "H3", "H5")
    elif referencia == "hora_de_consulta":
        base, hipotesis = plazo + 2 * mmd, ("H1", "H2", "H3", "H4", "H5")
    else:
        raise ValueError(f"referencia desconocida: {referencia!r}")
    u = reloj.incertidumbre()
    if u is None:
        return UmbralCondicionado(None, hipotesis, "cota_de_error_sin_declarar_pendiente")
    return UmbralCondicionado(base + u, hipotesis, "umbral_condicionado_a_hipotesis_sin_fijar")

# ---------------------------------------------------------------------------
# Vias de ausencia en escenarios hipoteticos
# ---------------------------------------------------------------------------

REQUISITOS_DE_VIA = MappingProxyType({
    "via_1_omision_declarada": (_R0, _R9, *CONDICIONES_DEL_PROTOCOLO, "politica_de_vistas_divididas"),
    "via_2_ausencia_inferida": (_R0, _R9, "identidad_autorizada", "canal_canonico", "reloj_de_recepcion",
                                "margen_de_incorporacion", "revision_completa", "calendario_oficial",
                                "politica_de_vistas_divididas", "tratamiento_de_envios_sin_recibo"),
})

RESULTADOS_DE_VIA = ("pendiente", "hipotesis_completa_sin_evidencia_operativa_ni_resolucion_de_vistas_divididas",
                     "hipotesis_completa_pendiente_de_envios_sin_recibo_y_vistas_divididas")

_RESULTADO_COMPLETO = MappingProxyType({
    "via_1_omision_declarada": RESULTADOS_DE_VIA[1],
    "via_2_ausencia_inferida": RESULTADOS_DE_VIA[2],
})


def estado_hipotetico_de_via(via: str, escenario: Mapping[str, bool]) -> str:
    """Estado de una via en un escenario de prueba (que requisitos se suponen
    fijados). No lee ni modifica los estados reales, que siguen sin_fijar."""
    requisitos = REQUISITOS_DE_VIA[via]
    desconocidos = set(escenario) - set(requisitos)
    if desconocidos:
        raise ValueError(f"requisitos desconocidos en el escenario: {sorted(desconocidos)}")
    if all(escenario.get(r, False) for r in requisitos):
        return _RESULTADO_COMPLETO[via]
    return "pendiente"
