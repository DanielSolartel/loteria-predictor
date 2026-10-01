"""
Publicacion sintetica y monitoreo cruzado de constancias AE-80
-Etapa AE-81, validada localmente como trabajo preparatorio.

Cuatro formatos versionados, canonicos (JSON de AE-52) y con separacion de
dominio. Las piezas firmadas usan el `ObjetoFirmado` y la firma Ed25519 de
AE-76; los directorios, el manifiesto de archivos declarados y la lectura
endurecida de AE-78:

- `checkpoint-publicacion-constancias/1`, firmado por un publicador: un
  registro, una posicion, el hash del checkpoint anterior, la huella de la
  politica de claves de AE-80, el dominio de las constancias y las cabezas
  AE-80 observadas (firmante, serie, secuencia y hash de la constancia);
- `observacion-checkpoint/1`, firmada por un monitor: el SHA-256 exacto de
  los bytes del checkpoint que vio, su publicador, registro y posicion;
- `politica-rol-de-prueba/1`: una politica de claves por rol (`publicador`
  o `monitor`), suministrada aparte; una clave no puede repetirse ni
  servir en dos roles;
- `inventario-esperado-de-prueba/1`: referencias de checkpoints, cabezas y
  monitores esperados, con su procedencia etiquetada.

El verificador (`verificar`) recalcula AE-79 y AE-80 con sus verificadores
reales y vincula las cabezas AE-80 con los checkpoints y estos con las
observaciones. Separa integridad y firmas, concordancia con referencias,
cobertura del inventario, publicacion externa, autoridad, cronologia,
completitud global y autorizacion operativa. Distingue bifurcaciones
firmadas del publicador, observaciones incompatibles con el checkpoint que
nombran, progresiones validas, evidencia ausente y discrepancias entre
actores sin contexto para adjudicarlas.

Una posicion o un vinculo de hashes no prueban anterioridad ni cronologia;
un archivo local, dos firmas o una huella copiada no acreditan publicacion
externa, independencia ni completitud. Todo es de fixture.
`AUTORIZA_EVALUACION = False` y `r0_final` no se promociona. A1-A3, C1-C3,
D8 operativa y D9 definitiva siguen sin decidir. Sin red, reloj local,
deserializacion ejecutable ni secretos.
"""
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from app.application.ml import auditoria_cruzada as _ae79
from app.application.ml import constancias_auditoria as _ae80
from app.application.ml import expediente_portable as _ae78
from app.application.ml import expediente_r0_recepcion as _ae76
from app.application.ml import propuesta_inferencia_prospectiva as _expediente

ESQUEMA_CHECKPOINT = "checkpoint-publicacion-constancias/1"
ESQUEMA_OBSERVACION = "observacion-checkpoint/1"
ESQUEMA_CHECKPOINTS = "checkpoints-publicacion/1"
ESQUEMA_OBSERVACIONES = "observaciones-monitor/1"
ESQUEMA_POLITICA_ROL = "politica-rol-de-prueba/1"
ESQUEMA_INVENTARIO = "inventario-esperado-de-prueba/1"
ESQUEMA_INFORME = "informe-publicacion-constancias/1"
NOMBRE_CHECKPOINTS = "checkpoints.json"
NOMBRE_OBSERVACIONES = "observaciones.json"
NOMBRE_POLITICA_ROL = "politica_rol.json"
NOMBRE_INVENTARIO = "inventario.json"
DOMINIO_CHECKPOINT = "loteria-predictor/checkpoint-constancias/fixture"
DOMINIO_OBSERVACION = "loteria-predictor/observacion-checkpoint/fixture"
"""Separacion de dominio: solo existen dominios de fixture. Un checkpoint,
una observacion y una constancia AE-80 tienen esquemas y dominios
distintos, asi que unos bytes firmados no sirven como otra pieza."""
NATURALEZAS = ("fixture_de_prueba",)
ROLES = ("publicador", "monitor")
PROCEDENCIAS_DEL_INVENTARIO = ("declarada_por_quien_verifica", "copiada_de_lo_presentado")
CLAVES_DEL_CHECKPOINT = ("esquema", "dominio", "naturaleza", "registro", "posicion", "anterior",
                         "sha256_politica_de_constancias", "dominio_de_constancias", "cabezas", "algoritmo",
                         "huella_de_clave")
CLAVES_DE_LA_OBSERVACION = ("esquema", "dominio", "naturaleza", "registro", "posicion", "publicador",
                            "sha256_checkpoint", "algoritmo", "huella_de_clave")
MAXIMO_DE_CONJUNTOS = 8
MAXIMO_DE_PIEZAS = 64


# ---------------------------------------------------------------------------
# Construccion y lectura estricta de piezas
# ---------------------------------------------------------------------------

def cabezas_de_constancias(informe_ae80: dict) -> list:
    """Cabezas AE-80 admitidas, como `[firmante, serie, secuencia, id]`."""
    return sorted([c["firmante"], c["serie"], c["secuencia"], c["id"]]
                  for c in informe_ae80.get("constancias", []) if c.get("admitida") and c.get("rol") == "cabeza")


