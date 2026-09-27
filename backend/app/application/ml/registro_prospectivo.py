"""
Registro prospectivo encadenado -Etapa AE-52, validada.

Primera etapa de la evaluacion prospectiva exigida por el NO-GO de
AE-39 ("cualquier evaluacion futura debera ser prospectiva,
prerregistrada antes de observar sorteos posteriores a ese
prerregistro"). Define el formato y las reglas de un registro de solo
anexado con tres tipos de entrada, cada una en JSON canonico:

  1. `protocolo` (siempre la primera y unica): version exacta de la
     estrategia congelada (huella del codigo, parametros y entorno),
     corte temporal por juego, reglas de evaluacion fijas y decisiones
     aun pendientes. Con pendientes es un BORRADOR y no admite salidas.
     En AE-52 un protocolo real solo puede ser el borrador: con AE-41 en
     `BLOQUEADO_DATOS_INSUFICIENTES` ninguna operacion predictiva nueva
     queda autorizada. Los protocolos cerrados solo existen como
     registros sinteticos de prueba (`sintetico: true`), que nunca cuentan.
  2. `prediccion`: salida registrada ANTES del sorteo objetivo, con la
     huella de la entrada (historico contiguo que termina justo antes
     del objetivo) y la salida (una probabilidad por numero del rango).
  3. `resultado`: numeros del sorteo, incorporados DESPUES y siempre en
     una entrada aparte que referencia a su prediccion.

Cada entrada lleva `secuencia` y el hash de la anterior: la cadena
prueba el orden interno y detecta cualquier cambio en una entrada que
tenga otra detras, pero no acredita la fecha. Esa anterioridad exige
un sellado temporal externo (ver `ALCANCE_REGISTRO` y la documentacion
de AE-52).

Este modulo no genera predicciones, no entrena ni carga modelos, no
evalua resultados y no modifica el NO-GO de AE-39 ni los bloqueos de
AE-40 a AE-46. Es puro: sin reloj, sin azar, sin archivos ni base de
datos. La escritura exclusiva de cada entrada vive en
`scripts/registro_prospectivo_ml.py`.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.incertidumbre import MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT
from app.application.ml.reapertura import JUEGOS_AUTORIZADOS_AE40
from app.application.ml.ventanas_temporales import FIN_CONTRATO_AE36, INICIO_HISTORICO_REAL
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame
from app.domain.value_objects.combination import Combination

ESQUEMA_ENTRADA = "registro-prospectivo-ml/1.0"
ESQUEMA_VERIFICACION = "verificacion-registro-prospectivo-ml/1.0"
TIPOS_ENTRADA = ("protocolo", "prediccion", "resultado")
_ORDEN_JUEGOS = ("BALOTO", "BALOTO_REVANCHA")

REGLAS_EVALUACION_AE52 = {
    "minimo_sorteos_resueltos_por_juego": MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT,
    "metricas_principales": ["log_loss", "brier_score"],
    "metricas_secundarias": ["precision_en_5", "recall_en_5"],
    "referencia_azar": "uniforme_cantidad_numeros_sobre_tamano_rango",
    "orientacion_diferencia": "uniforme_menos_estrategia",
    "juegos_por_separado": True,
    "sorteos_consecutivos_sin_sustitucion": True,
    "sin_agregados_antes_del_minimo": True,
}
"""Reglas que el repositorio ya fija (AE-36 metricas y baseline
uniforme; AE-39 orientacion y juegos por separado; minimo vigente de
100 sorteos, que nunca se cambia retroactivamente) mas dos salvaguardas
contra la seleccion a posteriori: sorteos consecutivos sin sustitucion
y ningun agregado antes de alcanzar el minimo. Un protocolo con reglas
distintas se rechaza."""

PENDIENTES_BORRADOR_AE52 = (
    "aprobacion_de_la_estrategia_a_congelar",
    "tramo_de_entrenamiento",
    "contrato_de_inferencia_prospectiva",
    "autorizacion_ae41_para_prerregistro",
    "corte_temporal_por_juego",
    "regla_estadistica_de_decision",
    "mecanismo_de_sellado_temporal_externo",
)
"""Decisiones que el repositorio no permite fijar con rigor en AE-52;
mientras alguna siga pendiente, el protocolo es un borrador."""
_PENDIENTES_CONOCIDOS = frozenset(PENDIENTES_BORRADOR_AE52)

NOTA_PROTOCOLO = (
    "Protocolo del registro prospectivo AE-52. Un protocolo con decisiones pendientes es un borrador y no admite "
    "salidas. El registro no genera predicciones, no habilita recomendaciones ni apuestas y no modifica el NO-GO "
    "de AE-39."
)
ALCANCE_REGISTRO = (
    "La cadena de hashes prueba el orden interno de las entradas y detecta cualquier cambio en una entrada que "
    "tenga otra detras, pero no acredita la fecha: sin un sellado temporal externo de cada salida (o de la cabeza "
    "de la cadena) antes del sorteo, un registro completo podria fabricarse despues. La ultima entrada solo es "
    "comprobable contra una cabeza anclada externamente. En AE-52 un registro real solo contiene el protocolo en "
    "borrador: no admite salidas y no acumula evidencia prospectiva. Este verificador no genera predicciones ni "
    "evalua resultados; los sorteos historicos y las simulaciones no cuentan como sorteos futuros, y el NO-GO de "
    "AE-39 sigue vigente."
)

_JUEGOS_DOMINIO = {"BALOTO": BalotoGame, "BALOTO_REVANCHA": BalotoRevanchaGame}
_HASH = re.compile(r"[0-9a-f]{64}")
_CLAVES_COMUNES = frozenset({"esquema", "secuencia", "tipo", "hash_anterior"})
_CLAVES = {
    "protocolo": _CLAVES_COMUNES | {"protocolo_id", "sintetico", "estrategia", "juegos", "reglas", "pendientes", "nota"},
    "prediccion": _CLAVES_COMUNES | {"protocolo_hash", "codigo_juego", "sorteo_objetivo", "entrada", "salida"},
    "resultado": _CLAVES_COMUNES | {"prediccion_hash", "codigo_juego", "sorteo_objetivo", "numeros"},
}
_CLAVES_ESTRATEGIA = frozenset({"nombre", "descripcion", "huella_codigo", "archivos_codigo", "parametros", "entorno"})


class RegistroProspectivoError(Exception):
    codigo_salida = 1


class RegistroIlegibleError(RegistroProspectivoError):
    codigo_salida = 3


class EntradaRegistroInvalidaError(RegistroProspectivoError):
    codigo_salida = 4


class CadenaRegistroInconsistenteError(RegistroProspectivoError):
    codigo_salida = 5


# ---------------------------------------------------------------------------
# Serializacion canonica
# ---------------------------------------------------------------------------

def serializar_entrada(entrada: dict) -> bytes:
    """JSON canonico en una sola linea: claves ordenadas, sin espacios,
    UTF-8, terminado en LF. Estos bytes son los que se guardan y se
    encadenan."""
    try:
        texto = json.dumps(entrada, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise EntradaRegistroInvalidaError(f"Entrada no serializable como JSON estandar: {error}") from error
    return (texto + "\n").encode("utf-8")


def hash_entrada(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _rechazar_constante(nombre: str):
    raise RegistroIlegibleError(f"Constante JSON no estandar: {nombre}")


def _objeto_sin_duplicados(pares):
    claves = [clave for clave, _ in pares]
    if len(set(claves)) != len(claves):
        raise EntradaRegistroInvalidaError("Clave duplicada en un objeto JSON")
    return dict(pares)


def leer_entrada(contenido: bytes) -> dict:
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RegistroIlegibleError(f"Entrada no UTF-8: {error}") from error
    try:
        entrada = json.loads(texto, parse_constant=_rechazar_constante, object_pairs_hook=_objeto_sin_duplicados)
    except json.JSONDecodeError as error:
        raise RegistroIlegibleError(f"Entrada que no es JSON valido: {error}") from error
    if not isinstance(entrada, dict):
        raise EntradaRegistroInvalidaError("Cada entrada debe ser un objeto JSON")
    if serializar_entrada(entrada) != contenido:
        raise EntradaRegistroInvalidaError("La entrada no esta en forma canonica")
    return entrada


# ---------------------------------------------------------------------------
# Validaciones auxiliares
# ---------------------------------------------------------------------------

def _invalida(mensaje: str) -> EntradaRegistroInvalidaError:
    return EntradaRegistroInvalidaError(mensaje)


def _es_entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _igual_estricto(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _claves_exactas(nodo, esperadas, donde: str) -> None:
    if not isinstance(nodo, dict) or set(nodo) != set(esperadas):
        raise _invalida(f"{donde}: claves distintas de las esperadas")


def _texto(valor, donde: str) -> None:
    if not isinstance(valor, str) or not valor.strip():
        raise _invalida(f"{donde}: debe ser un texto no vacio")


def _parametros_juego(codigo: str):
    juego = _JUEGOS_DOMINIO[codigo]()
    rango_min, rango_max = juego.number_range
    return juego, rango_min, rango_max, juego.numbers_to_pick


def huella_entrada(codigo_juego: str, historico: Sequence[ResultadoNumerico]) -> str:
    """SHA-256 de la entrada normalizada de una salida: numeracion,
    numeros ordenados y superbalota de cada sorteo, en orden. Permite
    comprobar despues que se uso exactamente ese historico."""
    lineas = ["ae52-entrada-v1", codigo_juego]
    for r in sorted(historico, key=lambda r: r.numero_sorteo):
        lineas.append(f"{r.numero_sorteo}:{','.join(str(n) for n in sorted(r.numeros))}:{r.superbalota}")
    return hashlib.sha256(("\n".join(lineas) + "\n").encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Protocolo
# ---------------------------------------------------------------------------

def _validar_estrategia(estrategia) -> None:
    _claves_exactas(estrategia, _CLAVES_ESTRATEGIA, "estrategia")
    _texto(estrategia["nombre"], "estrategia.nombre")
    _texto(estrategia["descripcion"], "estrategia.descripcion")
    if not isinstance(estrategia["huella_codigo"], str) or not _HASH.fullmatch(estrategia["huella_codigo"]):
        raise _invalida("estrategia.huella_codigo debe ser SHA-256 hexadecimal en minusculas")
    archivos = estrategia["archivos_codigo"]
    if not isinstance(archivos, list) or not archivos or not all(isinstance(a, str) and a.strip() for a in archivos):
        raise _invalida("estrategia.archivos_codigo debe ser una lista no vacia de rutas")
    if not isinstance(estrategia["parametros"], dict):
        raise _invalida("estrategia.parametros debe ser un objeto")
    entorno = estrategia["entorno"]
    if not isinstance(entorno, dict) or not all(isinstance(v, str) for v in entorno.values()):
        raise _invalida("estrategia.entorno debe ser un objeto de textos")


def _validar_protocolo(protocolo: dict) -> None:
    _claves_exactas(protocolo, _CLAVES["protocolo"], "protocolo")
    if protocolo["esquema"] != ESQUEMA_ENTRADA:
        raise _invalida("protocolo: esquema desconocido")
    _texto(protocolo["protocolo_id"], "protocolo_id")
    if not isinstance(protocolo["sintetico"], bool):
        raise _invalida("sintetico debe ser booleano")
    _validar_estrategia(protocolo["estrategia"])
    pendientes = protocolo["pendientes"]
    if (not isinstance(pendientes, list) or len(set(pendientes)) != len(pendientes)
            or not all(isinstance(p, str) and p in _PENDIENTES_CONOCIDOS for p in pendientes)):
        raise _invalida(f"pendientes debe ser una lista sin repetir de {sorted(_PENDIENTES_CONOCIDOS)}")
    if not protocolo["sintetico"] and pendientes != list(PENDIENTES_BORRADOR_AE52):
        raise _invalida(
            "AE-52 solo admite un protocolo real en borrador, con todas sus decisiones pendientes: AE-41 no autoriza "
            "ninguna operacion predictiva nueva y cerrar un protocolo real exige una etapa posterior validada"
        )
    juegos = protocolo["juegos"]
    if not isinstance(juegos, dict) or not juegos or not set(juegos) <= JUEGOS_AUTORIZADOS_AE40:
        raise _invalida(f"juegos debe ser un subconjunto no vacio de {sorted(JUEGOS_AUTORIZADOS_AE40)}")
    for codigo, datos in juegos.items():
        _claves_exactas(datos, {"ultimo_sorteo_conocido"}, f"juegos[{codigo}]")
        corte = datos["ultimo_sorteo_conocido"]
        if corte is None:
            if "corte_temporal_por_juego" not in pendientes:
                raise _invalida(f"juegos[{codigo}]: el corte solo puede quedar sin fijar si esta pendiente")
        elif not _es_entero(corte) or corte < FIN_CONTRATO_AE36:
            raise _invalida(
                f"juegos[{codigo}]: ultimo_sorteo_conocido debe ser un entero >= {FIN_CONTRATO_AE36} "
                "(fin del contrato congelado de AE-36)"
            )
    if not _igual_estricto(protocolo["reglas"], REGLAS_EVALUACION_AE52):
        raise _invalida("reglas distintas de las fijas de AE-52 (incluido el minimo vigente de 100 sorteos)")
    if protocolo["nota"] != NOTA_PROTOCOLO:
        raise _invalida("nota distinta de la fija de AE-52")


def construir_protocolo(*, protocolo_id: str, estrategia: dict, cortes: dict, pendientes: Sequence[str],
                        sintetico: bool) -> dict:
    """Primera entrada de un registro. `cortes`: ultimo sorteo conocido
    por juego al registrar el protocolo; solo cuentan objetivos
    posteriores. `sintetico=True` marca registros de prueba, que nunca
    cuentan como evidencia."""
    if not isinstance(cortes, dict):
        raise _invalida("cortes debe ser un objeto por juego")
    protocolo = {
        "esquema": ESQUEMA_ENTRADA, "secuencia": 1, "tipo": "protocolo", "hash_anterior": None,
        "protocolo_id": protocolo_id, "sintetico": sintetico, "estrategia": copy.deepcopy(estrategia),
        "juegos": {codigo: {"ultimo_sorteo_conocido": corte} for codigo, corte in cortes.items()},
        "reglas": copy.deepcopy(REGLAS_EVALUACION_AE52), "pendientes": list(pendientes), "nota": NOTA_PROTOCOLO,
    }
    _validar_protocolo(protocolo)
    return protocolo


def construir_protocolo_borrador(estrategia: dict) -> dict:
    """Borrador real de AE-52: todas las decisiones que el repositorio no
    fija quedan pendientes, incluido el corte temporal. No admite salidas."""
    return construir_protocolo(
        protocolo_id=f"ae52-borrador-{estrategia.get('nombre', 'estrategia')}", estrategia=estrategia,
        cortes={codigo: None for codigo in _ORDEN_JUEGOS}, pendientes=PENDIENTES_BORRADOR_AE52, sintetico=False,
    )


# ---------------------------------------------------------------------------
# Estado del registro
# ---------------------------------------------------------------------------

@dataclass
class EstadoRegistro:
    """Estado derivado de un registro ya validado entrada por entrada."""
    protocolo: dict
    hash_protocolo: str
    hashes: tuple[str, ...] = ()
    tipos: tuple[str, ...] = ()
    predicciones: dict = field(default_factory=dict)  # (juego, objetivo) -> hash
    objetivo_por_hash: dict = field(default_factory=dict)  # hash -> (juego, objetivo)
    resueltas: set = field(default_factory=set)  # hashes de prediccion con resultado

    @property
    def cabeza(self) -> str:
        return self.hashes[-1]

    @property
    def total(self) -> int:
        return len(self.hashes)

    @property
    def protocolo_en_borrador(self) -> bool:
        return bool(self.protocolo["pendientes"])

    @property
    def admite_salidas(self) -> bool:
        return not self.protocolo_en_borrador

    def ultimo_objetivo(self, codigo: str) -> int | None:
        objetivos = [objetivo for juego, objetivo in self.predicciones if juego == codigo]
        return max(objetivos) if objetivos else None


def _validar_prediccion(prediccion: dict, estado: EstadoRegistro) -> None:
    _claves_exactas(prediccion, _CLAVES["prediccion"], "prediccion")
    if prediccion["protocolo_hash"] != estado.hash_protocolo:
        raise _invalida("La prediccion pertenece a otra version de la estrategia (protocolo distinto)")
    if estado.protocolo_en_borrador:
        raise _invalida("El protocolo esta en borrador (decisiones pendientes): no admite predicciones")
    codigo = prediccion["codigo_juego"]
    if codigo not in estado.protocolo["juegos"]:
        raise _invalida(f"El juego '{codigo}' no forma parte del protocolo")
    objetivo = prediccion["sorteo_objetivo"]
    if not _es_entero(objetivo):
        raise _invalida("sorteo_objetivo debe ser entero")
    corte = estado.protocolo["juegos"][codigo]["ultimo_sorteo_conocido"]
    if objetivo <= corte:
        raise _invalida(
            f"El sorteo {objetivo} ya era conocido al registrar el protocolo (corte {corte}): no cuenta como futuro"
        )
    entrada = prediccion["entrada"]
    _claves_exactas(entrada, {"desde", "hasta", "total_sorteos", "huella"}, "prediccion.entrada")
    if not all(_es_entero(entrada[c]) for c in ("desde", "hasta", "total_sorteos")):
        raise _invalida("prediccion.entrada: desde, hasta y total_sorteos deben ser enteros")
    if entrada["hasta"] >= objetivo:
        raise _invalida("La entrada incluye el sorteo objetivo o uno posterior: resultado futuro como entrada")
    if entrada["hasta"] != objetivo - 1:
        raise _invalida("La entrada debe terminar exactamente en el sorteo anterior al objetivo")
    if entrada["desde"] < INICIO_HISTORICO_REAL or entrada["total_sorteos"] != entrada["hasta"] - entrada["desde"] + 1:
        raise _invalida("prediccion.entrada: rango incoherente")
    if not isinstance(entrada["huella"], str) or not _HASH.fullmatch(entrada["huella"]):
        raise _invalida("prediccion.entrada.huella debe ser SHA-256 hexadecimal")
    _claves_exactas(prediccion["salida"], {"probabilidades"}, "prediccion.salida")
    _, rango_min, rango_max, _ = _parametros_juego(codigo)
    probabilidades = prediccion["salida"]["probabilidades"]
    if (not isinstance(probabilidades, list) or len(probabilidades) != rango_max - rango_min + 1
            or not all(isinstance(p, float) and math.isfinite(p) and 0.0 < p < 1.0 for p in probabilidades)):
        raise _invalida(
            f"La salida debe tener {rango_max - rango_min + 1} probabilidades reales en (0, 1), una por numero"
        )
    if (codigo, objetivo) in estado.predicciones:
        raise _invalida(f"La prediccion de {codigo} para el sorteo {objetivo} ya registrada: no se sobrescribe")
    ultimo = estado.ultimo_objetivo(codigo)
    if ultimo is not None and objetivo <= ultimo:
        raise _invalida(f"Los objetivos de {codigo} deben ser estrictamente crecientes (ultimo {ultimo})")


def _validar_resultado(resultado: dict, estado: EstadoRegistro) -> None:
    _claves_exactas(resultado, _CLAVES["resultado"], "resultado")
    referencia = estado.objetivo_por_hash.get(resultado["prediccion_hash"])
    if referencia is None:
        raise _invalida("El resultado no referencia a una prediccion registrada antes")
    if referencia != (resultado["codigo_juego"], resultado["sorteo_objetivo"]):
        raise _invalida("El resultado no coincide en juego y sorteo con su prediccion")
    if resultado["prediccion_hash"] in estado.resueltas:
        raise _invalida("El resultado de esa prediccion ya incorporado: no se sobrescribe")
    _, rango_min, rango_max, cantidad = _parametros_juego(resultado["codigo_juego"])
    numeros = resultado["numeros"]
    if (not isinstance(numeros, list) or len(numeros) != cantidad or not all(_es_entero(n) for n in numeros)
            or numeros != sorted(set(numeros)) or numeros[0] < rango_min or numeros[-1] > rango_max):
        raise _invalida(f"numeros debe ser una lista ordenada de {cantidad} enteros distintos en [{rango_min}, {rango_max}]")


def validar_registro(entradas: Sequence[bytes]) -> EstadoRegistro:
    """Valida un registro completo, entrada por entrada y en orden:
    forma canonica, cadena de hashes y secuencia, y reglas de cada tipo
    frente al estado de las entradas anteriores."""
    if not entradas:
        raise _invalida("El registro esta vacio: la primera entrada debe ser el protocolo")
    estado = None
    for indice, contenido in enumerate(entradas):
        entrada = leer_entrada(contenido)
        tipo = entrada.get("tipo")
        if indice == 0:
            if tipo != "protocolo":
                raise _invalida("La primera entrada del registro debe ser el protocolo")
            if entrada.get("secuencia") != 1 or entrada.get("hash_anterior") is not None:
                raise CadenaRegistroInconsistenteError("El protocolo debe tener secuencia 1 y hash_anterior nulo")
            _validar_protocolo(entrada)
            hash_actual = hash_entrada(contenido)
            estado = EstadoRegistro(protocolo=entrada, hash_protocolo=hash_actual)
        else:
            if entrada.get("secuencia") != indice + 1 or entrada.get("hash_anterior") != estado.cabeza:
                raise CadenaRegistroInconsistenteError(
                    f"La entrada {indice + 1} no enlaza con la anterior (secuencia o hash_anterior)"
                )
            if entrada.get("esquema") != ESQUEMA_ENTRADA:
                raise _invalida(f"La entrada {indice + 1} tiene un esquema desconocido")
            hash_actual = hash_entrada(contenido)
            if tipo == "protocolo":
                raise _invalida("Un registro solo admite una version de la estrategia: segundo protocolo rechazado")
            if tipo == "prediccion":
                _validar_prediccion(entrada, estado)
                clave = (entrada["codigo_juego"], entrada["sorteo_objetivo"])
                estado.predicciones[clave] = hash_actual
                estado.objetivo_por_hash[hash_actual] = clave
            elif tipo == "resultado":
                _validar_resultado(entrada, estado)
                estado.resueltas.add(entrada["prediccion_hash"])
            else:
                raise _invalida(f"Tipo de entrada desconocido: {tipo!r}")
        estado.hashes = estado.hashes + (hash_actual,)
        estado.tipos = estado.tipos + (tipo,)
    return estado


# ---------------------------------------------------------------------------
# Construccion de nuevas entradas
# ---------------------------------------------------------------------------

def _validar_historico_entrada(codigo: str, objetivo: int, historico: Sequence[ResultadoNumerico]) -> list:
    if not _es_entero(objetivo):
        raise _invalida("sorteo_objetivo debe ser entero")
    futuros = sorted(r.numero_sorteo for r in historico if r.numero_sorteo >= objetivo)
    if futuros:
        raise _invalida(
            f"La entrada contiene sorteos iguales o posteriores al objetivo {objetivo} "
            f"(primero {futuros[0]}): no se acepta un resultado futuro como entrada"
        )
    ordenado = sorted(historico, key=lambda r: r.numero_sorteo)
    if not ordenado or ordenado[-1].numero_sorteo != objetivo - 1:
        raise _invalida(f"La entrada debe terminar exactamente en el sorteo {objetivo - 1}")
    if ordenado[0].numero_sorteo < INICIO_HISTORICO_REAL:
        raise _invalida(f"La entrada no puede empezar antes de {INICIO_HISTORICO_REAL}")
    for anterior, actual in zip(ordenado, ordenado[1:]):
        if actual.numero_sorteo != anterior.numero_sorteo + 1:
            raise _invalida(f"La entrada tiene un hueco o un duplicado entre {anterior.numero_sorteo} y {actual.numero_sorteo}")
    juego = _JUEGOS_DOMINIO[codigo]()
    for r in ordenado:
        try:
            valido = juego.validate_draw(Combination(numeros=tuple(r.numeros), superbalota=r.superbalota)).is_valid
        except ValueError:
            valido = False
        if not valido:
            raise _invalida(f"La entrada contiene un sorteo invalido: {r.numero_sorteo}")
    return ordenado


def nueva_prediccion(estado: EstadoRegistro, codigo_juego: str, sorteo_objetivo: int,
                     historico_entrada: Sequence[ResultadoNumerico], probabilidades: Sequence[float]) -> dict:
    """Entrada `prediccion` lista para anexar. No calcula la salida:
    la recibe. En AE-52 solo se usa con salidas sinteticas en pruebas."""
    if codigo_juego not in _JUEGOS_DOMINIO:
        raise _invalida(f"Juego no autorizado: {codigo_juego!r}")
    ordenado = _validar_historico_entrada(codigo_juego, sorteo_objetivo, historico_entrada)
    prediccion = {
        "esquema": ESQUEMA_ENTRADA, "secuencia": estado.total + 1, "tipo": "prediccion",
        "hash_anterior": estado.cabeza, "protocolo_hash": estado.hash_protocolo, "codigo_juego": codigo_juego,
        "sorteo_objetivo": sorteo_objetivo,
        "entrada": {
            "desde": ordenado[0].numero_sorteo, "hasta": ordenado[-1].numero_sorteo, "total_sorteos": len(ordenado),
            "huella": huella_entrada(codigo_juego, ordenado),
        },
        "salida": {"probabilidades": list(probabilidades)},
    }
    _validar_prediccion(prediccion, estado)
    return prediccion


def nuevo_resultado(estado: EstadoRegistro, codigo_juego: str, sorteo_objetivo: int, numeros: Sequence[int]) -> dict:
    """Entrada `resultado`, separada de su prediccion y posterior a ella."""
    prediccion_hash = estado.predicciones.get((codigo_juego, sorteo_objetivo))
    if prediccion_hash is None:
        raise _invalida(f"No hay prediccion registrada de {codigo_juego} para el sorteo {sorteo_objetivo}")
    resultado = {
        "esquema": ESQUEMA_ENTRADA, "secuencia": estado.total + 1, "tipo": "resultado",
        "hash_anterior": estado.cabeza, "prediccion_hash": prediccion_hash, "codigo_juego": codigo_juego,
        "sorteo_objetivo": sorteo_objetivo, "numeros": sorted(numeros),
    }
    _validar_resultado(resultado, estado)
    return resultado


# ---------------------------------------------------------------------------
# Resumen de verificacion (sin metricas ni conclusiones)
# ---------------------------------------------------------------------------

def resumir_registro(estado: EstadoRegistro) -> dict:
    minimo = REGLAS_EVALUACION_AE52["minimo_sorteos_resueltos_por_juego"]
    protocolo = estado.protocolo
    juegos = []
    for codigo in (c for c in _ORDEN_JUEGOS if c in protocolo["juegos"]):
        corte = protocolo["juegos"][codigo]["ultimo_sorteo_conocido"]
        objetivos = sorted(objetivo for juego, objetivo in estado.predicciones if juego == codigo)
        resueltos = sorted(o for o in objetivos if estado.predicciones[(codigo, o)] in estado.resueltas)
        omisiones = []
        if corte is not None and objetivos:
            registrados = set(objetivos)
            omisiones = [n for n in range(corte + 1, objetivos[-1] + 1) if n not in registrados]
        juegos.append({
            "codigo": codigo, "ultimo_sorteo_conocido": corte, "predicciones_registradas": len(objetivos),
            "resultados_incorporados": len(resueltos),
            "predicciones_sin_resultado": [o for o in objetivos if o not in resueltos], "omisiones": omisiones,
            "minimo_resultados_requeridos": minimo, "faltantes": max(0, minimo - len(resueltos)),
        })
    motivos = []
    if estado.protocolo_en_borrador:
        motivos.append("protocolo_en_borrador")
    if protocolo["sintetico"]:
        motivos.append("registro_sintetico")
    if any(j["faltantes"] > 0 for j in juegos):
        motivos.append("faltan_resultados_minimos")
    motivos += ["regla_estadistica_no_implementada_en_ae52", "sellado_temporal_externo_no_verificado",
                "no_go_ae39_vigente"]
    return {
        "esquema": ESQUEMA_VERIFICACION,
        "protocolo": {
            "hash": estado.hash_protocolo, "protocolo_id": protocolo["protocolo_id"],
            "estado": "borrador" if estado.protocolo_en_borrador else "cerrado", "sintetico": protocolo["sintetico"],
            "admite_salidas": estado.admite_salidas,
            "estrategia": protocolo["estrategia"]["nombre"], "huella_codigo": protocolo["estrategia"]["huella_codigo"],
            "pendientes": list(protocolo["pendientes"]),
        },
        "total_entradas": estado.total,
        "cabeza_cadena": estado.cabeza,
        "entradas": [{"secuencia": i + 1, "tipo": t, "hash": h} for i, (t, h) in enumerate(zip(estado.tipos, estado.hashes))],
        "juegos": juegos,
        "evaluacion": {"evaluable": False, "motivos": motivos},
        "alcance": ALCANCE_REGISTRO,
    }
