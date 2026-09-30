"""
Expediente preparatorio de autenticacion de R0 y recepcion de predicciones
-Etapa AE-76, validada localmente como trabajo preparatorio (solo el
expediente sintetico y sus pruebas; r0_final sigue rechazada).

Tres piezas versionadas, en JSON canonico de AE-52 y firmadas con Ed25519
(`cryptography`):

- `sobre-autenticacion-r0/1`: vincula la declaracion R0, el hash del
  protocolo 1.2, el contrato, la regla, el alcance de la firma y la huella de
  la clave que firma;
- `acuse-recepcion-prediccion/1`: un acuse por prediccion, ligado al
  protocolo, al juego, al objetivo, al canal, a una secuencia y al acuse
  anterior;
- `cierre-canal-predicciones/1`: manifiesto que declara el conjunto de
  objetivos, la lista ordenada de acuses, su total, su cabeza y si se declara
  completo.

Una firma correcta solo prueba integridad frente a una clave. La clave debe
estar admitida explicitamente, y en AE-76 solo existen claves de fixture:
identidad del firmante, publicacion fuera de banda y reconocimiento del
operador quedan en planos separados y pendientes. El cierre distingue tres
niveles de completitud:

- respecto del manifiesto recibido;
- respecto del registro presentado;
- respecto de todo lo que debio existir, siempre pendiente sin evidencia
  externa.

Una secuencia o una hora declaradas por el canal no prueban recepcion
anterior al plazo, y el sello de AE-75 cubre el compromiso R0 por objetivo,
no cada prediccion. El informe conjunto lee AE-74 y AE-75 sin cambiar sus
puertas ni sus planos: `r0_final` sigue rechazada y
`AUTORIZA_EVALUACION = False`.

D8 sigue aprobada solo para el modelo sintetico y D9 con su espera
provisional; R0, R9 y las ocho condiciones siguen `sin_fijar`. Sin red,
reloj local, claves operativas, datos reales ni PostgreSQL.
"""
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from app.application.ml import contrato_vinculo_r0 as _contrato
from app.application.ml import propuesta_inferencia_prospectiva as _expediente
from app.application.ml import registro_prospectivo as _rp
from app.application.ml import sello_temporal_r0 as _sello

ESQUEMA_SOBRE = "sobre-autenticacion-r0/1"
ESQUEMA_ACUSE = "acuse-recepcion-prediccion/1"
ESQUEMA_CIERRE = "cierre-canal-predicciones/1"
ALCANCE_DE_LA_FIRMA = "declaracion_r0_y_protocolo_1_2_del_contrato"
ALGORITMO_DE_FIRMA = "ed25519"
CLAVES_DEL_SOBRE = ("esquema", "contrato", "esquema_del_protocolo", "regla", "protocolo_hash", "hash_declaracion",
                    "alcance", "algoritmo", "huella_de_clave")
CLAVES_DEL_ACUSE = ("esquema", "canal", "protocolo_hash", "prediccion_hash", "codigo_juego", "sorteo_objetivo",
                    "secuencia", "acuse_anterior", "hora_declarada_utc", "algoritmo", "huella_de_clave")
CLAVES_DEL_CIERRE = ("esquema", "canal", "protocolo_hash", "conjunto_declarado", "acuses", "total", "cabeza",
                     "declara_completo", "algoritmo", "huella_de_clave")
ROLES_DE_CLAVE = ("firmante_r0", "canal")
NATURALEZAS_DE_CLAVE = ("fixture_de_prueba",)
CLAVES_OPERATIVAS_ADMITIDAS = ()
"""Ninguna: AE-76 no elige autoridad, identidad ni politica de firmas
operativa."""
_HEX64 = re.compile(r"[0-9a-f]{64}")
_CANAL = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


class ExpedienteInvalido(ValueError):
    """Pieza que no puede construirse; `motivo` es la causa."""

    def __init__(self, motivo: str, detalle: str = ""):
        super().__init__(motivo, detalle)

    @property
    def motivo(self) -> str:
        return self.args[0]

    def __str__(self) -> str:
        return f"{self.args[0]}: {self.args[1]}" if self.args[1] else self.args[0]


