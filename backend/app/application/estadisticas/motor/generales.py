"""
Motor de estadísticas generales (Paso 3).

Funciones puras: ninguna conoce PostgreSQL, SQLAlchemy, HTTP ni
ningún detalle de infraestructura. Reciben secuencias de DTOs planos
(`tipos.py`) y devuelven dataclasses tipados -nunca floats ni dicts
sueltos donde corresponde una magnitud estadística.

`resultados` siempre llega YA CORTADO por el llamador (vía
`hasta_numero_sorteo` del futuro repositorio, cuando aplique). Estas
funciones no filtran nada por su cuenta -solo resumen lo que reciben.
Esto es lo que permite reutilizarlas sin cambios tanto para el
análisis histórico completo como para backtesting walk-forward.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from app.application.estadisticas.tipos import (
    FrecuenciaObservada,
    ReporteConsistenciaTemporal,
    ReporteHuecos,
    ResumenGeneral,
    TieneMetadatosSorteo,
)


def calcular_resumen_general(
    resultados: Sequence[TieneMetadatosSorteo], juego_codigo: str = ""
) -> ResumenGeneral:
    """Total de sorteos, primer/último (número + fecha), rango de
    numero_sorteo. Con lista vacía: todos los campos opcionales
    quedan en None, total_sorteos=0."""
    if not resultados:
        return ResumenGeneral(
            juego_codigo=juego_codigo,
            total_sorteos=0,
            primer_sorteo_numero=None,
            primer_sorteo_fecha=None,
            ultimo_sorteo_numero=None,
            ultimo_sorteo_fecha=None,
            numero_sorteo_minimo=None,
            numero_sorteo_maximo=None,
        )

    ordenados = sorted(resultados, key=lambda r: r.numero_sorteo)
    primero = ordenados[0]
    ultimo = ordenados[-1]
    numeros_sorteo = [r.numero_sorteo for r in resultados]

    return ResumenGeneral(
        juego_codigo=juego_codigo,
        total_sorteos=len(resultados),
        primer_sorteo_numero=primero.numero_sorteo,
        primer_sorteo_fecha=primero.fecha,
        ultimo_sorteo_numero=ultimo.numero_sorteo,
        ultimo_sorteo_fecha=ultimo.fecha,
        numero_sorteo_minimo=min(numeros_sorteo),
        numero_sorteo_maximo=max(numeros_sorteo),
    )


def _frecuencia_desde_contador(contador: Counter, total_sorteos: int) -> list[FrecuenciaObservada]:
    filas = []
    for valor, apariciones in sorted(contador.items()):
        frecuencia_relativa = (apariciones / total_sorteos) if total_sorteos else 0.0
        filas.append(
            FrecuenciaObservada(
                valor=str(valor),
                apariciones=apariciones,
                total_sorteos=total_sorteos,
                frecuencia_relativa=frecuencia_relativa,
            )
        )
    return filas


def calcular_frecuencia_sorteos_por_anio(
    resultados: Sequence[TieneMetadatosSorteo],
) -> list[FrecuenciaObservada]:
    """valor = año como string ("2024"). Solo incluye años con al
    menos un sorteo -a diferencia de la frecuencia de números, no
    tiene sentido enumerar "años sin sorteos" en un rango arbitrario."""
    total = len(resultados)
    contador = Counter(r.fecha.year for r in resultados)
    return _frecuencia_desde_contador(contador, total)


def calcular_frecuencia_sorteos_por_mes(
    resultados: Sequence[TieneMetadatosSorteo],
) -> list[FrecuenciaObservada]:
    """valor = mes como string ("1".."12"), AGREGADO across todos los
    años del histórico (no por combinación año-mes)."""
    total = len(resultados)
    contador = Counter(r.fecha.month for r in resultados)
    return _frecuencia_desde_contador(contador, total)


def calcular_frecuencia_sorteos_por_dia_semana(
    resultados: Sequence[TieneMetadatosSorteo],
) -> list[FrecuenciaObservada]:
    """valor = el literal exacto de `dia_semana` tal como lo define
    la entidad de dominio Sorteo ("lunes".."domingo") -se reutiliza
    ese vocabulario en vez de inventar uno nuevo."""
    total = len(resultados)
    contador = Counter(r.dia_semana for r in resultados)
    return _frecuencia_desde_contador(contador, total)


def detectar_huecos_serie_historica(numeros_sorteo: Sequence[int]) -> ReporteHuecos:
    """Compara el rango [min, max] contra los numero_sorteo
    realmente presentes. Deduplica defensivamente (usa un set
    internamente) -no asume que el llamador ya garantizó unicidad,
    aunque la restricción UNIQUE de la base de datos lo asegure en la
    práctica; esta función es pura y debe ser robusta por su cuenta.

    Nota de diseño: existe una duplicación pequeña y deliberada con
    `ValidarIntegridadDatos` (Fase 2) -no se unifica en esta etapa
    para no tocar código de importación ya estable. Queda como
    refactor futuro posible."""
    presentes = set(numeros_sorteo)
    if not presentes:
        return ReporteHuecos(total_esperado=0, total_presente=0, huecos=(), porcentaje_cobertura=0.0)

    minimo, maximo = min(presentes), max(presentes)
    total_esperado = maximo - minimo + 1
    huecos = tuple(n for n in range(minimo, maximo + 1) if n not in presentes)
    total_presente = len(presentes)
    porcentaje_cobertura = (total_presente / total_esperado * 100) if total_esperado else 0.0

    return ReporteHuecos(
        total_esperado=total_esperado,
        total_presente=total_presente,
        huecos=huecos,
        porcentaje_cobertura=porcentaje_cobertura,
    )


def validar_consistencia_temporal(
    resultados: Sequence[TieneMetadatosSorteo],
) -> ReporteConsistenciaTemporal:
    """Recorre `resultados` ordenados por numero_sorteo y verifica
    que `fecha` no retroceda. Reporta CADA violación encontrada (no
    solo la primera), identificando los numero_sorteo involucrados.
    No corrige nada."""
    if len(resultados) < 2:
        return ReporteConsistenciaTemporal(es_consistente=True, problemas=())

    ordenados = sorted(resultados, key=lambda r: r.numero_sorteo)
    problemas: list[str] = []

    for anterior, actual in zip(ordenados, ordenados[1:]):
        if actual.fecha < anterior.fecha:
            problemas.append(
                f"El sorteo {actual.numero_sorteo} ({actual.fecha.isoformat()}) tiene fecha "
                f"anterior al sorteo {anterior.numero_sorteo} ({anterior.fecha.isoformat()})"
            )

    return ReporteConsistenciaTemporal(es_consistente=not problemas, problemas=tuple(problemas))
