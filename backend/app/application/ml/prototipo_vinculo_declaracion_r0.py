"""
Prototipo optativo de vinculo entre la declaracion R0 y el protocolo de
AE-52 -Etapa AE-72, validada (solo como prototipo sintetico optativo y sus
pruebas; la topologia sigue siendo candidata y R0, R9 y las ocho condiciones
siguen sin fijar).

Conecta de extremo a extremo los once elementos de una declaracion R0
sintetica (AE-69) con un protocolo y una prediccion sinteticos de AE-52,
mediante la topologia candidata `directo_en_campo_existente_no_previsto` de
AE-70: el hash de la declaracion viaja en una clave reservada de
`estrategia.parametros`, junto con el identificador versionado de la regla.

Piezas:

1. `declaracion-r0-sintetica/1`: envoltorio estricto y canonico (JSON de
   AE-52) de los once elementos, con un estado por elemento: pendiente
   explicito, ausente, declarado, declarado con texto marcador o formato
   invalido. Ningun resultado se llama «fijado».
2. `ae72-vinculo-r0-en-parametros/1`: regla candidata, de activacion
   optativa. Solo `construir_protocolo_candidato` la usa, y siempre con
   protocolos sinteticos; los registros existentes y `construir_protocolo`
   no cambian.
3. `verificar_vinculo`: comprueba solo integridad de bytes y devuelve un
   informe que separa esa comprobacion de la autenticacion de R0, la
   recepcion antes del plazo, la completitud y unicidad del canal y la
   aptitud inferencial, que quedan sin evidencia o no autorizadas.

La topologia es `candidata`: `TOPOLOGIA_ELEGIDA` y `REPRESENTACION_ELEGIDA`
de AE-70 siguen en None y D1-D9 de AE-71 sin decidir. AE-52 y AE-63 a AE-71
no cambian. R0, R9 y las ocho condiciones siguen `sin_fijar`; el expediente
sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`. Puro:
sin red, relojes, sellos reales, archivos, datos reales ni PostgreSQL.
"""
from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from app.application.ml import propuesta_inferencia_prospectiva as _expediente
from app.application.ml.analisis_alternativas_de_declaracion_previa import (
    DECISIONES_DEL_OPERADOR_AE71,
    estado_verificable_de_elemento,
)
from app.application.ml.inventario_declaracion_previa_del_protocolo import ELEMENTOS_DE_R0, motivos_de_incompletitud
from app.application.ml.registro_prospectivo import (
    RegistroProspectivoError,
    construir_protocolo,
    hash_entrada,
    leer_entrada,
    nueva_prediccion,
    serializar_entrada,
    validar_registro,
)
from app.application.ml.vinculo_declaracion_previa_con_protocolo import (
    ReglaDeVinculo,
    hash_designado,
)

# ---------------------------------------------------------------------------
# Identificadores versionados
# ---------------------------------------------------------------------------

ESQUEMA_DECLARACION = "declaracion-r0-sintetica/1"
TOPOLOGIA_CANDIDATA = "directo_en_campo_existente_no_previsto"
ESTADO_DE_LA_TOPOLOGIA = "candidata"
ACTIVACION = "optativa"
REGLA_CANDIDATA = "ae72-vinculo-r0-en-parametros/1"
CLAVE_RESERVADA = "vinculo_r0_candidato"
RUTA_DEL_HASH = ("estrategia", "parametros", CLAVE_RESERVADA, "hash_declaracion")
_CLAVES_DEL_VINCULO = frozenset({"regla", "esquema_declaracion", "hash_declaracion"})
_HASH = re.compile(r"[0-9a-f]{64}")

