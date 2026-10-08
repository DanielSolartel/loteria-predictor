"""
Almacen del laboratorio de modelos (Producto 4), separado de los almacenes
de Productos 1-3 (`DIRECTORIO_LABORATORIO_MODELOS`, ignorado por Git).

    <dir>/experimentos/<JUEGO>/<clave>.json
    <dir>/pronosticos/<JUEGO>/<linea>/<objetivo>-<clave>.json
    <dir>/pronosticos/<JUEGO>/<linea>/<objetivo>-<secuencia>.secuencia
    <dir>/operacion/...  (progreso y cerrojos, con las primitivas de Producto 3)

Informes y pronosticos son INMUTABLES: JSON canonico (AE-52) publicado como
en Producto 3 (temporal en la misma carpeta, `flush` + `fsync`, `os.link`
al nombre final, que falla si ya existe; nunca se sobrescribe). Un lector ve
la ausencia o el JSON completo. Al leer se comprueban bytes canonicos,
sello, huella, clave y ubicacion; si no coinciden, el elemento es
`Ilegible` con su motivo. Temporales y reservas huerfanas nunca se
presentan como experimentos o pronosticos.

ORDEN DE EMISION de los pronosticos: por linea de modelo (modelo, version y
perfil) y objetivo, con una secuencia reservada de forma exclusiva
(`O_EXCL`) y sellada dentro del artefacto (`generacion.secuencia_en_la_linea`).
Nunca por hash, fecha, mtime ni orden de `iterdir()`. Las lineas del
laboratorio no se mezclan con las de Productos 1-3, asi que no cambian cual
es la primera emision que selecciona `/rendimiento`.

Requiere disco local NTFS o POSIX (enlaces duros y creacion exclusiva).
"""
from __future__ import annotations

import os
import re
import secrets
from dataclasses import replace
from pathlib import Path

from app.application.interfaces.laboratorio_store import GuardadoLaboratorio, IlegibleLaboratorio, LaboratorioStore
from app.application.ml import laboratorio_artefactos as la
from app.application.ml.registro_prospectivo import (
    EntradaRegistroInvalidaError,
    RegistroIlegibleError,
    leer_entrada,
    serializar_entrada,
)
from app.infrastructure.storage.pronostico_experimental_file_store import (
    PublicacionNoAdmitidaError,
    _sincronizar_directorio,
)

_JUEGO = re.compile(r"^[A-Z][A-Z_]{1,29}$")
_CLAVE = re.compile(r"^[0-9a-f]{64}$")
_LINEA = re.compile(r"^[a-z0-9_]{1,40}-v[a-z0-9.\-]{1,40}$")
_PRONOSTICO = re.compile(r"^(\d{1,9})-([0-9a-f]{64})\.json$")
_EXPERIMENTO = re.compile(r"^([0-9a-f]{64})\.json$")
_RESERVA = re.compile(r"^(\d{1,9})-(\d{6})\.secuencia$")
_TEMPORAL = re.compile(r"^\..+\.[0-9a-f]{16}\.tmp$")


Guardado = GuardadoLaboratorio
Ilegible = IlegibleLaboratorio


