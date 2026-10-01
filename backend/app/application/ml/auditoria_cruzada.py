"""
Auditoria cruzada de expedientes portables y capturas de observadores
-Etapa AE-79, validada localmente como trabajo preparatorio.

Tres formatos versionados, todos con el manifiesto de archivos declarados de
AE-78 (ruta, tamano y SHA-256) y su lectura endurecida:

- `captura-observador-expediente/1`: pieza JSON canonica firmada con Ed25519
  (el `ObjetoFirmado` de AE-76). Vincula el SHA-256 exacto del manifiesto de
  un expediente AE-78, el de la politica del verificador usada, el protocolo,
  el canal, el alcance de corte, el corte sintetico, el conjunto esperado y
  las historias de acuses y vistas, la posicion en la secuencia del
  firmante y el hash de su captura anterior;
- `capturas-de-observador/1`: directorio con `capturas.json` y los bytes de
  cada captura, su firma y su clave publica;
- `politica-auditoria-cruzada-de-prueba/1`: directorio con
  `politica_auditoria.json`, que suministra quien audita: claves publicas de
  capturadores de prueba y cortes sinteticos admitidos.

El auditor (`auditar`) lee cada expediente con la lectura endurecida de
AE-78 y lo evalua con AE-78 (sin copiar su logica). Despues compara, solo
dentro de un mismo protocolo, canal y alcance de corte, las capturas
admitidas (`CRITERIO_DE_ADMISION`: lectura y firma superadas, politica
capturada igual a la usada y, si su expediente se presento, campos
coincidentes): cadenas y bifurcaciones del mismo firmante, discrepancias
entre firmantes, objetivos retirados, cortes que retroceden y omisiones
frente a un conjunto esperado firmado. Tambien compara entre expedientes
los acuses del canal y las declaraciones del observador de AE-77 por
posicion. Un firmante es una clave publica: una etiqueta distinta con la
misma clave no es otro firmante.

Una captura solo prueba que una clave de prueba firmo esos bytes. No
acredita fecha de publicacion, custodia independiente, autoridad operativa
ni completitud global; la coincidencia de firmantes, aunque sean todos, no
sustituye a una fuente autorizada. Las huellas esperadas las aporta quien
audita; una huella copiada de los propios archivos no es una publicacion
independiente. `AUTORIZA_EVALUACION = False`; A1-A3, C1-C3, D8 operativa y
D9 definitiva siguen sin decidir. Sin red, reloj local, deserializacion
ejecutable ni secretos.
"""
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from app.application.ml import expediente_portable as _ae78
from app.application.ml import expediente_r0_recepcion as _ae76
from app.application.ml import propuesta_inferencia_prospectiva as _expediente
from app.application.ml import recepcion_por_objetivo as _ae77
from app.application.ml import registro_prospectivo as _rp

ESQUEMA_CAPTURA = "captura-observador-expediente/1"
ESQUEMA_CAPTURAS = "capturas-de-observador/1"
ESQUEMA_POLITICA_AUDITORIA = "politica-auditoria-cruzada-de-prueba/1"
ESQUEMA_INFORME = "informe-auditoria-cruzada/1"
NOMBRE_CAPTURAS = "capturas.json"
NOMBRE_POLITICA_AUDITORIA = "politica_auditoria.json"
CLAVES_DE_LA_CAPTURA = ("esquema", "observador", "secuencia", "anterior", "sha256_manifiesto", "sha256_politica",
                        "protocolo_hash", "canal", "alcance_de_corte", "corte_sintetico", "conjunto_esperado",
                        "objetivos_esperados", "acuses", "vistas", "algoritmo", "huella_de_clave")
CAMPOS_DEL_EXPEDIENTE = ("protocolo_hash", "canal", "alcance_de_corte", "corte_sintetico", "conjunto_esperado",
                         "objetivos_esperados", "acuses", "vistas")
"""Campos de una captura que se derivan de los bytes del expediente."""
NATURALEZAS_DE_CAPTURADOR = ("fixture_de_prueba",)
CAPTURADORES_OPERATIVOS_ADMITIDOS = ()
"""Ninguno: AE-79 no elige observador, monitor ni autoridad real."""

MINIMO_DE_EXPEDIENTES = 2
MAXIMO_DE_EXPEDIENTES = 8
MAXIMO_DE_CONJUNTOS_DE_CAPTURAS = 8
MAXIMO_DE_CAPTURAS = 64
BYTES_AGREGADOS = 64 << 20
ARCHIVOS_AGREGADOS = 4096
"""Limites agregados de una auditoria: los de AE-78 siguen valiendo para
cada directorio, pero no se multiplican sin control por el numero de
entradas."""

_HEX64 = re.compile(r"[0-9a-f]{64}")
_NOMBRE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


# ---------------------------------------------------------------------------
# Resumen de un expediente y construccion de capturas
# ---------------------------------------------------------------------------

def resumen_del_expediente(expediente: "_ae78.ExpedienteLeido") -> dict:
    """Campos de captura derivados de los bytes de un expediente leido.
    Lanza `ValueError` si el expediente no permite derivarlos."""
    try:
        estado = _rp.validar_registro(list(expediente.entradas))
        conjunto = _ae77.leer_conjunto_esperado(expediente.conjunto_esperado.datos)
        acuses = [_ae76.leer_acuse(a.datos) for a in expediente.acuses]
    except (_rp.RegistroProspectivoError, _ae77.ConjuntoEsperadoInvalido, _ae76.ExpedienteInvalido) as error:
        raise ValueError("expediente_no_resumible") from error
    canales = {a["canal"] for a in acuses}
    if expediente.cierre is not None:
        try:
            canales.add(_ae76.leer_cierre(expediente.cierre.datos)["canal"])
        except _ae76.ExpedienteInvalido as error:
            raise ValueError("expediente_no_resumible") from error
    if len(canales) != 1:
        raise ValueError("expediente_no_resumible")
    objetivos = sorted([list(o) for o in conjunto["objetivos_esperados"]])
    lista_acuses = [[_ae76.hash_de_pieza(o.datos), a["codigo_juego"], a["sorteo_objetivo"]]
                    for o, a in zip(expediente.acuses, acuses)]
    alcance = sorted({o[0] for o in objetivos} | {a[1] for a in lista_acuses})
    return {"protocolo_hash": estado.hash_protocolo, "canal": canales.pop(), "alcance_de_corte": alcance,
            "corte_sintetico": conjunto["corte_sintetico"],
            "conjunto_esperado": _ae76.hash_de_pieza(expediente.conjunto_esperado.datos),
            "objetivos_esperados": objetivos, "acuses": lista_acuses,
            "vistas": [[_ae76.hash_de_pieza(o.datos) for o in vista] for vista in expediente.vistas]}