# ---------------------------------------------------------------------------
# Politica de claves (solo fixtures) y objetos firmados
# ---------------------------------------------------------------------------

def huella_de_clave(clave_publica: bytes) -> str:
    """SHA-256 de los 32 bytes de una clave publica Ed25519."""
    return hashlib.sha256(clave_publica).hexdigest()


@dataclass(frozen=True)
class ClaveDePrueba:
    """Clave publica Ed25519 de fixture admitida para un rol. No existe otra
    naturaleza: una clave operativa exige otra decision y otra etapa."""
    clave_publica: bytes
    rol: str
    etiqueta: str
    naturaleza: str = "fixture_de_prueba"

    def __post_init__(self):
        if self.naturaleza not in NATURALEZAS_DE_CLAVE:
            raise ValueError(f"naturaleza de clave no admitida en AE-76: {self.naturaleza!r}")
        if self.rol not in ROLES_DE_CLAVE:
            raise ValueError(f"rol de clave desconocido: {self.rol!r}")
        if not isinstance(self.clave_publica, bytes) or len(self.clave_publica) != 32:
            raise ValueError("la clave publica Ed25519 debe tener 32 bytes")


@dataclass(frozen=True)
class PoliticaDeClavesDePrueba:
    """Lista explicita de claves de fixture admitidas por rol."""
    claves: tuple

    def __post_init__(self):
        if not all(isinstance(c, ClaveDePrueba) for c in self.claves):
            raise ValueError("solo se admiten claves de prueba")

    def admite(self, clave_publica: bytes, rol: str) -> bool:
        return any(c.clave_publica == clave_publica and c.rol == rol for c in self.claves)


@dataclass(frozen=True)
class ObjetoFirmado:
    """Bytes canonicos de una pieza, firma Ed25519 y clave publica aportada
    por el expediente."""
    datos: bytes
    firma: bytes
    clave_publica: bytes


@dataclass(frozen=True)
class Resultado:
    estado: str
    motivos: tuple = ()


_OK = Resultado("superada")


def _r(estado: str, *motivos: str) -> Resultado:
    return Resultado(estado, tuple(motivos))


def bytes_canonicos(pieza: dict) -> bytes:
    """JSON canonico de AE-52 (claves ordenadas, UTF-8, LF final)."""
    return _rp.serializar_entrada(pieza)


def hash_de_pieza(datos: bytes) -> str:
    return _rp.hash_entrada(datos)


