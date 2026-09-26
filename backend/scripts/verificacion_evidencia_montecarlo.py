"""AE-50, validada: validacion de formato y coherencia interna de una
evidencia JSON de AE-49 (`python -m scripts.simular_azar_uniforme`).

No es prueba de autenticidad ni de procedencia. El SHA-256 identifica
los bytes examinados; sin firma ni fuente externa de confianza, un
archivo fabricado y serializado de forma canonica podria pasar. No
confirma que los datos provengan de PostgreSQL, no recalcula las
estadisticas y no ejecuta Monte Carlo. Una evidencia valida sigue
siendo exploratoria sobre datos reutilizados y no modifica el NO-GO
de AE-39.

Regla estricta: solo se aceptan los parametros fijos de AE-49
(semilla 20260926, B = 10 000, rango 2081..2705, familia de 8).

Comprobaciones, con los codigos de salida del CLI:
  3  bytes no UTF-8, JSON invalido o constantes no estandar
     (NaN, Infinity, -Infinity);
  4  claves duplicadas o exactas, valores no finitos, textos,
     parametros, rango, familia, juegos, totales, huellas, tipos,
     referencias analiticas, claves predictivas o recomendaciones;
  5  coherencia interna: percentil y p-valor alcanzables con B y
     compatibles entre si, Bonferroni y umbral recalculados con la
     funcion existente del motor, y forma canonica de AE-48/49.

Modulo puro: sin base de datos, sin red y sin escribir nada."""
from __future__ import annotations

import hashlib
import json
import math
import re
from fractions import Fraction

from app.application.estadisticas.motor.tests_estadisticos import aplicar_correccion_bonferroni
from app.application.estadisticas.tipos import ResultadoTestEstadistico
from app.application.simulaciones.montecarlo_uniforme import (
    ALPHA_AE49,
    CARACTER_AE49,
    COBERTURA_AJUSTE,
    ESQUEMA_AE49,
    ESTADISTICAS_AE49,
    FRASES_NEGATIVAS_DISCLAIMER,
    GENERADOR_AE49,
    ITERACIONES_AE49,
    JUEGOS_AE49,
    NOTA_AE49,
    RANGO_PRINCIPAL_AE49,
    SEMILLA_AE49,
    TAMANO_FAMILIA_AE49,
    TEXTO_TRAMOS,
    parametros_desde_dominio,
)
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame
from scripts.comparacion_estado_prediccion import CLAVES_PREDICTIVAS, serializar_reporte

ESQUEMA_VERIFICACION = "verificacion-evidencia-montecarlo/1.0"
RESULTADO_VALIDO = "formato_y_coherencia_interna_validos"
ALCANCE_VERIFICACION = (
    "Validacion de formato y coherencia interna de una evidencia JSON de AE-49 con sus parametros fijos; "
    "no es prueba de autenticidad ni de procedencia. El SHA-256 solo identifica los bytes examinados: sin firma "
    "ni fuente externa de confianza, un archivo fabricado y serializado de forma canonica podria pasar; "
    "no confirma que los datos provengan de PostgreSQL y no recalcula las estadisticas. Que dos archivos sean "
    "identicos solo indica bytes iguales y no demuestra por si sola la reproducibilidad del proceso. Una "
    "evidencia valida sigue siendo exploratoria sobre datos reutilizados y no modifica el NO-GO de AE-39."
)
COMPROBACIONES = (
    "utf8_y_json_estandar",
    "sin_claves_duplicadas",
    "valores_finitos",
    "claves_exactas",
    "textos_fijos_ae49",
    "parametros_fijos_ae49",
    "rango_y_familia_fijos",
    "juegos_y_totales",
    "huellas_de_entrada_con_formato",
    "tipos_y_rangos_de_estadisticas",
    "referencias_analiticas",
    "sin_claves_predictivas_ni_recomendaciones",
    "percentil_y_p_valor_alcanzables_y_compatibles",
    "bonferroni_y_umbral_recalculados",
    "forma_canonica",
)

