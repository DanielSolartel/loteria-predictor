"""
Constancias desprendidas y verificables de una auditoria cruzada AE-79
-Etapa AE-80, validada localmente como trabajo preparatorio.

Una constancia (`constancia-auditoria-cruzada/1`) es una pieza JSON canonica
de AE-52 firmada con Ed25519 mediante las primitivas de AE-76. Atestigua el
estado exacto que observo quien la firma:

- dominio y naturaleza, ambos limitados a fixtures (`DOMINIO_DE_PRUEBA`);
- serie, posicion (`secuencia`) y hash de la constancia anterior;
- huellas de la politica del verificador y de la politica de auditoria;
- huellas de las entradas: SHA-256 del manifiesto de cada expediente y del
  `capturas.json` de cada conjunto de capturas;
- alcance (protocolo, canal y juegos) de los expedientes resumibles;
- huella del informe AE-79 normalizado y su resultado.

El informe AE-79 normalizado se recalcula siempre con el auditor real de
AE-79, con nombres de entrada neutros y sin referencias externas, para que
no dependa de los nombres de los directorios. Ningun informe JSON aportado se
acepta como verdad.

El verificador (`verificar`) recalcula ese estado desde los expedientes, las
capturas y las politicas presentados y lo coteja con las constancias y con
una politica de claves (`politica-constancias-de-prueba/1`) suministrada
aparte. Distingue constancias coincidentes, que no coinciden, lecturas
rechazadas, bifurcaciones firmadas del mismo firmante, desacuerdos entre
firmantes (sin adjudicar) y predecesores o referencias que faltan
(pendientes).

Una firma valida solo prueba la firma de esos bytes frente a una clave
admitida por la politica suministrada. No prueba que la clave pertenezca a
una autoridad real, publicacion fuera de banda, independencia de custodia,
fecha anterior a un plazo, completitud global ni que R0 sea final. Las
secuencias y los vinculos de hashes solo relacionan bytes presentados: no
prueban cronologia ni que no existan otras constancias. No se usa mayoria ni
quorum. `AUTORIZA_EVALUACION = False`; A1-A3, C1-C3, D8 operativa y D9
definitiva siguen sin decidir. Sin red, reloj local, deserializacion
ejecutable ni secretos.
"""
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from app.application.ml import auditoria_cruzada as _ae79
from app.application.ml import expediente_portable as _ae78
from app.application.ml import expediente_r0_recepcion as _ae76
from app.application.ml import propuesta_inferencia_prospectiva as _expediente

ESQUEMA_CONSTANCIA = "constancia-auditoria-cruzada/1"
ESQUEMA_CONSTANCIAS = "constancias-auditoria/1"
ESQUEMA_POLITICA_CONSTANCIAS = "politica-constancias-de-prueba/1"
ESQUEMA_INFORME = "informe-constancias-auditoria/1"
NOMBRE_CONSTANCIAS = "constancias.json"
NOMBRE_POLITICA_CONSTANCIAS = "politica_constancias.json"
DOMINIO_DE_PRUEBA = "loteria-predictor/constancia-auditoria-cruzada/fixture"
"""Separacion de dominio de las firmas. Solo existe el dominio de fixture: la
identidad operativa del dominio y de las series es una decision abierta
(`DECISIONES_ABIERTAS_AE80`)."""
NATURALEZAS = ("fixture_de_prueba",)
CLAVES_DE_LA_CONSTANCIA = ("esquema", "dominio", "naturaleza", "serie", "secuencia", "anterior",
                           "sha256_politica_del_verificador", "sha256_politica_de_auditoria", "entradas", "alcance",
                           "sha256_informe_ae79", "resultado_ae79", "algoritmo", "huella_de_clave")
CAMPOS_DEL_ESTADO = ("sha256_politica_del_verificador", "sha256_politica_de_auditoria", "entradas", "alcance",
                     "sha256_informe_ae79", "resultado_ae79")
"""Campos de la constancia que se recalculan desde las entradas."""
NOMBRE_NEUTRO = "entrada"
MAXIMO_DE_CONJUNTOS_DE_CONSTANCIAS = 8
MAXIMO_DE_CONSTANCIAS = 64

DECISIONES_ABIERTAS_AE80 = MappingProxyType({
    "dominio_y_series_operativos": "identidad operativa del dominio de firma y de las series de constancias (A2)",
    "firmantes_de_constancias": "quien puede firmar constancias, su identidad, custodia y revocacion (A1, A3)",
    "publicacion_de_constancias": "medio de publicacion externa e independiente de las constancias y monitores "
                                  "que comparen lo que ven (A2, C3)",
})


# ---------------------------------------------------------------------------
# Estado auditado (recalculado siempre desde las entradas)
# ---------------------------------------------------------------------------

def _huella(archivos, nombre: str):
    if isinstance(archivos, Mapping) and nombre in archivos:
        return hashlib.sha256(archivos[nombre]).hexdigest()
    return None


