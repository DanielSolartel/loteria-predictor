"""
Contrato de vinculacion R0 elegido por el operador -Etapa AE-74, validada
(solo como contrato versionado sintetico, sus puertas de admision y sus
pruebas; la puerta R0 final sigue sin poder superarse).

El operador aprobo D1, D2 y D7:

- D1: el campo explicito versionado es la unica ruta admitida por este
  contrato. El contrato y su regla quedan en los bytes del protocolo con la
  version `registro-prospectivo-ml/1.2` (campo `declaracion_r0` con
  `contrato: contrato-vinculo-r0/1` y `regla: ae74-vinculo-r0-contrato/1`),
  para que un contrato posterior no reinterprete protocolos anteriores. D3
  (campo) y D4 (regla) quedan decididas solo para esta ruta; D5 y D6 no se
  aplican a ella.
- D2: estados explicitos por elemento en la declaracion y lista ordenada y
  unica de pendientes en el vinculo, comprobada contra la declaracion.
- D7: pendientes solo en borradores sinteticos; un registro con pendientes
  nunca llega a R0 final, y completarlos exige otro protocolo y otro
  registro.

D9 tiene una espera provisional (`marcadores_textuales_sin_resolver`); su
politica de rechazo y D8 siguen sin decidir.

`evaluar_admision` responde con cuatro puertas independientes (borrador
sintetico, vinculo integro, declaracion estructuralmente completa y R0
final), cada una con estado y motivos, y con cinco planos separados. Un
borrador con pendientes puede tener un vinculo integro sin ser completo. La
puerta R0 final no admite evidencia como entrada y no puede superarse con lo
que existe: protocolos solo sinteticos y sin autenticacion, recepcion antes
del plazo ni evidencia del canal. Las rutas 1.0, AE-72 y 1.1 siguen
disponibles con sus verificadores, sin cambios, pero no son admitidas por
este contrato.

R0, R9 y las ocho condiciones siguen `sin_fijar`; el expediente sigue en
`expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`. Puro: sin red,
relojes, sellos, firmas, canales, archivos ni datos reales.
"""
from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from app.application.ml import propuesta_inferencia_prospectiva as _expediente
from app.application.ml import prototipo_vinculo_declaracion_r0 as _ae72
from app.application.ml import registro_prospectivo as _rp
from app.application.ml import vinculo_r0_campo_explicito as _ae73
from app.application.ml.vinculo_declaracion_previa_con_protocolo import ReglaDeVinculo, hash_designado

CONTRATO = _rp.CONTRATO_VINCULO_R0
ESQUEMA_DEL_PROTOCOLO = _rp.ESQUEMA_ENTRADA_PROTOCOLO_CONTRATO_R0
REGLA = _rp.REGLA_VINCULO_R0_CONTRATO
_TOPOLOGIA_AE70 = "directo_en_nuevo_esquema"
_RUTA_DEL_HASH = (_rp.CAMPO_VINCULO_R0, "hash_declaracion")

PUERTAS = ("borrador_sintetico", "vinculo_integro", "declaracion_estructuralmente_completa", "r0_final")
ESTADOS_DE_PUERTA = ("superada", "pendiente", "rechazada", "no_evaluable")
RUTAS = ("contrato_1_2", "ruta_ae72_no_admitida", "ruta_1_1_no_admitida", "sin_vinculo_r0", "registro_invalido")
_SIN_EVIDENCIA = ("sin_evidencia_de_autenticacion_de_r0", "sin_evidencia_de_recepcion_antes_del_plazo",
                  "sin_evidencia_de_completitud_y_unicidad_del_canal")
MOTIVOS_DE_PUERTA = (
    "registro_vacio", "registro_invalido", *_rp.MOTIVOS_VINCULO_R0_CONTRATO, "vinculo_en_esquema_1_0",
    "vinculo_ausente_en_esquema_1_1", "ruta_ae72_no_admitida", "ruta_1_1_no_admitida", "sin_vinculo_r0",
    "registro_no_admitido", "ruta_no_admitida", "protocolo_hash_no_coincide", "declaracion_ausente",
    "declaracion_invalida", "hash_de_declaracion_no_coincide", "pendientes_contradictorios", "prediccion_omitida",
    "declaracion_no_designada", "elementos_pendientes", "marcadores_textuales_sin_resolver", "protocolo_sintetico",
    "registro_con_pendientes", "vinculo_no_integro", "declaracion_incompleta", *_SIN_EVIDENCIA,
)

