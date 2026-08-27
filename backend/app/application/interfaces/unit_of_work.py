"""
Puerto: UnitOfWork.

Existe por una razón muy concreta, detectada en la auditoría final
de Fase 2: `get_db()` confirma (commit) UNA vez, al final de todo el
request. Eso es correcto y suficiente para el 95% de los casos de
uso (una escritura por request), pero es peligroso para
`SincronizarSorteos` y `ReprocesarSorteosDesdeHtml`, que pueden
registrar decenas o cientos de sorteos dentro de UN SOLO request
HTTP. Sin este mecanismo, si el proceso fallaba después de importar
90 de 100 sorteos, el `rollback()` automático de `get_db()` habría
deshecho los 90 -contradiciendo la garantía de "cada sorteo se
persiste individualmente" que se documentó (incorrectamente, hasta
este fix) en `docs/resiliencia_sincronizacion.md`.

`confirmar()` hace un commit intermedio explícito, para que el
progreso ya escrito sobreviva aunque algo posterior en el mismo
request falle. Se modela como puerto (no como un import directo de
`sqlalchemy.orm.Session`) para no romper la regla de que
`application/` nunca depende de `infrastructure/`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class UnitOfWork(ABC):
    @abstractmethod
    def confirmar(self) -> None:
        """Confirma (commit) el trabajo realizado hasta este punto.
        Después de llamar a esto, un rollback posterior (p.ej. por una
        excepción no capturada más adelante en el mismo request) ya
        no puede deshacer lo confirmado aquí."""