def _leer(datos: bytes, esquema: str, claves: tuple) -> dict:
    try:
        pieza = json.loads(datos.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ExpedienteInvalido("pieza_ilegible", str(error)) from error
    if not isinstance(pieza, dict):
        raise ExpedienteInvalido("pieza_ilegible", "no es un objeto")
    if pieza.get("esquema") != esquema:
        raise ExpedienteInvalido("version_desconocida", str(pieza.get("esquema")))
    if set(pieza) != set(claves):
        raise ExpedienteInvalido("pieza_ilegible", "claves distintas de las de la version 1")
    if bytes_canonicos(pieza) != datos:
        raise ExpedienteInvalido("pieza_no_canonica")
    return pieza


def _ed25519():
    """Carga diferida: sin `cryptography` la integridad queda pendiente."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    return Ed25519PublicKey, InvalidSignature


def _firma(objeto: ObjetoFirmado, pieza: dict | None, politica: PoliticaDeClavesDePrueba, rol: str) -> dict:
    """Planos separados de una firma: integridad matematica, clave admitida
    para el rol y huella declarada dentro de los bytes firmados."""
    try:
        Ed25519PublicKey, InvalidSignature = _ed25519()
    except ImportError:
        integridad = _r("pendiente", "dependencia_criptografica_ausente")
    else:
        try:
            Ed25519PublicKey.from_public_bytes(objeto.clave_publica).verify(objeto.firma, objeto.datos)
            integridad = _OK
        except InvalidSignature:
            integridad = _r("rechazada", "firma_no_coincide")
        except ValueError:
            integridad = _r("rechazada", "clave_mal_formada")
    admitida = _OK if politica.admite(objeto.clave_publica, rol) else _r("rechazada", "clave_no_admitida")
    if pieza is None:
        huella = _r("no_evaluable", "pieza_ilegible")
    elif pieza.get("algoritmo") != ALGORITMO_DE_FIRMA:
        huella = _r("rechazada", "algoritmo_no_admitido")
    elif pieza.get("huella_de_clave") != huella_de_clave(objeto.clave_publica):
        huella = _r("rechazada", "huella_de_clave_no_coincide")
    else:
        huella = _OK
    return {"integridad_de_la_firma": integridad, "clave_admitida_de_prueba": admitida, "huella_declarada": huella}


def _registro_del_contrato(entradas: Sequence[bytes], bytes_declaracion: bytes | None):
    admision = _contrato.evaluar_admision(entradas, bytes_declaracion)
    if admision.ruta != "contrato_1_2":
        raise ExpedienteInvalido("ruta_no_admitida", admision.ruta)
    if admision.puertas["vinculo_integro"].estado != "superada":
        raise ExpedienteInvalido("vinculo_no_integro", ",".join(admision.puertas["vinculo_integro"].motivos))
    return admision, _rp.validar_registro(list(entradas))


# ---------------------------------------------------------------------------
# 1. Autenticacion preparatoria de R0
# ---------------------------------------------------------------------------

PLANOS_DE_AUTENTICACION = ("integridad_de_la_firma", "clave_admitida_de_prueba", "huella_declarada",
                           "vinculo_con_el_registro", "identidad_del_firmante", "publicacion_fuera_de_banda",
                           "reconocimiento_del_operador")
PENDIENTES_DE_AUTENTICACION = MappingProxyType({
    "identidad_del_firmante": "sin_autoridad_de_firma_operativa",
    "publicacion_fuera_de_banda": "sin_evidencia_de_publicacion_fuera_de_banda",
    "reconocimiento_del_operador": "sin_reconocimiento_del_operador",
})
"""Planos que ninguna firma de fixture puede superar."""


def construir_sobre(entradas: Sequence[bytes], bytes_declaracion: bytes, *, clave_publica: bytes) -> dict:
    """Sobre de autenticacion sobre un registro 1.2 del contrato con vinculo
    integro. La huella de la clave queda dentro de los bytes firmados."""
    admision, estado = _registro_del_contrato(entradas, bytes_declaracion)
    vinculo = estado.protocolo[_rp.CAMPO_VINCULO_R0]
    return {"esquema": ESQUEMA_SOBRE, "contrato": vinculo["contrato"],
            "esquema_del_protocolo": estado.protocolo["esquema"], "regla": vinculo["regla"],
            "protocolo_hash": admision.protocolo_hash, "hash_declaracion": admision.hash_declaracion,
            "alcance": ALCANCE_DE_LA_FIRMA, "algoritmo": ALGORITMO_DE_FIRMA,
            "huella_de_clave": huella_de_clave(clave_publica)}


def leer_sobre(datos: bytes) -> dict:
    return _leer(datos, ESQUEMA_SOBRE, CLAVES_DEL_SOBRE)


@dataclass(frozen=True)
class InformeDeAutenticacion:
    planos: dict
    estado: str
    motivos: tuple


def verificar_autenticacion(entradas: Sequence[bytes], bytes_declaracion: bytes | None,
                            objeto: ObjetoFirmado | None, politica: PoliticaDeClavesDePrueba) -> InformeDeAutenticacion:
    """Autenticacion preparatoria de R0. Nunca supera: en el mejor caso queda
    pendiente de identidad, publicacion fuera de banda y reconocimiento."""
    pendientes = {p: _r("pendiente", m) for p, m in PENDIENTES_DE_AUTENTICACION.items()}
    if objeto is None:
        planos = {p: pendientes.get(p, _r("no_evaluable", "sin_sobre")) for p in PLANOS_DE_AUTENTICACION}
        return InformeDeAutenticacion(planos, "sin_evidencia", ())
    try:
        sobre = leer_sobre(objeto.datos)
    except ExpedienteInvalido as error:
        sobre, lectura = None, _r("rechazada", error.motivo)
    else:
        lectura = None
    planos = _firma(objeto, sobre, politica, "firmante_r0")
    if lectura is not None:
        planos["vinculo_con_el_registro"] = lectura
    else:
        planos["vinculo_con_el_registro"] = _vinculo_del_sobre(sobre, entradas, bytes_declaracion)
    planos.update(pendientes)
    planos = {p: planos[p] for p in PLANOS_DE_AUTENTICACION}
    rechazos = tuple(dict.fromkeys(m for r in planos.values() if r.estado == "rechazada" for m in r.motivos))
    if rechazos:
        return InformeDeAutenticacion(planos, "rechazada", rechazos)
    espera = tuple(dict.fromkeys(m for r in planos.values() if r.estado == "pendiente" for m in r.motivos))
    return InformeDeAutenticacion(planos, "pendiente", espera)


def _vinculo_del_sobre(sobre: dict, entradas, bytes_declaracion) -> Resultado:
    try:
        admision, estado = _registro_del_contrato(entradas, bytes_declaracion)
    except ExpedienteInvalido as error:
        return _r("rechazada", "sobre_no_corresponde_al_registro", error.motivo)
    vinculo = estado.protocolo[_rp.CAMPO_VINCULO_R0]
    motivos = []
    if sobre["protocolo_hash"] != admision.protocolo_hash:
        motivos.append("protocolo_hash_no_coincide")
    if sobre["hash_declaracion"] != admision.hash_declaracion:
        motivos.append("hash_de_declaracion_no_coincide")
    if (sobre["contrato"], sobre["regla"], sobre["esquema_del_protocolo"]) != (
            vinculo["contrato"], vinculo["regla"], estado.protocolo["esquema"]):
        motivos.append("contrato_o_regla_no_coincide")
    if sobre["alcance"] != ALCANCE_DE_LA_FIRMA:
        motivos.append("alcance_no_admitido")
    return _r("rechazada", "sobre_no_corresponde_al_registro", *motivos) if motivos else _OK


# ---------------------------------------------------------------------------
# 2. Acuses y cierre del canal
# ---------------------------------------------------------------------------

def construir_acuse(entradas: Sequence[bytes], *, canal: str, codigo_juego: str, sorteo_objetivo: int,
                    secuencia: int, acuse_anterior: str | None, hora_declarada_utc: str,
                    clave_publica: bytes) -> dict:
    """Acuse de la prediccion registrada para (juego, objetivo). La hora es
    la que declara el canal: se conserva, pero no prueba nada."""
    estado = _rp.validar_registro(list(entradas))
    if not isinstance(canal, str) or not _CANAL.fullmatch(canal):
        raise ExpedienteInvalido("canal_mal_formado", str(canal))
    clave = (codigo_juego, sorteo_objetivo)
    if clave not in estado.predicciones:
        raise ExpedienteInvalido("prediccion_desconocida", f"{codigo_juego} {sorteo_objetivo}")
    if type(secuencia) is not int or secuencia < 1:
        raise ExpedienteInvalido("secuencia_mal_formada", str(secuencia))
    if (secuencia == 1) != (acuse_anterior is None) or (acuse_anterior is not None
                                                          and not _HEX64.fullmatch(acuse_anterior)):
        raise ExpedienteInvalido("encadenamiento_mal_formado")
    _sello.instante_de_plazo(hora_declarada_utc)
    return {"esquema": ESQUEMA_ACUSE, "canal": canal, "protocolo_hash": estado.hash_protocolo,
            "prediccion_hash": estado.predicciones[clave], "codigo_juego": codigo_juego,
            "sorteo_objetivo": sorteo_objetivo, "secuencia": secuencia, "acuse_anterior": acuse_anterior,
            "hora_declarada_utc": hora_declarada_utc, "algoritmo": ALGORITMO_DE_FIRMA,
            "huella_de_clave": huella_de_clave(clave_publica)}


def construir_cierre(*, canal: str, protocolo_hash: str, conjunto_declarado: Sequence[tuple[str, int]],
                     acuses: Sequence[bytes], declara_completo: bool, clave_publica: bytes) -> dict:
    """Manifiesto del canal: conjunto de objetivos declarado, hashes de los
    acuses en su orden, total, cabeza y declaracion de completitud."""
    hashes = [hash_de_pieza(a) for a in acuses]
    return {"esquema": ESQUEMA_CIERRE, "canal": canal, "protocolo_hash": protocolo_hash,
            "conjunto_declarado": sorted([list(o) for o in conjunto_declarado]), "acuses": hashes,
            "total": len(hashes), "cabeza": hashes[-1] if hashes else None, "declara_completo": declara_completo,
            "algoritmo": ALGORITMO_DE_FIRMA, "huella_de_clave": huella_de_clave(clave_publica)}


def _entero_positivo(valor) -> bool:
    return type(valor) is int and valor >= 1


def _hash_hex(valor) -> bool:
    return isinstance(valor, str) and _HEX64.fullmatch(valor) is not None


def leer_acuse(datos: bytes) -> dict:
    acuse = _leer(datos, ESQUEMA_ACUSE, CLAVES_DEL_ACUSE)
    tipos = (isinstance(acuse["canal"], str) and _hash_hex(acuse["protocolo_hash"])
             and _hash_hex(acuse["prediccion_hash"]) and isinstance(acuse["codigo_juego"], str)
             and _entero_positivo(acuse["sorteo_objetivo"]) and _entero_positivo(acuse["secuencia"])
             and (acuse["acuse_anterior"] is None or _hash_hex(acuse["acuse_anterior"]))
             and isinstance(acuse["hora_declarada_utc"], str))
    if not tipos:
        raise ExpedienteInvalido("pieza_mal_formada", "tipos del acuse")
    return acuse


def leer_cierre(datos: bytes) -> dict:
    cierre = _leer(datos, ESQUEMA_CIERRE, CLAVES_DEL_CIERRE)
    lista = cierre["acuses"]
    conjunto = cierre["conjunto_declarado"]
    tipos = (isinstance(cierre["canal"], str) and _hash_hex(cierre["protocolo_hash"])
             and isinstance(lista, list) and all(_hash_hex(h) for h in lista)
             and isinstance(conjunto, list) and all(isinstance(o, list) and len(o) == 2 and isinstance(o[0], str)
                                                    and _entero_positivo(o[1]) for o in conjunto)
             and type(cierre["total"]) is int and (cierre["cabeza"] is None or _hash_hex(cierre["cabeza"]))
             and type(cierre["declara_completo"]) is bool)
    if not tipos:
        raise ExpedienteInvalido("pieza_mal_formada", "tipos del cierre")
    return cierre


NIVELES_DE_COMPLETITUD = ("respecto_del_manifiesto", "respecto_del_registro_presentado",
                          "respecto_de_lo_que_debio_existir")
EVIDENCIA_EXTERNA_FALTANTE = (
    "un calendario oficial identificado, versionado y publicado antes del cierre que fije los objetivos esperados",
    "una bitacora externa de solo anexado, con monitores independientes, donde el canal publique cada acuse",
    "la unicidad del canal: que no exista otro canal o registro con predicciones para el mismo protocolo",
    "un sello o recepcion independiente de cada acuse, no solo del compromiso R0 por objetivo",
    "la declaracion en R0 del canal, su clave y su politica de revocacion",
)
"""Lo que falta para pasar de completo respecto del manifiesto a completo
respecto de todo lo que debio existir."""
PENDIENTES_DE_RECEPCION = ("hora_declarada_por_el_canal_no_prueba_anterioridad",
                           "sello_ae75_cubre_el_compromiso_r0_no_cada_prediccion",
                           "sin_sello_independiente_de_cada_acuse")


@dataclass(frozen=True)
class InformeDelCanal:
    acuses: tuple
    cierre: dict
    completitud: dict
    recepcion_antes_del_plazo: Resultado
    estado: str
    motivos: tuple
    evidencia_externa_faltante: tuple = EVIDENCIA_EXTERNA_FALTANTE


def verificar_canal(entradas: Sequence[bytes], acuses: Sequence[ObjetoFirmado], cierre: ObjetoFirmado | None,
                    politica: PoliticaDeClavesDePrueba, *, canal: str) -> InformeDelCanal:
    """Comprueba cada acuse, la secuencia y el cierre. Detecta alteraciones,
    duplicados, omisiones, reordenamientos y una declaracion de completitud
    falsa frente al registro presentado."""
    estado = _rp.validar_registro(list(entradas))
    por_hash = {h: o for o, h in estado.predicciones.items()}
    informes, leidos = [], []
    for objeto in acuses:
        try:
            pieza = leer_acuse(objeto.datos)
            lectura = _OK
        except ExpedienteInvalido as error:
            pieza, lectura = None, _r("rechazada", error.motivo)
        planos = {"lectura": lectura, **_firma(objeto, pieza, politica, "canal")}
        if pieza is not None:
            motivos = []
            if pieza["canal"] != canal:
                motivos.append("canal_no_coincide")
            if pieza["protocolo_hash"] != estado.hash_protocolo:
                motivos.append("protocolo_hash_no_coincide")
            objetivo = por_hash.get(pieza["prediccion_hash"])
            if objetivo is None:
                motivos.append("prediccion_desconocida")
            elif objetivo != (pieza["codigo_juego"], pieza["sorteo_objetivo"]):
                motivos.append("acuse_de_otro_objetivo")
            planos["vinculo_con_el_registro"] = _r("rechazada", *motivos) if motivos else _OK
            leidos.append((hash_de_pieza(objeto.datos), pieza))
        informes.append(planos)

    motivos_canal = [m for p in informes for r in p.values() if r.estado == "rechazada" for m in r.motivos]
    motivos_canal += _secuencia(leidos)
    cierre_planos, cierre_pieza = _verificar_cierre(cierre, politica, estado, canal, leidos)
    motivos_canal += [m for r in cierre_planos.values() if r.estado == "rechazada" for m in r.motivos]
    motivos_canal = list(dict.fromkeys(motivos_canal))

    if motivos_canal:
        manifiesto = _r("rechazada", *motivos_canal)
    elif cierre_pieza is None:
        manifiesto = _r("pendiente", "sin_cierre")
    elif cierre_pieza["declara_completo"] is not True:
        manifiesto = _r("pendiente", "cierre_no_declara_completitud")
    else:
        manifiesto = _OK
    reconocidos = {(p["codigo_juego"], p["sorteo_objetivo"]) for _, p in leidos}
    if set(estado.predicciones) - reconocidos:
        registro = _r("rechazada", "prediccion_del_registro_sin_acuse")
    elif manifiesto.estado != "superada":
        registro = _r(manifiesto.estado, "completitud_del_manifiesto_no_superada")
    else:
        registro = _OK
    completitud = {"respecto_del_manifiesto": manifiesto, "respecto_del_registro_presentado": registro,
                   "respecto_de_lo_que_debio_existir": _r("pendiente", "sin_evidencia_externa_del_conjunto_esperado")}
    recepcion = _r("pendiente", *PENDIENTES_DE_RECEPCION)
    rechazos = tuple(dict.fromkeys([*motivos_canal, *(registro.motivos if registro.estado == "rechazada" else ())]))
    if rechazos:
        return InformeDelCanal(tuple(informes), cierre_planos, completitud, recepcion, "rechazada", rechazos)
    motivos = (*(m for m in (*manifiesto.motivos,) if manifiesto.estado == "pendiente"),
               "sin_evidencia_externa_del_conjunto_esperado", *PENDIENTES_DE_RECEPCION)
    return InformeDelCanal(tuple(informes), cierre_planos, completitud, recepcion, "pendiente", motivos)


def _secuencia(leidos) -> list:
    """Duplicados, huecos, orden de presentacion y encadenamiento por hash."""
    motivos = []
    hashes = [h for h, _ in leidos]
    predicciones = [p["prediccion_hash"] for _, p in leidos]
    secuencias = [p["secuencia"] for _, p in leidos]
    duplicado = any(len(set(v)) != len(v) for v in (hashes, predicciones, secuencias))
    if duplicado:
        motivos.append("acuse_duplicado")
    unicas = sorted(set(secuencias))
    if unicas != list(range(1, len(unicas) + 1)):
        motivos.append("secuencia_con_huecos")
    elif not duplicado and secuencias != unicas:
        motivos.append("orden_alterado")
    anterior = None
    for h, pieza in sorted(leidos, key=lambda x: x[1]["secuencia"]):
        if pieza["acuse_anterior"] != anterior:
            motivos.append("encadenamiento_roto")
            break
        anterior = h
    return motivos


def _verificar_cierre(cierre, politica, estado, canal, leidos):
    if cierre is None:
        return {"lectura": _r("pendiente", "sin_cierre")}, None
    try:
        pieza = leer_cierre(cierre.datos)
        lectura = _OK
    except ExpedienteInvalido as error:
        pieza, lectura = None, _r("rechazada", error.motivo)
    planos = {"lectura": lectura, **_firma(cierre, pieza, politica, "canal")}
    if pieza is None:
        return planos, None
    motivos = []
    if pieza["canal"] != canal:
        motivos.append("canal_no_coincide")
    if pieza["protocolo_hash"] != estado.hash_protocolo:
        motivos.append("protocolo_hash_no_coincide")
    presentados = [h for h, _ in sorted(leidos, key=lambda x: x[1]["secuencia"])]
    listados = pieza["acuses"]
    if set(listados) - set(presentados):
        motivos.append("acuse_omitido")
    if set(presentados) - set(listados):
        motivos.append("acuse_fuera_del_cierre")
    if set(listados) == set(presentados) and listados != presentados:
        motivos.append("orden_alterado")
    if len(listados) != len(set(listados)):
        motivos.append("acuse_duplicado")
    if pieza["total"] != len(listados) or pieza["cabeza"] != (listados[-1] if listados else None):
        motivos.append("total_o_cabeza_no_coincide")
    declarado = {tuple(o) for o in pieza["conjunto_declarado"]}
    reconocidos = [(p["codigo_juego"], p["sorteo_objetivo"]) for _, p in leidos]
    if declarado - set(reconocidos):
        motivos.append("omision_respecto_del_conjunto_declarado")
    if set(reconocidos) - declarado:
        motivos.append("acuse_fuera_del_conjunto_declarado")
    if pieza["declara_completo"] is True and set(estado.predicciones) - declarado:
        motivos.append("declaracion_de_completitud_falsa_frente_al_registro")
    planos["contenido"] = _r("rechazada", *dict.fromkeys(motivos)) if motivos else _OK
    return planos, pieza


# ---------------------------------------------------------------------------
# 3. Informe conjunto
# ---------------------------------------------------------------------------

PLANOS_PREPARATORIOS = ("autenticacion_preparatoria_de_r0", "cierre_del_canal",
                        "completitud_respecto_del_manifiesto", "completitud_respecto_del_registro_presentado",
                        "completitud_respecto_de_lo_que_debio_existir", "recepcion_preparatoria_antes_del_plazo")
ESTADOS_PREPARATORIOS = ("sin_evidencia", "rechazada", "pendiente", "superada", "no_evaluable")
"""`superada` solo aparece en la completitud respecto del manifiesto o del
registro presentado; ningun plano de AE-74 o AE-75 cambia por ello."""

DECISIONES_PENDIENTES_AE76 = MappingProxyType({id_: MappingProxyType({"estado": "sin_decidir", "texto": texto})
                                               for id_, texto in (
    ("A1", "autoridad e identidad del firmante de R0 y su politica de firmas operativa"),
    ("A2", "medio de publicacion fuera de banda del sobre y forma del reconocimiento del operador"),
    ("A3", "revocacion y custodia de las claves de firma y del canal"),
    ("C1", "canal operativo, su clave y su declaracion en R0"),
    ("C2", "evidencia temporal independiente de cada acuse"),
    ("C3", "fuente externa del conjunto de objetivos esperado y bitacora publica del canal"),
)})

LIMITES = (
    "las claves son de fixture: una firma correcta prueba integridad frente a una clave admitida en la prueba, no "
    "identidad, autoridad, publicacion ni reconocimiento",
    "completo respecto del manifiesto o del registro presentado no significa completo respecto de lo que debio "
    "existir; eso exige evidencia externa",
    "la secuencia y la hora del canal no prueban recepcion anterior al plazo; el sello de AE-75 cubre el compromiso "
    "R0 por objetivo, no cada prediccion",
    "el informe conjunto no cambia puertas ni planos de AE-74 y AE-75; r0_final sigue rechazada",
    "D8 sigue aprobada solo para el modelo sintetico y D9 con su espera provisional; calendario oficial, anclas "
    "operativas, revocacion, publicacion fuera de banda, autoridad del firmante y completitud global siguen "
    "pendientes",
)


@dataclass(frozen=True)
class InformeDelExpediente:
    admision: object
    autenticacion: InformeDeAutenticacion
    canal: InformeDelCanal | None
    planos: dict
    planos_preparatorios: dict
    r0_final: object
    autoriza_evaluacion: bool
    limites: tuple = LIMITES


def evaluar_expediente(entradas: Sequence[bytes], bytes_declaracion: bytes | None, *,
                       evidencias_de_sello: Mapping, politica_de_sello, sobre: ObjetoFirmado | None,
                       acuses: Sequence[ObjetoFirmado], cierre: ObjetoFirmado | None,
                       politica_de_claves: PoliticaDeClavesDePrueba, canal: str,
                       objetivos_esperados: Sequence[tuple[str, int]] = ()) -> InformeDelExpediente:
    """Informe conjunto. Los planos de AE-74 y AE-75 se copian sin cambios y
    los resultados de AE-76 van en planos preparatorios con otros nombres."""
    admision = _sello.evaluar_admision_con_plano_temporal(entradas, bytes_declaracion, evidencias_de_sello,
                                                          politica_de_sello, objetivos_esperados=objetivos_esperados)
    autenticacion = verificar_autenticacion(entradas, bytes_declaracion, sobre, politica_de_claves)
    if admision.admision.ruta == "contrato_1_2" and (acuses or cierre is not None):
        informe_canal = verificar_canal(entradas, acuses, cierre, politica_de_claves, canal=canal)
        preparatorios = {
            "cierre_del_canal": informe_canal.estado,
            **{f"completitud_{k}": v.estado for k, v in informe_canal.completitud.items()},
            "recepcion_preparatoria_antes_del_plazo": informe_canal.recepcion_antes_del_plazo.estado,
        }
    else:
        informe_canal = None
        preparatorios = {p: "sin_evidencia" for p in PLANOS_PREPARATORIOS[1:]}
    preparatorios = {"autenticacion_preparatoria_de_r0": autenticacion.estado, **preparatorios}
    return InformeDelExpediente(admision, autenticacion, informe_canal, dict(admision.planos),
                                {p: preparatorios[p] for p in PLANOS_PREPARATORIOS},
                                admision.admision.puertas["r0_final"], _expediente.AUTORIZA_EVALUACION)
