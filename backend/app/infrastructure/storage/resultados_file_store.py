"""
Almacen de informes de Producto 6 (`DIRECTORIO_RESULTADOS_MODELOS`, por
defecto `storage/resultados`, ignorado por Git), separado de los de
Productos 1-5.

    <dir>/informes/<JUEGO>/<clave>.json

Cada informe es JSON canonico (AE-52) inmutable, publicado con la primitiva
de Producto 5 (temporal corto `.publicacion.<16 hex>.tmp` en la misma
carpeta, `flush` + `fsync`, `os.link` al nombre final, que falla si ya
existe): un lector ve la ausencia o el informe completo y nunca se
sobrescribe. La clave es la huella del contenido: repetir el mismo contenido
reutiliza el informe. Al leer se comprueban bytes canonicos, sello, clave y
ubicacion; si no coinciden, el informe es ilegible con su motivo.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.application.interfaces.resultados_store import InformeGuardado, InformeIlegible, ResultadosStore
from app.application.ml import resultados_informes as ri
from app.application.ml.registro_prospectivo import (
    EntradaRegistroInvalidaError,
    RegistroIlegibleError,
    leer_entrada,
    serializar_entrada,
)
from app.infrastructure.storage.carteras_file_store import _publicar

_JUEGO = re.compile(r"^[A-Z][A-Z_]{1,29}$")
_CLAVE = re.compile(r"^[0-9a-f]{64}$")
_INFORME = re.compile(r"^([0-9a-f]{64})\.json$")


class ResultadosFileStore(ResultadosStore):
    def __init__(self, directorio: str | Path):
        self.directorio = Path(directorio)

    def _carpeta(self, juego: str) -> Path:
        if not _JUEGO.fullmatch(juego or ""):
            raise ValueError(f"juego no admitido: {juego!r}")
        return self.directorio / "informes" / juego

    def guardar(self, artefacto: dict) -> InformeGuardado:
        clave = artefacto.get("clave", "")
        if not _CLAVE.fullmatch(clave) or not ri.integro(artefacto):
            raise ValueError("informe sin clave valida o sin sello coherente")
        carpeta = self._carpeta(artefacto["juego"])
        ruta = carpeta / f"{clave}.json"
        if not ruta.exists():
            try:
                _publicar(carpeta, ruta, serializar_entrada(artefacto))
            except FileExistsError:
                pass  # otro escritor publico la misma clave: se reutiliza
        else:
            leido = self._leer(artefacto["juego"], ruta)
            if not isinstance(leido, InformeGuardado):
                raise FileExistsError(f"ya existe un archivo alterado con la clave {clave}: no se sobrescribe")
            return InformeGuardado(leido.clave, leido.juego, leido.artefacto, reutilizado=True)
        leido = self._leer(artefacto["juego"], ruta)
        if not isinstance(leido, InformeGuardado):  # otro escritor dejo un archivo alterado con esa clave
            raise FileExistsError(f"ya existe un archivo alterado con la clave {clave}: no se sobrescribe")
        reutilizado = leido.artefacto.get("guardado") != artefacto.get("guardado")
        return InformeGuardado(leido.clave, leido.juego, leido.artefacto, reutilizado=reutilizado)

    def _leer(self, juego: str, ruta: Path) -> InformeGuardado | InformeIlegible:
        m = _INFORME.fullmatch(ruta.name)
        clave = m.group(1) if m else ruta.name
        if m is None or ruta.is_symlink() or not ruta.is_file():
            return InformeIlegible(clave, juego, "nombre_o_tipo_de_archivo_no_admitido")
        try:
            artefacto = leer_entrada(ruta.read_bytes())
        except (EntradaRegistroInvalidaError, RegistroIlegibleError):
            return InformeIlegible(clave, juego, "json_no_canonico")
        if not ri.integro(artefacto) or artefacto.get("clave") != clave:
            return InformeIlegible(clave, juego, "contenido_alterado")
        if artefacto.get("juego") != juego:
            return InformeIlegible(clave, juego, "juego_no_coincide")
        return InformeGuardado(clave, juego, artefacto)

    def obtener(self, clave: str) -> InformeGuardado | InformeIlegible | None:
        if not _CLAVE.fullmatch(clave or ""):
            return None
        raiz = self.directorio / "informes"
        if not raiz.is_dir():
            return None
        for carpeta in sorted(raiz.iterdir()):
            ruta = carpeta / f"{clave}.json"
            if _JUEGO.fullmatch(carpeta.name) and ruta.exists():
                return self._leer(carpeta.name, ruta)
        return None

    def listar(self, juego: str) -> list[InformeGuardado | InformeIlegible]:
        carpeta = self._carpeta(juego)
        if not carpeta.is_dir():
            return []
        elementos = [self._leer(juego, r) for r in carpeta.iterdir() if r.suffix == ".json"]
        guardados = sorted((e for e in elementos if isinstance(e, InformeGuardado)),
                           key=lambda e: (str(e.artefacto["guardado"].get("guardado_en")), e.clave), reverse=True)
        return [*guardados, *sorted((e for e in elementos if isinstance(e, InformeIlegible)), key=lambda e: e.clave)]
