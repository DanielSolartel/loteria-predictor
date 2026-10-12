"""
Almacen del laboratorio de modelos (Producto 4), separado de los almacenes
de Productos 1-3 (`DIRECTORIO_LABORATORIO_MODELOS`, ignorado por Git).

    <dir>/experimentos/<JUEGO>/<clave>.json
    <dir>/pronosticos/<JUEGO>/<linea>/<objetivo>-<clave>.json
    <dir>/pronosticos/<JUEGO>/<linea>/<objetivo>-<secuencia>.secuencia
    <dir>/modelos/<JUEGO>/<clave>.json                 (Fase 3: manifiesto del modelo)
    <dir>/modelos/<JUEGO>/estimadores/<sha256>.pkl     (Fase 3: estimador serializado)
    <dir>/modelos/<JUEGO>/<modelo>-<numero>.version    (Fase 3: reserva del numero)
    <dir>/operacion/...  (progreso y cerrojos, con las primitivas de Producto 3)

Informes y pronosticos son INMUTABLES: JSON canonico (AE-52) publicado como
en Producto 3 (temporal en la misma carpeta, `flush` + `fsync`, `os.link`
al nombre final, que falla si ya existe; nunca se sobrescribe). Un lector ve
la ausencia o el JSON completo. Al leer se comprueban bytes canonicos,
sello, huella, clave y ubicacion; si no coinciden, el elemento es
`Ilegible` con su motivo. Temporales y reservas huerfanas nunca se
presentan como experimentos o pronosticos.

RUTAS EN WINDOWS: el temporal tiene el nombre corto de Producto 5,
`.publicacion.<16 hex>.tmp` (33 caracteres, independiente del destino), y el
mismo publicador sirve a Productos 4 a 6. El nombre anterior,
`.<nombre final>.<16 hex>.tmp`, anadia 22 caracteres al destino: en la primera
ejecucion de la Fase 3 en Windows (sin rutas largas, limite de 259) los
estimadores y los pronosticos de versiones registradas cabian, pero su
temporal no se podia crear. Los temporales con el nombre anterior o el nuevo
(escrituras en curso, interrumpidas o de otros escritores) se reconocen como
tales, nunca se listan como resultados y nunca se borran solos.

ORDEN DE EMISION de los pronosticos: por linea de modelo (modelo, version y
perfil) y objetivo, con una secuencia reservada de forma exclusiva
(`O_EXCL`) y sellada dentro del artefacto (`generacion.secuencia_en_la_linea`).
Nunca por hash, fecha, mtime ni orden de `iterdir()`. Las lineas del
laboratorio no se mezclan con las de Productos 1-3, asi que no cambian cual
es la primera emision que selecciona `/rendimiento`.

MODELOS REGISTRADOS (Fase 3): tres archivos por version, publicados en este
orden y con el mismo mecanismo (temporal + `fsync` + enlace exclusivo):
1. el estimador, con su SHA-256 como nombre (si ya existe, se comprueba que
   sus bytes son los mismos; nunca se sobrescribe);
2. la reserva exclusiva (`O_EXCL`) del numero de version por juego y modelo;
3. el manifiesto sellado, que lleva el numero, el SHA-256 y el tamano del
   estimador. Es el ULTIMO paso: hasta entonces la version no existe para
   ningun lector. Si otro proceso publico la misma entrada, el enlace falla,
   la reserva se retira y se devuelve la version ya publicada.
Una interrupcion antes del paso 3 deja, como mucho, un estimador sin
manifiesto (`huerfanos`) o una reserva sin manifiesto (`reservas_sin_modelo`):
se informan y nunca se presentan como modelos ni se borran solos. Al leer se
comprueban manifiesto, sello, clave, juego, reserva del numero y SHA-256 y
tamano del estimador.

Requiere disco local NTFS o POSIX (enlaces duros y creacion exclusiva).
"""
from __future__ import annotations

