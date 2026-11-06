"""Adaptador Linux/Docker para ENSAYO. Nunca usa down, rm, prune ni borra datos.

Solo opera sobre proyectos con propietario, plan, generación, imágenes y
montajes comprobados. Los comandos son listas cerradas, sin intérprete shell.
"""
from __future__ import annotations

import http.client
import ipaddress
import os
import re
import secrets
import signal
import socket
import ssl
import stat
import subprocess
import time
from pathlib import Path

from .estado import Almacen
from .infraestructura import MANTENIMIENTO, PREFIJO, componer, etiquetas, montajes, nginx
from .modelo import PRIVADAS, Plan, Rechazo, canonico, json_estricto


# La imagen mínima solo contiene Python; no requiere curl ni un shell.
SONDA_API = """import json,os,urllib.request
from pathlib import Path
k=Path(os.environ['PASARELA_CLAVE_API_ARCHIVO']).read_bytes()
assert 32 <= len(k.strip()) <= 256
u=os.environ['PASARELA_API_URL']+'/api/v1/estado'
r=urllib.request.Request(u,headers={'X-API-Key':k.decode('ascii').strip()})
with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(r,timeout=3) as s:
    b=s.read(65537)
assert len(b)<=65536
d=json.loads(b)
assert d['base']=='disponible'
print(json.dumps(d))
"""
SONDA_VINCULO = """import json
from app.api.publica.privada import app
print(json.dumps(app.state.generacion))
"""