# ---------------------------------------------------------------------------
# Decisiones
# ---------------------------------------------------------------------------

DECISIONES_DEL_CONTRATO = MappingProxyType({id_: MappingProxyType({"estado": estado, "texto": texto})
                                            for id_, estado, texto in (
    ("D1", "aprobada_por_el_operador",
     "el campo explicito versionado (version 1.2 con contrato y regla en los bytes) es la unica ruta admitida por "
     "este contrato; 1.0, AE-72 y 1.1 siguen disponibles sin ser admitidas"),
    ("D2", "aprobada_por_el_operador",
     "estados explicitos por elemento en la declaracion y lista ordenada y unica de pendientes en el vinculo, "
     "comprobada contra la declaracion"),
    ("D3", "decidida_solo_para_esta_ruta", "campo declaracion_r0 de la version 1.2"),
    ("D4", "decidida_solo_para_esta_ruta",
     "regla ae74-vinculo-r0-contrato/1 del contrato contrato-vinculo-r0/1, definida en AE-52 y escrita en los "
     "bytes del protocolo 1.2"),
    ("D5", "inaplicable_a_esta_ruta", "envoltorio del vinculo inverso; no se declara resuelta de forma general"),
    ("D6", "inaplicable_a_esta_ruta", "manifiesto externo; no se declara resuelta de forma general"),
    ("D7", "aprobada_por_el_operador",
     "pendientes solo en borradores sinteticos; un registro con pendientes nunca llega a R0 final y completarlos "
     "exige otro protocolo y otro registro"),
    ("D8", "sin_decidir", "plazo frente a corte; la puerta de recepcion antes del plazo queda sin evidencia"),
    ("D9", "espera_provisional_aprobada",
     "un texto marcador deja la completitud en espera (marcadores_textuales_sin_resolver) sin rechazar el borrador "
     "ni contar como valor suficiente; la politica definitiva de rechazo sigue sin decidir"),
)})

# ---------------------------------------------------------------------------
# Construccion
# ---------------------------------------------------------------------------


def construir_vinculo_del_contrato(declaracion: dict) -> dict:
    """Campo `declaracion_r0` de la version 1.2 a partir de una declaracion
    de AE-72 (D2): contrato, regla, esquema, hash y pendientes ordenados."""
    return {"contrato": CONTRATO, "regla": REGLA, "esquema_declaracion": _ae72.ESQUEMA_DECLARACION,
            "hash_declaracion": _ae72.hash_de_declaracion(declaracion),
            "pendientes": sorted(_ae72.elementos_pendientes(declaracion))}


def construir_protocolo_del_contrato(declaracion: dict, *, protocolo_id: str, estrategia: dict,
                                     cortes: dict) -> dict:
    """Protocolo sintetico 1.2 del contrato (D7: solo sintetico)."""
    return _rp.construir_protocolo_con_contrato_r0(protocolo_id=protocolo_id, estrategia=estrategia, cortes=cortes,
                                                   pendientes=[], sintetico=True,
                                                   vinculo_r0=construir_vinculo_del_contrato(declaracion))


# ---------------------------------------------------------------------------
# Admision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultadoDePuerta:
    estado: str
    motivos: tuple[str, ...] = ()


@dataclass(frozen=True)
class InformeDeAdmision:
    contrato: str
    ruta: str
    detalle: str
    puertas: dict
    estados_alcanzados: tuple[str, ...]
    planos: dict
    protocolo_hash: str | None = None
    hash_declaracion: str | None = None
    predicciones_vinculadas: int = 0
    elementos: dict = field(default_factory=dict)
    pendientes: tuple[str, ...] = ()
    marcadores: tuple[str, ...] = ()
    omitidas: tuple = ()
    verificacion_de_la_ruta: str | None = None


def _aptitud() -> str:
    return "sin_evidencia" if _expediente.AUTORIZA_EVALUACION else "no_autorizada"


def _informe(ruta: str, detalle: str, puertas: dict, **campos) -> InformeDeAdmision:
    planos = {"integridad_de_bytes": puertas["vinculo_integro"].estado, "autenticacion_de_r0": "sin_evidencia",
              "recepcion_antes_del_plazo": "sin_evidencia", "completitud_y_unicidad_del_canal": "sin_evidencia",
              "aptitud_inferencial": _aptitud()}
    alcanzados = tuple(p for p in PUERTAS if puertas[p].estado == "superada")
    return InformeDeAdmision(CONTRATO, ruta, detalle, puertas, alcanzados, planos, **campos)