def construir_captura(expediente: "_ae78.ExpedienteLeido", *, sha256_politica: str, observador: str,
                      secuencia: int, anterior: str | None, clave_publica: bytes) -> dict:
    """Pieza de captura sin firmar; la firma la pone quien tiene la clave."""
    if not isinstance(observador, str) or not _NOMBRE.fullmatch(observador):
        raise ValueError("observador_mal_formado")
    if type(secuencia) is not int or secuencia < 1 or (secuencia == 1) != (anterior is None):
        raise ValueError("encadenamiento_mal_formado")
    return {"esquema": ESQUEMA_CAPTURA, "observador": observador, "secuencia": secuencia, "anterior": anterior,
            "sha256_manifiesto": expediente.sha256_manifiesto, "sha256_politica": sha256_politica,
            **resumen_del_expediente(expediente), "algoritmo": _ae76.ALGORITMO_DE_FIRMA,
            "huella_de_clave": _ae76.huella_de_clave(clave_publica)}


def es_huella(valor) -> bool:
    """SHA-256 en hexadecimal minuscula."""
    return isinstance(valor, str) and _HEX64.fullmatch(valor) is not None


_es_hex = es_huella


def _es_objetivo(valor) -> bool:
    return isinstance(valor, list) and len(valor) == 2 and isinstance(valor[0], str) and type(valor[1]) is int


def leer_captura(datos: bytes) -> dict:
    """Lectura estricta de una captura; `ExpedienteInvalido` con `motivo`."""
    pieza = _ae76._leer(datos, ESQUEMA_CAPTURA, CLAVES_DE_LA_CAPTURA)
    objetivos, acuses, vistas, alcance = (pieza["objetivos_esperados"], pieza["acuses"], pieza["vistas"],
                                          pieza["alcance_de_corte"])
    tipos = (
        isinstance(pieza["observador"], str) and _NOMBRE.fullmatch(pieza["observador"]) is not None
        and type(pieza["secuencia"]) is int and pieza["secuencia"] >= 1
        and ((pieza["secuencia"] == 1 and pieza["anterior"] is None)
             or (pieza["secuencia"] > 1 and _es_hex(pieza["anterior"])))
        and all(_es_hex(pieza[c]) for c in ("sha256_manifiesto", "sha256_politica", "protocolo_hash",
                                            "conjunto_esperado"))
        and isinstance(pieza["canal"], str) and _NOMBRE.fullmatch(pieza["canal"]) is not None
        and type(pieza["corte_sintetico"]) is int
        and isinstance(alcance, list) and alcance and all(isinstance(j, str) and j for j in alcance)
        and alcance == sorted(set(alcance))
        and isinstance(objetivos, list) and all(_es_objetivo(o) for o in objetivos)
        and objetivos == sorted(objetivos) and len({tuple(o) for o in objetivos}) == len(objetivos)
        and isinstance(acuses, list) and all(isinstance(a, list) and len(a) == 3 and _es_hex(a[0])
                                             and _es_objetivo(a[1:]) for a in acuses)
        and isinstance(vistas, list) and all(isinstance(v, list) and all(_es_hex(h) for h in v) for v in vistas))
    if not tipos:
        raise _ae76.ExpedienteInvalido("pieza_mal_formada")
    return pieza


# ---------------------------------------------------------------------------
# Formatos de directorio: capturas y politica de auditoria
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClaveDeCapturadorDePrueba:
    clave_publica: bytes
    etiqueta: str
    naturaleza: str = "fixture_de_prueba"

    def __post_init__(self):
        if self.naturaleza not in NATURALEZAS_DE_CAPTURADOR:
            raise ValueError(f"naturaleza de capturador no admitida en AE-79: {self.naturaleza!r}")
        if not isinstance(self.clave_publica, bytes) or len(self.clave_publica) != 32:
            raise ValueError("la clave publica Ed25519 debe tener 32 bytes")


@dataclass(frozen=True)
class PoliticaDeAuditoria:
    capturadores: tuple
    cortes_admitidos: tuple
    sha256: str


def componer_capturas(capturas: Sequence) -> dict:
    """{ruta: bytes} de un conjunto de capturas firmadas (solo publico)."""
    archivos: dict = {}
    lista = [_ae78._objeto(f"capturas/{i:03d}", c, archivos) for i, c in enumerate(capturas, start=1)]
    return _ae78._con_manifiesto(NOMBRE_CAPTURAS, {"esquema": ESQUEMA_CAPTURAS, "capturas": lista}, archivos)


def componer_politica_de_auditoria(*, capturadores: Sequence, cortes_admitidos: Sequence[int]) -> dict:
    """{ruta: bytes} de la politica de prueba de quien audita."""
    archivos: dict = {}
    lista = []
    for i, (clave, etiqueta) in enumerate(capturadores, start=1):
        archivos[f"capturadores/{i:02d}.bin"] = bytes(clave)
        lista.append({"clave_publica": f"capturadores/{i:02d}.bin", "etiqueta": etiqueta})
    cabecera = {"esquema": ESQUEMA_POLITICA_AUDITORIA, "naturaleza": "fixture_de_prueba", "capturadores": lista,
                "cortes_admitidos": sorted(cortes_admitidos)}
    return _ae78._con_manifiesto(NOMBRE_POLITICA_AUDITORIA, cabecera, archivos)


def _leer_manifiesto(archivos: Mapping[str, bytes], nombre: str, esquema: str, limites) -> dict:
    _ae78._limites(archivos, nombre, limites)
    manifiesto = _ae78._leer_json_canonico(archivos[nombre])
    if manifiesto.get("esquema") != esquema:
        _ae78._rechazar("version_desconocida", str(manifiesto.get("esquema"))[:80])
    return manifiesto