_CLAVES_RAIZ = frozenset({
    "esquema", "caracter", "alembic_revision", "parametros", "rango_principal", "familia_comparaciones",
    "juegos", "nota",
})
_CLAVES_JUEGO = frozenset({
    "codigo", "total_sorteos", "total_transiciones", "total_superbalotas", "entrada_sha256", "estadisticas",
})
_CLAVES_ESTADISTICA = frozenset({
    "nombre", "observado", "media_simulada", "desviacion_simulada", "referencia_analitica",
    "percentil_observado", "p_valor_empirico", "p_valor_ajustado_bonferroni", "supera_umbral_exploratorio",
})
_ESTADISTICAS_ENTERAS = frozenset({"rango_frecuencia_numeros"})
_HUELLA = re.compile(r"[0-9a-f]{64}")
_TEXTOS_PROHIBIDOS = ("recomendacion", "recomendamos", "recomendad", "combinacion", "prediccion", "confirmatorio")
_JUEGOS_DOMINIO = {"BALOTO": BalotoGame, "BALOTO_REVANCHA": BalotoRevanchaGame}


class VerificacionEvidenciaError(Exception):
    codigo_salida = 1


class EvidenciaIlegibleError(VerificacionEvidenciaError):
    codigo_salida = 3


class EvidenciaInvalidaError(VerificacionEvidenciaError):
    codigo_salida = 4


class EvidenciaIncoherenteError(VerificacionEvidenciaError):
    codigo_salida = 5


# ---------------------------------------------------------------------------
# Lectura estricta
# ---------------------------------------------------------------------------

def _rechazar_constante(nombre: str):
    raise EvidenciaIlegibleError(f"Constante JSON no estandar: {nombre}")


def _objeto_sin_duplicados(pares):
    claves = [clave for clave, _ in pares]
    if len(set(claves)) != len(claves):
        raise EvidenciaInvalidaError("Clave duplicada en un objeto JSON")
    return dict(pares)


def _leer(contenido: bytes):
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError as error:
        raise EvidenciaIlegibleError(f"El archivo no es UTF-8: {error}") from error
    try:
        return json.loads(texto, parse_constant=_rechazar_constante, object_pairs_hook=_objeto_sin_duplicados)
    except json.JSONDecodeError as error:
        raise EvidenciaIlegibleError(f"El archivo no es JSON valido: {error}") from error


# ---------------------------------------------------------------------------
# Estructura, textos, constantes y tipos (codigo 4)
# ---------------------------------------------------------------------------

def _invalida(mensaje: str) -> EvidenciaInvalidaError:
    return EvidenciaInvalidaError(mensaje)