def _no_admitido(ruta: str, motivo: str, detalle: str, **campos) -> InformeDeAdmision:
    ajena = "ruta_no_admitida" if ruta not in ("registro_invalido",) else "registro_no_admitido"
    puertas = {"borrador_sintetico": ResultadoDePuerta("rechazada", (motivo,)),
               "vinculo_integro": ResultadoDePuerta("no_evaluable", (ajena,)),
               "declaracion_estructuralmente_completa": ResultadoDePuerta("no_evaluable", (ajena,)),
               "r0_final": ResultadoDePuerta("rechazada", (ajena, *_SIN_EVIDENCIA))}
    return _informe(ruta, detalle, puertas, **campos)


def evaluar_admision(entradas: Sequence[bytes], bytes_declaracion: bytes | None, *,
                     protocolo_hash_esperado: str | None = None,
                     objetivos_esperados: Sequence[tuple[str, int]] = ()) -> InformeDeAdmision:
    """Puertas de admision del contrato sobre un registro de AE-52 y los
    bytes de una declaracion. Las puertas son independientes: el vinculo se
    comprueba aunque la declaracion tenga pendientes. No hay entrada de
    evidencia: la puerta R0 final no puede superarse con lo que existe."""
    if not entradas:
        return _no_admitido("registro_invalido", "registro_vacio", "registro vacio")
    try:
        estado = _rp.validar_registro(list(entradas))
    except _rp.VinculoR0InvalidoError as error:
        return _no_admitido("registro_invalido", error.motivo, str(error))
    except _rp.RegistroProspectivoError as error:
        return _no_admitido("registro_invalido", "registro_invalido", str(error))
    protocolo = estado.protocolo
    protocolo_hash = estado.hash_protocolo
    vinculadas = len(estado.predicciones)
    if protocolo["esquema"] != ESQUEMA_DEL_PROTOCOLO:
        ruta_previa = _ae73.ruta_del_protocolo(protocolo)
        ruta = {_ae73.RUTA_AE73: "ruta_1_1_no_admitida", _ae73.RUTA_AE72: "ruta_ae72_no_admitida"}.get(
            ruta_previa, "sin_vinculo_r0")
        verificacion = _ae73.verificar_vinculo_r0(entradas, bytes_declaracion).estado_de_bytes
        return _no_admitido(ruta, ruta, "el contrato solo admite la version 1.2", protocolo_hash=protocolo_hash,
                            predicciones_vinculadas=vinculadas, verificacion_de_la_ruta=verificacion)
    vinculo = protocolo[_rp.CAMPO_VINCULO_R0]
    campos = dict(protocolo_hash=protocolo_hash, predicciones_vinculadas=vinculadas)
    declaracion, motivo_declaracion = None, None
    if bytes_declaracion is None:
        motivo_declaracion = "declaracion_ausente"
    else:
        try:
            declaracion = _ae72.leer_declaracion(bytes_declaracion)
        except _ae72.DeclaracionR0Invalida:
            motivo_declaracion = "declaracion_invalida"
    designado = hash_designado(_TOPOLOGIA_AE70, entradas[0], protocolo_hash,
                               ReglaDeVinculo(_TOPOLOGIA_AE70, _RUTA_DEL_HASH))
    designada = declaracion is not None and _rp.hash_entrada(bytes_declaracion) == designado
    pendientes_decl = tuple(sorted(_ae72.elementos_pendientes(declaracion))) if declaracion is not None else ()
    marcadores = _ae72.elementos_con_marcador(declaracion) if declaracion is not None else ()
    if declaracion is not None:
        campos.update(hash_declaracion=_rp.hash_entrada(bytes_declaracion),
                      elementos=_ae72.estados_de_elementos(declaracion),
                      pendientes=_ae72.elementos_pendientes(declaracion), marcadores=marcadores)
    omitidas = tuple(tuple(o) for o in objetivos_esperados if tuple(o) not in estado.predicciones)
    campos["omitidas"] = omitidas

    if protocolo_hash_esperado is not None and protocolo_hash_esperado != protocolo_hash:
        vinculo_integro = ResultadoDePuerta("rechazada", ("protocolo_hash_no_coincide",))
    elif motivo_declaracion == "declaracion_ausente":
        vinculo_integro = ResultadoDePuerta("pendiente", ("declaracion_ausente",))
    elif motivo_declaracion == "declaracion_invalida":
        vinculo_integro = ResultadoDePuerta("rechazada", ("declaracion_invalida",))
    elif not designada:
        vinculo_integro = ResultadoDePuerta("rechazada", ("hash_de_declaracion_no_coincide",))
    elif list(pendientes_decl) != vinculo["pendientes"]:
        vinculo_integro = ResultadoDePuerta("rechazada", ("pendientes_contradictorios",))
    elif omitidas:
        vinculo_integro = ResultadoDePuerta("rechazada", ("prediccion_omitida",))
    else:
        vinculo_integro = ResultadoDePuerta("superada")

    if motivo_declaracion == "declaracion_ausente":
        completa = ResultadoDePuerta("no_evaluable", ("declaracion_ausente",))
    elif motivo_declaracion == "declaracion_invalida":
        completa = ResultadoDePuerta("rechazada", ("declaracion_invalida",))
    elif not designada:
        completa = ResultadoDePuerta("no_evaluable", ("declaracion_no_designada",))
    else:
        espera = tuple(m for m, activo in (("elementos_pendientes", pendientes_decl),
                                           ("marcadores_textuales_sin_resolver", marcadores)) if activo)
        completa = ResultadoDePuerta("pendiente", espera) if espera else ResultadoDePuerta("superada")

    bloqueos = []
    if protocolo["sintetico"] is True:
        bloqueos.append("protocolo_sintetico")
    if vinculo["pendientes"]:
        bloqueos.append("registro_con_pendientes")
    if vinculo_integro.estado != "superada":
        bloqueos.append("vinculo_no_integro")
    if completa.estado != "superada":
        bloqueos.append("declaracion_incompleta")
    r0_final = ResultadoDePuerta("rechazada" if bloqueos else "pendiente", (*bloqueos, *_SIN_EVIDENCIA))

    puertas = {"borrador_sintetico": ResultadoDePuerta("superada"), "vinculo_integro": vinculo_integro,
               "declaracion_estructuralmente_completa": completa, "r0_final": r0_final}
    return _informe("contrato_1_2", "registro 1.2 del contrato evaluado por puertas", puertas, **campos)


