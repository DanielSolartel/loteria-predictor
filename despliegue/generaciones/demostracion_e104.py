"""Fase 10 (E10.4): demostracion de extremo a extremo de las generaciones sobre PostgreSQL y archivos SINTETICOS.

Fuente sintetica con los productores REALES (`tests.e102_preparar_publicacion`: cuatro juegos, tres
procedencias con resultados observados) y una prediccion nueva de BALOTO con `objetivo = corte + 1` y su
explicacion (C7). Despues, con la CLI `scripts.generaciones` en procesos aparte:

  G1  capturar (rol de captura de solo lectura) -> verificar -> importar (rol importador) -> activar;
      API PRIVADA ligada a G1 (uvicorn, usuario sin privilegios) consultada por HTTP;
  R   capturar con alcance `respaldo` en el MISMO estado -> respaldar (cifrado) -> verificar-respaldo ->
      restaurar en una base y carpeta NUEVAS -> criterios R-L (huellas, Alembic y filas, 0 ilegibles nuevos y
      cuerpos identicos a G1 en los 19 endpoints x 4 juegos y las tres procedencias) -> retencion;
  N   controles negativos: paquete alterado, archivo de mas o de menos, otra clave, incompatibilidad (re-firmada),
      respaldo alterado o truncado, API ligada a otra base o a una generacion alterada;
  F   fallos inyectados en cada paso de la importacion de G2 y un proceso importador terminado con SIGKILL:
      nunca queda una generacion parcial utilizable y la activa (G1) no cambia; despues G2 se acepta.

Exige una base de pruebas (`loteria_prueba`, vacia de sorteos) con los roles de
`despliegue/consulta-privada/postgres/roles.sql` y `despliegue/generaciones/postgres/{roles,rol-captura}.sql`.
Las URL se leen de archivos. Salida: `<salida>/demostracion.json` (sin URL ni claves). Codigo 0 solo si todo
se cumple.

    python despliegue/generaciones/demostracion_e104.py --salida <dir nuevo> --url-propietario-archivo <f>
        --url-captura-archivo <f> --url-admin-archivo <f> --url-lector-archivo <f>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
BACKEND = RAIZ / "backend"
sys.path.insert(0, str(BACKEND))
ALMACENES_FUENTE = {"pronosticos": "f4/pronosticos", "laboratorio": "f4/laboratorio", "carteras": "f4/carteras",
                    "predicciones": "f4/predicciones", "operacion": "f4/operacion-producto3"}


class Demo:
    def __init__(self, salida: Path, urls: dict, python: str):
        self.salida, self.urls, self.python = salida, urls, python
        self.filas, self.secretos, self.almacenes = [], salida / "secretos", {}
        self.recorrido_g1 = None
        self.ids: set[str] = set()  # generaciones de ESTA demostracion: solo sus bases se borran al final
        self.secretos.mkdir(mode=0o700)
        for nombre, url in urls.items():
            ruta = self.secretos / f"url-{nombre}"
            ruta.write_text(url + "\n", encoding="ascii")
            ruta.chmod(0o600)

    # -- utilidades ---------------------------------------------------------
    def anotar(self, ident: str, descripcion: str, ok: bool, **detalle) -> bool:
        self.filas.append({"id": ident, "descripcion": descripcion, "ok": bool(ok), **detalle})
        print(json.dumps({"id": ident, "ok": bool(ok), **{k: v for k, v in detalle.items() if k != "informe"}},
                         ensure_ascii=False)[:600], flush=True)
        return ok

    def entorno(self, base: str = "propietario", almacenes: dict | None = None) -> dict:
        e = {k: v for k, v in os.environ.items() if not k.startswith(("DATABASE_URL", "DIRECTORIO_", "API_PUBLICA_",
                                                                     "GENERACION_"))}
        e["DATABASE_URL"] = self.urls[base].replace("postgresql://", "postgresql+psycopg://", 1)
        for nombre, ruta in (self.almacenes if almacenes is None else almacenes).items():
            e[_ajuste(nombre).upper()] = str(ruta)
        e["PYTHONDONTWRITEBYTECODE"] = "1"
        return e

    def cli(self, *args, base="propietario", almacenes=None, timeout=900) -> tuple[int, dict | str]:
        r = subprocess.run([self.python, "-B", "-m", "scripts.generaciones", *map(str, args)], cwd=BACKEND,
                           env=self.entorno(base, almacenes), capture_output=True, text=True, timeout=timeout)
        try:
            return r.returncode, json.loads(r.stdout)
        except ValueError:
            return r.returncode, (r.stderr or r.stdout)[-800:]

    def admin(self):
        from app.infrastructure.generaciones import base_logica as bl
        from app.infrastructure.generaciones import importacion as im
        return bl.conectar(im._url_con_base(self.urls["admin"], "postgres"), autocommit=True)

    def bases(self, patron: str) -> list[str]:
        with self.admin() as c:
            return [r[0] for r in c.execute("SELECT datname FROM pg_database WHERE datname LIKE %s ORDER BY 1",
                                            (patron,)).fetchall()]

    # -- fuente -------------------------------------------------------------
    def preparar(self) -> None:
        r = subprocess.run([self.python, "-B", "-m", "tests.e102_preparar_publicacion", "--salida",
                            str(self.salida / "fuente")], cwd=BACKEND, env=self.entorno(almacenes={}),
                           capture_output=True, text=True, timeout=1800)
        trabajo = next((self.salida / "fuente").glob("e102-trabajo-*"))
        self.almacenes = {n: trabajo / "generacion" / r_ for n, r_ in ALMACENES_FUENTE.items()}
        for n in ("resultados", "automatizacion", "simulaciones"):
            self.almacenes[n] = trabajo / "sin_publicar" / n
        self.anotar("D01", "fuente sintetica con los productores reales (4 juegos, 3 procedencias)", r.returncode == 0,
                    resumen=r.stdout.strip()[-400:] if r.returncode == 0 else r.stderr[-600:])
        r = subprocess.run([self.python, "-B", "-m", "scripts.predicciones", "generar", "--juego", "BALOTO"],
                           cwd=BACKEND, env=self.entorno(), capture_output=True, text=True, timeout=900)
        self.anotar("D02", "prediccion nueva de BALOTO (cartera con objetivo = corte + 1 y explicacion) con el "
                    "productor real", r.returncode == 0, detalle=None if r.returncode == 0 else r.stderr[-400:])

    # -- G1 -----------------------------------------------------------------
    def g1(self) -> None:
        s = self.secretos
        rc, d = self.cli("claves-firma", "--privada", s / "firma.pem", "--publica", s / "firma.pub")
        rc2, d2 = self.cli("claves-respaldo", "--privada", s / "respaldo.pem", "--publica", s / "respaldo.pub")
        self.anotar("D03", "claves locales de firma (Ed25519) y de respaldo (X25519), privadas 0600", rc == rc2 == 0)
        from app.infrastructure.generaciones import archivos as ar
        antes = ar.fotografiar(self.almacenes)
        rc, d = self.cli("capturar", "--destino", self.salida / "capturas", "--clave-privada", s / "firma.pem",
                         "--intentos", 1, base="captura")
        despues = ar.fotografiar(self.almacenes)
        self.g1_id = d.get("generacion") if isinstance(d, dict) else None
        self.ids.add(str(self.g1_id))
        self.paquete_g1 = self.salida / "capturas" / str(self.g1_id)
        m = json.loads((self.paquete_g1 / "manifiesto.json").read_text()) if self.g1_id else {}
        self.anotar("D04", "captura G1 sellada con el rol de captura (solo lectura); la fuente no cambia",
                    rc == 0 and antes == despues and m.get("coherencia", {}).get("rechazos") == 0,
                    generacion=self.g1_id, coherencia=m.get("coherencia"), archivos=len(m.get("archivos", {})))
        self.anotar("D05", "C7: la cartera con objetivo = corte + 1 y su explicacion se conservan en la generacion",
                    m.get("coherencia", {}).get("objetivos_posteriores_al_ultimo_sorteo", 0) >= 2)
        # Respaldo en el MISMO estado (sin escritores entre ambas capturas): base de la comparacion R-L.
        rc, d = self.cli("capturar", "--destino", self.salida / "capturas-respaldo", "--clave-privada",
                         s / "firma.pem", "--alcance", "respaldo", "--intentos", 1, base="captura")
        self.respaldo_id = d.get("generacion") if isinstance(d, dict) else None
        self.ids.add(str(self.respaldo_id))
        self.anotar("R01", "captura con alcance respaldo (base, publicables, informes y estado operativo)", rc == 0,
                    generacion=self.respaldo_id)
        rc, d = self.cli("verificar", "--paquete", self.paquete_g1, "--clave-publica", s / "firma.pub")
        self.anotar("D06", "verificacion del paquete G1 (firma, identidad, archivos exactos y huellas)", rc == 0)
        self.raiz = self.salida / "srv-pub"
        t = time.monotonic()
        rc, d = self.cli("importar", "--paquete", self.paquete_g1, "--clave-publica", s / "firma.pub", "--raiz",
                         self.raiz, "--url-admin-archivo", s / "url-admin", "--url-lector-archivo", s / "url-lector")
        self.importacion_g1 = d if isinstance(d, dict) else {}
        contenido = self.importacion_g1.get("consultas", {}).get("contenido", {})
        # Requisitos NO VACIOS propios de la demostracion (datos sinteticos completos; E104-DAT-06: no se exigen
        # a una fuente real, que solo se rechaza por dano o perdida frente a lo sellado)
        procedencias = {f"{j}:{p}": v["emisiones"] > 0 and v["lineas_con_resultado_observado"] > 0
                        for j, c in contenido.items() for p, v in c["procedencias"].items()}
        fiabilidad = {j: c["fiabilidad"] for j, c in contenido.items()}
        lecturas = self.importacion_g1.get("consultas", {}).get("lecturas", {})
        self.anotar("D07", "importacion de G1: preparacion aislada, esquema, filas, coherencia, permisos y consultas",
                    rc == 0 and self.importacion_g1.get("resultado") == "aceptada", segundos=round(time.monotonic() - t, 1),
                    pasos=self.importacion_g1.get("pasos"), consultas=self.importacion_g1.get("consultas", {}).get("total"))
        self.anotar("D08", "(requisito de la demostracion) /resultados con operacion, laboratorio y carteras con "
                    "emisiones y resultado observado en los 4 juegos", len(procedencias) == 12 and all(procedencias.values()), procedencias=procedencias)
        self.anotar("D09", "(requisito de la demostracion) /fiabilidad no vacua en los 4 juegos (base consultada, lineas y muestra >= 1 sorteo)",
                    len(fiabilidad) == 4 and all(f["con_muestra"] >= 1 and f["base"] == "consultada"
                                                 for f in fiabilidad.values()), fiabilidad=fiabilidad)
        self.anotar("D10", "DAT-01 medido: la API solo lee los subarboles declarados (sondeos de lo ausente aparte)",
                    lecturas.get("fuera_de_lo_declarado") == [] and not lecturas.get("escrituras"),
                    lecturas=lecturas)
        rc, d = self.cli("activar", "--raiz", self.raiz, "--id", self.g1_id, "--clave-publica", s / "firma.pub",
                         "--url-admin-archivo", s / "url-admin")
        self.anotar("D11", "activacion explicita de G1 (activa.json; no arranca ni para procesos)",
                    rc == 0 and json.loads((self.raiz / "activa.json").read_text())["id"] == self.g1_id)

    # -- API privada ligada --------------------------------------------------
    def api_privada(self, carpeta: Path, base: str, *, esperar_arranque: bool = True):
        puerto = _puerto_libre()
        from app.api.publica.seguridad import generar_clave
        clave = generar_clave()
        secretos = self.salida / "api-secretos" / f"{puerto}"
        secretos.mkdir(parents=True)
        (secretos / "url").write_text(self._url_de_base(self.urls["lector"], base) + "\n", encoding="ascii")
        (secretos / "claves").write_text(f"demo:sha256:{hashlib.sha256(clave.encode()).hexdigest()}\n", encoding="ascii")
        e = {k: v for k, v in os.environ.items() if not k.startswith(("DATABASE_URL", "DIRECTORIO_", "API_PUBLICA_",
                                                                     "GENERACION_"))}
        vacios = self.salida / "sin-publicar"
        e.update({"DATABASE_URL_ARCHIVO": str(secretos / "url"), "API_PUBLICA_CLAVES_ARCHIVO": str(secretos / "claves"),
                  "API_PUBLICA_HOSTS": f"127.0.0.1:{puerto}", "API_PUBLICA_CLIENTES": "127.0.0.1",
                  "API_PUBLICA_CONCURRENCIA_COSTOSAS": "2", "BASE_TIEMPO_MAXIMO_CONSULTA_MS": "5000",
                  "BASE_TIEMPO_MAXIMO_INACTIVA_MS": "5000", "API_PUBLICA_DOCUMENTACION": "false",
                  # 77 consultas seguidas de un solo cliente: cuota de la demostracion (la real se prueba en E10.2)
                  "API_PUBLICA_FICHAS_POR_MINUTO": "100000", "API_PUBLICA_FICHAS_POR_MINUTO_IP": "100000",
                  "GENERACION_DIRECTORIO": str(carpeta), "GENERACION_CLAVE_PUBLICA": str(secretos / "firma.pub"),
                  "DIRECTORIO_RESULTADOS_MODELOS": str(vacios / "resultados"),
                  "DIRECTORIO_OPERACION": str(vacios / "operacion"),
                  "DIRECTORIO_AUTOMATIZACION": str(vacios / "automatizacion"),
                  "DIRECTORIO_SIMULACIONES": str(vacios / "simulaciones"), "PYTHONDONTWRITEBYTECODE": "1"})
        shutil.copy(self.secretos / "firma.pub", secretos / "firma.pub")
        orden = [self.python, "-B", "-m", "uvicorn", "app.api.publica.privada:app", "--host", "127.0.0.1", "--port",
                 str(puerto), "--workers", "1", "--no-access-log", "--no-proxy-headers"]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            # El perfil privado no corre como root. En un entorno que solo tiene root (contenedor de
            # desarrollo) se ejecuta en un espacio de nombres de usuario: dentro, uid 10001 (como la imagen).
            # En CI el ejecutor ya no es root y esto no se usa.
            orden = ["unshare", "--user", "--map-user=10001", "--map-group=10001", *orden]
        proceso = subprocess.Popen(orden, cwd=BACKEND, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if not esperar_arranque:
            try:
                salida, errores = proceso.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                proceso.kill()
                salida, errores = proceso.communicate()
            return proceso.returncode, errores[-400:]
        for _ in range(240):
            if proceso.poll() is not None:
                return None, proceso.stderr.read()[-600:]
            try:
                with socket.create_connection(("127.0.0.1", puerto), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.25)
        return proceso, (puerto, clave)

    @staticmethod
    def _url_de_base(url: str, base: str) -> str:
        from sqlalchemy.engine import make_url
        return make_url(url).set(drivername="postgresql+psycopg", database=base).render_as_string(hide_password=False)

    def api_ligada(self) -> None:
        import http.client
        from app.infrastructure.generaciones.importacion import nombre_base

        proceso, datos = self.api_privada(self.raiz / "generaciones" / self.g1_id, nombre_base(self.g1_id, True))
        if not hasattr(proceso, "terminate"):
            self.anotar("D12", "API privada ligada a G1", False, detalle=datos)
            return
        puerto, clave = datos

        def get(ruta):
            c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=60)
            c.request("GET", ruta, headers={"X-API-Key": clave, "Host": f"127.0.0.1:{puerto}"})
            r = c.getresponse()
            cuerpo = json.loads(r.read() or b"null")
            c.close()
            return r.status, cuerpo

        try:
            from app.infrastructure.generaciones import consultas
            m_g1 = json.loads((self.paquete_g1 / "manifiesto.json").read_text())
            sellado = consultas.esperado_de(m_g1["juegos"],
                                            json.loads((self.paquete_g1 / "coherencia.json").read_text()))
            recorrido = consultas.recorrer(get, sellado)
            no_vacios = consultas.requisitos_de_demostracion(recorrido)
            estado, pred = get("/api/v1/juegos/BALOTO/predicciones")
            prediccion = (pred or {}).get("prediccion") or {}
        finally:
            proceso.terminate()
            proceso.wait(timeout=30)
        self.anotar("D12", "API PRIVADA ligada a G1 por HTTP (perfil privado, rol lector, usuario sin privilegios): "
                    "consultas sin dano ni perdida frente a los recuentos sellados", not recorrido["fallos"],
                    total=recorrido["total"], fallos=recorrido["fallos"][:5])
        self.anotar("D12b", "requisitos NO VACIOS de la demostracion (solo aqui; no se exigen a fuentes reales): "
                    "procedencias con resultado observado, /fiabilidad con muestra, prediccion, carteras y modelos",
                    not no_vacios, faltan=no_vacios[:5])
        m = json.loads((self.paquete_g1 / "manifiesto.json").read_text())
        esperado = m["juegos"]["BALOTO"]["ultimo_sorteo"] + 1
        self.anotar("D13", "C7 publicada: /predicciones de BALOTO sirve la cartera pendiente (objetivo = corte + 1) "
                    "con su explicacion", estado == 200 and prediccion.get("objetivo") == esperado and
                    prediccion.get("corte") == esperado - 1 and prediccion.get("explicacion_disponible") is True,
                    objetivo=prediccion.get("objetivo"), esperado=esperado,
                    explicacion=prediccion.get("explicacion_disponible"))
        self.recorrido_g1 = recorrido

    # -- R-L ----------------------------------------------------------------
    def respaldo(self) -> None:
        s = self.secretos
        paquete = self.salida / "capturas-respaldo" / str(self.respaldo_id)
        destino = self.salida / "respaldos"
        rc, cat = self.cli("respaldar", "--paquete", paquete, "--clave-publica-firma", s / "firma.pub",
                           "--clave-publica-respaldo", s / "respaldo.pub", "--destino", destino)
        archivo = destino / cat["archivo"] if isinstance(cat, dict) and "archivo" in cat else None
        claro = sum(1 for _ in paquete.rglob("*.json"))  # archivos JSON del paquete en claro (antes de cifrar)
        self.anotar("R02", "respaldo cifrado (X25519 + HKDF + AES-256-GCM por bloques) con catalogo", rc == 0 and
                    archivo is not None and b"sorteos" not in archivo.read_bytes(), bytes=(cat or {}).get("bytes"),
                    json_en_claro=claro)
        rc, d = self.cli("verificar-respaldo", "--archivo", archivo, "--clave-privada-respaldo", s / "respaldo.pem",
                         "--clave-publica-firma", s / "firma.pub")
        self.anotar("R03", "verificacion completa del respaldo (descifrado, firma y huellas)", rc == 0)
        for nombre, mutar in (("alterado", lambda b: b[:-200] + bytes([b[-200] ^ 1]) + b[-199:]),
                              ("truncado", lambda b: b[:-300])):
            copia = self.salida / "respaldos-alterados" / nombre / archivo.name
            copia.parent.mkdir(parents=True)
            copia.write_bytes(mutar(archivo.read_bytes()))
            shutil.copy(archivo.with_name(archivo.name + ".json"), copia.with_name(copia.name + ".json"))
            rc2, d2 = self.cli("verificar-respaldo", "--archivo", copia, "--clave-privada-respaldo", s / "respaldo.pem",
                               "--clave-publica-firma", s / "firma.pub")
            self.anotar(f"N-respaldo-{nombre}", f"respaldo {nombre}: rechazado", rc2 == 1,
                        motivo=d2.get("motivo") if isinstance(d2, dict) else d2)
        t = time.monotonic()
        rc, d = self.cli("restaurar", "--archivo", archivo, "--clave-privada-respaldo", s / "respaldo.pem",
                         "--clave-publica-firma", s / "firma.pub", "--destino", self.salida / "restauracion",
                         "--url-admin-archivo", s / "url-admin")
        segundos = round(time.monotonic() - t, 1)
        from app.infrastructure.generaciones import respaldo as rp
        try:
            estado_rest = rp.comprobar_restauracion(self.salida / "restauracion")["estado"]
        except Exception as error:  # noqa: BLE001 - se anota
            estado_rest = f"{type(error).__name__}: {error}"
        self.anotar("R04", "restauracion aislada: base NUEVA y carpeta NUEVA, estado `completa`; no registra ni "
                    "activa la tarea", rc == 0 and isinstance(d, dict) and d.get("base", "").startswith("rest_")
                    and estado_rest == "completa", segundos=segundos, estado=estado_rest,
                    base=d.get("base") if isinstance(d, dict) else d)
        if rc != 0:
            return
        self.criterios_rl(d["base"], Path(d["almacenes"]))
        # retencion: dos respaldos; la politica por defecto conserva ambos; una minima conserva 1
        rc, cat2 = self.cli("respaldar", "--paquete", paquete, "--clave-publica-firma", s / "firma.pub",
                            "--clave-publica-respaldo", s / "respaldo.pub", "--destino", destino)
        rc, plan = self.cli("retener", "--destino", destino)
        dos = len(list(destino.glob("*.lpr"))) == 2
        rc2, con_minimo = self.cli("retener", "--destino", destino, "--minimo", 2)
        rc3, aplicado = self.cli("retener", "--destino", destino, "--aplicar")
        quedan = sorted(p.name for p in destino.glob("*.lpr"))
        self.anotar("R05", "retencion configurable (GFS): en seco propone borrar solo el duplicado mas antiguo del dia "
                    "sin borrar nada; --minimo 2 conserva ambos; --aplicar borra solo respaldos verificados y conserva "
                    "el mas reciente", rc == rc2 == rc3 == 0 and dos and len(plan["borrar"]) == 1 and
                    not plan["aplicado"] and not con_minimo["borrar"] and aplicado["borrados"] == plan["borrar"] and
                    quedan == plan["conservar"], en_seco=plan, con_minimo=con_minimo["conservar"], quedan=quedan)

    def criterios_rl(self, base: str, almacenes: Path) -> None:
        from app.infrastructure.generaciones import base_logica as bl
        from app.infrastructure.generaciones import importacion as im

        m_resp = json.loads((self.salida / "capturas-respaldo" / self.respaldo_id / "manifiesto.json").read_text())
        m_g1 = json.loads((self.paquete_g1 / "manifiesto.json").read_text())
        with bl.conectar(im._url_con_base(self.urls["admin"], base)) as c:
            revision = bl.revision_alembic(c)
            filas = {n: h.como_dict() for n, h in bl.huellas(c).items()}
        self.anotar("R06", "R-L (1-2): huellas del paquete al 100 %, revision de Alembic y filas iguales al origen",
                    revision == m_resp["esquema"]["revision_alembic"] and filas == m_resp["base"]["tablas"] ==
                    m_g1["base"]["tablas"], revision=revision, tablas=len(filas))
        from app.infrastructure.generaciones import coherencia as co
        historico, cerrar = im._historico_de(im._url_con_base(self.urls["admin"], base))
        try:
            informe = co.evaluar(almacenes, historico, juegos_de_la_base=m_resp["juegos"])
        finally:
            cerrar()
        self.anotar("R07", "R-L (3): 0 ilegibles y 0 estimadores ausentes o alterados nuevos; misma coherencia",
                    informe["resumen"] == m_g1["coherencia"] and informe["resumen"]["ilegibles"] == 0,
                    resumen=informe["resumen"])
        salida = self.salida / "restauracion-consultas.json"
        from app.infrastructure.generaciones import consultas
        restaurada = im.consultas_en_proceso_aparte(
            im._url_con_base(self.urls["admin"], base), almacenes, salida,
            esperado=consultas.esperado_de(m_resp["juegos"], json.loads((self.salida / "capturas-respaldo" /
                                                                         self.respaldo_id / "coherencia.json")
                                                                        .read_text())))
        g1 = (self.recorrido_g1 or {"rutas": {}})["rutas"]
        diferencias = [r for r in sorted(set(restaurada["rutas"]) | set(g1)) if restaurada["rutas"].get(r) != g1.get(r)]
        self.anotar("R08", "R-L (4): los mismos cuerpos que G1 en los 19 endpoints x 4 juegos y las 3 procedencias "
                    "(salvo /salud y /estado, solo estado)", bool(g1) and not diferencias and not restaurada["fallos"],
                    rutas=len(restaurada["rutas"]), diferencias=diferencias[:10])

    # -- negativos ----------------------------------------------------------
    def negativos(self) -> None:
        s = self.secretos
        activa = (self.raiz / "activa.json").read_bytes()

        def copia(nombre):
            destino = self.salida / "negativos" / nombre / self.g1_id
            shutil.copytree(self.paquete_g1, destino)
            return destino

        def importar(paquete):
            return self.cli("importar", "--paquete", paquete, "--clave-publica", s / "firma.pub", "--raiz",
                            self.salida / "srv-negativos", "--url-admin-archivo", s / "url-admin",
                            "--url-lector-archivo", s / "url-lector")

        p = copia("alterado")
        objetivo = next(p.glob("archivos/carteras/carteras/*/*/*.json"))
        datos = bytearray(objetivo.read_bytes())
        datos[len(datos) // 2] ^= 1
        objetivo.write_bytes(bytes(datos))
        rc, d = importar(p)
        self.anotar("N01", "paquete con un byte alterado en una cartera: rechazado en la verificacion",
                    rc == 1 and d.get("paso") == "verificacion", motivo=d.get("motivo"))
        p = copia("archivo-de-mas")
        (p / "archivos" / "pronosticos" / "extra.json").write_text("{}\n")
        rc, d = importar(p)
        self.anotar("N02", "archivo de mas en el paquete: rechazado", rc == 1 and d.get("paso") == "verificacion")
        p = copia("archivo-de-menos")
        next(p.glob("base/sorteos.jsonl")).unlink()
        rc, d = importar(p)
        self.anotar("N03", "volcado de una tabla ausente: rechazado", rc == 1 and d.get("paso") == "verificacion")
        otra_pub = self.salida / "negativos" / "otra.pub"
        from app.infrastructure.generaciones import firma
        firma.generar(self.salida / "negativos" / "otra.pem", otra_pub)
        rc, d = self.cli("verificar", "--paquete", self.paquete_g1, "--clave-publica", otra_pub)
        self.anotar("N04", "otra clave publica de firma: rechazado", rc == 1, motivo=d.get("motivo"))
        p = self.incompatible()
        rc, d = importar(p)
        self.anotar("N05", "generacion firmada con la clave valida pero de otra revision de Alembic: rechazada por "
                    "compatibilidad", rc == 1 and d.get("paso") == "compatibilidad", motivo=d.get("motivo"))
        from app.infrastructure.generaciones.importacion import nombre_base
        rc, err = self.api_privada(self.raiz / "generaciones" / self.g1_id, "loteria_prueba", esperar_arranque=False)
        self.anotar("N06", "API ligada a G1 pero conectada a otra base: no arranca (codigo 3)", rc == 3, motivo=err)
        alterada = self.salida / "negativos" / "generacion-alterada" / self.g1_id
        shutil.copytree(self.raiz / "generaciones" / self.g1_id, alterada)
        for carpeta, _, nombres in os.walk(alterada):  # copia PROPIA recien hecha (copytree no sigue enlaces aqui)
            os.chmod(carpeta, 0o700)
            for nombre in nombres:
                os.chmod(os.path.join(carpeta, nombre), 0o600)
        objetivo = next(alterada.glob("archivos/predicciones/explicaciones/*/*.json"))
        objetivo.write_bytes(objetivo.read_bytes().replace(b'"', b"'", 1))
        rc, err = self.api_privada(alterada, nombre_base(self.g1_id, True), esperar_arranque=False)
        self.anotar("N07", "API ligada a una generacion con una explicacion alterada: no arranca (codigo 3)", rc == 3,
                    motivo=err)
        self.anotar("N08", "los rechazos no tocaron la generacion activa", (self.raiz / "activa.json").read_bytes() ==
                    activa and self.verificar_g1())

    def incompatible(self) -> Path:
        from app.infrastructure.generaciones import firma
        from app.infrastructure.generaciones.captura import id_de
        from app.infrastructure.generaciones.formato import canonico

        m = json.loads((self.paquete_g1 / "manifiesto.json").read_text())
        m["codigo"]["revision_alembic"] = m["esquema"]["revision_alembic"] = "9999"
        m["id"] = id_de(m)
        self.ids.add(m["id"])
        destino = self.salida / "negativos" / "incompatible" / m["id"]
        shutil.copytree(self.paquete_g1, destino)
        datos = canonico(m)
        (destino / "manifiesto.json").write_bytes(datos)
        clave = firma.cargar_privada(self.secretos / "firma.pem")
        (destino / "manifiesto.firma").write_text(firma.firmar(clave, datos) + "\n", encoding="ascii")
        return destino

    def verificar_g1(self) -> bool:
        from app.infrastructure.generaciones import importacion as im
        try:
            with self.admin() as c:
                im.verificar_publicada(self.raiz / "generaciones" / self.g1_id, self.secretos / "firma.pub", c)
            return True
        except Exception:
            return False

    # -- fallos durante la importacion ---------------------------------------
    def fallos(self) -> None:
        from app.infrastructure.generaciones import importacion as im

        r = subprocess.run([self.python, "-B", "-m", "scripts.predicciones", "generar", "--juego", "MILOTO"],
                           cwd=BACKEND, env=self.entorno(), capture_output=True, text=True, timeout=900)
        rc, d = self.cli("capturar", "--destino", self.salida / "capturas", "--clave-privada",
                         self.secretos / "firma.pem", "--intentos", 1, base="captura")
        g2 = d.get("generacion") if isinstance(d, dict) else None
        self.ids.add(str(g2))
        self.anotar("F00", "G2: otra prediccion (MILOTO) y una captura nueva", r.returncode == 0 and rc == 0, generacion=g2)
        paquete = self.salida / "capturas" / str(g2)
        destino = im.Destino(self.raiz, self.urls["admin"], self.urls["lector"])
        activa = (self.raiz / "activa.json").read_bytes()
        puntos = ("verificacion", "base_creada", "esquema", "filas_cargadas", "archivos", "coherencia", "permisos",
                  "consultas", "base_aceptada")
        resultados = {}
        for punto in puntos:
            def fase(nombre, punto=punto):
                if nombre == punto:
                    raise OSError(f"fallo inyectado en {punto}")
            try:
                im.importar(paquete, self.secretos / "firma.pub", destino, fase=fase)
                rechazada = False
            except im.ImportacionRechazada:
                rechazada = True
            resultados[punto] = {"rechazada": rechazada, "bases": self.bases(f"%{g2}%"),
                                 "preparacion": (self.raiz / "preparacion" / g2).exists(),
                                 "generacion": (self.raiz / "generaciones" / g2).exists()}
        limpio = all(v["rechazada"] and not v["bases"] and not v["preparacion"] and not v["generacion"]
                     for v in resultados.values())
        self.anotar("F01", "fallo inyectado en cada uno de los 9 pasos: rechazo, sin base ni carpeta parcial de G2",
                    limpio, puntos=resultados)
        self.anotar("F02", "tras los fallos, la generacion activa (G1) sigue igual y verificable",
                    (self.raiz / "activa.json").read_bytes() == activa and self.verificar_g1())
        # Proceso importador terminado con SIGKILL a mitad: quedan restos propios, nunca utilizables.
        orden = [self.python, "-B", "-m", "scripts.generaciones", "importar", "--paquete", str(paquete),
                 "--clave-publica", str(self.secretos / "firma.pub"), "--raiz", str(self.raiz),
                 "--url-admin-archivo", str(self.secretos / "url-admin"), "--url-lector-archivo",
                 str(self.secretos / "url-lector")]
        proceso = subprocess.Popen(orden, cwd=BACKEND, env=self.entorno(), stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        for _ in range(600):
            if (self.raiz / "preparacion" / g2 / "archivos").exists() or proceso.poll() is not None:
                break
            time.sleep(0.05)
        proceso.send_signal(signal.SIGKILL)
        proceso.wait()
        restos = {"bases": self.bases(f"%{g2}%"), "preparacion": (self.raiz / "preparacion" / g2).exists(),
                  "generacion": (self.raiz / "generaciones" / g2).exists()}
        from app.infrastructure.generaciones.importacion import nombre_base
        resto_prep = next((b for b in restos["bases"] if b.startswith("prep_")), nombre_base(g2, False))
        rc_api, err = self.api_privada(self.raiz / "generaciones" / g2, resto_prep, esperar_arranque=False)
        self.anotar("F03", "importador terminado con SIGKILL: sin generacion aceptada; la API no puede ligarse a los "
                    "restos", not restos["generacion"] and rc_api == 3, restos=restos)
        rc, d = self.cli("importar", "--paquete", paquete, "--clave-publica", self.secretos / "firma.pub", "--raiz",
                         self.raiz, "--url-admin-archivo", self.secretos / "url-admin", "--url-lector-archivo",
                         self.secretos / "url-lector")
        self.anotar("F04", "reimportar G2 limpia sus propios restos y la acepta; G1 sigue activa e intacta",
                    rc == 0 and (self.raiz / "activa.json").read_bytes() == activa and self.verificar_g1() and
                    not (self.raiz / "preparacion" / g2).exists() and
                    not [b for b in self.bases(f"prep_{g2}%")],
                    resultado=d.get("resultado") if isinstance(d, dict) else d,
                    restos_recuperados=d.get("restos_recuperados") if isinstance(d, dict) else None)

    def limpiar(self) -> dict:
        """Borra SOLO las bases `prep_<id>`, `pub_<id>` y `rest_<id>` de las generaciones de esta demostracion."""
        ids = {i for i in self.ids if i and i != "None"}
        borradas = []
        with self.admin() as c:
            for base in self.bases("prep_%") + self.bases("pub_%") + self.bases("rest_%"):
                prefijo, _, resto = base.partition("_")
                if resto[:32] not in ids or (len(resto) > 32 and not (prefijo == "prep" and resto[32] == "_")):
                    continue
                c.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (base,))
                c.execute(f'DROP DATABASE "{base}"')
                borradas.append(base)
        return {"bases_borradas": len(borradas), "ajenas_conservadas": "solo se borran las de esta demostracion"}


def _ajuste(nombre: str) -> str:
    from app.infrastructure.generaciones.inventario import POR_NOMBRE
    return POR_NOMBRE[nombre].ajuste


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--salida", required=True)
    for nombre in ("propietario", "captura", "admin", "lector"):
        p.add_argument(f"--url-{nombre}-archivo", required=True)
    p.add_argument("--python", default=sys.executable)
    a = p.parse_args(argv)
    salida = Path(a.salida).resolve()
    if salida.exists():
        sys.stderr.write("NEGADO: la salida debe ser una carpeta nueva\n")
        return 2
    urls = {n: Path(getattr(a, f"url_{n}_archivo")).read_text(encoding="ascii").strip()
            for n in ("propietario", "captura", "admin", "lector")}
    from sqlalchemy.engine import make_url
    if "prueba" not in (make_url(urls["propietario"]).database or "") or \
            make_url(urls["propietario"]).database != make_url(urls["captura"]).database:
        sys.stderr.write("NEGADO: la fuente debe ser una base de pruebas (nombre con 'prueba')\n")
        return 2
    salida.mkdir(parents=True)
    demo = Demo(salida, urls, a.python)
    inicio = time.monotonic()
    error = None
    try:
        demo.preparar()
        demo.g1()
        demo.api_ligada()
        demo.respaldo()
        demo.negativos()
        demo.fallos()
    except Exception as e:  # se informa como fallo de la demostracion, nunca como acierto
        error = f"{type(e).__name__}: {e}"
        demo.anotar("Z00", "la demostracion termino por una excepcion", False, error=error[:600])
    finally:
        limpieza = demo.limpiar()
        shutil.rmtree(demo.secretos, ignore_errors=True)
        shutil.rmtree(salida / "api-secretos", ignore_errors=True)
    correctas = sum(f["ok"] for f in demo.filas)
    informe = {"escenario": "e104-generaciones/1", "segundos": round(time.monotonic() - inicio, 1),
               "correctas": correctas, "total": len(demo.filas), "filas": demo.filas, "limpieza": limpieza,
               "entorno": {"plataforma": sys.platform, "python": sys.version.split()[0]},
               "no_acreditado": ["Windows (captura en el PC, R-W)", "proveedor de respaldos (D6)", "RPO/RTO (D5)",
                                 "datos reales (D10)", "activacion con drenaje (D11, E10.5)"]}
    (salida / "demostracion.json").write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"comprobaciones {correctas}/{len(demo.filas)} correctas")
    return 0 if correctas == len(demo.filas) and not error else 1


if __name__ == "__main__":
    raise SystemExit(main())