COMPARACION_DE_TOPOLOGIAS = MappingProxyType({
    "directo_en_nuevo_esquema": MappingProxyType({
        "efecto_en_ae52": "exige una version nueva del esquema y cambiar la comprobacion del protocolo de AE-52",
        "viable_de_extremo_a_extremo_sin_cambiar_ae52": False,
        "motivo": "no se puede registrar una prediccion con las API actuales sin modificar AE-52"}),
    TOPOLOGIA_CANDIDATA: MappingProxyType({
        "efecto_en_ae52": "ninguno en el codigo: usa una clave reservada de estrategia.parametros, que AE-52 ya "
                          "admite, y construir_protocolo sin la candidata no la anade",
        "viable_de_extremo_a_extremo_sin_cambiar_ae52": True,
        "motivo": "cumple K1 y K2 de AE-70 bajo S1 a S3 con las API reales; su coste es reinterpretar un campo de "
                  "la estrategia (K4 de AE-70, B13), que queda como criterio para descartarla"}),
    "inverso_desde_la_declaracion": MappingProxyType({
        "efecto_en_ae52": "ninguno",
        "viable_de_extremo_a_extremo_sin_cambiar_ae52": False,
        "motivo": "los bytes del protocolo no designan ninguna declaracion y dos declaraciones pueden citar el mismo "
                  "protocolo (K1 y K2 de AE-70 no se cumplen)"}),
    "manifiesto_externo": MappingProxyType({
        "efecto_en_ae52": "ninguno",
        "viable_de_extremo_a_extremo_sin_cambiar_ae52": False,
        "motivo": "exige un formato, una publicacion y una autoridad de manifiesto que no existen (S4, D6)"}),
})

# ---------------------------------------------------------------------------
# Declaracion R0 sintetica versionada
# ---------------------------------------------------------------------------

ESTADOS_DE_ELEMENTO = ("sin_fijar_explicito", "ausente", "declarado_sintetico", "declarado_con_marcador_textual",
                       "formato_invalido")
RESUMENES_DE_DECLARACION = ("todos_pendientes", "parcial_con_pendientes_explicitos",
                            "parcial_con_pendientes_y_marcadores_textuales",
                            "estructuralmente_completa_con_marcadores_textuales",
                            "estructuralmente_completa_sin_autenticar")
MARCADORES_TEXTUALES = frozenset({"pendiente", "pending", "sin fijar", "sin_fijar", "por definir", "por_definir",
                                  "tbd", "todo", "n/a", "?", "xxx", "placeholder"})
"""Deteccion heuristica del prototipo: un texto marcador se informa, no se
rechaza ni se trata como valor sustantivo; rechazarlo es la decision D9."""


class DeclaracionR0Invalida(ValueError):
    """La declaracion no tiene la forma estricta de `declaracion-r0-sintetica/1`."""


def _validar_declaracion(declaracion) -> None:
    if type(declaracion) is not dict or set(declaracion) != {"esquema", "elementos"}:
        raise DeclaracionR0Invalida("la declaracion debe tener exactamente las claves esquema y elementos")
    if declaracion["esquema"] != ESQUEMA_DECLARACION:
        raise DeclaracionR0Invalida(f"esquema distinto de {ESQUEMA_DECLARACION}")
    motivos = motivos_de_incompletitud(declaracion["elementos"])
    if motivos:
        raise DeclaracionR0Invalida("elementos no admitidos: " + ", ".join(motivos))
    if leer_entrada(serializar_entrada(declaracion)) != declaracion:
        raise DeclaracionR0Invalida("la serializacion canonica no reproduce la declaracion")


def construir_declaracion(elementos: dict) -> dict:
    """Envoltorio versionado de los once elementos; los valores son datos
    sinteticos de prueba, no decisiones."""
    declaracion = {"esquema": ESQUEMA_DECLARACION, "elementos": copy.deepcopy(elementos)}
    _validar_declaracion(declaracion)
    return declaracion


def bytes_de_declaracion(declaracion: dict) -> bytes:
    _validar_declaracion(declaracion)
    return serializar_entrada(declaracion)


def hash_de_declaracion(declaracion: dict) -> str:
    return hash_entrada(bytes_de_declaracion(declaracion))