def _igual_estricto(a, b) -> bool:
    """Igualdad que distingue `true` de `1` y `1.0` de `1`."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _es_entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _es_real(valor) -> bool:
    return isinstance(valor, float)


def _verificar_finitos(nodo, donde="raiz") -> None:
    if isinstance(nodo, float) and not math.isfinite(nodo):
        raise _invalida(f"{donde}: valor no finito")
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            _verificar_finitos(valor, f"{donde}.{clave}")
    elif isinstance(nodo, list):
        for indice, valor in enumerate(nodo):
            _verificar_finitos(valor, f"{donde}[{indice}]")


def _claves_exactas(nodo, esperadas: frozenset, donde: str) -> None:
    if not isinstance(nodo, dict):
        raise _invalida(f"{donde}: se esperaba un objeto")
    if set(nodo) != esperadas:
        raise _invalida(f"{donde}: claves distintas de las esperadas")


def _sin_predicciones_ni_recomendaciones(reporte) -> None:
    def recorrer(nodo):
        if isinstance(nodo, dict):
            for clave, valor in nodo.items():
                if clave in CLAVES_PREDICTIVAS:
                    raise _invalida(f"Clave predictiva '{clave}'")
                yield from recorrer(valor)
        elif isinstance(nodo, list):
            for valor in nodo:
                yield from recorrer(valor)
        elif isinstance(nodo, str):
            yield nodo

    for texto in recorrer(reporte):
        texto = texto.lower()
        for frase in FRASES_NEGATIVAS_DISCLAIMER:
            texto = texto.replace(frase, "")
        for prohibido in _TEXTOS_PROHIBIDOS:
            if prohibido in texto:
                raise _invalida(f"Texto no permitido: '{prohibido}' fuera del disclaimer fijo")


def _referencias(codigo: str):
    params = parametros_desde_dominio(codigo, _JUEGOS_DOMINIO[codigo]())
    n = params.rango_max - params.rango_min + 1
    k = params.cantidad_numeros
    m = params.superbalota_max - params.superbalota_min + 1
    return (float(Fraction(n - k)), None, float(Fraction(k * k, n)), float(Fraction(m - 1)))


def _validar_estadistica(e, nombre: str, referencia, donde: str) -> None:
    _claves_exactas(e, _CLAVES_ESTADISTICA, donde)
    if e["nombre"] != nombre:
        raise _invalida(f"{donde}: estadistica fuera de orden")
    if nombre in _ESTADISTICAS_ENTERAS:
        if not _es_entero(e["observado"]) or e["observado"] < 0:
            raise _invalida(f"{donde}: 'observado' debe ser entero >= 0")
    elif not _es_real(e["observado"]) or e["observado"] < 0:
        raise _invalida(f"{donde}: 'observado' debe ser real >= 0")
    for campo in ("media_simulada", "desviacion_simulada"):
        if not _es_real(e[campo]) or e[campo] < 0:
            raise _invalida(f"{donde}: '{campo}' debe ser real >= 0")
    if not _igual_estricto(e["referencia_analitica"], referencia):
        raise _invalida(f"{donde}: 'referencia_analitica' distinta de la de AE-49")
    if not _es_real(e["percentil_observado"]) or not 0 <= e["percentil_observado"] <= 1:
        raise _invalida(f"{donde}: 'percentil_observado' fuera de [0, 1]")
    for campo in ("p_valor_empirico", "p_valor_ajustado_bonferroni"):
        if not _es_real(e[campo]) or not 0 < e[campo] <= 1:
            raise _invalida(f"{donde}: '{campo}' fuera de (0, 1]")
    if not isinstance(e["supera_umbral_exploratorio"], bool):
        raise _invalida(f"{donde}: 'supera_umbral_exploratorio' debe ser booleano")


def _validar_estructura(reporte, *, semilla: int, iteraciones: int) -> None:
    if not isinstance(reporte, dict):
        raise _invalida("La raiz debe ser un objeto JSON")
    _verificar_finitos(reporte)
    _claves_exactas(reporte, _CLAVES_RAIZ, "raiz")
    for campo, esperado in (("esquema", ESQUEMA_AE49), ("caracter", CARACTER_AE49), ("nota", NOTA_AE49)):
        if reporte[campo] != esperado:
            raise _invalida(f"'{campo}' distinto del texto fijo de AE-49")
    if not isinstance(reporte["alembic_revision"], str) or not reporte["alembic_revision"].strip():
        raise _invalida("'alembic_revision' debe ser un texto no vacio")
    if not _igual_estricto(reporte["parametros"], {
        "semilla": semilla, "iteraciones": iteraciones, "generador": GENERADOR_AE49,
        "estadisticas": list(ESTADISTICAS_AE49),
    }):
        raise _invalida("'parametros' distintos de los fijos de AE-49 (semilla, iteraciones, generador, estadisticas)")
    if not _igual_estricto(reporte["rango_principal"], {
        "desde": RANGO_PRINCIPAL_AE49[0], "hasta": RANGO_PRINCIPAL_AE49[1], "tramos": TEXTO_TRAMOS,
    }):
        raise _invalida("'rango_principal' distinto del fijo de AE-49")
    if not _igual_estricto(reporte["familia_comparaciones"], {
        "metodo": "bonferroni", "tamano": TAMANO_FAMILIA_AE49, "alcance": "ocho_comparaciones_de_esta_ejecucion",
        "alpha": ALPHA_AE49, "cobertura": COBERTURA_AJUSTE,
    }):
        raise _invalida("'familia_comparaciones' distinta de la fija de AE-49")

    juegos = reporte["juegos"]
    if not isinstance(juegos, list) or len(juegos) != len(JUEGOS_AE49):
        raise _invalida("'juegos' debe contener exactamente BALOTO y BALOTO_REVANCHA")
    total_esperado = RANGO_PRINCIPAL_AE49[1] - RANGO_PRINCIPAL_AE49[0] + 1
    totales_esperados = {
        "total_sorteos": total_esperado, "total_transiciones": total_esperado - 1,
        "total_superbalotas": total_esperado,
    }
    for juego, codigo in zip(juegos, JUEGOS_AE49):
        donde = f"juegos[{codigo}]"
        _claves_exactas(juego, _CLAVES_JUEGO, donde)
        if juego["codigo"] != codigo:
            raise _invalida(f"{donde}: juego fuera de orden")
        for campo, esperado in totales_esperados.items():
            if not _es_entero(juego[campo]) or juego[campo] != esperado:
                raise _invalida(f"{donde}: '{campo}' debe ser {esperado}")
        if not isinstance(juego["entrada_sha256"], str) or not _HUELLA.fullmatch(juego["entrada_sha256"]):
            raise _invalida(f"{donde}: 'entrada_sha256' debe ser hexadecimal en minusculas de 64 caracteres")
        estadisticas = juego["estadisticas"]
        if not isinstance(estadisticas, list) or len(estadisticas) != len(ESTADISTICAS_AE49):
            raise _invalida(f"{donde}: se esperaban {len(ESTADISTICAS_AE49)} estadisticas")
        for e, nombre, referencia in zip(estadisticas, ESTADISTICAS_AE49, _referencias(codigo)):
            _validar_estadistica(e, nombre, referencia, f"{donde}.{nombre}")
    _sin_predicciones_ni_recomendaciones(reporte)


# ---------------------------------------------------------------------------
# Coherencia interna (codigo 5)
# ---------------------------------------------------------------------------

def _numerador_exacto(valor: float, denominador: int, maximo: int) -> int | None:
    """Entero j en [0, maximo] con float(Fraction(j, denominador)) == valor,
    tal como lo serializa AE-49; None si no existe."""
    base = round(valor * denominador)
    for j in (base - 1, base, base + 1):
        if 0 <= j <= maximo and float(Fraction(j, denominador)) == valor:
            return j
    return None


def _p_compatible(p: float, j: int, iteraciones: int) -> bool:
    """AE-49: percentil = j/(2B) con j = 2·menores + iguales, y
    p = min(1, 2·(1 + min(B, j) − menores)/(B+1)), porque
    1 + menores + iguales = 1 + j − menores. `menores` debe cumplir
    max(0, j − B) <= menores <= j // 2."""
    b = iteraciones
    menores_min, menores_max = max(0, j - b), j // 2
    if menores_min > menores_max:
        return False
    if p == 1.0:
        return 2 * (1 + min(b, j) - menores_min) >= b + 1
    k = _numerador_exacto(p, b + 1, b + 1)
    if k is None or k % 2:
        return False
    menores = 1 + min(b, j) - k // 2
    return menores_min <= menores <= menores_max and float(min(Fraction(1), Fraction(k, b + 1))) == p


