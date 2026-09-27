"""
Contrato de coherencia del diseno de una regla prospectiva -Etapa
AE-56, validada (solo como contrato preparatorio, validador y pruebas;
no aprueba metodo, parametro, regla prospectiva, inferencia ni
autorizacion).

Contrato preparatorio, sin inferencia:

- `DIMENSIONES_AE56`: catalogo profundamente inmutable de las
  dimensiones de diseno, cada una con sus categorias (puede pertenecer
  a varias), su base (literatura verificada o inferencia propia) y sus
  fuentes (pendientes de AE-52, de AE-53 y decisiones de AE-55).
- `validar_especificacion_diseno`: comprueba SOLO la consistencia de los
  campos que declara una especificacion candidata. Estados:
  `incompleta` (falta un campo requerido, vale None o queda una decision
  adicional), `incoherente` (un campo presente tiene tipo, valor o
  combinacion contradictoria; tiene prioridad) y `coherente_no_aprobada`
  (campos declarados consistentes y nada mas).

Nunca aprueba una pregunta, un metodo, parametros, niveles, horizontes
ni mecanismos. No verifica supuestos, procedencia, sellado, token,
manifiesto, hora oficial, custodia, anterioridad, autorizacion ni
validez inferencial. Las variantes M1-M4 de AE-54 solo pueden anotarse
como referencia; nunca deciden. No cierra `regla_estadistica_de_decision`
ni ningun pendiente de AE-52 y no modifica el NO-GO de AE-39 ni los
bloqueos de AE-41/AE-46.

AE-57 (auditoria, validada) corrige defectos verificables sin cambiar
el catalogo ni su huella: el tipo de `supuestos_declarados` y de
`metodo.parametros` se comprueba aunque falte la familia; sin pregunta
valida, cada nivel presente se comprueba contra el rango de su campo; el
EMD de AE-55 exige unidad `sigma`; y un entero con mas de
`DIGITOS_MAXIMOS_ENTERO_CANDIDATA` (640) digitos decimales queda fuera del
limite para calcular la huella, cualquiera que sea la configuracion de
CPython. `coincide_con_propuesta_ae53` es una coincidencia parcial.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields
from types import MappingProxyType

from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from app.application.ml.registro_prospectivo import PENDIENTES_BORRADOR_AE52, REGLAS_EVALUACION_AE52

CATEGORIAS = (
    "justificable_antes_de_datos",
    "pendiente_bloqueado",
    "requiere_decision_humana_o_mecanismo_externo",
    "supuesto_no_verificable",
)
ESTADOS = ("coherente_no_aprobada", "incoherente", "incompleta")
_MINIMO_AE52 = REGLAS_EVALUACION_AE52["minimo_sorteos_resueltos_por_juego"]
_VENTANA_AE53 = ESPECIFICACION_CANDIDATA_AE53["propuestas"]["horizonte"]["valor_propuesto"]["objetivos"]


class DisenoReglaInvalidoError(ValueError):
    """Entrada no canonica o catalogo mal formado."""


@dataclass(frozen=True)
class Dimension:
    id: str
    descripcion: str
    categorias: tuple[str, ...]
    base: str
    fuentes: tuple[str, ...] = ()
    depende_de: tuple[str, ...] = ()
    fijado_por: str | None = None
    propuesta_ae53: str | None = None

    def __post_init__(self) -> None:
        if not self.categorias or self.categorias != tuple(sorted(set(self.categorias))):
            raise DisenoReglaInvalidoError(f"{self.id}: categorias debe ser una tupla ordenada y sin repetidos")
        if not set(self.categorias) <= set(CATEGORIAS):
            raise DisenoReglaInvalidoError(f"{self.id}: categoria desconocida")
        if self.base != "inferencia_propia" and not self.base.startswith("lit:"):
            raise DisenoReglaInvalidoError(f"{self.id}: base debe ser 'inferencia_propia' o 'lit:<referencia>'")
        for nombre in ("fuentes", "depende_de"):
            valor = getattr(self, nombre)
            if not isinstance(valor, tuple) or valor != tuple(sorted(set(valor))):
                raise DisenoReglaInvalidoError(f"{self.id}: {nombre} debe ser una tupla ordenada y sin repetidos")


_J, _P, _H, _S = CATEGORIAS


def _dimension(id_, descripcion, categorias, base, fuentes=(), depende_de=(), fijado_por=None, propuesta=None):
    return Dimension(id_, descripcion, tuple(sorted(categorias)), base, tuple(sorted(fuentes)),
                     tuple(sorted(depende_de)), fijado_por, propuesta)


DIMENSIONES_AE56 = (
    _dimension("pregunta", "P1 media de la ventana, P2 capacidad condicional o P3 mecanismo uniforme (AE-55)",
              (_H, _J), "inferencia_propia", ("ae52:pendiente:regla_estadistica_de_decision", "ae55:decision:pregunta")),
    _dimension("direccion_y_nivel", "P1: nivel unilateral y direccion de mejora; P2: nivel de contraste no direccional",
              (_H, _J), "lit:Diebold-Mariano 1995; Giacomini-White 2006",
              ("ae53:pendiente:nivel_y_umbral", "ae55:decision:alfa_y_direccion"), ("pregunta",)),
    _dimension("familia_metodo", "familia descriptiva compatible con la pregunta; M1-M4 de AE-54 solo como referencia",
              (_H, _J, _P), "lit:Diebold-Mariano 1995; Giacomini-White 2006",
              ("ae52:pendiente:regla_estadistica_de_decision", "ae53:pendiente:unidad_y_metodo_inferencial",
               "ae55:decision:metodo"), ("pregunta",)),
    _dimension("parametros_metodo", "presencia, tipo y rango segun la familia; nunca su adecuacion",
              (_H, _J), "inferencia_propia", ("ae55:decision:metodo",), ("familia_metodo",)),
    _dimension("supuestos_metodo", "supuestos que la familia exige declarar; declararlos no los verifica",
              (_H, _S), "lit:Kunsch 1989; Politis-Romano 1994; Newey-West 1987; Harvey-Leybourne-Newbold 1997",
              ("ae53:pendiente:tratamiento_dependencia_serial", "ae55:decision:supuestos_kappa_estacionariedad"),
              ("familia_metodo",)),
    _dimension("metricas_principales", "LL y Brier en conjuncion (interseccion-union)", (_J,), "lit:Berger 1982",
              ("ae52:regla:metricas_principales",), (), "REGLAS_EVALUACION_AE52"),
    _dimension("secundaria", "una sola condicion P@5 (P@5 = R@5 por sorteo); su papel lo decide el operador",
              (_H, _J), "inferencia_propia", ("ae55:decision:secundaria",), (), "REGLAS_EVALUACION_AE52"),
    _dimension("multiplicidad_juegos", "una afirmacion conjunta entre juegos exige correccion", (_H, _J), "lit:Holm 1979",
              ("ae53:pendiente:multiplicidad_entre_juegos", "ae55:decision:multiplicidad"), ("pregunta",)),
    _dimension("horizonte", "minimo >= 100 fijado por AE-52; ventana exacta de 100 y un analisis propuesta por AE-53",
              (_H, _J), "inferencia_propia", ("ae52:pendiente:corte_temporal_por_juego", "ae55:decision:horizonte"),
              (), "REGLAS_EVALUACION_AE52", "primeros_100_objetivos_un_analisis"),
    _dimension("omisiones", "una omision en la ventana hace el juego no evaluable (propuesta de AE-53)", (_H,),
              "inferencia_propia", ("ae55:decision:omisiones",), ("horizonte",), None,
              "cualquier_omision_en_el_horizonte_no_evaluable"),
    _dimension("efecto_minimo_y_potencia", "valor y unidad declarados; el EMD de AE-55 solo aplica a P1 con media",
              (_H, _S), "inferencia_propia", ("ae53:pendiente:efecto_minimo", "ae55:decision:efecto_minimo_y_potencia"),
              ("direccion_y_nivel", "familia_metodo", "pregunta")),
    _dimension("sellado", "nombre de un mecanismo externo declarado; no se verifica ni se aprueba", (_H, _P),
              "lit:RFC 3161 (norma)", ("ae52:pendiente:mecanismo_de_sellado_temporal_externo",
                                         "ae53:pendiente:mecanismo_de_sellado_temporal_externo",
                                         "ae55:decision:sellado_y_manifiesto")),
    _dimension("hora_oficial", "fuente declarada de la hora oficial del sorteo; no se verifica", (_H,),
              "inferencia_propia", ("ae55:decision:sellado_y_manifiesto",), ("sellado",)),
    _dimension("modelo_congelado", "codigo, configuracion y parametros fijados no congelan las predicciones",
              (_H, _P, _S), "inferencia_propia",
              ("ae52:pendiente:aprobacion_de_la_estrategia_a_congelar", "ae52:pendiente:contrato_de_inferencia_prospectiva",
               "ae52:pendiente:tramo_de_entrenamiento", "ae55:decision:tramo_y_contrato")),
    _dimension("autorizacion", "AE-41 mas validacion humana; NO-GO de AE-39 y AE-46 vigentes", (_H, _P),
              "inferencia_propia", ("ae52:pendiente:autorizacion_ae41_para_prerregistro",
                                    "ae52:pendiente:regla_estadistica_de_decision", "ae55:decision:autorizacion"),
              ("modelo_congelado", "sellado")),
)
"""Catalogo de AE-56: solo textos y tuplas; ningun contenedor mutable."""

SUPUESTOS_POR_FAMILIA = MappingProxyType(dict((
    ("remuestreo_iid_media", ("independencia_de_d_t",)),
    ("remuestreo_bloques_media", ("dependencia_debil", "estacionariedad", "memoria_menor_que_longitud_bloque")),
    ("t_media_sin_autocorrelacion", ("sin_autocorrelacion_de_d_t",)),
    ("t_media_varianza_hac", ("ancho_banda_adecuado", "estacionariedad_en_covarianza")),
    ("contraste_condicional", ("aproximacion_asintotica", "memoria_limitada_o_parametros_congelados")),
)))
"""Supuestos que cada familia exige DECLARAR (AE-55); declararlos no los verifica."""

_FAMILIAS_MEDIA = frozenset({"remuestreo_iid_media", "remuestreo_bloques_media", "t_media_sin_autocorrelacion",
                             "t_media_varianza_hac"})
_REFERENCIAS_AE54 = frozenset({"M1", "M2a", "M2b", "M3a", "M3b", "M4"})
_UNIDADES = frozenset({"sigma", "unidad_de_metrica"})
_CORRECCIONES = frozenset({"holm", "bonferroni"})
_CLAVES = frozenset({"pregunta", "direccion", "nivel_unilateral", "nivel_contraste", "metodo", "supuestos_declarados",
                     "metricas_principales", "secundaria", "multiplicidad", "ventana", "efecto_minimo",
                     "potencia_objetivo", "sellado_declarado", "fuente_hora_oficial_declarada"})
NO_VERIFICA = ("anterioridad", "autorizacion", "custodia", "hora_oficial", "manifiesto", "procedencia", "sellado",
               "supuestos", "token", "validez_inferencial")
BLOQUEOS_DE_LA_BASE_DOCUMENTADA = (
    "no_go_ae39", "ae41_bloqueado_datos_insuficientes", "ae46_desbloqueable_false", *PENDIENTES_BORRADOR_AE52,
)
"""Bloqueos segun la base documentada (sin consultar sus modulos) y los 7 pendientes de AE-52 tal cual."""


# ---------------------------------------------------------------------------
# Serializacion canonica
# ---------------------------------------------------------------------------

def _json(valor) -> bytes:
    texto = json.dumps(valor, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return (texto + "\n").encode("utf-8")


def serializar_catalogo(catalogo=None) -> bytes:
    dimensiones = DIMENSIONES_AE56 if catalogo is None else catalogo
    return _json({
        "dimensiones": [{f.name: getattr(d, f.name) for f in fields(d)} for d in dimensiones],
        "supuestos_por_familia": {k: list(v) for k, v in SUPUESTOS_POR_FAMILIA.items()},
    })


def huella_diseno(catalogo=None) -> str:
    """SHA-256 del catalogo canonico. Lo identifica; no prueba cuando se fijo."""
    return hashlib.sha256(serializar_catalogo(catalogo)).hexdigest()


PROFUNDIDAD_MAXIMA_CANDIDATA = 32
"""Anidamiento maximo de la candidata (la raiz es 0); mas profundo se rechaza."""
DIGITOS_MAXIMOS_ENTERO_CANDIDATA = 640
"""Limite de AE-57: un entero con hasta 640 digitos decimales admite huella.

