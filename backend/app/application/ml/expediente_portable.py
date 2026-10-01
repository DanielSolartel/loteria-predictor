"""
Expediente portable de la recepcion por objetivo y verificacion offline
-Etapa AE-78, validada localmente como trabajo preparatorio.

Formato `expediente-portable-recepcion/1`: un directorio con
`manifiesto.json` (JSON canonico de AE-52) y archivos de evidencia
referenciados por ruta relativa, tamano y SHA-256. Contiene las piezas que
necesita la evaluacion compuesta de AE-77:

- registro, declaracion R0 y sobre firmado (AE-74 y AE-76);
- sellos del compromiso R0 por objetivo (AE-75);
- acuses, sus sellos, cierre, conjunto esperado y vistas del observador
  (AE-76 y AE-77).

La confianza y las expectativas no viajan en el expediente: anclas, OID de
politica, margen, claves admitidas por rol, canal y corte esperados llegan en
una politica aparte, `politica-verificador-de-prueba/1`, que solo admite la
naturaleza `fixture_de_prueba`; su ubicacion separada no acredita por si
misma custodia ni autoridad independiente. El manifiesto no esta firmado:
solo prueba que los archivos coinciden con sus hashes declarados.

El compositor no incluye claves privadas de fixture, y compositor y lector
rechazan las marcas textuales `PRIVATE KEY` y `OPENSSH PRIVATE`. Esa
deteccion es textual: no reconoce cualquier clave privada codificada como
bytes crudos.

Este modulo es puro: recibe los bytes ya leidos (`{ruta: bytes}`), comprueba
el manifiesto con reglas estrictas y reconstruye las piezas. Despues llama a
`recepcion_por_objetivo.evaluar_recepcion_por_objetivo`, que usa los
verificadores de AE-74 a AE-77 sin copiarlos, y devuelve un informe JSON
determinista. La lectura del directorio (enlaces, archivos no regulares,
limites) vive en `scripts/verificar_expediente_recepcion.py`.

Ejecutar la auditoria nunca autoriza evaluacion: `r0_final` sigue rechazada
cuando se evalua; si la lectura falla no se evalua ningun plano, tampoco
`r0_final`, y el informe registra el fallo y deniega la autorizacion.
`AUTORIZA_EVALUACION = False`, A1-A3 y C1-C3 siguen sin decidir, y la
autoridad del conjunto esperado y la completitud global quedan pendientes.
Sin red, reloj local, deserializacion ejecutable ni secretos.
"""
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from app.application.ml import contrato_vinculo_r0 as _ae74
from app.application.ml import expediente_r0_recepcion as _ae76
from app.application.ml import propuesta_inferencia_prospectiva as _expediente
from app.application.ml import recepcion_por_objetivo as _ae77
from app.application.ml import registro_prospectivo as _rp
from app.application.ml import sello_temporal_r0 as _ae75

ESQUEMA_EXPEDIENTE = "expediente-portable-recepcion/1"
ESQUEMA_POLITICA = "politica-verificador-de-prueba/1"
ESQUEMA_INFORME = "informe-expediente-recepcion/1"
NOMBRE_MANIFIESTO = "manifiesto.json"
NOMBRE_POLITICA = "politica.json"
NATURALEZAS_DE_POLITICA = ("fixture_de_prueba",)
_RUTA = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}(/[a-z0-9][a-z0-9_.-]{0,63}){0,5}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_MARCAS_PRIVADAS = (b"PRIVATE KEY", b"OPENSSH PRIVATE")


class ExpedienteIlegible(ValueError):
    """La lectura endurecida rechazo el expediente o la politica."""

    def __init__(self, motivo: str, detalle: str = ""):
        super().__init__(motivo, detalle)

    @property
    def motivo(self) -> str:
        return self.args[0]

    def __str__(self) -> str:
        return f"{self.args[0]}: {self.args[1]}" if self.args[1] else self.args[0]


@dataclass(frozen=True)
class Limites:
    bytes_por_archivo: int = 1 << 20
    bytes_totales: int = 16 << 20
    archivos: int = 512
    bytes_manifiesto: int = 1 << 20


LIMITES_POR_DEFECTO = Limites()


def _rechazar(motivo: str, detalle: str = ""):
    raise ExpedienteIlegible(motivo, detalle)