def leer_declaracion(contenido: bytes) -> dict:
    """Lee bytes canonicos de una declaracion; rechaza forma no canonica,
    esquema distinto, claves de mas o elementos no admitidos."""
    if type(contenido) is not bytes:
        raise DeclaracionR0Invalida("la declaracion debe llegar como bytes")
    try:
        declaracion = leer_entrada(contenido)
    except RegistroProspectivoError as error:
        raise DeclaracionR0Invalida(str(error)) from error
    _validar_declaracion(declaracion)
    return declaracion


def _es_marcador(valor) -> bool:
    if type(valor) is str:
        return valor.strip().lower() in MARCADORES_TEXTUALES
    if type(valor) is list:
        return any(_es_marcador(v) for v in valor)
    if type(valor) is dict:
        return any(_es_marcador(v) for v in valor.values())
    return False


def estados_de_elementos(declaracion) -> dict:
    """Estado de cada uno de los once elementos. Tolera declaraciones
    invalidas para poder informar que elemento falla."""
    elementos = declaracion.get("elementos") if type(declaracion) is dict else None
    if type(elementos) is not dict:
        return {e: "formato_invalido" for e in ELEMENTOS_DE_R0}
    estados = {}
    for e in ELEMENTOS_DE_R0:
        base = estado_verificable_de_elemento(elementos, e)
        if base == "forma_no_admitida":
            estados[e] = "formato_invalido"
        elif base == "declarado_sintetico" and _es_marcador(elementos[e]["valor"]):
            estados[e] = "declarado_con_marcador_textual"
        else:
            estados[e] = base
    return estados


def elementos_pendientes(declaracion: dict) -> tuple[str, ...]:
    return tuple(e for e, s in estados_de_elementos(declaracion).items() if s == "sin_fijar_explicito")


def elementos_con_marcador(declaracion: dict) -> tuple[str, ...]:
    return tuple(e for e, s in estados_de_elementos(declaracion).items() if s == "declarado_con_marcador_textual")


def resumen_de_declaracion(declaracion: dict) -> str:
    _validar_declaracion(declaracion)
    pendientes, marcadores = elementos_pendientes(declaracion), elementos_con_marcador(declaracion)
    if len(pendientes) == len(ELEMENTOS_DE_R0):
        return "todos_pendientes"
    if pendientes:
        return "parcial_con_pendientes_y_marcadores_textuales" if marcadores else "parcial_con_pendientes_explicitos"
    if marcadores:
        return "estructuralmente_completa_con_marcadores_textuales"
    return "estructuralmente_completa_sin_autenticar"


# ---------------------------------------------------------------------------
# Protocolo candidato (activacion optativa, siempre sintetico)
# ---------------------------------------------------------------------------

def construir_protocolo_candidato(declaracion: dict, *, protocolo_id: str, estrategia: dict, cortes: dict) -> dict:
    """Protocolo sintetico de AE-52 que lleva el hash de la declaracion bajo
    la regla candidata. No modifica la estrategia recibida."""
    hash_declaracion = hash_de_declaracion(declaracion)
    if type(estrategia) is not dict or type(estrategia.get("parametros")) is not dict:
        raise ValueError("la estrategia debe ser un objeto con parametros")
    if CLAVE_RESERVADA in estrategia["parametros"]:
        raise ValueError(f"la clave {CLAVE_RESERVADA} esta reservada para el vinculo candidato")
    con_vinculo = copy.deepcopy(estrategia)
    con_vinculo["parametros"][CLAVE_RESERVADA] = {
        "regla": REGLA_CANDIDATA, "esquema_declaracion": ESQUEMA_DECLARACION, "hash_declaracion": hash_declaracion}
    return construir_protocolo(protocolo_id=protocolo_id, estrategia=con_vinculo, cortes=cortes, pendientes=[],
                               sintetico=True)


# ---------------------------------------------------------------------------
# Verificador
# ---------------------------------------------------------------------------

