"""Instalación y retirada por usuario del visor de Windows."""

import hashlib
import json
import runpy
import shutil
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from perfil_piloto_windows import (
    CARPETA_OPERATIVA, VERSION as VERSION_PILOTO, VERSION_OPERATIVA,
    PerfilPilotoError, _directorio_local, _guardar, _instancia_unica, _sin_enlace,
)

VERSION_INICIAL = "1.0.0"
VERSION_APUESTAS = "2.0.0"
REGISTRO = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
MANIFIESTO = "manifiesto-kit.json"
IDENTIFICACION = "instalacion.json"
DESINSTALADOR = "Desinstalar.exe"
ARCHIVOS_OPERATIVOS = {"Abrir Loteria Predictor.cmd", "abrir.zip"}
MANIFIESTO_OPERATIVO_V1 = {
    "entrega": "operativo_usuario",
    "archivos": {
        "Abrir Loteria Predictor.cmd": "e0162a928b0b77552b0255dffbe93cf899ccfd718de8867e26ff0ca0278f287a",
        "abrir.zip": "64fa9de81b01d82e418fe5f2a1d2dd786693ffdeaf5e1af59e8bb04792133800",
    },
}
HUELLA_OPERATIVO_V1 = "05f7f8b457e94ff41dc0a4f7bb62841448c471110c5496f30f5999d971479bcc"


@dataclass(frozen=True)
class Producto:
    nombre: str
    carpeta: str
    clave: str
    aplicacion: str
    carpeta_perfil: str
    version_perfil: str
    entrega: str


PRODUCTOS = {
    "piloto": Producto("Lotería Predictor (piloto)", "LP11-Piloto", REGISTRO + "\\LoteriaPredictorPiloto",
                       "loteria-predictor-piloto", "LP11", VERSION_PILOTO, "instalador_usuario"),
    "operativo": Producto("Lotería Predictor", CARPETA_OPERATIVA, REGISTRO + "\\LoteriaPredictorOperativo",
                          "loteria-predictor-operativo", CARPETA_OPERATIVA, VERSION_OPERATIVA, "operativo_usuario"),
}


class InstalacionError(RuntimeError):
    pass


def _huella(ruta: Path) -> str:
    _sin_enlace(ruta)
    with ruta.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _identidad(producto: Producto, version: str, huella: str) -> dict:
    return {"aplicacion": producto.aplicacion, "version": version, "manifiesto_sha256": huella}


def _anterior(producto: Producto, identidad: dict) -> tuple[dict, dict] | None:
    if producto.entrega == "operativo_usuario" and identidad["version"] == VERSION_APUESTAS:
        return MANIFIESTO_OPERATIVO_V1, _identidad(producto, VERSION_INICIAL, HUELLA_OPERATIVO_V1)
    return None


def _verificar_carga(kit: Path, manifiesto: dict, huella: str) -> None:
    _sin_enlace(kit)
    if _huella(kit / MANIFIESTO) != huella:
        raise InstalacionError("La huella del manifiesto de la carga no coincide.")
    archivos = manifiesto["archivos"]
    if manifiesto["entrega"] == "operativo_usuario":
        nombres = {p.name for p in kit.iterdir()} - {MANIFIESTO}
        if nombres != ARCHIVOS_OPERATIVOS or nombres != archivos.keys():
            raise InstalacionError("La carga operativa está incompleta o contiene archivos ajenos.")
        if any(_huella(kit / nombre) != archivos[nombre] for nombre in nombres):
            raise InstalacionError("La huella de un archivo del visor operativo no coincide.")
        return
    if _huella(kit / "arrancar.py") != archivos["arrancar.py"]:
        raise InstalacionError("El manifiesto o el verificador de la carga no coincide.")
    verificar = runpy.run_path(str(kit / "arrancar.py"), run_name="verificador_piloto")["verificar"]
    verificar(kit)


def _identidad_instalada(ruta: Path) -> dict | None:
    _sin_enlace(ruta)
    marcador = ruta / IDENTIFICACION
    _sin_enlace(marcador)
    return json.loads(marcador.read_bytes()) if marcador.is_file() else None


def _comprobar_pertenencia(ruta: Path, manifiesto: dict, identidad: dict) -> None:
    if _identidad_instalada(ruta) != identidad:
        raise InstalacionError(f"{ruta.name} no corresponde a esta instalación del visor.")

    archivos = {f"app/{nombre}" for nombre in manifiesto["archivos"]}
    archivos.update({f"app/{MANIFIESTO}", DESINSTALADOR, IDENTIFICACION})
    carpetas = {str(padre) for nombre in archivos for padre in PurePosixPath(nombre).parents}
    for entrada in ruta.rglob("*", recurse_symlinks=False):
        _sin_enlace(entrada)
        permitido = carpetas if entrada.is_dir() else archivos
        if entrada.relative_to(ruta).as_posix() not in permitido:
            raise InstalacionError(f"{ruta.name} contiene un archivo o directorio ajeno al visor.")


