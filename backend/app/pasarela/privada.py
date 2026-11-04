"""Ingreso fiable, identidad por persona y cuotas del perfil PRIVADO de la pasarela (Fase 10, E10.2).

Frontera de confianza (`docs/fase10_consulta_privada.md`):

    navegador --TLS + certificado de cliente--> proxy --HTTP interno--> pasarela --clave--> API

- La persona se autentica en el PROXY con su certificado de cliente (emitido
  por la CA de consulta, separada de las cuentas de la consola de E10.1). El
  proxy descarta toda `X-Consulta-Identidad` / `X-Consulta-Ingreso` del cliente
  y escribe las suyas: la identidad es el CN verificado del certificado.
- La pasarela solo cree esa identidad si el socket es de una IP EXACTA de
  `PASARELA_PROXIES_FIABLES` y si `X-Consulta-Ingreso` coincide (tiempo
  constante) con el secreto del proxy. Cualquier otra cosa: 403, sin reenviar
  nada. `X-Forwarded-For`, `Forwarded`, la IP de la VPN o una IP privada no
  identifican a nadie y no se leen.
- Cuotas en memoria de ESTE proceso (un trabajador por servicio): una cubeta
  por persona y otra agregada, con los costes de la API. Se descuenta solo si
  ambas admiten la consulta: el rechazo de una no consume la otra, A no gasta la
  cuota de B y la suma queda bajo el agregado. Con N trabajadores la cuota
  efectiva seria N x Q (por eso el arranque soportado fija `--workers 1`); un
  reinicio devuelve las cubetas a su capacidad.
- Memoria acotada SIN olvidar deudas (v2, F1023-LIM-01): con `max_personas`
  identidades seguidas, una identidad nueva solo entra si alguna cubeta ya se
  ha RECUPERADO del todo (se descarta la menos reciente de esas, que no debe
  nada). Si todas tienen deuda, la identidad nueva recibe 429
  `limite_identidades_excedido` con el `Retry-After` hasta que la primera se
  recupere; las identidades ya seguidas siguen con su cuota. Expulsar una cubeta
  agotada nunca la devuelve a su capacidad.
- La pasarela no guarda respuestas: no hay cache que mezclar entre personas ni
  que sobreviva a una revocacion (la revocacion la aplica el proxy con su CRL).
"""
from __future__ import annotations

import hmac
import math
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

CABECERA_IDENTIDAD = "x-consulta-identidad"
CABECERA_INGRESO = "x-consulta-ingreso"
_IDENTIDAD = re.compile(r"[a-z0-9][a-z0-9-]{1,62}")

#: Coste en fichas de cada consulta, el mismo que declara la API (`rutas.py`, `guardados.py`); `/salud`, sin
#: clave en la API, cuesta 1 en la pasarela privada (ninguna consulta es gratuita para una persona).
COSTES = {
    "/api/v1/salud": 1,
    "/api/v1/estado": 1,
    "/api/v1/juegos": 1,
    "/api/v1/juegos/{codigo}": 1,
    "/api/v1/juegos/{codigo}/sorteos": 2,
    "/api/v1/juegos/{codigo}/sorteos/{numero_sorteo}": 1,
    "/api/v1/juegos/{codigo}/estadisticas": 1,
    "/api/v1/juegos/{codigo}/estadisticas/resumen": 5,
    "/api/v1/juegos/{codigo}/estadisticas/panel": 5,
    "/api/v1/juegos/{codigo}/estadisticas/{metrica}": 5,
    "/api/v1/juegos/{codigo}/predicciones": 3,
    "/api/v1/juegos/{codigo}/fiabilidad": 3,
    "/api/v1/juegos/{codigo}/modelos-guardados": 2,
    "/api/v1/juegos/{codigo}/modelos-guardados/{clave}": 2,
    "/api/v1/juegos/{codigo}/carteras-guardadas": 2,
    "/api/v1/juegos/{codigo}/carteras-guardadas/{clave}": 2,
    "/api/v1/juegos/{codigo}/resultados": 5,
    "/api/v1/juegos/{codigo}/simulaciones": 2,
    "/api/v1/simulaciones/{identificador}": 2,
}


class IngresoNoFiable(Exception):
    """La solicitud no llega del proxy autenticado; `codigo` es publico."""

    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo, self.mensaje = codigo, mensaje