@dataclass(frozen=True)
class EstadoAuditado:
    """Estado recalculado de una auditoria AE-79 y sus huellas."""
    informe_ae79: dict
    sha256_informe_ae79: str
    sha256_politica_del_verificador: str | None
    sha256_politica_de_auditoria: str | None
    entradas: dict
    entradas_sin_huella: dict
    alcance: list
    resultado_ae79: dict

    def campos(self) -> dict:
        return {c: getattr(self, c) for c in CAMPOS_DEL_ESTADO}


def estado_auditado(*, expedientes: Sequence, politica_del_verificador, politica_de_auditoria,
                    capturas: Sequence = ()) -> EstadoAuditado:
    """Recalcula el informe AE-79 normalizado (nombres neutros, sin
    referencias externas) y las huellas de las entradas. `expedientes` y
    `capturas` son secuencias de `{ruta: bytes}` o `ExpedienteIlegible`."""
    informe = _ae79.auditar(expedientes=[(NOMBRE_NEUTRO, e) for e in expedientes],
                            politica_del_verificador=politica_del_verificador,
                            politica_de_auditoria=politica_de_auditoria,
                            capturas=[(NOMBRE_NEUTRO, c) for c in capturas])
    exp = [_huella(e, _ae78.NOMBRE_MANIFIESTO) for e in expedientes]
    cap = [_huella(c, _ae79.NOMBRE_CAPTURAS) for c in capturas]
    alcance = set()
    for e in expedientes:
        try:
            resumen = _ae79.resumen_del_expediente(_ae78.leer_expediente(e))
        except (_ae78.ExpedienteIlegible, ValueError, TypeError):
            continue
        alcance.add((resumen["protocolo_hash"], resumen["canal"], tuple(resumen["alcance_de_corte"])))
    return EstadoAuditado(
        informe_ae79=informe, sha256_informe_ae79=hashlib.sha256(_ae79.informe_json(informe)).hexdigest(),
        sha256_politica_del_verificador=_huella(politica_del_verificador, _ae78.NOMBRE_POLITICA),
        sha256_politica_de_auditoria=_huella(politica_de_auditoria, _ae79.NOMBRE_POLITICA_AUDITORIA),
        entradas={"expedientes": sorted({h for h in exp if h}), "conjuntos_de_capturas": sorted({h for h in cap if h})},
        entradas_sin_huella={"expedientes": sum(h is None for h in exp),
                             "conjuntos_de_capturas": sum(h is None for h in cap)},
        alcance=[[p, c, list(j)] for p, c, j in sorted(alcance)],
        resultado_ae79={"resultado": informe["resultado"],
                        "entre_expedientes": (informe.get("entre_expedientes") or {}).get("estado")})


# ---------------------------------------------------------------------------
# Constancia: construccion y lectura estricta
# ---------------------------------------------------------------------------

def construir_constancia(estado: EstadoAuditado, *, serie: str, secuencia: int, anterior: str | None,
                         clave_publica: bytes) -> dict:
    """Pieza de constancia sin firmar; la firma la pone quien tiene la clave."""
    if not isinstance(serie, str) or not _ae79._NOMBRE.fullmatch(serie):
        raise ValueError("serie_mal_formada")
    if type(secuencia) is not int or secuencia < 1 or (secuencia == 1) != (anterior is None):
        raise ValueError("encadenamiento_mal_formado")
    if estado.sha256_politica_del_verificador is None or estado.sha256_politica_de_auditoria is None:
        raise ValueError("politica_sin_huella")
    return {"esquema": ESQUEMA_CONSTANCIA, "dominio": DOMINIO_DE_PRUEBA, "naturaleza": "fixture_de_prueba",
            "serie": serie, "secuencia": secuencia, "anterior": anterior, **estado.campos(),
            "algoritmo": _ae76.ALGORITMO_DE_FIRMA, "huella_de_clave": _ae76.huella_de_clave(clave_publica)}


def _lista_de_huellas(valor) -> bool:
    return (isinstance(valor, list) and all(_ae79.es_huella(h) for h in valor) and valor == sorted(set(valor)))


def _alcance_valido(alcance) -> bool:
    """Forma y tipos de cada elemento antes de comprobar el orden: `sorted`
    solo se aplica a listas de `[huella, canal, [juegos]]`, cuyos elementos
    son comparables entre si."""
    if not isinstance(alcance, list):
        return False
    if not all(isinstance(a, list) and len(a) == 3 and _ae79.es_huella(a[0]) and isinstance(a[1], str)
               and isinstance(a[2], list) and all(isinstance(j, str) for j in a[2]) for a in alcance):
        return False
    return alcance == sorted(alcance)