def construir_checkpoint(*, cabezas: Sequence, sha256_politica_de_constancias: str, registro: str, posicion: int,
                         anterior: str | None, clave_publica: bytes) -> dict:
    """Pieza de checkpoint sin firmar; la firma la pone quien publica."""
    if not isinstance(registro, str) or not _ae79._NOMBRE.fullmatch(registro):
        raise ValueError("registro_mal_formado")
    if type(posicion) is not int or posicion < 1 or (posicion == 1) != (anterior is None):
        raise ValueError("encadenamiento_mal_formado")
    return {"esquema": ESQUEMA_CHECKPOINT, "dominio": DOMINIO_CHECKPOINT, "naturaleza": "fixture_de_prueba",
            "registro": registro, "posicion": posicion, "anterior": anterior,
            "sha256_politica_de_constancias": sha256_politica_de_constancias,
            "dominio_de_constancias": _ae80.DOMINIO_DE_PRUEBA, "cabezas": sorted([list(c) for c in cabezas]),
            "algoritmo": _ae76.ALGORITMO_DE_FIRMA, "huella_de_clave": _ae76.huella_de_clave(clave_publica)}


def construir_observacion(checkpoint, *, clave_publica: bytes) -> dict:
    """Observacion sin firmar de los bytes exactos de un checkpoint."""
    pieza = leer_checkpoint(checkpoint.datos)
    return {"esquema": ESQUEMA_OBSERVACION, "dominio": DOMINIO_OBSERVACION, "naturaleza": "fixture_de_prueba",
            "registro": pieza["registro"], "posicion": pieza["posicion"], "publicador": pieza["huella_de_clave"],
            "sha256_checkpoint": _ae76.hash_de_pieza(checkpoint.datos), "algoritmo": _ae76.ALGORITMO_DE_FIRMA,
            "huella_de_clave": _ae76.huella_de_clave(clave_publica)}


def _posicion_valida(pieza: dict) -> bool:
    return (isinstance(pieza["registro"], str) and _ae79._NOMBRE.fullmatch(pieza["registro"]) is not None
            and type(pieza["posicion"]) is int and pieza["posicion"] >= 1)


def _cabezas_validas(cabezas) -> bool:
    """Forma y tipos antes del orden y de la unicidad."""
    if not isinstance(cabezas, list):
        return False
    if not all(isinstance(c, list) and len(c) == 4 and _ae79.es_huella(c[0]) and isinstance(c[1], str)
               and _ae79._NOMBRE.fullmatch(c[1]) is not None and type(c[2]) is int and c[2] >= 1
               and _ae79.es_huella(c[3]) for c in cabezas):
        return False
    return cabezas == sorted(cabezas) and len({(c[0], c[1]) for c in cabezas}) == len(cabezas)


def _comun(pieza: dict, dominio: str):
    if pieza["dominio"] != dominio:
        raise _ae76.ExpedienteInvalido("dominio_no_admitido")
    if pieza["naturaleza"] not in NATURALEZAS:
        raise _ae76.ExpedienteInvalido("naturaleza_no_admitida")


def leer_checkpoint(datos: bytes) -> dict:
    """Lectura estricta (lector compartido de AE-76); `ExpedienteInvalido`."""
    pieza = _ae76._leer(datos, ESQUEMA_CHECKPOINT, CLAVES_DEL_CHECKPOINT)
    if not (_posicion_valida(pieza)
            and ((pieza["posicion"] == 1 and pieza["anterior"] is None)
                 or (pieza["posicion"] > 1 and _ae79.es_huella(pieza["anterior"])))
            and _ae79.es_huella(pieza["sha256_politica_de_constancias"])
            and isinstance(pieza["dominio_de_constancias"], str) and _cabezas_validas(pieza["cabezas"])):
        raise _ae76.ExpedienteInvalido("pieza_mal_formada")
    _comun(pieza, DOMINIO_CHECKPOINT)
    return pieza


def leer_observacion(datos: bytes) -> dict:
    pieza = _ae76._leer(datos, ESQUEMA_OBSERVACION, CLAVES_DE_LA_OBSERVACION)
    if not (_posicion_valida(pieza) and _ae79.es_huella(pieza["publicador"])
            and _ae79.es_huella(pieza["sha256_checkpoint"])):
        raise _ae76.ExpedienteInvalido("pieza_mal_formada")
    _comun(pieza, DOMINIO_OBSERVACION)
    return pieza


# ---------------------------------------------------------------------------
# Directorios: conjuntos, politicas por rol e inventario
# ---------------------------------------------------------------------------

def _componer_conjunto(nombre: str, esquema: str, clave: str, prefijo: str, objetos: Sequence) -> dict:
    archivos: dict = {}
    lista = [_ae78._objeto(f"{prefijo}/{i:03d}", o, archivos) for i, o in enumerate(objetos, start=1)]
    return _ae78._con_manifiesto(nombre, {"esquema": esquema, clave: lista}, archivos)


def componer_checkpoints(checkpoints: Sequence) -> dict:
    return _componer_conjunto(NOMBRE_CHECKPOINTS, ESQUEMA_CHECKPOINTS, "checkpoints", "checkpoints", checkpoints)


def componer_observaciones(observaciones: Sequence) -> dict:
    return _componer_conjunto(NOMBRE_OBSERVACIONES, ESQUEMA_OBSERVACIONES, "observaciones", "observaciones",
                              observaciones)


def _leer_conjunto(archivos, nombre: str, esquema: str, clave: str, limites) -> tuple:
    manifiesto = _ae79._leer_manifiesto(archivos, nombre, esquema, limites)
    _ae78._claves(manifiesto, {"esquema", "archivos", clave}, clave)
    _ae78._exigir(isinstance(manifiesto[clave], list), clave)
    if len(manifiesto[clave]) > MAXIMO_DE_PIEZAS:
        _ae78._rechazar("demasiadas_piezas")
    refs = [r for o in manifiesto[clave] for r in _ae78._rutas_de_objeto(o, clave)]
    _ae78._comprobar_archivos(archivos, nombre, manifiesto, refs, limites)
    return tuple(_ae78._firmado(archivos, o) for o in manifiesto[clave])


