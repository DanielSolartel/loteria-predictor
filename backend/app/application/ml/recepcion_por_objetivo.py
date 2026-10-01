"""
Expediente de recepcion por objetivo: tiempo por acuse y conjunto esperado
externo -Etapa AE-77, validada localmente como trabajo preparatorio (solo
con claves, certificados, TSA y observador de fixture; r0_final sigue
rechazada).

Extiende la ruta sintetica AE-74 -> AE-75 -> AE-76 con dos piezas
independientes:

- Tiempo por acuse (C2): `compromiso-sello-acuse/1` fija el hash de los
  bytes del acuse firmado y de su firma, la huella de la clave del canal, el
  canal, el protocolo, la prediccion, el juego, el objetivo, la secuencia y
  un plazo UTC sintetico. Un token RFC 3161 sobre esos bytes se verifica con
  la misma ruta criptografica de AE-75 (`verificar_token_sobre_bytes`). Se
  separan sello criptografico, impronta, anterioridad relativa al plazo,
  confianza en el ancla y revocacion. Un sello del compromiso R0 nunca cuenta
  como sello de un acuse, y la hora declarada por el canal no se usa.
- Conjunto esperado externo (C3): `conjunto-esperado-observador/1`, firmado
  por un observador de fixture distinto del canal, declara los objetivos
  esperados para un corte sintetico. Se compara con el registro, los acuses y
  el cierre de AE-76, y las vistas encadenadas del observador se comprueban
  por continuidad y contradicciones. Eso no descarta historias ocultas ni
  prueba completitud global sin monitores independientes y una fuente
  autorizada.

El informe compuesto separa integridad de bytes, firmas y roles de prueba,
tiempo por acuse, completitud respecto del manifiesto presentado, autoridad
del manifiesto y completitud global; las dos ultimas quedan pendientes. El
informe de AE-76 (y con el AE-74 y AE-75) se conserva sin cambios:
`r0_final` sigue rechazada y `AUTORIZA_EVALUACION = False`. A1-A3 y C1-C3
siguen sin decidir; D8 sigue limitada al modelo sintetico y D9 con su espera
provisional. Sin red, reloj local, claves operativas ni datos reales.
"""
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from types import MappingProxyType

from app.application.ml import expediente_r0_recepcion as _ae76
from app.application.ml import propuesta_inferencia_prospectiva as _expediente
from app.application.ml import registro_prospectivo as _rp
from app.application.ml import sello_temporal_r0 as _sello

ESQUEMA_COMPROMISO_ACUSE = "compromiso-sello-acuse/1"
CLAVES_DEL_COMPROMISO_ACUSE = ("esquema", "hash_acuse", "hash_firma_acuse", "huella_de_clave_del_canal", "canal",
                               "protocolo_hash", "prediccion_hash", "codigo_juego", "sorteo_objetivo", "secuencia",
                               "plazo_utc", "procedencia_del_plazo")
ESQUEMA_CONJUNTO = "conjunto-esperado-observador/1"
CLAVES_DEL_CONJUNTO = ("esquema", "observador", "protocolo_hash", "corte_sintetico", "objetivos_esperados",
                       "secuencia", "anterior", "algoritmo", "huella_de_clave")
NATURALEZAS_DE_OBSERVADOR = ("fixture_de_prueba",)
OBSERVADORES_OPERATIVOS_ADMITIDOS = ()
"""Ninguno: AE-77 no elige autoridad ni fuente del conjunto esperado."""
_HEX64 = re.compile(r"[0-9a-f]{64}")
_OBSERVADOR = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


class _Invalido(ValueError):
    def __init__(self, motivo: str, detalle: str = ""):
        super().__init__(motivo, detalle)

    @property
    def motivo(self) -> str:
        return self.args[0]

    def __str__(self) -> str:
        return f"{self.args[0]}: {self.args[1]}" if self.args[1] else self.args[0]


class CompromisoDeAcuseInvalido(_Invalido):
    """Compromiso de acuse que no puede construirse o leerse."""


class ConjuntoEsperadoInvalido(_Invalido):
    """Declaracion del observador que no puede construirse o leerse."""


@dataclass(frozen=True)
class Resultado:
    estado: str
    motivos: tuple = ()


_OK = Resultado("superada")


def _r(estado: str, *motivos: str) -> Resultado:
    return Resultado(estado, tuple(dict.fromkeys(motivos)))


