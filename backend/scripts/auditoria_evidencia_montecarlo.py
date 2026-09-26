"""AE-51, validada: auditoria de una evidencia JSON de AE-49 frente al
historico actual 2081..2705 de BALOTO y BALOTO_REVANCHA.

La evidencia se valida primero con AE-50 (formato y coherencia
interna). Despues, con los repositorios inyectados, se comprueba para
cada juego que el historico actual cumple el contrato de AE-49
(exactamente 2081..2705 y sorteos validos) y se comparan con la
evidencia:
  - la huella normalizada de entrada (`huella_entrada` de AE-49);
  - los totales de sorteos, transiciones y superbalotas;
  - las cuatro estadisticas observadas, recalculadas con
    `calcular_estadisticas` de AE-49 y serializadas igual que AE-49.

No repite Monte Carlo: no verifica medias ni desviaciones simuladas,
percentiles, p-valores ni Bonferroni frente a los datos (solo su
coherencia interna, que ya comprueba AE-50). Una coincidencia indica
que los datos actuales producen la misma entrada y los mismos valores
observados; no prueba la procedencia historica del archivo ni cuando
se genero. El resultado es exploratorio y no modifica el NO-GO de
AE-39.

Modulo sin SQLAlchemy ni escrituras: la conexion READ ONLY y el
ROLLBACK los gestiona el CLI `scripts/auditar_evidencia_montecarlo.py`."""
from __future__ import annotations

import json
from fractions import Fraction

from app.application.simulaciones.montecarlo_uniforme import (
    ESTADISTICAS_AE49,
    JUEGOS_AE49,
    RANGO_PRINCIPAL_AE49,
    EntradaSimulacionInvalidaError,
    calcular_estadisticas,
    huella_entrada,
    parametros_desde_dominio,
    verificar_rango_principal,
)
from app.domain.games.baloto import BalotoGame
from app.domain.games.baloto_revancha import BalotoRevanchaGame
from scripts.verificacion_evidencia_montecarlo import validar_evidencia

ESQUEMA_AUDITORIA = "auditoria-evidencia-montecarlo/1.0"
COMPROBADO = (
    "formato_y_coherencia_interna_ae50",
    "transaccion_read_only_verificada",
    "revision_alembic_esperada",
    "rango_2081_2705_exacto_y_valido",
    "parametros_del_juego_frente_al_dominio",
    "huella_normalizada_de_entrada",
    "totales_de_sorteos_transiciones_y_superbalotas",
    "estadisticas_observadas_recalculadas",
)
NO_COMPROBADO = (
    "simulacion_monte_carlo_no_repetida",
    "medias_y_desviaciones_simuladas",
    "percentiles_y_p_valores",
    "bonferroni_y_umbral_frente_a_datos",
    "procedencia_historica_del_archivo",
    "tramo_2706_en_adelante",
)
ALCANCE_AUDITORIA = (
    "Auditoria de una evidencia AE-49 frente al historico actual 2081..2705 de BALOTO y BALOTO_REVANCHA, "
    "leido en una transaccion READ ONLY verificada que termina con ROLLBACK; 2706 en adelante no se lee. "
    "Compara la huella normalizada de entrada, los totales y las cuatro estadisticas observadas recalculadas "
    "con el codigo de AE-49. El auditor no repite Monte Carlo: no verifica medias ni desviaciones simuladas, "
    "percentiles, p-valores ni Bonferroni frente a los datos, mas alla de la coherencia interna de AE-50. "
    "Una coincidencia indica que los datos actuales producen la misma entrada y los mismos valores observados; "
    "no prueba la procedencia historica del archivo ni cuando se genero. El resultado es exploratorio sobre "
    "datos reutilizados y no modifica el NO-GO de AE-39."
)

_JUEGOS_DOMINIO = {"BALOTO": BalotoGame, "BALOTO_REVANCHA": BalotoRevanchaGame}
_ESTADISTICAS_ENTERAS = frozenset({"rango_frecuencia_numeros"})


def leer_evidencia_validada(contenido: bytes) -> tuple[dict, dict]:
    """Valida con AE-50 (propaga sus errores, codigos 3/4/5) y devuelve
    el resumen de AE-50 y el reporte ya parseado."""
    resumen = validar_evidencia(contenido)
    return resumen, json.loads(contenido.decode("utf-8"))