def _registro(producto: Producto) -> dict | None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, producto.clave) as clave:
            subclaves, cantidad, _ = winreg.QueryInfoKey(clave)
            if subclaves:
                raise InstalacionError("La entrada de Windows contiene subclaves ajenas al piloto.")
            return {nombre: (valor, tipo) for nombre, valor, tipo in (
                winreg.EnumValue(clave, indice) for indice in range(cantidad)
            )}
    except FileNotFoundError:
        return None


def _guardar_registro(producto: Producto, valores: dict | None) -> None:
    import winreg

    if valores is None:
        with suppress(FileNotFoundError):
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, producto.clave)
        return
    anteriores = _registro(producto) or {}
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, producto.clave, 0, winreg.KEY_SET_VALUE) as clave:
        for nombre, (valor, tipo) in valores.items():
            winreg.SetValueEx(clave, nombre, 0, tipo, valor)
        for nombre in anteriores.keys() - valores.keys():
            winreg.DeleteValue(clave, nombre)


def _valores_registro(producto: Producto, programa: Path, version: str) -> dict:
    import winreg

    return {
        "InstallLocation": (str(programa), winreg.REG_SZ),
        "DisplayName": (producto.nombre, winreg.REG_SZ),
        "DisplayVersion": (version, winreg.REG_SZ),
        "UninstallString": (f'"{programa / DESINSTALADOR}"', winreg.REG_SZ),
        "NoModify": (1, winreg.REG_DWORD),
        "NoRepair": (1, winreg.REG_DWORD),
    }


def _guardar_acceso(ruta: Path, datos: bytes | None) -> None:
    if datos is None:
        ruta.unlink(missing_ok=True)
        return
    with TemporaryDirectory(dir=ruta.parent, prefix="lp11-") as directorio:
        temporal = Path(directorio) / ruta.name
        temporal.write_bytes(datos)
        temporal.replace(ruta)


def _integrar(producto: Producto, programa: Path, acceso: Path, datos: bytes | None, *, existente: bool,
              version: str = VERSION_INICIAL) -> None:
    _sin_enlace(acceso)
    registro = _registro(producto)
    if registro and registro.get("InstallLocation", (None,))[0] != str(programa):
        raise InstalacionError("La entrada de Windows pertenece a otra instalación.")
    enlace = acceso.read_bytes() if acceso.exists() else None
    if enlace is not None and not (existente or registro):
        raise InstalacionError("Ya existe un acceso directo con el nombre del visor.")
    try:
        _guardar_registro(producto, _valores_registro(producto, programa, version) if datos is not None else None)
        _guardar_acceso(acceso, datos)
    except BaseException:
        _guardar_registro(producto, registro)
        _guardar_acceso(acceso, enlace)
        raise


def _retirado(programa: Path) -> Path:
    return programa.with_name(f"{programa.name}.retirar")


def _borrar_retirado(ruta: Path, manifiesto: dict, identidad: dict, *, anterior: tuple[dict, dict] | None = None) -> None:
    _sin_enlace(ruta)
    if not ruta.exists():
        return
    if any(ruta.iterdir()):
        if anterior is not None and _identidad_instalada(ruta) == anterior[1]:
            manifiesto, identidad = anterior
        _comprobar_pertenencia(ruta, manifiesto, identidad)
        if (ruta / "app").is_dir():
            shutil.rmtree(ruta / "app")
        (ruta / DESINSTALADOR).unlink(missing_ok=True)
        (ruta / IDENTIFICACION).unlink()
    ruta.rmdir()


def _respaldo_actualizacion(programa: Path) -> Path:
    return programa.with_name(f"{programa.name}.anterior")