def _validar_coherencia(reporte, contenido: bytes, *, iteraciones: int) -> None:
    if serializar_reporte(reporte) != contenido:
        raise EvidenciaIncoherenteError("Los bytes no estan en la forma canonica de AE-49 (serializar_reporte)")
    entradas = [(j["codigo"], e) for j in reporte["juegos"] for e in j["estadisticas"]]
    for codigo, e in entradas:
        donde = f"juegos[{codigo}].{e['nombre']}"
        j = _numerador_exacto(e["percentil_observado"], 2 * iteraciones, 2 * iteraciones)
        if j is None:
            raise EvidenciaIncoherenteError(f"{donde}: percentil no alcanzable con B = {iteraciones}")
        if not _p_compatible(e["p_valor_empirico"], j, iteraciones):
            raise EvidenciaIncoherenteError(f"{donde}: p-valor no alcanzable o incompatible con el percentil")
    pruebas = [
        ResultadoTestEstadistico(
            nombre_test=f"montecarlo_{codigo}_{e['nombre']}", elementos=("*",), estadistico=0.0,
            grados_libertad=None, p_value=e["p_valor_empirico"], p_value_ajustado=None, metodo_correccion=None,
            alpha=None, significativo=None,
        )
        for codigo, e in entradas
    ]
    for (codigo, e), ajustada in zip(entradas, aplicar_correccion_bonferroni(pruebas, alpha=ALPHA_AE49)):
        if ajustada.p_value_ajustado != e["p_valor_ajustado_bonferroni"]:
            raise EvidenciaIncoherenteError(f"juegos[{codigo}].{e['nombre']}: Bonferroni sobre 8 no coincide")
        if bool(ajustada.significativo) != e["supera_umbral_exploratorio"]:
            raise EvidenciaIncoherenteError(f"juegos[{codigo}].{e['nombre']}: umbral exploratorio incoherente")