def _serializado_como_ae49(nombre: str, valor: Fraction):
    """Misma conversion que usa AE-49 al construir su reporte."""
    return int(valor) if nombre in _ESTADISTICAS_ENTERAS else float(valor)


def _igual_estricto(a, b) -> bool:
    """Distingue `31` de `31.0`, como la serializacion JSON."""
    return json.dumps(a) == json.dumps(b)


def _verificar_parametros(juego, dominio) -> None:
    """Los parametros registrados en la base de datos deben coincidir con
    el dominio, que es la fuente de verdad del mecanismo de sorteo."""
    esperado = (dominio.number_range, dominio.numbers_to_pick, dominio.has_superballot, dominio.superballot_range)
    registrado = (
        (juego.rango_min, juego.rango_max), juego.cantidad_numeros, juego.tiene_superbalota,
        (juego.superbalota_min, juego.superbalota_max),
    )
    if registrado != esperado:
        raise EntradaSimulacionInvalidaError(
            f"Los parametros de '{juego.codigo}' en la base de datos no coinciden con el dominio"
        )


def auditar_contra_historico(reporte: dict, juego_repository, resultados_repository) -> list[dict]:
    """Compara la evidencia (ya validada por AE-50) con el historico actual.
    Lee ambos juegos antes de devolver nada: un fallo se propaga sin
    resultado parcial. `EntradaSimulacionInvalidaError` si el historico o
    los parametros actuales no cumplen el contrato de AE-49."""
    por_codigo = {juego["codigo"]: juego for juego in reporte["juegos"]}
    auditados = []
    for codigo in JUEGOS_AE49:
        dominio = _JUEGOS_DOMINIO[codigo]()
        juego = juego_repository.obtener_por_codigo(codigo)
        if juego is None:
            raise EntradaSimulacionInvalidaError(f"El juego '{codigo}' no existe en la base de datos")
        _verificar_parametros(juego, dominio)
        historico = resultados_repository.listar_resultados_numericos(
            juego.id, hasta_numero_sorteo=RANGO_PRINCIPAL_AE49[1],
        )
        historico = verificar_rango_principal(historico, dominio)
        valores = calcular_estadisticas(historico, parametros_desde_dominio(codigo, dominio))
        evidencia = por_codigo[codigo]
        actual = huella_entrada(codigo, historico)
        totales_actuales = (valores.total_sorteos, valores.total_transiciones, valores.total_superbalotas)
        totales_evidencia = (
            evidencia["total_sorteos"], evidencia["total_transiciones"], evidencia["total_superbalotas"],
        )
        estadisticas = []
        for nombre, valor, en_evidencia in zip(ESTADISTICAS_AE49, valores.como_fracciones(), evidencia["estadisticas"]):
            estadisticas.append({
                "nombre": nombre,
                "coincide": _igual_estricto(_serializado_como_ae49(nombre, valor), en_evidencia["observado"]),
            })
        auditados.append({
            "codigo": codigo,
            "entrada_sha256_evidencia": evidencia["entrada_sha256"],
            "entrada_sha256_actual": actual,
            "huella_coincide": actual == evidencia["entrada_sha256"],
            "totales_coinciden": totales_actuales == totales_evidencia,
            "estadisticas_observadas": estadisticas,
        })
    return auditados


def construir_informe_auditoria(resumen: dict, reporte: dict, juegos: list[dict], revision_actual: str) -> dict:
    coincide = all(
        juego["huella_coincide"] and juego["totales_coinciden"]
        and all(e["coincide"] for e in juego["estadisticas_observadas"])
        for juego in juegos
    )
    return {
        "esquema": ESQUEMA_AUDITORIA,
        "resultado": "coincide" if coincide else "no_coincide",
        "evidencia": {"sha256": resumen["sha256"], "bytes": resumen["bytes"]},
        "alembic_revision_evidencia": reporte["alembic_revision"],
        "alembic_revision_actual": revision_actual,
        "misma_revision_alembic": reporte["alembic_revision"] == revision_actual,
        "rango_auditado": {"desde": RANGO_PRINCIPAL_AE49[0], "hasta": RANGO_PRINCIPAL_AE49[1]},
        "juegos": juegos,
        "comprobado": list(COMPROBADO),
        "no_comprobado": list(NO_COMPROBADO),
        "alcance": ALCANCE_AUDITORIA,
    }