PLANOS_DEL_INFORME = MappingProxyType({
    "integridad_de_bytes": "los bytes del registro, del protocolo y de la declaracion son coherentes con la regla "
                           "candidata; es lo unico que el prototipo comprueba",
    "autenticacion_de_r0": "quien declaro R0 y con que autoridad; el prototipo no tiene firmas ni custodios",
    "recepcion_antes_del_plazo": "cuando se recibieron los bytes; el prototipo no tiene sello, reloj ni canal",
    "completitud_y_unicidad_del_canal": "que no existan otros protocolos, declaraciones o predicciones fuera del "
                                        "registro presentado; el prototipo solo ve ese registro",
    "aptitud_inferencial": "si el registro puede usarse para evaluar; AUTORIZA_EVALUACION sigue en False",
})
ESTADOS_DE_BYTES = ("vinculo_de_bytes_verificado", "registro_invalido", "protocolo_hash_no_coincide",
                    "protocolo_sin_vinculo_candidato", "vinculo_mal_formado", "regla_distinta",
                    "declaracion_ausente", "declaracion_invalida", "hash_de_declaracion_no_coincide",
                    "prediccion_omitida")
ESTADOS_DE_PLANO = ("sin_evidencia", "no_autorizada")
_FALTA_SIEMPRE = ("autenticacion_de_r0", "recepcion_antes_del_plazo", "completitud_y_unicidad_del_canal",
                  "decisiones_del_operador_d1_a_d9", "autorizacion_de_evaluacion")


@dataclass(frozen=True)
class InformeDeVinculo:
    estado_de_bytes: str
    detalle: str
    protocolo_hash: str | None = None
    hash_declaracion: str | None = None
    predicciones_vinculadas: int = 0
    omitidas: tuple = ()
    resumen_de_declaracion: str | None = None
    elementos: dict = field(default_factory=dict)
    pendientes: tuple[str, ...] = ()
    marcadores: tuple[str, ...] = ()
    autenticacion_de_r0: str = "sin_evidencia"
    recepcion_antes_del_plazo: str = "sin_evidencia"
    completitud_y_unicidad_del_canal: str = "sin_evidencia"
    aptitud_inferencial: str = "no_autorizada"
    falta: tuple[str, ...] = ()


def _aptitud() -> str:
    return "sin_evidencia" if _expediente.AUTORIZA_EVALUACION else "no_autorizada"


def _informe(estado: str, detalle: str, **campos) -> InformeDeVinculo:
    falta = list(_FALTA_SIEMPRE)
    if estado != "vinculo_de_bytes_verificado":
        falta.insert(0, "vinculo_de_bytes")
    if campos.get("pendientes"):
        falta.append("elementos_pendientes_en_la_declaracion")
    if campos.get("marcadores"):
        falta.append("valores_con_marcador_textual")
    if campos.get("omitidas"):
        falta.append("predicciones_omitidas")
    return InformeDeVinculo(estado, detalle, aptitud_inferencial=_aptitud(), falta=tuple(falta), **campos)


