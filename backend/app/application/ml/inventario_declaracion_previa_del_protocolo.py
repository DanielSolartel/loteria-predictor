"""
Inventario verificable del contenido de R0 frente al formato del protocolo
de AE-52 -Etapa AE-69, validada (solo como inventario preparatorio y sus
pruebas; los once elementos siguen pendientes y R0, R9 y las ocho
condiciones siguen sin fijar).

AE-68 dejo R0 (`declaracion_previa_del_protocolo`) como unica raiz de
confianza y dijo que es el protocolo de AE-52 y que declara claves, canal,
clave de unicidad, regla de duplicados, reloj, margen, revision completa,
politica ante vistas divididas, calendario y plazo. El formato vigente de
AE-52 no admite ninguna de esas declaraciones: ni como campo (conjunto
exacto de claves) ni como pendiente (solo sus siete identificadores). Este
modulo inventaria los once elementos del contenido de R0, que alimentan las
ocho condiciones de AE-68 y R9, y ofrece un comprobador sintetico de
completitud en el que cada elemento debe tratarse de forma explicita.

Separa el contenido de R0 de su autenticacion: los tres elementos de
`AUTENTICACION_DE_R0` siguen pendientes. `completa_sintetica_sin_autenticar`
solo indica completitud estructural de los once elementos; no acredita
suficiencia de sus valores, autenticacion, fijacion de R0 ni cumplimiento
de ninguna condicion. Lo que procede de RFC 9162 cubre certificados y
precertificados (AE-67), no nuestras entradas.

No se decide la ubicacion ni el formato de la declaracion, ni mecanismo,
esquema de firma, regla o valor alguno. R0, R9 y las ocho condiciones
siguen `sin_fijar`; AE-52 y AE-63 a AE-68 no cambian. El expediente sigue en
`expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`. Puro: sin red,
relojes o servicios reales, archivos, datos reales ni PostgreSQL.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from app.application.ml.registro_prospectivo import hash_entrada, leer_entrada, serializar_entrada

_R9 = "puente_entrada_canal"
_SC = " solo_certificados"
_BASE = "@9cd222c"
_RP = "backend/app/application/ml/registro_prospectivo.py"
_PRUEBAS = "prueba:"


@dataclass(frozen=True)
class ElementoDeR0:
    id: str
    definicion: str
    alimenta: tuple[str, ...]
    situacion_en_ae52: str
    estandar: tuple[str, ...]
    evidencia_que_lo_resolveria: str
    criterio_para_mantener_pendiente: str
    estado: str = "pendiente"


SITUACIONES_EN_AE52 = ("sin_campo_en_el_protocolo_ae52", "componentes_en_prediccion_sin_declaracion_de_clave")

RELACION_CON_AE52 = (
    "el protocolo de AE-52 exige un conjunto exacto de claves y rechaza cualquier otra, tambien en protocolos "
    "sinteticos; su lista de pendientes solo admite los siete identificadores de AE-52. Por tanto, hoy ningun "
    "elemento del contenido de R0 puede figurar en el protocolo ni como valor ni como pendiente. AE-69 no modifica "
    "ese formato ni elige donde vivira la declaracion; solo reutiliza el serializador canonico de AE-52")

_SIN = SITUACIONES_EN_AE52[0]


def _e(id_, definicion, alimenta, estandar, evidencia, criterio, situacion=_SIN):
    return ElementoDeR0(id_, definicion, alimenta, situacion, estandar, evidencia, criterio)


ELEMENTOS_DE_R0 = MappingProxyType({e.id: e for e in (
    _e("conjunto_de_claves_y_revocacion",
       "claves con las que se verifican las entradas y su politica de revocacion",
       ("identidad_autorizada",), ("AE-67:T4", "AE-67:T5", "AE-67:C7" + _SC),
       "declaracion en R0 con su autenticacion completa, mas registro de custodia y revocaciones",
       "mientras R0 no declare el conjunto de claves y su revocacion"),
    _e("identidad_del_canal",
       "identificador del canal y clave o compromiso publico con que se reconoce",
       ("canal_canonico",), ("AE-67:T6", "AE-67:C5" + _SC),
       "declaracion en R0 con su autenticacion completa y operacion comprobable del canal",
       "mientras R0 no declare el canal"),
    _e("composicion_de_la_clave_de_unicidad",
       "campos que forman la clave por objetivo; la propuesta de AE-66 es (protocolo_hash, juego, objetivo)",
       ("unicidad_por_objetivo",), ("AE-67:C3" + _SC, "AE-67:C7" + _SC),
       "declaracion en R0 con su autenticacion completa de la clave; los componentes ya existen en las "
       "entradas de prediccion",
       "mientras R0 no declare la composicion de la clave",
       situacion=SITUACIONES_EN_AE52[1]),
    _e("regla_de_duplicados",
       "regla determinista, tras detectar y registrar conflictos, que solo usa hash, tipo, firmante y t_rec",
       ("regla_de_duplicados",), ("AE-67:C7" + _SC,),
       "declaracion en R0 con su autenticacion completa de una de las candidatas u otra regla admisible",
       "mientras R0 no declare la regla"),
    _e("reloj_zona_resolucion_cota_y_trato_del_intervalo",
       "reloj de recepcion con zona, resolucion, cota declarada del error frente a UTC y trato de un intervalo "
       "que cruza el plazo",
       ("reloj_de_recepcion",), ("AE-67:T1", "AE-67:T2", "AE-67:C4" + _SC),
       "declaracion en R0 con su autenticacion completa, mas recibos y comprobacion de la cota",
       "mientras R0 no declare el reloj, su cota y el trato del intervalo"),
    _e("margen_delta_y_mmd",
       "margen delta y MMD del canal que se designe",
       ("margen_de_incorporacion",), ("AE-67:C1" + _SC, "AE-67:C4" + _SC),
       "declaracion en R0 con su autenticacion completa y auditoria de recibos con pruebas de inclusion",
       "mientras R0 no declare delta y MMD"),
    _e("procedimiento_de_revision_completa",
       "como se obtienen todas las entradas hasta un punto de control que cumple el margen y como se comprueba "
       "su consistencia",
       ("revision_completa",), ("AE-67:C2" + _SC, "AE-67:C5" + _SC, "AE-67:C6" + _SC),
       "declaracion en R0 con su autenticacion completa, copia completa y pruebas de consistencia",
       "mientras R0 no declare el procedimiento"),
    _e("politica_ante_vistas_divididas",
       "con quien se comparan los puntos de control y que se hace si difieren",
       ("revision_completa",), ("AE-67:C5" + _SC, "AE-67:C6" + _SC),
       "declaracion en R0 con su autenticacion completa y comparacion entre partes",
       "mientras R0 no declare la politica"),
    _e("fuente_del_calendario",
       "fuente del calendario oficial de sorteos y de sus reprogramaciones",
       ("calendario_oficial",), ("ninguno",),
       "declaracion en R0 con su autenticacion completa y archivo por terceros",
       "mientras R0 no declare la fuente"),
    _e("definicion_del_plazo",
       "como se deriva el plazo en UTC por (juego, objetivo) a partir de la fuente",
       ("calendario_oficial",), ("ninguno",),
       "declaracion en R0 con su autenticacion completa; su relacion con el corte temporal de AE-52 sigue abierta",
       "mientras R0 no declare la definicion"),
    _e("formato_de_entrada_y_recibo",
       "como se codifica una entrada del protocolo en el canal que se designe y que recibo firmado emite ese canal",
       (_R9,), ("AE-67:C4" + _SC, "AE-67:C7" + _SC),
       "declaracion en R0 con su autenticacion completa y recibos emitidos por el canal; un registro de "
       "certificados no acepta nuestras entradas",
       "mientras no exista un canal con recibos verificables para nuestro formato"),
)})
"""Los once elementos del contenido de R0; todos `pendiente`."""

ESTADO_ACTUAL_DE_R0 = MappingProxyType({id_: "pendiente" for id_ in ELEMENTOS_DE_R0})

CORRESPONDENCIA_CON_PENDIENTES_AE52 = MappingProxyType({
    "mecanismo_de_sellado_temporal_externo": MappingProxyType({
        "corresponde_a": "autenticacion_de_r0:sello_externo_anterior_al_corte",
        "texto": "toca a la autenticacion de R0 (elemento a de AE-68), no a su contenido"}),
    "corte_temporal_por_juego": MappingProxyType({
        "corresponde_a": "relacionado_con_definicion_del_plazo_sin_identificar",
        "texto": "el corte de AE-52 y la definicion del plazo estan relacionados, pero no se identifican"}),
})

PREGUNTAS_ABIERTAS_AE69 = MappingProxyType({
    "ubicacion_de_la_declaracion": MappingProxyType({
        "texto": "donde viviria el contenido de R0: una version nueva del formato de AE-52, un documento aparte "
                 "referenciado por hash u otra opcion; sin decidir",
        "estado": "sin_respuesta"}),
    "definicion_del_plazo_frente_al_corte": MappingProxyType({
        "texto": "si la definicion del plazo y el corte temporal por juego de AE-52 son decisiones distintas o "
                 "una depende de la otra",
        "estado": "sin_respuesta"}),
    "expresion_de_pendientes_de_r0_en_ae52": MappingProxyType({
        "texto": "como expresar un elemento pendiente de R0 sin romper la regla de protocolo de AE-52",
        "estado": "sin_respuesta"}),
})

ESTADOS_DE_ELEMENTO = ("pendiente", "declarado_sintetico")
RESULTADOS_DECLARACION = ("incompleta", "todos_pendientes", "parcial", "completa_sintetica_sin_autenticar")

ALCANCE_DE_LA_COMPLETITUD = (
    "completa_sintetica_sin_autenticar solo indica completitud estructural de los once elementos: no acredita "
    "suficiencia de sus valores, autenticacion, fijacion de R0 ni cumplimiento de ninguna condicion. Los valores "
    "de una declaracion sintetica son datos de prueba, no propuestas ni decisiones")

TRATAMIENTO_DE_VALORES_VACIOS = (
    "un valor vacio o nulo no es una declaracion sustantiva: None, un texto vacio o solo con espacios, una lista o "
    "un objeto vacios, o cualquiera de ellos anidado, hacen la declaracion incompleta y no se hashea. Los "
    "enteros y booleanos, incluidos 0 y false, cuentan como valores")

_PROFUNDIDAD_MAXIMA = 16


class DeclaracionSinteticaInvalidaError(ValueError):
    """La declaracion sintetica es incompleta o su forma no es admisible."""


def _motivo_de_valor(valor, profundidad: int = 0) -> str | None:
    """Motivo por el que un valor no es admisible o no es sustantivo; None si lo es."""
    if profundidad > _PROFUNDIDAD_MAXIMA:
        return "valor_demasiado_profundo"
    if valor is None:
        return "valor_vacio_o_nulo"
    if isinstance(valor, bool) or type(valor) is int:
        return None
    if type(valor) is str:
        return None if valor.strip() else "valor_vacio_o_nulo"
    if type(valor) is list:
        if not valor:
            return "valor_vacio_o_nulo"
        for v in valor:
            motivo = _motivo_de_valor(v, profundidad + 1)
            if motivo:
                return motivo
        return None
    if type(valor) is dict:
        if not valor:
            return "valor_vacio_o_nulo"
        if not all(type(k) is str for k in valor):
            return "clave_no_textual_en_valor"
        for v in valor.values():
            motivo = _motivo_de_valor(v, profundidad + 1)
            if motivo:
                return motivo
        return None
    return "tipo_de_valor_no_admitido"


def motivos_de_incompletitud(declaracion) -> tuple[str, ...]:
    """Motivos, ordenados, por los que una declaracion sintetica es
    incompleta; tupla vacia si no lo es. Nunca lanza excepciones."""
    if type(declaracion) is not dict:
        return ("no_es_un_objeto",)
    motivos = []
    for clave in declaracion:
        if type(clave) is not str:
            motivos.append(f"clave_no_textual:{clave!r}")
        elif clave not in ELEMENTOS_DE_R0:
            motivos.append(f"sobra:{clave}")
    for id_ in ELEMENTOS_DE_R0:
        if id_ not in declaracion:
            motivos.append(f"falta:{id_}")
            continue
        elemento = declaracion[id_]
        if type(elemento) is not dict:
            motivos.append(f"forma_invalida:{id_}")
            continue
        estado = elemento.get("estado")
        if estado == "pendiente" and set(elemento) == {"estado"}:
            continue
        if estado == "declarado_sintetico" and set(elemento) == {"estado", "valor"}:
            motivo = _motivo_de_valor(elemento["valor"])
            if motivo:
                motivos.append(f"{motivo}:{id_}")
            continue
        if estado not in ESTADOS_DE_ELEMENTO:
            motivos.append(f"estado_desconocido:{id_}")
        else:
            motivos.append(f"forma_invalida:{id_}")
    return tuple(sorted(motivos))


def comprobar_declaracion_sintetica(declaracion) -> str:
    """Completitud estructural de una declaracion sintetica de prueba.
    `completa_sintetica_sin_autenticar` no acredita suficiencia de los
    valores, autenticacion, fijacion de R0 ni cumplimiento de ninguna
    condicion (`ALCANCE_DE_LA_COMPLETITUD`). Nunca lanza excepciones."""
    if motivos_de_incompletitud(declaracion):
        return "incompleta"
    estados = {elemento["estado"] for elemento in declaracion.values()}
    if estados == {"pendiente"}:
        return "todos_pendientes"
    if estados == {"declarado_sintetico"}:
        return "completa_sintetica_sin_autenticar"
    return "parcial"


def hash_de_declaracion_sintetica(declaracion) -> str:
    """SHA-256 del JSON canonico de AE-52 de una declaracion sintetica no
    incompleta. Una declaracion incompleta no se hashea. No es una entrada de
    AE-52 ni pasa por `validar_registro`."""
    motivos = motivos_de_incompletitud(declaracion)
    if motivos:
        raise DeclaracionSinteticaInvalidaError(f"declaracion incompleta: {', '.join(motivos)}")
    contenido = serializar_entrada(declaracion)
    if leer_entrada(contenido) != declaracion:
        raise DeclaracionSinteticaInvalidaError("la serializacion canonica no reproduce la declaracion")
    return hash_entrada(contenido)


# ---------------------------------------------------------------------------
# Clasificacion de afirmaciones
# ---------------------------------------------------------------------------

CLASES_DE_AFIRMACION = ("hecho_observado_en_codigo", "hecho_citado_de_fuente", "derivacion_propia",
                        "hipotesis_de_aplicacion")

_ESTADO_POR_CLASE = MappingProxyType({
    "hecho_observado_en_codigo": "observado_en_pruebas", "hecho_citado_de_fuente": "citado_de_ae67",
    "derivacion_propia": "derivado", "hipotesis_de_aplicacion": "pendiente"})


@dataclass(frozen=True)
class AfirmacionAE69:
    id: str
    texto: str
    clase: str
    procedencia: tuple[str, ...]
    evidencia: str
    estado: str


def _a(id_, texto, clase, procedencia, evidencia):
    return AfirmacionAE69(id_, texto, clase, procedencia, evidencia, _ESTADO_POR_CLASE[clase])


_T = "backend/tests/unit/ml/test_inventario_declaracion_previa_del_protocolo.py"

CLASIFICACION_DE_AFIRMACIONES = (
    _a("A1", "un protocolo sintetico de AE-52 con una clave adicional se rechaza al validar el registro",
       "hecho_observado_en_codigo",
       (f"{_RP}:_validar_protocolo{_BASE}", f"{_RP}:validar_registro{_BASE}",
        _PRUEBAS + "test_g3_a1_protocolo_sintetico_con_clave_adicional_se_rechaza"),
       f"integracion G3 en {_T}"),
    _a("A2", "un identificador de R0 en la lista de pendientes se rechaza, tambien con sintetico=True",
       "hecho_observado_en_codigo",
       (f"{_RP}:_validar_protocolo{_BASE}", f"{_RP}:construir_protocolo{_BASE}",
        _PRUEBAS + "test_g3_a2_identificador_de_r0_en_pendientes_se_rechaza_tambien_sintetico"),
       f"integracion G3 en {_T}"),
    _a("A3", "los once elementos y los siete pendientes de AE-52 son disjuntos; el pendiente del mecanismo de "
             "sellado corresponde a la autenticacion de R0, no a su contenido",
       "derivacion_propia",
       ("premisa:registro_prospectivo.PENDIENTES_BORRADOR_AE52",
        "premisa:especificacion_condiciones_del_protocolo.AUTENTICACION_DE_R0",
        "premisa:inventario_declaracion_previa_del_protocolo.ELEMENTOS_DE_R0"),
       "prueba G1 de disjuncion y correspondencia"),
    _a("A4", "una prediccion sintetica de AE-52 contiene protocolo_hash, codigo_juego y sorteo_objetivo",
       "hecho_observado_en_codigo",
       (f"{_RP}:nueva_prediccion{_BASE}",
        _PRUEBAS + "test_g3_a4_prediccion_sintetica_contiene_los_componentes_de_la_clave"),
       f"integracion G3 en {_T}"),
    _a("A5", "que esos tres campos formen la clave de unicidad es la propuesta de AE-66, no una declaracion de R0",
       "hipotesis_de_aplicacion",
       ("backend/app/application/ml/propuesta_evidencia_temporal_externa.py:"
        f"CONDICIONES_PENDIENTES_DEL_PROTOCOLO[clave_unica_por_objetivo]{_BASE}",),
       "la resolveria una declaracion de R0 con su autenticacion completa"),
    _a("A6", "cada una de las ocho condiciones y R9 recibe al menos un elemento, y los destinos se limitan a ellas",
       "derivacion_propia",
       ("premisa:especificacion_condiciones_del_protocolo.CONDICIONES_DEL_PROTOCOLO",
        "premisa:especificacion_condiciones_del_protocolo.REQUISITOS_PREVIOS",
        "premisa:especificacion_condiciones_del_protocolo.DEPENDENCIAS_NORMATIVAS"),
       "prueba G1 de cobertura"),
    _a("A7", "un contenido completo no autentica R0: la autenticacion exige sus tres elementos, todos pendientes",
       "derivacion_propia",
       ("premisa:especificacion_condiciones_del_protocolo.AUTENTICACION_DE_R0", "premisa:AE-67:T6"),
       "prueba G1 con una declaracion sintetica completa"),
    _a("A8", "RFC 9162 describe registros de certificados y precertificados; sus garantias no se trasladan a "
             "nuestras entradas (alcance registrado en AE-67 y recogido en AE-68)",
       "hecho_citado_de_fuente",
       tuple(f"AE-67:C{i}" for i in range(1, 8)),
       "referencias de pagina que registra AE-67 en AFIRMACIONES_RFC_9162; sin cita nueva"),
    _a("A9", "la definicion del plazo y el corte temporal por juego de AE-52 estan relacionados, pero no se "
             "identifican",
       "hipotesis_de_aplicacion",
       (f"{_RP}:PENDIENTES_BORRADOR_AE52{_BASE}",
        "backend/app/application/ml/especificacion_condiciones_del_protocolo.py:"
        f"CONDICIONES_DEL_PROTOCOLO[calendario_oficial]{_BASE}"),
       "la resolveria una decision del operador en una etapa posterior"),
    _a("A10", "en los ejemplos probados, cambiar un solo elemento cambia el hash; no se afirma ninguna propiedad "
              "universal contra colisiones",
       "hecho_observado_en_codigo",
       (f"{_RP}:serializar_entrada{_BASE}", f"{_RP}:hash_entrada{_BASE}",
        _PRUEBAS + "test_g1_hash_por_serializacion_de_ae52_en_ejemplos_concretos"),
       f"prueba G1 sobre ejemplos concretos en {_T}"),
    _a("A11", "el serializador de AE-52 no comprueba el tipo de nivel superior, convierte claves enteras en texto "
              "y tuplas en listas, y rechaza nan, conjuntos, bytes y MappingProxyType",
       "hecho_observado_en_codigo",
       (f"{_RP}:serializar_entrada{_BASE}",
        _PRUEBAS + "test_g3_a11_comportamiento_observado_del_serializador_de_ae52"),
       f"integracion G3 en {_T}"),
)