import os
import re
import secrets
from dataclasses import replace
from pathlib import Path

from app.application.interfaces.laboratorio_store import (
    GuardadoLaboratorio,
    GuardadoModelo,
    IlegibleLaboratorio,
    IlegibleModelo,
    LaboratorioStore,
    ReservaSinModelo,
)
from app.application.ml import laboratorio_artefactos as la
from app.application.ml import modelos_registrados as mr
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
# Temporales de publicacion: el nombre corto actual y el anterior, `.<nombre final>.<16 hex>.tmp`
_TEMPORAL_ACTUAL = re.compile(r"^\.publicacion\.[0-9a-f]{16}\.tmp$")
_TEMPORAL_ANTERIOR = re.compile(r"^\..+\.[0-9a-f]{16}\.tmp$")
_MODELO = re.compile(r"^([0-9a-f]{64})\.json$")
_ESTIMADOR = re.compile(r"^([0-9a-f]{64})\.pkl$")
_ID_MODELO = re.compile(r"^[a-z0-9_]{1,40}$")
_VERSION = re.compile(r"^([a-z0-9_]{1,40})-(\d{6})\.version$")


Guardado = GuardadoLaboratorio
Ilegible = IlegibleLaboratorio


def _es_temporal(nombre: str) -> bool:
    return bool(_TEMPORAL_ACTUAL.fullmatch(nombre) or _TEMPORAL_ANTERIOR.fullmatch(nombre))


