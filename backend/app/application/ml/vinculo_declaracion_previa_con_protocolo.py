"""
Criterios verificables de vinculacion entre el contenido de R0 y el
protocolo de AE-52 -Etapa AE-70, validada (solo como modelo preparatorio de
vinculacion y sus pruebas; sin elegir topologia ni representacion, y R0,
R9 y las ocho condiciones siguen sin fijar).

AE-69 inventario los once elementos del contenido de R0 y aporto un hash de
una declaracion sintetica, pero dejo sin respuesta donde viviria esa
declaracion y como se expresarian sus pendientes. Este modulo no responde
esas preguntas: registra cuatro topologias candidatas de vinculo, siete
criterios (K1-K7), los supuestos del modelo (S1-S4) y una matriz topologia x
criterio cuyas celdas exponen sus supuestos, respaldadas por pruebas
sinteticas y por integraciones contra AE-52 real.

K1 exige los bytes canonicos del protocolo y una regla de vinculo declarada:
el `protocolo_hash` aislado es un digest y no permite obtener nada. K2 solo
dice que el vinculo designa como maximo un hash de declaracion bajo el
modelo; no afirma unicidad de las declaraciones existentes ni ausencia de
colisiones. Ningun vinculo aporta autenticacion, anterioridad ni suficiencia,
y `completa_sintetica_sin_autenticar` sigue indicando solo completitud
estructural.

No se elige topologia, representacion, campo ni mecanismo; AE-52 y AE-63 a
AE-69 no cambian. R0, R9 y las ocho condiciones siguen `sin_fijar`. El
expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION =
False`. Puro: sin red, relojes o servicios reales, archivos, datos reales ni
PostgreSQL.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from types import MappingProxyType

from app.application.ml.inventario_declaracion_previa_del_protocolo import (
    CLASES_DE_AFIRMACION,
    hash_de_declaracion_sintetica,
)
from app.application.ml.registro_prospectivo import RegistroProspectivoError, hash_entrada, leer_entrada

_BASE = "@b278d88"
_RP = "backend/app/application/ml/registro_prospectivo.py"
_IV = "backend/app/application/ml/inventario_declaracion_previa_del_protocolo.py"
_T = "backend/tests/unit/ml/test_vinculo_declaracion_previa_con_protocolo.py"
_HASH = re.compile(r"[0-9a-f]{64}")

_DIRECTO_NUEVO = "directo_en_nuevo_esquema"
_DIRECTO_CAMPO = "directo_en_campo_existente_no_previsto"
_INVERSO = "inverso_desde_la_declaracion"
_MANIFIESTO = "manifiesto_externo"
_CAMPO_NO_PREVISTO = ("estrategia", "parametros")

# ---------------------------------------------------------------------------
# Supuestos, topologias y criterios
# ---------------------------------------------------------------------------

SUPUESTOS_DEL_MODELO = MappingProxyType({
    "S1": MappingProxyType({
        "texto": "SHA-256 se trata como resistente a colisiones; se supone y no se verifica, y las pruebas no lo "
                 "demuestran",
        "estado": "supuesto_no_verificado"}),
    "S2": MappingProxyType({
        "texto": "el verificador dispone de los bytes canonicos del protocolo y comprueba que hash_entrada(bytes) "
                 "coincide con el protocolo_hash; el digest aislado no permite recuperar nada",
        "estado": "supuesto_del_modelo"}),
    "S3": MappingProxyType({
        "texto": "la regla de vinculo esta declarada (topologia y campo que designa el hash de la declaracion); en "
                 "AE-70 es un parametro de prueba, no una decision",
        "estado": "supuesto_del_modelo"}),
    "S4": MappingProxyType({
        "texto": "existe un unico manifiesto reconocido por protocolo; requisito pendiente, analogo a la "
                 "autenticacion de R0",
        "estado": "requisito_pendiente"}),
})

TOPOLOGIAS_DE_VINCULO = MappingProxyType({
    _DIRECTO_NUEVO: MappingProxyType({
        "texto": "un campo nuevo del protocolo lleva el hash de la declaracion; exige cambiar el formato de AE-52",
        "formato_ae52": "exige_cambio", "los_bytes_del_protocolo_designan": True}),
    _DIRECTO_CAMPO: MappingProxyType({
        "texto": "el hash de la declaracion va en un campo libre existente (estrategia.parametros); el formato lo "
                 "admite hoy, pero reinterpreta un campo de la estrategia",
        "formato_ae52": "admite_hoy_reinterpretando_un_campo", "los_bytes_del_protocolo_designan": True}),
    _INVERSO: MappingProxyType({
        "texto": "la declaracion lleva el protocolo_hash; los bytes del protocolo no designan ninguna declaracion",
        "formato_ae52": "sin_cambio", "los_bytes_del_protocolo_designan": False}),
    _MANIFIESTO: MappingProxyType({
        "texto": "un tercer documento enlaza el protocolo_hash con el hash de la declaracion",
        "formato_ae52": "sin_cambio", "los_bytes_del_protocolo_designan": False}),
})

CRITERIOS_DE_VINCULO = MappingProxyType({
    "K1": MappingProxyType({
        "id": "compromiso_transitivo_verificable",
        "texto": "con los bytes canonicos del protocolo, que hashean al protocolo_hash de la prediccion (S2), y la "
                 "regla de vinculo (S3), el verificador obtiene un hash de declaracion designado; cambiar la "
                 "declaracion designada cambia esos bytes y, en los ejemplos y bajo S1, el protocolo_hash. El "
                 "protocolo_hash aislado no basta"}),
    "K2": MappingProxyType({
        "id": "designacion_unica_por_el_vinculo",
        "texto": "dados los bytes del protocolo y la regla, el vinculo designa como maximo un hash de declaracion. "
                 "K2 no afirma unicidad de las declaraciones existentes ni ausencia de colisiones; que otra "
                 "declaracion no tenga el mismo hash depende de S1"}),
    "K3": MappingProxyType({"id": "sin_cambio_de_formato_ae52",
                            "texto": "la topologia no exige cambiar el formato de AE-52"}),
    "K4": MappingProxyType({"id": "sin_reinterpretar_campos_ae52",
                            "texto": "la topologia no usa un campo de AE-52 para algo distinto de su semantica"}),
    "K5": MappingProxyType({"id": "pendientes_explicitos",
                            "texto": "los once elementos se representan con las formas de AE-69; depende de la "
                                     "representacion de pendientes, no de la topologia"}),
    "K6": MappingProxyType({"id": "no_implica_autenticacion",
                            "texto": "verificar el vinculo no autentica R0; la topologia no pretende hacerlo"}),
    "K7": MappingProxyType({"id": "no_aporta_anterioridad",
                            "texto": "verificar el vinculo no fecha la declaracion; la topologia no pretende "
                                     "hacerlo"}),
})

ESTADOS_DE_CELDA = ("cumple_en_modelo_bajo_supuestos", "cumple_por_definicion", "no_cumple_por_definicion",
                    "no_cumple_contraejemplo", "depende_de_requisito_pendiente", "independiente_de_la_topologia")


@dataclass(frozen=True)
class Celda:
    estado: str
    supuestos: tuple[str, ...]
    afirmaciones: tuple[str, ...]
    alcance: str


_SOLO_MODELO = "solo en el modelo sintetico y en los ejemplos probados; no significa acreditacion ni suficiencia"
_K2_DIRECTO = ("los bytes y la regla designan como maximo un hash; no afirma unicidad de las declaraciones "
               "existentes ni ausencia de colisiones, que dependen de S1; " + _SOLO_MODELO)
_K5 = Celda("independiente_de_la_topologia", (), ("B6",),
            "K5 se evalua sobre REPRESENTACIONES_DE_PENDIENTES, sin elegir representacion")
_K6 = Celda("cumple_por_definicion", (), ("B11",), "no pretende autenticar R0; la autenticacion sigue pendiente")
_K7 = Celda("cumple_por_definicion", (), ("B11",), "no pretende fechar la declaracion; la anterioridad sigue "
                                                    "pendiente")

MATRIZ_DE_VINCULO = MappingProxyType({
    _DIRECTO_NUEVO: MappingProxyType({
        "K1": Celda("cumple_en_modelo_bajo_supuestos", ("S1", "S2", "S3"), ("B7", "B8"),
                    "modelo sintetico de un campo nuevo, sin AE-52; " + _SOLO_MODELO),
        "K2": Celda("cumple_en_modelo_bajo_supuestos", ("S2", "S3"), ("B8",), _K2_DIRECTO),
        "K3": Celda("no_cumple_por_definicion", (), ("B13",), "exige una version nueva del formato de AE-52"),
        "K4": Celda("cumple_por_definicion", (), ("B13",), "el campo nuevo tendria esa semantica propia"),
        "K5": _K5, "K6": _K6, "K7": _K7}),
    _DIRECTO_CAMPO: MappingProxyType({
        "K1": Celda("cumple_en_modelo_bajo_supuestos", ("S1", "S2", "S3"), ("B1", "B3", "B7", "B8"),
                    "propagacion observada con AE-52 real en ejemplos: el valor se conserva en los bytes, cambia el "
                    "hash del protocolo y llega al protocolo_hash de la prediccion; " + _SOLO_MODELO),
        "K2": Celda("cumple_en_modelo_bajo_supuestos", ("S2", "S3"), ("B8",), _K2_DIRECTO),
        "K3": Celda("cumple_por_definicion", (), ("B1",), "el formato vigente admite la clave en parametros"),
        "K4": Celda("no_cumple_por_definicion", (), ("B13",), "reinterpreta un parametro de la estrategia"),
        "K5": _K5, "K6": _K6, "K7": _K7}),
    _INVERSO: MappingProxyType({
        "K1": Celda("no_cumple_contraejemplo", (), ("B7", "B9"),
                    "los bytes del protocolo no designan ningun hash de declaracion"),
        "K2": Celda("no_cumple_contraejemplo", (), ("B9",),
                    "dos declaraciones distintas que apuntan al mismo protocolo_hash son aceptadas ambas"),
        "K3": Celda("cumple_por_definicion", (), ("B9",), "no toca el formato de AE-52"),
        "K4": Celda("cumple_por_definicion", (), ("B9",), "no usa campos de AE-52"),
        "K5": _K5, "K6": _K6, "K7": _K7}),
    _MANIFIESTO: MappingProxyType({
        "K1": Celda("depende_de_requisito_pendiente", ("S2", "S3", "S4"), ("B10",),
                    "los bytes del protocolo no designan nada; la designacion depende de un manifiesto unico (S4)"),
        "K2": Celda("depende_de_requisito_pendiente", ("S4",), ("B10",),
                    "dos manifiestos distintos para el mismo protocolo designan dos hashes"),
        "K3": Celda("cumple_por_definicion", (), ("B10",), "no toca el formato de AE-52"),
        "K4": Celda("cumple_por_definicion", (), ("B10",), "no usa campos de AE-52"),
        "K5": _K5, "K6": _K6, "K7": _K7}),
})

TOPOLOGIA_ELEGIDA = None

# ---------------------------------------------------------------------------
# Representacion de pendientes
# ---------------------------------------------------------------------------

REPRESENTACIONES_DE_PENDIENTES = MappingProxyType({
    "estado_pendiente_por_elemento": MappingProxyType({
        "texto": "cada elemento pendiente se escribe con la forma de AE-69 dentro de la declaracion; se hashea y es "
                 "compatible con cualquier topologia",
        "K3": "cumple_por_definicion", "K5": "cumple_en_modelo_bajo_supuestos",
        "separada_de_los_siete_pendientes_ae52": "cumple_por_definicion"}),
    "ampliar_pendientes_de_ae52": MappingProxyType({
        "texto": "anadir identificadores de R0 a la lista de pendientes de AE-52; hoy se rechaza (AE-69 A2)",
        "K3": "no_cumple_por_definicion", "K5": "cumple_en_modelo_bajo_supuestos",
        "separada_de_los_siete_pendientes_ae52": "no_cumple_por_definicion"}),
    "ausencia_implicita": MappingProxyType({
        "texto": "tratar un elemento ausente como pendiente; AE-69 la trata como incompleta y no la hashea",
        "K3": "cumple_por_definicion", "K5": "no_cumple_contraejemplo",
        "separada_de_los_siete_pendientes_ae52": "cumple_por_definicion"}),
})

REPRESENTACION_ELEGIDA = None

CONSECUENCIA_DE_COMPLETAR_DESPUES = (
    "bajo vinculo directo, completar un elemento pendiente cambia el hash designado y, con el, los bytes y el hash "
    "del protocolo (ejemplos, bajo S1): resulta otro protocolo, que no cabe en el mismo registro de AE-52; las "
    "predicciones previas siguen comprometidas con la version anterior")

ALCANCE_DEL_ANALISIS = (
    "cumplir en el modelo no significa acreditacion, suficiencia ni conformidad: vale solo bajo los supuestos listados y "
    "en los ejemplos probados. Ningun vinculo aporta autenticacion ni anterioridad, y "
    "completa_sintetica_sin_autenticar sigue indicando solo completitud estructural, no suficiencia de valores. "
    "No se elige topologia, representacion, campo ni mecanismo")

# ---------------------------------------------------------------------------
# Modelos sinteticos y funciones puras
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReglaDeVinculo:
    """Regla de prueba (S3): topologia y ruta del campo que designaria el
    hash de la declaracion. No es una decision."""
    topologia: str
    ruta_del_campo: tuple[str, ...]


@dataclass(frozen=True)
class CandidataDeVinculo:
    declaracion: dict
    protocolo_hash_referenciado: str | None = None


@dataclass(frozen=True)
class ManifiestoSintetico:
    protocolo_hash: str
    hash_declaracion: str


def celda(topologia: str, criterio: str) -> Celda:
    return MATRIZ_DE_VINCULO[topologia][criterio]


def _comprobar_regla(topologia: str, regla: ReglaDeVinculo) -> None:
    if topologia not in TOPOLOGIAS_DE_VINCULO:
        raise ValueError(f"topologia desconocida: {topologia!r}")
    if regla.topologia != topologia:
        raise ValueError("la regla corresponde a otra topologia")
    if topologia == _DIRECTO_CAMPO and (len(regla.ruta_del_campo) <= len(_CAMPO_NO_PREVISTO)
                                        or regla.ruta_del_campo[:2] != _CAMPO_NO_PREVISTO):
        raise ValueError("el campo no previsto se modela solo dentro de estrategia.parametros")
    if topologia == _DIRECTO_NUEVO and not regla.ruta_del_campo:
        raise ValueError("el modelo de campo nuevo necesita una ruta")


def hash_designado(topologia: str, bytes_protocolo: bytes, protocolo_hash: str, regla: ReglaDeVinculo) -> str | None:
    """Hash de declaracion que designan los bytes canonicos del protocolo
    segun la regla (S2, S3). Devuelve None si los bytes no hashean al
    protocolo_hash, si no son JSON canonico de AE-52, si la topologia no hace
    que los bytes designen nada o si el campo no contiene un hash. No existe
    una variante que reciba solo el digest."""
    _comprobar_regla(topologia, regla)
    if hash_entrada(bytes_protocolo) != protocolo_hash:
        return None
    if not TOPOLOGIAS_DE_VINCULO[topologia]["los_bytes_del_protocolo_designan"]:
        return None
    try:
        nodo = leer_entrada(bytes_protocolo)
    except RegistroProspectivoError:
        return None
    for clave in regla.ruta_del_campo:
        if type(nodo) is not dict or clave not in nodo:
            return None
        nodo = nodo[clave]
    return nodo if type(nodo) is str and _HASH.fullmatch(nodo) else None


def declaraciones_que_verifican(topologia: str, protocolo_hash: str, candidatas: Sequence[CandidataDeVinculo], *,
                                bytes_protocolo: bytes | None = None, regla: ReglaDeVinculo | None = None,
                                manifiestos: Sequence[ManifiestoSintetico] = ()) -> tuple[str, ...]:
    """Hashes de las declaraciones candidatas que el vinculo acepta, sin
    repetir y en el orden de las candidatas. Sirve para los contraejemplos de
    K2; no afirma que existan o no otras declaraciones."""
    if topologia not in TOPOLOGIAS_DE_VINCULO:
        raise ValueError(f"topologia desconocida: {topologia!r}")
    hashes = []
    for candidata in candidatas:
        h = hash_de_declaracion_sintetica(candidata.declaracion)
        if h not in hashes:
            hashes.append(h)
    if TOPOLOGIAS_DE_VINCULO[topologia]["los_bytes_del_protocolo_designan"]:
        if bytes_protocolo is None or regla is None:
            raise ValueError("el vinculo directo exige los bytes del protocolo y la regla (S2, S3)")
        designado = hash_designado(topologia, bytes_protocolo, protocolo_hash, regla)
        return tuple(h for h in hashes if h == designado)
    if topologia == _INVERSO:
        aceptados = {hash_de_declaracion_sintetica(c.declaracion) for c in candidatas
                     if c.protocolo_hash_referenciado == protocolo_hash}
        return tuple(h for h in hashes if h in aceptados)
    nombrados = {m.hash_declaracion for m in manifiestos if m.protocolo_hash == protocolo_hash}
    return tuple(h for h in hashes if h in nombrados)


# ---------------------------------------------------------------------------
# Clasificacion de afirmaciones
# ---------------------------------------------------------------------------

_ESTADO_POR_CLASE = MappingProxyType({
    "hecho_observado_en_codigo": "observado_en_pruebas", "hecho_citado_de_fuente": "citado_de_ae67",
    "derivacion_propia": "derivado", "hipotesis_de_aplicacion": "pendiente"})


@dataclass(frozen=True)
class AfirmacionAE70:
    id: str
    texto: str
    clase: str
    procedencia: tuple[str, ...]
    evidencia: str
    estado: str


def _a(id_, texto, clase, procedencia, evidencia):
    return AfirmacionAE70(id_, texto, clase, procedencia, evidencia, _ESTADO_POR_CLASE[clase])


_P = "prueba:"

CLASIFICACION_DE_AFIRMACIONES = (
    _a("B1", "estrategia.parametros solo se comprueba como objeto: una clave con un hash pasa validar_registro en "
             "un protocolo sintetico",
       "hecho_observado_en_codigo",
       (f"{_RP}:_validar_estrategia{_BASE}", _P + "test_g3_b1_parametros_admite_una_clave_con_un_hash"),
       f"integracion G3 en {_T}"),
    _a("B2", "una prediccion con protocolo_hash distinto del hash del protocolo se rechaza, con la cadena correcta "
             "para aislar esa comprobacion",
       "hecho_observado_en_codigo",
       (f"{_RP}:_validar_prediccion{_BASE}", f"{_RP}:validar_registro{_BASE}",
        _P + "test_g3_b2_protocolo_hash_distinto_se_rechaza_con_la_cadena_correcta"),
       f"integracion G3 en {_T}"),
    _a("B3", "en los ejemplos probados, un valor distinto en parametros se conserva en los bytes canonicos, cambia "
             "el hash del protocolo y llega al protocolo_hash de la prediccion reconstruida",
       "hecho_observado_en_codigo",
       (f"{_RP}:construir_protocolo{_BASE}", f"{_RP}:serializar_entrada{_BASE}", f"{_RP}:nueva_prediccion{_BASE}",
        _P + "test_g3_b3_cambio_en_parametros_llega_a_bytes_hash_y_prediccion"),
       f"integracion G3 en {_T}, limitada a ejemplos"),
    _a("B4", "un segundo protocolo en el mismo registro se rechaza",
       "hecho_observado_en_codigo",
       (f"{_RP}:validar_registro{_BASE}", _P + "test_g3_b4_segundo_protocolo_en_el_registro_se_rechaza"),
       f"integracion G3 en {_T}"),
    _a("B5", "el protocolo real es un borrador con los siete pendientes y no admite predicciones",
       "hecho_observado_en_codigo",
       (f"{_RP}:construir_protocolo_borrador{_BASE}", f"{_RP}:EstadoRegistro.admite_salidas{_BASE}",
        _P + "test_g3_b5_protocolo_real_en_borrador_no_admite_predicciones"),
       f"integracion G3 en {_T}"),
    _a("B6", "una declaracion con pendientes explicitos se hashea y una omision da incompleta",
       "hecho_observado_en_codigo",
       (f"{_IV}:comprobar_declaracion_sintetica{_BASE}", f"{_IV}:hash_de_declaracion_sintetica{_BASE}",
        _P + "test_g3_b6_declaracion_con_pendientes_se_hashea_y_la_omision_es_incompleta"),
       f"integracion G3 en {_T}"),
    _a("B7", "el protocolo_hash es un digest: sin los bytes del protocolo no permite obtener un hash de declaracion",
       "derivacion_propia", ("premisa:B2", "premisa:supuesto:S2"),
       "prueba G1: ninguna funcion recibe solo el digest y unos bytes que no hashean a el no designan nada"),
    _a("B8", "con bytes y regla, el vinculo directo designa como maximo un hash y la prediccion se compromete con "
             "esos bytes; que ninguna otra declaracion tenga ese hash depende de S1",
       "derivacion_propia", ("premisa:B2", "premisa:B3", "premisa:supuesto:S2", "premisa:supuesto:S3"),
       "pruebas G1 de K1 y K2, limitadas a ejemplos"),
    _a("B9", "el vinculo inverso acepta dos declaraciones distintas que apuntan al mismo protocolo",
       "derivacion_propia", ("premisa:B2", "premisa:AE-67:T6"),
       "contraejemplo G1"),
    _a("B10", "el manifiesto traslada la designacion a la unicidad del propio manifiesto (S4)",
       "derivacion_propia",
       ("premisa:B9", "premisa:supuesto:S4", "premisa:especificacion_condiciones_del_protocolo.AUTENTICACION_DE_R0"),
       "contraejemplo G1 con dos manifiestos"),
    _a("B11", "ningun vinculo aporta autenticacion ni anterioridad",
       "derivacion_propia",
       ("premisa:especificacion_condiciones_del_protocolo.AUTENTICACION_DE_R0", "premisa:AE-67:T6"),
       "prueba G1: la autenticacion de R0 sigue pendiente tras verificar un vinculo"),
    _a("B12", "bajo vinculo directo, completar un pendiente despues da otro protocolo, que no cabe en el mismo "
              "registro",
       "derivacion_propia", ("premisa:B3", "premisa:B4"),
       "prueba G1 con AE-52 real y datos sinteticos"),
    _a("B13", "usar parametros reinterpretaria la semantica de la estrategia, y un esquema nuevo exigiria una "
              "etapa que cambie AE-52",
       "hipotesis_de_aplicacion",
       (f"{_RP}:_CLAVES_ESTRATEGIA{_BASE}", f"{_RP}:ESQUEMA_ENTRADA{_BASE}"),
       "pendiente; la resolveria una decision del operador"),
    _a("B14", "AE-67 verifico RFC 9162 para registros de certificados y precertificados",
       "hecho_citado_de_fuente", tuple(f"AE-67:C{i}" for i in range(1, 8)),
       "referencias de pagina que registra AE-67 en AFIRMACIONES_RFC_9162; sin cita nueva"),
    _a("B15", "de B14 se deriva que lo verificado no aporta una garantia aplicable a un manifiesto de predicciones "
              "ni a nuestras entradas; no se afirma que ese uso sea imposible, solo que no esta cubierto",
       "derivacion_propia", ("premisa:B14",),
       "derivacion propia, no atribuida al RFC"),
)