def identidad_verificada(cliente: str, cabeceras, proxies: frozenset[str], secreto: str) -> str:
    """La identidad que afirma el proxy fiable, o `IngresoNoFiable`. `cabeceras` es la lista cruda (bytes) ASGI."""
    if cliente not in proxies:
        raise IngresoNoFiable("ingreso_no_fiable", "Solo se admite el acceso a través del proxy autenticado")
    ingresos = [v for k, v in cabeceras if k == CABECERA_INGRESO.encode()]
    esperado = secreto.encode("ascii")
    if len(ingresos) != 1 or not hmac.compare_digest(ingresos[0], esperado):
        raise IngresoNoFiable("ingreso_no_fiable", "Solo se admite el acceso a través del proxy autenticado")
    identidades = [v for k, v in cabeceras if k == CABECERA_IDENTIDAD.encode()]
    try:
        identidad = identidades[0].decode("ascii") if len(identidades) == 1 else ""
    except UnicodeDecodeError:
        identidad = ""
    if not _IDENTIDAD.fullmatch(identidad):
        raise IngresoNoFiable("identidad_no_verificada", "El proxy no acreditó una identidad válida")
    return identidad


@dataclass(frozen=True)
class DecisionDeCuota:
    permitida: bool
    alcance: str  # "persona", "agregado" o "capacidad" (el que decide)
    capacidad: int
    restantes: int
    reintentar_en: int


class _Cubeta:
    __slots__ = ("fichas", "instante")

    def __init__(self, fichas: float, instante: float):
        self.fichas, self.instante = fichas, instante


class CuotasDeConsulta:
    """Cubeta por persona + cubeta agregada; descuento atomico de ambas o de ninguna."""

    def __init__(self, fichas_persona: int, fichas_agregadas: int, max_personas: int, *,
                 reloj: Callable[[], float] = time.monotonic):
        if not 0 < fichas_persona <= fichas_agregadas:
            raise ValueError("la cuota agregada no puede ser menor que la de una persona")
        self.capacidad_persona, self.capacidad_agregada = fichas_persona, fichas_agregadas
        self._ritmo_persona, self._ritmo_agregado = fichas_persona / 60.0, fichas_agregadas / 60.0
        self._max, self._reloj = max_personas, reloj
        self._personas: OrderedDict[str, _Cubeta] = OrderedDict()
        self._agregado = _Cubeta(float(fichas_agregadas), reloj())
        self._cerrojo = threading.Lock()
        self.rechazos = {"persona": 0, "agregado": 0, "capacidad": 0}

    @staticmethod
    def _recargar(cubeta: _Cubeta, capacidad: int, ritmo: float, ahora: float) -> None:
        cubeta.fichas = min(float(capacidad), cubeta.fichas + max(0.0, ahora - cubeta.instante) * ritmo)
        cubeta.instante = ahora

    def _fichas_actuales(self, cubeta: _Cubeta, ahora: float) -> float:
        return min(float(self.capacidad_persona),
                   cubeta.fichas + max(0.0, ahora - cubeta.instante) * self._ritmo_persona)

    def _hacer_sitio(self, ahora: float) -> int:
        """0 si hay sitio (descarta, si hace falta, la cubeta recuperada menos reciente); si no, los segundos
        hasta que la primera cubeta con deuda se recupere del todo."""
        if len(self._personas) < self._max:
            return 0
        espera = math.inf
        for nombre, cubeta in self._personas.items():  # de la menos a la mas reciente
            fichas = self._fichas_actuales(cubeta, ahora)
            if fichas >= self.capacidad_persona:
                del self._personas[nombre]
                return 0
            espera = min(espera, (self.capacidad_persona - fichas) / self._ritmo_persona)
        return max(1, math.ceil(espera))

    def consumir(self, persona: str, coste: int) -> DecisionDeCuota:
        with self._cerrojo:
            ahora = self._reloj()
            cubeta = self._personas.pop(persona, None)
            if cubeta is None:
                espera = self._hacer_sitio(ahora)
                if espera:  # todas las identidades seguidas tienen deuda: no se olvida ninguna
                    self.rechazos["capacidad"] += 1
                    return DecisionDeCuota(False, "capacidad", self.capacidad_persona, 0, espera)
                cubeta = _Cubeta(float(self.capacidad_persona), ahora)
            self._personas[persona] = cubeta
            self._recargar(cubeta, self.capacidad_persona, self._ritmo_persona, ahora)
            self._recargar(self._agregado, self.capacidad_agregada, self._ritmo_agregado, ahora)
            if cubeta.fichas < coste:
                self.rechazos["persona"] += 1
                espera = math.ceil((coste - cubeta.fichas) / self._ritmo_persona)
                return DecisionDeCuota(False, "persona", self.capacidad_persona, int(cubeta.fichas), max(1, espera))
            if self._agregado.fichas < coste:
                self.rechazos["agregado"] += 1
                espera = math.ceil((coste - self._agregado.fichas) / self._ritmo_agregado)
                return DecisionDeCuota(False, "agregado", self.capacidad_persona, int(cubeta.fichas), max(1, espera))
            cubeta.fichas -= coste
            self._agregado.fichas -= coste
            return DecisionDeCuota(True, "persona", self.capacidad_persona, int(cubeta.fichas), 0)