def leer_capturas(archivos: Mapping[str, bytes], *,
                  limites: "_ae78.Limites" = _ae78.LIMITES_POR_DEFECTO) -> tuple:
    """Lectura endurecida de un conjunto de capturas: tupla de
    `ObjetoFirmado`. Las piezas se leen despues, una a una."""
    manifiesto = _leer_manifiesto(archivos, NOMBRE_CAPTURAS, ESQUEMA_CAPTURAS, limites)
    _ae78._claves(manifiesto, {"esquema", "archivos", "capturas"}, "capturas")
    _ae78._exigir(isinstance(manifiesto["capturas"], list), "capturas")
    if len(manifiesto["capturas"]) > MAXIMO_DE_CAPTURAS:
        _ae78._rechazar("demasiadas_capturas")
    refs = [r for c in manifiesto["capturas"] for r in _ae78._rutas_de_objeto(c, "captura")]
    _ae78._comprobar_archivos(archivos, NOMBRE_CAPTURAS, manifiesto, refs, limites)
    return tuple(_ae78._firmado(archivos, c) for c in manifiesto["capturas"])


def leer_politica_de_auditoria(archivos: Mapping[str, bytes], *,
                               limites: "_ae78.Limites" = _ae78.LIMITES_POR_DEFECTO) -> PoliticaDeAuditoria:
    """Lectura endurecida de la politica de quien audita. Una misma clave
    publica declarada dos veces, con cualquier etiqueta, se rechaza."""
    manifiesto = _leer_manifiesto(archivos, NOMBRE_POLITICA_AUDITORIA, ESQUEMA_POLITICA_AUDITORIA, limites)
    _ae78._claves(manifiesto, {"esquema", "naturaleza", "archivos", "capturadores", "cortes_admitidos"},
                  "politica_de_auditoria")
    if manifiesto["naturaleza"] not in NATURALEZAS_DE_CAPTURADOR:
        _ae78._rechazar("naturaleza_no_admitida", str(manifiesto["naturaleza"])[:80])
    cortes = manifiesto["cortes_admitidos"]
    _ae78._exigir(isinstance(cortes, list) and all(type(c) is int for c in cortes)
                  and cortes == sorted(set(cortes)), "cortes_admitidos")
    _ae78._exigir(isinstance(manifiesto["capturadores"], list), "capturadores")
    refs = []
    for c in manifiesto["capturadores"]:
        _ae78._claves(c, {"clave_publica", "etiqueta"}, "capturador")
        _ae78._exigir(isinstance(c["etiqueta"], str), "etiqueta")
        refs.append(c["clave_publica"])
    _ae78._comprobar_archivos(archivos, NOMBRE_POLITICA_AUDITORIA, manifiesto, refs, limites)
    try:
        capturadores = tuple(ClaveDeCapturadorDePrueba(archivos[c["clave_publica"]], c["etiqueta"])
                             for c in manifiesto["capturadores"])
    except (ValueError, TypeError) as error:
        _ae78._rechazar("estructura_invalida", str(error)[:120])
    claves = [c.clave_publica for c in capturadores]
    if len(claves) != len(set(claves)):
        _ae78._rechazar("clave_duplicada", "misma clave publica con dos etiquetas")
    return PoliticaDeAuditoria(capturadores, tuple(cortes),
                               _ae78.hashlib.sha256(archivos[NOMBRE_POLITICA_AUDITORIA]).hexdigest())


# ---------------------------------------------------------------------------
# Referencias externas (procedencia)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReferenciasExternas:
    """Huellas SHA-256 que aporta quien audita, desde fuera de los
    expedientes. Una huella copiada de los propios archivos no es una
    publicacion independiente."""
    politica_del_verificador: str | None = None
    politica_de_auditoria: str | None = None
    manifiestos: frozenset = field(default_factory=frozenset)
    capturas: frozenset = field(default_factory=frozenset)

    def __post_init__(self):
        for valor in (self.politica_del_verificador, self.politica_de_auditoria):
            if valor is not None and not _es_hex(valor):
                raise ValueError("huella_mal_formada")
        if not all(_es_hex(h) for h in (*self.manifiestos, *self.capturas)):
            raise ValueError("huella_mal_formada")


# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------

CONTRADICCIONES = (
    "equivocacion_del_firmante", "vinculo_roto", "cadena_cambia_de_alcance", "corte_retrocede",
    "objetivo_retirado", "historia_reescrita", "discrepancia_entre_firmantes", "omision_comprobable",
    "acuses_contradictorios_del_canal", "declaraciones_contradictorias_del_observador",
)
"""Motivos que prueban una contradiccion entre bytes firmados presentados.
Ninguno adjudica que parte dice la verdad."""

NO_COINCIDENCIAS = (
    "pieza_ilegible", "pieza_no_canonica", "pieza_mal_formada", "version_desconocida", "firma_no_coincide",
    "clave_no_admitida", "huella_de_clave_no_coincide", "clave_mal_formada", "algoritmo_no_admitido",
    "capturador_no_independiente_del_canal", "politica_distinta_de_la_capturada",
    "manifiesto_distinto_del_capturado", "captura_no_coincide_con_el_expediente",
    "captura_no_verificable_frente_al_expediente",
    "huella_de_politica_no_coincide", "huella_de_politica_de_auditoria_no_coincide",
    "manifiesto_esperado_no_presentado", "captura_esperada_no_presentada", "evaluacion_ae78_con_rechazos",
)
"""Firmas, hashes, vinculos o politicas que no coinciden: la evidencia
presentada no es la esperada, pero no se prueba una contradiccion."""

CRITERIO_DE_ADMISION = (
    "lectura estricta superada",
    "firma integra con clave admitida como capturador, huella declarada e independencia del canal y del "
    "firmante de R0",
    "sha256_politica igual a la politica del verificador usada en esta auditoria",
    "si su expediente se presento: resumible y con todos los campos de CAMPOS_DEL_EXPEDIENTE coincidentes; si no "
    "se presento, la comprobacion queda pendiente y la captura se admite como declaracion firmada",
)
"""Condiciones para que una captura participe en la comparacion cruzada.
Una captura que no las cumple sigue en el informe como evidencia
individual que no coincide y nunca produce una contradiccion."""

PENDIENTES = (
    "expediente_de_la_captura_no_presentado", "anterior_no_presentado", "expediente_sin_captura",
    "cabeza_sin_referencia_externa", "huella_no_aportada", "incomparables",
)

CODIGOS_DE_SALIDA = MappingProxyType({"sin_contradiccion_detectable": 0, "contradiccion_comprobada": 1,
                                      "uso_incorrecto": 2, "lectura_rechazada": 3, "evidencia_no_coincide": 4})