def leer_constancia(datos: bytes) -> dict:
    """Lectura estricta; `ExpedienteInvalido` con `motivo`."""
    pieza = _ae76._leer(datos, ESQUEMA_CONSTANCIA, CLAVES_DE_LA_CONSTANCIA)
    entradas, alcance, resultado = pieza["entradas"], pieza["alcance"], pieza["resultado_ae79"]
    tipos = (
        isinstance(pieza["serie"], str) and _ae79._NOMBRE.fullmatch(pieza["serie"]) is not None
        and type(pieza["secuencia"]) is int and pieza["secuencia"] >= 1
        and ((pieza["secuencia"] == 1 and pieza["anterior"] is None)
             or (pieza["secuencia"] > 1 and _ae79.es_huella(pieza["anterior"])))
        and all(_ae79.es_huella(pieza[c]) for c in ("sha256_politica_del_verificador",
                                                     "sha256_politica_de_auditoria", "sha256_informe_ae79"))
        and isinstance(entradas, dict) and set(entradas) == {"expedientes", "conjuntos_de_capturas"}
        and all(_lista_de_huellas(v) for v in entradas.values())
        and _alcance_valido(alcance)
        and isinstance(resultado, dict) and set(resultado) == {"resultado", "entre_expedientes"}
        and isinstance(resultado["resultado"], str)
        and (resultado["entre_expedientes"] is None or isinstance(resultado["entre_expedientes"], str)))
    if not tipos:
        raise _ae76.ExpedienteInvalido("pieza_mal_formada")
    if pieza["dominio"] != DOMINIO_DE_PRUEBA:
        raise _ae76.ExpedienteInvalido("dominio_no_admitido")
    if pieza["naturaleza"] not in NATURALEZAS:
        raise _ae76.ExpedienteInvalido("naturaleza_no_admitida")
    return pieza


# ---------------------------------------------------------------------------
# Directorios: conjunto de constancias y politica de claves
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClaveDeFirmanteDePrueba:
    clave_publica: bytes
    etiqueta: str
    naturaleza: str = "fixture_de_prueba"

    def __post_init__(self):
        if self.naturaleza not in NATURALEZAS:
            raise ValueError(f"naturaleza no admitida en AE-80: {self.naturaleza!r}")
        if not isinstance(self.clave_publica, bytes) or len(self.clave_publica) != 32:
            raise ValueError("la clave publica Ed25519 debe tener 32 bytes")


@dataclass(frozen=True)
class PoliticaDeConstancias:
    firmantes: tuple
    sha256: str


def componer_constancias(constancias: Sequence) -> dict:
    archivos: dict = {}
    lista = [_ae78._objeto(f"constancias/{i:03d}", c, archivos) for i, c in enumerate(constancias, start=1)]
    return _ae78._con_manifiesto(NOMBRE_CONSTANCIAS, {"esquema": ESQUEMA_CONSTANCIAS, "constancias": lista},
                                 archivos)


def componer_politica_de_constancias(*, firmantes: Sequence) -> dict:
    archivos: dict = {}
    lista = []
    for i, (clave, etiqueta) in enumerate(firmantes, start=1):
        archivos[f"firmantes/{i:02d}.bin"] = bytes(clave)
        lista.append({"clave_publica": f"firmantes/{i:02d}.bin", "etiqueta": etiqueta})
    return _ae78._con_manifiesto(NOMBRE_POLITICA_CONSTANCIAS, {"esquema": ESQUEMA_POLITICA_CONSTANCIAS,
                                                               "naturaleza": "fixture_de_prueba",
                                                               "firmantes": lista}, archivos)


def leer_constancias(archivos: Mapping[str, bytes], *,
                     limites: "_ae78.Limites" = _ae78.LIMITES_POR_DEFECTO) -> tuple:
    manifiesto = _ae79._leer_manifiesto(archivos, NOMBRE_CONSTANCIAS, ESQUEMA_CONSTANCIAS, limites)
    _ae78._claves(manifiesto, {"esquema", "archivos", "constancias"}, "constancias")
    _ae78._exigir(isinstance(manifiesto["constancias"], list), "constancias")
    if len(manifiesto["constancias"]) > MAXIMO_DE_CONSTANCIAS:
        _ae78._rechazar("demasiadas_constancias")
    refs = [r for c in manifiesto["constancias"] for r in _ae78._rutas_de_objeto(c, "constancia")]
    _ae78._comprobar_archivos(archivos, NOMBRE_CONSTANCIAS, manifiesto, refs, limites)
    return tuple(_ae78._firmado(archivos, c) for c in manifiesto["constancias"])