class LaboratorioFileStore(LaboratorioStore):
    def __init__(self, directorio: str | Path):
        self.directorio = Path(directorio)

    # ------------------------------------------------------------------
    # Rutas
    # ------------------------------------------------------------------

    def _experimentos(self, juego: str) -> Path:
        if not _JUEGO.fullmatch(juego):
            raise ValueError(f"juego no admitido: {juego!r}")
        return self.directorio / "experimentos" / juego

    def _linea(self, juego: str, linea: str) -> Path:
        if not _JUEGO.fullmatch(juego) or not _LINEA.fullmatch(linea):
            raise ValueError(f"juego o linea no admitidos: {juego!r}, {linea!r}")
        return self.directorio / "pronosticos" / juego / linea

    # ------------------------------------------------------------------
    # Publicacion atomica sin sobrescritura
    # ------------------------------------------------------------------

    @staticmethod
    def _publicar(carpeta: Path, ruta: Path, contenido: bytes, reserva: Path | None = None) -> None:
        carpeta.mkdir(parents=True, exist_ok=True)
        temporal = carpeta / f".{ruta.name}.{secrets.token_hex(8)}.tmp"
        with open(temporal, "xb") as flujo:
            flujo.write(contenido)
            flujo.flush()
            os.fsync(flujo.fileno())
        try:
            os.link(temporal, ruta)
        except FileExistsError:
            _retirar(temporal, reserva)
            raise
        except OSError as error:
            _retirar(temporal, reserva)
            raise PublicacionNoAdmitidaError(
                f"no se pudo publicar con un enlace duro en {carpeta} ({error}); use un disco local NTFS o POSIX"
            ) from error
        temporal.unlink()
        _sincronizar_directorio(carpeta)

    def temporales(self) -> list[str]:
        """Temporales de escrituras en curso o interrumpidas (no son resultados)."""
        if not self.directorio.is_dir():
            return []
        return sorted(str(p.relative_to(self.directorio)) for p in self.directorio.rglob("*.tmp")
                      if _TEMPORAL.fullmatch(p.name))

    # ------------------------------------------------------------------
    # Experimentos
    # ------------------------------------------------------------------

    def guardar_experimento(self, artefacto: dict) -> Guardado:
        clave = artefacto.get("clave", "")
        if not _CLAVE.fullmatch(clave) or artefacto.get("esquema") != la.ESQUEMA_EXPERIMENTO or not la.integro(artefacto):
            raise ValueError("informe sin clave valida o sin sello coherente")
        carpeta = self._experimentos(artefacto["juego"])
        ruta = carpeta / f"{clave}.json"
        if ruta.exists():
            raise FileExistsError(str(ruta))
        self._publicar(carpeta, ruta, serializar_entrada(artefacto))
        leido = self._leer_experimento(artefacto["juego"], ruta)
        if not isinstance(leido, Guardado):
            raise ValueError("el informe recien guardado no se pudo releer")
        return leido

    def _leer_experimento(self, juego: str, ruta: Path) -> Guardado | Ilegible:
        m = _EXPERIMENTO.fullmatch(ruta.name)
        identificador = m.group(1) if m else ruta.name
        if m is None or ruta.is_symlink() or not ruta.is_file():
            return Ilegible(identificador, juego, "nombre_o_tipo_de_archivo_no_admitido")
        try:
            artefacto = leer_entrada(ruta.read_bytes())
        except (EntradaRegistroInvalidaError, RegistroIlegibleError):
            return Ilegible(identificador, juego, "json_no_canonico")
        if artefacto.get("esquema") != la.ESQUEMA_EXPERIMENTO or not la.integro(artefacto) or \
                artefacto.get("clave") != identificador:
            return Ilegible(identificador, juego, "contenido_alterado")
        if artefacto.get("juego") != juego:
            return Ilegible(identificador, juego, "juego_no_coincide")
        return Guardado(identificador, juego, artefacto)

    def experimentos(self, juego: str) -> list[Guardado | Ilegible]:
        """Del mas reciente al mas antiguo por fecha de terminacion declarada
        (solo para mostrarlos; no define ningun orden de emision)."""
        carpeta = self._experimentos(juego)
        if not carpeta.is_dir():
            return []
        elementos = [self._leer_experimento(juego, r) for r in carpeta.iterdir() if r.suffix == ".json"]
        validos = sorted((e for e in elementos if isinstance(e, Guardado)),
                         key=lambda e: (str(e.artefacto["ejecucion"].get("terminado_en")), e.identificador),
                         reverse=True)
        return [*validos, *sorted((e for e in elementos if isinstance(e, Ilegible)), key=lambda e: e.identificador)]

    def obtener_experimento(self, clave: str) -> Guardado | Ilegible | None:
        if not _CLAVE.fullmatch(clave or ""):
            return None
        raiz = self.directorio / "experimentos"
        if not raiz.is_dir():
            return None
        for carpeta in sorted(raiz.iterdir()):
            ruta = carpeta / f"{clave}.json"
            if _JUEGO.fullmatch(carpeta.name) and ruta.exists():
                return self._leer_experimento(carpeta.name, ruta)
        return None

    # ------------------------------------------------------------------
    # Pronosticos
    # ------------------------------------------------------------------

    def _reservar(self, carpeta: Path, objetivo: int, clave: str, previas: list[Guardado]) -> int:
        carpeta.mkdir(parents=True, exist_ok=True)
        usadas = [int(m.group(2)) for p in carpeta.iterdir()
                  if (m := _RESERVA.fullmatch(p.name)) and int(m.group(1)) == objetivo]
        secuencia = max([0, len(previas), *usadas, *(g.secuencia for g in previas)]) + 1
        while True:
            try:
                descriptor = os.open(carpeta / f"{objetivo}-{secuencia:06d}.secuencia",
                                     os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                secuencia += 1
                continue
            with os.fdopen(descriptor, "w", encoding="ascii") as flujo:
                flujo.write(clave + "\n")
            return secuencia

    def guardar_pronostico(self, artefacto: dict) -> Guardado:
        clave = artefacto.get("clave_de_entrada", "")
        if not _CLAVE.fullmatch(clave) or artefacto.get("esquema") != la.ESQUEMA_PRONOSTICO or not la.integro(artefacto):
            raise ValueError("pronostico sin clave valida o sin sello coherente")
        juego, linea = artefacto["juego"], artefacto["linea"]["id"]
        carpeta = self._linea(juego, linea)
        objetivo = int(artefacto["pronostico"]["objetivo"])
        ruta = carpeta / f"{objetivo}-{clave}.json"
        if ruta.exists():
            raise FileExistsError(str(ruta))
        previas = [e for e in self.pronosticos(juego, linea) if isinstance(e, Guardado) and e.objetivo == objetivo]
        secuencia = self._reservar(carpeta, objetivo, clave, previas)
        anteriores = sorted((g for g in previas if g.secuencia < secuencia), key=lambda g: g.secuencia)
        sellado = la.con_orden(artefacto, secuencia, anteriores[-1].identificador if anteriores else None)
        self._publicar(carpeta, ruta, serializar_entrada(sellado), carpeta / f"{objetivo}-{secuencia:06d}.secuencia")
        leido = self._leer_pronostico(juego, linea, ruta)
        if not isinstance(leido, Guardado):
            raise ValueError("el pronostico recien guardado no se pudo releer")
        return leido

    def _leer_pronostico(self, juego: str, linea: str, ruta: Path) -> Guardado | Ilegible:
        m = _PRONOSTICO.fullmatch(ruta.name)
        identificador = m.group(2) if m else ruta.name
        objetivo = int(m.group(1)) if m else None
        if m is None or ruta.is_symlink() or not ruta.is_file():
            return Ilegible(identificador, juego, "nombre_o_tipo_de_archivo_no_admitido", linea, objetivo)
        try:
            artefacto = leer_entrada(ruta.read_bytes())
        except (EntradaRegistroInvalidaError, RegistroIlegibleError):
            return Ilegible(identificador, juego, "json_no_canonico", linea, objetivo)
        if artefacto.get("esquema") != la.ESQUEMA_PRONOSTICO or not la.integro(artefacto) or \
                artefacto.get("clave_de_entrada") != identificador:
            return Ilegible(identificador, juego, "contenido_alterado", linea, objetivo)
        if artefacto.get("juego") != juego or artefacto.get("linea", {}).get("id") != linea or \
                int(artefacto["pronostico"]["objetivo"]) != objetivo:
            return Ilegible(identificador, juego, "juego_linea_u_objetivo_no_coincide", linea, objetivo)
        guardado = Guardado(identificador, juego, artefacto, linea)
        reserva = ruta.parent / f"{objetivo}-{guardado.secuencia:06d}.secuencia"
        if guardado.secuencia < 1 or (reserva.exists() and
                                      reserva.read_text(encoding="ascii", errors="replace").strip() != identificador):
            return Ilegible(identificador, juego, "secuencia_no_valida_o_reservada_por_otra_clave", linea, objetivo)
        return guardado

    def lineas(self, juego: str) -> list[str]:
        raiz = self.directorio / "pronosticos" / juego
        if not _JUEGO.fullmatch(juego) or not raiz.is_dir():
            return []
        return sorted(p.name for p in raiz.iterdir() if p.is_dir() and _LINEA.fullmatch(p.name))

    def pronosticos(self, juego: str, linea: str) -> list[Guardado | Ilegible]:
        """Pronosticos de una linea: por objetivo descendente y, dentro de cada
        objetivo, por secuencia sellada descendente (version 1 = la primera)."""
        carpeta = self._linea(juego, linea)
        if not carpeta.is_dir():
            return []
        elementos = [self._leer_pronostico(juego, linea, r) for r in carpeta.iterdir() if r.suffix == ".json"]
        validos = [e for e in elementos if isinstance(e, Guardado)]
        salida = []
        for objetivo in sorted({e.objetivo for e in validos}, reverse=True):
            grupo = sorted((e for e in validos if e.objetivo == objetivo), key=lambda e: e.secuencia)
            salida.extend(reversed([replace(e, version=i, versiones=len(grupo)) for i, e in enumerate(grupo, 1)]))
        return [*salida, *sorted((e for e in elementos if isinstance(e, Ilegible)), key=lambda e: e.identificador)]

    def obtener_pronostico(self, clave: str) -> Guardado | Ilegible | None:
        if not _CLAVE.fullmatch(clave or ""):
            return None
        raiz = self.directorio / "pronosticos"
        if not raiz.is_dir():
            return None
        for ruta in sorted(raiz.glob(f"*/*/*-{clave}.json")):
            juego, linea = ruta.parent.parent.name, ruta.parent.name
            if _JUEGO.fullmatch(juego) and _LINEA.fullmatch(linea):
                for e in self.pronosticos(juego, linea):
                    if e.identificador == clave:
                        return e
        return None


def _retirar(*rutas: Path | None) -> None:
    for ruta in rutas:
        if ruta is None:
            continue
        try:
            ruta.unlink()
        except FileNotFoundError:
            pass
