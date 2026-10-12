"""
Almacen de Producto 5 (`DIRECTORIO_CARTERAS_MODELOS`, por defecto
`storage/carteras`, ignorado por Git), separado de los de Productos 1-4.

    <dir>/comparaciones/<JUEGO>/<clave>.json
    <dir>/carteras/<JUEGO>/<linea>/<objetivo>-<clave>.json
    <dir>/carteras/<JUEGO>/<linea>/<objetivo>-<secuencia>.secuencia
    <dir>/simulaciones/<JUEGO>/<clave>.json
    <dir>/configuraciones/<JUEGO>/<version>.json
    <dir>/operacion/...  (progreso y cerrojos, primitivas de Producto 3)

Publicacion atomica sin sobrescritura como en Producto 4 (temporal en la
misma carpeta, `flush` + `fsync`, `os.link` al nombre final, que falla si ya
existe) y reserva exclusiva (`O_EXCL`) de la secuencia de emision de Producto
4, sellada dentro del artefacto (`generacion.secuencia_en_la_linea`). El
temporal tiene un nombre corto de longitud constante,
`.publicacion.<16 hex>.tmp`: el anterior (`.<nombre final>.<16 hex>.tmp`)
anade 22 caracteres al nombre final y, en Windows sin rutas largas, no se
podia crear aunque el destino cupiera. Desde la correccion de rutas de la
Fase 3, este publicador vive en `laboratorio_file_store` y lo comparten
Productos 4 a 6. Un lector ve la
ausencia o el JSON completo. Al leer se comprueban bytes canonicos, sello,
huella, clave y ubicacion; si no coinciden, el elemento es `Ilegible` con su
motivo. Temporales (con el nombre anterior o el nuevo) y reservas huerfanas
nunca se presentan como resultados.

Las configuraciones son versiones numeradas (000001, 000002, ...): cada
version es un archivo inmutable publicado con el mismo mecanismo; si dos
escritores compiten por un numero, el segundo toma el siguiente.

Requiere disco local NTFS o POSIX (enlaces duros y creacion exclusiva).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from app.application.interfaces.carteras_store import CarterasStore, GuardadoCarteras, IlegibleCarteras
from app.application.ml import carteras_artefactos as ca
from app.application.ml.registro_prospectivo import (
    EntradaRegistroInvalidaError,
    RegistroIlegibleError,
    leer_entrada,
    serializar_entrada,
)
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore, _publicar

_JUEGO = re.compile(r"^[A-Z][A-Z_]{1,29}$")
_CLAVE = re.compile(r"^[0-9a-f]{64}$")
_LINEA = re.compile(r"^[a-z0-9_]{1,40}-v[a-z0-9.\-]{1,40}-n\d{1,2}-(libre|limitada)-s\d{1,10}(-reducido)?$")
_CARTERA = re.compile(r"^(\d{1,9})-([0-9a-f]{64})\.json$")
_SIMPLE = re.compile(r"^([0-9a-f]{64})\.json$")
_CONFIGURACION = re.compile(r"^(\d{6})\.json$")
_TEMPORAL = re.compile(r"^\..+\.[0-9a-f]{16}\.tmp$")  # `.publicacion.<16 hex>.tmp` y el nombre de Producto 4

Guardado = GuardadoCarteras
Ilegible = IlegibleCarteras


_ESQUEMAS = {"comparacion": ca.ESQUEMA_COMPARACION, "simulacion": ca.ESQUEMA_SIMULACION}
_CARPETAS = {"comparacion": "comparaciones", "simulacion": "simulaciones"}


class CarterasFileStore(CarterasStore):
    def __init__(self, directorio: str | Path):
        self.directorio = Path(directorio)

    def temporales(self) -> list[str]:
        if not self.directorio.is_dir():
            return []
        return sorted(str(p.relative_to(self.directorio)) for p in self.directorio.rglob("*.tmp")
                      if _TEMPORAL.fullmatch(p.name))

    def _carpeta(self, tipo: str, juego: str) -> Path:
        if not _JUEGO.fullmatch(juego):
            raise ValueError(f"juego no admitido: {juego!r}")
        return self.directorio / _CARPETAS[tipo] / juego

    # ------------------------------------------------------------------
    # Comparaciones y simulaciones (un archivo por clave)
    # ------------------------------------------------------------------

    def _guardar_simple(self, tipo: str, artefacto: dict) -> Guardado:
        clave = artefacto.get("clave", "")
        if not _CLAVE.fullmatch(clave) or artefacto.get("esquema") != _ESQUEMAS[tipo] or not ca.integro(artefacto):
            raise ValueError(f"{tipo} sin clave valida o sin sello coherente")
        carpeta = self._carpeta(tipo, artefacto["juego"])
        ruta = carpeta / f"{clave}.json"
        if ruta.exists():
            raise FileExistsError(str(ruta))
        _publicar(carpeta, ruta, serializar_entrada(artefacto))
        leido = self._leer_simple(tipo, artefacto["juego"], ruta)
        if not isinstance(leido, Guardado):
            raise ValueError(f"{tipo} recien guardada no se pudo releer")
        return leido

    def _leer_simple(self, tipo: str, juego: str, ruta: Path) -> Guardado | Ilegible:
        m = _SIMPLE.fullmatch(ruta.name)
        identificador = m.group(1) if m else ruta.name
        if m is None or ruta.is_symlink() or not ruta.is_file():
            return Ilegible(identificador, juego, tipo, "nombre_o_tipo_de_archivo_no_admitido")
        try:
            artefacto = leer_entrada(ruta.read_bytes())
        except (EntradaRegistroInvalidaError, RegistroIlegibleError):
            return Ilegible(identificador, juego, tipo, "json_no_canonico")
        if artefacto.get("esquema") != _ESQUEMAS[tipo] or not ca.integro(artefacto) or \
                artefacto.get("clave") != identificador:
            return Ilegible(identificador, juego, tipo, "contenido_alterado")
        if artefacto.get("juego") != juego:
            return Ilegible(identificador, juego, tipo, "juego_no_coincide")
        return Guardado(identificador, juego, tipo, artefacto)

    def _listar_simple(self, tipo: str, juego: str, volatil: str) -> list[Guardado | Ilegible]:
        carpeta = self._carpeta(tipo, juego)
        if not carpeta.is_dir():
            return []
        elementos = [self._leer_simple(tipo, juego, r) for r in carpeta.iterdir() if r.suffix == ".json"]
        validos = sorted((e for e in elementos if isinstance(e, Guardado)),
                         key=lambda e: (str(e.artefacto[volatil].get("terminado_en")), e.identificador), reverse=True)
        return [*validos, *sorted((e for e in elementos if isinstance(e, Ilegible)), key=lambda e: e.identificador)]

    def _obtener_simple(self, tipo: str, clave: str) -> Guardado | Ilegible | None:
        if not _CLAVE.fullmatch(clave or ""):
            return None
        raiz = self.directorio / _CARPETAS[tipo]
        if not raiz.is_dir():
            return None
        for carpeta in sorted(raiz.iterdir()):
            ruta = carpeta / f"{clave}.json"
            if _JUEGO.fullmatch(carpeta.name) and ruta.exists():
                return self._leer_simple(tipo, carpeta.name, ruta)
        return None

    def guardar_comparacion(self, artefacto: dict) -> Guardado:
        return self._guardar_simple("comparacion", artefacto)

    def obtener_comparacion(self, clave: str) -> Guardado | Ilegible | None:
        return self._obtener_simple("comparacion", clave)

    def comparaciones(self, juego: str) -> list:
        """Mas reciente primero por fecha declarada (solo para mostrar)."""
        return self._listar_simple("comparacion", juego, "ejecucion")

    def guardar_simulacion(self, artefacto: dict) -> Guardado:
        return self._guardar_simple("simulacion", artefacto)

    def obtener_simulacion(self, clave: str) -> Guardado | Ilegible | None:
        return self._obtener_simple("simulacion", clave)

    def simulaciones(self, juego: str) -> list:
        return self._listar_simple("simulacion", juego, "ejecucion")

    # ------------------------------------------------------------------
    # Carteras (orden de emision sellado por linea y objetivo)
    # ------------------------------------------------------------------

    def _linea(self, juego: str, linea: str) -> Path:
        if not _JUEGO.fullmatch(juego) or not _LINEA.fullmatch(linea):
            raise ValueError(f"juego o linea no admitidos: {juego!r}, {linea!r}")
        return self.directorio / "carteras" / juego / linea

    def guardar_cartera(self, artefacto: dict) -> Guardado:
        clave = artefacto.get("clave_de_entrada", "")
        if not _CLAVE.fullmatch(clave) or artefacto.get("esquema") != ca.ESQUEMA_CARTERA or not ca.integro(artefacto):
            raise ValueError("cartera sin clave valida o sin sello coherente")
        if artefacto["cartera"].get("estado") != "completa":
            raise ValueError("una cartera parcial no se publica como completa")
        juego, linea = artefacto["juego"], artefacto["linea"]["id"]
        carpeta = self._linea(juego, linea)
        objetivo = int(artefacto["cartera"]["objetivo"])
        ruta = carpeta / f"{objetivo}-{clave}.json"
        if ruta.exists():
            raise FileExistsError(str(ruta))
        previas = [e for e in self.carteras(juego, linea) if isinstance(e, Guardado) and e.objetivo == objetivo]
        secuencia = LaboratorioFileStore._reservar(self, carpeta, objetivo, clave, previas)
        anteriores = sorted((g for g in previas if g.secuencia < secuencia), key=lambda g: g.secuencia)
        sellado = ca.la.con_orden(artefacto, secuencia, anteriores[-1].identificador if anteriores else None)
        _publicar(carpeta, ruta, serializar_entrada(sellado), carpeta / f"{objetivo}-{secuencia:06d}.secuencia")
        leido = self._leer_cartera(juego, linea, ruta)
        if not isinstance(leido, Guardado):
            raise ValueError("la cartera recien guardada no se pudo releer")
        return leido

    def _leer_cartera(self, juego: str, linea: str, ruta: Path) -> Guardado | Ilegible:
        m = _CARTERA.fullmatch(ruta.name)
        identificador = m.group(2) if m else ruta.name
        objetivo = int(m.group(1)) if m else None
        if m is None or ruta.is_symlink() or not ruta.is_file():
            return Ilegible(identificador, juego, "cartera", "nombre_o_tipo_de_archivo_no_admitido", linea, objetivo)
        try:
            artefacto = leer_entrada(ruta.read_bytes())
        except (EntradaRegistroInvalidaError, RegistroIlegibleError):
            return Ilegible(identificador, juego, "cartera", "json_no_canonico", linea, objetivo)
        if artefacto.get("esquema") != ca.ESQUEMA_CARTERA or not ca.integro(artefacto) or \
                artefacto.get("clave_de_entrada") != identificador:
            return Ilegible(identificador, juego, "cartera", "contenido_alterado", linea, objetivo)
        if artefacto.get("juego") != juego or artefacto.get("linea", {}).get("id") != linea or \
                int(artefacto["cartera"]["objetivo"]) != objetivo:
            return Ilegible(identificador, juego, "cartera", "juego_linea_u_objetivo_no_coincide", linea, objetivo)
        guardado = Guardado(identificador, juego, "cartera", artefacto, linea)
        reserva = ruta.parent / f"{objetivo}-{guardado.secuencia:06d}.secuencia"
        if guardado.secuencia < 1 or (reserva.exists() and
                                      reserva.read_text(encoding="ascii", errors="replace").strip() != identificador):
            return Ilegible(identificador, juego, "cartera", "secuencia_no_valida_o_reservada_por_otra_clave", linea,
                            objetivo)
        return guardado

    def lineas(self, juego: str) -> list[str]:
        raiz = self.directorio / "carteras" / juego
        if not _JUEGO.fullmatch(juego) or not raiz.is_dir():
            return []
        return sorted(p.name for p in raiz.iterdir() if p.is_dir() and _LINEA.fullmatch(p.name))

    def carteras(self, juego: str, linea: str) -> list[Guardado | Ilegible]:
        """Por objetivo descendente y, dentro de cada objetivo, por secuencia
        sellada descendente (version 1 = la primera emision)."""
        carpeta = self._linea(juego, linea)
        if not carpeta.is_dir():
            return []
        elementos = [self._leer_cartera(juego, linea, r) for r in carpeta.iterdir() if r.suffix == ".json"]
        validos = [e for e in elementos if isinstance(e, Guardado)]
        salida = []
        for objetivo in sorted({e.objetivo for e in validos}, reverse=True):
            grupo = sorted((e for e in validos if e.objetivo == objetivo), key=lambda e: e.secuencia)
            salida.extend(reversed([replace(e, version=i, versiones=len(grupo)) for i, e in enumerate(grupo, 1)]))
        return [*salida, *sorted((e for e in elementos if isinstance(e, Ilegible)), key=lambda e: e.identificador)]

    def obtener_cartera(self, clave: str) -> Guardado | Ilegible | None:
        if not _CLAVE.fullmatch(clave or ""):
            return None
        raiz = self.directorio / "carteras"
        if not raiz.is_dir():
            return None
        for ruta in sorted(raiz.glob(f"*/*/*-{clave}.json")):
            juego, linea = ruta.parent.parent.name, ruta.parent.name
            if _JUEGO.fullmatch(juego) and _LINEA.fullmatch(linea):
                for e in self.carteras(juego, linea):
                    if e.identificador == clave:
                        return e
        return None

    # ------------------------------------------------------------------
    # Configuraciones versionadas
    # ------------------------------------------------------------------

    def _configuraciones(self, juego: str) -> Path:
        if not _JUEGO.fullmatch(juego):
            raise ValueError(f"juego no admitido: {juego!r}")
        return self.directorio / "configuraciones" / juego

    def guardar_configuracion(self, juego: str, crear_cuerpo: Callable[[int], dict]) -> Guardado:
        """`crear_cuerpo(version)` devuelve el artefacto sellado de esa version."""
        carpeta = self._configuraciones(juego)
        version = max([0, *(int(m.group(1)) for p in (carpeta.iterdir() if carpeta.is_dir() else [])
                            if (m := _CONFIGURACION.fullmatch(p.name)))]) + 1
        while True:
            artefacto = crear_cuerpo(version)
            if artefacto.get("esquema") != ca.ESQUEMA_CONFIGURACION or artefacto.get("version") != version or \
                    artefacto.get("juego") != juego or not ca.integro(artefacto):
                raise ValueError("configuracion sin version, juego o sello coherente")
            ruta = carpeta / f"{version:06d}.json"
            try:
                _publicar(carpeta, ruta, serializar_entrada(artefacto))
            except FileExistsError:
                version += 1
                continue
            leido = self._leer_configuracion(juego, ruta)
            if not isinstance(leido, Guardado):
                raise ValueError("la configuracion recien guardada no se pudo releer")
            return leido

    def _leer_configuracion(self, juego: str, ruta: Path) -> Guardado | Ilegible:
        m = _CONFIGURACION.fullmatch(ruta.name)
        if m is None or ruta.is_symlink() or not ruta.is_file():
            return Ilegible(ruta.name, juego, "configuracion", "nombre_o_tipo_de_archivo_no_admitido")
        try:
            artefacto = leer_entrada(ruta.read_bytes())
        except (EntradaRegistroInvalidaError, RegistroIlegibleError):
            return Ilegible(m.group(1), juego, "configuracion", "json_no_canonico")
        if artefacto.get("esquema") != ca.ESQUEMA_CONFIGURACION or not ca.integro(artefacto) or \
                artefacto.get("version") != int(m.group(1)) or artefacto.get("juego") != juego:
            return Ilegible(m.group(1), juego, "configuracion", "contenido_alterado")
        return Guardado(m.group(1), juego, "configuracion", artefacto)

    def configuraciones(self, juego: str) -> list[Guardado | Ilegible]:
        """Version mas alta primero."""
        carpeta = self._configuraciones(juego)
        if not carpeta.is_dir():
            return []
        elementos = [self._leer_configuracion(juego, r) for r in carpeta.iterdir() if r.suffix == ".json"]
        return sorted(elementos, key=lambda e: e.identificador, reverse=True)
