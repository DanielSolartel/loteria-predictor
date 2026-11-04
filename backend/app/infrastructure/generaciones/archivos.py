"""Archivos de los almacenes durante la captura (E10.4).

FOTOGRAFIA. Para cada raiz observada se registra, sin seguir enlaces, cada carpeta y archivo con su tipo,
dispositivo e inodo, tamano, `st_mtime_ns` y `st_ctime_ns`. En POSIX `st_ctime` es el instante del ultimo
cambio de contenido O de metadatos del inodo y ningun proceso sin privilegios puede fijarlo; una carpeta cambia
su `mtime`/`ctime` al crear, borrar o renombrar una entrada. Por eso dos fotografias identicas de un arbol
excluyen escrituras, altas, bajas y renombrados entre ambas, incluso las que vuelven al contenido anterior
(ABA). Excepciones declaradas: cambiar el reloj del sistema hacia atras o escribir como superusuario en el
mismo nanosegundo registrado. En WINDOWS, `st_ctime` es la fecha de CREACION: la deteccion se apoya en tamano,
`mtime`, indice de archivo y la huella del contenido copiado, y queda PENDIENTE de validacion nativa.

COPIA. Cada archivo publicable se lee una sola vez, se escribe con creacion exclusiva en la preparacion, se
sincroniza y se vuelve a leer del destino para comprobar su SHA-256.
"""
from __future__ import annotations

import errno
import os
import re
import secrets
import stat
from collections.abc import Callable
from pathlib import Path

from app.infrastructure.generaciones.formato import BLOQUE, GeneracionNoValida, sha256_archivo

# Temporales de publicacion: `.publicacion.<16 hex>.tmp` (Productos 4-6), el nombre anterior
# `.<final>.<16 hex>.tmp` y el de Producto 1 `.<objetivo>-<clave>.<aleatorio>.tmp`.
_TEMPORAL = re.compile(r"^\..+\.tmp$")
_RESERVA_OBJETIVO = re.compile(r"^(\d{1,9})-(\d{6})\.secuencia$")
_RESERVA_MODELO = re.compile(r"^(.+)-(\d{1,9})\.version$")


def es_temporal(nombre: str) -> bool:
    return bool(_TEMPORAL.fullmatch(nombre))


def _entrada(ruta: Path) -> tuple:
    s = os.lstat(ruta)
    if stat.S_ISDIR(s.st_mode):
        tipo = "carpeta"
    elif stat.S_ISREG(s.st_mode):
        tipo = "archivo"
    elif stat.S_ISLNK(s.st_mode):
        tipo = "enlace"
    else:
        tipo = "otro"
    return (tipo, s.st_dev, s.st_ino, s.st_size if tipo == "archivo" else 0, s.st_mtime_ns, s.st_ctime_ns,
            stat.S_IMODE(s.st_mode))


def fotografiar(raices: dict[str, Path]) -> dict[str, tuple]:
    """`{"<almacen>/<ruta relativa POSIX>": entrada}`; la raiz es `"<almacen>/"`; una raiz ausente se registra."""
    foto: dict[str, tuple] = {}
    for nombre, raiz in sorted(raices.items()):
        if not os.path.lexists(raiz):
            foto[f"{nombre}/"] = ("ausente",)
            continue
        foto[f"{nombre}/"] = _entrada(raiz)
        if foto[f"{nombre}/"][0] != "carpeta":
            continue
        pila = [raiz]
        while pila:
            carpeta = pila.pop()
            with os.scandir(carpeta) as it:
                for e in sorted(it, key=lambda x: x.name):
                    ruta = Path(e.path)
                    relativa = ruta.relative_to(raiz).as_posix()
                    foto[f"{nombre}/{relativa}"] = entrada = _entrada(ruta)
                    if entrada[0] == "carpeta":
                        pila.append(ruta)
    return foto


def diferencias(antes: dict[str, tuple], despues: dict[str, tuple], limite: int = 20) -> list[str]:
    salida = []
    for clave in sorted(set(antes) | set(despues)):
        a, d = antes.get(clave), despues.get(clave)
        if a != d:
            salida.append(f"{clave}: {'alta' if a is None else 'baja' if d is None else 'cambio'}")
            if len(salida) >= limite:
                salida.append("...")
                break
    return salida


