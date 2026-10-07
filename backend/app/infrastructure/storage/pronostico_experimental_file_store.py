"""
Almacen de pronosticos experimentales en archivos JSON canonicos.

Un archivo por clave de entrada en
`<directorio>/<CODIGO_JUEGO>/<objetivo>-<clave_de_entrada>.json`, con la
serializacion canonica de AE-52; nunca se sobrescribe. Al leer se comprueba que los bytes sean canonicos, que el
sello SHA-256 cubra todo el artefacto (incluida la fecha de generacion),
que la huella de reproduccion corresponda al cuerpo y que la clave
coincida con el nombre; si no, el artefacto se informa como alterado.

ORDEN DE EMISION. Cada artefacto lleva, dentro de lo sellado,
`generacion.secuencia_en_el_objetivo` y `generacion.version_anterior`
(clave de la version previa del mismo objetivo). El almacen asigna la
secuencia al guardar y la reserva de forma atomica con un archivo
`<objetivo>-<secuencia>.secuencia` creado en modo exclusivo (`O_EXCL`,
tambien en NTFS) que contiene la clave. Las versiones se numeran por esa
secuencia: nunca por la fecha declarada, el nombre (hash), el orden de
`iterdir()` ni fechas del sistema de archivos. Reconstruir el almacen
desde los JSON (incluso sin las reservas) conserva el orden.

PUBLICACION (issue #83). El contenido completo se escribe primero en un
temporal de la misma carpeta (`.<objetivo>-<clave>.<aleatorio>.tmp`,
creado con `xb`, vaciado con `flush` + `fsync`) y se publica con
`os.link(temporal, final)`: crear un enlace duro es atomico y falla con
`FileExistsError` si el nombre final ya existe, en Linux y en NTFS
(`CreateHardLinkW`). Asi un lector nunca ve un JSON final a medio escribir
y nunca se sobrescribe un destino existente (ni siquiera uno ilegible).
`os.replace` no sirve: sustituye el destino en silencio. Despues se borra
el nombre temporal. Garantias: visibilidad atomica del nombre final y
exclusion entre escritores (hilos o procesos, p. ej. el comando y el
servidor). Frente a un corte de energia solo se promete lo que da el
sistema: el contenido se sincroniza con `fsync` antes de publicar y, en
POSIX, tambien el directorio despues; en Windows no se sincroniza el
directorio. Un proceso interrumpido antes de publicar no deja JSON final:
deja un temporal (ignorado al listar y visible con `temporales()`) y una
reserva de secuencia huerfana. Ninguno se borra automaticamente, porque
podria pertenecer a una escritura activa; volver a generar la misma
entrada publica normalmente. Requiere enlaces duros: disco local NTFS o un
sistema de archivos POSIX (no FAT ni algunas carpetas de red).

Concurrencia local: dos escritores con la misma clave no duplican (el
perdedor recibe `FileExistsError`, borra su temporal y libera su
reserva); dos con claves distintas obtienen secuencias distintas. Si un proceso muere
entre la reserva y la escritura queda una reserva huerfana: la secuencia
tiene un hueco, pero el numero de version (posicion) no cambia. Limites:
requiere un sistema de archivos con creacion exclusiva atomica (disco
local; no se garantiza en carpetas de red), y `version_anterior` refleja
la ultima version ya escrita al reservar.
"""
from __future__ import annotations

import os
import re
import secrets
from dataclasses import replace
from pathlib import Path

from app.application.interfaces.pronostico_experimental_store import (
    PronosticoExperimentalStore,
    PronosticoGuardado,
    PronosticoIlegible,
)
from app.application.ml.pronostico_experimental import artefacto_integro, con_orden_de_emision
from app.application.ml.registro_prospectivo import (
    EntradaRegistroInvalidaError,
    RegistroIlegibleError,
    leer_entrada,
    serializar_entrada,
)

_CODIGO = re.compile(r"^[A-Z][A-Z_]{1,29}$")
_NOMBRE = re.compile(r"^(\d{1,9})-([0-9a-f]{64})\.json$")
_IDENTIFICADOR = re.compile(r"^[0-9a-f]{64}$")
_RESERVA = re.compile(r"^(\d{1,9})-(\d{6})\.secuencia$")
_TEMPORAL = re.compile(r"^\.(\d{1,9})-([0-9a-f]{64})\.[0-9a-f]{16}\.tmp$")


class PublicacionNoAdmitidaError(OSError):
    """El sistema de archivos no admite enlaces duros: no se puede publicar
    sin riesgo de lecturas parciales ni de sobrescritura."""