def _publicar(carpeta: Path, ruta: Path, contenido: bytes, reserva: Path | None = None) -> None:
    """Publicacion atomica sin sobrescritura con un temporal de nombre corto e
    independiente del destino (33 caracteres, en la misma carpeta y el mismo
    volumen): creacion exclusiva, `flush` + `fsync` y enlace duro, que falla si
    el destino existe. Si falla, retira el temporal y la reserva indicada."""
    carpeta.mkdir(parents=True, exist_ok=True)
    temporal = carpeta / f".publicacion.{secrets.token_hex(8)}.tmp"
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

    _publicar = staticmethod(_publicar)

    def temporales(self) -> list[str]:
        """Temporales de escrituras en curso, interrumpidas o de otros
        escritores, con el nombre actual o el anterior (no son resultados ni se
        borran)."""
        if not self.directorio.is_dir():
            return []
        return sorted(str(p.relative_to(self.directorio)) for p in self.directorio.rglob("*.tmp")
                      if _es_temporal(p.name))

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


    # ------------------------------------------------------------------
    # Modelos registrados (Fase 3)
    # ------------------------------------------------------------------

    def _modelos(self, juego: str) -> Path:
        if not _JUEGO.fullmatch(juego):
            raise ValueError(f"juego no admitido: {juego!r}")
        return self.directorio / "modelos" / juego

    def _publicar_estimador(self, carpeta: Path, digesto: str, contenido: bytes) -> None:
        ruta = carpeta / f"{digesto}.pkl"
        try:
            if not ruta.exists():
                self._publicar(carpeta, ruta, contenido)
                return
        except FileExistsError:  # otro proceso lo publico a la vez
            pass
        if ruta.is_symlink() or not ruta.is_file() or mr.sha256(ruta.read_bytes()) != digesto:
            raise ValueError(f"ya existe un estimador {digesto[:12]} con otros bytes; no se sobrescribe")

    def _reservar_numero(self, carpeta: Path, modelo: str, clave: str) -> int:
        usados = [int(m.group(2)) for p in carpeta.iterdir() if (m := _VERSION.fullmatch(p.name)) and m.group(1) == modelo]
        numero = max([0, *usados]) + 1
        while True:
            try:
                descriptor = os.open(carpeta / f"{modelo}-{numero:06d}.version", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                numero += 1
                continue
            with os.fdopen(descriptor, "w", encoding="ascii") as flujo:
                flujo.write(clave + "\n")
                flujo.flush()
                os.fsync(flujo.fileno())
            return numero

    def guardar_modelo(self, artefacto: dict, estimador: bytes) -> GuardadoModelo:
        """Publica una version NUEVA (ver el docstring del modulo). Si la clave
        ya existe lanza `FileExistsError` sin tocar nada."""
        clave = artefacto.get("clave", "")
        modelo = (artefacto.get("identidad") or {}).get("modelo", {}).get("id", "")
        if not _CLAVE.fullmatch(clave) or artefacto.get("esquema") != mr.ESQUEMA_MODELO or \
                not _ID_MODELO.fullmatch(modelo) or not mr.integro(artefacto):
            raise ValueError("modelo sin clave valida o sin sello coherente")
        digesto = artefacto["estimador"]["sha256"]
        if not _CLAVE.fullmatch(digesto) or mr.sha256(estimador) != digesto or \
                len(estimador) != artefacto["estimador"]["bytes"]:
            raise ValueError("el estimador no coincide con el SHA-256 y el tamano del manifiesto")
        juego = artefacto["juego"]
        carpeta = self._modelos(juego)
        ruta = carpeta / f"{clave}.json"
        if ruta.exists():
            raise FileExistsError(str(ruta))
        carpeta.mkdir(parents=True, exist_ok=True)
        self._publicar_estimador(carpeta / "estimadores", digesto, estimador)
        numero = self._reservar_numero(carpeta, modelo, clave)
        sellado = mr.con_numero(artefacto, numero)
        self._publicar(carpeta, ruta, serializar_entrada(sellado), carpeta / f"{modelo}-{numero:06d}.version")
        leido = self._leer_modelo(juego, ruta)
        if not isinstance(leido, GuardadoModelo):
            raise ValueError(f"el modelo recien guardado no se pudo releer ({leido.motivo})")
        return leido

    def _leer_modelo(self, juego: str, ruta: Path) -> GuardadoModelo | IlegibleModelo:
        m = _MODELO.fullmatch(ruta.name)
        identificador = m.group(1) if m else ruta.name
        if m is None or ruta.is_symlink() or not ruta.is_file():
            return IlegibleModelo(identificador, juego, "nombre_o_tipo_de_archivo_no_admitido")
        try:
            artefacto = leer_entrada(ruta.read_bytes())
        except (EntradaRegistroInvalidaError, RegistroIlegibleError):
            return IlegibleModelo(identificador, juego, "json_no_canonico")
        if artefacto.get("esquema") != mr.ESQUEMA_MODELO or not mr.integro(artefacto) or \
                artefacto.get("clave") != identificador:
            return IlegibleModelo(identificador, juego, "contenido_alterado")
        modelo = artefacto["identidad"]["modelo"]["id"]
        if artefacto.get("juego") != juego:
            return IlegibleModelo(identificador, juego, "juego_no_coincide", modelo)
        try:
            numero = mr.numero_de(artefacto)
        except (KeyError, TypeError, ValueError):
            return IlegibleModelo(identificador, juego, "sin_numero_de_version", modelo)
        reserva = ruta.parent / f"{modelo}-{numero:06d}.version"
        if numero < 1 or not _ID_MODELO.fullmatch(modelo) or not reserva.is_file() or \
                reserva.read_text(encoding="ascii", errors="replace").strip() != identificador:
            return IlegibleModelo(identificador, juego, "numero_no_reservado_para_esta_clave", modelo, numero)
        digesto = artefacto["estimador"]["sha256"]
        objeto = ruta.parent / "estimadores" / f"{digesto}.pkl"
        if not _CLAVE.fullmatch(digesto) or objeto.is_symlink() or not objeto.is_file():
            return IlegibleModelo(identificador, juego, "estimador_ausente", modelo, numero)
        contenido = objeto.read_bytes()
        if len(contenido) != artefacto["estimador"]["bytes"] or mr.sha256(contenido) != digesto:
            return IlegibleModelo(identificador, juego, "estimador_alterado", modelo, numero)
        return GuardadoModelo(identificador, juego, artefacto)

    def modelos(self, juego: str) -> list[GuardadoModelo | IlegibleModelo]:
        """Versiones validas por modelo y numero descendente; despues las ilegibles."""
        carpeta = self._modelos(juego)
        if not carpeta.is_dir():
            return []
        elementos = [self._leer_modelo(juego, r) for r in carpeta.iterdir() if r.suffix == ".json"]
        validos = sorted((e for e in elementos if isinstance(e, GuardadoModelo)),
                         key=lambda e: (e.modelo, -e.numero))
        return [*validos, *sorted((e for e in elementos if isinstance(e, IlegibleModelo)),
                                  key=lambda e: e.identificador)]

    def obtener_modelo(self, clave: str) -> GuardadoModelo | IlegibleModelo | None:
        if not _CLAVE.fullmatch(clave or ""):
            return None
        raiz = self.directorio / "modelos"
        if not raiz.is_dir():
            return None
        for carpeta in sorted(raiz.iterdir()):
            ruta = carpeta / f"{clave}.json"
            if _JUEGO.fullmatch(carpeta.name) and ruta.exists():
                return self._leer_modelo(carpeta.name, ruta)
        return None

    def leer_estimador(self, guardado: GuardadoModelo) -> bytes:
        """Bytes del estimador de una version ya validada. Quien los carga vuelve
        a comprobar el SHA-256 sobre estos mismos bytes."""
        digesto = guardado.artefacto["estimador"]["sha256"]
        if not _CLAVE.fullmatch(digesto):
            raise ValueError("SHA-256 del estimador no valido")
        return (self._modelos(guardado.juego) / "estimadores" / f"{digesto}.pkl").read_bytes()

    def reservas_sin_modelo(self, juego: str) -> list[ReservaSinModelo]:
        carpeta = self._modelos(juego)
        if not carpeta.is_dir():
            return []
        validos = [e for e in self.modelos(juego) if isinstance(e, GuardadoModelo)]
        publicados = {(e.modelo, e.numero) for e in validos}
        claves = {e.identificador for e in validos}
        salida = []
        for p in sorted(carpeta.iterdir()):
            m = _VERSION.fullmatch(p.name)
            if not m or (m.group(1), int(m.group(2))) in publicados:
                continue
            clave = p.read_text(encoding="ascii", errors="replace").strip()
            if clave not in claves and _CLAVE.fullmatch(clave) and (carpeta / f"{clave}.json").exists():
                continue  # su manifiesto existe pero es ilegible: ya se informa en `modelos` como tal
            salida.append(ReservaSinModelo(juego, m.group(1), int(m.group(2)), clave,
                                           "duplicada" if clave in claves else "sin_publicar"))
        return salida

    def huerfanos(self) -> list[str]:
        """Estimadores sin manifiesto que los cite y temporales (no son modelos)."""
        raiz = self.directorio / "modelos"
        salida = []
        if raiz.is_dir():
            for carpeta in sorted(raiz.iterdir()):
                if not _JUEGO.fullmatch(carpeta.name) or not (carpeta / "estimadores").is_dir():
                    continue
                citados = {e.artefacto["estimador"]["sha256"] for e in self.modelos(carpeta.name)
                           if isinstance(e, GuardadoModelo)}
                salida += [str(p.relative_to(self.directorio)) for p in sorted((carpeta / "estimadores").iterdir())
                           if _ESTIMADOR.fullmatch(p.name) and p.name[:-4] not in citados]
        return salida + self.temporales()


def _retirar(*rutas: Path | None) -> None:
    for ruta in rutas:
        if ruta is None:
            continue
        try:
            ruta.unlink()
        except FileNotFoundError:
            pass