Es un limite conservador y estable del contrato, no una imposibilidad de
serializar: 640 es el menor limite no nulo que CPython permite configurar
para convertir enteros a texto (`sys.int_info.str_digits_check_threshold`),
asi que un entero admitido se serializa con cualquier configuracion valida
y el resultado no depende de ella."""
_COTA_ENTERO_CANDIDATA = 10 ** DIGITOS_MAXIMOS_ENTERO_CANDIDATA


def _canonica(valor, ruta: str, sin_huella: list, profundidad: int = 0):
    """Copia canonica. Registra en `sin_huella` las rutas cuyo valor impide
    calcular la huella: NaN, infinito o un entero con mas de
    `DIGITOS_MAXIMOS_ENTERO_CANDIDATA` digitos decimales."""
    if profundidad > PROFUNDIDAD_MAXIMA_CANDIDATA:
        raise DisenoReglaInvalidoError(f"{ruta}: anidamiento mayor que {PROFUNDIDAD_MAXIMA_CANDIDATA}")
    if isinstance(valor, Mapping):
        salida = {}
        for clave, contenido in valor.items():
            if not isinstance(clave, str):
                raise DisenoReglaInvalidoError(f"{ruta or 'candidata'}: clave no textual {clave!r}")
            salida[clave] = _canonica(contenido, f"{ruta}.{clave}" if ruta else clave, sin_huella, profundidad + 1)
        return salida
    if isinstance(valor, (list, tuple)):
        return [_canonica(v, f"{ruta}[{i}]", sin_huella, profundidad + 1) for i, v in enumerate(valor)]
    if valor is None or isinstance(valor, (str, bool)):
        return valor
    if isinstance(valor, int):
        if abs(valor) >= _COTA_ENTERO_CANDIDATA:
            sin_huella.append((ruta, f"entero con mas de {DIGITOS_MAXIMOS_ENTERO_CANDIDATA} digitos decimales: "
                                     "fuera del limite de AE-57 para calcular la huella"))
        return valor
    if isinstance(valor, float):
        if not math.isfinite(valor):
            sin_huella.append((ruta, "valor no finito"))
        return valor
    raise DisenoReglaInvalidoError(f"{ruta}: tipo no canonico {type(valor).__name__}")


# ---------------------------------------------------------------------------
# Validacion
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InformeDiseno:
    """Informe inmutable de `validar_especificacion_diseno`.

    `coincide_con_propuesta_ae53` indica una coincidencia parcial con la
    propuesta de horizonte de AE-53: solo en la cantidad de objetivos (100)
    y en el numero de analisis (1). La candidata no puede declarar desde que
    objetivo empieza la ventana (`desde`) ni cuando se analiza, asi que el
    informe no certifica la propuesta completa ni la aprueba. El nombre del
    campo se conserva por compatibilidad (limite residual, AE-57)."""

    estado: str
    violaciones: tuple[str, ...]
    sin_decidir: tuple[str, ...]
    decisiones_adicionales_requeridas: tuple[str, ...]
    coincide_con_propuesta_ae53: tuple[str, ...]
    alternativas_sin_aprobar: tuple[str, ...]
    no_verifica: tuple[str, ...]
    bloqueos_de_la_base_documentada: tuple[str, ...]
    huella: str | None


def _es_entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _es_real(valor) -> bool:
    """Entero (no bool) o float finito. Un entero siempre es finito: no se
    pasa por `math.isfinite`, que desborda con enteros enormes."""
    if isinstance(valor, bool):
        return False
    return isinstance(valor, int) or (isinstance(valor, float) and math.isfinite(valor))


def _en(valor, admitidos) -> bool:
    """Pertenencia segura: solo un texto puede pertenecer a un conjunto de
    textos; un valor no hashable (lista, objeto) no llega a la busqueda."""
    return isinstance(valor, str) and valor in admitidos


def _es_texto(valor) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


class _Revision:
    def __init__(self, candidata: dict) -> None:
        self.c = candidata
        self.violaciones: list[str] = []
        self.sin_decidir: list[str] = []
        self.adicionales: list[str] = []
        self.coincide: list[str] = []
        self.alternativas: list[str] = []

    def mal(self, mensaje: str) -> None:
        self.violaciones.append(mensaje)

    def falta(self, ruta: str) -> None:
        self.sin_decidir.append(ruta)

    def objeto(self, clave: str, permitidas: frozenset) -> dict | None:
        valor = self.c.get(clave)
        if valor is None:
            self.falta(clave)
            return None
        if not isinstance(valor, dict):
            self.mal(f"{clave}: debe ser un objeto")
            return None
        desconocidas = sorted(set(valor) - permitidas)
        if desconocidas:
            self.mal(f"{clave}: campos desconocidos {desconocidas}")
        return valor

    def texto(self, clave: str, contenedor: dict | None = None, ruta: str | None = None, regla: str = "") -> str | None:
        fuente = self.c if contenedor is None else contenedor
        ruta = ruta or clave
        valor = fuente.get(clave)
        if valor is None:
            self.falta(ruta)
            return None
        if not _es_texto(valor):
            self.mal(f"{regla}{ruta}: debe ser un texto no vacio")
            return None
        return valor


def _reglas_pregunta_y_nivel(r: _Revision) -> str | None:
    pregunta = r.texto("pregunta", regla="R1 ")
    if pregunta is not None and not _en(pregunta, ("P1", "P2", "P3")):
        r.mal("R1 pregunta: debe ser P1, P2 o P3")
        pregunta = None
    if pregunta == "P3":
        r.mal("R1 pregunta: P3 trata del mecanismo de sorteo y no se responde con el registro de estrategias de AE-52")
    direccion = r.texto("direccion", regla="R2 ")
    if direccion is not None and not _en(direccion, ("mejora", "no_direccional")):
        r.mal("R2 direccion: debe ser 'mejora' o 'no_direccional'")
    campos = {"P1": ("nivel_unilateral", "nivel_contraste", "mejora", 0.5),
              "P2": ("nivel_contraste", "nivel_unilateral", "no_direccional", 1.0)}
    if pregunta in campos:
        propio, ajeno, direccion_esperada, maximo = campos[pregunta]
        if direccion is not None and direccion != direccion_esperada:
            r.mal(f"R2 direccion: {pregunta} exige '{direccion_esperada}'")
        if r.c.get(ajeno) is not None:
            r.mal(f"R2 {ajeno}: no corresponde a {pregunta}")
        nivel = r.c.get(propio)
        if nivel is None:
            r.falta(propio)
        elif not _es_real(nivel) or not 0.0 < nivel < maximo:
            r.mal(f"R2 {propio}: debe ser un real finito en (0, {maximo})")
    elif pregunta is None:
        # AE-57: sin pregunta valida, cada nivel presente se comprueba contra
        # el rango de su propio campo.
        for campo, maximo in (("nivel_unilateral", 0.5), ("nivel_contraste", 1.0)):
            valor = r.c.get(campo)
            if valor is not None and (not _es_real(valor) or not 0.0 < valor < maximo):
                r.mal(f"R2 {campo}: debe ser un real finito en (0, {maximo})")
    return pregunta


def _reglas_metodo(r: _Revision, pregunta: str | None) -> str | None:
    metodo = r.objeto("metodo", frozenset({"familia", "parametros", "referencia_banco_ae54"}))
    if metodo is None:
        r.falta("metodo.familia")
        _regla_supuestos(r, None)
        return None
    referencia = metodo.get("referencia_banco_ae54")
    if referencia is not None and not _en(referencia, _REFERENCIAS_AE54):
        r.mal("R3 metodo.referencia_banco_ae54: solo anota M1, M2a, M2b, M3a, M3b o M4")
    familia = r.texto("familia", metodo, "metodo.familia", "R3 ")
    if familia is not None and not _en(familia, SUPUESTOS_POR_FAMILIA):
        r.mal(f"R3 metodo.familia: familia desconocida {familia!r}")
        familia = None
    if familia is not None and pregunta == "P1" and familia not in _FAMILIAS_MEDIA:
        r.mal("R3 metodo.familia: P1 solo admite familias de media")
    if familia is not None and pregunta == "P2" and familia != "contraste_condicional":
        r.mal("R3 metodo.familia: P2 solo admite contraste_condicional")
    parametros = metodo.get("parametros")
    if familia is not None:
        _regla_parametros(r, familia, parametros)
    elif parametros is not None and not isinstance(parametros, dict):
        # AE-57: sin familia valida no se juzgan los valores, pero un
        # `parametros` presente que no es un objeto es contradictorio.
        r.mal("R4 metodo.parametros: debe ser un objeto")
    _regla_supuestos(r, familia)
    return familia


def _regla_supuestos(r: _Revision, familia: str | None) -> None:
    """R5. AE-57: el tipo se comprueba tambien cuando falta `metodo`."""
    supuestos = r.c.get("supuestos_declarados")
    if supuestos is None:
        r.falta("supuestos_declarados")
    elif not isinstance(supuestos, list) or not all(_es_texto(s) for s in supuestos):
        r.mal("R5 supuestos_declarados: debe ser una lista de textos")
    elif familia is not None:
        faltan = sorted(set(SUPUESTOS_POR_FAMILIA[familia]) - set(supuestos))
        if faltan:
            r.mal(f"R5 supuestos_declarados: faltan supuestos exigidos por {familia}: {faltan}")


def _regla_parametros(r: _Revision, familia: str, parametros) -> None:
    esperados = {
        "remuestreo_iid_media": ("replicas", "semilla"),
        "remuestreo_bloques_media": ("longitud_bloque", "replicas", "semilla", "variante"),
        "t_media_sin_autocorrelacion": (),
        "t_media_varianza_hac": ("ancho_banda", "kernel"),
        "contraste_condicional": ("funcion_prueba",),
    }[familia]
    if parametros is None:
        parametros = {}
    elif not isinstance(parametros, dict):
        r.mal("R4 metodo.parametros: debe ser un objeto")
        return
    desconocidos = sorted(set(parametros) - set(esperados))
    if desconocidos:
        r.mal(f"R4 metodo.parametros: parametros no previstos para {familia}: {desconocidos}")
    for nombre in esperados:
        valor = parametros.get(nombre)
        ruta = f"metodo.parametros.{nombre}"
        if valor is None:
            r.falta(ruta)
        elif nombre in ("replicas", "longitud_bloque") and not (_es_entero(valor) and valor >= 1):
            r.mal(f"R4 {ruta}: debe ser un entero >= 1")
        elif nombre == "ancho_banda" and not (_es_entero(valor) and valor >= 0):
            r.mal(f"R4 {ruta}: debe ser un entero >= 0")
        elif nombre == "semilla" and not _es_entero(valor):
            r.mal(f"R4 {ruta}: debe ser un entero")
        elif nombre in ("variante", "kernel") and not _es_texto(valor):
            r.mal(f"R4 {ruta}: debe ser un texto no vacio")
        elif nombre == "funcion_prueba" and not (
                isinstance(valor, list) and valor and all(_es_texto(v) for v in valor) and len(set(valor)) == len(valor)):
            r.mal(f"R4 {ruta}: debe ser una lista no vacia de nombres de instrumentos distintos")


def _reglas_metricas(r: _Revision) -> None:
    principales = r.objeto("metricas_principales", frozenset({"metricas", "combinacion"}))
    if principales is not None:
        metricas, combinacion = principales.get("metricas"), principales.get("combinacion")
        if metricas is None or combinacion is None:
            r.falta("metricas_principales.metricas" if metricas is None else "metricas_principales.combinacion")
        if metricas is not None and (not isinstance(metricas, list) or not all(isinstance(m, str) for m in metricas)
                                     or sorted(metricas) != ["brier_score", "log_loss"]
                                     or len(metricas) != 2):
            r.mal("R6 metricas_principales: deben ser exactamente log_loss y brier_score (AE-52)")
        if combinacion is not None and combinacion != "conjuncion":
            r.mal("R6 metricas_principales: la combinacion debe ser 'conjuncion'")
    secundaria = r.objeto("secundaria", frozenset({"metricas", "papel", "tolerancia"}))
    if secundaria is not None:
        metricas = secundaria.get("metricas")
        if metricas is None:
            r.falta("secundaria.metricas")
        elif metricas != ["precision_en_5"]:
            r.mal("R7 secundaria: una sola condicion precision_en_5 (P@5 = R@5 por sorteo)")
        r.texto("papel", secundaria, "secundaria.papel", "R7 ")
        tolerancia = secundaria.get("tolerancia")
        if tolerancia is not None and not _es_real(tolerancia):
            r.mal("R7 secundaria.tolerancia: debe ser un real finito")


def _regla_multiplicidad(r: _Revision) -> None:
    multiplicidad = r.objeto("multiplicidad", frozenset({"afirmacion_conjunta_juegos", "correccion"}))
    if multiplicidad is None:
        return
    conjunta = multiplicidad.get("afirmacion_conjunta_juegos")
    if conjunta is None:
        r.falta("multiplicidad.afirmacion_conjunta_juegos")
    elif not isinstance(conjunta, bool):
        r.mal("R8 multiplicidad.afirmacion_conjunta_juegos: debe ser booleano")
    correccion = multiplicidad.get("correccion")
    if correccion is not None and not _en(correccion, _CORRECCIONES):
        r.mal("R8 multiplicidad.correccion: debe ser 'holm' o 'bonferroni'")
    elif conjunta is True and correccion is None:
        r.falta("multiplicidad.correccion")


def _regla_ventana(r: _Revision) -> None:
    ventana = r.objeto("ventana", frozenset({"objetivos", "analisis"}))
    if ventana is None:
        return
    objetivos, analisis = ventana.get("objetivos"), ventana.get("analisis")
    validos = True
    if objetivos is None:
        r.falta("ventana.objetivos")
        validos = False
    elif not _es_entero(objetivos) or objetivos < _MINIMO_AE52:
        r.mal(f"R9 ventana.objetivos: entero >= {_MINIMO_AE52} (minimo de AE-52; sin reduccion retroactiva)")
        validos = False
    if analisis is None:
        r.falta("ventana.analisis")
        validos = False
    elif not _es_entero(analisis) or analisis < 1:
        r.mal("R9 ventana.analisis: entero >= 1")
        validos = False
    if not validos:
        return
    # Coincidencia parcial (AE-57): solo objetivos y numero de analisis; no se
    # puede comprobar `desde` ni el momento del analisis de la propuesta.
    if objetivos == _VENTANA_AE53 and analisis == 1:
        r.coincide.append("ventana")
    else:
        r.alternativas.append("ventana")
    if analisis > 1:
        r.adicionales.append("analisis_repetidos_y_control_de_error")


def _regla_efecto(r: _Revision, pregunta: str | None, familia: str | None) -> None:
    efecto = r.objeto("efecto_minimo", frozenset({"valor", "unidad", "calculado_con"}))
    potencia = r.c.get("potencia_objetivo")
    if potencia is not None and not (_es_real(potencia) and 0.0 < potencia < 1.0):
        r.mal("R10 potencia_objetivo: debe ser un real finito en (0, 1)")
        potencia = None
    if efecto is None:
        return
    valor = efecto.get("valor")
    if valor is None:
        r.falta("efecto_minimo.valor")
    elif not _es_real(valor) or valor <= 0:
        r.mal("R10 efecto_minimo.valor: debe ser un real finito > 0")
    unidad = efecto.get("unidad")
    if unidad is None:
        r.falta("efecto_minimo.unidad")
    elif not _en(unidad, _UNIDADES):
        r.mal("R10 efecto_minimo.unidad: 'sigma' o 'unidad_de_metrica'")
    calculado_con = efecto.get("calculado_con")
    if calculado_con is None:
        return
    if not _es_texto(calculado_con):
        r.mal("R10 efecto_minimo.calculado_con: debe ser un texto no vacio")
    elif calculado_con == "emd_ae55":
        if unidad is not None and unidad != "sigma":
            # AE-57: el EMD de AE-55 se expresa en unidades de sigma, nunca del problema.
            r.mal("R10 efecto_minimo: el EMD de AE-55 se expresa en unidades de sigma")
        if pregunta == "P2":
            r.mal("R10 efecto_minimo: el EMD unilateral de AE-55 no aplica a P2")
        if familia is not None and familia not in _FAMILIAS_MEDIA:
            r.mal("R10 efecto_minimo: el EMD de AE-55 solo aplica a familias de media")
        if r.c.get("potencia_objetivo") is None:
            r.falta("potencia_objetivo")
        nivel = r.c.get("nivel_unilateral")
        if potencia is not None and _es_real(nivel) and not nivel < potencia:
            r.mal("R10 potencia_objetivo: el dominio de efecto_minimo_detectable exige nivel < potencia < 1")


def _reglas_sellado_y_hora(r: _Revision) -> None:
    sellado = r.texto("sellado_declarado", regla="R11 ")
    if sellado is not None and sellado.strip().lower() == "commit_firmado":
        r.mal("R11 sellado_declarado: un commit firmado solo no es un sello temporal suficiente")
    r.texto("fuente_hora_oficial_declarada", regla="R12 ")


def validar_especificacion_diseno(candidata) -> InformeDiseno:
    """Comprueba solo la consistencia de los campos declarados. No
    aprueba ni verifica supuestos, procedencia, sellado, hora oficial,
    autorizacion ni validez inferencial."""
    if not isinstance(candidata, Mapping):
        raise DisenoReglaInvalidoError("La candidata debe ser un objeto (Mapping)")
    sin_huella: list[tuple[str, str]] = []
    canonica = _canonica(candidata, "", sin_huella)
    r = _Revision(canonica)
    for ruta, motivo in sin_huella:
        r.mal(f"{ruta}: {motivo}")
    desconocidas = sorted(set(canonica) - _CLAVES)
    if desconocidas:
        r.mal(f"campos desconocidos: {desconocidas}")
    pregunta = _reglas_pregunta_y_nivel(r)
    familia = _reglas_metodo(r, pregunta)
    _reglas_metricas(r)
    _regla_multiplicidad(r)
    _regla_ventana(r)
    _regla_efecto(r, pregunta, familia)
    _reglas_sellado_y_hora(r)
    if r.violaciones:
        estado = "incoherente"
    elif r.sin_decidir or r.adicionales:
        estado = "incompleta"
    else:
        estado = "coherente_no_aprobada"
    huella = None if sin_huella else hashlib.sha256(_json(canonica)).hexdigest()
    return InformeDiseno(
        estado=estado, violaciones=tuple(r.violaciones), sin_decidir=tuple(dict.fromkeys(r.sin_decidir)),
        decisiones_adicionales_requeridas=tuple(r.adicionales), coincide_con_propuesta_ae53=tuple(r.coincide),
        alternativas_sin_aprobar=tuple(r.alternativas), no_verifica=NO_VERIFICA,
        bloqueos_de_la_base_documentada=BLOQUEOS_DE_LA_BASE_DOCUMENTADA, huella=huella,
    )