def reserva_huerfana(ruta: Path) -> bool:
    """Una reserva (`<objetivo>-<secuencia>.secuencia` o `<modelo>-<numero>.version`) cuya clave no tiene su
    artefacto publicado al lado. Los almacenes nunca la presentan como resultado (v2, 2.5: transitorio)."""
    nombre = ruta.name
    try:
        clave = ruta.read_text(encoding="ascii", errors="replace").strip()
    except OSError:
        return True
    if not re.fullmatch(r"[0-9a-f]{64}", clave):
        return True
    m = _RESERVA_OBJETIVO.fullmatch(nombre)
    if m:
        return not (ruta.parent / f"{int(m.group(1))}-{clave}.json").is_file()
    if _RESERVA_MODELO.fullmatch(nombre):
        return not (ruta.parent / f"{clave}.json").is_file()
    return False


def copiar_verificado(origen: Path, destino: Path, comprobar: Callable[[str], None] | None = None) -> tuple[int, str]:
    """Copia con creacion exclusiva, `fsync` y relectura. `comprobar(donde)` se llama antes de cada bloque (plazo
    total de la captura, E104-PLA-04) y puede abortar la copia; el destino parcial queda dentro de la carpeta
    propia que se borra entera."""
    import hashlib

    destino.parent.mkdir(parents=True, exist_ok=True)
    h, total = hashlib.sha256(), 0
    with open(origen, "rb") as fuente, open(destino, "xb") as salida:
        while True:
            if comprobar is not None:
                comprobar(f"copia de {origen.name}")
            bloque = fuente.read(BLOQUE)
            if not bloque:
                break
            h.update(bloque)
            total += len(bloque)
            salida.write(bloque)
        salida.flush()
        os.fsync(salida.fileno())
    leido = sha256_archivo(destino)
    if leido != (total, h.hexdigest()):
        raise GeneracionNoValida(f"la copia de {origen.name} no coincide con lo leido")
    return leido


# ---------------------------------------------------------------------------
# Carpetas PROPIAS: creacion con marca, solo lectura y borrado ligados a OBJETOS abiertos (E104-LIM-03, LIM-07)
# ---------------------------------------------------------------------------
#
# La marca hermana `.<nombre>.propietario-e104` (fuera del contenido: el paquete sigue exacto) guarda el
# intento que creo la carpeta Y la identidad (dispositivo:inodo) del PADRE y de la CARPETA en el momento de
# crearla. Toda autorizacion se hace sobre descriptores, nunca sobre rutas ya validadas:
#
#  1. se abre el padre (un descriptor) y su identidad debe ser la registrada en la marca;
#  2. la marca se lee RELATIVA a ese descriptor (`O_NOFOLLOW`, archivo regular propio);
#  3. la carpeta se abre relativa al padre con `O_NOFOLLOW` y su identidad debe ser la registrada;
#  4. el recorrido (borrado o solo lectura) parte de ESE descriptor de carpeta; cada subcarpeta se abre relativa
#     a su padre con `O_NOFOLLOW` (un enlace se quita, nunca se sigue) y solo se cambian permisos (`fchmod`) de
#     objetos abiertos asi, del mismo usuario y del mismo dispositivo;
#  5. la entrada de la carpeta solo se retira del padre si el nombre sigue designando el MISMO objeto.
#
# Sustituir despues de validar el padre (p. ej. un alias) o la carpeta (otra carpeta real del mismo usuario)
# hace que la identidad no coincida: `NoPropia` y nada ajeno se toca. Lo que quede entre 5 y `rmdir` solo puede
# afectar a una carpeta VACIA (`rmdir` no borra contenido). Dentro de la carpeta propia (0700) las subcarpetas no
# llevan marca: lo que otro proceso del mismo usuario mueva DENTRO de ella pasa a ser contenido suyo.
# Sin `dir_fd`/`O_NOFOLLOW` (Windows) no hay esta garantia: el borrado y `solo_lectura` se NIEGAN de forma
# explicita (`NoPropia`) hasta su validacion nativa; los restos se conservan y se avisa.

MARCA = ".propietario-e104"
FORMATO_MARCA = "e104-propia/2"
_INTENTO = re.compile(r"^[0-9a-f]{16,64}$")
_IDENTIDAD = re.compile(r"^\d+:\d+$")
_SEGURO = os.name == "posix" and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY") and \
    os.rmdir in os.supports_dir_fd and os.unlink in os.supports_dir_fd and os.open in os.supports_dir_fd and \
    os.mkdir in os.supports_dir_fd and os.stat in os.supports_dir_fd and os.rename in os.supports_dir_fd and \
    os.scandir in os.supports_fd
_DIR = getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0) | os.O_RDONLY
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class NoPropia(GeneracionNoValida):
    """La carpeta no se puede acreditar como propia: no se toca."""


