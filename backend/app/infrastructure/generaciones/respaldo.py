"""Respaldo cifrado, verificacion, restauracion aislada (R-L) y retencion (E10.4, DAT-05 y DAT-08 en Linux).

QUE SE RESPALDA. Un paquete capturado con el MISMO metodo coherente de las generaciones y alcance `respaldo`:
base completa, almacenes publicables, informes internos y estado operativo (registros, progreso, cerrojos y
configuracion de Fase 6), sin temporales y SIN secretos (cuentas de la consola, `.env`): estos van en un
respaldo aparte (D12) que no es de esta entrega. Tambien se puede cifrar un paquete de publicacion.

CIFRADO (archivo `.lpr`), con `cryptography` (ya en los locks):
- receptor X25519: el equipo que respalda solo tiene la clave PUBLICA; la privada (restauracion) se custodia
  aparte (D6, pendiente: aqui solo archivos locales 0600);
- por archivo: clave efimera X25519, HKDF-SHA256 (sal aleatoria; informacion con ambas claves publicas) ->
  clave AES-256 y prefijo de nonce; contenido (un tar PAX del paquete) en bloques de 1 MiB con AES-256-GCM,
  nonce = prefijo + contador, datos asociados = huella de la cabecera + contador + marca de bloque final.
  Reordenar, quitar, truncar o alterar un bloque, o cambiar la cabecera, hace fallar el descifrado.
- junto al `.lpr`, un `.lpr.json` (catalogo: id, fecha, tamano, SHA-256 del cifrado y receptor) permite
  comprobar sin la clave privada que el archivo no cambio; la verificacion COMPLETA descifra y verifica la firma
  y las huellas del paquete.

GARANTIAS LOCALES PROBADAS frente a las que dependen del PROVEEDOR (D6, no elegido): aqui se prueban el
cifrado y su autenticacion, la verificacion, la restauracion aislada y la politica de retencion sobre una
carpeta local. NO se prueban (dependen del destino que se elija): inmutabilidad o versiones del almacenamiento,
copia fuera de ambas maquinas, credencial de subida sin borrado (DAT-06), custodia de la clave privada,
RPO/RTO (D5). Ninguna de esas decisiones se toma aqui.

RESTAURACION R-L: descifra en una carpeta privada nueva, verifica el paquete (firma, archivos, huellas),
crea una base NUEVA (nunca la de origen ni una existente), migra a la revision del paquete, carga y comprueba
las filas, y copia los almacenes a una carpeta NUEVA. No registra, habilita ni ejecuta ninguna tarea programada
ni toca Fase 6: la recuperacion operativa en Windows (R-W) sigue pendiente de su ensayo nativo autorizado.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import secrets
import struct
import tarfile
from dataclasses import dataclass
from pathlib import Path

from app.infrastructure.generaciones import archivos as ar
from app.infrastructure.generaciones import base_logica as bl
from app.infrastructure.generaciones.formato import (
    BLOQUE, FORMATO_RESPALDO, GeneracionNoValida, canonico, escribir_exclusivo, leer_canonico, sha256_archivo,
    sha256_bytes,
)

MAGIA = b"LPRESP1\n"
INFO = b"loteria-respaldo-e104/1"
MAXIMO_CABECERA = 16 * 1024


# ---------------------------------------------------------------------------
# Claves
# ---------------------------------------------------------------------------

def generar_claves(privada: Path, publica: Path) -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

    if privada.exists() or publica.exists():
        raise FileExistsError("las claves ya existen: no se sobrescriben")
    clave = X25519PrivateKey.generate()
    privada.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(privada, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as f:
        f.write(clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()))
    crudo = _crudo(clave.public_key())
    publica.parent.mkdir(parents=True, exist_ok=True)
    with open(publica, "x", encoding="ascii") as f:
        f.write(crudo.hex() + "\n")
    return sha256_bytes(crudo)[:16]


def _crudo(publica) -> bytes:
    from cryptography.hazmat.primitives import serialization
    return publica.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _publica(ruta: Path):
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    try:
        return X25519PublicKey.from_public_bytes(bytes.fromhex(ruta.read_text(encoding="ascii").strip()))
    except (ValueError, OSError) as error:
        raise GeneracionNoValida("clave publica de respaldo no valida") from error


def _privada(ruta: Path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

    if os.name == "posix" and os.stat(ruta).st_mode & 0o077:
        raise GeneracionNoValida("la clave privada de respaldo no debe ser legible por otros (0600)")
    clave = serialization.load_pem_private_key(ruta.read_bytes(), password=None)
    if not isinstance(clave, X25519PrivateKey):
        raise GeneracionNoValida("la clave de respaldo no es X25519")
    return clave


def _derivar(compartido: bytes, sal: bytes, efimera: bytes, receptor: bytes) -> tuple[bytes, bytes]:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    material = HKDF(algorithm=hashes.SHA256(), length=40, salt=sal, info=INFO + efimera + receptor).derive(compartido)
    return material[:32], material[32:]


def _asociados(cabecera: bytes, contador: int, final: bool) -> bytes:
    return sha256_bytes(cabecera).encode("ascii") + struct.pack(">Q?", contador, final)


# ---------------------------------------------------------------------------
# Cifrado en flujo
# ---------------------------------------------------------------------------

class _Cifrador:
    def __init__(self, salida, clave: bytes, prefijo: bytes, cabecera: bytes):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        self.salida, self.aes, self.prefijo, self.cabecera = salida, AESGCM(clave), prefijo, cabecera
        self.pendiente, self.contador = bytearray(), 0

    def write(self, datos: bytes) -> int:
        self.pendiente += datos
        while len(self.pendiente) > BLOQUE:
            self._bloque(bytes(self.pendiente[:BLOQUE]), False)
            del self.pendiente[:BLOQUE]
        return len(datos)

    def _bloque(self, claro: bytes, final: bool) -> None:
        nonce = self.prefijo + struct.pack(">I", self.contador)
        cifrado = self.aes.encrypt(nonce, claro, _asociados(self.cabecera, self.contador, final))
        self.salida.write(struct.pack(">I", len(cifrado)) + cifrado)
        self.contador += 1

    def cerrar(self) -> None:
        self._bloque(bytes(self.pendiente), True)
        self.pendiente.clear()


def _tar(paquete: Path, flujo) -> None:
    with tarfile.open(fileobj=flujo, mode="w|", format=tarfile.PAX_FORMAT) as tar:
        for ruta in [paquete, *sorted(paquete.rglob("*"))]:
            if ruta.is_symlink():
                raise GeneracionNoValida("enlace simbolico en el paquete a respaldar")
            info = tar.gettarinfo(str(ruta), arcname=str(Path(paquete.name) / ruta.relative_to(paquete)))
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o755 if info.isdir() else 0o644
            if info.isfile():
                with open(ruta, "rb") as f:
                    tar.addfile(info, f)
            else:
                tar.addfile(info)


def respaldar(paquete: Path, clave_publica: Path, destino: Path) -> dict:
    """Cifra la carpeta `paquete` (ya sellada) en `<destino>/<marca>-<id>.lpr` y su catalogo `.lpr.json`."""
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

    manifiesto = leer_canonico(paquete / "manifiesto.json")
    receptor = _publica(clave_publica)
    efimera = X25519PrivateKey.generate()
    efimera_cruda, receptor_crudo, sal = _crudo(efimera.public_key()), _crudo(receptor), secrets.token_bytes(32)
    clave, prefijo = _derivar(efimera.exchange(receptor), sal, efimera_cruda, receptor_crudo)
    creado = dt.datetime.now(dt.timezone.utc)
    cabecera = canonico({"formato": FORMATO_RESPALDO, "receptor": sha256_bytes(receptor_crudo)[:16],
                         "efimera": efimera_cruda.hex(), "sal": sal.hex(), "bloque": BLOQUE, "contenido": "tar-pax",
                         "generacion": manifiesto["id"], "alcance": manifiesto["alcance"],
                         "creado_en": creado.isoformat()})
    destino.mkdir(parents=True, exist_ok=True)
    nombre = f"{creado:%Y%m%dT%H%M%S%fZ}-{manifiesto['id']}.lpr"
    final, temporal = destino / nombre, destino / f".{nombre}.{secrets.token_hex(8)}.tmp"
    with open(temporal, "xb") as salida:
        salida.write(MAGIA + struct.pack(">I", len(cabecera)) + cabecera)
        cifrador = _Cifrador(salida, clave, prefijo, cabecera)
        _tar(paquete, cifrador)
        cifrador.cerrar()
        salida.flush()
        os.fsync(salida.fileno())
    os.link(temporal, final)
    os.unlink(temporal)
    tam, sha = sha256_archivo(final)
    catalogo = {"archivo": nombre, "bytes": tam, "sha256": sha, "generacion": manifiesto["id"],
                "alcance": manifiesto["alcance"], "creado_en": creado.isoformat(),
                "receptor": sha256_bytes(receptor_crudo)[:16], "formato": FORMATO_RESPALDO}
    escribir_exclusivo(destino / f"{nombre}.json", canonico(catalogo))
    return catalogo


def comprobar_sin_descifrar(archivo: Path) -> dict:
    """Tamano y SHA-256 del cifrado frente a su catalogo (sin la clave privada)."""
    catalogo = leer_canonico(archivo.with_name(archivo.name + ".json"))
    if sha256_archivo(archivo) != (catalogo["bytes"], catalogo["sha256"]) or catalogo["archivo"] != archivo.name:
        raise GeneracionNoValida("el respaldo no coincide con su catalogo")
    return catalogo


def descifrar(archivo: Path, clave_privada: Path, destino: Path) -> Path:
    """Descifra y extrae el paquete en `destino` (carpeta NUEVA). Devuelve la carpeta del paquete."""
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    privada = _privada(clave_privada)
    destino.mkdir(parents=True, exist_ok=False)
    os.chmod(destino, 0o700)
    with open(archivo, "rb") as f:
        if f.read(len(MAGIA)) != MAGIA:
            raise GeneracionNoValida("no es un respaldo e104")
        (largo,) = struct.unpack(">I", f.read(4))
        if largo > MAXIMO_CABECERA:
            raise GeneracionNoValida("cabecera de respaldo demasiado grande")
        cabecera = f.read(largo)
        datos = json.loads(cabecera)
        if canonico(datos) != cabecera or datos.get("formato") != FORMATO_RESPALDO:
            raise GeneracionNoValida("cabecera de respaldo no valida")
        receptor_crudo = _crudo(privada.public_key())
        if datos["receptor"] != sha256_bytes(receptor_crudo)[:16]:
            raise GeneracionNoValida("el respaldo es para otra clave")
        efimera = bytes.fromhex(datos["efimera"])
        clave, prefijo = _derivar(privada.exchange(X25519PublicKey.from_public_bytes(efimera)),
                                  bytes.fromhex(datos["sal"]), efimera, receptor_crudo)
        aes, contador, final = AESGCM(clave), 0, False
        claro = destino / ".contenido.tar"
        with open(claro, "xb") as tar_salida:
            while not final:
                encabezado = f.read(4)
                if len(encabezado) != 4:
                    raise GeneracionNoValida("respaldo truncado (falta el bloque final)")
                (n,) = struct.unpack(">I", encabezado)
                if n > datos["bloque"] + 16:
                    raise GeneracionNoValida("bloque de respaldo demasiado grande")
                cifrado = f.read(n)
                nonce = prefijo + struct.pack(">I", contador)
                for es_final in (False, True):
                    try:
                        tar_salida.write(aes.decrypt(nonce, cifrado, _asociados(cabecera, contador, es_final)))
                        final = es_final
                        break
                    except InvalidTag:
                        continue
                else:
                    raise GeneracionNoValida(f"bloque {contador} del respaldo alterado o fuera de orden")
                contador += 1
            if f.read(1):
                raise GeneracionNoValida("datos tras el bloque final del respaldo")
    with tarfile.open(claro, mode="r:") as tar:
        nombres = tar.getnames()
        raiz = {n.split("/", 1)[0] for n in nombres}
        if len(raiz) != 1 or raiz != {datos["generacion"]}:
            raise GeneracionNoValida("el contenido del respaldo no es un unico paquete")
        tar.extractall(destino, filter="data")
    claro.unlink()
    return destino / datos["generacion"]


# ---------------------------------------------------------------------------
# Restauracion aislada (R-L)
# ---------------------------------------------------------------------------

@dataclass
class Restauracion:
    paquete: Path
    base: str
    almacenes: Path
    manifiesto: dict


ESTADO = "RESTAURACION.json"


class RestauracionFallida(GeneracionNoValida):
    """La restauracion no es utilizable; `diagnostico` dice que se limpio y que queda (solo recursos propios)."""

    def __init__(self, motivo: str, diagnostico: dict):
        super().__init__(motivo)
        self.diagnostico = diagnostico


def _escribir_estado(destino: Path, datos: dict) -> None:
    temporal = destino / f".{ESTADO}.{secrets.token_hex(8)}.tmp"
    with open(temporal, "xb") as f:
        f.write(canonico(datos))
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporal, destino / ESTADO)


def estado_de_restauracion(destino: Path) -> dict:
    ruta = destino / ESTADO
    if ruta.is_symlink() or not ruta.is_file() or ruta.stat().st_size > 64 * 1024:
        raise GeneracionNoValida(f"{destino.name}: sin estado de restauracion valido")
    return json.loads(ruta.read_text(encoding="utf-8"))


def comprobar_restauracion(destino: Path) -> dict:
    """Unica puerta para USAR una restauracion: exige `estado = completa` (una fallida o en curso no vale)."""
    estado = estado_de_restauracion(destino)
    if estado.get("estado") != "completa":
        raise GeneracionNoValida(f"restauracion {estado.get('estado')}: no utilizable ({estado.get('motivo')})")
    return estado


def _recuperar_restauracion(admin, destino: Path, base: str, im) -> dict:
    """`destino` ya existe: solo se retira si es una restauracion PROPIA no completa (marca hermana con el
    intento de su estado; base con el ajuste de ese intento). Si no, se rechaza explicando por que."""
    try:
        estado = estado_de_restauracion(destino)
        intento = estado.get("intento")
        if ar.intento_de(destino, destino.parent) != intento:
            raise ar.NoPropia("la marca de propiedad no es la del estado")
    except (ar.NoPropia, GeneracionNoValida, ValueError, OSError) as error:
        raise GeneracionNoValida(f"el destino {destino.name} ya existe y no es una restauracion propia "
                                 f"recuperable ({error}); no se toca") from error
    if estado.get("estado") == "completa":
        raise GeneracionNoValida(f"el destino {destino.name} contiene una restauracion completa; no se sobrescribe")
    restos = []
    anterior = estado.get("base")
    if anterior and im._existe_base(admin, anterior):
        if not im.borrar_base_propia(admin, anterior, im.AJUSTE_RESTAURACION, intento):
            raise GeneracionNoValida(f"la base {anterior} del intento anterior existe sin prueba de propiedad; "
                                     "no se toca (retirela a mano)")
        restos.append(anterior)
    ar.borrar_propia(destino, destino.parent, intento)
    restos.append(destino.name)
    return {"intento_anterior": intento, "estado_anterior": estado.get("estado"), "retirados": restos}


def restaurar(archivo: Path, clave_privada: Path, clave_publica_firma: Path, destino: Path, url_admin: str,
              base: str | None = None, *, espera_exclusion: float = 0.0,
              fase=lambda _: None) -> Restauracion:
    """Descifra, verifica y restaura en una base NUEVA y una carpeta NUEVA. Nunca toca la base ni los
    almacenes de origen, ni la tarea programada.

    E104-RES-05: todo el recorrido (descifrado, base, migracion, carga y COPIA FINAL de almacenes) esta bajo
    la misma limpieza. `destino/RESTAURACION.json` dice `en_curso` desde el principio, `fallida` (con motivo y
    lo que no se pudo limpiar) si algo falla y `completa` solo al final; `comprobar_restauracion` es la puerta
    de uso. Solo se borran recursos PROPIOS: la carpeta creada con marca de este intento y la base creada en
    esta llamada (mismo OID, duena = rol actual, ajuste `loteria.restauracion` = intento). Un `destino` que
    quedo de un intento propio fallido o interrumpido se recupera al repetir; uno ajeno se rechaza explicando
    por que. Comparte la exclusion del servidor con el importador."""
    from app.infrastructure.generaciones import importacion as im
    from app.infrastructure.generaciones.verificacion import verificar

    if base is not None and not base.startswith(("rest_", "prueba_")):
        raise GeneracionNoValida("la base restaurada debe llamarse rest_* o prueba_* (nunca la de origen)")
    with bl.conectar(im._url_con_base(url_admin, "postgres"), autocommit=True) as admin, \
            im.Exclusion(admin, espera_exclusion):
        recuperado = None
        if os.path.lexists(destino):
            recuperado = _recuperar_restauracion(admin, destino, base or "", im)
        intento = secrets.token_hex(16)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino = ar.crear_propia(destino, intento)
        estado = {"estado": "en_curso", "intento": intento, "base": None, "respaldo": archivo.name,
                  "inicio": dt.datetime.now(dt.timezone.utc).isoformat(), "recuperado": recuperado}
        _escribir_estado(destino, estado)
        creada, oid = None, None
        try:
            paquete = descifrar(archivo, clave_privada, destino / "paquete")
            manifiesto = verificar(paquete, clave_publica_firma,
                                   alcance=leer_canonico(paquete / "manifiesto.json")["alcance"])
            nombre = base or f"rest_{manifiesto['id']}"
            if not nombre.startswith(("rest_", "prueba_")):
                raise GeneracionNoValida("la base restaurada debe llamarse rest_* o prueba_* (nunca la de origen)")
            if im._existe_base(admin, nombre):
                raise GeneracionNoValida(f"la base {nombre} ya existe: la restauracion nunca la sobrescribe")
            estado["base"] = nombre
            _escribir_estado(destino, estado)  # antes de crearla: un corte deja constancia de su nombre
            admin.execute(f"CREATE DATABASE {im._ident(nombre)} TEMPLATE template0 ENCODING 'UTF8'")
            creada, oid = nombre, im._oid(admin, nombre)
            im.marcar_base(admin, nombre, im.AJUSTE_RESTAURACION, intento)
            admin.execute(f"REVOKE ALL ON DATABASE {im._ident(nombre)} FROM PUBLIC")
            fase("base_creada")
            url = im._url_con_base(url_admin, nombre)
            im._migrar(url, manifiesto["esquema"]["revision_alembic"])
            with bl.conectar(url) as c:
                if bl.huella_esquema(c) != manifiesto["esquema"]["huella"]:
                    raise GeneracionNoValida("el esquema migrado no es el del respaldo")
                bl.restaurar(c, paquete / "base", manifiesto["base"], bl.tablas(c))
                c.commit()
            fase("filas_cargadas")
            almacenes = destino / "almacenes"
            for ruta in sorted(manifiesto["archivos"]):
                if ruta.startswith("archivos/"):
                    ar.copiar_verificado(paquete / ruta, almacenes / ruta[len("archivos/"):])
            for nombre_a in manifiesto["almacenes"]:
                (almacenes / nombre_a).mkdir(parents=True, exist_ok=True)
            fase("almacenes")
            estado.update(estado="completa", fin=dt.datetime.now(dt.timezone.utc).isoformat(), id=manifiesto["id"])
            _escribir_estado(destino, estado)
            return Restauracion(paquete, nombre, almacenes, manifiesto)
        except BaseException as error:
            motivo = f"{type(error).__name__}: {str(error)[:300]}"
            diagnostico = {"motivo": motivo, "base": creada, "base_borrada": None, "carpeta_borrada": None,
                           "pendiente": []}
            try:  # primero se deja constancia: la carpeta nunca parece utilizable
                _escribir_estado(destino, {**estado, "estado": "fallida", "motivo": motivo})
            except Exception as fallo:
                diagnostico["pendiente"].append(f"no se pudo escribir el estado fallida: {type(fallo).__name__}")
            if creada:
                try:
                    diagnostico["base_borrada"] = im.borrar_base_propia(admin, creada, im.AJUSTE_RESTAURACION,
                                                                        intento, oid)
                    if not diagnostico["base_borrada"] and im._existe_base(admin, creada):
                        diagnostico["pendiente"].append(f"base {creada}: sin prueba de propiedad, no se toca")
                except Exception as fallo:
                    diagnostico["base_borrada"] = False
                    diagnostico["pendiente"].append(f"base {creada}: {type(fallo).__name__}: {fallo}")
            try:
                ar.borrar_propia(destino, destino.parent, intento)
                diagnostico["carpeta_borrada"] = True
            except Exception as fallo:
                diagnostico["carpeta_borrada"] = False
                diagnostico["pendiente"].append(f"carpeta {destino.name}: {type(fallo).__name__}: {fallo}")
            if diagnostico["pendiente"]:
                try:  # sigue marcada `fallida`; repetir la restauracion en el mismo destino la recupera
                    _escribir_estado(destino, {**estado, "estado": "fallida", "motivo": motivo,
                                               "pendiente": diagnostico["pendiente"]})
                except Exception:
                    pass
            raise RestauracionFallida(f"restauracion fallida ({motivo}); limpieza: {diagnostico}",
                                      diagnostico) from error


# ---------------------------------------------------------------------------
# Retencion (politica configurable; por defecto, la propuesta de la v2: 14 diarios, 8 semanales, 12 mensuales)
# ---------------------------------------------------------------------------

def plan_de_retencion(destino: Path, diarios: int = 14, semanales: int = 8, mensuales: int = 12,
                      minimo: int = 1) -> dict:
    """Conserva el mas reciente de cada uno de los ultimos `diarios` dias, `semanales` semanas ISO y `mensuales`
    meses, y siempre los `minimo` mas recientes. Solo considera pares `.lpr` + `.lpr.json` coherentes: un archivo
    sin catalogo, alterado o desconocido NUNCA se propone borrar (se informa)."""
    if min(diarios, semanales, mensuales) < 0 or minimo < 1:
        raise ValueError("politica de retencion no valida")
    validos, informados = [], []
    for ruta in sorted(destino.glob("*.lpr")):
        try:
            catalogo = comprobar_sin_descifrar(ruta)
            validos.append((dt.datetime.fromisoformat(catalogo["creado_en"]), ruta.name))
        except (GeneracionNoValida, OSError, ValueError, KeyError):
            informados.append(ruta.name)
    validos.sort(reverse=True)
    conservar = {n for _, n in validos[:minimo]}
    for cubos, clave in ((diarios, lambda f: f.date()), (semanales, lambda f: f.isocalendar()[:2]),
                         (mensuales, lambda f: (f.year, f.month))):
        vistos = []
        for fecha, nombre in validos:
            k = clave(fecha)
            if k not in vistos:
                vistos.append(k)
                if len(vistos) <= cubos:
                    conservar.add(nombre)
    return {"conservar": sorted(conservar), "borrar": sorted(n for _, n in validos if n not in conservar),
            "no_considerados": informados,
            "politica": {"diarios": diarios, "semanales": semanales, "mensuales": mensuales, "minimo": minimo}}


def aplicar_retencion(destino: Path, plan: dict) -> list[str]:
    borrados = []
    for nombre in plan["borrar"]:
        ruta = destino / nombre
        comprobar_sin_descifrar(ruta)  # vuelve a comprobar justo antes de borrar
        ruta.unlink()
        ruta.with_name(nombre + ".json").unlink()
        borrados.append(nombre)
    return borrados