SIGNIFICADO_DE_LOS_CODIGOS = MappingProxyType({
    0: "sin contradiccion detectable en lo presentado; no autoriza evaluacion y los pendientes siguen pendientes",
    1: "contradiccion comprobada entre bytes firmados presentados; no adjudica cual es cierto",
    2: "uso incorrecto del comando; no se audito nada",
    3: "la lectura endurecida rechazo al menos una entrada; esa entrada no se evaluo",
    4: "firmas, hashes, vinculos, politicas o huellas esperadas no coinciden, sin contradiccion comprobada",
})
"""Prioridad: 1 sobre 3, 3 sobre 4 y 4 sobre 0. Ningun codigo significa
autorizacion."""

DECISIONES_ABIERTAS = ("A1", "A2", "A3", "C1", "C2", "C3", "D8_operativa", "D9_definitiva")

LIMITES = (
    "las claves de capturadores, del canal, del observador y de la TSA y las politicas son de fixture; un "
    "resultado solo prueba coherencia frente a ese material",
    "una captura solo prueba que una clave de prueba firmo esos bytes: no acredita fecha de publicacion, custodia "
    "independiente, autoridad operativa ni completitud global",
    "un firmante es una clave publica; una etiqueta distinta con la misma clave no es otro firmante",
    "la coincidencia de firmantes, incluso de todos los presentados, no es una fuente autorizada: no se usa "
    "mayoria ni quorum",
    "sin contradiccion detectable significa solo eso frente a lo presentado; lo no presentado puede contradecirlo",
    "una captura antigua no puede llamarse ultima sin una referencia externa",
    "una huella esperada copiada de los propios archivos no es una publicacion independiente",
    "ejecutar la auditoria no autoriza evaluacion ni convierte R0 en final; AUTORIZA_EVALUACION es False",
)


def _plano(estado: str, motivos=()) -> dict:
    return {"estado": estado, "motivos": list(dict.fromkeys(motivos))}


def _es_prefijo(a: list, b: list) -> bool:
    return len(a) <= len(b) and b[:len(a)] == a


def _vistas_compatibles(a: list, b: list) -> bool:
    """Cada vista de `a` es prefijo de la vista correspondiente de `b`."""
    return len(a) <= len(b) and all(_es_prefijo(x, y) for x, y in zip(a, b))


def _vistas_coherentes(a: list, b: list) -> bool:
    """Una de las dos historias de vistas extiende a la otra, vista a vista."""
    return all(_es_prefijo(x, y) or _es_prefijo(y, x) for x, y in zip(a, b))


def _alcance(pieza: dict) -> tuple:
    return pieza["protocolo_hash"], pieza["canal"], tuple(pieza["alcance_de_corte"])


def _firma_de_captura(objeto, pieza, politica_auditoria: PoliticaDeAuditoria, politica_verificador) -> dict:
    """Planos de la firma con las primitivas de AE-76: integridad, clave
    admitida como capturador y huella declarada; y la independencia
    respecto de las claves del canal y del firmante de R0."""
    admitidas = _ae76.PoliticaDeClavesDePrueba(claves=tuple(
        _ae76.ClaveDePrueba(c.clave_publica, "canal", c.etiqueta) for c in politica_auditoria.capturadores))
    planos = _ae76._firma(objeto, pieza, admitidas, "canal")
    motivos = [m for r in planos.values() if r.estado != "superada" for m in r.motivos]
    if politica_verificador.claves.admite(objeto.clave_publica, "canal") or politica_verificador.claves.admite(
            objeto.clave_publica, "firmante_r0"):
        motivos.append("capturador_no_independiente_del_canal")
    return _plano("rechazada" if motivos else "superada", motivos)


def _acuse_admitido(objeto, acuse: dict, politica_verificador) -> bool:
    """Firma del canal integra, con clave admitida y huella declarada."""
    planos = _ae76._firma(objeto, acuse, politica_verificador.claves, "canal")
    return all(r.estado == "superada" for r in planos.values())


def _observador_admitido(objeto, pieza: dict, politica_verificador) -> bool:
    return _ae77._firma_del_observador(objeto, pieza, politica_verificador.observadores,
                                       politica_verificador.claves).estado == "superada"


def _resumen_ae78(informe: dict) -> dict:
    """Resultado individual de AE-78 con sus planos y motivos."""
    planos = {nombre: plano for clave in ("integridad_y_firmas", "tiempo", "completitud_presentada", "pendientes")
              for nombre, plano in informe["secciones"][clave]["planos"].items()}
    return {"resultado": informe["resultado_de_la_auditoria"], "planos": planos,
            "r0_final": informe["secciones"]["autorizacion_operativa"]["r0_final"]}


def _corte_para(expediente, politica_verificador, politica_auditoria):
    try:
        corte = _ae77.leer_conjunto_esperado(expediente.conjunto_esperado.datos)["corte_sintetico"]
    except _ae77.ConjuntoEsperadoInvalido:
        corte = None
    if corte is not None and corte in politica_auditoria.cortes_admitidos:
        return corte, "cortes_admitidos_de_la_politica_de_auditoria"
    return politica_verificador.corte_esperado, "politica_del_verificador"


def _leer_entrada(entrada, lector):
    nombre, contenido = entrada
    if isinstance(contenido, _ae78.ExpedienteIlegible):
        return nombre, None, contenido
    try:
        return nombre, lector(contenido), None
    except _ae78.ExpedienteIlegible as error:
        return nombre, None, error


def informe_de_lectura_rechazada(objeto: str, motivo: str, n_exp: int, n_cap: int) -> dict:
    """Informe cuando una politica o el limite agregado impiden auditar: no
    se evalua ningun expediente ni ninguna captura."""
    return {"esquema": ESQUEMA_INFORME,
            "entradas": {"expedientes": n_exp, "conjuntos_de_capturas": n_cap},
            "lectura": {"estado": "rechazada", "objeto": objeto, "motivos": [motivo]},
            "expedientes": [], "capturas": [], "entre_expedientes": {}, "procedencia": {},
            "pendientes": _pendientes(), "autorizacion_operativa": _autorizacion(),
            "resultado": "lectura_rechazada", "limites": list(LIMITES)}


