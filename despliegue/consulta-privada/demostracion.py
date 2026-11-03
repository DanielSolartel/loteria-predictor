"""
Fase 10 (E10.2/E10.3): demostracion AUTOMATICA de extremo a extremo de la consulta privada, con datos y
credenciales SINTETICOS. No toca la operacion de Fase 6 ni su `docker-compose.yml`: proyecto Docker con
nombre unico (`e102demo<hex>`), redes y volumen propios con etiqueta, puerto 127.0.0.1:18443 y limpieza solo
de esos recursos al terminar (salvo `--conservar`).

Topologia: cliente autenticado -> proxy (TLS + certificado de cliente) -> pasarela con la SPA -> API publica
(perfil privado) -> PostgreSQL desechable (rol lector) + publicacion sintetica montada de solo lectura.

Pasos: PKI de prueba (CA de consulta, servidor, tres invitados, CA ajena) y CRL; secretos en archivos;
publicacion sintetica (`tests.e102_preparar_publicacion`) con la base migrada; `docker compose up`; despues las
comprobaciones (cada una con su resultado, duracion y detalles, sin secretos) y la limpieza.

Uso (desde la raiz del repositorio; Docker, OpenSSL y Node con Playwright disponibles):
    python despliegue/consulta-privada/demostracion.py --salida <carpeta nueva> \
        --python-preparacion <python con requirements.lock> [--ca-extra <pem>] [--conservar]
Salida: <salida>/demostracion.json y registros saneados. Codigo 0 solo si todas las comprobaciones pasan.

Robustez del arnes (PR #109, CI109-02): la salida puede ser relativa o absoluta (tambien con espacios); se
normaliza a una ruta absoluta antes de derivar cualquier otra, de modo que los bind mounts y la configuracion de
Compose reciben siempre origenes absolutos. Un fallo en cualquier fase (entorno, PKI, imagenes, publicacion,
arranque) se registra con su motivo original y no impide la limpieza; cada paso de limpieza esta aislado (un
error no impide los demas) y solo actua sobre recursos con la etiqueta y el nombre del proyecto. El informe
JSON se escribe siempre, saneado (sin secretos ni la ruta de trabajo), con `todas_correctas: false` y codigo
distinto de cero ante cualquier fallo, residuo o limpieza incompleta.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import http.client
import ipaddress
import json
import os
import random
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path

DEMO = Path(__file__).resolve().parent
RAIZ = DEMO.parents[1]
BACKEND = RAIZ / "backend"
HOST, PUERTO = "consulta.e102.prueba", 18443
ORIGEN = f"https://{HOST}:{PUERTO}"
IMAGEN_PG = ("docker.io/library/postgres:16-alpine@sha256:"
             "0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab")
ETIQUETA = "e102.demostracion"
JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
INVITADOS = ("invitado-a", "invitado-b", "invitado-c")


def ejecutar(args, *, entrada: bytes | None = None, check: bool = True, timeout: float = 900, env=None, cwd=None):
    r = subprocess.run([str(a) for a in args], input=entrada, capture_output=True, timeout=timeout, env=env, cwd=cwd)
    if check and r.returncode != 0:
        raise RuntimeError(f"{Path(str(args[0])).name} {args[1] if len(args) > 1 else ''}: codigo {r.returncode}: "
                           f"{r.stderr.decode(errors='replace')[-600:]}")
    return r


def puerto_libre(puerto: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", puerto))
            return True
        except OSError:
            return False


class Demostracion:
    def __init__(self, salida: Path, python_prep: str, ca_extra: str | None, conservar: bool):
        # Absoluta ANTES de derivar nada: Docker trata un origen relativo de `-v` como nombre de volumen.
        salida = Path(salida).expanduser().absolute()
        self.salida, self.python_prep, self.ca_extra, self.conservar = salida, python_prep, ca_extra, conservar
        self.id = secrets.token_hex(3)
        self.proyecto = f"e102demo{self.id}"
        self.trabajo = salida / "trabajo"  # PKI, secretos y publicacion: nunca se empaquetan
        self.pki = self.trabajo / "pki"
        self.pki_proxy = self.trabajo / "pki-proxy"
        self.secretos = self.trabajo / "secretos"
        self.generado = self.trabajo / "generado"
        self.registros = salida / "registros"
        self.volumen = f"{self.proyecto}-pgdatos"
        self.resultados: list[dict] = []
        self.inicio = time.monotonic()
        self.valores_secretos: list[str] = []
        segundo = random.randint(200, 250)
        self.redes = {n: f"10.{segundo}.{i}" for i, n in enumerate(("interna", "servicio", "datos"), start=11)}
        self.imagenes: dict[str, dict] = {}
        self.publicacion: Path | None = None  # existe solo tras preparar_publicacion
        self.fase = "inicio"
        self.error_inicial: dict | None = None
        self.errores_limpieza: list[dict] = []

    # ------------------------------------------------------------------ utilidades
    def anotar(self, ident: str, descripcion: str, ok: bool, inicio: float, **detalles):
        fila = {"id": ident, "descripcion": descripcion, "ok": bool(ok),
                "segundos": round(time.monotonic() - inicio, 2), **detalles}
        self.resultados.append(fila)
        print(json.dumps(fila, ensure_ascii=False)[:400], flush=True)
        return ok

    def secreto(self, nombre: str, valor: str) -> Path:
        ruta = self.secretos / nombre
        ruta.write_text(valor + ("\n" if not valor.endswith("\n") else ""), encoding="ascii")
        ruta.chmod(0o444)
        if len(valor.strip()) >= 16:
            self.valores_secretos.append(valor.strip())
        return ruta

    def reescribir(self, nombre: str, valor: str) -> None:
        """Mismo inodo (el archivo esta montado en el contenedor)."""
        ruta = self.secretos / nombre
        ruta.chmod(0o644)
        with open(ruta, "r+", encoding="ascii") as f:
            f.seek(0)
            f.write(valor + "\n")
            f.truncate()
        ruta.chmod(0o444)
        if len(valor.strip()) >= 16:
            self.valores_secretos.append(valor.strip())

    def entorno_compose(self) -> dict:
        """Valido en cualquier estado: antes de publicar o de construir se usan valores inertes (rutas absolutas
        inexistentes bajo la carpeta de trabajo e imagenes sin etiqueta real), suficientes para `compose down`."""
        base = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONFIG")}
        publicacion = self.publicacion if self.publicacion is not None else self.trabajo / "sin-publicacion"
        imagen = {o: (self.imagenes.get(o) or {}).get("etiqueta") or f"{self.proyecto}-{o}-sin-construir:ninguna"
                  for o in ("api", "pasarela")}
        return {**base, "E102_SECRETOS": str(self.secretos), "E102_PUBLICACION": str(publicacion),
                "E102_PKI_PROXY": str(self.pki_proxy), "E102_PROXY_GENERADO": str(self.generado),
                "E102_RED_INTERNA": self.redes["interna"], "E102_RED_SERVICIO": self.redes["servicio"],
                "E102_RED_DATOS": self.redes["datos"], "E102_IMAGEN_API": imagen["api"],
                "E102_IMAGEN_PASARELA": imagen["pasarela"], "E102_VOLUMEN_PG": self.volumen,
                "E102_FICHAS_PERSONA": "30", "E102_FICHAS_AGREGADAS": "50"}

    def sanear(self, texto: str) -> str:
        """Diagnosticos sin secretos sinteticos ni rutas de trabajo/salida (PKI, secretos, publicacion)."""
        for valor in sorted(set(self.valores_secretos), key=len, reverse=True):
            texto = texto.replace(valor, "[secreto]")
        for ruta, etiqueta in ((self.trabajo, "[trabajo]"), (self.salida, "[salida]")):
            texto = texto.replace(str(ruta), etiqueta)
        return texto

    def compose(self, *args, check=True, timeout=300):
        return ejecutar(["docker", "compose", "-p", self.proyecto, "-f", DEMO / "compose.yml", *args], check=check,
                        timeout=timeout, env=self.entorno_compose())

    def contenedor(self, servicio: str) -> str:
        return f"{self.proyecto}-{servicio}-1"

    def docker_exec(self, servicio: str, *args, entrada: bytes | None = None, check=False, timeout=120):
        return ejecutar(["docker", "exec", "-i", self.contenedor(servicio), *args], entrada=entrada, check=check,
                        timeout=timeout)

    def psql(self, sql: str, *, base: str = "loteria_prueba", check=True, contenedor: str | None = None):
        return ejecutar(["docker", "exec", "-i", contenedor or self.contenedor("postgres"), "psql", "-q", "-At", "-v",
                         "ON_ERROR_STOP=1", "-U", "superprueba", "-d", base, "-f", "-"], entrada=sql.encode(),
                        check=check)

    # ------------------------------------------------------------------ TLS a traves del proxy
    def contexto(self, persona: str | None, *, ca: str = "ca-consulta") -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if ca:
            ctx.load_verify_locations(self.pki / f"{ca}.crt")
        if persona:
            ctx.load_cert_chain(self.pki / f"{persona}.crt", self.pki / f"{persona}.key")
        return ctx

    def https(self, ruta: str, persona: str | None = "invitado-a", *, cabeceras=(), host: str | None = None,
              ca: str = "ca-consulta", metodo: str = "GET", timeout: float = 30, abandonar: float | None = None):
        ctx = self.contexto(persona, ca=ca)
        crudo = socket.create_connection(("127.0.0.1", PUERTO), timeout=timeout)
        tls = ctx.wrap_socket(crudo, server_hostname=HOST)
        conexion = http.client.HTTPConnection(HOST, PUERTO, timeout=timeout)
        conexion.sock = tls
        conexion.putrequest(metodo, ruta, skip_host=True, skip_accept_encoding=True)
        conexion.putheader("Host", host or f"{HOST}:{PUERTO}")
        conexion.putheader("Accept", "application/json")
        for nombre, valor in cabeceras:
            conexion.putheader(nombre, valor)
        conexion.endheaders()
        if abandonar is not None:  # el cliente se desconecta sin esperar la respuesta
            time.sleep(abandonar)
            conexion.close()
            return None, {}, None
        r = conexion.getresponse()
        cuerpo = r.read()
        cabeceras_r = {k.lower(): v for k, v in r.getheaders()}
        conexion.close()
        try:
            datos = json.loads(cuerpo)
        except ValueError:
            datos = None
        return r.status, cabeceras_r, datos if datos is not None else cuerpo[:200].decode(errors="replace")

    @staticmethod
    def codigo(datos) -> str | None:
        return datos.get("error", {}).get("codigo") if isinstance(datos, dict) else None

    # ------------------------------------------------------------------ preparacion
    def comprobar_entorno(self):
        inicio = time.monotonic()
        existentes = []
        for red in ejecutar(["docker", "network", "ls", "-q"]).stdout.decode().split():
            for cfg in json.loads(ejecutar(["docker", "network", "inspect", red]).stdout)[0]["IPAM"]["Config"] or []:
                if cfg.get("Subnet"):
                    existentes.append(ipaddress.ip_network(cfg["Subnet"], strict=False))
        propias = [ipaddress.ip_network(f"{p}.0/24") for p in self.redes.values()]
        solapadas = [str(p) for p in propias if any(p.overlaps(e) for e in existentes)]
        libre = puerto_libre(PUERTO)
        if solapadas or not libre:
            raise RuntimeError(f"entorno no apto: subredes solapadas {solapadas} o puerto {PUERTO} ocupado")
        self.anotar("E00", "entorno propio: proyecto, subredes y puerto libres", True, inicio, proyecto=self.proyecto,
                    subredes=[str(p) for p in propias], puerto=f"127.0.0.1:{PUERTO}",
                    docker=ejecutar(["docker", "version", "--format", "{{.Server.Version}}"]).stdout.decode().strip(),
                    openssl=ejecutar(["openssl", "version"]).stdout.decode().strip())

    def preparar_pki(self):
        inicio = time.monotonic()
        p = self.pki
        p.mkdir(mode=0o700)

        def openssl(*a):
            ejecutar(["openssl", *a])

        def clave(nombre):
            openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", p / f"{nombre}.key")

        def ca(nombre, cn):
            clave(nombre)
            openssl("req", "-x509", "-new", "-key", p / f"{nombre}.key", "-out", p / f"{nombre}.crt", "-days", "2",
                    "-subj", f"/CN={cn}", "-addext", "basicConstraints=critical,CA:TRUE",
                    "-addext", "keyUsage=critical,keyCertSign,cRLSign")

        def emitir(nombre, sujeto, autoridad, uso, san=None):
            clave(nombre)
            (p / f"{nombre}.ext").write_text("basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n"
                                             f"extendedKeyUsage={uso}\n" + (f"subjectAltName=DNS:{san}\n" if san else ""),
                                             encoding="ascii")
            openssl("req", "-new", "-key", p / f"{nombre}.key", "-subj", sujeto, "-out", p / f"{nombre}.csr")
            openssl("x509", "-req", "-in", p / f"{nombre}.csr", "-CA", p / f"{autoridad}.crt", "-CAkey",
                    p / f"{autoridad}.key", "-set_serial", "0x" + secrets.token_hex(8), "-days", "2", "-sha256",
                    "-extfile", p / f"{nombre}.ext", "-out", p / f"{nombre}.crt")

        ca("ca-consulta", "CA de consulta E10.2 PRUEBA")
        ca("ca-ajena", "CA ajena E10.2 PRUEBA")
        emitir("servidor", f"/CN={HOST}", "ca-consulta", "serverAuth", san=HOST)
        for persona in INVITADOS:
            emitir(persona, f"/CN={persona}", "ca-consulta", "clientAuth")
        emitir("ajeno-a", "/CN=invitado-a", "ca-ajena", "clientAuth")  # mismo CN, otra CA
        emitir("con-organizacion", "/CN=invitado-d/O=Otra", "ca-consulta", "clientAuth")  # sujeto no exacto
        (p / "index.txt").write_text("", encoding="ascii")
        (p / "crlnumber").write_text("01\n", encoding="ascii")
        (p / "ca.cnf").write_text(f"[ ca ]\ndefault_ca = consulta\n[ consulta ]\ndatabase = {p}/index.txt\n"
                                  f"crlnumber = {p}/crlnumber\ndefault_md = sha256\ndefault_crl_days = 1\n"
                                  f"certificate = {p}/ca-consulta.crt\nprivate_key = {p}/ca-consulta.key\n",
                                  encoding="ascii")
        self.generar_crl()
        self.pki_proxy.mkdir(mode=0o755)
        for nombre in ("servidor.crt", "servidor.key", "ca-consulta.crt", "crl.pem"):
            shutil.copyfile(p / nombre, self.pki_proxy / nombre)
            (self.pki_proxy / nombre).chmod(0o444)
        self.anotar("E01", "PKI de prueba: CA de consulta, servidor, tres invitados, CA ajena y CRL", True, inicio,
                    invitados=list(INVITADOS), algoritmo="EC P-256", validez_dias=2)

    def generar_crl(self):
        ejecutar(["openssl", "ca", "-config", self.pki / "ca.cnf", "-gencrl", "-out", self.pki / "crl.pem"])

    def preparar_secretos(self):
        inicio = time.monotonic()
        self.secretos.mkdir(mode=0o700)
        self.generado.mkdir(mode=0o755)
        self.claves_pg = {n: secrets.token_hex(24) for n in ("pg_super", "pg_propietario", "pg_lector")}
        for nombre, valor in self.claves_pg.items():
            self.secreto(nombre, valor)
        sys.path.insert(0, str(BACKEND))
        from app.api.publica.seguridad import generar_clave, huella  # solo generan y resumen; sin estado

        self.huella = huella
        self.clave_1, self.clave_2 = generar_clave(), generar_clave()
        self.secreto("api_claves", f"pasarela-1:sha256:{huella(self.clave_1)}")
        self.secreto("pasarela_clave_api", self.clave_1)
        self.ingreso = secrets.token_hex(32)
        self.secreto("pasarela_ingreso", self.ingreso)
        self.secreto("proxy_ingreso.conf", f'proxy_set_header X-Consulta-Ingreso "{self.ingreso}";')
        self.secreto("api_database_url", f"postgresql+psycopg://consulta_lector:{self.claves_pg['pg_lector']}@"
                                         f"{self.redes['datos']}.30:5432/loteria_prueba")
        (self.generado / "pasarela.conf").write_text(f"server {self.redes['interna']}.20:8020;\n", encoding="ascii")
        self.anotar("E02", "secretos sinteticos en archivos (0444, carpeta 0700); nunca en imagenes ni entorno", True,
                    inicio, archivos=sorted(p.name for p in self.secretos.iterdir()))

    def construir_imagenes(self):
        for objetivo in ("api", "pasarela"):
            inicio = time.monotonic()
            etiqueta = f"loteria-e102-{objetivo}:{self.proyecto}"
            extra = ["--secret", f"id=ca_extra,src={self.ca_extra}"] if self.ca_extra else []
            r = ejecutar(["docker", "build", "-f", RAIZ / "despliegue/imagenes/Dockerfile", "--target", objetivo,
                          *extra, "--label", f"{ETIQUETA}={self.proyecto}", "-t", etiqueta, RAIZ], timeout=1800)
            (self.registros / f"build-{objetivo}.log").write_bytes(r.stdout + r.stderr)
            identificador = ejecutar(["docker", "image", "inspect", "-f", "{{.Id}}", etiqueta]).stdout.decode().strip()
            usuario = ejecutar(["docker", "image", "inspect", "-f", "{{.Config.User}}", etiqueta]).stdout.decode().strip()
            self.imagenes[objetivo] = {"etiqueta": etiqueta, "imagen_id": identificador, "usuario": usuario}
            self.anotar(f"E03-{objetivo}", f"imagen {objetivo} construida (varias etapas, base por digest)",
                        usuario == "10001:10001", inicio, **self.imagenes[objetivo])

    def preparar_publicacion(self):
        inicio = time.monotonic()
        ejecutar(["docker", "volume", "create", "--label", f"{ETIQUETA}={self.proyecto}", self.volumen])
        puerto = random.randint(30000, 39999)
        while not puerto_libre(puerto):
            puerto = random.randint(30000, 39999)
        nombre = f"{self.proyecto}-pg-preparacion"
        ejecutar(["docker", "run", "-d", "--name", nombre, "--label", f"{ETIQUETA}={self.proyecto}",
                  "-e", "POSTGRES_USER=superprueba", "-e", "POSTGRES_DB=loteria_prueba",
                  "-e", "POSTGRES_PASSWORD_FILE=/run/secretos/pg_super",
                  "-v", f"{self.secretos / 'pg_super'}:/run/secretos/pg_super:ro",
                  "-v", f"{self.volumen}:/var/lib/postgresql/data", "-p", f"127.0.0.1:{puerto}:5432", IMAGEN_PG])
        try:
            self.esperar(lambda: ejecutar(["docker", "exec", nombre, "pg_isready", "-U", "superprueba", "-d",
                                           "loteria_prueba"], check=False).returncode == 0, 60)
            time.sleep(2)  # el arranque inicial del contenedor reinicia el servidor una vez
            self.esperar(lambda: ejecutar(["docker", "exec", nombre, "pg_isready", "-U", "superprueba", "-d",
                                           "loteria_prueba"], check=False).returncode == 0, 60)
            roles = (f"\\set clave_propietario '{self.claves_pg['pg_propietario']}'\n"
                     f"\\set clave_lector '{self.claves_pg['pg_lector']}'\n\\set base loteria_prueba\n"
                     + (DEMO / "postgres/roles.sql").read_text(encoding="utf-8"))
            self.psql(roles, base="postgres", contenedor=nombre)
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith(("DIRECTORIO_", "API_PUBLICA_", "PASARELA_", "BASE_", "DATABASE_URL"))}
            env.update({"PYTHONDONTWRITEBYTECODE": "1", "DATABASE_URL":
                        f"postgresql+psycopg://consulta_propietario:{self.claves_pg['pg_propietario']}@127.0.0.1:"
                        f"{puerto}/loteria_prueba"})
            ejecutar([self.python_prep, "-B", "-m", "alembic", "upgrade", "head"], env=env, cwd=BACKEND)
            r = ejecutar([self.python_prep, "-B", "-m", "tests.e102_preparar_publicacion", "--salida",
                          self.trabajo / "preparacion"], env=env, cwd=BACKEND, timeout=1800)
            resumen = json.loads(r.stdout.decode().strip().splitlines()[-1])
        finally:
            ejecutar(["docker", "rm", "-f", nombre], check=False)
        self.publicacion = self.trabajo / "preparacion" / "publicacion"
        self.manifiesto = json.loads((self.trabajo / "preparacion" / "manifiesto-publicacion.json").read_text())
        for ruta in sorted(self.publicacion.rglob("*"), reverse=True):
            ruta.chmod(0o555 if ruta.is_dir() else 0o444)
        self.publicacion.chmod(0o555)
        self.anotar("E04", "publicacion sintetica preparada ANTES de montarla de solo lectura (base migrada, roles)",
                    resumen["archivos"] > 0 and resumen["estimadores_pkl"] > 0, inicio, **resumen)

    @staticmethod
    def esperar(condicion, plazo: float, paso: float = 0.5) -> float:
        inicio = time.monotonic()
        while time.monotonic() - inicio < plazo:
            try:
                if condicion():
                    return time.monotonic() - inicio
            except Exception:
                pass
            time.sleep(paso)
        raise TimeoutError("plazo agotado")

    def levantar(self):
        inicio = time.monotonic()
        self.compose("up", "-d", "--wait", "--wait-timeout", "180", timeout=400)
        espera = self.esperar(lambda: self.https("/api/v1/salud", "invitado-c")[0] == 200, 120)
        self.anotar("E05", "pila arrancada: proxy, pasarela, API y PostgreSQL (redes internas)", True, inicio,
                    espera_salud_s=round(espera, 2))

    def reiniciar(self, servicio: str, persona: str = "invitado-c") -> float:
        """Reinicia y espera con la SPA (`/`), que no consume cuota: la espera no altera las cubetas."""
        inicio = time.monotonic()
        self.compose("restart", servicio)
        self.esperar(lambda: self.https("/", persona)[0] == 200, 120)
        return round(time.monotonic() - inicio, 2)

    # ------------------------------------------------------------------ comprobaciones
    def tls_e_identidad(self):
        inicio = time.monotonic()
        estado, cab, cuerpo = self.https("/", "invitado-a")
        self.anotar("T01", "SPA por el proxy con TLS verificado (CA de prueba explicita) y certificado de invitado-a",
                    estado == 200 and isinstance(cuerpo, str) and "<" in cuerpo
                    and cab.get("content-security-policy", "").startswith("default-src 'self'"), inicio, estado=estado)
        inicio = time.monotonic()
        estados = {}
        for nombre, kwargs in {"sin_certificado": {"persona": None}, "ca_ajena": {"persona": "ajeno-a"},
                               "sujeto_no_exacto": {"persona": "con-organizacion"},
                               "host_distinto": {"host": "otro.prueba:18443"}}.items():
            persona = kwargs.pop("persona", "invitado-a")
            estados[nombre] = self.https("/api/v1/estado", persona, **kwargs)[0]
        self.anotar("T02", "sin certificado, CA ajena con el mismo CN, sujeto no exacto u otro Host: rechazo en el proxy",
                    estados == {"sin_certificado": 400, "ca_ajena": 400, "sujeto_no_exacto": 403,
                                "host_distinto": 421}, inicio, estados=estados)
        inicio = time.monotonic()
        try:
            self.https("/", "invitado-a", ca="")
            verificado = False
        except ssl.SSLCertVerificationError as error:
            verificado = "certificate verify failed" in str(error)
        self.anotar("T03", "control negativo: sin la CA de prueba el cliente rechaza el servidor (no se ignora TLS)",
                    verificado, inicio)
        inicio = time.monotonic()
        a, b = self.https("/api/v1/estado", "invitado-a"), self.https("/api/v1/estado", "invitado-b")
        esquema = json.loads((RAIZ / "frontend/src/api/openapi.json").read_text(encoding="utf-8"))
        propiedades = set(esquema["components"]["schemas"]["EstadoDelServicio"]["properties"])
        ok = a[0] == b[0] == 200 and set(a[2]) == propiedades and a[2]["api"] == "v1" and a[2]["base"] == "disponible"
        self.anotar("T04", "dos invitados autenticados consultan /api/v1/estado: 200 con el cuerpo del contrato",
                    ok, inicio, estados=[a[0], b[0]], claves_del_cuerpo=sorted(set(a[2]) if isinstance(a[2], dict) else []),
                    restantes={"a": a[1].get("x-ratelimit-remaining"), "b": b[1].get("x-ratelimit-remaining")})

    def identidad_falsa(self):
        inicio = time.monotonic()
        antes_b = self.https("/api/v1/juegos", "invitado-b")[1].get("x-ratelimit-remaining")
        falsas = [("X-Consulta-Identidad", "invitado-b"), ("X-Consulta-Identidad", "invitado-b"),
                  ("X-Consulta-Ingreso", "0" * 64), ("X-Forwarded-For", f"{self.redes['interna']}.10"),
                  ("Forwarded", "for=127.0.0.1"), ("X-Real-IP", "127.0.0.1")]
        estado, cab, _ = self.https("/api/v1/juegos", "invitado-a", cabeceras=falsas)
        despues_b = self.https("/api/v1/juegos", "invitado-b")[1].get("x-ratelimit-remaining")
        registro = ejecutar(["docker", "logs", self.contenedor("pasarela")]).stderr.decode(errors="replace")
        lineas = [l for l in registro.splitlines() if "/api/v1/juegos " in l]
        ok = (estado == 200 and antes_b is not None and int(despues_b) == int(antes_b) - 1
              and any("identidad=invitado-a" in l for l in lineas))
        self.anotar("T05", "identidad, ingreso y XFF falsos del cliente: el proxy los reemplaza; cuenta como invitado-a",
                    ok, inicio, estado=estado, restante_b_antes=antes_b, restante_b_despues=despues_b,
                    restante_a=cab.get("x-ratelimit-remaining"))

    def cuotas(self):
        inicio = time.monotonic()
        self.reiniciar("pasarela")
        ruta = "/api/v1/juegos/BALOTO/estadisticas/resumen"
        a = [self.https(ruta, "invitado-a") for _ in range(7)]
        estados_a = [r[0] for r in a]
        b = []
        while len(b) < 7 and (not b or b[-1][0] == 200):
            b.append(self.https(ruta, "invitado-b"))
        estados_b, aceptadas_b = [r[0] for r in b], sum(r[0] == 200 for r in b)
        ultima = b[-1]
        # El agregado (50) se agota con las 6 de A (30) y 4 de B (20); la recarga (50/min) puede admitir una mas.
        ok = (estados_a == [200] * 6 + [429] and self.codigo(a[6][2]) == "limite_excedido"
              and int(a[6][1].get("retry-after", "0")) >= 1 and ultima[0] == 429 and aceptadas_b in (4, 5)
              and self.codigo(ultima[2]) == "limite_agregado_excedido"
              and ultima[1].get("x-ratelimit-remaining") == str(30 - 5 * aceptadas_b)
              and int(ultima[1].get("retry-after", "0")) >= 1)
        self.anotar("T06", "cuota por persona (30/min) y agregada (50/min): A no gasta la de B; 429 con Retry-After",
                    ok, inicio, estados_a=estados_a, estados_b=estados_b, codigo_a=self.codigo(a[6][2]),
                    codigo_b=self.codigo(ultima[2]), retry_after=[a[6][1].get("retry-after"), ultima[1].get("retry-after")],
                    restante_b_en_rechazo_agregado=ultima[1].get("x-ratelimit-remaining"))
        inicio = time.monotonic()
        segundos = self.reiniciar("pasarela")
        estado = self.https(ruta, "invitado-a")[0]
        self.anotar("T07", "efecto declarado del reinicio: las cubetas en memoria vuelven a su capacidad (N x Q)",
                    estado == 200, inicio, reinicio_s=segundos, estado_tras_reinicio=estado)

    def acceso_directo(self):
        inicio = time.monotonic()
        imagen = self.imagenes["pasarela"]["etiqueta"]
        sonda = ("import http.client,json,sys\n"
                 "def get(h,p,ruta,cab):\n"
                 "    try:\n"
                 "        c=http.client.HTTPConnection(h,p,timeout=3); c.request('GET',ruta,headers=cab); r=c.getresponse()\n"
                 "        cuerpo=r.read(); c.close()\n"
                 "        try: codigo=json.loads(cuerpo).get('error',{}).get('codigo')\n"
                 "        except Exception: codigo=None\n"
                 "        return [r.status,codigo]\n"
                 "    except Exception as e: return ['sin_conexion',type(e).__name__]\n"
                 "a=json.loads(sys.stdin.read()); print(json.dumps({k:get(*v) for k,v in a.items()}))\n")
        p, s, i = self.redes["interna"], self.redes["servicio"], self.redes["datos"]
        casos = {
            "frontal": {"pasarela": [f"{p}.20", 8020, "/api/v1/estado", {"Host": f"{HOST}:{PUERTO}"}],
                        "api": [f"{s}.20", 8010, "/api/v1/estado", {"X-API-Key": "x" * 40}],
                        "postgres": [f"{i}.30", 5432, "/", {}]},
            "interna": {"pasarela_sin_secreto": [f"{p}.20", 8020, "/api/v1/estado",
                                                 {"Host": f"{HOST}:{PUERTO}", "X-Consulta-Identidad": "invitado-a"}],
                        "pasarela_secreto_falso": [f"{p}.20", 8020, "/api/v1/estado",
                                                   {"Host": f"{HOST}:{PUERTO}", "X-Consulta-Identidad": "invitado-a",
                                                    "X-Consulta-Ingreso": "f" * 64,
                                                    "X-Forwarded-For": f"{p}.10"}],
                        "api": [f"{s}.20", 8010, "/api/v1/estado", {}]},
            "servicio": {"api_con_clave_valida": [f"{s}.20", 8010, "/api/v1/estado",
                                                  {"Host": f"{s}.20:8010", "X-API-Key": self.clave_1,
                                                   "X-Forwarded-For": f"{s}.10"}]},
        }
        resultados = {}
        for red, peticiones in casos.items():
            r = ejecutar(["docker", "run", "--rm", "-i", "--name", f"{self.proyecto}-atacante-{red}", "--label",
                          f"{ETIQUETA}={self.proyecto}", "--network", f"{self.proyecto}_{red}", "--read-only",
                          "--cap-drop", "ALL", "--entrypoint", "python", imagen, "-B", "-c", sonda],
                         entrada=json.dumps(peticiones).encode(), check=False, timeout=120)
            resultados[red] = json.loads(r.stdout.decode() or "{}")
        f, n, v = resultados["frontal"], resultados["interna"], resultados["servicio"]
        ok = (all(x[0] == "sin_conexion" for x in f.values())
              and n["pasarela_sin_secreto"] == [403, "ingreso_no_fiable"]
              and n["pasarela_secreto_falso"] == [403, "ingreso_no_fiable"] and n["api"][0] == "sin_conexion"
              and v["api_con_clave_valida"] == [403, "cliente_no_permitido"])
        self.anotar("T08", "acceso directo: desde la red frontal nada alcanza pasarela/API/base; en la interna sin el "
                           "secreto del proxy 403; en la de servicio, incluso con una clave valida, 403", ok, inicio,
                    resultados=resultados)

    def guion_matriz(self, destino: str | None = None) -> bytes:
        esperado = {"juegos": json.loads((self.trabajo / "preparacion" / "esperado-consultas.json").read_text()),
                    "sorteos": self.manifiesto["sorteos"], "simulacion_juego": "MILOTO"}
        prefijo = f"ESPERADO = {json.dumps(esperado)!r}\nESPERADO = __import__('json').loads(ESPERADO)\n"
        if destino:
            prefijo += f"DESTINO = {destino!r}\n"
        return (prefijo + (DEMO / "matriz_e102.py").read_text(encoding="utf-8")).encode()

    def matriz(self):
        inicio = time.monotonic()
        r = self.docker_exec("pasarela", "python", "-B", "-", entrada=self.guion_matriz(), timeout=600)
        filas = json.loads(r.stdout.decode())
        (self.salida / "matriz-19x4.json").write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
        fallos = [f for f in filas["filas"] if f["clase"] == "fallo"]
        procedencias_ok = all(v["coincide"] for v in filas["procedencias"].values()) and len(filas["procedencias"]) == 12
        self.anotar("T09", "19 endpoints x 4 juegos con comprobacion de contenido (IDs, totales, claves) y las tres "
                           "procedencias de Producto 6 presentes y observadas en cada juego",
                    not fallos and not filas["discrepancias"] and filas["total"] == 76 and procedencias_ok, inicio,
                    total=filas["total"], por_clase=filas["por_clase"], discrepancias=filas["discrepancias"][:6],
                    procedencias={k: [v["emisiones"], v["lineas_con_resultado_observado"]]
                                  for k, v in filas["procedencias"].items()})
        inicio = time.monotonic()
        declaradas = [f for f in filas["filas"] if f["clase"] in ("vacio_declarado", "ausencia_declarada")]
        ok = (filas["por_clase"].get("vacio_declarado") == 3 and filas["por_clase"].get("ausencia_declarada") == 3
              and all(f["juego"] != "MILOTO" for f in declaradas))
        self.anotar("T10", "ausencias deliberadas aparte: 3 juegos sin simulaciones (lista vacia declarada) y su "
                           "simulacion inexistente (404)", ok, inicio,
                    ausencias=[f"{f['juego']} {f['plantilla']} {f['estado']}" for f in declaradas])

    def solo_lectura(self):
        inicio = time.monotonic()
        pruebas = {}
        for servicio in ("api", "pasarela"):
            r = self.docker_exec(servicio, "sh", "-c",
                                 "id -u; for d in /srv/pub /srv/backend /srv/sin-publicar /opt/venv /tmp; do "
                                 "touch $d/e102-escritura 2>&1 && echo \"$d escribible\" && rm -f $d/e102-escritura; "
                                 "done; ls -d /srv/sin-publicar 2>&1 | head -1")
            pruebas[servicio] = r.stdout.decode().strip().splitlines()
        api, pas = pruebas["api"], pruebas["pasarela"]
        ok = (api[0] == "10001" and pas[0] == "10001" and "/tmp escribible" in api and "/tmp escribible" in pas
              and not any(l.endswith("escribible") and not l.startswith("/tmp") for l in api + pas)
              and any("Read-only file system" in l for l in api) and "No such file" in api[-1])
        self.anotar("T11", "contenedores sin root y de solo lectura (salvo /tmp en memoria); la publicacion :ro; "
                           "nada crea /srv/sin-publicar", ok, inicio, salida=pruebas)
        inicio = time.monotonic()
        sql = ("import json,psycopg\n"
               "u=open('/run/secretos/api_database_url').read().strip().replace('postgresql+psycopg://','postgresql://')\n"
               "out={}\n"
               "def probar(n,sentencias):\n"
               "    try:\n"
               "        with psycopg.connect(u,autocommit=True) as c:\n"
               "            for s in sentencias: c.execute(s)\n"
               "        out[n]='permitido'\n"
               "    except psycopg.Error as e: out[n]=e.sqlstate\n"
               "probar('insert',['INSERT INTO juegos(codigo,nombre) VALUES (\\'X\\',\\'x\\')'])\n"
               "probar('insert_sin_solo_lectura',['SET default_transaction_read_only=off',"
               "'INSERT INTO juegos(codigo,nombre) VALUES (\\'X\\',\\'x\\')'])\n"
               "probar('update',['SET default_transaction_read_only=off','UPDATE sorteos SET fuente=fuente'])\n"
               "probar('delete',['SET default_transaction_read_only=off','DELETE FROM simulaciones'])\n"
               "probar('create',['SET default_transaction_read_only=off','CREATE TABLE e102 (x int)'])\n"
               "probar('truncate',['SET default_transaction_read_only=off','TRUNCATE sorteos'])\n"
               "probar('select',['SELECT count(*) FROM sorteos'])\n"
               "probar('consulta_lenta_sin_opciones_de_la_api',['SELECT pg_sleep(3)'])\n"
               "import time\n"
               "try:\n"
               "    with psycopg.connect(u) as c:\n"
               "        c.execute('SELECT 1'); time.sleep(6.5); c.execute('SELECT 1')\n"
               "    out['inactiva_en_transaccion']='permitido'\n"
               "except psycopg.Error as e: out['inactiva_en_transaccion']=e.sqlstate or type(e).__name__\n"
               "print(json.dumps(out))\n")
        r = self.docker_exec("api", "python", "-B", "-", entrada=sql.encode(), timeout=120)
        rol = json.loads(r.stdout.decode() or "{}")
        ok = (rol.get("insert") == "25006" and all(rol.get(k) == "42501" for k in
                                                   ("insert_sin_solo_lectura", "update", "delete", "create", "truncate"))
              and rol.get("select") == "permitido" and rol.get("consulta_lenta_sin_opciones_de_la_api") == "57014"
              and rol.get("inactiva_en_transaccion") not in (None, "permitido"))
        self.anotar("T12", "rol lector: escrituras rechazadas (25006/42501), SELECT permitido; statement_timeout e "
                           "idle_in_transaction_session_timeout del propio rol", ok, inicio, sqlstate=rol)

    def bloqueo(self, segundos: float):
        """Una sesion del superusuario de PRUEBAS bloquea `sorteos` durante `segundos` (consulta lenta simulada)."""
        sql = f"BEGIN; LOCK TABLE sorteos IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep({segundos}); COMMIT;"
        proceso = subprocess.Popen(["docker", "exec", "-i", self.contenedor("postgres"), "psql", "-q", "-U",
                                    "superprueba", "-d", "loteria_prueba", "-c", sql], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        self.esperar(lambda: self.psql("SELECT count(*) FROM pg_locks l JOIN pg_class c ON c.oid = l.relation "
                                       "WHERE c.relname = 'sorteos' AND l.mode = 'AccessExclusiveLock' AND l.granted")
                     .stdout.decode().strip() == "1", 20, 0.1)
        return proceso

    def recursos(self):
        inicio = time.monotonic()
        self.reiniciar("pasarela")
        ruta = "/api/v1/juegos/BALOTO/estadisticas/resumen"
        bloqueo = self.bloqueo(5)
        with concurrent.futures.ThreadPoolExecutor(4) as hilos:
            futuros = [hilos.submit(self.https, ruta, persona) for persona in
                       ("invitado-a", "invitado-b", "invitado-a", "invitado-b")]
            respuestas = [f.result() for f in futuros]
        codigos = sorted(f"{r[0]}:{self.codigo(r[2])}" for r in respuestas)
        bloqueo.wait(30)
        recuperada = self.https(ruta, "invitado-b")
        colgadas = self.psql("SELECT count(*) FROM pg_stat_activity WHERE usename = 'consulta_lector' "
                             "AND state LIKE 'idle in transaction%'").stdout.decode().strip()
        ok = (codigos == ["503:consulta_cancelada"] * 2 + ["503:consultas_ocupadas"] * 2
              and all(r[1].get("retry-after") for r in respuestas) and recuperada[0] == 200 and colgadas == "0")
        self.anotar("T13", "consulta lenta (tabla bloqueada): 2 cancelan por statement_timeout y 2 esperan hueco; "
                           "503 controlados con Retry-After; despues 200 y sin sesiones colgadas", ok, inicio,
                    codigos=codigos, recuperada=recuperada[0], sesiones_inactivas_en_transaccion=colgadas)
        inicio = time.monotonic()
        bloqueo = self.bloqueo(4)
        abandonos = [threading.Thread(target=self.https, args=(ruta, p), kwargs={"abandonar": 0.3})
                     for p in ("invitado-a", "invitado-b")]
        for t in abandonos:
            t.start()
        for t in abandonos:
            t.join()
        time.sleep(0.2)
        durante = self.https(ruta, "invitado-a")
        bloqueo.wait(30)
        time.sleep(0.5)
        despues = self.https(ruta, "invitado-a")
        ok = durante[0] == 503 and self.codigo(durante[2]) == "consultas_ocupadas" and despues[0] == 200
        self.anotar("T14", "desconexion del cliente: el hueco sigue ocupado mientras el trabajo continua; se libera "
                           "al terminar", ok, inicio, durante=f"{durante[0]}:{self.codigo(durante[2])}",
                    despues=despues[0])
        inicio = time.monotonic()
        self.compose("restart", "postgres")
        caida = self.https("/api/v1/juegos/BALOTO/sorteos?por_pagina=5", "invitado-b")
        self.esperar(lambda: self.https("/api/v1/juegos", "invitado-c")[0] == 200, 60, 1.0)
        tras = self.https("/api/v1/juegos/BALOTO/sorteos?por_pagina=5", "invitado-b")
        ok = tras[0] == 200 and (caida[0] == 200 or caida[0] == 503)
        self.anotar("T15", "reinicio de PostgreSQL: errores controlados durante la caida y el pool se recupera",
                    ok, inicio, durante=f"{caida[0]}:{self.codigo(caida[2])}", despues=tras[0])

    def sondear_api(self, segundos: float):
        script = ("import http.client,time,json,os\n"
                  "h,p=os.environ['PASARELA_API_URL'][7:].rsplit(':',1); fin=time.monotonic()+%s; caidas=[]; ok=0\n"
                  "while time.monotonic()<fin:\n"
                  "    t=time.monotonic()\n"
                  "    try:\n"
                  "        c=http.client.HTTPConnection(h,int(p),timeout=1); c.request('GET','/api/v1/salud'); s=c.getresponse().status; c.close()\n"
                  "    except Exception: s=0\n"
                  "    if s==200: ok+=1\n"
                  "    else: caidas.append(round(t,2))\n"
                  "    time.sleep(0.1)\n"
                  "print(json.dumps({'ok':ok,'fallidas':len(caidas),'ventana_s':round(caidas[-1]-caidas[0],2) if caidas else 0}))\n"
                  % segundos)
        return subprocess.Popen(["docker", "exec", "-i", self.contenedor("pasarela"), "python", "-B", "-c", script],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def clave_directa(self, clave: str):
        script = ("import http.client,os,sys\n"
                  "h,p=os.environ['PASARELA_API_URL'][7:].rsplit(':',1); k=sys.stdin.read().strip()\n"
                  "c=http.client.HTTPConnection(h,int(p),timeout=5); c.request('GET','/api/v1/estado',headers={'X-API-Key':k})\n"
                  "print(c.getresponse().status)\n")
        r = self.docker_exec("pasarela", "python", "-B", "-c", script, entrada=clave.encode())
        return int(r.stdout.decode().strip() or 0)

    def claves(self):
        inicio = time.monotonic()
        self.reescribir("api_claves", f"pasarela-1:sha256:{self.huella(self.clave_1)}\n"
                                      f"pasarela-2:sha256:{self.huella(self.clave_2)}")
        sondeo = self.sondear_api(12)
        time.sleep(1)
        self.compose("restart", "api")
        ventana = json.loads(sondeo.communicate(timeout=60)[0].decode() or "{}")
        solape = (self.clave_directa(self.clave_1), self.clave_directa(self.clave_2))
        self.reescribir("pasarela_clave_api", self.clave_2)
        reinicio_pasarela = self.reiniciar("pasarela")
        por_proxy = self.https("/api/v1/estado", "invitado-a")[0]
        self.reescribir("api_claves", f"pasarela-2:sha256:{self.huella(self.clave_2)}")
        self.compose("restart", "api")
        self.esperar(lambda: self.https("/api/v1/salud", "invitado-c")[0] == 200, 60)
        tras = (self.clave_directa(self.clave_1), self.clave_directa(self.clave_2))
        por_proxy_final = self.https("/api/v1/estado", "invitado-a")[0]
        ok = solape == (200, 200) and por_proxy == 200 and tras == (401, 200) and por_proxy_final == 200
        self.anotar("T16", "rotacion con solapamiento y revocacion de la clave de API (reinicio; ventana medida)",
                    ok, inicio, solape=solape, tras_revocar=tras, ventana_reinicio_api=ventana,
                    reinicio_pasarela_s=reinicio_pasarela, por_proxy=[por_proxy, por_proxy_final])
        inicio = time.monotonic()
        self.reescribir("api_claves", "# sin huellas")
        self.compose("restart", "api", check=False)
        time.sleep(3)
        salida_api = ejecutar(["docker", "inspect", "-f", "{{.State.Status}} {{.State.ExitCode}}",
                               self.contenedor("api")]).stdout.decode().strip()
        motivo = ejecutar(["docker", "logs", self.contenedor("api")]).stderr.decode(errors="replace")
        via_proxy = self.https("/api/v1/estado", "invitado-a")
        self.reescribir("api_claves", f"pasarela-2:sha256:{self.huella(self.clave_2)}")
        self.compose("up", "-d", "--wait", "api", timeout=300)
        self.reescribir("pasarela_clave_api", "x")
        self.compose("restart", "pasarela", check=False)
        time.sleep(3)
        salida_pasarela = ejecutar(["docker", "inspect", "-f", "{{.State.Status}} {{.State.ExitCode}}",
                                    self.contenedor("pasarela")]).stdout.decode().strip()
        via_proxy_2 = self.https("/api/v1/estado", "invitado-a")[0]
        self.reescribir("pasarela_clave_api", self.clave_2)
        self.compose("up", "-d", "--wait", "pasarela", timeout=300)
        self.esperar(lambda: self.https("/api/v1/salud", "invitado-c")[0] == 200, 60)
        # Un contenedor detenido no responde en su IP: la pasarela da 504 `api_sin_respuesta` (plazo de conexion)
        # o 503 `api_no_disponible` (rechazo); el proxy, 502/504 con la pasarela caida. Nunca un 200.
        ok = (salida_api == "exited 3" and "api_publica privada: API_PUBLICA_CLAVES_ARCHIVO: archivo vacio" in motivo
              and f"{via_proxy[0]}:{self.codigo(via_proxy[2])}" in ("503:api_no_disponible", "504:api_sin_respuesta")
              and salida_pasarela.startswith("exited") and via_proxy_2 in (502, 504))
        self.anotar("T17", "cerrado ante el fallo: API sin huellas no arranca (codigo 3) y la pasarela responde 503/504 "
                           "controlado; pasarela sin clave valida no arranca y el proxy da 502/504", ok, inicio,
                    api=salida_api, motivo_api=next((l for l in motivo.splitlines() if "api_publica privada" in l), ""),
                    proxy_con_api_caida=f"{via_proxy[0]}:{self.codigo(via_proxy[2])}", pasarela=salida_pasarela,
                    proxy_con_pasarela_caida=via_proxy_2)

    def revocacion(self):
        inicio = time.monotonic()
        antes = self.https("/api/v1/salud", "invitado-c")[0]
        ejecutar(["openssl", "ca", "-config", self.pki / "ca.cnf", "-revoke", self.pki / "invitado-c.crt"])
        self.generar_crl()
        destino = self.pki_proxy / "crl.pem"
        destino.chmod(0o644)
        destino.write_bytes((self.pki / "crl.pem").read_bytes())
        destino.chmod(0o444)
        recarga = time.monotonic()
        ejecutar(["docker", "exec", self.contenedor("proxy"), "nginx", "-s", "reload"])
        seguidos = []

        def revocado():  # tres rechazos seguidos: los trabajadores anteriores ya no aceptan conexiones
            seguidos.append(self.https("/", "invitado-c")[0])
            return seguidos[-3:] == [400, 400, 400]
        ventana = self.esperar(revocado, 30, 0.2)
        despues = [self.https("/", "invitado-c")[0] for _ in range(5)]
        otros = (self.https("/", "invitado-a")[0], self.https("/", "invitado-b")[0])
        ok = antes == 200 and despues == [400] * 5 and otros == (200, 200)
        self.anotar("T18", "revocacion del certificado de invitado-c: CRL nueva + `nginx -s reload`, sin reiniciar",
                    ok, inicio, antes=antes, despues=despues, otros=otros,
                    segundos_hasta_efecto=round(time.monotonic() - recarga, 2), sondeo_s=round(ventana, 2))

    def navegador(self):
        inicio = time.monotonic()
        guion = DEMO / "navegador_e102.cjs"
        destino = self.salida / "navegador"
        destino.mkdir()
        # El nombre de la demostracion es local: fuera del proxy de salida del entorno (si lo hay).
        locales = ",".join(x for x in (HOST, "127.0.0.1", os.environ.get("NO_PROXY", "")) if x)
        entorno = {**os.environ, "NO_PROXY": locales, "no_proxy": locales,
                   "NODE_EXTRA_CA_CERTS": str(self.pki / "ca-consulta.crt")}
        ejecutar(["node", guion, ORIGEN, self.pki / "invitado-b.crt", self.pki / "invitado-b.key", destino / "invitado-b"],
                 env=entorno, timeout=180, check=False)
        positivo = json.loads((destino / "invitado-b.json").read_text())
        sin_ca = {k: v for k, v in entorno.items() if k != "NODE_EXTRA_CA_CERTS"}
        ejecutar(["node", guion, ORIGEN, self.pki / "invitado-b.crt", self.pki / "invitado-b.key", destino / "sin-ca"],
                 env=sin_ca, timeout=180, check=False)
        sin_ca_r = json.loads((destino / "sin-ca.json").read_text())
        ejecutar(["node", guion, ORIGEN, "-", "-", destino / "sin-certificado"], env=entorno, timeout=180, check=False)
        sin_cert = json.loads((destino / "sin-certificado.json").read_text())
        api = [r for r in positivo.get("respuestas", []) if r["ruta"].startswith("/api/v1/")]
        ok = (positivo.get("ok") and positivo.get("base") == "disponible" and api and all(r["estado"] == 200 for r in api)
              and not sin_ca_r.get("ok") and not sin_cert.get("ok"))
        self.anotar("T19", "SPA en Chromium (Playwright) por el proxy con el certificado de invitado-b: pantalla "
                           "Servicio y modelos; sin la CA de prueba o sin certificado no carga", bool(ok), inicio,
                    positivo={k: positivo.get(k) for k in ("ok", "base", "titulo", "error")}, consultas_api=api[:12],
                    sin_ca={k: sin_ca_r.get(k) for k in ("ok", "error")},
                    sin_certificado={"ok": sin_cert.get("ok"), "error": sin_cert.get("error"),
                                     "estados": sorted({r["estado"] for r in sin_cert.get("respuestas", [])})})

    def integridad_y_registros(self):
        inicio = time.monotonic()
        actuales = {p.relative_to(self.publicacion).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(self.publicacion.rglob("*")) if p.is_file()}
        difs = {}
        for s in ("api", "pasarela"):  # se descartan los puntos de montaje que crea Docker (y sus carpetas padre)
            montajes = json.loads(ejecutar(["docker", "inspect", "-f", "{{json .Mounts}}", self.contenedor(s)]).stdout)
            admitidos = set()
            for m in montajes:
                partes = Path(m["Destination"]).parts
                admitidos |= {str(Path(*partes[:i])) for i in range(2, len(partes) + 1)}
            lineas = ejecutar(["docker", "diff", self.contenedor(s)]).stdout.decode().splitlines()
            difs[s] = [l for l in lineas if l.split(" ", 1)[1] not in admitidos]
        ok = actuales == self.manifiesto["huellas"] and not difs["api"] and not difs["pasarela"]
        self.anotar("T20", "tras todas las consultas la publicacion es identica (SHA-256) y los contenedores no "
                           "cambiaron su sistema de archivos", ok, inicio, archivos=len(actuales), docker_diff=difs)
        inicio = time.monotonic()
        registros = {}
        for servicio in ("proxy", "pasarela", "api", "postgres"):
            r = ejecutar(["docker", "logs", self.contenedor(servicio)], check=False)
            registros[servicio] = (r.stdout + r.stderr).decode(errors="replace")
        texto = "\n".join(registros.values())
        fugas = [i for i, v in enumerate(self.valores_secretos) if v and v in texto]
        fugas += ["huella"] if self.huella(self.clave_1) in texto or self.huella(self.clave_2) in texto else []
        fugas += ["clave_privada"] if "PRIVATE KEY" in texto else []
        identidades = sorted(set(re.findall(r"identidad=(invitado-[a-c])", registros["pasarela"])))
        for servicio, contenido in registros.items():
            (self.registros / f"{servicio}.log").write_text(contenido, encoding="utf-8")
        ok = not fugas and identidades == ["invitado-a", "invitado-b", "invitado-c"]
        self.anotar("T21", "registros sin claves, huellas, contrasenas ni secreto del proxy; la pasarela registra "
                           "la identidad acreditada", ok, inicio, fugas=len(fugas), identidades=identidades)

    def copia_publicacion(self, nombre: str) -> Path:
        copia = self.trabajo / nombre
        shutil.copytree(self.publicacion, copia)
        for ruta in copia.rglob("*"):
            ruta.chmod(0o755 if ruta.is_dir() else 0o644)
        return copia

    @staticmethod
    def solo_lectura_local(raiz: Path) -> None:
        for ruta in sorted(raiz.rglob("*"), reverse=True):
            ruta.chmod(0o555 if ruta.is_dir() else 0o444)
        raiz.chmod(0o555)

    def api_auxiliar(self, nombre: str, sufijo: int, publicacion: Path, directorios: dict[str, str] | None = None):
        """Arranca otra API (misma imagen y frontera) en `<servicio>.<sufijo>` sobre `publicacion` montada RO.
        Devuelve su destino `ip:8010` y una funcion que la elimina."""
        s, d = self.redes["servicio"], self.redes["datos"]
        contenedor = f"{self.proyecto}-{nombre}"
        rutas = {"LABORATORIO_MODELOS": "/srv/pub/laboratorio", "CARTERAS_MODELOS": "/srv/pub/carteras",
                 "PREDICCIONES_MODELOS": "/srv/pub/predicciones", "PRONOSTICOS_EXPERIMENTALES": "/srv/pub/pronosticos",
                 **(directorios or {})}
        ejecutar(["docker", "create", "--name", contenedor, "--label", f"{ETIQUETA}={self.proyecto}", "--read-only",
                  "--tmpfs", "/tmp:size=16m", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                  "--user", "10001:10001", "--network", f"{self.proyecto}_servicio", "--ip", f"{s}.{sufijo}",
                  "-v", f"{publicacion}:/srv/pub:ro",
                  "-v", f"{self.secretos / 'api_database_url'}:/run/secretos/api_database_url:ro",
                  "-v", f"{self.secretos / 'api_claves'}:/run/secretos/api_claves:ro",
                  "-e", "DATABASE_URL_ARCHIVO=/run/secretos/api_database_url",
                  "-e", "API_PUBLICA_CLAVES_ARCHIVO=/run/secretos/api_claves",
                  "-e", f"API_PUBLICA_HOSTS={s}.{sufijo}:8010,127.0.0.1:8010",
                  "-e", f"API_PUBLICA_CLIENTES={s}.10,127.0.0.1", "-e", "API_PUBLICA_FICHAS_POR_MINUTO=1200",
                  "-e", "API_PUBLICA_FICHAS_POR_MINUTO_IP=2400", "-e", "API_PUBLICA_CONCURRENCIA_COSTOSAS=2",
                  "-e", "BASE_TIEMPO_MAXIMO_CONSULTA_MS=1500", "-e", "BASE_TIEMPO_MAXIMO_INACTIVA_MS=5000",
                  *[x for k, v in rutas.items() for x in ("-e", f"DIRECTORIO_{k}={v}")],
                  "-e", "DIRECTORIO_RESULTADOS_MODELOS=/srv/sin-publicar/resultados",
                  "-e", "DIRECTORIO_SIMULACIONES=/srv/sin-publicar/simulaciones",
                  self.imagenes["api"]["etiqueta"]])
        ejecutar(["docker", "network", "connect", "--ip", f"{d}.{sufijo}", f"{self.proyecto}_datos", contenedor])
        ejecutar(["docker", "start", contenedor])
        destino = f"{s}.{sufijo}:8010"
        espera = ("import http.client,time\n"
                  f"h='{s}.{sufijo}'\n"
                  "for i in range(80):\n"
                  "    try:\n"
                  "        c=http.client.HTTPConnection(h,8010,timeout=2); c.request('GET','/api/v1/salud'); c.getresponse(); break\n"
                  "    except Exception: time.sleep(0.5)\n")
        self.docker_exec("pasarela", "python", "-B", "-c", espera, timeout=120)
        return destino, lambda: ejecutar(["docker", "rm", "-f", contenedor], check=False)

    def api_alterada(self):
        """La API relee y vuelve a hashear el estimador `.pkl` en una copia alterada ANTES de montarla RO."""
        inicio = time.monotonic()
        alterada = self.copia_publicacion("publicacion-alterada")
        modelo = self.manifiesto["modelos"]["BALOTO"][-1]
        artefacto = json.loads((alterada / f"laboratorio/modelos/BALOTO/{modelo}.json").read_text(encoding="utf-8"))
        pkl = next((alterada / "laboratorio/modelos/BALOTO/estimadores").glob(artefacto["estimador"]["sha256"] + ".*"))
        pkl.write_bytes(pkl.read_bytes() + b"alteracion sintetica e102")
        self.solo_lectura_local(alterada)
        destino, borrar = self.api_auxiliar("api-alterada", 21, alterada)
        try:
            script = ("import http.client,json\n"
                      f"h,p='{destino}'.split(':'); k=open('/run/secretos/pasarela_clave_api').read().strip(); out={{}}\n"
                      f"for n,ruta in (('detalle','/api/v1/juegos/BALOTO/modelos-guardados/{modelo}'),('lista','/api/v1/juegos/BALOTO/modelos-guardados')):\n"
                      "    c=http.client.HTTPConnection(h,int(p),timeout=30); c.request('GET',ruta,headers={'X-API-Key':k}); r=c.getresponse(); b=json.loads(r.read())\n"
                      "    out[n]=[r.status,b.get('error',{}).get('codigo') if 'error' in b else ([e.get('estado') for e in b['elementos']] if 'elementos' in b else b.get('estado'))]\n"
                      "print(json.dumps(out))\n")
            r = self.docker_exec("pasarela", "python", "-B", "-c", script, timeout=120)
            res = json.loads(r.stdout.decode() or "{}")
        finally:
            borrar()
        ok = (res.get("detalle", [None])[0] == 409 and res["detalle"][1] == "alterado"
              and res.get("lista", [None, []])[0] == 200 and "alterado" in res["lista"][1])
        self.anotar("T22", "estimador .pkl alterado ANTES del montaje RO: la API lo vuelve a hashear y responde 409 "
                           "`alterado` (no lo sirve como valido)", ok, inicio, resultado=res)

    def almacen_vaciado_o_mal_apuntado(self):
        """Control NEGATIVO (v2, F1023-DAT-01): con un almacen requerido vaciado o mal apuntado la API responde 200
        (`sin_artefactos`), pero la matriz lo RECHAZA porque no coincide con lo publicado."""
        inicio = time.monotonic()
        variantes = {}
        vaciada = self.copia_publicacion("publicacion-sin-operacion")
        for ruta in sorted((vaciada / "pronosticos").rglob("*"), reverse=True):
            ruta.rmdir() if ruta.is_dir() else ruta.unlink()
        self.solo_lectura_local(vaciada)
        for nombre, sufijo, publicacion, directorios in (
                ("operacion-vaciada", 22, vaciada, None),
                ("laboratorio-mal-apuntado", 23, self.publicacion, {"LABORATORIO_MODELOS": "/srv/pub/carteras"})):
            destino, borrar = self.api_auxiliar(f"api-{nombre}", sufijo, publicacion, directorios)
            try:
                r = self.docker_exec("pasarela", "python", "-B", "-", entrada=self.guion_matriz(destino), timeout=600)
                m = json.loads(r.stdout.decode())
            finally:
                borrar()
            resultados = [f for f in m["filas"] if f["plantilla"] == "/api/v1/juegos/{codigo}/resultados"]
            variantes[nombre] = {"estados_resultados": sorted({f["estado"] for f in resultados}),
                                 "filas_resultados_rechazadas": sum(f["clase"] == "fallo" for f in resultados),
                                 "procedencias_rechazadas": sorted(k for k, v in m["procedencias"].items()
                                                                   if not v["coincide"])}
        ok = all(v["estados_resultados"] == [200] and v["filas_resultados_rechazadas"] == 4 for v in variantes.values())
        ok &= all(k.endswith(":operacion") for k in variantes["operacion-vaciada"]["procedencias_rechazadas"])
        ok &= len(variantes["operacion-vaciada"]["procedencias_rechazadas"]) == 4
        ok &= any(k.endswith(":laboratorio") for k in variantes["laboratorio-mal-apuntado"]["procedencias_rechazadas"])
        self.anotar("T24", "control negativo: almacen de operacion vaciado y laboratorio mal apuntado -> la API responde "
                           "200 pero la matriz lo rechaza (no coincide con la publicacion)", ok, inicio,
                    variantes=variantes)

    def ausencia_de_almacen(self):
        inicio = time.monotonic()
        r = ejecutar(["docker", "run", "--rm", "--name", f"{self.proyecto}-api-sin-almacen", "--label",
                      f"{ETIQUETA}={self.proyecto}", "--network", "none", "--read-only", "--tmpfs", "/tmp:size=16m",
                      "--cap-drop", "ALL", "--user", "10001:10001", "-v", f"{self.publicacion}:/srv/pub:ro",
                      "-v", f"{self.secretos / 'api_database_url'}:/run/secretos/api_database_url:ro",
                      "-v", f"{self.secretos / 'api_claves'}:/run/secretos/api_claves:ro",
                      "-e", "DATABASE_URL_ARCHIVO=/run/secretos/api_database_url",
                      "-e", "API_PUBLICA_CLAVES_ARCHIVO=/run/secretos/api_claves",
                      "-e", "API_PUBLICA_HOSTS=127.0.0.1:8010", "-e", "API_PUBLICA_CLIENTES=127.0.0.1",
                      "-e", "API_PUBLICA_CONCURRENCIA_COSTOSAS=2", "-e", "BASE_TIEMPO_MAXIMO_CONSULTA_MS=1500",
                      "-e", "BASE_TIEMPO_MAXIMO_INACTIVA_MS=5000",
                      "-e", "DIRECTORIO_LABORATORIO_MODELOS=/srv/pub/laboratorio",
                      "-e", "DIRECTORIO_CARTERAS_MODELOS=/srv/pub/carteras",
                      "-e", "DIRECTORIO_PREDICCIONES_MODELOS=/srv/pub/predicciones",
                      "-e", "DIRECTORIO_PRONOSTICOS_EXPERIMENTALES=/srv/pub/no-existe",
                      self.imagenes["api"]["etiqueta"]], check=False, timeout=120)
        texto = (r.stdout + r.stderr).decode(errors="replace")
        ok = r.returncode == 3 and "DIRECTORIO_PRONOSTICOS_EXPERIMENTALES: almacen de consulta ausente" in texto
        self.anotar("T23", "un almacen de consulta ausente impide arrancar (codigo 3): no se sirve vacio como valido",
                    ok, inicio, codigo=r.returncode,
                    motivo=next((l for l in texto.splitlines() if "perfil privado" in l), "")[:300])

    # ------------------------------------------------------------------ limpieza
    def _paso_limpieza(self, nombre: str, funcion):
        """Un paso aislado: su error se anota y NO impide los siguientes intentos sobre recursos propios."""
        try:
            return funcion()
        except Exception as error:
            self.errores_limpieza.append({"paso": nombre,
                                          "error": self.sanear(f"{type(error).__name__}: {str(error)[:300]}")})
            return None

    def _listar(self, *args) -> list[str]:
        return ejecutar(["docker", *args]).stdout.decode().split()

    def limpiar(self):
        inicio = time.monotonic()
        if self.conservar:
            self.anotar("Z00", "recursos conservados a peticion (--conservar)", True, inicio, proyecto=self.proyecto)
            return
        for servicio in ("proxy", "pasarela", "api", "postgres"):  # registros finales antes de borrar
            def registro(servicio=servicio):
                r = ejecutar(["docker", "logs", self.contenedor(servicio)], check=False)
                if r.returncode == 0 and self.registros.is_dir():
                    texto = (r.stdout + r.stderr).decode(errors="replace")
                    (self.registros / f"final-{servicio}.log").write_text(self.sanear(texto), encoding="utf-8")
            self._paso_limpieza(f"registro final de {servicio}", registro)
        self._paso_limpieza("compose down", lambda: self.compose("down", "--remove-orphans", "--timeout", "10",
                                                                 check=False))
        etiqueta = f"label={ETIQUETA}={self.proyecto}"

        def contenedores():
            ids = self._listar("ps", "-aq", "--filter", etiqueta)
            if ids:
                ejecutar(["docker", "rm", "-f", *ids], check=False)

        def volumenes():  # etiqueta del proyecto Y nombre con su prefijo: nunca un volumen ajeno
            nombres = [n for n in self._listar("volume", "ls", "-q", "--filter", etiqueta) if n.startswith(self.proyecto)]
            if nombres:
                ejecutar(["docker", "volume", "rm", *nombres], check=False)

        self._paso_limpieza("contenedores del proyecto", contenedores)
        self._paso_limpieza("volumenes del proyecto", volumenes)
        restos: dict[str, list[str]] = {}
        for clave, args in (("contenedores", ("ps", "-aq", "--filter", f"name={self.proyecto}")),
                            ("redes", ("network", "ls", "-q", "--filter", f"name={self.proyecto}")),
                            ("volumenes", ("volume", "ls", "-q", "--filter", f"name={self.proyecto}"))):
            listado = self._paso_limpieza(f"verificacion de {clave}", lambda args=args: self._listar(*args))
            restos[clave] = listado if listado is not None else ["no verificado"]
        self.anotar("Z01", "limpieza solo de los recursos del proyecto (contenedores, redes, volumen)",
                    not any(restos.values()) and not self.errores_limpieza, inicio, restos=restos,
                    errores_limpieza=self.errores_limpieza,
                    imagenes_conservadas=[i.get("etiqueta") for i in self.imagenes.values()])

    def escribir_informe(self) -> int:
        """Siempre un JSON valido y saneado; exito solo sin fallo inicial, sin errores de limpieza y con todas las
        comprobaciones correctas."""
        correcto = (bool(self.resultados) and all(r["ok"] for r in self.resultados) and self.error_inicial is None
                    and not self.errores_limpieza)
        resumen = {"proyecto": self.proyecto, "plataforma": sys.platform, "python": sys.version.split()[0],
                   "segundos": round(time.monotonic() - self.inicio, 1), "imagenes": self.imagenes,
                   "comprobaciones": len(self.resultados), "correctas": sum(r["ok"] for r in self.resultados),
                   "todas_correctas": correcto, "error_inicial": self.error_inicial,
                   "errores_limpieza": self.errores_limpieza, "resultados": self.resultados,
                   "atribucion": "Linux aislado (Claude), Docker propio; no acredita Windows ni el CI remoto"}
        texto = self.sanear(json.dumps(resumen, ensure_ascii=False, indent=1))
        try:
            temporal = self.salida / "demostracion.json.tmp"
            temporal.write_text(texto, encoding="utf-8")
            os.replace(temporal, self.salida / "demostracion.json")
        except OSError as error:  # sin archivo: el informe va a la salida estandar y el codigo es de fallo
            print(f"no se pudo escribir demostracion.json: {type(error).__name__}", flush=True)
            print(texto, flush=True)
            return 1
        print(f"comprobaciones {resumen['correctas']}/{resumen['comprobaciones']} correctas"
              + ("" if correcto else " - FALLO"), flush=True)
        return 0 if correcto else 1

    def ejecutar(self) -> int:
        self.salida.mkdir(parents=True, exist_ok=False)
        interrumpido = None
        inicio = time.monotonic()
        try:
            self.trabajo.mkdir(mode=0o700)
            self.registros.mkdir()
            for fase in ("comprobar_entorno", "preparar_pki", "preparar_secretos", "construir_imagenes",
                         "preparar_publicacion", "levantar"):
                self.fase = fase
                inicio = time.monotonic()
                getattr(self, fase)()
            self.fase = "comprobaciones"
            for paso in (self.tls_e_identidad, self.identidad_falsa, self.cuotas, self.acceso_directo, self.matriz,
                         self.solo_lectura, self.recursos, self.claves, self.revocacion, self.navegador,
                         self.api_alterada, self.almacen_vaciado_o_mal_apuntado, self.ausencia_de_almacen,
                         self.integridad_y_registros):
                inicio = time.monotonic()
                try:
                    paso()
                except Exception as error:  # una comprobacion rota se anota como fallida y se sigue
                    self.anotar(f"X-{getattr(paso, '__name__', 'paso')}", "excepcion en una comprobacion", False,
                                inicio, error=self.sanear(f"{type(error).__name__}: {str(error)[:300]}"))
        except BaseException as error:  # fallo de una fase: se conserva el motivo ORIGINAL y se limpia igualmente
            if isinstance(error, KeyboardInterrupt):
                interrumpido = error
            self.error_inicial = {"fase": self.fase, "tipo": type(error).__name__,
                                  "mensaje": self.sanear(str(error)[:600])}
            self.anotar(f"X-{self.fase}", f"fallo en la fase {self.fase}: se interrumpe la demostracion y se limpia",
                        False, inicio, error=f"{self.error_inicial['tipo']}: {self.error_inicial['mensaje']}")
        try:
            self.limpiar()
        except BaseException as error:  # defensa: incluso un fallo inesperado de la limpieza queda en el informe
            self.errores_limpieza.append({"paso": "limpieza",
                                          "error": self.sanear(f"{type(error).__name__}: {str(error)[:300]}")})
        codigo = self.escribir_informe()
        if interrumpido is not None:
            raise interrumpido
        return codigo


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--salida", required=True)
    p.add_argument("--python-preparacion", required=True)
    p.add_argument("--ca-extra", default=None, help="CA adicional SOLO para construir (proxy con inspeccion TLS)")
    p.add_argument("--conservar", action="store_true")
    a = p.parse_args(argv)
    demo = Demostracion(Path(a.salida), a.python_preparacion, a.ca_extra, a.conservar)
    if demo.salida.exists():
        print(f"la salida ya existe; use una carpeta nueva: {a.salida}", file=sys.stderr, flush=True)
        return 2
    return demo.ejecutar()


if __name__ == "__main__":
    raise SystemExit(main())