def leer_checkpoints(archivos: Mapping[str, bytes], *, limites=_ae78.LIMITES_POR_DEFECTO) -> tuple:
    return _leer_conjunto(archivos, NOMBRE_CHECKPOINTS, ESQUEMA_CHECKPOINTS, "checkpoints", limites)


def leer_observaciones(archivos: Mapping[str, bytes], *, limites=_ae78.LIMITES_POR_DEFECTO) -> tuple:
    return _leer_conjunto(archivos, NOMBRE_OBSERVACIONES, ESQUEMA_OBSERVACIONES, "observaciones", limites)


@dataclass(frozen=True)
class PoliticaDeRol:
    rol: str
    claves: tuple
    sha256: str

    def admite(self, clave_publica: bytes) -> bool:
        return clave_publica in self.claves


def componer_politica_de_rol(*, rol: str, claves: Sequence) -> dict:
    archivos: dict = {}
    lista = []
    for i, (clave, etiqueta) in enumerate(claves, start=1):
        archivos[f"claves/{i:02d}.bin"] = bytes(clave)
        lista.append({"clave_publica": f"claves/{i:02d}.bin", "etiqueta": etiqueta})
    return _ae78._con_manifiesto(NOMBRE_POLITICA_ROL, {"esquema": ESQUEMA_POLITICA_ROL,
                                                       "naturaleza": "fixture_de_prueba", "rol": rol,
                                                       "claves": lista}, archivos)


def leer_politica_de_rol(archivos: Mapping[str, bytes], *, limites=_ae78.LIMITES_POR_DEFECTO) -> PoliticaDeRol:
    manifiesto = _ae79._leer_manifiesto(archivos, NOMBRE_POLITICA_ROL, ESQUEMA_POLITICA_ROL, limites)
    _ae78._claves(manifiesto, {"esquema", "naturaleza", "rol", "archivos", "claves"}, "politica_de_rol")
    if manifiesto["naturaleza"] not in NATURALEZAS:
        _ae78._rechazar("naturaleza_no_admitida", str(manifiesto["naturaleza"])[:80])
    if manifiesto["rol"] not in ROLES:
        _ae78._rechazar("rol_desconocido", str(manifiesto["rol"])[:80])
    _ae78._exigir(isinstance(manifiesto["claves"], list), "claves")
    refs = []
    for c in manifiesto["claves"]:
        _ae78._claves(c, {"clave_publica", "etiqueta"}, "clave")
        _ae78._exigir(isinstance(c["etiqueta"], str), "etiqueta")
        refs.append(c["clave_publica"])
    _ae78._comprobar_archivos(archivos, NOMBRE_POLITICA_ROL, manifiesto, refs, limites)
    claves = tuple(archivos[r] for r in refs)
    if not all(len(c) == 32 for c in claves):
        _ae78._rechazar("estructura_invalida", "la clave publica Ed25519 debe tener 32 bytes")
    if len(claves) != len(set(claves)):
        _ae78._rechazar("clave_duplicada", "misma clave publica con dos etiquetas")
    return PoliticaDeRol(manifiesto["rol"], claves, hashlib.sha256(archivos[NOMBRE_POLITICA_ROL]).hexdigest())


@dataclass(frozen=True)
class Inventario:
    procedencia: str
    checkpoints: tuple
    cabezas: tuple
    monitores: tuple
    sha256: str


def componer_inventario(*, procedencia: str, checkpoints: Sequence = (), cabezas: Sequence = (),
                        monitores: Sequence = ()) -> dict:
    """`checkpoints`: `[publicador, registro, posicion, sha256]`;
    `cabezas`: hashes de constancias; `monitores`: huellas de clave."""
    cabecera = {"esquema": ESQUEMA_INVENTARIO, "naturaleza": "fixture_de_prueba", "procedencia": procedencia,
                "checkpoints": sorted([list(c) for c in checkpoints]), "cabezas": sorted(set(cabezas)),
                "monitores": sorted(set(monitores))}
    return _ae78._con_manifiesto(NOMBRE_INVENTARIO, cabecera, {})


def leer_inventario(archivos: Mapping[str, bytes], *, limites=_ae78.LIMITES_POR_DEFECTO) -> Inventario:
    manifiesto = _ae79._leer_manifiesto(archivos, NOMBRE_INVENTARIO, ESQUEMA_INVENTARIO, limites)
    _ae78._claves(manifiesto, {"esquema", "naturaleza", "procedencia", "archivos", "checkpoints", "cabezas",
                               "monitores"}, "inventario")
    if manifiesto["naturaleza"] not in NATURALEZAS:
        _ae78._rechazar("naturaleza_no_admitida", str(manifiesto["naturaleza"])[:80])
    _ae78._exigir(manifiesto["procedencia"] in PROCEDENCIAS_DEL_INVENTARIO, "procedencia")
    checkpoints, cabezas, monitores = manifiesto["checkpoints"], manifiesto["cabezas"], manifiesto["monitores"]
    forma = (isinstance(checkpoints, list)
             and all(isinstance(c, list) and len(c) == 4 and _ae79.es_huella(c[0]) and isinstance(c[1], str)
                     and _ae79._NOMBRE.fullmatch(c[1]) is not None and type(c[2]) is int and c[2] >= 1
                     and _ae79.es_huella(c[3]) for c in checkpoints)
             and isinstance(cabezas, list) and all(_ae79.es_huella(h) for h in cabezas)
             and isinstance(monitores, list) and all(_ae79.es_huella(h) for h in monitores))
    _ae78._exigir(forma, "inventario")
    _ae78._exigir(checkpoints == sorted(checkpoints) and len({tuple(c[:3]) for c in checkpoints}) == len(checkpoints)
                  and cabezas == sorted(set(cabezas)) and monitores == sorted(set(monitores)), "inventario")
    _ae78._comprobar_archivos(archivos, NOMBRE_INVENTARIO, manifiesto, [], limites)
    return Inventario(manifiesto["procedencia"], tuple(tuple(c) for c in checkpoints), tuple(cabezas),
                      tuple(monitores), hashlib.sha256(archivos[NOMBRE_INVENTARIO]).hexdigest())