def _pendientes() -> dict:
    return {"planos": {
        "autoridad_del_manifiesto": _plano("pendiente", ("observador_de_fixture_sin_autoridad",
                                                         "decision_c3_sin_tomar")),
        "completitud_global": _plano("pendiente", ("sin_fuente_autorizada",
                                                   "coincidencia_de_firmantes_no_es_autoridad")),
        "completitud_respecto_de_lo_que_debio_existir": _plano("pendiente", ("sin_evidencia_externa",)),
    }, "decisiones_sin_tomar": list(DECISIONES_ABIERTAS)}


def _autorizacion() -> dict:
    return {"estado": "denegada", "AUTORIZA_EVALUACION": _expediente.AUTORIZA_EVALUACION}


def auditar(*, expedientes: Sequence, politica_del_verificador, politica_de_auditoria, capturas: Sequence = (),
            referencias: ReferenciasExternas = ReferenciasExternas()) -> dict:
    """Auditoria cruzada. `expedientes` y `capturas` son pares
    `(nombre, archivos)`, donde `archivos` es `{ruta: bytes}` o una
    `ExpedienteIlegible` si ya fallo la lectura del directorio; las dos
    politicas son `{ruta: bytes}` o `ExpedienteIlegible`. Devuelve el
    informe (JSON determinista con `informe_json`)."""
    if not MINIMO_DE_EXPEDIENTES <= len(expedientes) <= MAXIMO_DE_EXPEDIENTES:
        raise ValueError("numero_de_expedientes_fuera_de_limites")
    if len(capturas) > MAXIMO_DE_CONJUNTOS_DE_CAPTURAS:
        raise ValueError("numero_de_conjuntos_de_capturas_fuera_de_limites")
    n_exp, n_cap = len(expedientes), len(capturas)
    for objeto, contenido, lector in (("politica_del_verificador", politica_del_verificador, _ae78.leer_politica),
                                      ("politica_de_auditoria", politica_de_auditoria, leer_politica_de_auditoria)):
        _, leido, error = _leer_entrada(("", contenido), lector)
        if error is not None:
            return informe_de_lectura_rechazada(objeto, error.motivo, n_exp, n_cap)
        if objeto == "politica_del_verificador":
            pv = leido
        else:
            pa = leido

    # 1. Cada expediente: lectura endurecida y evaluacion AE-78.
    leidos = {}          # sha256_manifiesto -> (ExpedienteLeido, resumen | None)
    fila_exp = []
    lectura_rechazada = False
    no_coincide = set()
    for nombre, exp, error in (_leer_entrada(e, _ae78.leer_expediente) for e in expedientes):
        if error is not None:
            lectura_rechazada = True
            fila_exp.append({"nombre": nombre, "lectura": _plano("rechazada", (error.motivo,))})
            continue
        if exp.sha256_manifiesto in leidos:
            fila = next(f for f in fila_exp if f.get("sha256_manifiesto") == exp.sha256_manifiesto)
            fila["presentado_mas_de_una_vez"] = True
            continue
        corte, origen = _corte_para(exp, pv, pa)
        informe = _ae78.evaluar(exp, _ae78.PoliticaLeida(pv.sello, pv.claves, pv.observadores, pv.canal, corte,
                                                          pv.sha256))
        individual = _resumen_ae78(informe)
        if individual["resultado"] == "con_rechazos":
            no_coincide.add("evaluacion_ae78_con_rechazos")
        try:
            resumen = resumen_del_expediente(exp)
        except ValueError:
            resumen = None
        leidos[exp.sha256_manifiesto] = (exp, resumen)
        fila_exp.append({"sha256_manifiesto": exp.sha256_manifiesto, "lectura": _plano("superada"),
                         "corte_esperado": {"valor": corte, "origen": origen}, "ae78": individual,
                         "resumible": resumen is not None})

    # 2. Capturas: lectura, firma, politica y coincidencia con su expediente.
    conjuntos, fila_cap, validas, vistos = [], [], {}, set()
    for nombre, objetos, error in (_leer_entrada(c, leer_capturas) for c in capturas):
        if error is not None:
            lectura_rechazada = True
            conjuntos.append({"nombre": nombre, "lectura": _plano("rechazada", (error.motivo,))})
            continue
        conjuntos.append({"nombre": nombre, "lectura": _plano("superada"), "capturas": len(objetos)})
        for objeto in objetos:
            # Solo se descartan copias identicas (datos, firma y clave): una
            # copia con firma invalida no puede ocultar a la valida, y el
            # resultado no depende del orden de presentacion.
            if (objeto.datos, objeto.firma, objeto.clave_publica) in vistos:
                continue
            vistos.add((objeto.datos, objeto.firma, objeto.clave_publica))
            id_ = _ae76.hash_de_pieza(objeto.datos)
            fila = {"id": id_, "firmante": _ae76.huella_de_clave(objeto.clave_publica),
                    "sha256_firma": _ae78.hashlib.sha256(objeto.firma).hexdigest()}
            try:
                pieza = leer_captura(objeto.datos)
            except _ae76.ExpedienteInvalido as error:
                pieza = None
                fila["lectura"] = _plano("rechazada", (error.motivo,))
            else:
                fila["lectura"] = _plano("superada")
                fila.update(observador=pieza["observador"], secuencia=pieza["secuencia"],
                            sha256_manifiesto=pieza["sha256_manifiesto"])
            fila["firma"] = _firma_de_captura(objeto, pieza, pa, pv)
            motivos = [*fila["lectura"]["motivos"], *fila["firma"]["motivos"]]
            if pieza is not None:
                if pieza["sha256_politica"] != pv.sha256:
                    motivos.append("politica_distinta_de_la_capturada")
                referido = leidos.get(pieza["sha256_manifiesto"])
                if referido is None:
                    fila["expediente"] = "no_presentado"
                elif referido[1] is None:
                    fila["expediente"] = "presentado_no_resumible"
                    motivos.append("captura_no_verificable_frente_al_expediente")
                else:
                    fila["expediente"] = "presentado"
                    distintos = [c for c in CAMPOS_DEL_EXPEDIENTE if pieza[c] != referido[1][c]]
                    if distintos:
                        motivos.append("captura_no_coincide_con_el_expediente")
                        fila["campos_que_no_coinciden"] = distintos
            fila["motivos"] = list(dict.fromkeys(motivos))
            fila["estado"] = "no_coincide" if motivos else "coincide"
            no_coincide.update(motivos)
            # Solo una captura admitida entra en la comparacion cruzada (ver
            # CRITERIO_DE_ADMISION); las demas quedan como evidencia
            # individual que no coincide.
            fila["admitida_para_comparar"] = pieza is not None and not motivos
            if fila["admitida_para_comparar"]:
                validas[id_] = pieza
            fila_cap.append(fila)

    # Expedientes capturados, expedientes no presentados y manifiestos
    # distintos de los capturados (alteracion coherente de archivo y
    # manifiesto frente a una captura ya firmada).
    capturados = {p["sha256_manifiesto"] for p in validas.values()}
    for fila in fila_cap:
        if fila.get("expediente") != "no_presentado" or not fila["admitida_para_comparar"]:
            continue
        pieza = validas[fila["id"]]
        sustitutos = [sha for sha, (_, res) in leidos.items() if res is not None and sha not in capturados
                      and _alcance(res) == _alcance(pieza) and res["corte_sintetico"] == pieza["corte_sintetico"]]
        if sustitutos:
            fila["expediente"] = "manifiesto_distinto_del_capturado"
            fila["motivos"].append("manifiesto_distinto_del_capturado")
            fila["estado"] = "no_coincide"
            no_coincide.add("manifiesto_distinto_del_capturado")
        else:
            fila["motivos"].append("expediente_de_la_captura_no_presentado")
    for fila in fila_exp:
        if "sha256_manifiesto" in fila:
            fila["capturado"] = fila["sha256_manifiesto"] in capturados

    # 3. Entre expedientes: canal y observador de AE-77 por posicion.
    entre = _entre_expedientes(leidos, pv)
    # 4. Entre capturas: firmante, cadenas, alcances y firmantes distintos.
    cruce = _entre_capturas(validas)
    # 5. Procedencia y cabezas.
    procedencia = _procedencia(referencias, pv, pa, leidos, fila_cap, validas)
    no_coincide.update(m for c in procedencia["comprobaciones"] if c["estado"] == "no_coincide"
                       for m in c["motivos"])

    contradicciones = sorted(set(entre["motivos"]) | set(cruce["motivos"]))
    if contradicciones:
        resultado = "contradiccion_comprobada"
    elif lectura_rechazada:
        resultado = "lectura_rechazada"
    elif no_coincide & set(NO_COINCIDENCIAS):
        resultado = "evidencia_no_coincide"
    else:
        resultado = "sin_contradiccion_detectable"
    if contradicciones:
        estado_cruzado = "contradiccion_comprobada"
    elif cruce["progresiones"]:
        estado_cruzado = "progresion_demostrable"
    elif cruce["comparaciones"]:
        estado_cruzado = "compatibles"
    elif cruce["incomparables"]:
        estado_cruzado = "incomparables"
    else:
        estado_cruzado = "sin_capturas_comparables"
    return {
        "esquema": ESQUEMA_INFORME,
        "entradas": {"expedientes": n_exp, "conjuntos_de_capturas": n_cap},
        "lectura": {"estado": "superada" if not lectura_rechazada else "rechazada_en_parte", "objeto": "entradas"},
        "politicas": {
            "del_verificador": {"esquema": _ae78.ESQUEMA_POLITICA, "sha256": pv.sha256,
                                "naturaleza": "fixture_de_prueba"},
            "de_auditoria": {"esquema": ESQUEMA_POLITICA_AUDITORIA, "sha256": pa.sha256,
                             "naturaleza": "fixture_de_prueba",
                             "capturadores": sorted(_ae76.huella_de_clave(c.clave_publica) for c in pa.capturadores),
                             "cortes_admitidos": list(pa.cortes_admitidos)},
            "origen": "suministradas_a_quien_audita_no_a_los_expedientes"},
        "expedientes": sorted(fila_exp, key=lambda f: (f.get("sha256_manifiesto", ""), f.get("nombre", ""),
                                                       f["lectura"]["motivos"])),
        "conjuntos_de_capturas": sorted(conjuntos, key=lambda c: (c["lectura"]["estado"], c["nombre"])),
        "capturas": sorted(fila_cap, key=lambda f: (f["firmante"], f.get("secuencia", 0), f["id"],
                                                    f["sha256_firma"])),
        "entre_expedientes": {"estado": estado_cruzado, "motivos": contradicciones, "por_posicion": entre,
                              "capturas": {k: cruce[k] for k in ("comparaciones", "progresiones", "incomparables",
                                                                 "pendientes")}},
        "procedencia": procedencia,
        "pendientes": _pendientes(),
        "autorizacion_operativa": _autorizacion(),
        "resultado": resultado,
        "limites": list(LIMITES),
    }


