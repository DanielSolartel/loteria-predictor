"""
Puerto: DisponibilidadHoldoutRepository -Etapa AE-40, validada.

Puerto DEDICADO y minimo, deliberadamente separado de
`ResultadosHistoricosRepository`: nunca carga resultados historicos
completos, nunca trae numeros ganadores, superbalota, colores,
fechas como senal, features ni targets. Su unica responsabilidad es
devolver metadatos agregados de disponibilidad -conteos y numeros de
sorteo- para que AE-40 pueda determinar elegibilidad operativa sin
observar ningun resultado del holdout."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.application.ml.tipos import ResumenDisponibilidadHoldout


class DisponibilidadHoldoutRepository(ABC):
    @abstractmethod
    def obtener_resumen_disponibilidad(
        self, juego_id: UUID, codigo_juego: str, desde_numero_sorteo: int,
    ) -> ResumenDisponibilidadHoldout:
        """Resumen agregado (COUNT, COUNT DISTINCT, MIN, MAX de
        `numero_sorteo`) de los sorteos de `juego_id` con
        `numero_sorteo >= desde_numero_sorteo` -el filtro se aplica
        EN LA CONSULTA SQL, nunca trayendo filas individuales para
        filtrarlas o contarlas despues en Python. Nunca proyecta
        columnas de resultados (numeros, superbalota, color, fecha).
        `codigo_juego` se usa unicamente para etiquetar el resumen
        devuelto -la implementacion no necesita resolverlo por su
        cuenta."""