def marca_de(ruta: Path) -> Path:
    return ruta.parent / f".{ruta.name}{MARCA}"


def _nombre_marca(nombre: str) -> str:
    return f".{nombre}{MARCA}"


def _identidad(estado) -> str:
    return f"{estado.st_dev}:{estado.st_ino}"


def _uid_propio(estado) -> bool:
    return not hasattr(os, "geteuid") or estado.st_uid == os.geteuid()


def _sin_plataforma_segura(que: str):
    raise NoPropia(f"{que}: sin dir_fd/O_NOFOLLOW en esta plataforma no se puede ligar la propiedad al objeto "
                   "abierto; se conserva sin tocar (pendiente de validacion nativa)")


def _abrir_padre(padre: Path) -> int:
    fd = os.open(padre, _DIR)
    try:
        if not _uid_propio(os.fstat(fd)):
            raise NoPropia(f"{padre.name}: carpeta padre de otro usuario")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _texto_marca(intento: str, padre: str, carpeta: str | None) -> bytes:
    return f"{FORMATO_MARCA} {intento} {padre} {carpeta or '-'}\n".encode("ascii")


def _escribir_marca(padre_fd: int, nombre: str, datos: bytes, *, exclusiva: bool) -> None:
    destino = _nombre_marca(nombre)
    temporal = destino if exclusiva else f".{nombre}.{secrets.token_hex(6)}.marca.tmp"
    fd = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | getattr(os, "O_CLOEXEC", 0), 0o600,
                 dir_fd=padre_fd)
    try:
        os.write(fd, datos)
        os.fsync(fd)
    finally:
        os.close(fd)
    if not exclusiva:
        os.rename(temporal, destino, src_dir_fd=padre_fd, dst_dir_fd=padre_fd)  # atomico en POSIX


def _leer_marca(padre_fd: int, nombre: str) -> tuple[str, str, str | None]:
    try:
        fd = os.open(_nombre_marca(nombre), os.O_RDONLY | _NOFOLLOW | getattr(os, "O_NONBLOCK", 0) |
                     getattr(os, "O_CLOEXEC", 0), dir_fd=padre_fd)
    except FileNotFoundError:
        raise NoPropia(f"{nombre}: sin marca de propiedad") from None
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.EMLINK):
            raise NoPropia(f"{nombre}: la marca de propiedad es un enlace") from None
        raise
    try:
        estado = os.fstat(fd)
        if not stat.S_ISREG(estado.st_mode) or estado.st_size > 300 or not _uid_propio(estado):
            raise NoPropia(f"{nombre}: marca de propiedad no valida")
        partes = os.read(fd, 400).decode("ascii", errors="replace").split()
    finally:
        os.close(fd)
    if len(partes) != 4 or partes[0] != FORMATO_MARCA or not _INTENTO.fullmatch(partes[1]) or \
            not _IDENTIDAD.fullmatch(partes[2]) or not (partes[3] == "-" or _IDENTIDAD.fullmatch(partes[3])):
        raise NoPropia(f"{nombre}: marca de propiedad no valida")
    return partes[1], partes[2], None if partes[3] == "-" else partes[3]


def crear_propia(ruta: Path, intento: str) -> Path:
    """Crea `ruta` (0700) y su marca ligada a la identidad del padre y de la carpeta. Falla si ya existe."""
    if not _INTENTO.fullmatch(intento):
        raise ValueError("intento no valido")
    if not _SEGURO:
        return _crear_sin_dir_fd(ruta, intento)
    nombre = ruta.name
    padre_fd = _abrir_padre(ruta.parent)
    try:
        padre_id = _identidad(os.fstat(padre_fd))
        try:  # antes de tocar la marca: la de una carpeta existente (propia o no) se conserva
            os.stat(nombre, dir_fd=padre_fd, follow_symlinks=False)
            raise FileExistsError(str(ruta))
        except FileNotFoundError:
            pass
        try:
            os.unlink(_nombre_marca(nombre), dir_fd=padre_fd)  # marca huerfana (carpeta ya borrada o promovida)
        except FileNotFoundError:
            pass
        _escribir_marca(padre_fd, nombre, _texto_marca(intento, padre_id, None), exclusiva=True)
        os.mkdir(nombre, 0o700, dir_fd=padre_fd)  # falla si existe (tambien si es un enlace)
        fd = os.open(nombre, _DIR | _NOFOLLOW, dir_fd=padre_fd)
        try:
            estado = os.fstat(fd)
            # recien creada: propia, vacia; si otro proceso la sustituyo entre mkdir y open, no se adopta
            with os.scandir(fd) as entradas:
                vacia = next(entradas, None) is None
            if not _uid_propio(estado) or not vacia:
                raise NoPropia(f"{nombre}: la carpeta recien creada fue sustituida; no se adopta")
            _escribir_marca(padre_fd, nombre, _texto_marca(intento, padre_id, _identidad(estado)), exclusiva=False)
        finally:
            os.close(fd)
    finally:
        os.close(padre_fd)
    return ruta


