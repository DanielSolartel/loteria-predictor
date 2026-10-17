"""Contratos de parámetros compartidos por las interfaces HTTP.

El corte opcional sigue el contrato de las pantallas de Producto 1:
solo la cadena vacía del formulario representa ausencia de límite.
"""
from typing import Annotated

from fastapi import Query
from pydantic import BeforeValidator, Field


def _vacio_a_none(valor):
    return None if valor == "" else valor


CorteOpcional = Annotated[
    Annotated[int, Field(ge=1)] | None, BeforeValidator(_vacio_a_none), Query()
]