# ---------------------------------------------------------------------------
# JSON estricto y manifiesto
# ---------------------------------------------------------------------------

def _sin_duplicados(pares):
    claves = [k for k, _ in pares]
    if len(claves) != len(set(claves)):
        raise ValueError("clave duplicada")
    return dict(pares)


def _constante_no_admitida(valor):
    raise ValueError(f"constante no admitida: {valor}")


def _leer_json_canonico(datos: bytes) -> dict:
    """JSON sin claves duplicadas ni constantes no estandar, objeto en la
    raiz y exactamente en la forma canonica de AE-52."""
    try:
        valor = json.loads(datos.decode("utf-8"), object_pairs_hook=_sin_duplicados,
                           parse_constant=_constante_no_admitida)
    except (UnicodeDecodeError, ValueError) as error:
        _rechazar("manifiesto_ilegible", str(error))
    if not isinstance(valor, dict):
        _rechazar("manifiesto_ilegible", "la raiz no es un objeto")
    try:
        canonicos = _rp.serializar_entrada(valor)
    except _rp.EntradaRegistroInvalidaError as error:
        # 1e999 se lee como infinito sin pasar por `parse_constant`
        # (correccion incluida en AE-80).
        raise ExpedienteIlegible("manifiesto_ilegible", "numero fuera de rango") from error
    if canonicos != datos:
        _rechazar("manifiesto_no_canonico")
    return valor


def _exigir(condicion: bool, detalle: str):
    if not condicion:
        _rechazar("estructura_invalida", detalle)


def _claves(objeto, claves: set, contexto: str):
    _exigir(isinstance(objeto, dict) and set(objeto) == claves, contexto)


def _es_ruta(valor) -> bool:
    return isinstance(valor, str) and len(valor) <= 200 and _RUTA.fullmatch(valor) is not None


def _comprobar_archivos(archivos: Mapping[str, bytes], nombre: str, manifiesto: dict, referencias: list,
                        limites: Limites):
    """Rutas, duplicados, archivos faltantes o no declarados, tamanos, hashes,
    referencias y material privado (tambien en el propio manifiesto, desde
    AE-79). El orden de las comprobaciones es fijo."""
    lista = manifiesto["archivos"]
    _exigir(isinstance(lista, list), "archivos")
    for entrada in lista:
        _claves(entrada, {"ruta", "bytes", "sha256"}, "archivo")
        _exigir(type(entrada["bytes"]) is int and entrada["bytes"] >= 0, "bytes")
        _exigir(isinstance(entrada["sha256"], str) and _HEX64.fullmatch(entrada["sha256"]) is not None, "sha256")
    todas = [e["ruta"] for e in lista] + referencias
    for ruta in todas:
        if not _es_ruta(ruta) or ruta == nombre:
            _rechazar("ruta_invalida", repr(ruta)[:80])
    declaradas = [e["ruta"] for e in lista]
    if len(declaradas) != len(set(declaradas)):
        _rechazar("referencia_duplicada", "archivo declarado dos veces")
    if declaradas != sorted(declaradas):
        _rechazar("estructura_invalida", "archivos no ordenados")
    presentes = set(archivos) - {nombre}
    faltan = sorted(set(declaradas) - presentes)
    if faltan:
        _rechazar("archivo_faltante", faltan[0])
    sobran = sorted(presentes - set(declaradas))
    if sobran:
        _rechazar("archivo_no_declarado", sobran[0][:80])
    for entrada in lista:
        datos = archivos[entrada["ruta"]]
        if len(datos) != entrada["bytes"]:
            _rechazar("tamano_incorrecto", entrada["ruta"])
        if hashlib.sha256(datos).hexdigest() != entrada["sha256"]:
            _rechazar("sha256_incorrecto", entrada["ruta"])
    for ruta in [nombre, *declaradas]:
        if any(marca in archivos[ruta] for marca in _MARCAS_PRIVADAS):
            _rechazar("material_privado_detectado", ruta)
    no_declaradas = sorted(set(referencias) - set(declaradas))
    if no_declaradas:
        _rechazar("referencia_no_declarada", no_declaradas[0])
    if len(referencias) != len(set(referencias)):
        _rechazar("referencia_duplicada", "archivo referenciado dos veces")
    sin_referencia = sorted(set(declaradas) - set(referencias))
    if sin_referencia:
        _rechazar("archivo_sin_referencia", sin_referencia[0])