# ---------------------------------------------------------------------------
# Verificacion
# ---------------------------------------------------------------------------

CONTRADICCIONES = ("bifurcacion_firmada_del_publicador", "vinculo_roto", "cabeza_retrocede", "serie_retirada",
                   "observacion_incompatible_con_el_checkpoint", "observaciones_incompatibles_del_mismo_monitor",
                   "contradiccion_en_constancias_ae80")
"""Bytes firmados presentados que se contradicen entre si."""
NO_COINCIDENCIAS = (
    "pieza_ilegible", "pieza_no_canonica", "pieza_mal_formada", "version_desconocida", "dominio_no_admitido",
    "naturaleza_no_admitida", "firma_no_coincide", "clave_no_admitida", "huella_de_clave_no_coincide",
    "clave_mal_formada", "algoritmo_no_admitido", "politica_de_constancias_no_coincide",
    "dominio_de_constancias_no_coincide", "cabeza_no_publicada", "cabeza_publicada_no_presentada",
    "checkpoint_no_coincide_con_referencia", "checkpoint_presentado_no_esperado", "monitor_no_esperado",
    "cabeza_no_esperada", "constancias_ae80_no_coinciden",
)
DISCREPANCIAS = ("discrepancia_entre_monitores", "observacion_de_otro_contenido")
"""Actores que no coinciden sin que los bytes presentados prueben cual se
contradice: no son contradicciones."""
INCOMPLETAS = ("predecesor_no_presentado", "checkpoint_observado_no_presentado", "inventario_no_aportado",
               "checkpoint_esperado_no_presentado", "cabeza_esperada_no_presentada",
               "monitor_esperado_sin_observacion", "sin_checkpoint_admitido", "sin_constancias_ae80")

CODIGOS_DE_SALIDA = MappingProxyType({"coincidente_con_lo_suministrado": 0, "contradiccion_comprobada": 1,
                                      "uso_incorrecto": 2, "lectura_rechazada": 3, "no_coincide": 4,
                                      "evidencia_incompleta": 5, "discrepancia_entre_actores": 6})
SIGNIFICADO_DE_LOS_CODIGOS = MappingProxyType({
    0: "lo presentado coincide con las referencias y el inventario suministrados; no acredita publicacion externa "
       "ni autoriza evaluacion",
    1: "bytes firmados presentados que se contradicen; no adjudica cual es cierto",
    2: "uso incorrecto del comando; no se verifico nada",
    3: "la lectura endurecida rechazo al menos una entrada o las politicas de rol son incompatibles",
    4: "una firma, una clave, una referencia, una cabeza o el inventario no coincide",
    5: "falta evidencia: referencias, predecesores, checkpoints, cabezas o monitores esperados",
    6: "actores que no coinciden sin contexto para probar una contradiccion",
})
"""Prioridad: 1, 3, 4, 6, 5 y 0. Ningun codigo significa autorizacion."""

DECISIONES_ABIERTAS_AE81 = MappingProxyType({
    "medio_de_publicacion": "registro o medio de publicacion externo, su operador y su politica de retencion (A2)",
    "monitores": "quienes actuan como monitores independientes y como se acredita su independencia (C3)",
    "inventario_autorizado": "quien firma y publica el inventario esperado de cabezas, checkpoints y monitores "
                             "(A2, C3)",
})

LIMITES = (
    "publicadores, monitores, politicas e inventario son de fixture; una firma valida solo prueba la firma de esos "
    "bytes frente a una clave admitida por la politica de su rol",
    "un archivo local, dos firmas o una huella copiada no acreditan publicacion externa, independencia de los "
    "monitores ni completitud",
    "posiciones y vinculos de hashes solo relacionan bytes presentados: no prueban anterioridad, cronologia ni "
    "que no existan otros checkpoints u observaciones",
    "no se usa mayoria, quorum ni cantidad de firmas como sustituto de autoridad del conjunto esperado",
    "el inventario y las referencias los suministra quien verifica; si se copiaron de lo presentado, asi se "
    "etiquetan y no acreditan nada externo",
    "AE-79 y AE-80 se recalculan siempre; ningun informe aportado se acepta como autoridad",
    "RFC 9162 conserva solo su alcance de certificados y precertificados; estas piezas no heredan sus garantias",
    "ejecutar la verificacion no autoriza evaluacion ni convierte R0 en final; AUTORIZA_EVALUACION es False",
)


def _plano(estado: str, motivos=()) -> dict:
    return {"estado": estado, "motivos": sorted(set(motivos))}


def _leer_entrada(contenido, lector):
    if isinstance(contenido, _ae78.ExpedienteIlegible):
        return None, contenido
    try:
        return lector(contenido), None
    except _ae78.ExpedienteIlegible as error:
        return None, error


def _firma(objeto, pieza, politica: PoliticaDeRol) -> dict:
    admitidas = _ae76.PoliticaDeClavesDePrueba(claves=tuple(
        _ae76.ClaveDePrueba(c, "canal", politica.rol) for c in politica.claves))
    planos = _ae76._firma(objeto, pieza, admitidas, "canal")
    motivos = [m for r in planos.values() if r.estado in ("rechazada", "pendiente") for m in r.motivos]
    if motivos:
        return _plano("rechazada", motivos)
    return _plano("superada" if all(r.estado == "superada" for r in planos.values()) else "no_evaluable")