def _validar_reporte(reporte, contenido: bytes, *, semilla: int, iteraciones: int) -> None:
    _validar_estructura(reporte, semilla=semilla, iteraciones=iteraciones)
    _validar_coherencia(reporte, contenido, iteraciones=iteraciones)


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def validar_evidencia(contenido: bytes) -> dict:
    """Valida una evidencia con los parametros fijos de AE-49 y devuelve
    un resumen sin valores estadisticos."""
    reporte = _leer(contenido)
    _validar_reporte(reporte, contenido, semilla=SEMILLA_AE49, iteraciones=ITERACIONES_AE49)
    return {
        "sha256": hashlib.sha256(contenido).hexdigest(),
        "bytes": len(contenido),
        "juegos": [{"codigo": j["codigo"], "entrada_sha256": j["entrada_sha256"]} for j in reporte["juegos"]],
    }


def construir_informe(resumenes: list[dict], *, bytes_identicos: bool | None = None) -> dict:
    """Informe de una o dos evidencias ya validadas por separado.

    Con una evidencia, `bytes_identicos` debe ser None. Con dos, debe ser
    exactamente True: el resultado de comparar los bytes reales de ambos
    archivos (`contenido_a == contenido_b`), calculado por quien llama.
    Las huellas SHA-256 de los resumenes son solo informativas y nunca
    deciden la igualdad. Si falta la comparacion o dio False, ValueError
    (el CLI devuelve el codigo 6 sin informe)."""
    if len(resumenes) == 1:
        if bytes_identicos is not None:
            raise ValueError("Con una sola evidencia no hay comparacion de bytes")
    elif len(resumenes) == 2:
        if bytes_identicos is not True:
            raise ValueError(
                "Con dos evidencias solo se informa si la comparacion efectiva de bytes dio identicos "
                "(bytes_identicos=True); la misma huella no basta"
            )
    else:
        raise ValueError("Se esperaban una o dos evidencias")
    return {
        "esquema": ESQUEMA_VERIFICACION,
        "resultado": RESULTADO_VALIDO,
        "archivos": [{"sha256": r["sha256"], "bytes": r["bytes"]} for r in resumenes],
        "comparacion_de_archivos": "archivos_identicos" if len(resumenes) == 2 else "no_aplica",
        "juegos": resumenes[0]["juegos"],
        "comprobaciones": list(COMPROBACIONES),
        "alcance": ALCANCE_VERIFICACION,
    }