def _crear_sin_dir_fd(ruta: Path, intento: str) -> Path:
    marca = marca_de(ruta)
    if os.path.lexists(ruta):
        raise FileExistsError(str(ruta))
    if os.path.lexists(marca):
        os.unlink(marca)
    padre_id = _identidad(os.stat(ruta.parent))
    with open(marca, "xb") as f:
        f.write(_texto_marca(intento, padre_id, None))
    os.mkdir(ruta, 0o700)
    datos = _texto_marca(intento, padre_id, _identidad(os.lstat(ruta)))
    temporal = ruta.parent / f".{ruta.name}.{secrets.token_hex(6)}.marca.tmp"
    with open(temporal, "xb") as f:
        f.write(datos)
    os.replace(temporal, marca)
    return ruta


def soltar_marca(ruta: Path) -> None:
    """Tras promover la carpeta (renombrarla a su nombre final), su marca de preparacion ya no aplica."""
    marca = marca_de(ruta)
    if os.path.lexists(marca) and not os.path.islink(marca):
        os.unlink(marca)


def _abrir_propia(ruta: Path, padre: Path, intento: str | None) -> tuple[int, int, str, os.stat_result]:
    """(descriptor del padre, descriptor de la carpeta, intento, fstat de la carpeta) TRAS acreditar que ambos
    descriptores son los objetos registrados en la marca. El llamador cierra los descriptores."""
    if not _SEGURO:
        _sin_plataforma_segura(ruta.name)
    nombre = ruta.name
    if nombre in ("", ".", "..") or os.path.abspath(ruta.parent) != os.path.abspath(padre):
        raise NoPropia(f"{nombre}: fuera de la carpeta esperada")
    padre_fd = _abrir_padre(padre)
    try:
        valor, padre_marca, carpeta_marca = _leer_marca(padre_fd, nombre)
        if padre_marca != _identidad(os.fstat(padre_fd)):
            raise NoPropia(f"{nombre}: el padre abierto no es el registrado en la marca (sustituido)")
        if intento is not None and valor != intento:
            raise NoPropia(f"{nombre}: creada por otro intento")
        try:
            fd = os.open(nombre, _DIR | _NOFOLLOW, dir_fd=padre_fd)
        except FileNotFoundError:
            raise NoPropia(f"{nombre}: no existe") from None
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise NoPropia(f"{nombre}: no es una carpeta real (enlace u otro tipo)") from None
            raise
        try:
            estado = os.fstat(fd)
            if not _uid_propio(estado):
                raise NoPropia(f"{nombre}: pertenece a otro usuario")
            if carpeta_marca is None or _identidad(estado) != carpeta_marca:
                raise NoPropia(f"{nombre}: la carpeta abierta no es el objeto registrado en la marca (sustituida)")
        except BaseException:
            os.close(fd)
            raise
    except BaseException:
        os.close(padre_fd)
        raise
    return padre_fd, fd, valor, estado


def intento_de(ruta: Path, padre: Path) -> str:
    """Identificador del intento que creo `ruta`, acreditado sobre los objetos abiertos, o `NoPropia`."""
    padre_fd, fd, valor, _ = _abrir_propia(ruta, padre, None)
    os.close(fd)
    os.close(padre_fd)
    return valor


def borrar_propia(ruta: Path, padre: Path, intento: str | None = None) -> None:
    """Borra `ruta` solo si es propia (y, si se da, del mismo `intento`), recorriendo los descriptores
    acreditados. Si no, `NoPropia` sin tocar nada ajeno."""
    if not _SEGURO:
        _sin_plataforma_segura(ruta.name)
    nombre = ruta.name
    try:
        padre_fd, fd, _, estado = _abrir_propia(ruta, padre, intento)
    except NoPropia as error:
        if "no existe" in str(error):
            _soltar_marca_sin_carpeta(ruta, padre, intento)
            return
        raise
    try:
        _vaciar_fd(fd, estado.st_dev)
        actual = os.stat(nombre, dir_fd=padre_fd, follow_symlinks=False)
        if _identidad(actual) != _identidad(estado):
            raise NoPropia(f"{nombre}: sustituida durante el borrado; no se retira la entrada")
        os.rmdir(nombre, dir_fd=padre_fd)
        try:
            os.unlink(_nombre_marca(nombre), dir_fd=padre_fd)
        except FileNotFoundError:
            pass
    finally:
        os.close(fd)
        os.close(padre_fd)


