"""Autenticidad de las generaciones: firma Ed25519 del manifiesto canonico (biblioteca `cryptography`, ya en
los locks). La clave PRIVADA queda en el equipo que captura (fuera de Git y de los datos publicables, permisos
0600); el servidor solo tiene la PUBLICA. Custodia, copia y rotacion de la clave dependen de D6/D8 (pendientes):
aqui solo se generan, cargan y usan archivos locales."""
from __future__ import annotations

import os
from pathlib import Path

from app.infrastructure.generaciones.formato import GeneracionNoValida, sha256_bytes


def generar(privada: Path, publica: Path) -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if privada.exists() or publica.exists():
        raise FileExistsError("las claves ya existen: no se sobrescriben")
    clave = Ed25519PrivateKey.generate()
    pem = clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                              serialization.NoEncryption())
    privada.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(privada, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as f:
        f.write(pem)
    crudo = clave.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    publica.parent.mkdir(parents=True, exist_ok=True)
    with open(publica, "x", encoding="ascii") as f:
        f.write(crudo.hex() + "\n")
    return identificador(crudo)


def identificador(publica_cruda: bytes) -> str:
    return sha256_bytes(publica_cruda)[:16]


def cargar_privada(ruta: Path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if os.name == "posix" and os.stat(ruta).st_mode & 0o077:
        raise GeneracionNoValida("la clave privada de firma no debe ser legible por otros (permisos 0600)")
    clave = serialization.load_pem_private_key(ruta.read_bytes(), password=None)
    if not isinstance(clave, Ed25519PrivateKey):
        raise GeneracionNoValida("la clave de firma no es Ed25519")
    return clave


def cargar_publica(ruta: Path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        crudo = bytes.fromhex(ruta.read_text(encoding="ascii").strip())
        return Ed25519PublicKey.from_public_bytes(crudo), identificador(crudo)
    except (ValueError, OSError) as error:
        raise GeneracionNoValida("clave publica de firma no valida") from error


def id_de_privada(clave) -> str:
    from cryptography.hazmat.primitives import serialization

    return identificador(clave.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def firmar(clave, datos: bytes) -> str:
    return clave.sign(datos).hex()


def verificar(publica, datos: bytes, firma_hex: str) -> None:
    from cryptography.exceptions import InvalidSignature

    try:
        publica.verify(bytes.fromhex(firma_hex.strip()), datos)
    except (InvalidSignature, ValueError) as error:
        raise GeneracionNoValida("firma del manifiesto no valida") from error