def _secuencia(guardado: PronosticoGuardado) -> int:
    """Secuencia sellada; 0 para artefactos anteriores a esta columna."""
    valor = guardado.artefacto["generacion"].get("secuencia_en_el_objetivo")
    return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0 else 0


def _orden(guardado: PronosticoGuardado):
    return (_secuencia(guardado), str(guardado.artefacto["generacion"]["generado_en"]), guardado.identificador)


class PronosticoExperimentalFileStore(PronosticoExperimentalStore):
    def __init__(self, directorio: str | Path):
        self._directorio = Path(directorio)

    def _carpeta(self, codigo_juego: str) -> Path:
        if not _CODIGO.fullmatch(codigo_juego):
            raise ValueError(f"codigo de juego no admitido: {codigo_juego!r}")
        return self._directorio / codigo_juego

    @staticmethod
    def _reserva(carpeta: Path, objetivo: int, secuencia: int) -> Path:
        return carpeta / f"{objetivo}-{secuencia:06d}.secuencia"

    def _reservar(self, carpeta: Path, objetivo: int, clave: str, previas: list) -> int:
        """Reserva atomicamente la siguiente secuencia libre del objetivo."""
        usadas = [int(m.group(2)) for p in carpeta.iterdir()
                  if (m := _RESERVA.fullmatch(p.name)) and int(m.group(1)) == objetivo]
        secuencia = max([0, len(previas), *usadas, *(_secuencia(g) for g in previas)]) + 1
        while True:
            try:
                descriptor = os.open(self._reserva(carpeta, objetivo, secuencia), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                secuencia += 1
                continue
            with os.fdopen(descriptor, "w", encoding="ascii") as flujo:
                flujo.write(clave + "\n")
            return secuencia

    def guardar(self, codigo_juego: str, artefacto: dict) -> PronosticoGuardado:
        clave = artefacto["clave_de_entrada"]
        if not _IDENTIFICADOR.fullmatch(clave) or not artefacto_integro(artefacto):
            raise ValueError("artefacto sin clave valida o sin sello coherente")
        carpeta = self._carpeta(codigo_juego)
        carpeta.mkdir(parents=True, exist_ok=True)
        objetivo = int(artefacto["pronostico"]["objetivo"])
        ruta = carpeta / f"{objetivo}-{clave}.json"
        if ruta.exists():
            raise FileExistsError(str(ruta))
        previas = sorted((e for e in self.listar(codigo_juego) if isinstance(e, PronosticoGuardado)
                          and int(e.artefacto["pronostico"]["objetivo"]) == objetivo), key=_orden)
        secuencia = self._reservar(carpeta, objetivo, clave, previas)
        anteriores = [g for g in previas if _secuencia(g) < secuencia]
        sellado = con_orden_de_emision(artefacto, secuencia=secuencia,
                                       version_anterior=anteriores[-1].identificador if anteriores else None)
        self._publicar(carpeta, ruta, objetivo, clave, secuencia, serializar_entrada(sellado))
        guardado = self.obtener(codigo_juego, clave)
        if not isinstance(guardado, PronosticoGuardado):
            raise ValueError("el artefacto recien guardado no se pudo releer")
        return guardado

    def _publicar(self, carpeta: Path, ruta: Path, objetivo: int, clave: str, secuencia: int, contenido: bytes):
        """Escribe en un temporal y lo publica con `os.link` (ver el
        docstring del modulo). Una interrupcion (excepcion no `OSError`, o
        la muerte del proceso) antes del enlace deja el temporal y la
        reserva, y ningun JSON final."""
        temporal = carpeta / f".{objetivo}-{clave}.{secrets.token_hex(8)}.tmp"
        with open(temporal, "xb") as flujo:
            flujo.write(contenido)
            flujo.flush()
            os.fsync(flujo.fileno())
        try:
            os.link(temporal, ruta)
        except FileExistsError:  # otro escritor publico la misma clave: se retira este intento
            self._retirar(temporal, self._reserva(carpeta, objetivo, secuencia))
            raise
        except OSError as error:  # sin enlaces duros no hay publicacion segura
            self._retirar(temporal, self._reserva(carpeta, objetivo, secuencia))
            raise PublicacionNoAdmitidaError(
                f"no se pudo publicar el pronostico con un enlace duro en {carpeta} ({error}); use un disco "
                "local NTFS o un sistema de archivos POSIX") from error
        temporal.unlink()
        _sincronizar_directorio(carpeta)

    @staticmethod
    def _retirar(*rutas: Path) -> None:
        for ruta in rutas:
            try:
                ruta.unlink()
            except FileNotFoundError:
                pass

    def temporales(self, codigo_juego: str) -> list[str]:
        """Temporales de escrituras en curso o interrumpidas antes de
        publicar. No son pronosticos ni errores de integridad, y no se
        borran automaticamente."""
        carpeta = self._carpeta(codigo_juego)
        if not carpeta.is_dir():
            return []
        return sorted(p.name for p in carpeta.iterdir() if _TEMPORAL.fullmatch(p.name))

    def objetivos_de_archivos(self, codigo_juego: str) -> dict[str, int | None]:
        """{identificador: objetivo segun el nombre del archivo} de cada JSON
        de la carpeta, incluidos los ilegibles (None si el nombre no sigue el
        formato). Permite saber a que objetivo pertenece un artefacto
        alterado sin confiar en su contenido."""
        carpeta = self._carpeta(codigo_juego)
        if not carpeta.is_dir():
            return {}
        salida: dict[str, int | None] = {}
        for ruta in carpeta.iterdir():
            if ruta.suffix != ".json":
                continue
            coincidencia = _NOMBRE.fullmatch(ruta.name)
            salida[coincidencia.group(2) if coincidencia else ruta.name] = (
                int(coincidencia.group(1)) if coincidencia else None)
        return salida

    def _leer(self, codigo_juego: str, ruta: Path):
        coincidencia = _NOMBRE.fullmatch(ruta.name)
        identificador = coincidencia.group(2) if coincidencia else ruta.name
        if coincidencia is None or ruta.is_symlink() or not ruta.is_file():
            return PronosticoIlegible(identificador, codigo_juego, "nombre_o_tipo_de_archivo_no_admitido")
        try:
            artefacto = leer_entrada(ruta.read_bytes())
        except (EntradaRegistroInvalidaError, RegistroIlegibleError):
            return PronosticoIlegible(identificador, codigo_juego, "json_no_canonico")
        if not artefacto_integro(artefacto) or artefacto.get("clave_de_entrada") != identificador:
            return PronosticoIlegible(identificador, codigo_juego, "contenido_alterado")
        if artefacto.get("juego") != codigo_juego or str(artefacto["pronostico"]["objetivo"]) != coincidencia.group(1):
            return PronosticoIlegible(identificador, codigo_juego, "juego_u_objetivo_no_coincide")
        guardado = PronosticoGuardado(identificador, codigo_juego, artefacto)
        secuencia = _secuencia(guardado)
        if secuencia:
            reserva = self._reserva(ruta.parent, int(coincidencia.group(1)), secuencia)
            if reserva.exists() and reserva.read_text(encoding="ascii", errors="replace").strip() != identificador:
                return PronosticoIlegible(identificador, codigo_juego, "secuencia_reservada_por_otra_clave")
        return guardado

    def listar(self, codigo_juego: str) -> list[PronosticoGuardado | PronosticoIlegible]:
        carpeta = self._carpeta(codigo_juego)
        if not carpeta.is_dir():
            return []
        elementos = [self._leer(codigo_juego, ruta) for ruta in carpeta.iterdir() if ruta.suffix == ".json"]
        validos = [e for e in elementos if isinstance(e, PronosticoGuardado)]
        ilegibles = sorted((e for e in elementos if isinstance(e, PronosticoIlegible)), key=lambda e: e.identificador)
        por_objetivo: dict[int, list[PronosticoGuardado]] = {}
        for e in validos:
            por_objetivo.setdefault(int(e.artefacto["pronostico"]["objetivo"]), []).append(e)
        salida = []
        for objetivo in sorted(por_objetivo, reverse=True):
            cronologico = sorted(por_objetivo[objetivo], key=_orden)
            total = len(cronologico)
            numerados = [replace(e, version=i, versiones=total) for i, e in enumerate(cronologico, start=1)]
            salida.extend(reversed(numerados))
        return [*salida, *ilegibles]

    def obtener(self, codigo_juego: str, identificador: str):
        if not _IDENTIFICADOR.fullmatch(identificador):
            return None
        carpeta = self._carpeta(codigo_juego)
        if not carpeta.is_dir() or not any(carpeta.glob(f"*-{identificador}.json")):
            return None
        for elemento in self.listar(codigo_juego):
            if elemento.identificador == identificador:
                return elemento
        return None


def _sincronizar_directorio(carpeta: Path) -> None:
    """En POSIX, `fsync` del directorio para que la entrada publicada
    sobreviva a un corte de energia; en Windows no hay equivalente
    portable y no se intenta."""
    if os.name != "posix":
        return
    descriptor = os.open(carpeta, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