def verificar_vinculo(entradas: Sequence[bytes], bytes_declaracion: bytes | None, *, regla: str = REGLA_CANDIDATA,
                      protocolo_hash_esperado: str | None = None,
                      objetivos_esperados: Sequence[tuple[str, int]] = ()) -> InformeDeVinculo:
    """Comprueba el vinculo de bytes entre un registro de AE-52 y una
    declaracion bajo la regla candidata. No acredita autenticacion,
    recepcion antes del plazo, completitud del canal ni aptitud inferencial."""
    if not entradas:
        return _informe("registro_invalido", "registro vacio")
    try:
        estado = validar_registro(list(entradas))
    except RegistroProspectivoError as error:
        return _informe("registro_invalido", str(error))
    protocolo_hash = estado.hash_protocolo
    vinculadas = len(estado.predicciones)
    if protocolo_hash_esperado is not None and protocolo_hash_esperado != protocolo_hash:
        return _informe("protocolo_hash_no_coincide", "el hash del protocolo no es el esperado",
                        protocolo_hash=protocolo_hash, predicciones_vinculadas=vinculadas)
    parametros = estado.protocolo["estrategia"]["parametros"]
    if CLAVE_RESERVADA not in parametros:
        return _informe("protocolo_sin_vinculo_candidato", "el protocolo no lleva la clave del vinculo candidato",
                        protocolo_hash=protocolo_hash, predicciones_vinculadas=vinculadas)
    vinculo = parametros[CLAVE_RESERVADA]
    if (type(vinculo) is not dict or set(vinculo) != _CLAVES_DEL_VINCULO
            or type(vinculo["hash_declaracion"]) is not str or not _HASH.fullmatch(vinculo["hash_declaracion"])
            or vinculo["esquema_declaracion"] != ESQUEMA_DECLARACION):
        return _informe("vinculo_mal_formado", "el objeto del vinculo no tiene la forma de la regla candidata",
                        protocolo_hash=protocolo_hash, predicciones_vinculadas=vinculadas)
    if regla != REGLA_CANDIDATA or vinculo["regla"] != regla:
        return _informe("regla_distinta", f"regla pedida {regla!r}, regla en el protocolo {vinculo['regla']!r}",
                        protocolo_hash=protocolo_hash, predicciones_vinculadas=vinculadas)
    designado = hash_designado(TOPOLOGIA_CANDIDATA, entradas[0], protocolo_hash,
                               ReglaDeVinculo(TOPOLOGIA_CANDIDATA, RUTA_DEL_HASH))
    if bytes_declaracion is None:
        return _informe("declaracion_ausente", "no se presento la declaracion",
                        protocolo_hash=protocolo_hash, predicciones_vinculadas=vinculadas)
    try:
        declaracion = leer_declaracion(bytes_declaracion)
    except DeclaracionR0Invalida as error:
        return _informe("declaracion_invalida", str(error), protocolo_hash=protocolo_hash,
                        predicciones_vinculadas=vinculadas)
    hash_presentado = hash_entrada(bytes_declaracion)
    detalles = dict(protocolo_hash=protocolo_hash, hash_declaracion=hash_presentado, predicciones_vinculadas=vinculadas,
                    resumen_de_declaracion=resumen_de_declaracion(declaracion),
                    elementos=estados_de_elementos(declaracion), pendientes=elementos_pendientes(declaracion),
                    marcadores=elementos_con_marcador(declaracion))
    if hash_presentado != designado:
        return _informe("hash_de_declaracion_no_coincide", "la declaracion presentada no es la designada",
                        **detalles)
    omitidas = tuple(tuple(o) for o in objetivos_esperados if tuple(o) not in estado.predicciones)
    if omitidas:
        return _informe("prediccion_omitida", "hay objetivos esperados sin prediccion en el registro",
                        omitidas=omitidas, **detalles)
    return _informe("vinculo_de_bytes_verificado", "los bytes del registro y de la declaracion coinciden con la "
                    "regla candidata", **detalles)


def demostrar_recorrido_sintetico(historico_sintetico: Sequence) -> InformeDeVinculo:
    """Recorrido completo y reproducible con datos sinteticos: declaracion ->
    bytes y hash -> protocolo candidato -> prediccion -> verificacion. El
    historico lo aporta quien llama (por ejemplo, el generador sintetico de
    las pruebas); el objetivo es el sorteo siguiente al ultimo del historico."""
    elementos = {e: {"estado": "declarado_sintetico", "valor": {"sintetico": f"demostracion-{i}"}}
                 for i, e in enumerate(ELEMENTOS_DE_R0)}
    declaracion = construir_declaracion(elementos)
    estrategia = {"nombre": "estrategia_sintetica", "descripcion": "demostracion sintetica de AE-72",
                  "huella_codigo": "0" * 64, "archivos_codigo": ["sintetico.py"], "parametros": {"semilla": 1},
                  "entorno": {"python": "3.x"}}
    protocolo = construir_protocolo_candidato(declaracion, protocolo_id="demostracion-ae72", estrategia=estrategia,
                                              cortes={"BALOTO": 2713})
    entradas = [serializar_entrada(protocolo)]
    objetivo = max(r.numero_sorteo for r in historico_sintetico) + 1
    prediccion = nueva_prediccion(validar_registro(entradas), "BALOTO", objetivo, historico_sintetico, [0.1] * 43)
    entradas.append(serializar_entrada(prediccion))
    return verificar_vinculo(entradas, bytes_de_declaracion(declaracion), objetivos_esperados=(("BALOTO", objetivo),))