def _filas(conjuntos, lector_conjunto, lector_pieza, politica, lectura):
    """Lee conjuntos y piezas; devuelve (filas, admitidas por id)."""
    filas, admitidas, vistos, resumen = [], {}, set(), []
    for contenido in conjuntos:
        objetos, error = _leer_entrada(contenido, lector_conjunto)
        if error is not None:
            lectura.append(error.motivo)
            resumen.append({"lectura": _plano("rechazada", (error.motivo,))})
            continue
        resumen.append({"lectura": _plano("superada"), "piezas": len(objetos)})
        for objeto in objetos:
            if (objeto.datos, objeto.firma, objeto.clave_publica) in vistos:
                continue
            vistos.add((objeto.datos, objeto.firma, objeto.clave_publica))
            fila = {"id": _ae76.hash_de_pieza(objeto.datos), "firmante": _ae76.huella_de_clave(objeto.clave_publica),
                    "sha256_firma": hashlib.sha256(objeto.firma).hexdigest()}
            try:
                pieza = lector_pieza(objeto.datos)
            except _ae76.ExpedienteInvalido as error:
                pieza = None
                fila["lectura"] = _plano("rechazada", (error.motivo,))
            else:
                fila["lectura"] = _plano("superada")
                fila.update(registro=pieza["registro"], posicion=pieza["posicion"])
            fila["firma"] = _firma(objeto, pieza, politica) if politica is not None else _plano("no_evaluable")
            fila["admitida"] = pieza is not None and fila["firma"]["estado"] == "superada"
            fila["motivos"] = sorted({*fila["lectura"]["motivos"], *fila["firma"]["motivos"]})
            if fila["admitida"]:
                admitidas.setdefault(fila["id"], pieza)
            filas.append(fila)
    return filas, admitidas, resumen