# ---------------------------------------------------------------------------
# Transiciones
# ---------------------------------------------------------------------------

TRANSICIONES = MappingProxyType({
    ("borrador_con_pendientes", "declaracion_estructuralmente_completa"): "solo_con_otro_protocolo_y_otro_registro",
    ("marcadores_textuales_sin_resolver", "declaracion_estructuralmente_completa"):
        "solo_con_otro_protocolo_y_otro_registro",
    ("declaracion_estructuralmente_completa", "borrador_con_pendientes"): "solo_con_otro_protocolo_y_otro_registro",
    ("ruta_ae72", "contrato_1_2"): "solo_con_otro_protocolo_y_otro_registro",
    ("ruta_1_1", "contrato_1_2"): "solo_con_otro_protocolo_y_otro_registro",
    ("borrador_con_pendientes", "r0_final"): "prohibida",
    ("marcadores_textuales_sin_resolver", "r0_final"): "prohibida",
    ("declaracion_estructuralmente_completa", "r0_final"): "prohibida_sin_evidencia",
    ("r0_final", "borrador_con_pendientes"): "prohibida",
})
"""Cambios de estado de un registro. Cambiar la declaracion cambia el hash
y el protocolo, y AE-52 no admite un segundo protocolo en el registro."""

# ---------------------------------------------------------------------------
# Demostracion reproducible
# ---------------------------------------------------------------------------

ESCENARIOS_DE_DEMOSTRACION = (
    "declaracion_completa", "borrador_con_pendientes", "marcadores_textuales", "declaracion_ausente",
    "declaracion_cambiada", "pendientes_contradictorios", "prediccion_omitida", "protocolo_hash_equivocado",
    "prediccion_con_protocolo_equivocado", "ruta_ae72", "ruta_1_1", "sin_vinculo_1_0", "vinculo_doble",
    "migracion_parcial_1_1_con_contrato", "migracion_parcial_1_2_sin_campo", "version_desconocida",
)
_ESTRATEGIA_DEMO = {"nombre": "estrategia_sintetica", "descripcion": "demostracion sintetica de AE-74",
                    "huella_codigo": "0" * 64, "archivos_codigo": ["sintetico.py"], "parametros": {"semilla": 1},
                    "entorno": {"python": "3.x"}}
