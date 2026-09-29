"""
Vinculo de la declaracion R0 mediante un campo explicito del protocolo de
AE-52 -Etapa AE-73, validada (solo como extension optativa y sintetica del
esquema, su verificador y sus pruebas; las rutas siguen siendo candidatas y
R0, R9 y las ocho condiciones siguen sin fijar).

AE-72 vinculo la declaracion R0 sintetica con el protocolo mediante una clave
reservada de `estrategia.parametros`. AE-73 anade a AE-52 una alternativa
optativa y versionada que no usa ese campo: la version
`registro-prospectivo-ml/1.1` de la entrada protocolo, con el campo propio
`declaracion_r0` = {regla, esquema_declaracion, hash_declaracion,
pendientes}, que AE-52 valida de forma estricta.

Este modulo construye ese vinculo a partir de una declaracion de AE-72,
verifica de extremo a extremo las dos rutas (la candidata de AE-72 y el
campo explicito) con un informe que separa cinco planos, compara ambas rutas
de forma verificable y documenta que haria falta para migrar, sin ejecutar
ninguna migracion.

Las dos rutas son candidatas y optativas: D1-D9 siguen sin decidir y
`TOPOLOGIA_ELEGIDA` y `REPRESENTACION_ELEGIDA` siguen en None. Solo se
comprueba integridad de bytes; la autenticacion de R0, la recepcion antes
del plazo, la completitud y unicidad del canal y la aptitud inferencial
siguen pendientes. R0, R9 y las ocho condiciones siguen `sin_fijar`; el
expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION =
False`. Puro: sin red, relojes, sellos reales, archivos ni datos reales.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from types import MappingProxyType

from app.application.ml import propuesta_inferencia_prospectiva as _expediente
from app.application.ml import prototipo_vinculo_declaracion_r0 as _ae72
from app.application.ml.analisis_alternativas_de_declaracion_previa import DECISIONES_DEL_OPERADOR_AE71
from app.application.ml.registro_prospectivo import (
    CAMPO_VINCULO_R0,
    ESQUEMA_ENTRADA_PROTOCOLO_VINCULO_R0,
    REGLA_VINCULO_R0_CAMPO_EXPLICITO,
    RegistroProspectivoError,
    VinculoR0InvalidoError,
    construir_protocolo_con_vinculo_r0,
    hash_entrada,
    validar_registro,
)
from app.application.ml.vinculo_declaracion_previa_con_protocolo import ReglaDeVinculo, hash_designado

RUTA_AE72 = "ae72_parametros"
RUTA_AE73 = "ae73_campo_explicito"
RUTAS = (RUTA_AE72, RUTA_AE73)
ESTADO_DE_LAS_RUTAS = "candidatas"
ACTIVACION = "optativa"
_TOPOLOGIA_AE70 = "directo_en_nuevo_esquema"
_RUTA_DEL_HASH = (CAMPO_VINCULO_R0, "hash_declaracion")

PLANOS_DEL_INFORME = _ae72.PLANOS_DEL_INFORME
ESTADOS_DE_BYTES = (*_ae72.ESTADOS_DE_BYTES, "protocolo_sin_vinculo_r0", "pendientes_no_coinciden")


# ---------------------------------------------------------------------------
# Construccion
# ---------------------------------------------------------------------------

def construir_vinculo_r0(declaracion: dict) -> dict:
    """Campo `declaracion_r0` a partir de una declaracion de AE-72: regla,
    esquema, hash de sus bytes canonicos y elementos pendientes explicitos
    (ordenados). No declara ni autentica nada."""
    return {
        "regla": REGLA_VINCULO_R0_CAMPO_EXPLICITO,
        "esquema_declaracion": _ae72.ESQUEMA_DECLARACION,
        "hash_declaracion": _ae72.hash_de_declaracion(declaracion),
        "pendientes": sorted(_ae72.elementos_pendientes(declaracion)),
    }


def construir_protocolo_con_campo_explicito(declaracion: dict, *, protocolo_id: str, estrategia: dict,
                                            cortes: dict) -> dict:
    """Protocolo sintetico 1.1 de AE-52 con el vinculo en su campo propio."""
    return construir_protocolo_con_vinculo_r0(protocolo_id=protocolo_id, estrategia=estrategia, cortes=cortes,
                                              pendientes=[], sintetico=True,
                                              vinculo_r0=construir_vinculo_r0(declaracion))


def ruta_del_protocolo(protocolo: dict) -> str | None:
    if protocolo.get("esquema") == ESQUEMA_ENTRADA_PROTOCOLO_VINCULO_R0:
        return RUTA_AE73
    if _ae72.CLAVE_RESERVADA in protocolo.get("estrategia", {}).get("parametros", {}):
        return RUTA_AE72
    return None


# ---------------------------------------------------------------------------
# Verificacion de las dos rutas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InformeDeVinculoR0:
    ruta: str | None
    regla: str | None
    estado_de_bytes: str
    detalle: str
    motivo_de_registro: str | None = None
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


def _informe(ruta, estado: str, detalle: str, **campos) -> InformeDeVinculoR0:
    falta = ["autenticacion_de_r0", "recepcion_antes_del_plazo", "completitud_y_unicidad_del_canal",
             "decisiones_del_operador_d1_a_d9", "autorizacion_de_evaluacion"]
    if estado != "vinculo_de_bytes_verificado":
        falta.insert(0, "vinculo_de_bytes")
    if campos.get("pendientes"):
        falta.append("elementos_pendientes_en_la_declaracion")
    if campos.get("marcadores"):
        falta.append("valores_con_marcador_textual")
    if campos.get("omitidas"):
        falta.append("predicciones_omitidas")
    regla = REGLA_VINCULO_R0_CAMPO_EXPLICITO if ruta == RUTA_AE73 else (
        _ae72.REGLA_CANDIDATA if ruta == RUTA_AE72 else None)
    return InformeDeVinculoR0(ruta, regla, estado, detalle, aptitud_inferencial=_aptitud(), falta=tuple(falta),
                              **campos)


def verificar_vinculo_r0(entradas: Sequence[bytes], bytes_declaracion: bytes | None, *, regla: str | None = None,
                         protocolo_hash_esperado: str | None = None,
                         objetivos_esperados: Sequence[tuple[str, int]] = ()) -> InformeDeVinculoR0:
    """Detecta la ruta del protocolo y verifica el vinculo de bytes con la
    declaracion. La ruta de AE-72 se delega en su verificador. Ningun
    resultado acredita autenticacion, recepcion antes del plazo, completitud
    del canal ni aptitud inferencial."""
    if not entradas:
        return _informe(None, "registro_invalido", "registro vacio")
    try:
        estado = validar_registro(list(entradas))
    except VinculoR0InvalidoError as error:
        return _informe(RUTA_AE73, "registro_invalido", str(error), motivo_de_registro=error.motivo)
    except RegistroProspectivoError as error:
        return _informe(None, "registro_invalido", str(error))
    ruta = ruta_del_protocolo(estado.protocolo)
    protocolo_hash = estado.hash_protocolo
    vinculadas = len(estado.predicciones)
    if ruta is None:
        return _informe(None, "protocolo_sin_vinculo_r0", "el protocolo no lleva ningun vinculo con R0",
                        protocolo_hash=protocolo_hash, predicciones_vinculadas=vinculadas)
    if ruta == RUTA_AE72:
        informe = _ae72.verificar_vinculo(entradas, bytes_declaracion, regla=regla or _ae72.REGLA_CANDIDATA,
                                          protocolo_hash_esperado=protocolo_hash_esperado,
                                          objetivos_esperados=objetivos_esperados)
        return InformeDeVinculoR0(RUTA_AE72, _ae72.REGLA_CANDIDATA, **asdict(informe))
    base = dict(protocolo_hash=protocolo_hash, predicciones_vinculadas=vinculadas)
    if protocolo_hash_esperado is not None and protocolo_hash_esperado != protocolo_hash:
        return _informe(ruta, "protocolo_hash_no_coincide", "el hash del protocolo no es el esperado", **base)
    if (regla or REGLA_VINCULO_R0_CAMPO_EXPLICITO) != REGLA_VINCULO_R0_CAMPO_EXPLICITO:
        return _informe(ruta, "regla_distinta", f"regla pedida {regla!r}, regla del campo "
                        f"{REGLA_VINCULO_R0_CAMPO_EXPLICITO!r}", **base)
    vinculo = estado.protocolo[CAMPO_VINCULO_R0]
    designado = hash_designado(_TOPOLOGIA_AE70, entradas[0], protocolo_hash,
                               ReglaDeVinculo(_TOPOLOGIA_AE70, _RUTA_DEL_HASH))
    if bytes_declaracion is None:
        return _informe(ruta, "declaracion_ausente", "no se presento la declaracion", **base)
    try:
        declaracion = _ae72.leer_declaracion(bytes_declaracion)
    except _ae72.DeclaracionR0Invalida as error:
        return _informe(ruta, "declaracion_invalida", str(error), **base)
    hash_presentado = hash_entrada(bytes_declaracion)
    detalles = dict(base, hash_declaracion=hash_presentado,
                    resumen_de_declaracion=_ae72.resumen_de_declaracion(declaracion),
                    elementos=_ae72.estados_de_elementos(declaracion),
                    pendientes=_ae72.elementos_pendientes(declaracion),
                    marcadores=_ae72.elementos_con_marcador(declaracion))
    if hash_presentado != designado:
        return _informe(ruta, "hash_de_declaracion_no_coincide", "la declaracion presentada no es la designada",
                        **detalles)
    if vinculo["pendientes"] != sorted(detalles["pendientes"]):
        return _informe(ruta, "pendientes_no_coinciden", "los pendientes del protocolo no son los de la declaracion",
                        **detalles)
    omitidas = tuple(tuple(o) for o in objetivos_esperados if tuple(o) not in estado.predicciones)
    if omitidas:
        return _informe(ruta, "prediccion_omitida", "hay objetivos esperados sin prediccion en el registro",
                        omitidas=omitidas, **detalles)
    return _informe(ruta, "vinculo_de_bytes_verificado", "los bytes del registro y de la declaracion coinciden con "
                    "el campo explicito", **detalles)


def _hash_designado_por_la_ruta(entradas: Sequence[bytes]) -> tuple[str | None, str]:
    estado = validar_registro(list(entradas))
    ruta = ruta_del_protocolo(estado.protocolo)
    if ruta == RUTA_AE73:
        return estado.protocolo[CAMPO_VINCULO_R0]["hash_declaracion"], estado.hash_protocolo
    if ruta == RUTA_AE72:
        return estado.protocolo["estrategia"]["parametros"][_ae72.CLAVE_RESERVADA]["hash_declaracion"], \
            estado.hash_protocolo
    return None, estado.hash_protocolo


def equivalencia_de_designacion(entradas_a: Sequence[bytes], entradas_b: Sequence[bytes]) -> dict:
    """Compara dos registros (de la misma o de distinta ruta): si designan el
    mismo hash de declaracion y si comparten protocolo. Dos rutas pueden
    designar la misma declaracion con protocolos distintos."""
    hash_a, protocolo_a = _hash_designado_por_la_ruta(entradas_a)
    hash_b, protocolo_b = _hash_designado_por_la_ruta(entradas_b)
    mismo = hash_a is not None and hash_a == hash_b
    return {"mismo_hash_declaracion": mismo, "mismo_protocolo_hash": protocolo_a == protocolo_b,
            "hash_declaracion": hash_a if mismo else None}


# ---------------------------------------------------------------------------
# Comparacion, migracion, decisiones y limites
# ---------------------------------------------------------------------------

COMPARACION_DE_RUTAS = MappingProxyType({
    RUTA_AE72: MappingProxyType({
        "cambio_en_ae52": "ninguno: usa la clave reservada vinculo_r0_candidato de estrategia.parametros",
        "semantica_del_campo": "reinterpreta un parametro de la estrategia (K4 de AE-70, B13)",
        "identificacion_de_la_regla": "objeto dentro de parametros con la regla ae72-vinculo-r0-en-parametros/1",
        "ae52_rechaza_vinculos_mal_formados": False,
        "pendientes_en_el_protocolo": False,
        "rechaza_doble_vinculo": False,
        "solo_sintetico": "lo impone construir_protocolo_candidato, no la validacion de AE-52",
        "compatibilidad_con_registros_1_0": True,
    }),
    RUTA_AE73: MappingProxyType({
        "cambio_en_ae52": "version optativa registro-prospectivo-ml/1.1 de la entrada protocolo y su validacion",
        "semantica_del_campo": "campo propio declaracion_r0, sin reinterpretar la estrategia",
        "identificacion_de_la_regla": "version 1.1 en los bytes y regla ae73-vinculo-r0-campo-explicito/1 en el "
                                      "campo; su definicion vive en AE-52 (D4 sigue sin decidir)",
        "ae52_rechaza_vinculos_mal_formados": True,
        "pendientes_en_el_protocolo": True,
        "rechaza_doble_vinculo": True,
        "solo_sintetico": "lo impone la validacion de AE-52 (motivo vinculo_solo_sintetico)",
        "compatibilidad_con_registros_1_0": True,
    }),
})

REQUISITOS_DE_MIGRACION = (
    "decidir D1 entre las rutas y, en su caso, D2, D4 y D7",
    "construir un protocolo nuevo en la ruta de destino con la misma declaracion: su hash cambia, y AE-52 no "
    "admite un segundo protocolo en el mismo registro, asi que hace falta otro registro",
    "las predicciones anteriores no se trasladan: su protocolo_hash y su cadena apuntan al protocolo de origen y "
    "siguen vinculadas solo a el",
    "comprobar con equivalencia_de_designacion que ambos registros designan el mismo hash de declaracion",
    "levantar la restriccion a protocolos sinteticos exigiria una decision del operador y una etapa validada",
)
MIGRACION_EJECUTADA = False

DECISIONES_REQUERIDAS = MappingProxyType({
    id_: MappingProxyType({"texto": d["texto"], "estado": d["estado"], "destacada": id_ in ("D1", "D2", "D7"),
                           "supuesto_del_prototipo": supuesto})
    for (id_, d), supuesto in zip(DECISIONES_DEL_OPERADOR_AE71.items(), (
        "dos rutas candidatas coexisten, sin elegir ninguna",
        "pendiente explicito de AE-69 en la declaracion y lista ordenada en el campo, sin elegir",
        "campo declaracion_r0 en la ruta 1.1 y clave reservada en la de AE-72, solo en el prototipo",
        "reglas versionadas definidas en AE-52 y AE-72, pendientes de decision",
        "no aplica",
        "no aplica",
        "se admiten pendientes al registrar para mostrar sus consecuencias, sin decidirlo",
        "sin supuesto: no se define plazo ni corte",
        "los textos marcadores se informan, no se rechazan",
    ))
})

COMPATIBILIDAD = (
    "los protocolos 1.0, las predicciones, los resultados y construir_protocolo no cambian; los bytes y hashes de "
    "registros 1.0 son identicos a los de la base. La ruta de AE-72 sigue funcionando sin cambios, y la version 1.1 "
    "es optativa: solo construir_protocolo_con_vinculo_r0 la produce, siempre con protocolos sinteticos")

LIMITES = (
    "un hash designado no autentica la declaracion ni prueba cuando existio; solo se comprueba integridad de bytes. "
    "La autenticacion de R0, la recepcion antes del plazo y la completitud y unicidad del canal quedan sin "
    "evidencia, y la aptitud inferencial sigue sin autorizacion (AUTORIZA_EVALUACION = False). Un elemento "
    "pendiente o un texto marcador nunca se presenta como valor establecido. Lo verificado de RFC 9162 cubre "
    "certificados y precertificados y no se atribuye a estas entradas")