def verificar(*, expedientes: Sequence, politica_del_verificador, politica_de_auditoria, capturas: Sequence = (),
              politica_de_constancias, constancias: Sequence = (), politica_de_publicadores, politica_de_monitores,
              checkpoints: Sequence = (), observaciones: Sequence = (), inventario=None) -> dict:
    """Recalcula AE-79 y AE-80 y vincula constancias, checkpoints y
    observaciones con las politicas de rol y el inventario suministrados.
    Cada coleccion es una secuencia de `{ruta: bytes}` o
    `ExpedienteIlegible`; `inventario` puede faltar (None)."""
    if max(len(checkpoints), len(observaciones)) > MAXIMO_DE_CONJUNTOS:
        raise ValueError("numero_de_conjuntos_fuera_de_limites")
    ae80 = _ae80.verificar(expedientes=expedientes, politica_del_verificador=politica_del_verificador,
                           politica_de_auditoria=politica_de_auditoria, capturas=capturas,
                           politica_de_constancias=politica_de_constancias, constancias=constancias)
    lectura, contradicciones, no_coincide, discrepancias, incompletas = [], [], [], [], []
    resultado80 = ae80["resultado"]
    if resultado80 == "contradiccion_comprobada":
        contradicciones.append("contradiccion_en_constancias_ae80")
    elif resultado80 == "lectura_rechazada":
        lectura.append("lectura_rechazada_en_ae80")
    elif resultado80 == "constancia_no_coincide":
        no_coincide.append("constancias_ae80_no_coinciden")
    elif resultado80 == "sin_constancia_admitida":
        incompletas.append("sin_constancias_ae80")
    cabezas80 = cabezas_de_constancias(ae80)
    sha_politica80 = (ae80.get("politica_de_constancias") or {}).get("sha256")

    politicas = {}
    for rol, contenido in (("publicador", politica_de_publicadores), ("monitor", politica_de_monitores)):
        politica, error = _leer_entrada(contenido, leer_politica_de_rol)
        if error is None and politica.rol != rol:
            error = _ae78.ExpedienteIlegible("rol_no_coincide")
        if error is not None:
            lectura.append(error.motivo)
            politica = None
        politicas[rol] = politica
    pub, mon = politicas["publicador"], politicas["monitor"]
    firmantes80 = set((ae80.get("politica_de_constancias") or {}).get("firmantes", []))
    reutilizadas = (pub is not None and mon is not None and set(pub.claves) & set(mon.claves)) or any(
        _ae76.huella_de_clave(c) in firmantes80 for p in (pub, mon) if p is not None for c in p.claves)
    if reutilizadas:
        lectura.append("clave_reutilizada_entre_roles")
        pub = mon = None

    filas_c, admitidos_c, conjuntos_c = _filas(checkpoints, leer_checkpoints, leer_checkpoint, pub, lectura)
    filas_o, admitidas_o, conjuntos_o = _filas(observaciones, leer_observaciones, leer_observacion, mon, lectura)
    for fila in (*filas_c, *filas_o):
        no_coincide.extend(fila["motivos"])

    # Checkpoints por (publicador, registro): bifurcaciones, vinculos,
    # predecesores, progresion y cabeza.
    registros: dict = {}
    for id_, p in admitidos_c.items():
        registros.setdefault((p["huella_de_clave"], p["registro"]), {}).setdefault(p["posicion"], []).append(id_)
    resumen_registros, cabezas_c, hallazgos = [], set(), []
    for (publicador, registro), posiciones in sorted(registros.items()):
        pendientes, motivos = [], []
        for posicion, ids in sorted(posiciones.items()):
            if len(ids) > 1:
                motivos.append("bifurcacion_firmada_del_publicador")
                hallazgos.append({"motivo": "bifurcacion_firmada_del_publicador", "publicador": publicador,
                                  "registro": registro, "posicion": posicion, "checkpoints": sorted(ids)})
            if posicion == 1:
                continue
            previas = posiciones.get(posicion - 1, [])
            for id_ in sorted(ids):
                actual = admitidos_c[id_]
                if not previas:
                    pendientes.append({"checkpoint": id_, "motivo": "predecesor_no_presentado"})
                    continue
                if actual["anterior"] not in previas:
                    motivos.append("vinculo_roto")
                    hallazgos.append({"motivo": "vinculo_roto", "publicador": publicador, "registro": registro,
                                      "posicion": posicion, "checkpoints": sorted([id_, *previas])})
                    continue
                previo = {(c[0], c[1]): c[2] for c in admitidos_c[actual["anterior"]]["cabezas"]}
                ahora = {(c[0], c[1]): c[2] for c in actual["cabezas"]}
                for clave, secuencia in sorted(previo.items()):
                    if clave not in ahora:
                        motivos.append("serie_retirada")
                    elif ahora[clave] < secuencia:
                        motivos.append("cabeza_retrocede")
        maximo = max(posiciones)
        cabezas_c.update(posiciones[maximo])
        contradicciones.extend(motivos)
        incompletas.extend(p["motivo"] for p in pendientes)
        enlazada = (sorted(posiciones) == list(range(1, maximo + 1)) and not pendientes and not motivos)
        resumen_registros.append({
            "publicador": publicador, "registro": registro, "posiciones": sorted(posiciones),
            "cabezas": sorted(posiciones[maximo]), "pendientes": pendientes, "motivos": sorted(set(motivos)),
            "progresion": ("progresion_demostrable_entre_lo_presentado" if enlazada and maximo > 1
                           else "posicion_unica" if enlazada else "contradiccion" if motivos else "pendiente"),
            "nota": "posicion y vinculo no prueban anterioridad ni que no existan otros checkpoints"})
    if not admitidos_c:
        incompletas.append("sin_checkpoint_admitido")

    # Cada cabeza de registro frente a la politica y las cabezas AE-80.
    actuales = {c[3] for c in cabezas80}
    for fila in filas_c:
        if fila["admitida"]:
            pieza = admitidos_c[fila["id"]]
            fila["rol"] = "cabeza" if fila["id"] in cabezas_c else "predecesor"
            cotejo = []
            if pieza["sha256_politica_de_constancias"] != sha_politica80:
                cotejo.append("politica_de_constancias_no_coincide")
            if pieza["dominio_de_constancias"] != _ae80.DOMINIO_DE_PRUEBA:
                cotejo.append("dominio_de_constancias_no_coincide")
            if fila["rol"] == "cabeza":
                publicadas = {c[3] for c in pieza["cabezas"]}
                cotejo += ["cabeza_no_publicada"] * bool(actuales - publicadas)
                cotejo += ["cabeza_publicada_no_presentada"] * bool(publicadas - actuales)
                fila["cabezas_no_publicadas"] = sorted(actuales - publicadas)
                fila["cabezas_publicadas_no_presentadas"] = sorted(publicadas - actuales)
            fila["cotejo"] = sorted(set(cotejo))
            fila["estado"] = ("no_coincide" if fila["cotejo"] else "coincide") if fila["rol"] == "cabeza" else (
                "predecesor_con_politica_distinta" if fila["cotejo"] else "predecesor")
            no_coincide.extend(fila["cotejo"])
        else:
            fila["estado"] = "no_admitido"

    # Observaciones: frente al checkpoint que nombran y entre monitores.
    por_posicion: dict = {}
    for fila in filas_o:
        if not fila["admitida"]:
            fila["estado"] = "no_admitida"
            continue
        o = admitidas_o[fila["id"]]
        contexto = (o["publicador"], o["registro"], o["posicion"])
        visto = admitidos_c.get(o["sha256_checkpoint"])
        if visto is not None:
            if (visto["huella_de_clave"], visto["registro"], visto["posicion"]) != contexto:
                fila["estado"] = "incompatible_con_el_checkpoint"
                contradicciones.append("observacion_incompatible_con_el_checkpoint")
                hallazgos.append({"motivo": "observacion_incompatible_con_el_checkpoint", "observacion": fila["id"],
                                  "checkpoint": o["sha256_checkpoint"]})
                continue
            fila["estado"] = "coincide_con_el_checkpoint"
        else:
            fila["estado"] = "checkpoint_observado_no_presentado"
            incompletas.append("checkpoint_observado_no_presentado")
        por_posicion.setdefault(contexto, {}).setdefault(o["sha256_checkpoint"], set()).add(o["huella_de_clave"])
    for (publicador, registro, posicion), por_hash in sorted(por_posicion.items()):
        presentados = set(registros.get((publicador, registro), {}).get(posicion, []))
        if len(por_hash) > 1:
            monitores = [m for ms in por_hash.values() for m in ms]
            if len(monitores) != len(set(monitores)):
                contradicciones.append("observaciones_incompatibles_del_mismo_monitor")
                motivo = "observaciones_incompatibles_del_mismo_monitor"
            elif set(por_hash) <= presentados:
                motivo = None
            else:
                discrepancias.append("discrepancia_entre_monitores")
                motivo = "discrepancia_entre_monitores"
            if motivo is not None:
                hallazgos.append({"motivo": motivo, "publicador": publicador, "registro": registro,
                                  "posicion": posicion, "checkpoints": sorted(por_hash),
                                  "nota": "no se adjudica cual es cierto"})
        for h in sorted(set(por_hash) - presentados):
            if presentados:
                discrepancias.append("observacion_de_otro_contenido")
                hallazgos.append({"motivo": "observacion_de_otro_contenido", "publicador": publicador,
                                  "registro": registro, "posicion": posicion, "observado": h,
                                  "presentados": sorted(presentados)})

    # Referencias e inventario suministrados por quien verifica.
    inv, error = (None, None) if inventario is None else _leer_entrada(inventario, leer_inventario)
    if error is not None:
        lectura.append(error.motivo)
    referencias, cobertura = _cotejo_con_inventario(inv, admitidos_c, cabezas_c, cabezas80, admitidas_o,
                                                    inventario is None)
    no_coincide.extend(referencias["motivos_no_coinciden"])
    no_coincide.extend(cobertura["motivos_no_coinciden"])
    incompletas.extend(referencias["motivos_faltan"])
    incompletas.extend(cobertura["motivos_faltan"])

    contradicciones = sorted(set(contradicciones))
    no_coincide_final = sorted(set(no_coincide) & set(NO_COINCIDENCIAS))
    if contradicciones:
        resultado = "contradiccion_comprobada"
    elif lectura:
        resultado = "lectura_rechazada"
    elif no_coincide_final:
        resultado = "no_coincide"
    elif discrepancias:
        resultado = "discrepancia_entre_actores"
    elif incompletas:
        resultado = "evidencia_incompleta"
    else:
        resultado = "coincidente_con_lo_suministrado"
    integridad = [m for f in (*filas_c, *filas_o) for m in f["motivos"]]
    planos = {
        "integridad_de_bytes_y_firmas": _plano("rechazada" if integridad or lectura else "superada",
                                               [*integridad, *lectura]),
        "concordancia_con_referencias": referencias["plano"],
        "cobertura_del_inventario": cobertura["plano"],
        "publicacion_externa": _plano("no_acreditada", (
            "archivo_local_no_es_publicacion", "sin_medio_de_publicacion_externo",
            *(["referencias_copiadas_de_lo_presentado"] if inv is not None
              and inv.procedencia == "copiada_de_lo_presentado" else []))),
        "autoridad_de_claves_y_del_conjunto_esperado": _plano("pendiente", (
            "claves_de_fixture", "decision_a1_sin_tomar", "decision_a3_sin_tomar", "decision_c3_sin_tomar",
            "cantidad_de_firmas_no_es_autoridad")),
        "cronologia": _plano("pendiente", ("posicion_no_es_tiempo", "sin_sello_temporal_de_publicacion")),
        "completitud_global": _plano("pendiente", ("sin_fuente_autorizada", "sin_monitores_independientes_acreditados")),
        "autorizacion_operativa": {"estado": "denegada", "AUTORIZA_EVALUACION": _expediente.AUTORIZA_EVALUACION,
                                   "r0_final": "no_se_promociona"},
    }
    return {
        "esquema": ESQUEMA_INFORME,
        "lectura": {"estado": "rechazada_en_parte" if lectura else "superada", "motivos": sorted(set(lectura))},
        "ae80": {"resultado": resultado80, "cabezas": cabezas80, "sha256_politica_de_constancias": sha_politica80,
                 "sha256_informe_ae79": (ae80.get("estado_recalculado") or {}).get("sha256_informe_ae79"),
                 "resultado_ae79": (ae80.get("informe_ae79") or {}).get("resultado")},
        "politicas_de_rol": {r: ({"sha256": p.sha256, "claves": sorted(_ae76.huella_de_clave(c) for c in p.claves)}
                                 if p is not None else None) for r, p in (("publicador", pub), ("monitor", mon))},
        "conjuntos": {"checkpoints": sorted(conjuntos_c, key=_clave_conjunto),
                      "observaciones": sorted(conjuntos_o, key=_clave_conjunto)},
        "checkpoints": sorted(filas_c, key=_clave_fila),
        "observaciones": sorted(filas_o, key=_clave_fila),
        "registros": resumen_registros,
        "hallazgos": sorted(hallazgos, key=lambda h: (h["motivo"], str(h.get("publicador", "")),
                                                      str(h.get("registro", "")), h.get("posicion", 0),
                                                      str(h.get("checkpoints", h.get("observacion", ""))))),
        "planos": planos,
        "motivos": {"contradicciones": contradicciones, "no_coincide": no_coincide_final,
                    "discrepancias": sorted(set(discrepancias)), "incompletas": sorted(set(incompletas))},
        "pendientes": {"decisiones_sin_tomar": list(_ae79.DECISIONES_ABIERTAS),
                       "decisiones_abiertas_ae81": dict(DECISIONES_ABIERTAS_AE81)},
        "resultado": resultado,
        "limites": list(LIMITES),
    }