class Docker:
    def __init__(self, almacen: Almacen, propietario: str, *, ejecutar=None, reloj=time.monotonic,
                 dormir=time.sleep, sonda_tls=None, sonda_cierre=None):
        self.a, self.propietario = almacen, propietario
        self.ejecutar = ejecutar or self._ejecutar
        self.reloj, self.dormir = reloj, dormir
        self.sonda_tls = sonda_tls or self._tls
        self.sonda_cierre = sonda_cierre or self._cierre
        self.ultimo_estado = None

    def _ejecutar(self, argumentos: list[str], plazo: float) -> bytes:
        restante = min(45, plazo - self.reloj())
        if restante <= 0:
            raise Rechazo("plazo_docker")
        proceso = None
        try:
            proceso = subprocess.Popen(["docker", "--host", "unix:///var/run/docker.sock", *argumentos],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True)
            salida, _ = proceso.communicate(timeout=restante)
        except (OSError, subprocess.TimeoutExpired) as error:
            if proceso is not None:
                try:
                    os.killpg(proceso.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proceso.communicate(timeout=5)
            raise Rechazo("docker_no_completo") from error
        except BaseException:
            if proceso is not None:
                try:
                    os.killpg(proceso.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proceso.communicate(timeout=5)
            raise
        # No devolver stderr: los errores de un servicio podrían contener secretos.
        if proceso.returncode != 0 or len(salida) > 1048576:
            raise Rechazo("docker_rechazado")
        return salida

    def _raiz(self):
        st = self.a.ruta.lstat()
        propio = os.fstat(self.a.fd)
        if not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino) != (propio.st_dev, propio.st_ino):
            raise Rechazo("control_movido")

    def carpeta(self, p: Plan) -> Path:
        self._raiz()
        return self.a.ruta / ("r-" + p.id)

    def _carpeta(self, p: Plan, crear: bool = False) -> int:
        self._raiz()
        nombre = "r-" + p.id
        nueva = False
        if crear:
            try:
                os.mkdir(nombre, 0o755, dir_fd=self.a.fd)
                nueva = True
            except FileExistsError:
                pass
        fd = os.open(nombre, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.a.fd)
        if nueva:
            os.fchmod(fd, 0o755)
        st = os.fstat(fd)
        # El directorio montado debe ser atravesable por nginx (UID 101).
        # El control padre sigue en 0700 y los archivos solo contienen referencias.
        if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o755:
            os.close(fd)
            raise Rechazo("release_no_es_propia")
        return fd

    @staticmethod
    def _leer(fd: int, nombre: str) -> bytes | None:
        try:
            archivo = os.open(nombre, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        except FileNotFoundError:
            return None
        with os.fdopen(archivo, "rb") as entrada:
            st = os.fstat(entrada.fileno())
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1
                    or stat.S_IMODE(st.st_mode) != 0o644):
                raise Rechazo("configuracion_no_es_propia")
            return entrada.read(262145)

    @staticmethod
    def _escribir(fd: int, nombre: str, datos: bytes):
        temporal = "tmp-" + secrets.token_hex(16)
        archivo = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=fd)
        try:
            with os.fdopen(archivo, "wb") as salida:
                os.fchmod(salida.fileno(), 0o644)
                salida.write(datos)
                salida.flush()
                os.fsync(salida.fileno())
            os.replace(temporal, nombre, src_dir_fd=fd, dst_dir_fd=fd)
            os.fsync(fd)
        finally:
            try:
                os.unlink(temporal, dir_fd=fd)
            except FileNotFoundError:
                pass

    def materializar(self, p: Plan):
        fd = self._carpeta(p, crear=True)
        try:
            for nombre, contenido in self._esperados(p).items():
                antes = self._leer(fd, nombre)
                if antes is not None and antes != contenido:
                    raise Rechazo("configuracion_alterada")
                if antes is None:
                    self._escribir(fd, nombre, contenido)
            mantenimiento = self._leer(fd, "mantenimiento.conf")
            if mantenimiento is None:
                self._escribir(fd, "mantenimiento.conf", MANTENIMIENTO.encode())
            elif mantenimiento not in (MANTENIMIENTO.encode(), b"# abierto\n"):
                raise Rechazo("mantenimiento_alterado")
        finally:
            os.close(fd)

    def _esperados(self, p: Plan) -> dict[str, bytes]:
        return {"compose.json": canonico(componer(p, self.propietario, str(self.carpeta(p)))),
                "nginx.conf": nginx(p).encode(), "entorno-vacio": b""}

    def _comprobar_configuracion(self, p: Plan):
        fd = self._carpeta(p)
        try:
            if any(self._leer(fd, n) != c for n, c in self._esperados(p).items()):
                raise Rechazo("configuracion_alterada")
        finally:
            os.close(fd)

    def _compose(self, p: Plan, argumentos: list[str], plazo: float):
        self._comprobar_configuracion(p)
        c = str(self.carpeta(p))
        return self.ejecutar(["compose", "--env-file", c + "/entorno-vacio", "--project-directory", c,
                             "--project-name", p.proyecto(self.propietario), "-f", c + "/compose.json",
                             *argumentos], plazo)

    def contenedores(self, p: Plan, plazo: float) -> dict[str, dict]:
        proyecto = p.proyecto(self.propietario)
        salida = self.ejecutar(["ps", "-aq", "--filter", "label=com.docker.compose.project=" + proyecto], plazo)
        ids = salida.decode("ascii").split()
        if not ids:
            return {}
        if len(ids) > 3 or len(set(ids)) != len(ids) or any(not re.fullmatch(r"[a-f0-9]{12,64}", i) for i in ids):
            raise Rechazo("conjunto_de_contenedores")
        datos = json_estricto(self.ejecutar(["inspect", *ids], plazo), 1048576)
        if not isinstance(datos, list) or len(datos) != len(ids):
            raise Rechazo("inspeccion_de_contenedores")
        resultado = {}
        esperadas = etiquetas(p, self.propietario)
        imagenes = {"api": p.imagen_api, "pasarela": p.imagen_pasarela, "proxy": p.imagen_proxy}
        for d in datos:
            try:
                conf, hc = d["Config"], d["HostConfig"]
                labs = conf["Labels"]
                nombre = labs["com.docker.compose.service"]
                if (nombre not in imagenes or nombre in resultado
                        or not any(d["Id"].startswith(i) for i in ids)
                        or labs.get("com.docker.compose.project") != proyecto
                        or any(labs.get(k) != v for k, v in esperadas.items())
                        or conf["Image"] != imagenes[nombre]
                        or conf["User"] != ("101:101" if nombre == "proxy" else "10001:10001")
                        or hc["Privileged"] or not hc["ReadonlyRootfs"]
                        or hc.get("NetworkMode") == "host"):
                    raise Rechazo("contenedor_no_es_propio")
                reales = {m["Destination"]: m for m in d["Mounts"] if m["Type"] == "bind"}
                esperados = montajes(p, str(self.carpeta(p)), nombre)
                if set(reales) != set(esperados) or any(reales[k]["RW"] or reales[k]["Source"] != v
                                                       for k, v in esperados.items()):
                    raise Rechazo("montajes_de_otra_generacion")
                declarado = componer(p, self.propietario, str(self.carpeta(p)))["services"][nombre]
                entorno = dict(v.split("=", 1) for v in conf["Env"])
                if (len(entorno) != len(conf["Env"])
                        or any(entorno.get(k) != v for k, v in declarado["environment"].items())
                        or conf.get("Entrypoint") != declarado["entrypoint"]
                        or (conf.get("Cmd") or []) != declarado["command"]):
                    raise Rechazo("proceso_de_otro_plan")
                puertos = hc.get("PortBindings") or {}
                puerto_esperado = {"18443/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(p.puerto)}]} if nombre == "proxy" else {}
                if puertos != puerto_esperado:
                    raise Rechazo("puerto_fuera_del_plan")
                redes = d["NetworkSettings"]["Networks"]
                esperadas_red = {p.red_datos if n == "datos" else proyecto + "_" + n: v.get("ipv4_address")
                                 for n, v in declarado["networks"].items()}
                if set(redes) - set(esperadas_red) or (d["State"]["Running"] and (
                        set(redes) != set(esperadas_red) or any(ip and redes[n].get("IPAddress") != ip
                                                               for n, ip in esperadas_red.items()))):
                    raise Rechazo("redes_fuera_del_plan")
                tmpfs = {"/tmp", "/var/cache/nginx"} if nombre == "proxy" else {"/tmp"}
                if any(m["Type"] != "bind" and not (m["Type"] == "tmpfs" and m["Destination"] in tmpfs)
                       for m in d["Mounts"]):
                    raise Rechazo("volumen_fuera_del_plan")
                resultado[nombre] = d
            except (KeyError, TypeError, AttributeError, ValueError) as error:
                raise Rechazo("inspeccion_de_contenedores") from error
        if len({d["Id"] for d in resultado.values()}) != len(ids):
            raise Rechazo("identidades_de_contenedores")
        return resultado

    @staticmethod
    def _ruta_existente(ruta: Path, directorio: bool):
        for parte in (ruta, *ruta.parents):
            if parte.is_symlink():
                raise Rechazo("montaje_con_enlace")
        st = ruta.stat()
        if (directorio and not stat.S_ISDIR(st.st_mode)) or (not directorio and not stat.S_ISREG(st.st_mode)):
            raise Rechazo("montaje_no_valido")

    def preparar(self, p: Plan, plazo: float):
        from app.infrastructure.generaciones.importacion import verificar_publicada
        for s in ("api", "pasarela", "proxy"):
            for origen in montajes(p, str(self.carpeta(p)), s).values():
                if origen != str(self.carpeta(p)):
                    self._ruta_existente(Path(origen), origen in (p.directorio_generacion, p.pki_proxy))
        for nombre in ("servidor.crt", "servidor.key", "ca-consulta.crt", "crl.pem"):
            self._ruta_existente(Path(p.pki_proxy) / nombre, False)
        for nombre in ("ca-servidor.crt", "cliente.crt", "cliente.key"):
            self._ruta_existente(Path(p.pki_sonda) / nombre, False)
        v = verificar_publicada(Path(p.directorio_generacion), Path(p.clave_publica))
        if (v["sha256_manifiesto"] != p.manifiesto_sha256 or v["manifiesto"]["codigo"]["huella_app"] != p.huella_app
                or v["manifiesto"]["id"] != p.generacion):
            raise Rechazo("generacion_de_otro_plan")
        redes = json_estricto(self.ejecutar(["network", "inspect", p.red_datos], plazo), 1048576)
        try:
            red = redes[0]
            subredes = [ipaddress.ip_network(c["Subnet"]) for c in red["IPAM"]["Config"]]
            if (len(redes) != 1 or red["Name"] != p.red_datos or not red["Internal"]
                    or red["Labels"].get(PREFIJO + ".modo") != "ensayo"
                    or not any(ipaddress.ip_address(p.ip_datos_api) in r for r in subredes)
                    or any(r.version != 4 or not any(r.subnet_of(v) for v in PRIVADAS) or
                           any(r.overlaps(ipaddress.ip_network(x)) for x in (p.red_interna, p.red_servicio))
                           for r in subredes)):
                raise Rechazo("red_de_datos_no_es_de_ensayo")
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise Rechazo("red_de_datos_no_valida") from error
        self.materializar(p)
        self.contenedores(p, plazo)  # inspección completa antes de que Compose pueda sustituir uno

    def arrancar(self, p: Plan, plazo: float):
        self.contenedores(p, plazo)
        self._compose(p, ["up", "-d", "--no-build", "--pull", "never", "--no-deps", "api", "pasarela"], plazo)

    def validar(self, p: Plan, plazo: float):
        ultimo = None
        while self.reloj() < plazo:
            try:
                cs = self.contenedores(p, plazo)
                if not all(n in cs and cs[n]["State"]["Running"] for n in ("api", "pasarela")):
                    raise Rechazo("pareja_no_iniciada")
                vinculo = json_estricto(self.ejecutar(["exec", cs["api"]["Id"], "python", "-B", "-c", SONDA_VINCULO], plazo))
                if vinculo != {"id": p.generacion, "sha256_manifiesto": p.manifiesto_sha256,
                               "huella_app": p.huella_app, "revision_esquema": "0006"}:
                    raise Rechazo("vinculo_de_otra_generacion")
                d = json_estricto(self.ejecutar(["exec", cs["pasarela"]["Id"], "python", "-B", "-c", SONDA_API], plazo))
                if not isinstance(d, dict) or d.get("base") != "disponible":
                    raise Rechazo("base_no_disponible")
                self.ultimo_estado = d
                return
            except Rechazo as error:
                ultimo = error
                self.dormir(min(0.5, max(0, plazo - self.reloj())))
        raise Rechazo("pareja_no_validada") from ultimo

    def mantenimiento(self, p: Plan, cerrar: bool, plazo: float):
        cs = self.contenedores(p, plazo)
        if "proxy" not in cs:
            if cerrar:
                return
            raise Rechazo("proxy_ausente")
        self._comprobar_configuracion(p)
        fd = self._carpeta(p)
        try:
            if self._leer(fd, "mantenimiento.conf") not in (MANTENIMIENTO.encode(), b"# abierto\n"):
                raise Rechazo("mantenimiento_alterado")
            self._escribir(fd, "mantenimiento.conf", MANTENIMIENTO.encode() if cerrar else b"# abierto\n")
        finally:
            os.close(fd)
        if cs["proxy"]["State"]["Running"]:
            for orden in (["nginx", "-c", "/etc/nginx/ensayo/nginx.conf", "-t"],
                          ["nginx", "-c", "/etc/nginx/ensayo/nginx.conf", "-s", "reload"]):
                self.ejecutar(["exec", cs["proxy"]["Id"], *orden], plazo)
            if cerrar:
                # reload es asíncrono. No contar el drenaje hasta observar el
                # 503 del nuevo trabajador, con TLS y certificado de cliente.
                limite = min(plazo, self.reloj() + 10)
                while True:
                    try:
                        self.sonda_cierre(p, limite)
                        break
                    except (OSError, ValueError, http.client.HTTPException):
                        if self.reloj() >= limite:
                            raise Rechazo("mantenimiento_no_confirmado") from None
                        self.dormir(min(0.1, max(0, limite - self.reloj())))

    def drenar(self, p: Plan, plazo: float):
        # nginx limita sus trabajadores anteriores; se espera todo ese límite
        # antes de parar el par. La prueba nativa de este límite sigue pendiente.
        cs = self.contenedores(p, plazo)
        if "proxy" not in cs or not cs["proxy"]["State"]["Running"]:
            return
        fin = self.reloj() + p.drenaje_s
        if fin >= plazo:
            raise Rechazo("sin_plazo_para_drenar")
        while self.reloj() < fin:
            self.dormir(min(0.5, fin - self.reloj()))

    def detener(self, p: Plan, plazo: float):
        cs = self.contenedores(p, plazo)
        ids = [cs[n]["Id"] for n in ("proxy", "pasarela", "api") if n in cs and cs[n]["State"]["Running"]]
        if ids:
            self.ejecutar(["stop", "--time", "5", *ids], plazo)
        if any(d["State"]["Running"] for d in self.contenedores(p, plazo).values()):
            raise Rechazo("contenedor_sigue_activo")

    def publicar(self, p: Plan, plazo: float):
        self.contenedores(p, plazo)
        self._compose(p, ["up", "-d", "--no-build", "--pull", "never", "--no-deps", "proxy"], plazo)

    def _peticion_tls(self, p: Plan, plazo: float):
        if self.reloj() >= plazo:
            raise Rechazo("plazo_sonda")
        contexto = ssl.create_default_context(cafile=p.pki_sonda + "/ca-servidor.crt")
        contexto.load_cert_chain(p.pki_sonda + "/cliente.crt", p.pki_sonda + "/cliente.key")
        espera = max(0.01, min(3, plazo - self.reloj()))
        conexion = http.client.HTTPSConnection(p.host, p.puerto, context=contexto, timeout=espera)
        # TCP exclusivamente local; SNI y validación del certificado conservan el host del plan.
        conexion._create_connection = lambda *args, **kw: socket.create_connection(("127.0.0.1", p.puerto), espera)
        try:
            conexion.request("GET", "/api/v1/estado", headers={"Connection": "close"})
            r = conexion.getresponse()
            datos = r.read(65537)
            if len(datos) > 65536:
                raise Rechazo("sonda_demasiado_grande")
            return r.status, r.getheader("Content-Type", "").split(";")[0], r.getheader("Retry-After"), datos
        finally:
            conexion.close()

    def _tls(self, p: Plan, plazo: float) -> dict:
        estado, tipo, _, datos = self._peticion_tls(p, plazo)
        if estado != 200 or tipo != "application/json":
            raise Rechazo("sonda_mtls_rechazada")
        d = json_estricto(datos, 65536)
        if not isinstance(d, dict) or d.get("base") != "disponible":
            raise Rechazo("base_no_disponible")
        return d

    def _cierre(self, p: Plan, plazo: float):
        estado, _, reintento, _ = self._peticion_tls(p, plazo)
        if estado != 503 or reintento != "30":
            raise Rechazo("mantenimiento_no_confirmado")

    def sonda(self, p: Plan, plazo: float):
        cs = self.contenedores(p, plazo)
        if set(cs) != {"proxy", "pasarela", "api"} or not all(d["State"]["Running"] for d in cs.values()):
            raise Rechazo("servicio_incompleto")
        try:
            self.ultimo_estado = self.sonda_tls(p, plazo)
        except (OSError, http.client.HTTPException, ValueError) as error:
            raise Rechazo("sonda_mtls_fallida") from error
