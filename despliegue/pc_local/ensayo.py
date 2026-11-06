"""Ensayo E10.7 de una sola ejecucion en Ubuntu/WSL, con recursos nuevos.

El lanzador de PowerShell entrega dos ZIP por stdin: un git archive de la base
integrada y los cambios revisados. No lee el arbol de trabajo ni datos del PC.
No instala, construye, descarga imagenes, cambia Git ni habilita servicios.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import io
import ipaddress
import json
import os
import re
import secrets
import shutil
import signal
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

BASE = "4aaca446c5ea79975683220da0037e2569fbe28e"
IMAGENES = {
    "api": "sha256:8894aa842c444e8e638d96899b0a4e97df908088843daa5e33c8d38bdf2e8adc",
    "pasarela": "sha256:aca6a94ef3e1a4fa0ef75589610afa10603d778864cbf846c1804a79a3121238",
    "preparacion": "sha256:3f1ef0b339e50f76326297bb15367eb40216f1bd6df3a85f07d6c71cd2ea2530",
    "proxy": "docker.io/library/nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de",
    "postgres": "docker.io/library/postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab",
}
ETIQUETA = "es.loteria.e107.ejecucion"
LIMITE_ZIP = 64 * 1024 * 1024


class Detenido(ValueError):
    pass


def extraer(datos: bytes, destino: Path, *, cambios: bool = False) -> None:
    if len(datos) > LIMITE_ZIP:
        raise Detenido("archivo_fuera_de_limite")
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        entradas = z.infolist()
        if len(entradas) > 5000 or sum(e.file_size for e in entradas) > LIMITE_ZIP:
            raise Detenido("fuentes_fuera_de_limite")
        vistos = set()
        for e in entradas:
            p = PurePosixPath(e.filename)
            if (not p.parts or p.is_absolute() or any(s in ("..", ".") for s in p.parts)
                    or p.as_posix() != e.filename.rstrip("/")
                    or "\\" in e.filename or "\x00" in e.filename or ":" in e.filename
                    or p.parts[0] not in ("backend", "despliegue")
                    or stat.S_ISLNK(e.external_attr >> 16) or e.filename in vistos
                    or (cambios and p.parts[:2] == ("backend", "app"))):
                raise Detenido("ruta_de_fuentes_rechazada")
            vistos.add(e.filename)
        # Validar todo el inventario ANTES de escribir un archivo.
        for e in entradas:
            p = destino.joinpath(*PurePosixPath(e.filename).parts)
            if e.is_dir():
                p.mkdir(mode=0o755, parents=True, exist_ok=True)
            else:
                p.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                p.write_bytes(z.read(e))
                p.chmod(0o644)


def ejecutar_docker(args: list[str], *, entrada: bytes | None = None, timeout: float = 60) -> bytes:
    proceso = None
    try:
        proceso = subprocess.Popen(["docker", "--host", "unix:///var/run/docker.sock", *args],
            stdin=subprocess.PIPE if entrada is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        salida, _ = proceso.communicate(input=entrada, timeout=timeout)
    except BaseException:
        if proceso is not None:
            try:
                os.killpg(proceso.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proceso.communicate(timeout=5)
        raise Detenido("comando_local_no_completo") from None
    if proceso.returncode or len(salida) > 1048576:
        raise Detenido("comando_local_rechazado")
    return salida


def json_docker(args, **kw):
    return json.loads(ejecutar_docker(args, **kw))


def puerto_libre(puerto: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", puerto))
            return True
        except OSError:
            return False


def elegir_redes(existentes) -> tuple[str, str, str]:
    ocupadas = [ipaddress.ip_network(s, strict=False) for s in existentes]
    for _ in range(40):
        segundo = 120 + secrets.randbelow(120)
        redes = tuple(f"10.{segundo}.{i}.0/24" for i in (11, 12, 13))
        if not any(ipaddress.ip_network(r).overlaps(e) for r in redes for e in ocupadas if e.version == 4):
            return redes
    raise Detenido("sin_subredes_libres")


def _privado(ruta: Path, datos: bytes, modo: int = 0o600):
    fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, modo)
    with os.fdopen(fd, "wb") as f:
        f.write(datos)


class Ensayo:
    def __init__(self, raiz: Path):
        self.raiz, self.id = raiz, secrets.token_hex(16)
        self.fuente = raiz / "fuente"
        self.imagenes = {}
        self.red = "e105ensayoe107" + self.id
        self.auxiliares = 0
        self.pg = "e107" + self.id + "-postgres"
        self.plan = self.control = self.runtime = None
        self.informe = {"version": "e107-ensayo-pc/1", "base_codigo": BASE, "codigo": 1,
            "estado": "iniciado", "destino_elegido": "pc_del_usuario", "datos": "sinteticos",
            "produccion_autorizada": False, "fase6_intervenida": False,
            "imagenes_descargadas_o_construidas": False, "instalaciones": False,
            "exposicion": "127.0.0.1", "comprobaciones": [], "servicios_detenidos": False,
            "fecha_utc": datetime.now(timezone.utc).isoformat(), "directorio_ensayo": str(raiz),
            "pendientes": ["datos_reales_D10", "activacion_real_D11", "drenaje_y_reversion_nativos",
                "recuperacion_Windows_RW", "custodia_externa_de_respaldos", "acceso_Brave_y_confianza_CA"]}

    def etapa(self, nombre: str):
        self.informe["estado"] = nombre
        print("E107_ETAPA:" + nombre, flush=True)

    def anotar(self, nombre: str, ok: bool):
        self.informe["comprobaciones"].append({"id": nombre, "ok": bool(ok)})
        if not ok:
            raise Detenido(nombre)

    def imagenes_locales(self):
        for nombre, referencia in IMAGENES.items():
            try:
                d = json_docker(["image", "inspect", referencia])
            except (Detenido, ValueError):
                raise Detenido("imagen_local_no_disponible_" + nombre) from None
            if (not isinstance(d, list) or len(d) != 1 or d[0].get("Os") != "linux"
                    or d[0].get("Architecture") not in ("amd64", "x86_64")
                    or not re.fullmatch(r"sha256:[a-f0-9]{64}", d[0].get("Id", ""))
                    or (referencia.startswith("sha256:") and d[0]["Id"] != referencia)):
                raise Detenido("imagen_local_no_compatible")
            self.imagenes[nombre] = d[0]["Id"]
        self.informe["imagenes"] = dict(self.imagenes)

    def auxiliar(self, modo: str, *, red: bool = False, timeout: float = 120) -> dict:
        self.auxiliares += 1
        nombre = "e107" + self.id + "-preparacion-" + str(self.auxiliares)
        orden = ["create", "--pull", "never", "--name", nombre, "--label", ETIQUETA + "=" + self.id,
                 "--user", f"{os.getuid()}:{os.getgid()}", "--read-only", "--cap-drop", "ALL",
                 "--security-opt", "no-new-privileges:true", "--pids-limit", "256", "--memory", "3g",
                 "--cpus", "2", "--tmpfs", "/tmp:size=256m,mode=1777", "--restart", "no",
                 "--network", self.red if red else "none",
                 "--mount", f"type=bind,src={self.raiz},dst={self.raiz}",
                 "--mount", f"type=bind,src={self.fuente},dst={self.fuente},readonly",
                 "--workdir", str(self.fuente / "backend"), "--entrypoint", "/opt/venv/bin/python",
                 self.imagenes["preparacion"], "-B", str(self.fuente / "despliegue/pc_local/preparar.py"),
                 modo, str(self.raiz), str(self.fuente)]
        cid = ejecutar_docker(orden).decode("ascii").strip()
        if not re.fullmatch(r"[a-f0-9]{64}", cid):
            raise Detenido("id_auxiliar_no_valido")
        salida = ejecutar_docker(["start", "--attach", cid], timeout=timeout)
        filas = [l.split(b":", 1)[1] for l in salida.splitlines() if l.startswith(b"E107_PREPARACION:")]
        if len(filas) != 1:
            raise Detenido("informe_auxiliar_ausente")
        d = json.loads(filas[0])
        if not isinstance(d, dict) or d.get("codigo") != 0:
            raise Detenido("preparacion_sintetica_rechazada")
        return d

    def preparar_postgres(self):
        ids = ejecutar_docker(["network", "ls", "-q"]).decode("ascii").split()
        existentes = []
        if ids:
            for red in json_docker(["network", "inspect", *ids]):
                existentes.extend(c["Subnet"] for c in (red.get("IPAM", {}).get("Config") or []) if c.get("Subnet"))
        self.red_interna, self.red_servicio, self.red_datos = elegir_redes(existentes)
        ejecutar_docker(["network", "create", "--internal", "--subnet", self.red_datos,
            "--label", ETIQUETA + "=" + self.id, "--label", "es.loteria.e105.modo=ensayo", self.red])
        self.claves = {n: secrets.token_hex(24) for n in ("super", "propietario", "lector", "captura", "admin")}
        pg_secreto = self.raiz / "pg-password"
        _privado(pg_secreto, (self.claves["super"] + "\n").encode(), 0o444)
        pg_datos = self.raiz / "pgdatos"
        pg_datos.mkdir(mode=0o700)
        pg_ip = str(ipaddress.ip_network(self.red_datos).network_address + 30)
        ejecutar_docker(["create", "--pull", "never", "--name", self.pg,
            "--label", ETIQUETA + "=" + self.id, "--network", self.red, "--ip", pg_ip,
            "--restart", "no", "--memory", "1g", "--cpus", "1", "--pids-limit", "128",
            "--mount", f"type=bind,src={pg_datos},dst=/var/lib/postgresql/data",
            "--mount", f"type=bind,src={pg_secreto},dst=/run/secrets/password,readonly",
            "--env", "POSTGRES_PASSWORD_FILE=/run/secrets/password", "--env", "POSTGRES_DB=loteria_prueba",
            self.imagenes["postgres"]])
        ejecutar_docker(["start", self.pg])
        limite = time.monotonic() + 60
        while True:
            try:
                ejecutar_docker(["exec", self.pg, "pg_isready", "-h", "127.0.0.1", "-U", "postgres",
                                 "-d", "loteria_prueba"], timeout=5)
                break
            except Detenido:
                if time.monotonic() >= limite:
                    raise Detenido("postgres_sintetico_no_disponible") from None
                time.sleep(0.5)
        roles = {"propietario": "consulta_propietario", "lector": "consulta_lector",
                 "captura": "generaciones_captura", "admin": "generaciones_importador"}
        urls = {n: f"postgresql+psycopg://{rol}:{self.claves[n]}@{pg_ip}:5432/" +
                ("postgres" if n == "admin" else "loteria_prueba") for n, rol in roles.items()}
        _privado(self.raiz / "urls.json", json.dumps(urls).encode())
        self.urls = urls
        variables = "\\set base loteria_prueba\n" + "".join(
            f"\\set clave_{n} {self.claves[n]}\n" for n in ("propietario", "lector"))
        variables += f"\\set clave_importador {self.claves['admin']}\n"
        sql = variables + (self.fuente / "despliegue/consulta-privada/postgres/roles.sql").read_text()
        sql += (self.fuente / "despliegue/generaciones/postgres/roles.sql").read_text()
        self.psql(sql)
        self.auxiliar("migrar", red=True)
        self.psql("\\set base loteria_prueba\n" + f"\\set clave_captura {self.claves['captura']}\n" +
            (self.fuente / "despliegue/generaciones/postgres/rol-captura.sql").read_text())

    def psql(self, sql: str):
        ejecutar_docker(["exec", "-i", self.pg, "psql", "-X", "-v", "ON_ERROR_STOP=1",
            "-U", "postgres", "-d", "postgres"], entrada=sql.encode(), timeout=60)

    def activar(self, d: dict):
        from despliegue.operacion_consulta.ciclo import Motor
        from despliegue.operacion_consulta.docker import Docker
        from despliegue.operacion_consulta.estado import Almacen
        from despliegue.operacion_consulta.local import autorizar
        secretos = self.raiz / "secretos-servicio"
        secretos.mkdir(mode=0o700)
        clave, ingreso = secrets.token_hex(32), secrets.token_hex(32)
        archivos = {"api_database_url": self.urls["lector"].rsplit("/", 1)[0] + "/pub_" + d["generacion"],
            "api_claves": "e107:sha256:" + hashlib.sha256(clave.encode()).hexdigest(),
            "pasarela_clave_api": clave, "pasarela_ingreso": ingreso,
            "proxy_ingreso.conf": 'proxy_set_header X-Consulta-Ingreso "' + ingreso + '";'}
        for nombre, valor in archivos.items():
            _privado(secretos / nombre, (valor + "\n").encode(), 0o444)
        proxy, sonda = self.raiz / "pki-proxy", self.raiz / "pki-sonda"
        for carpeta, copiar in ((proxy, {"servidor.crt": "servidor.crt", "servidor.key": "servidor.key",
                    "ca-consulta.crt": "ca.crt", "crl.pem": "crl.pem"}),
                (sonda, {"ca-servidor.crt": "ca.crt", "cliente.crt": "cliente.crt", "cliente.key": "cliente.key"})):
            carpeta.mkdir(mode=0o755 if carpeta == proxy else 0o700)
            for destino, origen in copiar.items():
                _privado(carpeta / destino, (self.raiz / "pki" / origen).read_bytes(),
                         0o444 if carpeta == proxy else 0o600)
        datos = {"formato": "operacion-consulta-local/1", "modo": "ensayo", "host": "localhost", "puerto": 18443,
            "generacion": d["generacion"], "manifiesto_sha256": d["manifiesto_sha256"], "huella_app": d["huella_app"],
            "imagen_api": self.imagenes["api"], "imagen_pasarela": self.imagenes["pasarela"],
            "imagen_proxy": self.imagenes["proxy"], "red_interna": self.red_interna, "red_servicio": self.red_servicio,
            "red_datos": self.red, "ip_datos_api": str(ipaddress.ip_network(self.red_datos).network_address + 21),
            "directorio_generacion": d["directorio_generacion"], "clave_publica": d["clave_publica"],
            "secretos": str(secretos), "pki_proxy": str(proxy), "pki_sonda": str(sonda)}
        self.control = Almacen(self.raiz / "control", crear=True)
        with self.control.exclusivo():
            self.plan = autorizar(self.control, datos, confirmar=True)
        def crear(propietario):
            self.runtime = Docker(self.control, propietario,
                verificador=lambda *_: self.auxiliar("verificar", red=False))
            return self.runtime
        resultado = Motor(self.control, crear).activar(self.plan)
        self.anotar("activacion_local_mtls", resultado.get("codigo") == 0)
        self.informe["generacion"] = self.plan.generacion
        self.informe["restauracion"] = d["restauracion"]
        self.informe["comprobaciones"].extend(d["comprobaciones"])

    def sondear(self):
        from despliegue.operacion_consulta import observabilidad as ob
        from despliegue.operacion_consulta.exportador import crear_servidor
        contexto = ssl.create_default_context(cafile=str(self.raiz / "pki/ca.crt"))
        c = http.client.HTTPSConnection("localhost", 18443, context=contexto, timeout=4)
        c._create_connection = lambda *a, **kw: socket.create_connection(("127.0.0.1", 18443), 4)
        rechazado = False
        try:
            c.request("GET", "/api/v1/estado", headers={"Connection": "close"})
            r = c.getresponse()
            r.read(65537)
            rechazado = r.status in (400, 403)
        except (ssl.SSLError, ConnectionError, http.client.RemoteDisconnected):
            rechazado = True
        finally:
            c.close()
        self.anotar("sin_certificado_cliente_rechazado", rechazado)
        ahora = datetime.now(timezone.utc)
        m = json.loads((Path(self.plan.directorio_generacion) / "manifiesto.json").read_text())
        s = ob.registrar(ob.senales_iniciales(), "contacto_pc", ahora.isoformat(), ahora=ahora)
        s = ob.registrar(s, "captura_verificada", m["creada_en"], ahora=ahora)
        v = ob.muestra(self.control.leer("estado.json"), m, self.runtime.ultimo_estado, s, ahora)
        with self.control.exclusivo():
            self.control.escribir("senales.json", s)
            self.control.escribir("observacion.json", v)
        servidor = crear_servidor(self.control, 9125)
        hilo = threading.Thread(target=servidor.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        hilo.start()
        try:
            abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
            with abrir("http://127.0.0.1:9125/metricas", timeout=3) as r:
                self.anotar("metricas_loopback", r.status == 200 and b"loteria_consulta_verificada 1" in r.read(65537))
        finally:
            servidor.shutdown()
            servidor.server_close()
            hilo.join(3)

    def detener(self):
        correcto = True
        if self.control is not None and self.plan is not None and self.runtime is not None:
            try:
                self.runtime.detener(self.plan, time.monotonic() + 30)
            except BaseException:
                correcto = False
        try:
            ids = ejecutar_docker(["ps", "-aq", "--filter", "label=" + ETIQUETA + "=" + self.id]).decode().split()
            if ids:
                conjunto = json_docker(["inspect", *ids])
                # Validar TODO el conjunto antes de detener un solo contenedor.
                if (len(conjunto) != len(ids) or any(
                    d["Config"]["Labels"].get(ETIQUETA) != self.id
                    or not d["Name"].startswith("/e107" + self.id + "-")
                    or d["Image"] not in self.imagenes.values() for d in conjunto)):
                    raise Detenido("recurso_auxiliar_ajeno")
                activos = [d["Id"] for d in conjunto if d["State"]["Running"]]
                if activos:
                    ejecutar_docker(["stop", "--time", "5", *activos], timeout=30)
                correcto = correcto and not any(d["State"]["Running"] for d in json_docker(["inspect", *ids]))
        except BaseException:
            correcto = False
        if self.control is not None:
            self.control.close()
        self.informe["servicios_detenidos"] = correcto
        self.informe["recursos_conservados"] = True
        return correcto


def realizar(fuente: bytes, cambios: bytes, *, confirmar: bool) -> dict:
    if confirmar is not True:
        raise Detenido("falta_autorizacion_local_explicita")
    if os.name != "posix" or sys.version_info[:2] != (3, 14) or os.getuid() == 0:
        raise Detenido("requiere_ubuntu_python314_usuario_sin_privilegios")
    if not all(puerto_libre(p) for p in (18443, 9125)):
        raise Detenido("puerto_local_ocupado")
    if shutil.disk_usage(tempfile.gettempdir()).free < 4 * 1024**3:
        raise Detenido("espacio_local_insuficiente")
    raiz = Path(tempfile.mkdtemp(prefix="e107pc-"))
    ensayo = Ensayo(raiz)
    try:
        ensayo.etapa("copiar_fuentes")
        ensayo.fuente.mkdir(mode=0o755)
        extraer(fuente, ensayo.fuente)
        extraer(cambios, ensayo.fuente, cambios=True)
        sys.path.insert(0, str(ensayo.fuente))
        sys.path.insert(0, str(ensayo.fuente / "backend"))
        ensayo.etapa("comprobar_imagenes_locales")
        ensayo.imagenes_locales()
        ensayo.auxiliar("comprobar")
        ensayo.etapa("crear_postgres_sintetico")
        ensayo.preparar_postgres()
        ensayo.etapa("capturar_importar_y_restaurar")
        d = ensayo.auxiliar("generar", red=True, timeout=2400)
        ensayo.etapa("activar_y_comprobar_mtls_local")
        ensayo.activar(d)
        ensayo.sondear()
        ensayo.informe.update(codigo=0, estado="ensayo_completado")
    except BaseException as error:
        ensayo.informe.update(codigo=1, estado="ensayo_detenido",
            motivo=str(error) if isinstance(error, Detenido) else "paso_local_no_completo")
    finally:
        if not ensayo.detener():
            ensayo.informe.update(codigo=1, estado="detencion_pendiente")
    return ensayo.informe


def paquete_evidencia(informe: dict) -> bytes:
    datos = (json.dumps(informe, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode()
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("resultado.json", datos)
        z.writestr("SHA256SUMS", hashlib.sha256(datos).hexdigest() + "  resultado.json\n")
    return salida.getvalue()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--autorizar-ensayo-sintetico", action="store_true", required=True)
    args = p.parse_args()
    try:
        r = realizar(base64.b64decode(FUENTE_BASE64, validate=True),
                     base64.b64decode(CAMBIOS_BASE64, validate=True),
                     confirmar=args.autorizar_ensayo_sintetico)
    except BaseException as error:
        r = {"version": "e107-ensayo-pc/1", "base_codigo": BASE, "codigo": 1,
             "estado": "precondicion_rechazada", "produccion_autorizada": False,
             "motivo": str(error) if isinstance(error, Detenido) else "entrada_no_valida"}
    b = paquete_evidencia(r)
    print("E107_RESULTADO_JSON:" + json.dumps({"resumen": r, "evidencia_base64": base64.b64encode(b).decode(),
        "evidencia_sha256": hashlib.sha256(b).hexdigest(), "evidencia_bytes": len(b)}, ensure_ascii=True), flush=True)
    return r["codigo"]


if __name__ == "__main__":
    raise SystemExit(main())