def leer_politica_de_constancias(archivos: Mapping[str, bytes], *,
                                 limites: "_ae78.Limites" = _ae78.LIMITES_POR_DEFECTO) -> PoliticaDeConstancias:
    """Lectura endurecida; una misma clave con dos etiquetas se rechaza."""
    manifiesto = _ae79._leer_manifiesto(archivos, NOMBRE_POLITICA_CONSTANCIAS, ESQUEMA_POLITICA_CONSTANCIAS, limites)
    _ae78._claves(manifiesto, {"esquema", "naturaleza", "archivos", "firmantes"}, "politica_de_constancias")
    if manifiesto["naturaleza"] not in NATURALEZAS:
        _ae78._rechazar("naturaleza_no_admitida", str(manifiesto["naturaleza"])[:80])
    _ae78._exigir(isinstance(manifiesto["firmantes"], list), "firmantes")
    refs = []
    for f in manifiesto["firmantes"]:
        _ae78._claves(f, {"clave_publica", "etiqueta"}, "firmante")
        _ae78._exigir(isinstance(f["etiqueta"], str), "etiqueta")
        refs.append(f["clave_publica"])
    _ae78._comprobar_archivos(archivos, NOMBRE_POLITICA_CONSTANCIAS, manifiesto, refs, limites)
    try:
        firmantes = tuple(ClaveDeFirmanteDePrueba(archivos[f["clave_publica"]], f["etiqueta"])
                          for f in manifiesto["firmantes"])
    except (ValueError, TypeError) as error:
        _ae78._rechazar("estructura_invalida", str(error)[:120])
    claves = [f.clave_publica for f in firmantes]
    if len(claves) != len(set(claves)):
        _ae78._rechazar("clave_duplicada", "misma clave publica con dos etiquetas")
    return PoliticaDeConstancias(firmantes, hashlib.sha256(archivos[NOMBRE_POLITICA_CONSTANCIAS]).hexdigest())


# ---------------------------------------------------------------------------
# Verificacion
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReferenciasDeConstancias:
    """Huellas que aporta quien verifica desde fuera: de la politica de
    constancias y de constancias esperadas (SHA-256 de su `datos.json`).
    Una huella copiada de los propios archivos no es una publicacion."""
    politica_de_constancias: str | None = None
    constancias: frozenset = field(default_factory=frozenset)

    def __post_init__(self):
        if self.politica_de_constancias is not None and not _ae79.es_huella(self.politica_de_constancias):
            raise ValueError("huella_mal_formada")
        if not all(_ae79.es_huella(h) for h in self.constancias):
            raise ValueError("huella_mal_formada")


CONTRADICCIONES = ("bifurcacion_firmada", "vinculo_roto", "informes_incompatibles_del_mismo_firmante",
                   "desacuerdo_entre_firmantes")
"""Bytes firmados presentados que se contradicen. Ninguno adjudica cual es
cierto."""
NO_COINCIDENCIAS = (
    "pieza_ilegible", "pieza_no_canonica", "pieza_mal_formada", "version_desconocida", "dominio_no_admitido",
    "naturaleza_no_admitida", "firma_no_coincide", "clave_no_admitida", "huella_de_clave_no_coincide",
    "clave_mal_formada", "algoritmo_no_admitido", "firmante_no_independiente_del_canal",
    "politica_no_coincide", "entrada_atestada_no_presentada", "entrada_presentada_no_atestada", "alcance_no_coincide", "informe_no_coincide", "resultado_no_coincide",
    "huella_de_politica_de_constancias_no_coincide", "constancia_esperada_no_presentada",
)
LECTURAS_DE_ENTRADAS = ("entrada_atestada_presentada_pero_ilegible", "entrada_presentada_ilegible_sin_huella")
"""Entradas presentadas pero invalidas: no son una constancia que no
coincide sino una lectura rechazada (codigo 3), distinta de una entrada
atestada que no se presento (`entrada_atestada_no_presentada`, codigo 4)."""
PENDIENTES = ("predecesor_no_presentado", "cabeza_sin_referencia_externa", "publicacion_externa_no_aportada",
              "sin_constancia_admitida")

CODIGOS_DE_SALIDA = MappingProxyType({"constancia_y_auditoria_coincidentes": 0, "contradiccion_comprobada": 1,
                                      "uso_incorrecto": 2, "lectura_rechazada": 3, "constancia_no_coincide": 4,
                                      "sin_constancia_admitida": 5})
SIGNIFICADO_DE_LOS_CODIGOS = MappingProxyType({
    0: "las constancias cabeza admitidas coinciden con la auditoria recalculada; no autoriza evaluacion y los "
       "pendientes siguen pendientes",
    1: "constancias firmadas presentadas que se contradicen; no adjudica cual es cierta",
    2: "uso incorrecto del comando; no se verifico nada",
    3: "la lectura endurecida rechazo al menos una entrada; esa entrada no se evaluo",
    4: "una constancia, una firma, una politica o una huella esperada no coincide, sin contradiccion comprobada",
    5: "no hay ninguna constancia admitida que cotejar: nada queda atestiguado",
})
"""Prioridad: 1, 3, 4, 5 y 0. Ningun codigo significa autorizacion."""