_CORTES_DEMO = {"BALOTO": 2713}


def _elementos_demo(valor="demostracion", pendientes=(), marcadores=()):
    elementos = {e: {"estado": "declarado_sintetico", "valor": {"sintetico": f"{valor}-{i}"}}
                 for i, e in enumerate(_ae72.ELEMENTOS_DE_R0)}
    for e in pendientes:
        elementos[e] = {"estado": "pendiente"}
    for e in marcadores:
        elementos[e] = {"estado": "declarado_sintetico", "valor": "TBD"}
    return elementos


def _resumen(informe: InformeDeAdmision) -> dict:
    resumen = {"ruta": informe.ruta, **{p: informe.puertas[p].estado for p in PUERTAS}}
    resumen["motivos"] = {p: informe.puertas[p].motivos for p in PUERTAS}
    return resumen


def demostrar_estados(historico_sintetico: Sequence) -> dict:
    """Recorre con datos sinteticos cada escenario de ESCENARIOS_DE_DEMOSTRACION
    y devuelve, por escenario, la ruta y el estado y motivos de cada puerta.
    El historico lo aporta quien llama; el objetivo es el sorteo siguiente."""
    objetivo = max(r.numero_sorteo for r in historico_sintetico) + 1
    lista = list(_ae72.ELEMENTOS_DE_R0)

    def registrar(protocolo):
        entradas = [_rp.serializar_entrada(protocolo)]
        prediccion = _rp.nueva_prediccion(_rp.validar_registro(entradas), "BALOTO", objetivo, historico_sintetico,
                                          [0.1] * 43)
        return [*entradas, _rp.serializar_entrada(prediccion)]

    def contrato(elementos):
        declaracion = _ae72.construir_declaracion(elementos)
        protocolo = construir_protocolo_del_contrato(declaracion, protocolo_id="demostracion-ae74",
                                                     estrategia=_ESTRATEGIA_DEMO, cortes=_CORTES_DEMO)
        return declaracion, _ae72.bytes_de_declaracion(declaracion), protocolo, registrar(protocolo)

    declaracion, bd, protocolo, entradas = contrato(_elementos_demo())
    otra = _ae72.bytes_de_declaracion(_ae72.construir_declaracion(_elementos_demo("cambiada")))
    con_pendiente = _ae72.construir_declaracion(_elementos_demo(pendientes=(lista[2],)))
    contradictorio = _rp.construir_protocolo_con_contrato_r0(
        protocolo_id="demostracion-ae74", estrategia=_ESTRATEGIA_DEMO, cortes=_CORTES_DEMO, pendientes=[],
        sintetico=True, vinculo_r0={**construir_vinculo_del_contrato(con_pendiente), "pendientes": []})
    prediccion = _rp.leer_entrada(entradas[1])
    ajena = _rp.serializar_entrada({**prediccion, "protocolo_hash": "f" * 64})
    base_10 = _rp.construir_protocolo(protocolo_id="demostracion-ae74", estrategia=_ESTRATEGIA_DEMO,
                                      cortes=_CORTES_DEMO, pendientes=[], sintetico=True)
    doble = copy.deepcopy(protocolo)
    doble["estrategia"]["parametros"][_ae72.CLAVE_RESERVADA] = {"regla": _ae72.REGLA_CANDIDATA}
    parcial_11 = {**protocolo, "esquema": _rp.ESQUEMA_ENTRADA_PROTOCOLO_VINCULO_R0}
    parcial_12 = {k: v for k, v in protocolo.items() if k != _rp.CAMPO_VINCULO_R0}
    desconocida = {**protocolo, "esquema": "registro-prospectivo-ml/1.9"}

    borrador = contrato(_elementos_demo(pendientes=(lista[3],)))
    marcada = contrato(_elementos_demo(marcadores=(lista[5],)))
    escenarios = {
        "declaracion_completa": (entradas, bd, {}),
        "borrador_con_pendientes": (borrador[3], borrador[1], {}),
        "marcadores_textuales": (marcada[3], marcada[1], {}),
        "declaracion_ausente": (entradas, None, {}),
        "declaracion_cambiada": (entradas, otra, {}),
        "pendientes_contradictorios": (registrar(contradictorio), _ae72.bytes_de_declaracion(con_pendiente), {}),
        "prediccion_omitida": (entradas, bd, {"objetivos_esperados": (("BALOTO", objetivo), ("BALOTO", objetivo + 1))}),
        "protocolo_hash_equivocado": (entradas, bd, {"protocolo_hash_esperado": "0" * 64}),
        "prediccion_con_protocolo_equivocado": ([entradas[0], ajena], bd, {}),
        "ruta_ae72": (registrar(_ae72.construir_protocolo_candidato(
            declaracion, protocolo_id="demostracion-ae74", estrategia=_ESTRATEGIA_DEMO, cortes=_CORTES_DEMO)), bd, {}),
        "ruta_1_1": (registrar(_ae73.construir_protocolo_con_campo_explicito(
            declaracion, protocolo_id="demostracion-ae74", estrategia=_ESTRATEGIA_DEMO, cortes=_CORTES_DEMO)), bd, {}),
        "sin_vinculo_1_0": (registrar(base_10), bd, {}),
        "vinculo_doble": ([_rp.serializar_entrada(doble)], bd, {}),
        "migracion_parcial_1_1_con_contrato": ([_rp.serializar_entrada(parcial_11)], bd, {}),
        "migracion_parcial_1_2_sin_campo": ([_rp.serializar_entrada(parcial_12)], bd, {}),
        "version_desconocida": ([_rp.serializar_entrada(desconocida)], bd, {}),
    }
    return {nombre: _resumen(evaluar_admision(escenarios[nombre][0], escenarios[nombre][1], **escenarios[nombre][2]))
            for nombre in ESCENARIOS_DE_DEMOSTRACION}


