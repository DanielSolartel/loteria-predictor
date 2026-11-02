"""Credenciales de la consola local (Fase 10, E10.1): hash adaptativo de contraseñas.

Se usa scrypt (RFC 7914) de la biblioteca estándar (`hashlib.scrypt`, respaldado por OpenSSL), con
sal aleatoria de 16 bytes por contraseña (`secrets.token_bytes`), N = 2**17, r = 8, p = 1 y clave de
32 bytes. Son los parámetros mínimos que recomienda para scrypt la guía OWASP de almacenamiento de
contraseñas; la decisión y sus fuentes constan en `docs/fase10_e101_seguridad_consola.md`. No se
implementa criptografía propia: solo se codifican los parámetros junto al resultado.

Formato almacenado (sin secretos en claro):

    scrypt$1$<n>$<r>$<p>$<sal base64>$<derivada base64>

La verificación usa los parámetros guardados y compara en tiempo constante. Un almacén puede exigir
unos parámetros mínimos: un hash por debajo de ellos no se acepta.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

ALGORITMO = "scrypt"
VERSION = "1"
LONGITUD_SAL = 16
LONGITUD_CLAVE = 32
LONGITUD_MINIMA = 12
LONGITUD_MAXIMA = 1024  # acota el trabajo de una entrada hostil


@dataclass(frozen=True)
class ParametrosScrypt:
    n: int = 2 ** 17
    r: int = 8
    p: int = 1

    @property
    def memoria(self) -> int:
        """Memoria que necesita la derivación (128·N·r), con margen para `maxmem`."""
        return 128 * self.n * self.r * (self.p + 1) + 1024 * 1024

    def cumple(self, minimos: "ParametrosScrypt") -> bool:
        return self.n >= minimos.n and self.r >= minimos.r and self.p >= minimos.p


PRODUCCION = ParametrosScrypt()


class ContrasenaNoValida(ValueError):
    """La contraseña propuesta no cumple la política; el mensaje no la incluye."""


def validar_contrasena(contrasena: str) -> None:
    if not isinstance(contrasena, str):
        raise ContrasenaNoValida("La contraseña debe ser texto.")
    if len(contrasena) < LONGITUD_MINIMA:
        raise ContrasenaNoValida(f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres.")
    if len(contrasena) > LONGITUD_MAXIMA:
        raise ContrasenaNoValida(f"La contraseña no puede superar {LONGITUD_MAXIMA} caracteres.")
    if not contrasena.strip():
        raise ContrasenaNoValida("La contraseña no puede estar formada solo por espacios.")
    if any(ord(c) < 32 for c in contrasena):
        raise ContrasenaNoValida("La contraseña no puede contener caracteres de control.")


def _derivar(contrasena: str, sal: bytes, parametros: ParametrosScrypt) -> bytes:
    return hashlib.scrypt(contrasena.encode("utf-8"), salt=sal, n=parametros.n, r=parametros.r, p=parametros.p,
                          maxmem=parametros.memoria, dklen=LONGITUD_CLAVE)


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def crear_hash(contrasena: str, parametros: ParametrosScrypt = PRODUCCION) -> str:
    validar_contrasena(contrasena)
    sal = secrets.token_bytes(LONGITUD_SAL)
    derivada = _derivar(contrasena, sal, parametros)
    return "$".join((ALGORITMO, VERSION, str(parametros.n), str(parametros.r), str(parametros.p), _b64(sal), _b64(derivada)))


def leer_parametros(codificado: str) -> ParametrosScrypt | None:
    try:
        algoritmo, version, n, r, p, _sal, _derivada = codificado.split("$")
        if algoritmo != ALGORITMO or version != VERSION:
            return None
        parametros = ParametrosScrypt(int(n), int(r), int(p))
    except (ValueError, AttributeError):
        return None
    if parametros.n < 2 or parametros.n & (parametros.n - 1) or parametros.r < 1 or parametros.p < 1:
        return None
    return parametros


def verificar(contrasena: str, codificado: str, minimos: ParametrosScrypt = PRODUCCION) -> bool:
    """True si la contraseña corresponde al hash. Cualquier formato no válido devuelve False."""
    if not isinstance(contrasena, str) or not isinstance(codificado, str) or len(contrasena) > LONGITUD_MAXIMA:
        return False
    parametros = leer_parametros(codificado)
    if parametros is None or not parametros.cumple(minimos):
        return False
    try:
        sal = base64.b64decode(codificado.split("$")[5], validate=True)
        esperado = base64.b64decode(codificado.split("$")[6], validate=True)
        obtenido = _derivar(contrasena, sal, parametros)
    except (ValueError, MemoryError):
        return False
    return hmac.compare_digest(obtenido, esperado)


def hash_ficticio(parametros: ParametrosScrypt = PRODUCCION) -> str:
    """Hash de una contraseña aleatoria con los mismos parámetros: iguala el coste de verificar un usuario
    inexistente al de uno existente, sin revelar cuál es el caso."""
    return crear_hash(secrets.token_urlsafe(24), parametros)
