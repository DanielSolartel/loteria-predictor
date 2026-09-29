"""
Comparacion verificable de las alternativas de declaracion previa R0 y de la
distincion entre «sin fijar», «ausente» y «fijado» -Etapa AE-71, validada
(solo como analisis preparatorio de alternativas y sus pruebas; sin elegir
topologia ni representacion, y R0, R9 y las ocho condiciones siguen sin
fijar).

AE-69 dejo tres preguntas abiertas (ubicacion de la declaracion,
representacion de sus pendientes y regla de vinculo) y AE-70 registro cuatro
topologias de vinculo. Este modulo compara esas topologias con fichas: que
habria que fijar antes del plazo, que bytes se verifican, que cambios
exigirian, que puede comprobar un tercero y que no queda demostrado. Tambien
examina si la representacion de AE-69 distingue de forma verificable «sin
fijar», «ausente» y «fijado».

Se separan tres planos: la dependencia entre bytes (un protocolo que contiene
H(D) depende de los bytes de D), una evidencia temporal sobre esos bytes y la
fijacion autenticada de R0. Ni S5 ni un hash son prueba temporal. «Fijado» no
es representable en los bytes sinteticos de AE-69 y exige cuatro componentes
no acreditados. El segundo manifiesto es solo un contraejemplo de un modelo
sintetico.

No se implementa ninguna topologia ni representacion, no se responden las
preguntas de AE-69 y D1-D9 siguen sin decidir; AE-52 y AE-63 a AE-70 no
cambian. R0, R9 y las ocho condiciones siguen `sin_fijar`. El expediente
sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`. Puro:
sin red, relojes o servicios reales, archivos, datos reales ni PostgreSQL.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from types import MappingProxyType

from app.application.ml.inventario_declaracion_previa_del_protocolo import ELEMENTOS_DE_R0, motivos_de_incompletitud
from app.application.ml.vinculo_declaracion_previa_con_protocolo import (
    TOPOLOGIAS_DE_VINCULO,
    ReglaDeVinculo,
    hash_designado,
)

_BASE = "@8137f93"
_RP = "backend/app/application/ml/registro_prospectivo.py"
_IV = "backend/app/application/ml/inventario_declaracion_previa_del_protocolo.py"
_VV = "backend/app/application/ml/vinculo_declaracion_previa_con_protocolo.py"
_T = "backend/tests/unit/ml/test_analisis_alternativas_de_declaracion_previa.py"
_P = "prueba:"

_NUEVO = "directo_en_nuevo_esquema"
_CAMPO = "directo_en_campo_existente_no_previsto"
_INVERSO = "inverso_desde_la_declaracion"
_MANIFIESTO = "manifiesto_externo"

# ---------------------------------------------------------------------------
# Planos, supuestos e hipotesis
# ---------------------------------------------------------------------------

SEPARACION_DE_PLANOS = (
    "se distinguen tres planos: la dependencia entre bytes (un protocolo que contiene H(D) depende de los bytes de "
    "D, comprobable por un tercero que tenga ambos); una evidencia temporal sobre esos bytes (sello o recepcion "
    "externa con reloj y margen), pendiente; y la fijacion autenticada de R0, pendiente. El primero no implica los "
    "otros dos")

SUPUESTOS_ADICIONALES_AE71 = MappingProxyType({
    "S5": MappingProxyType({
        "texto": "resistencia a preimagen y a segunda preimagen de SHA-256, supuesta y no verificada; solo sostiene "
                 "que no es factible presentar despues otra declaracion distinta con el mismo hash designado; no es "
                 "prueba temporal: no dice cuando existio, se publico ni se recibio la declaracion",
        "estado": "supuesto_no_verificado"}),
})

HIPOTESIS_PARA_CRONOLOGIA = MappingProxyType({
    "H-a": MappingProxyType({
        "texto": "un sello o recepcion externa del protocolo, o de H(D), con instante previo al plazo, con reloj y "
                 "margen declarados (AE-68 reloj_de_recepcion y margen_de_incorporacion)",
        "estado": "pendiente"}),
    "H-b": MappingProxyType({
        "texto": "la autenticacion de la declaracion (AUTENTICACION_DE_R0 de AE-68)",
        "estado": "pendiente"}),
    "H-c": MappingProxyType({
        "texto": "la definicion del plazo y del corte (AE-68 calendario_oficial; D8)",
        "estado": "pendiente"}),
    "H-d": MappingProxyType({
        "texto": "S5, supuesto no verificado",
        "estado": "pendiente"}),
})

# ---------------------------------------------------------------------------
# Distincion de estados
# ---------------------------------------------------------------------------

COMPONENTES_DE_FIJADO = MappingProxyType({
    "F-1": MappingProxyType({"texto": "integridad y autenticacion de la declaracion",
                             "procedencia": "AE-68 AUTENTICACION_DE_R0", "estado": "no_acreditado"}),
    "F-2": MappingProxyType({"texto": "regla de vinculo establecida por el operador",
                             "procedencia": "D3, D4", "estado": "no_acreditado"}),
    "F-3": MappingProxyType({"texto": "recepcion con instante previo al plazo, con reloj, margen y canal",
                             "procedencia": "AE-68 reloj, margen y canal; H-a", "estado": "no_acreditado"}),
    "F-4": MappingProxyType({"texto": "definicion del corte y del plazo",
                             "procedencia": "D8; AE-68 calendario_oficial", "estado": "no_acreditado"}),
})

DISTINCION_DE_ESTADOS = MappingProxyType({
    "sin_fijar": MappingProxyType({"representacion": "{\"estado\": \"pendiente\"} explicito",
                                   "bytes": "hasheable"}),
    "ausente": MappingProxyType({"representacion": "clave omitida en la declaracion",
                                 "bytes": "incompleta_no_hasheable"}),
    "declarado_sintetico": MappingProxyType({"representacion": "estado declarado_sintetico con valor sustantivo",
                                             "bytes": "hasheable"}),
    "fijado": MappingProxyType({"representacion": "no representable en los bytes sinteticos de AE-69; exige los "
                                                  "cuatro componentes de COMPONENTES_DE_FIJADO",
                                "bytes": "no_representable_en_los_bytes_de_ae69",
                                "exige": ("F-1", "F-2", "F-3", "F-4")}),
})

LAGUNAS_DE_DISTINCION = MappingProxyType({
    "L1": MappingProxyType({"texto": "un texto marcador dentro de valor, como pendiente o TBD, cuenta como declarado; "
                                     "la distincion la lleva solo el campo estado"}),
    "L2": MappingProxyType({"texto": "AE-69 no tiene un estado para fijado; declarado no equivale a fijado"}),
    "L3": MappingProxyType({"texto": "AE-69 no comprueba la estructura interna de cada valor, de modo que un valor "
                                     "sustantivo puede estar incompleto; la suficiencia no se demuestra"}),
})

ESTADOS_VERIFICABLES = ("sin_fijar_explicito", "ausente", "declarado_sintetico", "forma_no_admitida")

# ---------------------------------------------------------------------------
# Decisiones del operador
# ---------------------------------------------------------------------------

DECISIONES_DEL_OPERADOR_AE71 = MappingProxyType({id_: MappingProxyType({"texto": texto, "estado": "sin_decidir"})
                                                 for id_, texto in (
    ("D1", "topologia de vinculo"),
    ("D2", "representacion de los pendientes"),
    ("D3", "campo o ruta que designa el hash de la declaracion"),
    ("D4", "definicion del esquema o de la regla y su correspondencia con la version incluida en los bytes"),
    ("D5", "envoltorio de la declaracion para el vinculo inverso"),
    ("D6", "formato, publicacion y autoridad del manifiesto"),
    ("D7", "si se admiten pendientes al registrar el protocolo"),
    ("D8", "plazo frente a corte (pregunta abierta de AE-69)"),
    ("D9", "si se rechazan textos marcadores dentro de valor"),
)})

DEPENDENCIAS_QUE_IMPIDEN_IMPLEMENTAR = MappingProxyType({
    _NUEVO: ("D1", "D2", "D4", "D7", "D8"),
    _CAMPO: ("D1", "D2", "D3", "D4", "D7", "D8"),
    _INVERSO: ("D1", "D2", "D5", "D7", "D8"),
    _MANIFIESTO: ("D1", "D2", "D6", "D7", "D8"),
})

# ---------------------------------------------------------------------------
# Dependencia entre bytes (sin cronologia)
# ---------------------------------------------------------------------------

RELACIONES_DE_BYTES = ("protocolo_depende_de_declaracion", "prediccion_depende_de_protocolo",
                       "declaracion_depende_de_protocolo", "manifiesto_depende_de_ambos",
                       "protocolo_no_depende_de_declaracion")
MARCA_SIN_CRONOLOGIA = "sin_cronologia_acreditada"

_DIRECTA = ("protocolo_depende_de_declaracion", "prediccion_depende_de_protocolo", MARCA_SIN_CRONOLOGIA)

# ---------------------------------------------------------------------------
# Fichas por topologia
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FichaDeTopologia:
    topologia: str
    datos_a_fijar_antes_del_plazo: tuple[str, ...]
    bytes_verificados: tuple[str, ...]
    cambios_de_esquema_y_pruebas: tuple[str, ...]
    comprobable_por_un_tercero: tuple[str, ...]
    no_demostrado: tuple[str, ...]
    dependencia_de_bytes: tuple[str, ...]
    identificacion_de_la_regla: str
    consecuencia_de_cambiar_la_declaracion: MappingProxyType
    decisiones_del_operador: tuple[str, ...]


_NO_DEMOSTRADO_COMUN = (
    "cronologia: cuando existio, se publico o se recibio la declaracion",
    "autenticacion de la declaracion y de R0",
    "unicidad del protocolo frente a protocolos alternativos (AE-67 T6)",
    "suficiencia de los valores declarados",
    "completitud de las predicciones",
)
_FIJAR_COMUN = ("los componentes F-1 a F-4 de COMPONENTES_DE_FIJADO",)
_OTRO_PROTOCOLO = MappingProxyType({
    "resultado": "otro_protocolo",
    "texto": "cambiar la declaracion vinculada cambia su hash y, para conservar el vinculo, exige otro protocolo; "
             "AE-52 no admite dos protocolos en el mismo registro, asi que hace falta otro registro"})

FICHAS_POR_TOPOLOGIA = MappingProxyType({
    _NUEVO: FichaDeTopologia(
        _NUEVO,
        ("la declaracion (once elementos) y su hash", "el protocolo del esquema nuevo con ese hash",
         "el registro del protocolo", *_FIJAR_COMUN),
        ("bytes canonicos del protocolo, con su version de esquema", "bytes canonicos de la declaracion",
         "protocolo_hash de cada prediccion"),
        ("version nueva de ESQUEMA_ENTRADA", "claves y comprobacion del protocolo de AE-52",
         "script y pruebas de AE-52"),
        ("que el hash de la declaracion coincide con el campo del protocolo, bajo S1 a S3",
         "que cada prediccion apunta al protocolo"),
        _NO_DEMOSTRADO_COMUN,
        _DIRECTA,
        "la version incluida en los bytes puede identificar la regla si D4 fija la definicion del esquema y su "
        "correspondencia con esa version; los bytes no contienen por si solos toda la semantica",
        _OTRO_PROTOCOLO,
        ("D1", "D2", "D4", "D7", "D8")),
    _CAMPO: FichaDeTopologia(
        _CAMPO,
        ("la declaracion y su hash", "el protocolo con ese hash en estrategia.parametros",
         "el registro del protocolo", "el nombre de la clave (D3)", *_FIJAR_COMUN),
        ("bytes canonicos del protocolo", "bytes canonicos de la declaracion", "protocolo_hash de cada prediccion"),
        ("ninguno en el codigo de AE-52", "si en la semantica de estrategia.parametros (AE-70 B13)"),
        ("que el hash de la declaracion coincide con el campo, bajo S1 a S3, si conoce la regla",
         "que cada prediccion apunta al protocolo"),
        (*_NO_DEMOSTRADO_COMUN, "ambiguedad de la regla: otra ruta puede designar otro hash (AE-70 S3)"),
        _DIRECTA,
        "regla externa a los bytes (S3): el formato no identifica que clave de parametros designa la declaracion",
        _OTRO_PROTOCOLO,
        ("D1", "D2", "D3", "D4", "D7", "D8")),
    _INVERSO: FichaDeTopologia(
        _INVERSO,
        ("el protocolo y su registro", "la declaracion con el protocolo_hash, en un envoltorio (D5)",
         *_FIJAR_COMUN),
        ("bytes canonicos de la declaracion", "bytes canonicos del protocolo"),
        ("envoltorio para la declaracion, porque AE-69 exige exactamente once claves",),
        ("que la declaracion cita el protocolo",),
        (*_NO_DEMOSTRADO_COMUN, "designacion unica: dos declaraciones pueden citar el mismo protocolo",
         "nada en los bytes impide construir la declaracion despues de las predicciones"),
        ("declaracion_depende_de_protocolo", "protocolo_no_depende_de_declaracion",
         "prediccion_depende_de_protocolo", MARCA_SIN_CRONOLOGIA),
        "no aplica: los bytes del protocolo no designan ninguna declaracion",
        MappingProxyType({
            "resultado": "mismo_protocolo_declaraciones_coexisten",
            "texto": "el protocolo no cambia; la nueva declaracion cita el mismo protocolo_hash y coexiste con la "
                     "anterior (AE-70 K2)"}),
        ("D1", "D2", "D5", "D7", "D8")),
    _MANIFIESTO: FichaDeTopologia(
        _MANIFIESTO,
        ("el protocolo y su registro", "la declaracion", "el manifiesto (D6)", "la unicidad del manifiesto (S4)",
         *_FIJAR_COMUN),
        ("bytes del manifiesto", "bytes canonicos de la declaracion", "bytes canonicos del protocolo"),
        ("formato, publicacion y autoridad del manifiesto",),
        ("que el manifiesto cita el protocolo y la declaracion",),
        (*_NO_DEMOSTRADO_COMUN, "designacion unica, trasladada a la unicidad del manifiesto (S4)",
         "nada en los bytes impide construir el manifiesto despues de las predicciones"),
        ("manifiesto_depende_de_ambos", "protocolo_no_depende_de_declaracion", "prediccion_depende_de_protocolo",
         MARCA_SIN_CRONOLOGIA),
        "dentro del manifiesto, sujeta a S4",
        MappingProxyType({
            "resultado": "mismo_protocolo_otro_manifiesto_en_modelo_sintetico",
            "texto": "en el modelo sintetico de AE-70, sin formato ni garantia operativa, el protocolo no cambia y "
                     "otro manifiesto designa el hash nuevo; que manifiesto cuenta depende de S4"}),
        ("D1", "D2", "D6", "D7", "D8")),
})

ALCANCE_DEL_ANALISIS_AE71 = (
    "las fichas describen alternativas sin elegir ninguna. Una dependencia entre bytes, S5 o un hash no es prueba "
    "temporal y no acredita autenticacion, suficiencia ni completitud; fijado exige F-1 a F-4, ninguno "
    "disponible. El segundo manifiesto es solo un contraejemplo del modelo sintetico de AE-70")

# ---------------------------------------------------------------------------
# Funciones puras
# ---------------------------------------------------------------------------


def estado_verificable_de_elemento(declaracion, elemento: str) -> str:
    """Estado de un elemento que se puede leer en los bytes de una
    declaracion sintetica de AE-69. Nunca devuelve «fijado»."""
    if elemento not in ELEMENTOS_DE_R0:
        raise ValueError(f"elemento desconocido: {elemento!r}")
    if type(declaracion) is not dict:
        return "forma_no_admitida"
    if elemento not in declaracion:
        return "ausente"
    sufijo = f":{elemento}"
    if any(m.endswith(sufijo) for m in motivos_de_incompletitud(declaracion)):
        return "forma_no_admitida"
    return "sin_fijar_explicito" if declaracion[elemento]["estado"] == "pendiente" else "declarado_sintetico"


def designaciones_por_regla(bytes_protocolo: bytes, protocolo_hash: str,
                            rutas: Sequence[tuple[str, ...]]) -> dict:
    """Hash designado por cada ruta de prueba dentro de
    estrategia.parametros (regla externa, S3). Muestra que la designacion
    depende de la regla; no fija ninguna."""
    return {ruta: hash_designado(_CAMPO, bytes_protocolo, protocolo_hash, ReglaDeVinculo(_CAMPO, tuple(ruta)))
            for ruta in rutas}


def dependencia_de_bytes(topologia: str) -> tuple[str, ...]:
    """Relaciones de dependencia entre bytes de la topologia; siempre
    termina en la marca `sin_cronologia_acreditada`."""
    return FICHAS_POR_TOPOLOGIA[topologia].dependencia_de_bytes


def consecuencia_de_cambiar_la_declaracion(topologia: str) -> MappingProxyType:
    return FICHAS_POR_TOPOLOGIA[topologia].consecuencia_de_cambiar_la_declaracion


# ---------------------------------------------------------------------------
# Clasificacion de afirmaciones
# ---------------------------------------------------------------------------

_ESTADO_POR_CLASE = MappingProxyType({
    "hecho_observado_en_codigo": "observado_en_pruebas", "hecho_citado_de_fuente": "citado_de_ae67",
    "derivacion_propia": "derivado", "hipotesis_de_aplicacion": "pendiente"})


@dataclass(frozen=True)
class AfirmacionAE71:
    id: str
    texto: str
    clase: str
    procedencia: tuple[str, ...]
    evidencia: str
    estado: str


def _a(id_, texto, clase, procedencia, evidencia):
    return AfirmacionAE71(id_, texto, clase, procedencia, evidencia, _ESTADO_POR_CLASE[clase])


_EC = "premisa:especificacion_condiciones_del_protocolo."

CLASIFICACION_DE_AFIRMACIONES = (
    _a("C1", "un texto marcador dentro de valor con estado declarado_sintetico cuenta como declarado y la "
             "declaracion da completa_sintetica_sin_autenticar",
       "hecho_observado_en_codigo",
       (f"{_IV}:comprobar_declaracion_sintetica{_BASE}",
        _P + "test_g3_c1_marcador_textual_en_valor_cuenta_como_declarado"),
       f"integracion G3 en {_T}"),
    _a("C2", "un elemento ausente da incompleta y no se hashea; uno pendiente explicito se hashea",
       "hecho_observado_en_codigo",
       (f"{_IV}:hash_de_declaracion_sintetica{_BASE}", _P + "test_g3_c2_ausente_no_se_hashea_y_pendiente_si"),
       f"integracion G3 en {_T}"),
    _a("C3", "ESTADOS_DE_ELEMENTO de AE-69 no incluye un estado para fijado",
       "hecho_observado_en_codigo",
       (f"{_IV}:ESTADOS_DE_ELEMENTO{_BASE}", _P + "test_g3_c3_no_existe_estado_fijado"),
       f"integracion G3 en {_T}"),
    _a("C4", "con dos claves con hash en estrategia.parametros, la ruta de la regla determina el hash designado",
       "hecho_observado_en_codigo",
       (f"{_VV}:hash_designado{_BASE}", _P + "test_g3_c4_la_regla_determina_el_hash_designado"),
       f"integracion G3 en {_T}"),
    _a("C5", "el modelo de AE-70 acepta en el vinculo inverso una declaracion construida despues de una prediccion "
             "registrada; el modelo no representa el tiempo",
       "hecho_observado_en_codigo",
       (f"{_VV}:declaraciones_que_verifican{_BASE}", f"{_RP}:nueva_prediccion{_BASE}",
        _P + "test_g3_c5_inverso_acepta_declaracion_construida_tras_la_prediccion"),
       f"integracion G3 en {_T}"),
    _a("C6", "el esquema forma parte de los bytes canonicos del protocolo de AE-52, y en los ejemplos cambiar un "
             "campo de un protocolo sintetico cambia su hash",
       "hecho_observado_en_codigo",
       (f"{_RP}:serializar_entrada{_BASE}", f"{_RP}:ESQUEMA_ENTRADA{_BASE}",
        _P + "test_g3_c6_esquema_en_los_bytes_y_cambio_de_campo_cambia_el_hash"),
       f"integracion G3 en {_T}, limitada a ejemplos"),
    _a("C7", "AE-67 verifico RFC 9162 para registros de certificados y precertificados",
       "hecho_citado_de_fuente", tuple(f"AE-67:C{i}" for i in range(1, 8)),
       "referencias de pagina que registra AE-67; sin cita nueva"),
    _a("C8", "bajo vinculo directo, los bytes del protocolo dependen de los de la declaracion y los de la "
             "prediccion dependen del protocolo; es dependencia entre bytes, no cronologia",
       "derivacion_propia", ("premisa:C6", "premisa:supuesto:S1", "premisa:supuesto:S3"),
       "prueba G1 de dependencia_de_bytes"),
    _a("C9", "bajo S5, en vinculo directo no es factible sustituir despues la declaracion designada por otra con el "
             "mismo hash; esto no fecha la declaracion",
       "derivacion_propia", ("premisa:C8", "premisa:supuesto:S5"),
       "prueba G1 de S5 y de la marca sin_cronologia_acreditada"),
    _a("C10", "pasar de la dependencia entre bytes a una cronologia exige H-a a H-d, todas pendientes",
       "derivacion_propia",
       (_EC + "AUTENTICACION_DE_R0", _EC + "CONDICIONES_DEL_PROTOCOLO", "premisa:AE-67:T6"),
       "prueba G1 de HIPOTESIS_PARA_CRONOLOGIA"),
    _a("C11", "en el vinculo inverso el protocolo no depende de la declaracion, y los bytes no impiden construirla "
              "tras las predicciones",
       "derivacion_propia", ("premisa:C5",),
       "contraejemplo G1"),
    _a("C12", "ausente y sin fijar se distinguen en los bytes; declarado y fijado no, porque fijado exige F-1 a F-4",
       "derivacion_propia", ("premisa:C2", "premisa:C3", _EC + "AUTENTICACION_DE_R0"),
       "prueba G1 de estado_verificable_de_elemento y DISTINCION_DE_ESTADOS"),
    _a("C13", "con la regla externa, la designacion depende de S3",
       "derivacion_propia", ("premisa:C4", "premisa:supuesto:S3"),
       "prueba G1 de designaciones_por_regla"),
    _a("C14", "de C7 se deriva que lo verificado no aporta una garantia aplicable a un manifiesto de predicciones "
              "ni a nuestras entradas; no se afirma que ese uso sea imposible",
       "derivacion_propia", ("premisa:C7",),
       "derivacion propia, no atribuida al RFC"),
    _a("C15", "cambiar la declaracion vinculada: en las topologias directas exige otro protocolo, que AE-52 no "
              "admite en el mismo registro; en el inverso el protocolo no cambia y las declaraciones coexisten; en "
              "el modelo sintetico del manifiesto, otro manifiesto designa el hash nuevo segun S4",
       "derivacion_propia",
       ("premisa:C8", "premisa:C11",
        "premisa:vinculo_declaracion_previa_con_protocolo.CONSECUENCIA_DE_COMPLETAR_DESPUES", "premisa:supuesto:S4"),
       "pruebas G1 por topologia y G3 de la premisa sobre dos protocolos"),
    _a("C16", "la version incluida en los bytes puede identificar la regla si D4 fija la definicion y su "
              "correspondencia; los bytes no contienen por si solos toda la semantica",
       "hipotesis_de_aplicacion", (f"{_RP}:ESQUEMA_ENTRADA{_BASE}",),
       "pendiente de D4"),
    _a("C17", "rechazar textos marcadores dentro de valor exigiria cambiar AE-69",
       "hipotesis_de_aplicacion", (f"{_IV}:comprobar_declaracion_sintetica{_BASE}",),
       "pendiente de D9"),
    _a("C18", "admitir pendientes al registrar obligaria, al completarlos, a otro protocolo en las topologias "
              "directas y a otra declaracion u otro manifiesto en las demas",
       "hipotesis_de_aplicacion", (f"{_VV}:CONSECUENCIA_DE_COMPLETAR_DESPUES{_BASE}",),
       "pendiente de D7"),
)