def _entre_expedientes(leidos: dict, pv) -> dict:
    """Acuses del canal y declaraciones del observador de AE-77 con firma
    admitida: dos contenidos distintos para la misma posicion son una
    contradiccion que ningun expediente muestra por si solo."""
    acuses, declaraciones = {}, {}
    for sha, (exp, _) in sorted(leidos.items()):
        for objeto in exp.acuses:
            try:
                acuse = _ae76.leer_acuse(objeto.datos)
            except _ae76.ExpedienteInvalido:
                continue
            if _acuse_admitido(objeto, acuse, pv):
                clave = (acuse["protocolo_hash"], acuse["canal"], acuse["secuencia"])
                acuses.setdefault(clave, {}).setdefault(_ae76.hash_de_pieza(objeto.datos), set()).add(sha)
        for objeto in [exp.conjunto_esperado, *(o for vista in exp.vistas for o in vista)]:
            try:
                pieza = _ae77.leer_conjunto_esperado(objeto.datos)
            except _ae77.ConjuntoEsperadoInvalido:
                continue
            if _observador_admitido(objeto, pieza, pv):
                clave = (pieza["protocolo_hash"], _ae76.huella_de_clave(objeto.clave_publica), pieza["secuencia"])
                declaraciones.setdefault(clave, {}).setdefault(_ae76.hash_de_pieza(objeto.datos), set()).add(sha)
    hallazgos = []
    for motivo, grupo, etiqueta in (("acuses_contradictorios_del_canal", acuses, "canal"),
                                    ("declaraciones_contradictorias_del_observador", declaraciones, "observador")):
        for (protocolo, quien, secuencia), por_hash in sorted(grupo.items()):
            if len(por_hash) > 1:
                hallazgos.append({"motivo": motivo, "protocolo_hash": protocolo, etiqueta: quien,
                                  "secuencia": secuencia,
                                  "contenidos": [{"hash": h, "expedientes": sorted(s)}
                                                 for h, s in sorted(por_hash.items())]})
    return {"hallazgos": hallazgos, "motivos": sorted({h["motivo"] for h in hallazgos})}