LIMITES = (
    "claves de firmantes, politicas y constancias son de fixture; una firma valida solo prueba la firma de esos "
    "bytes frente a una clave admitida por la politica suministrada",
    "no prueba que la clave pertenezca a una autoridad real, publicacion fuera de banda, independencia de "
    "custodia, fecha anterior a un plazo, completitud global ni que R0 sea final",
    "secuencias y vinculos de hashes solo relacionan bytes presentados: no prueban cronologia ni que no existan "
    "otras constancias ocultas; una cabeza sin referencia externa no es la ultima version",
    "no se usa mayoria, quorum ni cantidad de firmas como sustituto de la autoridad del conjunto esperado",
    "el informe AE-79 nunca se acepta aportado: se recalcula desde las entradas con nombres neutros",
    "una huella copiada de los propios archivos no es una publicacion independiente",
    "RFC 9162 conserva solo su alcance de certificados y precertificados; estas constancias no heredan sus "
    "garantias",
    "ejecutar la verificacion no autoriza evaluacion ni convierte R0 en final; AUTORIZA_EVALUACION es False",
)


def _plano(estado: str, motivos=()) -> dict:
    return {"estado": estado, "motivos": list(dict.fromkeys(motivos))}


def _firma(objeto, pieza, politica: PoliticaDeConstancias, politica_verificador) -> dict:
    admitidas = _ae76.PoliticaDeClavesDePrueba(claves=tuple(
        _ae76.ClaveDePrueba(f.clave_publica, "canal", f.etiqueta) for f in politica.firmantes))
    planos = _ae76._firma(objeto, pieza, admitidas, "canal")
    # Una pieza ilegible deja la huella declarada sin evaluar: eso ya consta
    # en la lectura y no se repite como motivo de la firma.
    motivos = [m for r in planos.values() if r.estado in ("rechazada", "pendiente") for m in r.motivos]
    if politica_verificador is not None and (politica_verificador.claves.admite(objeto.clave_publica, "canal")
                                             or politica_verificador.claves.admite(objeto.clave_publica,
                                                                                   "firmante_r0")):
        motivos.append("firmante_no_independiente_del_canal")
    if motivos:
        return _plano("rechazada", motivos)
    return _plano("superada" if all(r.estado == "superada" for r in planos.values()) else "no_evaluable")


def _cotejar(pieza: dict, estado: EstadoAuditado, ilegibles_presentes: set) -> list:
    """Motivos por los que una constancia no atestigua el estado recalculado."""
    motivos = []
    if (pieza["sha256_politica_del_verificador"] != estado.sha256_politica_del_verificador
            or pieza["sha256_politica_de_auditoria"] != estado.sha256_politica_de_auditoria):
        motivos.append("politica_no_coincide")
    for clase in ("expedientes", "conjuntos_de_capturas"):
        atestadas, presentes = set(pieza["entradas"][clase]), set(estado.entradas[clase])
        for h in sorted(atestadas):
            if h not in presentes:
                motivos.append("entrada_atestada_no_presentada")
            elif h in ilegibles_presentes:
                motivos.append("entrada_atestada_presentada_pero_ilegible")
        if presentes - atestadas:
            motivos.append("entrada_presentada_no_atestada")
    if estado.entradas_sin_huella["expedientes"] or estado.entradas_sin_huella["conjuntos_de_capturas"]:
        motivos.append("entrada_presentada_ilegible_sin_huella")
    if pieza["alcance"] != estado.alcance:
        motivos.append("alcance_no_coincide")
    if pieza["sha256_informe_ae79"] != estado.sha256_informe_ae79:
        motivos.append("informe_no_coincide")
    if pieza["resultado_ae79"] != estado.resultado_ae79:
        motivos.append("resultado_no_coincide")
    return list(dict.fromkeys(motivos))


def _leer_entrada(contenido, lector):
    if isinstance(contenido, _ae78.ExpedienteIlegible):
        return None, contenido
    try:
        return lector(contenido), None
    except _ae78.ExpedienteIlegible as error:
        return None, error


