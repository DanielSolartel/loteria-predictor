"""Referencia de bytes de extremo a extremo -Etapa AE-49, validada.

Historico sintetico determinista (625 sorteos por juego, 2081..2705,
generado por formula) -> repositorios fake -> caso de uso con B=50 ->
`serializar_reporte` -> SHA-256 comparado con una constante fija.
Cubre generador, motor reutilizado, estadisticas exactas, p-valores,
Bonferroni, huellas de entrada, conversion a float (incluida
`math.sqrt`) y serializacion JSON.

La constante se capturo con la primera ejecucion de la
implementacion. Que los bytes coincidan en otras versiones de Python
no se da por supuesto: se verifica ejecutando esta prueba en cada
version disponible (ver README, AE-49). Windows/Python 3.14.6 queda
pendiente de la validacion del operador."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from app.application.use_cases.simular_referencia_azar_uniforme import SimularReferenciaAzarUniforme
from scripts.comparacion_estado_prediccion import serializar_reporte
from tests.unit.simulaciones import sinteticos

ITERACIONES_REFERENCIA = 50
SHA256_REFERENCIA = "99fb194bd0b94719bfbeb84526b2bc346f30b45140833fee4b38552083b2295f"
"""Capturada en el sandbox Linux con Python 3.11.15."""
RAIZ_BACKEND = Path(__file__).resolve().parents[3]


def bytes_de_referencia() -> bytes:
    caso = SimularReferenciaAzarUniforme(
        sinteticos.JuegoRepositoryFake(), sinteticos.ResultadosRepositoryFake(),
        iteraciones=ITERACIONES_REFERENCIA,
    )
    return serializar_reporte(caso.ejecutar("0006"))


def test_bytes_identicos_a_la_referencia():
    contenido = bytes_de_referencia()
    assert hashlib.sha256(contenido).hexdigest() == SHA256_REFERENCIA, (
        f"Python {sys.version.split()[0]}: {hashlib.sha256(contenido).hexdigest()}"
    )


_PROGRAMA = (
    "import hashlib\n"
    "from tests.unit.simulaciones.test_referencia_bytes_ae49 import bytes_de_referencia\n"
    "print(hashlib.sha256(bytes_de_referencia()).hexdigest())\n"
)


def test_independiente_de_pythonhashseed():
    huellas = set()
    for semilla_hash in ("0", "12345"):
        entorno = {**os.environ, "PYTHONPATH": str(RAIZ_BACKEND), "PYTHONHASHSEED": semilla_hash}
        proceso = subprocess.run([sys.executable, "-c", _PROGRAMA], cwd=RAIZ_BACKEND, env=entorno,
                                 capture_output=True, text=True, timeout=300)
        assert proceso.returncode == 0, proceso.stderr
        huellas.add(proceso.stdout.strip())
    assert huellas == {SHA256_REFERENCIA}