# ---------------------------------------------------------------------------
# Compatibilidad, requisitos y limites
# ---------------------------------------------------------------------------

RUTAS_COMPATIBLES = MappingProxyType({
    "1_0": MappingProxyType({
        "admitida_por_el_contrato": False,
        "texto": "protocolos 1.0 sin vinculo; bytes y hashes sin cambios"}),
    "ae72_parametros": MappingProxyType({
        "admitida_por_el_contrato": False,
        "texto": "ruta candidata de AE-72 en estrategia.parametros; su verificador sigue disponible sin cambios"}),
    "1_1_campo_explicito": MappingProxyType({
        "admitida_por_el_contrato": False,
        "texto": "version optativa 1.1 de AE-73; bytes, validacion y verificador sin cambios"}),
    "1_2_contrato": MappingProxyType({
        "admitida_por_el_contrato": True,
        "texto": "version 1.2 con contrato y regla en los bytes; unica ruta que este contrato evalua por puertas"}),
})

REQUISITOS_FALTANTES = (
    "autenticacion_de_r0: firma o custodia verificable de la declaracion, que el repositorio no tiene",
    "recepcion_antes_del_plazo: sello o recepcion externa con reloj y margen, y la definicion del plazo (D8)",
    "completitud_y_unicidad_del_canal: canal con recibos y revision completa",
    "protocolo_real: la version 1.2 solo admite protocolos sinteticos y un protocolo real de AE-52 sigue siendo "
    "borrador sin predicciones; levantarlo exige otra decision y otra etapa validada",
    "D9: politica definitiva de rechazo de textos marcadores",
    "autorizacion_de_evaluacion: AUTORIZA_EVALUACION sigue en False, con los bloqueos de AE-39 y AE-41 vigentes",
)

COMPATIBILIDAD = (
    "1.0 y 1.1 conservan bytes, hashes, validacion y verificadores; la ruta de AE-72 tambien. Ninguna de las tres es "
    "admitida por este contrato. El verificador de AE-73 no conoce la version 1.2 y la informa como "
    "protocolo_sin_vinculo_r0; para 1.2 se usa evaluar_admision. Una prueba de AE-73 usaba 1.2 como ejemplo de "
    "version desconocida; ahora usa 1.9 con la misma intencion")

LIMITES = (
    "un hash coincidente, una lista vacia de pendientes o las pruebas sinteticas no aportan autenticacion, "
    "recepcion antes del plazo, estado de R0 final ni aptitud para evaluacion. La puerta R0 final no tiene "
    "entrada de evidencia y no puede superarse. Lo verificado de RFC 9162 cubre certificados y precertificados y no "
    "se atribuye a estas entradas")