def verificar(*, expedientes: Sequence, politica_del_verificador, politica_de_auditoria, capturas: Sequence = (),
              politica_de_constancias, constancias: Sequence = (),
              referencias: ReferenciasDeConstancias = ReferenciasDeConstancias()) -> dict:
    """Recalcula la auditoria AE-79 y la coteja con las constancias.
    `constancias` es una secuencia de `{ruta: bytes}` o
    `ExpedienteIlegible`, uno por directorio. Devuelve el informe."""
    if len(constancias) > MAXIMO_DE_CONJUNTOS_DE_CONSTANCIAS:
        raise ValueError("numero_de_conjuntos_de_constancias_fuera_de_limites")
    estado = estado_auditado(expedientes=expedientes, politica_del_verificador=politica_del_verificador,
                             politica_de_auditoria=politica_de_auditoria, capturas=capturas)
    informe79 = estado.informe_ae79
    lectura_rechazada = informe79["lectura"]["estado"] != "superada"
    pv, _ = _leer_entrada(politica_del_verificador, _ae78.leer_politica)
    politica, error = _leer_entrada(politica_de_constancias, leer_politica_de_constancias)
    base = {"esquema": ESQUEMA_INFORME,
            "estado_recalculado": {**estado.campos(), "entradas_sin_huella": estado.entradas_sin_huella},
            "informe_ae79": informe79,
            "pendientes": _pendientes(), "autorizacion_operativa": _autorizacion(), "limites": list(LIMITES)}
    if error is not None:
        return {**base, "lectura": {"estado": "rechazada", "objeto": "politica_de_constancias",
                                    "motivos": [error.motivo]},
                "conjuntos_de_constancias": [], "constancias": [], "series": [], "entre_constancias": {},
                "procedencia": {}, "resultado": "lectura_rechazada"}

    # Entradas presentadas pero ilegibles con huella de manifiesto conocida.
    ilegibles = set()
    for e in expedientes:
        h = _huella(e, _ae78.NOMBRE_MANIFIESTO)
        if h is not None and _leer_entrada(e, _ae78.leer_expediente)[1] is not None:
            ilegibles.add(h)
    for c in capturas:
        h = _huella(c, _ae79.NOMBRE_CAPTURAS)
        if h is not None and _leer_entrada(c, _ae79.leer_capturas)[1] is not None:
            ilegibles.add(h)

    conjuntos, filas, admitidas, vistos = [], [], {}, set()
    no_coincide = set()
    for contenido in constancias:
        objetos, error = _leer_entrada(contenido, leer_constancias)
        if error is not None:
            lectura_rechazada = True
            conjuntos.append({"lectura": _plano("rechazada", (error.motivo,))})
            continue
        conjuntos.append({"lectura": _plano("superada"), "constancias": len(objetos),
                          "sha256": _huella(contenido, NOMBRE_CONSTANCIAS)})
        for objeto in objetos:
            if (objeto.datos, objeto.firma, objeto.clave_publica) in vistos:
                continue
            vistos.add((objeto.datos, objeto.firma, objeto.clave_publica))
            id_ = _ae76.hash_de_pieza(objeto.datos)
            fila = {"id": id_, "firmante": _ae76.huella_de_clave(objeto.clave_publica),
                    "sha256_firma": hashlib.sha256(objeto.firma).hexdigest()}
            try:
                pieza = leer_constancia(objeto.datos)
            except _ae76.ExpedienteInvalido as error:
                pieza = None
                fila["lectura"] = _plano("rechazada", (error.motivo,))
            else:
                fila["lectura"] = _plano("superada")
                fila.update(serie=pieza["serie"], secuencia=pieza["secuencia"])
            fila["firma"] = _firma(objeto, pieza, politica, pv)
            fila["admitida"] = pieza is not None and fila["firma"]["estado"] == "superada"
            fila["motivos"] = [*fila["lectura"]["motivos"], *fila["firma"]["motivos"]]
            no_coincide.update(fila["motivos"])
            if fila["admitida"]:
                admitidas.setdefault(id_, pieza)
                fila["cotejo"] = _cotejar(pieza, estado, ilegibles)
            filas.append(fila)

    # Series por firmante: bifurcaciones, vinculos, predecesores y cabezas.
    series, contradicciones, entre = {}, [], []
    for id_, p in admitidas.items():
        clave = (p["huella_de_clave"], p["serie"])
        series.setdefault(clave, {}).setdefault(p["secuencia"], []).append(id_)
    resumen_series, cabezas = [], set()
    for (firmante, serie), posiciones in sorted(series.items()):
        pendientes, roturas = [], []
        for secuencia, ids in sorted(posiciones.items()):
            if len(ids) > 1:
                contradicciones.append("bifurcacion_firmada")
                entre.append({"tipo": "mismo_firmante", "firmante": firmante, "serie": serie, "secuencia": secuencia,
                              "constancias": sorted(ids), "motivo": "bifurcacion_firmada"})
            if secuencia == 1:
                continue
            previas = posiciones.get(secuencia - 1, [])
            for id_ in sorted(ids):
                if not previas:
                    pendientes.append({"constancia": id_, "motivo": "predecesor_no_presentado"})
                elif admitidas[id_]["anterior"] not in previas:
                    roturas.append(id_)
                    contradicciones.append("vinculo_roto")
                    entre.append({"tipo": "mismo_firmante", "firmante": firmante, "serie": serie,
                                  "secuencia": secuencia, "constancias": sorted([id_, *previas]),
                                  "motivo": "vinculo_roto"})
        maximo = max(posiciones)
        cabezas.update(posiciones[maximo])
        completa = (sorted(posiciones) == list(range(1, maximo + 1)) and not pendientes and not roturas
                    and all(len(v) == 1 for v in posiciones.values()))
        resumen_series.append({
            "firmante": firmante, "serie": serie, "posiciones": sorted(posiciones), "cabezas": sorted(posiciones[maximo]),
            "continuidad": ("enlazada_desde_la_primera_entre_lo_presentado" if completa
                            else "pendiente" if not roturas and all(len(v) == 1 for v in posiciones.values())
                            else "contradiccion"),
            "pendientes": pendientes,
            "nota": "la continuidad solo relaciona bytes presentados; no prueba que sea la ultima ni que no haya "
                    "otras constancias"})

    # Constancias de firmantes distintos, o series distintas del mismo
    # firmante, que atestiguan las mismas politicas y entradas.
    ids = sorted(admitidas)
    for i, x in enumerate(ids):
        for y in ids[i + 1:]:
            a, b = admitidas[x], admitidas[y]
            mismas = all(a[c] == b[c] for c in ("sha256_politica_del_verificador", "sha256_politica_de_auditoria",
                                                 "entradas"))
            if not mismas or (a["huella_de_clave"] == b["huella_de_clave"] and a["serie"] == b["serie"]):
                continue
            if a["sha256_informe_ae79"] != b["sha256_informe_ae79"] or a["resultado_ae79"] != b["resultado_ae79"]:
                motivo = ("informes_incompatibles_del_mismo_firmante" if a["huella_de_clave"] == b["huella_de_clave"]
                          else "desacuerdo_entre_firmantes")
                contradicciones.append(motivo)
                entre.append({"tipo": "mismas_entradas", "constancias": [x, y], "motivo": motivo,
                              "nota": "no se adjudica cual tiene razon"})

    for fila in filas:
        if fila["admitida"]:
            fila["rol"] = "cabeza" if fila["id"] in cabezas else "predecesor"
            if fila["rol"] == "cabeza":
                fallos = [m for m in fila["cotejo"] if m in NO_COINCIDENCIAS]
                fila["estado"] = "no_coincide" if fallos else "coincide"
                no_coincide.update(fallos)
            else:
                fila["estado"] = "atestigua_el_estado_presentado" if not fila["cotejo"] else "atestigua_otro_estado"
        else:
            fila["estado"] = "no_admitida"

    procedencia = _procedencia(referencias, politica, filas, cabezas)
    no_coincide.update(m for c in procedencia["comprobaciones"] if c["estado"] == "no_coincide" for m in c["motivos"])
    contradicciones = sorted(set(contradicciones))
    if contradicciones:
        resultado = "contradiccion_comprobada"
    elif lectura_rechazada:
        resultado = "lectura_rechazada"
    elif no_coincide & set(NO_COINCIDENCIAS):
        resultado = "constancia_no_coincide"
    elif not admitidas:
        resultado = "sin_constancia_admitida"
    else:
        resultado = "constancia_y_auditoria_coincidentes"
    return {**base,
            "lectura": {"estado": "rechazada_en_parte" if lectura_rechazada else "superada", "objeto": "entradas"},
            "politica_de_constancias": {"esquema": ESQUEMA_POLITICA_CONSTANCIAS, "sha256": politica.sha256,
                                        "naturaleza": "fixture_de_prueba",
                                        "firmantes": sorted(_ae76.huella_de_clave(f.clave_publica)
                                                            for f in politica.firmantes),
                                        "origen": "suministrada_a_quien_verifica_no_a_las_constancias"},
            "conjuntos_de_constancias": sorted(conjuntos, key=lambda c: (c["lectura"]["estado"], c.get("sha256") or "",
                                                                        c["lectura"]["motivos"])),
            "constancias": sorted(filas, key=lambda f: (f["firmante"], f.get("serie", ""), f.get("secuencia", 0),
                                                        f["id"], f["sha256_firma"])),
            "series": resumen_series,
            "entre_constancias": {"motivos": contradicciones, "hallazgos": entre},
            "procedencia": procedencia,
            "resultado": resultado}