def _comparar_ordenados(a: dict, b: dict) -> list:
    """Motivos de un par del mismo alcance en el que `b` debe extender o
    igualar a `a` (a precede a b en la secuencia del firmante o en el
    corte)."""
    motivos = []
    if b["corte_sintetico"] < a["corte_sintetico"]:
        motivos.append("corte_retrocede")
    if {tuple(o) for o in a["objetivos_esperados"]} - {tuple(o) for o in b["objetivos_esperados"]}:
        motivos.append("objetivo_retirado")
    if not _es_prefijo(a["acuses"], b["acuses"]) or not _vistas_compatibles(a["vistas"], b["vistas"]):
        motivos.append("historia_reescrita")
    return motivos


def _omision(a: dict, b: dict) -> bool:
    """El conjunto esperado firmado en `a` exige objetivos que la historia de
    acuses de `b`, de corte igual o posterior, no contiene."""
    if b["corte_sintetico"] < a["corte_sintetico"]:
        return False
    return bool({tuple(o) for o in a["objetivos_esperados"]} - {(x[1], x[2]) for x in b["acuses"]})


def _entre_capturas(validas: dict) -> dict:
    """Comparaciones entre capturas admitidas (CRITERIO_DE_ADMISION)."""
    motivos, comparaciones, progresiones, incomparables, pendientes = [], [], [], [], []
    por_firmante: dict = {}
    for id_, p in validas.items():
        por_firmante.setdefault(p["huella_de_clave"], {}).setdefault(p["secuencia"], []).append(id_)
    # Mismo firmante: equivocacion y vinculos.
    for firmante, posiciones in sorted(por_firmante.items()):
        for secuencia, ids in sorted(posiciones.items()):
            if len(ids) > 1:
                motivos.append("equivocacion_del_firmante")
                comparaciones.append({"tipo": "mismo_firmante", "firmante": firmante, "secuencia": secuencia,
                                      "capturas": sorted(ids), "estado": "contradiccion",
                                      "motivos": ["equivocacion_del_firmante"]})
            for id_ in ids:
                p = validas[id_]
                if secuencia == 1:
                    continue
                previas = posiciones.get(secuencia - 1, [])
                if not previas:
                    pendientes.append({"captura": id_, "motivo": "anterior_no_presentado"})
                elif p["anterior"] not in previas:
                    motivos.append("vinculo_roto")
                    comparaciones.append({"tipo": "mismo_firmante", "firmante": firmante, "secuencia": secuencia,
                                          "capturas": sorted([id_, *previas]), "estado": "contradiccion",
                                          "motivos": ["vinculo_roto"]})
    # Pares: mismo firmante ordenado por secuencia; firmantes distintos
    # ordenados por corte; alcances distintos, incomparables.
    ids = sorted(validas)
    for i, x in enumerate(ids):
        for y in ids[i + 1:]:
            a, b = validas[x], validas[y]
            mismo = a["huella_de_clave"] == b["huella_de_clave"]
            if _alcance(a) != _alcance(b):
                if mismo and a["secuencia"] != b["secuencia"]:
                    motivos.append("cadena_cambia_de_alcance")
                    comparaciones.append({"tipo": "mismo_firmante", "capturas": [x, y], "estado": "contradiccion",
                                          "motivos": ["cadena_cambia_de_alcance"]})
                    continue
                causas = [c for c, k in (("protocolo_distinto_sin_base_comun", 0), ("canal_distinto", 1),
                                         ("alcance_de_corte_distinto", 2)) if _alcance(a)[k] != _alcance(b)[k]]
                incomparables.append({"capturas": [x, y], "motivos": causas})
                continue
            if mismo:
                if a["secuencia"] == b["secuencia"]:
                    continue
                (x0, a0), (y0, b0) = sorted(((x, a), (y, b)), key=lambda t: t[1]["secuencia"])
                hallados = _comparar_ordenados(a0, b0)
                hallados += ["omision_comprobable"] if _omision(a0, b0) else []
                tipo = "mismo_firmante"
            else:
                (x0, a0), (y0, b0) = sorted(((x, a), (y, b)), key=lambda t: (t[1]["corte_sintetico"], t[0]))
                hallados = []
                if a0["corte_sintetico"] == b0["corte_sintetico"]:
                    if a0["objetivos_esperados"] != b0["objetivos_esperados"]:
                        hallados.append("discrepancia_entre_firmantes")
                    if not (_es_prefijo(a0["acuses"], b0["acuses"]) or _es_prefijo(b0["acuses"], a0["acuses"])):
                        hallados.append("discrepancia_entre_firmantes")
                    if not _vistas_coherentes(a0["vistas"], b0["vistas"]):
                        hallados.append("discrepancia_entre_firmantes")
                    omite = _omision(a0, b0) or _omision(b0, a0)
                elif _comparar_ordenados(a0, b0):
                    hallados.append("discrepancia_entre_firmantes")
                    omite = _omision(a0, b0)
                else:
                    omite = _omision(a0, b0)
                hallados += ["omision_comprobable"] if omite else []
                tipo = "firmantes_distintos"
            hallados = list(dict.fromkeys(hallados))
            motivos.extend(hallados)
            fila = {"tipo": tipo, "capturas": [x0, y0], "estado": "contradiccion" if hallados else "compatibles",
                    "motivos": hallados}
            comparaciones.append(fila)
            if mismo and not hallados and b0["anterior"] == x0:
                progresiones.append({"capturas": [x0, y0], "firmante": a0["huella_de_clave"]})
    return {"motivos": sorted(set(motivos)), "comparaciones": comparaciones, "progresiones": progresiones,
            "incomparables": incomparables, "pendientes": pendientes}