def _limites(archivos: Mapping[str, bytes], nombre: str, limites: Limites):
    if nombre not in archivos:
        _rechazar("manifiesto_ausente")
    if len(archivos[nombre]) > limites.bytes_manifiesto:
        _rechazar("manifiesto_demasiado_grande")
    if len(archivos) - 1 > limites.archivos:
        _rechazar("demasiados_archivos")
    if any(len(v) > limites.bytes_por_archivo for k, v in archivos.items() if k != nombre):
        _rechazar("archivo_demasiado_grande")
    if sum(len(v) for v in archivos.values()) > limites.bytes_totales:
        _rechazar("expediente_demasiado_grande")


# ---------------------------------------------------------------------------
# Composicion (solo material publico)
# ---------------------------------------------------------------------------

def _objeto(prefijo: str, objeto, archivos: dict) -> dict:
    rutas = {"datos": f"{prefijo}/datos.json", "firma": f"{prefijo}/firma.bin",
             "clave_publica": f"{prefijo}/clave_publica.bin"}
    archivos[rutas["datos"]] = bytes(objeto.datos)
    archivos[rutas["firma"]] = bytes(objeto.firma)
    archivos[rutas["clave_publica"]] = bytes(objeto.clave_publica)
    return rutas


def _con_manifiesto(nombre: str, cabecera: dict, archivos: dict) -> dict:
    lista = [{"ruta": r, "bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()} for r, d in sorted(archivos.items())]
    for ruta, datos in archivos.items():
        if not _es_ruta(ruta) or any(marca in datos for marca in _MARCAS_PRIVADAS):
            raise ValueError(f"no se exporta {ruta!r}")
    manifiesto = _rp.serializar_entrada({**cabecera, "archivos": lista})
    if any(marca in manifiesto for marca in _MARCAS_PRIVADAS):
        raise ValueError(f"no se exporta {nombre!r}")
    return {**archivos, nombre: manifiesto}


def componer_expediente(*, entradas: Sequence[bytes], bytes_declaracion: bytes, sobre, sellos_r0: Mapping,
                        acuses: Sequence, sellos_de_acuses: Sequence, cierre, conjunto_esperado,
                        vistas: Sequence[Sequence]) -> dict:
    """{ruta: bytes} del expediente, con su manifiesto. Solo guarda bytes de
    piezas, firmas, claves publicas y tokens: nunca claves privadas."""
    archivos: dict = {}
    registro = []
    for i, entrada in enumerate(entradas, start=1):
        ruta = f"registro/{i:06d}.json"
        archivos[ruta] = bytes(entrada)
        registro.append(ruta)
    archivos["declaracion/declaracion_r0.json"] = bytes(bytes_declaracion)
    sellos = []
    for (juego, objetivo), evidencia in sorted(sellos_r0.items()):
        base = f"sellos_r0/{juego.lower()}-{objetivo}"
        archivos[f"{base}/respuesta.tsr"] = bytes(evidencia.respuesta_der)
        archivos[f"{base}/compromiso.json"] = bytes(evidencia.bytes_compromiso)
        sellos.append({"codigo_juego": juego, "sorteo_objetivo": objetivo, "respuesta": f"{base}/respuesta.tsr",
                       "compromiso": f"{base}/compromiso.json"})
    lista_acuses = [_objeto(f"acuses/{i:03d}", a, archivos) for i, a in enumerate(acuses, start=1)]
    indices = {bytes(a.datos): i for i, a in enumerate(acuses)}
    sellos_acuses = []
    for i, evidencia in enumerate(sellos_de_acuses, start=1):
        base = f"sellos_de_acuses/{i:03d}"
        archivos[f"{base}/respuesta.tsr"] = bytes(evidencia.respuesta_der)
        archivos[f"{base}/compromiso.json"] = bytes(evidencia.bytes_compromiso)
        sellos_acuses.append({"acuse": indices[bytes(evidencia.acuse.datos)], "respuesta": f"{base}/respuesta.tsr",
                              "compromiso": f"{base}/compromiso.json"})
    piezas = {
        "registro": registro, "declaracion_r0": "declaracion/declaracion_r0.json",
        "sobre": _objeto("sobre", sobre, archivos) if sobre is not None else None, "sellos_r0": sellos,
        "acuses": lista_acuses, "sellos_de_acuses": sellos_acuses,
        "cierre": _objeto("cierre", cierre, archivos) if cierre is not None else None,
        "conjunto_esperado": _objeto("conjunto_esperado", conjunto_esperado, archivos),
        "vistas": [[_objeto(f"vistas/{v:02d}/{j:03d}", o, archivos) for j, o in enumerate(vista, start=1)]
                   for v, vista in enumerate(vistas, start=1)],
    }
    return _con_manifiesto(NOMBRE_MANIFIESTO, {"esquema": ESQUEMA_EXPEDIENTE, "piezas": piezas}, archivos)


def componer_politica(*, anclas: Sequence, politicas_admitidas: Sequence[str], margen: str, claves: Sequence,
                      observadores: Sequence, canal: str, corte_esperado: int) -> dict:
    """{ruta: bytes} de una politica de prueba del verificador: certificados
    de ancla y claves publicas admitidas por rol."""
    archivos: dict = {}
    lista_anclas, lista_claves, lista_observadores = [], [], []
    for i, (der, etiqueta) in enumerate(anclas, start=1):
        archivos[f"anclas/{i:02d}.der"] = bytes(der)
        lista_anclas.append({"certificado": f"anclas/{i:02d}.der", "etiqueta": etiqueta})
    for i, (clave, rol, etiqueta) in enumerate(claves, start=1):
        archivos[f"claves/{i:02d}.bin"] = bytes(clave)
        lista_claves.append({"clave_publica": f"claves/{i:02d}.bin", "rol": rol, "etiqueta": etiqueta})
    for i, (clave, etiqueta) in enumerate(observadores, start=1):
        archivos[f"observadores/{i:02d}.bin"] = bytes(clave)
        lista_observadores.append({"clave_publica": f"observadores/{i:02d}.bin", "etiqueta": etiqueta})
    cabecera = {"esquema": ESQUEMA_POLITICA, "naturaleza": "fixture_de_prueba",
                "sello": {"anclas": lista_anclas, "politicas_admitidas": list(politicas_admitidas), "margen": margen},
                "claves": lista_claves, "observadores": lista_observadores,
                "auditoria": {"canal": canal, "corte_esperado": corte_esperado}}
    return _con_manifiesto(NOMBRE_POLITICA, cabecera, archivos)


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExpedienteLeido:
    entradas: tuple
    bytes_declaracion: bytes
    sobre: object
    sellos_r0: dict
    acuses: tuple
    sellos_de_acuses: tuple
    cierre: object
    conjunto_esperado: object
    vistas: tuple
    sha256_manifiesto: str
    numero_de_archivos: int


@dataclass(frozen=True)
class PoliticaLeida:
    sello: object
    claves: object
    observadores: object
    canal: str
    corte_esperado: int
    sha256: str


def _rutas_de_objeto(objeto, contexto: str) -> list:
    _claves(objeto, {"datos", "firma", "clave_publica"}, contexto)
    return [objeto["datos"], objeto["firma"], objeto["clave_publica"]]


def _referencias_del_expediente(piezas: dict) -> list:
    _claves(piezas, {"registro", "declaracion_r0", "sobre", "sellos_r0", "acuses", "sellos_de_acuses", "cierre",
                     "conjunto_esperado", "vistas"}, "piezas")
    refs = []
    _exigir(isinstance(piezas["registro"], list) and piezas["registro"], "registro")
    refs += piezas["registro"]
    refs.append(piezas["declaracion_r0"])
    for clave in ("sobre", "cierre"):
        if piezas[clave] is not None:
            refs += _rutas_de_objeto(piezas[clave], clave)
    refs += _rutas_de_objeto(piezas["conjunto_esperado"], "conjunto_esperado")
    _exigir(isinstance(piezas["sellos_r0"], list), "sellos_r0")
    for sello in piezas["sellos_r0"]:
        _claves(sello, {"codigo_juego", "sorteo_objetivo", "respuesta", "compromiso"}, "sello_r0")
        _exigir(isinstance(sello["codigo_juego"], str) and type(sello["sorteo_objetivo"]) is int, "sello_r0")
        refs += [sello["respuesta"], sello["compromiso"]]
    _exigir(isinstance(piezas["acuses"], list), "acuses")
    for acuse in piezas["acuses"]:
        refs += _rutas_de_objeto(acuse, "acuse")
    _exigir(isinstance(piezas["sellos_de_acuses"], list), "sellos_de_acuses")
    usados = [s.get("acuse") if isinstance(s, dict) else None for s in piezas["sellos_de_acuses"]]
    for sello in piezas["sellos_de_acuses"]:
        _claves(sello, {"acuse", "respuesta", "compromiso"}, "sello_de_acuse")
        _exigir(type(sello["acuse"]) is int and 0 <= sello["acuse"] < len(piezas["acuses"]), "indice de acuse")
        refs += [sello["respuesta"], sello["compromiso"]]
    _exigir(len(usados) == len(set(usados)), "dos sellos para un mismo acuse")
    _exigir(isinstance(piezas["vistas"], list) and all(isinstance(v, list) for v in piezas["vistas"]), "vistas")
    for vista in piezas["vistas"]:
        for objeto in vista:
            refs += _rutas_de_objeto(objeto, "vista")
    return refs


def _firmado(archivos, rutas: dict):
    return _ae76.ObjetoFirmado(archivos[rutas["datos"]], archivos[rutas["firma"]], archivos[rutas["clave_publica"]])


def leer_expediente(archivos: Mapping[str, bytes], *, limites: Limites = LIMITES_POR_DEFECTO) -> ExpedienteLeido:
    """Lectura endurecida del expediente a partir de sus bytes."""
    _limites(archivos, NOMBRE_MANIFIESTO, limites)
    manifiesto = _leer_json_canonico(archivos[NOMBRE_MANIFIESTO])
    if manifiesto.get("esquema") != ESQUEMA_EXPEDIENTE:
        _rechazar("version_desconocida", str(manifiesto.get("esquema"))[:80])
    _claves(manifiesto, {"esquema", "archivos", "piezas"}, "manifiesto")
    referencias = _referencias_del_expediente(manifiesto["piezas"])
    _comprobar_archivos(archivos, NOMBRE_MANIFIESTO, manifiesto, referencias, limites)
    piezas = manifiesto["piezas"]
    acuses = tuple(_firmado(archivos, a) for a in piezas["acuses"])
    return ExpedienteLeido(
        entradas=tuple(archivos[r] for r in piezas["registro"]),
        bytes_declaracion=archivos[piezas["declaracion_r0"]],
        sobre=_firmado(archivos, piezas["sobre"]) if piezas["sobre"] is not None else None,
        sellos_r0={(s["codigo_juego"], s["sorteo_objetivo"]): _ae75.EvidenciaDeSello(
            archivos[s["respuesta"]], archivos[s["compromiso"]]) for s in piezas["sellos_r0"]},
        acuses=acuses,
        sellos_de_acuses=tuple(_ae77.EvidenciaDeSelloDeAcuse(acuses[s["acuse"]], archivos[s["respuesta"]],
                                                            archivos[s["compromiso"]])
                               for s in piezas["sellos_de_acuses"]),
        cierre=_firmado(archivos, piezas["cierre"]) if piezas["cierre"] is not None else None,
        conjunto_esperado=_firmado(archivos, piezas["conjunto_esperado"]),
        vistas=tuple(tuple(_firmado(archivos, o) for o in vista) for vista in piezas["vistas"]),
        sha256_manifiesto=hashlib.sha256(archivos[NOMBRE_MANIFIESTO]).hexdigest(),
        numero_de_archivos=len(manifiesto["archivos"]))


def leer_politica(archivos: Mapping[str, bytes], *, limites: Limites = LIMITES_POR_DEFECTO) -> PoliticaLeida:
    """Lectura endurecida de la politica de prueba del verificador."""
    _limites(archivos, NOMBRE_POLITICA, limites)
    manifiesto = _leer_json_canonico(archivos[NOMBRE_POLITICA])
    if manifiesto.get("esquema") != ESQUEMA_POLITICA:
        _rechazar("version_desconocida", str(manifiesto.get("esquema"))[:80])
    _claves(manifiesto, {"esquema", "naturaleza", "archivos", "sello", "claves", "observadores", "auditoria"},
            "politica")
    if manifiesto["naturaleza"] not in NATURALEZAS_DE_POLITICA:
        _rechazar("naturaleza_no_admitida", str(manifiesto["naturaleza"])[:80])
    sello = manifiesto["sello"]
    _claves(sello, {"anclas", "politicas_admitidas", "margen"}, "sello")
    auditoria = manifiesto["auditoria"]
    _claves(auditoria, {"canal", "corte_esperado"}, "auditoria")
    _exigir(isinstance(auditoria["canal"], str) and type(auditoria["corte_esperado"]) is int, "auditoria")
    for lista in (sello["anclas"], sello["politicas_admitidas"], manifiesto["claves"], manifiesto["observadores"]):
        _exigir(isinstance(lista, list), "listas de la politica")
    refs = []
    for ancla in sello["anclas"]:
        _claves(ancla, {"certificado", "etiqueta"}, "ancla")
        refs.append(ancla["certificado"])
    for clave in manifiesto["claves"]:
        _claves(clave, {"clave_publica", "rol", "etiqueta"}, "clave")
        refs.append(clave["clave_publica"])
    for obs in manifiesto["observadores"]:
        _claves(obs, {"clave_publica", "etiqueta"}, "observador")
        refs.append(obs["clave_publica"])
    _comprobar_archivos(archivos, NOMBRE_POLITICA, manifiesto, refs, limites)
    try:
        politica_sello = _ae75.PoliticaDeConfianzaTemporal(
            anclas=tuple(_ae75.AnclaDePrueba(archivos[a["certificado"]], a["etiqueta"]) for a in sello["anclas"]),
            politicas_admitidas=tuple(sello["politicas_admitidas"]), margen=sello["margen"])
        claves = _ae76.PoliticaDeClavesDePrueba(claves=tuple(
            _ae76.ClaveDePrueba(archivos[c["clave_publica"]], c["rol"], c["etiqueta"]) for c in manifiesto["claves"]))
        observadores = _ae77.PoliticaDeObservadoresDePrueba(claves=tuple(
            _ae77.ClaveDeObservadorDePrueba(archivos[o["clave_publica"]], o["etiqueta"])
            for o in manifiesto["observadores"]))
    except (ValueError, TypeError) as error:
        _rechazar("estructura_invalida", str(error)[:120])
    return PoliticaLeida(politica_sello, claves, observadores, auditoria["canal"], auditoria["corte_esperado"],
                         hashlib.sha256(archivos[NOMBRE_POLITICA]).hexdigest())


# ---------------------------------------------------------------------------
# Evaluacion e informe
# ---------------------------------------------------------------------------

CODIGOS_DE_SALIDA = MappingProxyType({"sin_rechazos": 0, "con_rechazos": 1, "uso_incorrecto": 2,
                                      "expediente_ilegible": 3})
SIGNIFICADO_DE_LOS_CODIGOS = MappingProxyType({
    0: "auditoria completada sin planos comprobables rechazados; no autoriza evaluacion y los pendientes siguen "
       "pendientes",
    1: "auditoria completada con al menos un plano comprobable rechazado; no autoriza evaluacion",
    2: "uso incorrecto del comando; no se audito nada",
    3: "la lectura endurecida rechazo el expediente o la politica; no se evaluo ningun plano",
})
"""Ningun codigo significa autorizacion: la autorizacion operativa esta
denegada en todos los casos (`AUTORIZA_EVALUACION = False`)."""

LIMITES = (
    "las claves, certificados, TSA, observador y politica del verificador son de fixture; un plano superado solo "
    "prueba coherencia frente a ese material",
    "la politica del verificador se suministra aparte del expediente: anclas, claves admitidas, canal y corte "
    "esperados los decide quien verifica, no quien presenta la evidencia",
    "el manifiesto no esta firmado: prueba que los archivos coinciden con sus hashes declarados; una alteracion "
    "coherente de archivo y manifiesto solo la detectan las firmas y los vinculos de las piezas",
    "completo respecto del conjunto presentado no es completitud global: las vistas presentadas no descartan "
    "historias ocultas sin monitores independientes y una fuente autorizada",
    "el tiempo por acuse queda pendiente por el ancla de prueba, la revocacion sin comprobar y el plazo sintetico",
    "ejecutar la auditoria no autoriza evaluacion ni convierte R0 en final; AUTORIZA_EVALUACION es False",
)


def _plano(estado: str, motivos) -> dict:
    return {"estado": estado, "motivos": list(motivos)}


def evaluar(expediente: ExpedienteLeido, politica: PoliticaLeida) -> dict:
    """Evaluacion offline: la compuesta de AE-77 con las piezas del
    expediente y la politica del verificador. Devuelve el informe."""
    compuesto = _ae77.evaluar_recepcion_por_objetivo(
        expediente.entradas, expediente.bytes_declaracion, sellos_de_acuses=expediente.sellos_de_acuses,
        declaracion=expediente.conjunto_esperado, vistas=expediente.vistas,
        politica_de_observadores=politica.observadores, corte_esperado=politica.corte_esperado,
        evidencias_de_sello=expediente.sellos_r0, politica_de_sello=politica.sello, sobre=expediente.sobre,
        acuses=expediente.acuses, cierre=expediente.cierre, politica_de_claves=politica.claves,
        canal=politica.canal)
    ae76 = compuesto.expediente
    ae75 = ae76.admision
    p77, m77 = compuesto.planos_ae77, compuesto.motivos
    prep = ae76.planos_preparatorios
    canal = ae76.canal
    completitud = canal.completitud if canal is not None else {}

    def de_canal(nivel):
        r = completitud.get(nivel)
        return _plano(r.estado, r.motivos) if r is not None else _plano(prep[f"completitud_{nivel}"], ())

    tiempos = [{"acuse": i, "estado": t.estado, "motivos": list(t.motivos), "resultado": t.conclusion.resultado,
                "gen_time_utc": t.conclusion.gen_time_utc, "limite_superior_utc": t.conclusion.limite_superior_utc,
                "plazo_utc": t.conclusion.plazo_utc} for i, t in enumerate(compuesto.tiempos)]
    secciones = {
        "integridad_y_firmas": {"planos": {
            "integridad_de_bytes_de_las_piezas": _plano(p77["integridad_de_bytes_de_las_piezas"],
                                                        m77["integridad_de_bytes_de_las_piezas"]),
            "firmas_y_roles_de_prueba": _plano(p77["firmas_y_roles_de_prueba"], m77["firmas_y_roles_de_prueba"]),
            "autenticacion_preparatoria_de_r0": _plano(ae76.autenticacion.estado, ae76.autenticacion.motivos),
            "cierre_del_canal": _plano(prep["cierre_del_canal"], canal.motivos if canal is not None else ()),
            "vistas_del_observador": _plano(compuesto.vistas.estado, compuesto.vistas.motivos),
        }, "alcance": "frente al material presentado y a la politica de prueba del verificador"},
        "tiempo": {"planos": {
            "tiempo_por_acuse": _plano(p77["tiempo_por_acuse"], m77["tiempo_por_acuse"]),
            "sello_temporal_de_r0": _plano(ae75.plano_temporal, ae75.motivos_del_plano),
            "recepcion_preparatoria_antes_del_plazo": _plano(
                prep["recepcion_preparatoria_antes_del_plazo"],
                canal.recepcion_antes_del_plazo.motivos if canal is not None else ()),
        }, "por_acuse": tiempos, "limites": list(_ae75.LIMITES_OPERATIVOS)},
        "completitud_presentada": {"planos": {
            "completitud_respecto_del_manifiesto_presentado": _plano(
                p77["completitud_respecto_del_manifiesto_presentado"],
                m77["completitud_respecto_del_manifiesto_presentado"]),
            "completitud_respecto_del_manifiesto": de_canal("respecto_del_manifiesto"),
            "completitud_respecto_del_registro_presentado": de_canal("respecto_del_registro_presentado"),
        }},
        "pendientes": {"planos": {
            "autoridad_del_manifiesto": _plano(p77["autoridad_del_manifiesto"], m77["autoridad_del_manifiesto"]),
            "completitud_global": _plano(p77["completitud_global"], m77["completitud_global"]),
            "completitud_respecto_de_lo_que_debio_existir": de_canal("respecto_de_lo_que_debio_existir"),
        }, "decisiones_sin_tomar": sorted(k for k, v in _ae77.DECISIONES_OPERATIVAS_PENDIENTES.items()
                                          if v["estado"] == "sin_decidir")},
        "autorizacion_operativa": {
            "estado": "denegada", "AUTORIZA_EVALUACION": _expediente.AUTORIZA_EVALUACION,
            "r0_final": _plano(ae76.r0_final.estado, ae76.r0_final.motivos),
            "planos_ae74": {k: v for k, v in ae75.admision.planos.items()},
            "decisiones": {d: _ae74.DECISIONES_DEL_CONTRATO[d]["estado"] for d in ("D8", "D9")},
        },
    }
    comprobables = ("integridad_y_firmas", "tiempo", "completitud_presentada")
    rechazos = any(p["estado"] == "rechazada" for s in comprobables for p in secciones[s]["planos"].values())
    return {
        "esquema": ESQUEMA_INFORME,
        "expediente": {"esquema": ESQUEMA_EXPEDIENTE, "sha256_manifiesto": expediente.sha256_manifiesto,
                       "archivos": expediente.numero_de_archivos},
        "politica_del_verificador": {"esquema": ESQUEMA_POLITICA, "sha256": politica.sha256,
                                     "naturaleza": "fixture_de_prueba",
                                     "origen": "suministrada_al_verificador_no_al_expediente"},
        "lectura": {"estado": "superada", "motivos": [], "objeto": "expediente_y_politica"},
        "secciones": secciones,
        "resultado_de_la_auditoria": "con_rechazos" if rechazos else "sin_rechazos",
        "limites": list(LIMITES),
    }


def informe_de_lectura_rechazada(objeto: str, error: ExpedienteIlegible) -> dict:
    """Informe cuando la lectura endurecida rechaza el expediente o la
    politica: no se evalua ningun plano y la autorizacion sigue denegada."""
    return {"esquema": ESQUEMA_INFORME, "lectura": {"estado": "rechazada", "motivos": [error.motivo],
                                                    "objeto": objeto},
            "secciones": {}, "resultado_de_la_auditoria": "expediente_ilegible",
            "autorizacion_operativa": {"estado": "denegada", "AUTORIZA_EVALUACION": False},
            "limites": list(LIMITES)}


def codigo_de_salida(informe: dict) -> int:
    return CODIGOS_DE_SALIDA[informe["resultado_de_la_auditoria"]]


def informe_json(informe: dict) -> bytes:
    """JSON determinista: claves ordenadas, UTF-8, LF final."""
    return (json.dumps(informe, sort_keys=True, ensure_ascii=False, separators=(",", ": "), indent=2)
            + "\n").encode("utf-8")


def estado_de_plano(informe: dict, plano: str) -> str:
    for seccion in informe["secciones"].values():
        if plano in seccion.get("planos", {}):
            return seccion["planos"][plano]["estado"]
    raise KeyError(plano)


_TITULOS = (("integridad_y_firmas", "Integridad y firmas (frente al material presentado)"),
            ("tiempo", "Tiempo por acuse (ancla de prueba, revocacion sin comprobar, plazo sintetico)"),
            ("completitud_presentada", "Completitud respecto del conjunto presentado"),
            ("pendientes", "Pendientes (sin decision ni evidencia operativa)"))


def resumen_legible(informe: dict) -> str:
    """Resumen de texto con el estado y los motivos de cada plano."""
    lineas = [f"Expediente portable de recepcion ({ESQUEMA_EXPEDIENTE})",
              f"Lectura: {informe['lectura']['estado']} {' '.join(informe['lectura']['motivos'])}".rstrip()]
    for clave, titulo in _TITULOS:
        seccion = informe["secciones"].get(clave)
        if seccion is None:
            continue
        lineas.append(f"== {titulo}")
        for plano, valor in seccion["planos"].items():
            motivos = ", ".join(valor["motivos"])
            lineas.append(f"  {plano}: {valor['estado']}" + (f" ({motivos})" if motivos else ""))
    autorizacion = informe["secciones"].get("autorizacion_operativa", informe.get("autorizacion_operativa"))
    lineas.append("== Autorizacion operativa: DENEGADA")
    if "r0_final" in autorizacion:
        lineas.append(f"  r0_final: {autorizacion['r0_final']['estado']}")
    lineas.append("  AUTORIZA_EVALUACION = False")
    lineas.append(f"Resultado de la auditoria: {informe['resultado_de_la_auditoria']} "
                  f"(codigo {codigo_de_salida(informe)}: {SIGNIFICADO_DE_LOS_CODIGOS[codigo_de_salida(informe)]})")
    return "\n".join(lineas) + "\n"