def _clave_conjunto(c: dict):
    return (c["lectura"]["estado"], c["lectura"]["motivos"], c.get("piezas", 0))


def _clave_fila(f: dict):
    return (f["firmante"], f.get("registro", ""), f.get("posicion", 0), f["id"], f["sha256_firma"])


def _cotejo_con_inventario(inv, admitidos_c, cabezas_c, cabezas80, admitidas_o, ausente: bool):
    """Concordancia de referencias y cobertura del inventario."""
    if inv is None:
        motivo = "inventario_no_aportado" if ausente else "inventario_ilegible"
        nulo = {"plano": _plano("no_evaluable", (motivo,)), "motivos_no_coinciden": [],
                "motivos_faltan": ["inventario_no_aportado"] if ausente else []}
        return dict(nulo), dict(nulo)
    presentes = {(p["huella_de_clave"], p["registro"], p["posicion"]): set() for p in admitidos_c.values()}
    for id_, p in admitidos_c.items():
        presentes[(p["huella_de_clave"], p["registro"], p["posicion"])].add(id_)
    coinciden, no_coinciden, faltan = [], [], []
    for publicador, registro, posicion, sha in inv.checkpoints:
        ids = presentes.get((publicador, registro, posicion), set())
        if sha in ids:
            coinciden.append(sha)
        elif ids:
            no_coinciden.append({"esperado": sha, "presentados": sorted(ids), "posicion": posicion,
                                 "registro": registro})
        else:
            faltan.append(sha)
    esperados = {(c[0], c[1], c[2]) for c in inv.checkpoints}
    sobran = sorted(i for c, ids in presentes.items() if c not in esperados for i in ids if i in cabezas_c)
    referencias = {
        "plano": _plano("no_coincide" if no_coinciden or sobran else "incompleta" if faltan else "coincide",
                        [*(["checkpoint_no_coincide_con_referencia"] if no_coinciden else []),
                         *(["checkpoint_presentado_no_esperado"] if sobran else []),
                         *(["checkpoint_esperado_no_presentado"] if faltan else [])]),
        "motivos_no_coinciden": [*(["checkpoint_no_coincide_con_referencia"] if no_coinciden else []),
                                 *(["checkpoint_presentado_no_esperado"] if sobran else [])],
        "motivos_faltan": ["checkpoint_esperado_no_presentado"] if faltan else [],
    }
    referencias["plano"].update(coinciden=sorted(coinciden), no_coinciden=no_coinciden, faltan=sorted(faltan),
                                sobran=sobran, procedencia=inv.procedencia)
    actuales = {c[3] for c in cabezas80}
    vieron = {o["huella_de_clave"] for o in admitidas_o.values() if o["sha256_checkpoint"] in cabezas_c}
    cab_faltan, cab_sobran = sorted(set(inv.cabezas) - actuales), sorted(actuales - set(inv.cabezas))
    mon_faltan, mon_sobran = sorted(set(inv.monitores) - vieron), sorted(vieron - set(inv.monitores))
    motivos_nc = [*(["cabeza_no_esperada"] if cab_sobran else []), *(["monitor_no_esperado"] if mon_sobran else [])]
    motivos_f = [*(["cabeza_esperada_no_presentada"] if cab_faltan else []),
                 *(["monitor_esperado_sin_observacion"] if mon_faltan else [])]
    cobertura = {"plano": _plano("no_coincide" if motivos_nc else "incompleta" if motivos_f else "completa_respecto_"
                                 "del_inventario", [*motivos_nc, *motivos_f]),
                 "motivos_no_coinciden": motivos_nc, "motivos_faltan": motivos_f}
    cobertura["plano"].update(cabezas={"faltan": cab_faltan, "sobran": cab_sobran},
                              monitores={"faltan": mon_faltan, "sobran": mon_sobran,
                                         "vieron_la_cabeza": sorted(vieron)},
                              nota="completa respecto del inventario suministrado no es completitud global")
    return referencias, cobertura