def _procedencia(referencias: ReferenciasExternas, pv, pa, leidos: dict, fila_cap: list, validas: dict) -> dict:
    comprobaciones, faltan = [], []

    def comprobar(objeto, esperado, presente, motivo):
        if esperado is None:
            faltan.append(objeto)
            return
        estado = "coincide" if presente else "no_coincide"
        comprobaciones.append({"objeto": objeto, "huella": esperado, "estado": estado,
                               "motivos": [] if presente else [motivo]})

    comprobar("politica_del_verificador", referencias.politica_del_verificador,
              referencias.politica_del_verificador == pv.sha256, "huella_de_politica_no_coincide")
    comprobar("politica_de_auditoria", referencias.politica_de_auditoria,
              referencias.politica_de_auditoria == pa.sha256, "huella_de_politica_de_auditoria_no_coincide")
    for h in sorted(referencias.manifiestos):
        comprobar("manifiesto", h, h in leidos, "manifiesto_esperado_no_presentado")
    for h in sorted(referencias.capturas):
        comprobar("captura", h, h in {f["id"] for f in fila_cap}, "captura_esperada_no_presentada")
    sin_referencia = sorted(sha for sha in leidos if sha not in referencias.manifiestos)
    if sin_referencia:
        faltan.append("manifiestos")
    if not referencias.capturas and validas:
        faltan.append("capturas")
    cabezas = []
    por_firmante: dict = {}
    for id_, p in validas.items():
        por_firmante.setdefault(p["huella_de_clave"], []).append((p["secuencia"], id_))
    for firmante, lista in sorted(por_firmante.items()):
        secuencia, id_ = max(lista)
        estado = ("coincide_con_referencia_aportada" if id_ in referencias.capturas
                  else "cabeza_sin_referencia_externa")
        cabezas.append({"firmante": firmante, "secuencia": secuencia, "captura": id_, "estado": estado,
                        "nota": "la mayor posicion presentada; sin referencia externa no puede llamarse ultima"
                        if estado == "cabeza_sin_referencia_externa" else
                        "coincide con una huella aportada por quien audita; no prueba publicacion independiente"})
    return {"aportadas": {"politica_del_verificador": referencias.politica_del_verificador is not None,
                          "politica_de_auditoria": referencias.politica_de_auditoria is not None,
                          "manifiestos": len(referencias.manifiestos), "capturas": len(referencias.capturas)},
            "faltan": faltan, "manifiestos_sin_referencia": sin_referencia, "comprobaciones": comprobaciones,
            "cabezas": cabezas,
            "limite": "una huella copiada de los propios archivos no constituye una publicacion independiente"}


def informe_de_uso_incorrecto(motivo: str) -> dict:
    return {"esquema": ESQUEMA_INFORME, "lectura": {"estado": "no_iniciada", "motivos": [motivo]},
            "resultado": "uso_incorrecto", "autorizacion_operativa": _autorizacion(), "limites": list(LIMITES)}


def codigo_de_salida(informe: dict) -> int:
    return CODIGOS_DE_SALIDA[informe["resultado"]]


def informe_json(informe: dict) -> bytes:
    """JSON determinista: claves ordenadas, UTF-8, LF final."""
    return _ae78.informe_json(informe)


def resumen_legible(informe: dict) -> str:
    """Resumen por expediente, por captura y entre expedientes."""
    lineas = [f"Auditoria cruzada de expedientes portables ({ESQUEMA_INFORME})"]
    lectura = informe["lectura"]
    if lectura["estado"] in ("rechazada", "no_iniciada"):
        lineas.append(f"Lectura: {lectura['estado']} {' '.join(lectura['motivos'])}".rstrip())
    lineas.append("== Expedientes (lectura endurecida y evaluacion AE-78)")
    for fila in informe.get("expedientes", []):
        if fila["lectura"]["estado"] != "superada":
            lineas.append(f"  {fila['nombre']}: lectura rechazada ({', '.join(fila['lectura']['motivos'])}); "
                          "no se evaluo ningun plano")
            continue
        ae78 = fila["ae78"]
        rechazados = [f"{p}: {', '.join(v['motivos'])}" for p, v in sorted(ae78["planos"].items())
                      if v["estado"] == "rechazada"]
        lineas.append(f"  {fila['sha256_manifiesto'][:16]}: AE-78 {ae78['resultado']}; corte "
                      f"{fila['corte_esperado']['valor']}; r0_final {ae78['r0_final']['estado']}; "
                      f"capturado {'si' if fila['capturado'] else 'no'}")
        lineas.extend(f"    rechazada {r}" for r in rechazados)
    if informe.get("conjuntos_de_capturas"):
        lineas.append("== Conjuntos de capturas")
        for c in informe["conjuntos_de_capturas"]:
            lineas.append(f"  {c['nombre']}: lectura {c['lectura']['estado']} {' '.join(c['lectura']['motivos'])}"
                          .rstrip())
    if informe.get("capturas"):
        lineas.append("== Capturas (firmante = clave publica)")
        for f in informe["capturas"]:
            lineas.append(f"  {f['id'][:16]} firmante {f['firmante'][:16]} secuencia {f.get('secuencia', '?')}: "
                          f"{f['estado']}" + (f" ({', '.join(f['motivos'])})" if f["motivos"] else "")
                          + ("" if f["admitida_para_comparar"] else "; no admitida para comparar"))
    entre = informe.get("entre_expedientes") or {}
    if entre:
        lineas.append(f"== Entre expedientes: {entre['estado']}"
                      + (f" ({', '.join(entre['motivos'])})" if entre["motivos"] else ""))
        for inc in entre["capturas"]["incomparables"]:
            lineas.append(f"  incomparables: {', '.join(inc['motivos'])}")
    procedencia = informe.get("procedencia") or {}
    if procedencia:
        lineas.append(f"== Procedencia: faltan {', '.join(procedencia['faltan']) or 'ninguna'}")
        for c in procedencia["comprobaciones"]:
            lineas.append(f"  {c['objeto']} {c['huella'][:16]}: {c['estado']}")
        for c in procedencia["cabezas"]:
            lineas.append(f"  cabeza {c['firmante'][:16]} secuencia {c['secuencia']}: {c['estado']}")
    lineas.append("== Pendientes: autoridad_del_manifiesto, completitud_global y completitud respecto de lo que "
                  "debio existir siguen pendientes")
    lineas.append("== Autorizacion operativa: DENEGADA")
    lineas.append("  AUTORIZA_EVALUACION = False")
    codigo = codigo_de_salida(informe)
    lineas.append(f"Resultado: {informe['resultado']} (codigo {codigo}: {SIGNIFICADO_DE_LOS_CODIGOS[codigo]})")
    return "\n".join(lineas) + "\n"
