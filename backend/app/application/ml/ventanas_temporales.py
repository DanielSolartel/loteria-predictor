"""
Tramos temporales del historico de ML -Etapa AE-43, validada.

Fuente unica de los tramos que ya fijaron etapas validadas:
- DESARROLLO (`2081..2590`): unico historico permitido para
  desarrollo desde AE-37/AE-38.
- CONSUMIDO_AE36 (`2591..2705`): test final de AE-36, ya consumido;
  junto con DESARROLLO forma el contrato congelado de AE-36
  (`2081..2705`).
- HOLDOUT (`>= 2706`): sorteos nuevos, reservados desde AE-39.

Solo depende de la biblioteca estandar: `tipos.py` importa este
modulo, y `incertidumbre.py` (que ya define `PROXIMO_HOLDOUT_INICIO`)
importa `tipos.py`, asi que importarlo desde aqui cerraria un ciclo.
La coincidencia con las constantes de AE-36/37/38/39/40 se verifica
en `tests/unit/ml/test_ventanas_temporales.py`."""
from __future__ import annotations

from enum import Enum

INICIO_HISTORICO_REAL = 2081
FIN_DESARROLLO = 2590
FIN_CONTRATO_AE36 = 2705
"""Solo para clasificar y para la prueba de coherencia con el corte
congelado de AE-36 -AE-43 nunca usa este tramo."""
INICIO_HOLDOUT = 2706

MAXIMO_OBJETIVO_INFERENCIA_AE43 = FIN_DESARROLLO
"""AE-43 solo construye filas de inferencia para objetivos dentro de
DESARROLLO."""
MAXIMO_CORTE_INFERENCIA_AE43 = FIN_DESARROLLO - 1


class TramoTemporalML(Enum):
    """Conjunto CERRADO de tramos -nunca un string libre."""

    ANTERIOR_AL_HISTORICO = "anterior_al_historico"
    DESARROLLO = "desarrollo"
    CONSUMIDO_AE36 = "consumido_ae36"
    HOLDOUT = "holdout"


def clasificar_sorteo(numero_sorteo: int) -> TramoTemporalML:
    """Tramo al que pertenece `numero_sorteo`. Rechaza cualquier
    valor que no sea un `int` (incluido `bool`) -nunca lo convierte."""
    if isinstance(numero_sorteo, bool) or not isinstance(numero_sorteo, int):
        raise ValueError(f"numero_sorteo debe ser int, recibido {numero_sorteo!r}")
    if numero_sorteo < INICIO_HISTORICO_REAL:
        return TramoTemporalML.ANTERIOR_AL_HISTORICO
    if numero_sorteo <= FIN_DESARROLLO:
        return TramoTemporalML.DESARROLLO
    if numero_sorteo <= FIN_CONTRATO_AE36:
        return TramoTemporalML.CONSUMIDO_AE36
    return TramoTemporalML.HOLDOUT