def _soltar_marca_sin_carpeta(ruta: Path, padre: Path, intento: str | None) -> None:
    """La carpeta ya no existe: su marca (propia, de este padre e intento) se retira; si no, `NoPropia`."""
    padre_fd = _abrir_padre(padre)
    try:
        valor, padre_marca, _ = _leer_marca(padre_fd, ruta.name)
        if padre_marca != _identidad(os.fstat(padre_fd)) or (intento is not None and valor != intento):
            raise NoPropia(f"{ruta.name}: marca huerfana de otro padre o intento")
        os.unlink(_nombre_marca(ruta.name), dir_fd=padre_fd)
    finally:
        os.close(padre_fd)


def _abrir_hija(fd: int, nombre: str, dispositivo: int) -> int | None:
    """Subcarpeta abierta relativa a `fd` sin seguir enlaces; None si la entrada es un enlace u otro tipo."""
    try:
        hija = os.open(nombre, _DIR | _NOFOLLOW, dir_fd=fd)
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            return None
        raise
    estado = os.fstat(hija)
    if not _uid_propio(estado) or estado.st_dev != dispositivo:
        os.close(hija)
        raise NoPropia(f"{nombre}: subcarpeta de otro usuario o de otro sistema de archivos")
    return hija


def _vaciar_fd(fd: int, dispositivo: int) -> None:
    os.fchmod(fd, 0o700)  # carpeta propia acreditada, abierta sin seguir enlaces
    for entrada in list(os.scandir(fd)):
        if entrada.is_dir(follow_symlinks=False):
            hija = _abrir_hija(fd, entrada.name, dispositivo)
            if hija is None:  # sustituida por un enlace: se quita el enlace
                os.unlink(entrada.name, dir_fd=fd)
                continue
            try:
                identidad = _identidad(os.fstat(hija))
                _vaciar_fd(hija, dispositivo)
            finally:
                os.close(hija)
            if _identidad(os.stat(entrada.name, dir_fd=fd, follow_symlinks=False)) != identidad:
                raise NoPropia(f"{entrada.name}: subcarpeta sustituida durante el borrado")
            os.rmdir(entrada.name, dir_fd=fd)
        else:
            os.unlink(entrada.name, dir_fd=fd)  # archivos y enlaces: nunca se siguen


def solo_lectura(raiz: Path, padre: Path | None = None, intento: str | None = None) -> None:
    """Archivos 0444 y carpetas 0555 en una carpeta PROPIA acreditada sobre sus descriptores; un enlace, un
    archivo ajeno o con varios nombres en ella es un error."""
    if not _SEGURO:
        _sin_plataforma_segura(raiz.name)
    padre_fd, fd, _, estado = _abrir_propia(raiz, padre if padre is not None else raiz.parent, intento)
    try:
        _solo_lectura_fd(fd, estado.st_dev)
    finally:
        os.close(fd)
        os.close(padre_fd)


def _solo_lectura_fd(fd: int, dispositivo: int) -> None:
    for entrada in list(os.scandir(fd)):
        if entrada.is_symlink():
            raise NoPropia(f"{entrada.name}: enlace en una carpeta propia")
        if entrada.is_dir(follow_symlinks=False):
            hija = _abrir_hija(fd, entrada.name, dispositivo)
            if hija is None:
                raise NoPropia(f"{entrada.name}: enlace en una carpeta propia")
            try:
                _solo_lectura_fd(hija, dispositivo)
            finally:
                os.close(hija)
        else:
            archivo = os.open(entrada.name, os.O_RDONLY | _NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=fd)
            try:
                datos = os.fstat(archivo)
                # solo archivos regulares propios con un unico nombre: un enlace duro a algo de fuera
                # cambiaria tambien los permisos de ese otro archivo
                if not stat.S_ISREG(datos.st_mode) or not _uid_propio(datos) or datos.st_nlink != 1:
                    raise NoPropia(f"{entrada.name}: no es un archivo propio con un unico nombre")
                os.fchmod(archivo, 0o444)
            finally:
                os.close(archivo)
    os.fchmod(fd, 0o555)