def instalar(producto: Producto, programa: Path, acceso: Path, temporal: Path, manifiesto: dict, identidad: dict) -> None:
    carga = temporal / "carga"
    huella = identidad["manifiesto_sha256"]
    enlace = (temporal / "piloto.lnk").read_bytes()
    desinstalador = temporal / DESINSTALADOR
    version = identidad["version"]
    anterior = _anterior(producto, identidad)
    respaldo = _respaldo_actualizacion(programa)
    _verificar_carga(carga, manifiesto, huella)
    _sin_enlace(programa)
    _sin_enlace(respaldo)
    _borrar_retirado(_retirado(programa), manifiesto, identidad, anterior=anterior)
    if respaldo.exists():
        if anterior is None:
            raise InstalacionError("Completa la actualización con el instalador más reciente.")
        if not programa.exists():
            _comprobar_pertenencia(respaldo, *anterior)
            _verificar_carga(respaldo / "app", anterior[0], HUELLA_OPERATIVO_V1)
            respaldo.rename(programa)

    actualizar = False
    if programa.exists():
        actualizar = anterior is not None and not respaldo.exists() and _identidad_instalada(programa) == anterior[1]
        if actualizar:
            _comprobar_pertenencia(programa, *anterior)
            _verificar_carga(programa / "app", anterior[0], HUELLA_OPERATIVO_V1)
        else:
            _comprobar_pertenencia(programa, manifiesto, identidad)
            _verificar_carga(programa / "app", manifiesto, huella)
            if respaldo.exists():
                _borrar_retirado(respaldo, *anterior)
            if not (programa / DESINSTALADOR).exists():
                _guardar_acceso(programa / DESINSTALADOR, desinstalador.read_bytes())
            _integrar(producto, programa, acceso, enlace, existente=True, version=version)
            return

    with TemporaryDirectory(dir=programa.parent, prefix="lp11-") as directorio:
        nuevo = Path(directorio)
        shutil.copytree(carga, nuevo / "app")
        _verificar_carga(nuevo / "app", manifiesto, huella)
        shutil.copyfile(desinstalador, nuevo / DESINSTALADOR)
        _guardar(nuevo / IDENTIFICACION, identidad)
        _comprobar_pertenencia(nuevo, manifiesto, identidad)
        if actualizar:
            programa.rename(respaldo)
        try:
            nuevo.rename(programa)
            try:
                _integrar(producto, programa, acceso, enlace, existente=actualizar, version=version)
            except BaseException:
                programa.rename(nuevo)
                raise
        except BaseException:
            if actualizar:
                respaldo.rename(programa)
            raise
    if actualizar:
        _borrar_retirado(respaldo, *anterior)


def desinstalar(producto: Producto, programa: Path, acceso: Path, manifiesto: dict, identidad: dict) -> None:
    retirado = _retirado(programa)
    _sin_enlace(programa)
    _sin_enlace(retirado)
    respaldo = _respaldo_actualizacion(programa)
    _sin_enlace(respaldo)
    if respaldo.exists():
        anterior = _anterior(producto, identidad)
        if anterior is None or not programa.exists():
            raise InstalacionError("Completa la actualización con el instalador más reciente.")
        _comprobar_pertenencia(programa, manifiesto, identidad)
        _borrar_retirado(respaldo, *anterior)
    if programa.exists():
        _comprobar_pertenencia(programa, manifiesto, identidad)
        _borrar_retirado(retirado, manifiesto, identidad)
        programa.rename(retirado)
        try:
            _integrar(producto, programa, acceso, None, existente=True)
        except BaseException:
            retirado.rename(programa)
            raise
    elif retirado.exists():
        if any(retirado.iterdir()):
            _comprobar_pertenencia(retirado, manifiesto, identidad)
        _integrar(producto, programa, acceso, None, existente=True)
    elif _registro(producto) is not None:
        _integrar(producto, programa, acceso, None, existente=False)
    _borrar_retirado(retirado, manifiesto, identidad)


def main(operacion: str, menu: Path, temporal: Path, huella: str, modalidad: str = "piloto") -> None:
    producto = PRODUCTOS[modalidad]
    perfil = _directorio_local(producto.carpeta_perfil, producto.version_perfil)
    programas = perfil.parent / "Programs"
    _sin_enlace(programas)
    acceso = menu.resolve(strict=True) / f"{producto.nombre}.lnk"
    programa = programas / producto.carpeta
    manifiesto = temporal / MANIFIESTO
    if _huella(manifiesto) != huella:
        raise InstalacionError("No coincide la huella del manifiesto del instalador.")
    datos = json.loads(manifiesto.read_bytes())
    if datos.get("entrega") != producto.entrega or datos.get("version") != producto.version_perfil:
        raise InstalacionError("El manifiesto corresponde a otra edición del visor.")
    version = datos.get("version_instalacion", VERSION_INICIAL)
    if version != VERSION_INICIAL and (modalidad, version) != ("operativo", VERSION_APUESTAS):
        raise InstalacionError("La versión del instalador no es compatible.")
    identidad = _identidad(producto, version, huella)
    with _instancia_unica(perfil) as libre:
        if not libre:
            raise InstalacionError("Cierra el visor con «Cerrar piloto» y vuelve a intentarlo.")
        if operacion == "instalar":
            programas.mkdir(exist_ok=True)
            instalar(producto, programa, acceso, temporal, datos, identidad)
        elif operacion == "desinstalar":
            desinstalar(producto, programa, acceso, datos, identidad)
        else:
            raise InstalacionError("Operación del instalador desconocida.")


if __name__ == "__main__":
    operacion, menu, temporal, huella, *modalidad = sys.argv[1:]
    temporal = Path(temporal)
    try:
        main(operacion, Path(menu), temporal, huella, *modalidad)
    except (InstalacionError, PerfilPilotoError, OSError, ValueError, KeyError) as error:
        detalle = str(error) if isinstance(error, (InstalacionError, PerfilPilotoError)) else type(error).__name__
        (temporal / "resultado.txt").write_text(f"La operación del visor se detuvo. {detalle}", encoding="utf-16-le")
        raise SystemExit(1)
