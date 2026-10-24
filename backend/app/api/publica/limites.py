"""Limite de uso: cubeta de fichas por identidad, en memoria de ESTE proceso.

No es un limite global entre trabajadores: con N procesos de Uvicorn cada uno
lleva su propia cuenta (hasta N veces la cuota). Para un limite global hace
falta un unico proceso o un limite en el proxy. El estado se pierde al
reiniciar y nunca se escribe en disco ni en la base.

El numero de identidades es acotado: al superar `max_identidades` se descarta
la menos reciente (sus fichas vuelven a la capacidad si reaparece), de modo
que ni las claves inventadas ni muchos clientes hacen crecer la memoria."""
from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    permitida: bool
    restantes: int
    reintentar_en: int  # segundos, >= 1 si se rechaza


class LimitadorDeCuota:
    def __init__(self, fichas_por_minuto: int, max_identidades: int, *,
                 reloj: Callable[[], float] = time.monotonic):
        self.capacidad = fichas_por_minuto
        self._ritmo = fichas_por_minuto / 60.0
        self._max = max_identidades
        self._reloj = reloj
        self._cubetas: OrderedDict[str, tuple[float, float]] = OrderedDict()
        self._cerrojo = threading.Lock()
        self.rechazos = 0
        self.descartes = 0

    def consumir(self, identidad: str, coste: int = 1) -> Decision:
        with self._cerrojo:
            ahora = self._reloj()
            fichas, antes = self._cubetas.pop(identidad, (float(self.capacidad), ahora))
            fichas = min(float(self.capacidad), fichas + max(0.0, ahora - antes) * self._ritmo)
            permitida = fichas >= coste
            if permitida:
                fichas -= coste
            else:
                self.rechazos += 1
            self._cubetas[identidad] = (fichas, ahora)
            while len(self._cubetas) > self._max:
                self._cubetas.popitem(last=False)
                self.descartes += 1
            espera = 0 if permitida else max(1, math.ceil((coste - fichas) / self._ritmo))
            return Decision(permitida, int(fichas), espera)

    @property
    def identidades(self) -> int:
        with self._cerrojo:
            return len(self._cubetas)