# ---------------------------------------------------------------------------
# Compatibilidad, decisiones y criterios
# ---------------------------------------------------------------------------

CONSECUENCIA_DE_COMPLETAR_UN_PENDIENTE = (
    "completar un elemento pendiente cambia el hash de la declaracion y, con la topologia candidata, el del "
    "protocolo; AE-52 no admite un segundo protocolo en el mismo registro, asi que hace falta otro registro, y las "
    "predicciones previas siguen vinculadas solo a la declaracion anterior")

COMPATIBILIDAD = (
    "el prototipo no modifica AE-52 ni ningun modulo anterior: la activacion es optativa y solo "
    "construir_protocolo_candidato anade la clave reservada. construir_protocolo, validar_registro y los registros "
    "existentes se comportan igual; un registro sin la clave se informa como protocolo_sin_vinculo_candidato y "
    "sigue siendo un registro de AE-52 normal. Los protocolos candidatos son siempre sinteticos")

LIMITES_DEL_PROTOTIPO = (
    "el prototipo solo comprueba integridad de bytes bajo los supuestos S1 a S3 de AE-70 y S5 de AE-71; un hash no "
    "es prueba temporal. La autenticacion de R0, la recepcion antes del plazo y la completitud y unicidad del canal "
    "quedan sin evidencia, y la aptitud inferencial sigue sin autorizacion (AUTORIZA_EVALUACION = False). Los valores de "
    "la declaracion son sinteticos y la deteccion de textos marcadores es heuristica")

DECISIONES_REQUERIDAS = MappingProxyType({
    id_: MappingProxyType({"texto": d["texto"], "estado": d["estado"], "supuesto_del_prototipo": supuesto})
    for (id_, d), supuesto in zip(DECISIONES_DEL_OPERADOR_AE71.items(), (
        "topologia candidata directo_en_campo_existente_no_previsto, sin elegir",
        "pendiente explicito de AE-69 dentro del envoltorio, sin elegir",
        "clave reservada vinculo_r0_candidato, solo en el prototipo",
        "regla ae72-vinculo-r0-en-parametros/1 definida en este modulo",
        "no aplica a la candidata",
        "no aplica a la candidata",
        "se admiten pendientes en la declaracion para mostrar sus consecuencias, sin decidirlo",
        "sin supuesto: el prototipo no define plazo ni corte",
        "los textos marcadores se informan, no se rechazan",
    ))
})

CRITERIOS_PARA_PROMOVER = (
    "que el operador decida D1 a favor de esta topologia y D2, D3, D4 y D7 de forma compatible",
    "que el operador acepte usar una clave reservada de estrategia.parametros con esa semantica, o que una etapa "
    "posterior la traslade a un campo propio sin romper registros existentes",
    "que exista evidencia externa para H-a a H-d de AE-71 (sello o recepcion con reloj y margen, autenticacion de R0 "
    "y definicion del plazo)",
    "que el verificador siga devolviendo vinculo_de_bytes_verificado en los casos positivos y el estado exacto de "
    "fallo en cada contraejemplo",
)

CRITERIOS_PARA_DESCARTAR = (
    "que el operador rechace reinterpretar estrategia.parametros (B13 de AE-70)",
    "que el operador decida una version nueva del esquema de AE-52 o un manifiesto (D1 distinto)",
    "que la clave reservada entre en conflicto con parametros reales de alguna estrategia",
    "que un caso de las pruebas muestre un vinculo aceptado con una declaracion distinta de la designada",
)