def informe_de_lectura_rechazada(objeto: str, motivo: str) -> dict:
    return {"esquema": ESQUEMA_INFORME, "lectura": {"estado": "rechazada", "objeto": objeto, "motivos": [motivo]},
            "planos": {"autorizacion_operativa": {"estado": "denegada", "AUTORIZA_EVALUACION": False,
                                                  "r0_final": "no_se_promociona"}},
            "resultado": "lectura_rechazada", "limites": list(LIMITES)}


def codigo_de_salida(informe: dict) -> int:
    return CODIGOS_DE_SALIDA[informe["resultado"]]


def informe_json(informe: dict) -> bytes:
    return _ae78.informe_json(informe)


def resumen_legible(informe: dict) -> str:
    lineas = [f"Publicacion y monitoreo de constancias ({ESQUEMA_INFORME})"]
    if informe["lectura"]["estado"] != "superada":
        lineas.append(f"Lectura: {informe['lectura']['estado']} {' '.join(informe['lectura']['motivos'])}".rstrip())
    if "ae80" in informe:
        lineas.append(f"== AE-80 recalculado: {informe['ae80']['resultado']}; AE-79: {informe['ae80']['resultado_ae79']}")
    for f in informe.get("checkpoints", []):
        lineas.append(f"  checkpoint {f['id'][:16]} publicador {f['firmante'][:16]} posicion {f.get('posicion', '?')} "
                      f"[{f.get('rol', '-')}]: {f['estado']}" + (f" ({', '.join(f['motivos'] or f.get('cotejo', []))})"
                                                                  if f['motivos'] or f.get('cotejo') else ""))
    for f in informe.get("observaciones", []):
        lineas.append(f"  observacion {f['id'][:16]} monitor {f['firmante'][:16]}: {f['estado']}"
                      + (f" ({', '.join(f['motivos'])})" if f["motivos"] else ""))
    for r in informe.get("registros", []):
        lineas.append(f"  registro {r['registro']} de {r['publicador'][:16]}: {r['progresion']}")
    for h in informe.get("hallazgos", []):
        lineas.append(f"  hallazgo: {h['motivo']}")
    for nombre, plano in informe.get("planos", {}).items():
        lineas.append(f"== {nombre}: {plano['estado']}" + (f" ({', '.join(plano['motivos'])})"
                                                          if plano.get("motivos") else ""))
    lineas.append("  AUTORIZA_EVALUACION = False")
    codigo = codigo_de_salida(informe)
    lineas.append(f"Resultado: {informe['resultado']} (codigo {codigo}: {SIGNIFICADO_DE_LOS_CODIGOS[codigo]})")
    return "\n".join(lineas) + "\n"