def _pendientes() -> dict:
    return {"planos": {
        "publicacion_externa": _plano("pendiente", ("publicacion_externa_no_aportada", "decision_a2_sin_tomar")),
        "autoridad_del_conjunto_esperado": _plano("pendiente", ("decision_c3_sin_tomar",
                                                                "cantidad_de_firmas_no_es_autoridad")),
        "completitud_global": _plano("pendiente", ("sin_fuente_autorizada",)),
        "cronologia": _plano("pendiente", ("secuencia_no_es_tiempo",)),
    }, "decisiones_sin_tomar": list(_ae79.DECISIONES_ABIERTAS),
        "decisiones_abiertas_ae80": dict(DECISIONES_ABIERTAS_AE80)}


def _autorizacion() -> dict:
    return {"estado": "denegada", "AUTORIZA_EVALUACION": _expediente.AUTORIZA_EVALUACION}


def _procedencia(referencias: ReferenciasDeConstancias, politica: PoliticaDeConstancias, filas: list,
                 cabezas: set) -> dict:
    comprobaciones, faltan = [], []
    if referencias.politica_de_constancias is None:
        faltan.append("politica_de_constancias")
    else:
        coincide = referencias.politica_de_constancias == politica.sha256
        comprobaciones.append({"objeto": "politica_de_constancias", "huella": referencias.politica_de_constancias,
                               "estado": "coincide" if coincide else "no_coincide",
                               "motivos": [] if coincide else ["huella_de_politica_de_constancias_no_coincide"]})
    presentes = {f["id"] for f in filas}
    for h in sorted(referencias.constancias):
        comprobaciones.append({"objeto": "constancia", "huella": h,
                               "estado": "coincide" if h in presentes else "no_coincide",
                               "motivos": [] if h in presentes else ["constancia_esperada_no_presentada"]})
    if not referencias.constancias:
        faltan.append("constancias")
    estado_cabezas = [{"constancia": c, "estado": "coincide_con_referencia_aportada" if c in referencias.constancias
                       else "cabeza_sin_referencia_externa"} for c in sorted(cabezas)]
    return {"faltan": faltan, "comprobaciones": comprobaciones, "cabezas": estado_cabezas,
            "publicacion_externa": "no_aportada",
            "limite": "una huella copiada de los propios archivos no constituye una publicacion independiente"}


