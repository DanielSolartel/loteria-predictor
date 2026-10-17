"""
Almacen de explicaciones de la Fase 4 (`DIRECTORIO_PREDICCIONES_MODELOS`, por
defecto `storage/predicciones`, ignorado por Git), separado de los de
Productos 1-6.

    <dir>/explicaciones/<JUEGO>/<cartera 16 hex>-<clave 64 hex>.json

Cada explicacion es JSON canonico (AE-52) inmutable, publicado con el
publicador compartido de Productos 4-6 (temporal corto
`.publicacion.<16 hex>.tmp` en la misma carpeta, `flush` + `fsync` y enlace
duro que falla si el destino existe): un lector ve la ausencia o el archivo
completo y nunca se sobrescribe. La clave es la huella del contenido: la
misma entrada reutiliza la explicacion. El prefijo de 16 caracteres de la
cartera permite listar las explicaciones de una cartera sin leer todo el
almacen. Ruta mas larga: carpeta del almacen + 117 caracteres (con
BALOTO_REVANCHA); el temporal (33 caracteres) es mas corto que el destino.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.application.interfaces.predicciones_store import (
    ExplicacionGuardada,
    ExplicacionIlegible,
    PrediccionesStore,
)
from app.application.ml import predicciones_explicacion as pe
from app.application.ml.registro_prospectivo import (
    EntradaRegistroInvalidaError,
    RegistroIlegibleError,
    leer_entrada,
    serializar_entrada,
)
from app.infrastructure.storage.laboratorio_file_store import _publicar, _es_temporal

_JUEGO = re.compile(r"^[A-Z][A-Z_]{1,29}$")
_CLAVE = re.compile(r"^[0-9a-f]{64}$")
_ARCHIVO = re.compile(r"^([0-9a-f]{16})-([0-9a-f]{64})\.json$")


class PrediccionesFileStore(PrediccionesStore):
    def __init__(self, directorio: str | Path):
        self.directorio = Path(directorio)

    def _carpeta(self, juego: str) -> Path:
        if not _JUEGO.fullmatch(juego or ""):
            raise ValueError(f"juego no admitido: {juego!r}")
        return self.directorio / "explicaciones" / juego

    @staticmethod
    def _nombre(cartera: str, clave: str) -> str:
        return f"{cartera[:16]}-{clave}.json"

    def guardar(self, artefacto: dict) -> ExplicacionGuardada:
        clave = artefacto.get("clave", "")
        cartera = (artefacto.get("cartera") or {}).get("clave", "")
        if not _CLAVE.fullmatch(clave) or not _CLAVE.fullmatch(cartera) or not pe.integro(artefacto):
            raise ValueError("explicacion sin clave valida o sin sello coherente")
        carpeta = self._carpeta(artefacto["juego"])
        ruta = carpeta / self._nombre(cartera, clave)
        if ruta.exists():
            leido = self._leer(artefacto["juego"], ruta)
            if not isinstance(leido, ExplicacionGuardada):
                raise FileExistsError(f"ya existe un archivo alterado con la clave {clave}: no se sobrescribe")
            return ExplicacionGuardada(leido.clave, leido.juego, leido.artefacto, reutilizado=True)
        try:
            _publicar(carpeta, ruta, serializar_entrada(artefacto))
        except FileExistsError:  # otro escritor publico la misma clave: se reutiliza
            leido = self._leer(artefacto["juego"], ruta)
            if not isinstance(leido, ExplicacionGuardada):
                raise FileExistsError(f"ya existe un archivo alterado con la clave {clave}: no se sobrescribe")
            return ExplicacionGuardada(leido.clave, leido.juego, leido.artefacto, reutilizado=True)
        leido = self._leer(artefacto["juego"], ruta)
        if not isinstance(leido, ExplicacionGuardada):
            raise FileExistsError(f"el archivo publicado con la clave {clave} no supera la comprobacion")
        return leido

    def _leer(self, juego: str, ruta: Path) -> ExplicacionGuardada | ExplicacionIlegible:
        m = _ARCHIVO.fullmatch(ruta.name)
        clave = m.group(2) if m else ruta.name
        if m is None or ruta.is_symlink() or not ruta.is_file():
            return ExplicacionIlegible(clave, juego, "nombre_o_tipo_de_archivo_no_admitido")
        try:
            artefacto = leer_entrada(ruta.read_bytes())
        except (EntradaRegistroInvalidaError, RegistroIlegibleError, OSError):
            return ExplicacionIlegible(clave, juego, "json_no_canonico")
        if not pe.integro(artefacto) or artefacto.get("clave") != clave:
            return ExplicacionIlegible(clave, juego, "contenido_alterado")
        if artefacto.get("juego") != juego:
            return ExplicacionIlegible(clave, juego, "juego_no_coincide")
        if (artefacto.get("cartera") or {}).get("clave", "")[:16] != m.group(1):
            return ExplicacionIlegible(clave, juego, "cartera_no_coincide")
        return ExplicacionGuardada(clave, juego, artefacto)

    def obtener(self, clave: str) -> ExplicacionGuardada | ExplicacionIlegible | None:
        if not _CLAVE.fullmatch(clave or ""):
            return None
        raiz = self.directorio / "explicaciones"
        if not raiz.is_dir():
            return None
        for ruta in sorted(raiz.glob(f"*/*-{clave}.json")):
            if _JUEGO.fullmatch(ruta.parent.name):
                return self._leer(ruta.parent.name, ruta)
        return None

    def de_cartera(self, juego: str, cartera: str) -> list[ExplicacionGuardada | ExplicacionIlegible]:
        if not _CLAVE.fullmatch(cartera or ""):
            return []
        carpeta = self._carpeta(juego)
        if not carpeta.is_dir():
            return []
        elementos = [self._leer(juego, r) for r in sorted(carpeta.glob(f"{cartera[:16]}-*.json"))]
        return [e for e in elementos if not isinstance(e, ExplicacionGuardada) or e.cartera == cartera]

    def listar(self, juego: str) -> list[ExplicacionGuardada | ExplicacionIlegible]:
        carpeta = self._carpeta(juego)
        if not carpeta.is_dir():
            return []
        return [self._leer(juego, r) for r in sorted(carpeta.iterdir())
                if r.suffix == ".json" and not _es_temporal(r.name)]

    def temporales(self) -> list[str]:
        """Temporales de publicaciones en curso o interrumpidas (nunca se borran solos)."""
        raiz = self.directorio / "explicaciones"
        if not raiz.is_dir():
            return []
        return sorted(str(r.relative_to(self.directorio)) for r in raiz.glob("*/*") if _es_temporal(r.name))
