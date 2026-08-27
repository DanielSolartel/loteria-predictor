"""
Mapeo puro ORM -> DTO para ResultadosHistoricosRepository.

Extraído de `resultados_historicos_repository_sqlalchemy.py` a su
propio archivo por una razón concreta: este sandbox no tiene
`sqlalchemy` instalado (ni siquiera para importar, sin acceso a red
para instalarlo) -si estas dos funciones vivieran en el mismo módulo
que la clase repositorio (que sí importa `sqlalchemy`), sería
imposible probarlas de forma aislada sin esa dependencia presente.
Separarlas permite testear el código de PRODUCCIÓN real, no una
copia -las funciones aquí son exactamente las que usa
`ResultadosHistoricosRepositorySQLAlchemy` internamente.

No dependen de ningún tipo concreto de ORM -aceptan cualquier objeto
con los atributos esperados (`numero_sorteo`, `fecha`, `dia_semana`,
`numeros`, `superbalota`, `colores_numeros`, cada uno con la forma
correspondiente) -esto es lo que permite probarlas con objetos
simulados (dataclasses simples) sin necesitar SQLAlchemy en absoluto,
tanto en producción como en los tests.
"""
from __future__ import annotations

from typing import Any

from app.application.estadisticas.tipos import ResultadoColorLoto, ResultadoNumerico


def a_resultado_numerico(orm: Any) -> ResultadoNumerico:
    """`orm` debe tener: numero_sorteo, fecha, dia_semana,
    numeros (iterable de objetos con .numero y .posicion),
    superbalota (objeto con .numero, o None)."""
    numeros = tuple(sn.numero for sn in sorted(orm.numeros, key=lambda x: x.posicion))
    superbalota = orm.superbalota.numero if orm.superbalota is not None else None
    return ResultadoNumerico(
        numero_sorteo=orm.numero_sorteo, fecha=orm.fecha, dia_semana=orm.dia_semana,
        numeros=numeros, superbalota=superbalota,
    )


def a_resultado_colorloto(orm: Any) -> ResultadoColorLoto:
    """`orm` debe tener: numero_sorteo, fecha, dia_semana,
    colores_numeros (iterable de objetos con .numero, .posicion,
    .color.codigo)."""
    pares = tuple(
        (scn.numero, scn.color.codigo)
        for scn in sorted(orm.colores_numeros, key=lambda x: x.posicion)
    )
    return ResultadoColorLoto(
        numero_sorteo=orm.numero_sorteo, fecha=orm.fecha, dia_semana=orm.dia_semana, pares=pares,
    )