def informe_de_lectura_rechazada(objeto: str, motivo: str) -> dict:
    return {"esquema": ESQUEMA_INFORME, "lectura": {"estado": "rechazada", "objeto": objeto, "motivos": [motivo]},
            "resultado": "lectura_rechazada", "pendientes": _pendientes(), "autorizacion_operativa": _autorizacion(),
            "limites": list(LIMITES)}


def codigo_de_salida(informe: dict) -> int:
    return CODIGOS_DE_SALIDA[informe["resultado"]]


def informe_json(informe: dict) -> bytes:
    return _ae78.informe_json(informe)


def resumen_legible(informe: dict) -> str:
    lineas = [f"Verificacion de constancias de auditoria cruzada ({ESQUEMA_INFORME})"]
    if informe["lectura"]["estado"] == "rechazada":
        lineas.append(f"Lectura: rechazada {informe['lectura']['objeto']} {' '.join(informe['lectura']['motivos'])}")
    ae79 = informe.get("informe_ae79")
    if ae79:
        lineas.append(f"== Auditoria AE-79 recalculada: {ae79['resultado']} (codigo "
                      f"{_ae79.codigo_de_salida(ae79)}); informe "
                      f"{informe['estado_recalculado']['sha256_informe_ae79'][:16]}")
    for c in informe.get("conjuntos_de_constancias", []):
        if c["lectura"]["estado"] != "superada":
            lineas.append(f"  conjunto de constancias: lectura rechazada ({', '.join(c['lectura']['motivos'])})")
    if informe.get("constancias"):
        lineas.append("== Constancias (firmante = clave publica)")
        for f in informe["constancias"]:
            detalle = f["motivos"] or f.get("cotejo") or []
            lineas.append(f"  {f['id'][:16]} firmante {f['firmante'][:16]} serie {f.get('serie', '?')} posicion "
                          f"{f.get('secuencia', '?')} [{f.get('rol', '-')}]: {f['estado']}"
                          + (f" ({', '.join(detalle)})" if detalle else ""))
    for s in informe.get("series", []):
        lineas.append(f"  serie {s['serie']} de {s['firmante'][:16]}: {s['continuidad']}"
                      + (f" ({', '.join(p['motivo'] for p in s['pendientes'])})" if s["pendientes"] else ""))
    entre = informe.get("entre_constancias") or {}
    if entre:
        lineas.append(f"== Entre constancias: {', '.join(entre['motivos']) or 'sin contradiccion detectable'}")
    procedencia = informe.get("procedencia") or {}
    if procedencia:
        lineas.append(f"== Procedencia: faltan {', '.join(procedencia['faltan']) or 'ninguna'}; publicacion "
                      f"externa {procedencia['publicacion_externa']}")
        for c in procedencia["cabezas"]:
            lineas.append(f"  cabeza {c['constancia'][:16]}: {c['estado']}")
    lineas.append("== Pendientes: publicacion externa, autoridad del conjunto esperado, completitud global y "
                  "cronologia siguen pendientes")
    lineas.append("== Autorizacion operativa: DENEGADA")
    lineas.append("  AUTORIZA_EVALUACION = False")
    codigo = codigo_de_salida(informe)
    lineas.append(f"Resultado: {informe['resultado']} (codigo {codigo}: {SIGNIFICADO_DE_LOS_CODIGOS[codigo]})")
    return "\n".join(lineas) + "\n"