def _leer(datos: bytes, esquema: str, claves: tuple, error) -> dict:
    try:
        pieza = json.loads(datos.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as fallo:
        raise error("pieza_ilegible", str(fallo)) from fallo
    if not isinstance(pieza, dict):
        raise error("pieza_ilegible", "no es un objeto")
    if pieza.get("esquema") != esquema:
        raise error("version_desconocida", str(pieza.get("esquema")))
    if set(pieza) != set(claves):
        raise error("pieza_ilegible", "claves distintas de las de la version 1")
    try:
        canonicos = _rp.serializar_entrada(pieza)
    except _rp.EntradaRegistroInvalidaError as fallo:
        # NaN, Infinity y 1e999 (correccion incluida en AE-80).
        raise error("pieza_ilegible", "constante JSON no estandar") from fallo
    if canonicos != datos:
        raise error("pieza_no_canonica")
    return pieza


# ---------------------------------------------------------------------------
# 1. Tiempo por acuse (C2)
# ---------------------------------------------------------------------------

def construir_compromiso_de_acuse(entradas: Sequence[bytes], acuse: "_ae76.ObjetoFirmado", *, plazo_utc: str,
                                  procedencia_del_plazo: str = "sintetica_de_prueba") -> dict:
    """Compromiso inequivoco sobre un acuse firmado de AE-76 concreto: sus
    bytes, su firma, la clave del canal y su vinculo con la prediccion del
    registro. No comprueba la firma: eso lo hace la verificacion."""
    try:
        pieza = _ae76.leer_acuse(acuse.datos)
    except _ae76.ExpedienteInvalido as error:
        raise CompromisoDeAcuseInvalido("acuse_ilegible", error.motivo) from error
    estado = _rp.validar_registro(list(entradas))
    if estado.predicciones.get((pieza["codigo_juego"], pieza["sorteo_objetivo"])) != pieza["prediccion_hash"]:
        raise CompromisoDeAcuseInvalido("acuse_no_corresponde_al_registro")
    try:
        _sello.instante_de_plazo(plazo_utc)
    except ValueError as error:
        raise CompromisoDeAcuseInvalido("plazo_sin_utc_explicito", str(error)) from error
    if procedencia_del_plazo not in _sello.PROCEDENCIAS_DEL_PLAZO:
        raise CompromisoDeAcuseInvalido("procedencia_del_plazo_no_admitida", procedencia_del_plazo)
    return {"esquema": ESQUEMA_COMPROMISO_ACUSE, "hash_acuse": _ae76.hash_de_pieza(acuse.datos),
            "hash_firma_acuse": _ae76.hash_de_pieza(acuse.firma),
            "huella_de_clave_del_canal": _ae76.huella_de_clave(acuse.clave_publica), "canal": pieza["canal"],
            "protocolo_hash": pieza["protocolo_hash"], "prediccion_hash": pieza["prediccion_hash"],
            "codigo_juego": pieza["codigo_juego"], "sorteo_objetivo": pieza["sorteo_objetivo"],
            "secuencia": pieza["secuencia"], "plazo_utc": plazo_utc, "procedencia_del_plazo": procedencia_del_plazo}


def bytes_de_compromiso(compromiso: dict) -> bytes:
    """JSON canonico de AE-52."""
    return _rp.serializar_entrada(compromiso)


def leer_compromiso_de_acuse(datos: bytes) -> dict:
    return _leer(datos, ESQUEMA_COMPROMISO_ACUSE, CLAVES_DEL_COMPROMISO_ACUSE, CompromisoDeAcuseInvalido)


@dataclass(frozen=True)
class EvidenciaDeSelloDeAcuse:
    """Acuse firmado, TimeStampResp DER y bytes exactos del compromiso."""
    acuse: object
    respuesta_der: bytes
    bytes_compromiso: bytes


PLANOS_DE_TIEMPO = ("acuse_firmado", "vinculo_del_compromiso", "sello_criptografico", "impronta",
                    "anterioridad_relativa_al_plazo", "confianza_en_el_ancla", "revocacion")


@dataclass(frozen=True)
class InformeDeTiempoDeAcuse:
    planos: dict
    conclusion: object
    estado: str
    motivos: tuple


def _acuse_firmado(entradas, acuse, politica_de_claves, canal):
    try:
        pieza = _ae76.leer_acuse(acuse.datos)
    except _ae76.ExpedienteInvalido as error:
        firma = _ae76._firma(acuse, None, politica_de_claves, "canal")
        return _r("rechazada", error.motivo, *(m for r in firma.values() if r.estado == "rechazada"
                                              for m in r.motivos)), None
    firma = _ae76._firma(acuse, pieza, politica_de_claves, "canal")
    rechazos = [m for r in firma.values() if r.estado == "rechazada" for m in r.motivos]
    esperas = [m for r in firma.values() if r.estado in ("pendiente", "no_evaluable") for m in r.motivos]
    estado = _rp.validar_registro(list(entradas))
    if pieza["canal"] != canal:
        rechazos.append("canal_no_coincide")
    if estado.predicciones.get((pieza["codigo_juego"], pieza["sorteo_objetivo"])) != pieza["prediccion_hash"]:
        rechazos.append("acuse_no_corresponde_al_registro")
    if rechazos:
        return _r("rechazada", *rechazos), pieza
    return (_r("pendiente", *esperas) if esperas else _OK), pieza


def _vinculo(evidencia, pieza) -> tuple:
    try:
        compromiso = leer_compromiso_de_acuse(evidencia.bytes_compromiso)
    except CompromisoDeAcuseInvalido as error:
        try:
            _sello.leer_compromiso(evidencia.bytes_compromiso)
        except _sello.CompromisoInvalido:
            return _r("rechazada", error.motivo), None
        return _r("rechazada", "sello_de_r0_no_cuenta_como_sello_de_acuse"), None
    motivos = []
    acuse = evidencia.acuse
    if (compromiso["hash_acuse"] != _ae76.hash_de_pieza(acuse.datos)
            or compromiso["hash_firma_acuse"] != _ae76.hash_de_pieza(acuse.firma)
            or compromiso["huella_de_clave_del_canal"] != _ae76.huella_de_clave(acuse.clave_publica)):
        motivos.append("compromiso_de_otro_acuse")
    if pieza is not None:
        for campo in ("canal", "protocolo_hash", "prediccion_hash", "secuencia"):
            if compromiso[campo] != pieza[campo]:
                motivos.append(f"{campo}_no_coincide")
        if (compromiso["codigo_juego"], compromiso["sorteo_objetivo"]) != (pieza["codigo_juego"],
                                                                           pieza["sorteo_objetivo"]):
            motivos.append("objetivo_no_coincide")
    try:
        _sello.instante_de_plazo(compromiso["plazo_utc"])
    except ValueError:
        motivos.append("plazo_sin_utc_explicito")
    if compromiso["procedencia_del_plazo"] not in _sello.PROCEDENCIAS_DEL_PLAZO:
        motivos.append("procedencia_del_plazo_no_admitida")
    return (_r("rechazada", *motivos) if motivos else _OK), compromiso


def verificar_tiempo_de_acuse(entradas: Sequence[bytes], evidencia: EvidenciaDeSelloDeAcuse, politica_de_sello,
                              politica_de_claves, *, canal: str) -> InformeDeTiempoDeAcuse:
    """Tiempo de un acuse concreto. genTime solo se usa si el acuse, el
    vinculo, el sello criptografico y la impronta estan superados."""
    acuse, pieza = _acuse_firmado(entradas, evidencia.acuse, politica_de_claves, canal)
    vinculo, compromiso = _vinculo(evidencia, pieza)
    token = _sello.verificar_token_sobre_bytes(evidencia.respuesta_der, evidencia.bytes_compromiso, politica_de_sello)
    cripto = {k: v for k, v in token.comprobaciones_criptograficas.items() if k != "revocacion"}
    rechazos = [m for v in cripto.values() if v.estado == "rechazada" for m in v.motivos]
    esperas = [m for v in cripto.values() if v.estado in ("pendiente", "no_evaluable") for m in v.motivos]
    sello = _r("rechazada", *rechazos) if rechazos else (_r("pendiente", *esperas) if esperas else _OK)
    impronta = Resultado(token.impronta.estado, token.impronta.motivos)
    planos = {"acuse_firmado": acuse, "vinculo_del_compromiso": vinculo, "sello_criptografico": sello,
              "impronta": impronta}
    previos_superados = all(r.estado == "superada" for r in planos.values())
    if previos_superados:
        plazo = _sello.instante_de_plazo(compromiso["plazo_utc"])
        margen = _sello.segundos_decimales(politica_de_sello.margen)
        g, a = token.gen_time, token.precision
        resultado = _sello.comparar_con_plazo(g, a, margen, plazo)
        limites = {} if a is None else {"limite_inferior_utc": _sello.texto_utc(g - a - margen),
                                        "limite_superior_utc": _sello.texto_utc(g + a + margen)}
        conclusion = _sello.ConclusionTemporal(
            resultado, plazo_utc=compromiso["plazo_utc"], procedencia_del_plazo=compromiso["procedencia_del_plazo"],
            gen_time_utc=_sello.texto_utc(g), precision_segundos=None if a is None else _sello.texto_segundos(a),
            margen_segundos=_sello.texto_segundos(margen), condicionada_a=_sello.LIMITES_OPERATIVOS, **limites)
        planos["anterioridad_relativa_al_plazo"] = {
            "anterior_al_plazo": _OK,
            "no_concluyente_intervalo_cruza_el_plazo": _r("no_concluyente", "intervalo_cruza_el_plazo"),
            "posterior_al_plazo": _r("rechazada", "sello_posterior_al_plazo"),
            "precision_ausente_pendiente": _r("pendiente", "precision_ausente"),
        }[resultado]
    else:
        conclusion = _sello.ConclusionTemporal("no_evaluable")
        planos["anterioridad_relativa_al_plazo"] = _r("no_evaluable", "sello_o_vinculo_no_superado")
    planos["confianza_en_el_ancla"] = _r("pendiente", "ancla_de_prueba_no_operativa")
    planos["revocacion"] = _r("pendiente", "revocacion_sin_comprobar")

    rechazos = tuple(dict.fromkeys(m for r in planos.values() if r.estado == "rechazada" for m in r.motivos))
    if rechazos:
        return InformeDeTiempoDeAcuse(planos, conclusion, "rechazada", rechazos)
    if planos["anterioridad_relativa_al_plazo"].estado == "no_concluyente":
        return InformeDeTiempoDeAcuse(planos, conclusion, "no_concluyente", ("intervalo_cruza_el_plazo",))
    espera = tuple(dict.fromkeys(m for k, r in planos.items() if r.estado in ("pendiente", "no_evaluable")
                                 and k not in ("confianza_en_el_ancla", "revocacion") for m in r.motivos))
    return InformeDeTiempoDeAcuse(planos, conclusion, "pendiente", (*espera, *_sello.LIMITES_OPERATIVOS))


# ---------------------------------------------------------------------------
# 2. Conjunto esperado externo (C3)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClaveDeObservadorDePrueba:
    """Clave Ed25519 de un observador de fixture; no hay naturaleza
    operativa."""
    clave_publica: bytes
    etiqueta: str
    naturaleza: str = "fixture_de_prueba"

    def __post_init__(self):
        if self.naturaleza not in NATURALEZAS_DE_OBSERVADOR:
            raise ValueError(f"naturaleza de observador no admitida en AE-77: {self.naturaleza!r}")
        if not isinstance(self.clave_publica, bytes) or len(self.clave_publica) != 32:
            raise ValueError("la clave publica Ed25519 debe tener 32 bytes")


@dataclass(frozen=True)
class PoliticaDeObservadoresDePrueba:
    claves: tuple

    def __post_init__(self):
        if not all(isinstance(c, ClaveDeObservadorDePrueba) for c in self.claves):
            raise ValueError("solo se admiten claves de observador de prueba")


def construir_conjunto_esperado(entradas: Sequence[bytes], *, observador: str, corte_sintetico: int,
                                objetivos: Sequence[tuple[str, int]], secuencia: int, anterior: str | None,
                                clave_publica: bytes) -> dict:
    """Declaracion del observador para un corte sintetico. No exige que los
    objetivos tengan prediccion: la comparacion detecta las omisiones."""
    estado = _rp.validar_registro(list(entradas))
    if not isinstance(observador, str) or not _OBSERVADOR.fullmatch(observador):
        raise ConjuntoEsperadoInvalido("observador_mal_formado", str(observador))
    if type(corte_sintetico) is not int or type(secuencia) is not int or secuencia < 1:
        raise ConjuntoEsperadoInvalido("pieza_mal_formada")
    if (secuencia == 1) != (anterior is None):
        raise ConjuntoEsperadoInvalido("encadenamiento_mal_formado")
    return {"esquema": ESQUEMA_CONJUNTO, "observador": observador, "protocolo_hash": estado.hash_protocolo,
            "corte_sintetico": corte_sintetico, "objetivos_esperados": sorted([list(o) for o in objetivos]),
            "secuencia": secuencia, "anterior": anterior, "algoritmo": _ae76.ALGORITMO_DE_FIRMA,
            "huella_de_clave": _ae76.huella_de_clave(clave_publica)}


def leer_conjunto_esperado(datos: bytes) -> dict:
    pieza = _leer(datos, ESQUEMA_CONJUNTO, CLAVES_DEL_CONJUNTO, ConjuntoEsperadoInvalido)
    objetivos = pieza["objetivos_esperados"]
    tipos = (isinstance(pieza["observador"], str) and isinstance(pieza["protocolo_hash"], str)
             and type(pieza["corte_sintetico"]) is int and type(pieza["secuencia"]) is int and pieza["secuencia"] >= 1
             and (pieza["anterior"] is None or (isinstance(pieza["anterior"], str)
                                                and _HEX64.fullmatch(pieza["anterior"]) is not None))
             and isinstance(objetivos, list) and all(isinstance(o, list) and len(o) == 2 and isinstance(o[0], str)
                                                     and type(o[1]) is int for o in objetivos))
    if not tipos:
        raise ConjuntoEsperadoInvalido("pieza_mal_formada")
    return pieza


def _firma_del_observador(objeto, pieza, politica_obs, politica_claves) -> Resultado:
    """Integridad, clave admitida como observador, huella declarada e
    independencia respecto de toda clave admitida del canal."""
    admitidas = _ae76.PoliticaDeClavesDePrueba(claves=tuple(
        _ae76.ClaveDePrueba(c.clave_publica, "canal", c.etiqueta) for c in politica_obs.claves))
    firma = _ae76._firma(objeto, pieza, admitidas, "canal")
    motivos = [m for r in firma.values() if r.estado != "superada" for m in r.motivos]
    if politica_claves.admite(objeto.clave_publica, "canal") or politica_claves.admite(objeto.clave_publica,
                                                                                         "firmante_r0"):
        motivos.append("observador_no_independiente_del_canal")
    return _r("rechazada", *motivos) if motivos else _OK


PLANOS_DEL_CONJUNTO = ("lectura", "firma_del_observador", "vinculo_con_el_protocolo", "corte",
                       "frente_al_registro", "frente_a_los_acuses", "frente_al_cierre")


@dataclass(frozen=True)
class InformeDelConjunto:
    planos: dict
    estado: str
    motivos: tuple


def comparar_con_conjunto_esperado(entradas: Sequence[bytes], declaracion, acuses, cierre, politica_de_observadores,
                                   politica_de_claves, *, canal: str, corte_esperado: int) -> InformeDelConjunto:
    """Compara la declaracion del observador con el registro, los acuses y el
    cierre de AE-76. Detecta omisiones, objetivos extra, duplicados,
    vinculos incorrectos, firmas alteradas y cambios de corte."""
    estado = _rp.validar_registro(list(entradas))
    planos = {p: _r("no_evaluable", "declaracion_ilegible") for p in PLANOS_DEL_CONJUNTO}
    try:
        pieza = leer_conjunto_esperado(declaracion.datos)
        planos["lectura"] = _OK
    except ConjuntoEsperadoInvalido as error:
        pieza = None
        planos["lectura"] = _r("rechazada", error.motivo)
    planos["firma_del_observador"] = _firma_del_observador(declaracion, pieza, politica_de_observadores,
                                                          politica_de_claves)
    canal_informe = _ae76.verificar_canal(entradas, acuses, cierre, politica_de_claves, canal=canal)
    if pieza is not None:
        esperados = [tuple(o) for o in pieza["objetivos_esperados"]]
        conjunto = set(esperados)
        motivos = []
        if pieza["protocolo_hash"] != estado.hash_protocolo:
            motivos.append("protocolo_hash_no_coincide")
        for juego, objetivo in conjunto:
            corte = estado.protocolo["juegos"].get(juego, {}).get("ultimo_sorteo_conocido")
            if juego not in estado.protocolo["juegos"]:
                motivos.append("juego_fuera_del_protocolo")
            elif corte is None or objetivo <= corte:
                motivos.append("objetivo_esperado_no_posterior_al_corte_del_protocolo")
        if len(esperados) != len(conjunto):
            motivos.append("objetivo_esperado_duplicado")
        planos["vinculo_con_el_protocolo"] = _r("rechazada", *motivos) if motivos else _OK
        motivos = []
        if pieza["corte_sintetico"] != corte_esperado:
            motivos.append("corte_distinto_del_esperado")
        if any(objetivo > pieza["corte_sintetico"] for _, objetivo in conjunto):
            motivos.append("objetivo_posterior_al_corte_declarado")
        planos["corte"] = _r("rechazada", *motivos) if motivos else _OK
        registrados = set(estado.predicciones)
        motivos = [*(["objetivo_esperado_sin_prediccion"] if conjunto - registrados else []),
                   *(["objetivo_no_esperado"] if registrados - conjunto else [])]
        planos["frente_al_registro"] = _r("rechazada", *motivos) if motivos else _OK
        leidos = []
        for objeto in acuses:
            try:
                acuse = _ae76.leer_acuse(objeto.datos)
            except _ae76.ExpedienteInvalido:
                continue
            leidos.append((acuse["codigo_juego"], acuse["sorteo_objetivo"]))
        motivos = [*(["objetivo_esperado_sin_acuse"] if conjunto - set(leidos) else []),
                   *(["objetivo_no_esperado"] if set(leidos) - conjunto else []),
                   *(["acuse_duplicado"] if len(leidos) != len(set(leidos)) else []),
                   *(m for m in canal_informe.motivos if canal_informe.estado == "rechazada")]
        planos["frente_a_los_acuses"] = _r("rechazada", *motivos) if motivos else _OK
        if cierre is None:
            planos["frente_al_cierre"] = _r("pendiente", "sin_cierre")
        else:
            try:
                declarado = {tuple(o) for o in _ae76.leer_cierre(cierre.datos)["conjunto_declarado"]}
            except _ae76.ExpedienteInvalido as error:
                planos["frente_al_cierre"] = _r("rechazada", error.motivo)
            else:
                motivos = [*(["objetivo_esperado_fuera_del_cierre"] if conjunto - declarado else []),
                           *(["objetivo_no_esperado"] if declarado - conjunto else [])]
                planos["frente_al_cierre"] = _r("rechazada", *motivos) if motivos else _OK
    rechazos = tuple(dict.fromkeys(m for r in planos.values() if r.estado == "rechazada" for m in r.motivos))
    if rechazos:
        return InformeDelConjunto(planos, "rechazada", rechazos)
    espera = tuple(dict.fromkeys(m for r in planos.values() if r.estado != "superada" for m in r.motivos))
    return InformeDelConjunto(planos, "pendiente" if espera else "superada", espera)


LIMITES_DE_LAS_VISTAS = (
    "la continuidad y la ausencia de contradicciones entre las vistas presentadas no descartan historias ocultas: "
    "hacen falta monitores independientes que comparen lo que ven",
    "una cadena del observador de fixture no prueba completitud global sin una fuente autorizada del conjunto "
    "esperado",
)


@dataclass(frozen=True)
class InformeDeVistas:
    estado: str
    motivos: tuple
    no_descarta: tuple = LIMITES_DE_LAS_VISTAS


def verificar_vistas(entradas: Sequence[bytes], vistas: Sequence[Sequence[object]], politica_de_observadores,
                     politica_de_claves) -> InformeDeVistas:
    """Continuidad de cada vista (secuencia y hash anterior), solo anexado
    (el corte no retrocede y ningun objetivo se retira) y contradicciones
    entre vistas (misma secuencia con contenido distinto)."""
    motivos = []
    por_secuencia: dict = {}
    for vista in vistas:
        anterior_hash, anterior = None, None
        for posicion, objeto in enumerate(vista, start=1):
            try:
                pieza = leer_conjunto_esperado(objeto.datos)
            except ConjuntoEsperadoInvalido as error:
                motivos.append(error.motivo)
                break
            firma = _firma_del_observador(objeto, pieza, politica_de_observadores, politica_de_claves)
            motivos.extend(firma.motivos)
            h = _ae76.hash_de_pieza(objeto.datos)
            if pieza["secuencia"] != posicion or pieza["anterior"] != anterior_hash:
                motivos.append("cadena_rota")
            if anterior is not None:
                if pieza["corte_sintetico"] < anterior["corte_sintetico"]:
                    motivos.append("corte_retrocede")
                if {tuple(o) for o in anterior["objetivos_esperados"]} - {tuple(o) for o in
                                                                          pieza["objetivos_esperados"]}:
                    motivos.append("objetivo_retirado")
            if por_secuencia.setdefault(pieza["secuencia"], h) != h:
                motivos.append("vistas_contradictorias")
            anterior_hash, anterior = h, pieza
    motivos = tuple(dict.fromkeys(motivos))
    return InformeDeVistas("rechazada" if motivos else "superada", motivos)


# ---------------------------------------------------------------------------
# 3. Informe compuesto
# ---------------------------------------------------------------------------

PLANOS_COMPUESTOS = ("integridad_de_bytes_de_las_piezas", "firmas_y_roles_de_prueba", "tiempo_por_acuse",
                     "completitud_respecto_del_manifiesto_presentado", "autoridad_del_manifiesto",
                     "completitud_global")
_MOTIVOS_DE_BYTES = frozenset((
    "pieza_ilegible", "pieza_no_canonica", "pieza_mal_formada", "version_desconocida", "impronta_no_coincide",
    "compromiso_de_otro_acuse", "sello_de_r0_no_cuenta_como_sello_de_acuse", "acuse_ilegible",
    "algoritmo_de_impronta_no_admitido", "cadena_rota", "vistas_contradictorias"))
_MOTIVOS_DE_FIRMAS = frozenset((
    "firma_no_coincide", "clave_no_admitida", "huella_de_clave_no_coincide", "clave_mal_formada",
    "algoritmo_no_admitido", "observador_no_independiente_del_canal"))

MOTIVOS = (
    "pieza_ilegible", "pieza_no_canonica", "pieza_mal_formada", "version_desconocida", "acuse_ilegible",
    "acuse_no_corresponde_al_registro", "plazo_sin_utc_explicito", "procedencia_del_plazo_no_admitida",
    "sello_de_r0_no_cuenta_como_sello_de_acuse", "compromiso_de_otro_acuse", "canal_no_coincide",
    "protocolo_hash_no_coincide", "prediccion_hash_no_coincide", "secuencia_no_coincide", "objetivo_no_coincide",
    "sello_o_vinculo_no_superado", "intervalo_cruza_el_plazo", "sello_posterior_al_plazo", "precision_ausente",
    "ancla_de_prueba_no_operativa", "revocacion_sin_comprobar", "plazo_sintetico_sin_calendario_oficial",
    "acuse_sin_sello", "observador_mal_formado", "encadenamiento_mal_formado", "declaracion_ilegible",
    "observador_no_independiente_del_canal", "juego_fuera_del_protocolo",
    "objetivo_esperado_no_posterior_al_corte_del_protocolo", "objetivo_esperado_duplicado",
    "corte_distinto_del_esperado", "objetivo_posterior_al_corte_declarado", "objetivo_esperado_sin_prediccion",
    "objetivo_no_esperado", "objetivo_esperado_sin_acuse", "objetivo_esperado_fuera_del_cierre", "acuse_duplicado",
    "sin_cierre", "cadena_rota", "corte_retrocede", "objetivo_retirado", "vistas_contradictorias",
    "observador_de_fixture_sin_autoridad", "decision_c3_sin_tomar", "sin_monitores_independientes",
    "sin_fuente_autorizada",
)
"""Motivos propios de AE-77; los de firma y del canal vienen de AE-76 y los
del token de AE-75."""

DECISIONES_OPERATIVAS_PENDIENTES = MappingProxyType({id_: MappingProxyType({"estado": "sin_decidir", "texto": texto})
                                                     for id_, texto in (
    ("A1", "autoridad e identidad del firmante de R0 y su politica de firmas operativa"),
    ("A2", "publicacion fuera de banda y reconocimiento del operador"),
    ("A3", "revocacion y custodia de las claves de firma, del canal y del observador"),
    ("C1", "canal operativo, su clave y su declaracion en R0"),
    ("C2", "autoridad de sellado operativa para los acuses, su ancla, su politica y su revocacion"),
    ("C3", "fuente autorizada del conjunto esperado, su observador y los monitores independientes"),
)})

LIMITES = (
    "las claves, los certificados, la TSA y el observador son de fixture; un resultado superado solo prueba "
    "coherencia frente a esas fixtures",
    "un sello de R0 nunca cuenta como sello de un acuse, y la hora declarada por el canal no es prueba",
    "completo respecto del manifiesto presentado no es completitud global: las vistas presentadas no descartan "
    "historias ocultas sin monitores independientes y una fuente autorizada",
    "el informe compuesto no cambia puertas ni planos de AE-74, AE-75 o AE-76; r0_final sigue rechazada",
    "D8 sigue limitada al modelo sintetico y D9 con su espera provisional; A1-A3 y C1-C3 siguen sin decidir",
)


@dataclass(frozen=True)
class InformeCompuesto:
    expediente: object
    tiempos: tuple
    conjunto: InformeDelConjunto
    vistas: InformeDeVistas
    planos_ae77: dict
    motivos: dict
    autoriza_evaluacion: bool
    limites: tuple = LIMITES


def evaluar_recepcion_por_objetivo(entradas: Sequence[bytes], bytes_declaracion: bytes | None, *,
                                   sellos_de_acuses: Sequence[EvidenciaDeSelloDeAcuse], declaracion,
                                   vistas: Sequence[Sequence[object]], politica_de_observadores, corte_esperado: int,
                                   evidencias_de_sello, politica_de_sello, sobre, acuses, cierre, politica_de_claves,
                                   canal: str) -> InformeCompuesto:
    """Informe compuesto. El expediente de AE-76 se evalua igual que sin
    AE-77 y se conserva completo; los planos de AE-77 van aparte."""
    expediente = _ae76.evaluar_expediente(entradas, bytes_declaracion, evidencias_de_sello=evidencias_de_sello,
                                          politica_de_sello=politica_de_sello, sobre=sobre, acuses=acuses,
                                          cierre=cierre, politica_de_claves=politica_de_claves, canal=canal)
    tiempos = tuple(verificar_tiempo_de_acuse(entradas, e, politica_de_sello, politica_de_claves, canal=canal)
                    for e in sellos_de_acuses)
    conjunto = comparar_con_conjunto_esperado(entradas, declaracion, acuses, cierre, politica_de_observadores,
                                              politica_de_claves, canal=canal, corte_esperado=corte_esperado)
    informe_vistas = verificar_vistas(entradas, vistas, politica_de_observadores, politica_de_claves)

    todos = [m for t in tiempos for r in t.planos.values() if r.estado == "rechazada" for m in r.motivos]
    todos += [m for r in conjunto.planos.values() if r.estado == "rechazada" for m in r.motivos]
    todos += list(informe_vistas.motivos)
    bytes_ = tuple(dict.fromkeys(m for m in todos if m in _MOTIVOS_DE_BYTES))
    firmas = tuple(dict.fromkeys(m for m in todos if m in _MOTIVOS_DE_FIRMAS))

    sellados = {e.acuse.datos for e in sellos_de_acuses}
    sin_sello = any(a.datos not in sellados for a in acuses)
    estados = [t.estado for t in tiempos]
    if "rechazada" in estados:
        tiempo = ("rechazada", tuple(dict.fromkeys(m for t in tiempos if t.estado == "rechazada" for m in t.motivos)))
    elif "no_concluyente" in estados:
        tiempo = ("no_concluyente", ("intervalo_cruza_el_plazo",))
    else:
        tiempo = ("pendiente", tuple(dict.fromkeys([*(["acuse_sin_sello"] if sin_sello or not tiempos else []),
                                                    *(m for t in tiempos for m in t.motivos)])))
    manifiesto = (conjunto.estado, conjunto.motivos) if informe_vistas.estado == "superada" else (
        "rechazada", tuple(dict.fromkeys((*conjunto.motivos, *informe_vistas.motivos))))
    resultado = {
        "integridad_de_bytes_de_las_piezas": ("rechazada", bytes_) if bytes_ else ("superada", ()),
        "firmas_y_roles_de_prueba": ("rechazada", firmas) if firmas else ("superada", ()),
        "tiempo_por_acuse": tiempo,
        "completitud_respecto_del_manifiesto_presentado": manifiesto,
        "autoridad_del_manifiesto": ("pendiente", ("observador_de_fixture_sin_autoridad", "decision_c3_sin_tomar")),
        "completitud_global": ("pendiente", ("sin_monitores_independientes", "sin_fuente_autorizada")),
    }
    return InformeCompuesto(expediente, tiempos, conjunto, informe_vistas,
                            {p: resultado[p][0] for p in PLANOS_COMPUESTOS},
                            {p: resultado[p][1] for p in PLANOS_COMPUESTOS}, _expediente.AUTORIZA_EVALUACION)
