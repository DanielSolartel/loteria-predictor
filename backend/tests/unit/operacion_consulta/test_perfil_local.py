"""E10.7: pruebas ejecutables con unittest, sin Docker ni instalaciones.

TLS es real sobre loopback; las pruebas de estructura/comandos no se presentan
como una ejecucion nativa de Docker, PostgreSQL, nginx ni PowerShell.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import http.server
import io
import json
import os
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "backend"))

from despliegue.operacion_consulta.docker import Docker
from despliegue.operacion_consulta.estado import Almacen
from despliegue.operacion_consulta.infraestructura import componer, nginx
from despliegue.operacion_consulta.local import ARCHIVO, PlanLocal, autorizar, comprobar
from despliegue.operacion_consulta.modelo import Plan, Rechazo
from despliegue.pc_local import ensayo, preparar


def datos(raiz: Path, *, local=True):
    d = {"formato": "operacion-consulta-local/1" if local else "operacion-consulta/1",
         "modo": "ensayo", "generacion": "1" * 32, "manifiesto_sha256": "a" * 64,
         "huella_app": "b" * 64, "host": "localhost" if local else "consulta.ensayo.invalid", "puerto": 18443,
         "red_interna": "172.28.2.0/24", "red_servicio": "172.28.3.0/24",
         "red_datos": "e105ensayodatos12345678", "ip_datos_api": "172.29.0.21",
         "directorio_generacion": str(raiz / ("1" * 32)), "clave_publica": str(raiz / "firma.pub"),
         "secretos": str(raiz / "secretos"), "pki_proxy": str(raiz / "pki-proxy"), "pki_sonda": str(raiz / "pki")}
    for n, c in (("api", "c"), ("pasarela", "d"), ("proxy", "e")):
        d["imagen_" + n] = ("" if local else "prueba/" + n + "@") + "sha256:" + c * 64
    return d


class PerfilLocal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="e107-test-")
        self.raiz = Path(self.tmp.name)
        self.a = Almacen(self.raiz / "control", crear=True)

    def tearDown(self):
        self.a.close()
        self.tmp.cleanup()

    def permiso(self):
        with self.a.exclusivo():
            return autorizar(self.a, datos(self.raiz), confirmar=True)

    def test_serializacion_anterior_sin_campos_locales(self):
        d = datos(Path("/tmp/e107legacy"), local=False)
        p = Plan.de(d)
        self.assertIs(type(p), Plan)
        self.assertEqual(p.objeto(), dict(d, drenaje_s=30, presupuesto_corte_s=120))
        self.assertNotIn("permiso_local", p.objeto())

    def test_perfil_local_se_persiste_y_se_recupera(self):
        p = self.permiso()
        with self.a.exclusivo():
            self.a.inicializar()
            self.a.guardar_plan(p)
        q = self.a.plan(p.id)
        self.assertIs(type(q), PlanLocal)
        self.assertEqual(q, p)
        comprobar(self.a, q)

    def test_autorizacion_explicita_y_bloqueo_obligatorios(self):
        for flag in (False, 1, "si", None):
            with self.subTest(flag=flag), self.a.exclusivo():
                with self.assertRaises(Rechazo):
                    autorizar(self.a, datos(self.raiz), confirmar=flag)
        with self.assertRaises(Rechazo):
            autorizar(self.a, datos(self.raiz), confirmar=True)
        self.assertIsNone(self.a.leer(ARCHIVO))

    def test_control_anterior_no_hereda_permiso(self):
        with self.a.exclusivo():
            self.a.inicializar()
            with self.assertRaises(Rechazo):
                autorizar(self.a, datos(self.raiz), confirmar=True)

    def test_permiso_no_se_sobrescribe(self):
        self.permiso()
        with self.a.exclusivo(), self.assertRaises(Rechazo):
            autorizar(self.a, datos(self.raiz), confirmar=True)

    def test_plan_local_rechaza_exposicion_y_modos_no_locales(self):
        for campo, valor in (("host", "0.0.0.0"), ("host", "127.0.0.1"), ("host", "consulta.privada"),
                             ("host", "::1"), ("modo", "produccion"), ("permiso_local", None),
                             ("imagen_api", "prueba/api:latest"), ("imagen_api", "sha256:" + "A" * 64),
                             ("imagen_api", "prueba/api@sha256:" + "c" * 64), ("puerto", True),
                             ("red_servicio", "172.28.2.0/24"), ("ip_datos_api", "127.0.0.1")):
            with self.subTest(campo=campo, valor=valor), self.assertRaises(Rechazo):
                d = dict(datos(self.raiz), permiso_local="0" * 64)
                d[campo] = valor
                Plan.de(d)

    def test_formato_anterior_no_admite_imagenes_locales(self):
        with self.assertRaises(Rechazo):
            Plan.de(dict(datos(self.raiz), formato="operacion-consulta/1"))

    def test_sin_permiso_no_se_escribe_ni_consulta_docker(self):
        p = Plan.de(dict(datos(self.raiz), permiso_local="0" * 64))
        llamadas = []
        op = Docker(self.a, "1" * 32, ejecutar=lambda *args: llamadas.append(args))
        for metodo, args in ((op.materializar, (p,)), (op.contenedores, (p, time.monotonic() + 2)),
                             (op.preparar, (p, time.monotonic() + 2)), (op.detener, (p, time.monotonic() + 2))):
            with self.subTest(metodo=metodo.__name__), self.assertRaises(Rechazo):
                metodo(*args)
        self.assertFalse(llamadas)
        self.assertEqual(list(self.a.ruta.iterdir()), [])

    def test_alterar_cualquier_referencia_invalida_el_permiso(self):
        p = self.permiso()
        for campo, valor in (("puerto", 19443), ("imagen_api", "sha256:" + "f" * 64),
                             ("secretos", str(self.raiz / "otros")), ("generacion", "2" * 32),
                             ("manifiesto_sha256", "f" * 64)):
            d = dict(p.objeto(), **{campo: valor})
            if campo == "generacion":
                d["directorio_generacion"] = str(self.raiz / valor)
            with self.subTest(campo=campo), self.assertRaises(Rechazo):
                comprobar(self.a, Plan.de(d))

    def test_registro_ci_no_es_permiso_local(self):
        p = self.permiso()
        with self.a.exclusivo():
            self.a.escribir(ARCHIVO, {"aceptacion": "B", "produccion_autorizada": False})
        with self.assertRaises(Rechazo):
            comprobar(self.a, p)

    def test_archivo_de_permiso_no_puede_ser_enlace(self):
        p = self.permiso()
        original = self.a.ruta / ARCHIVO
        otro = self.raiz / "otro.json"
        original.rename(otro)
        original.symlink_to(otro)
        with self.assertRaises(OSError):
            comprobar(self.a, p)

    def test_compose_local_solo_expone_proxy_en_loopback(self):
        p = self.permiso()
        d = componer(p, "1" * 32, str(self.raiz / "release"))
        for n in ("api", "pasarela"):
            self.assertNotIn("ports", d["services"][n])
        self.assertEqual(d["services"]["proxy"]["ports"], [{"target": 18443, "published": "18443",
                         "host_ip": "127.0.0.1", "protocol": "tcp"}])
        for s in d["services"].values():
            self.assertEqual(s["pull_policy"], "never")
            self.assertEqual(s["restart"], "no")
            self.assertTrue(s["read_only"])
            self.assertTrue(all(v["read_only"] for v in s["volumes"]))
            self.assertNotIn("build", s)

    def test_nginx_conserva_mtls_y_host_local_exacto(self):
        config = nginx(self.permiso())
        self.assertIn('"localhost:18443" 1', config)
        self.assertIn("ssl_verify_client on;", config)
        self.assertIn("ssl_crl /etc/nginx/tls/crl.pem;", config)
        self.assertIn("server_name localhost;", config)

    def test_materializar_anterior_sigue_sin_exigir_permiso_nuevo(self):
        p = Plan.de(datos(self.raiz, local=False))
        op = Docker(self.a, "1" * 32)
        op.materializar(p)
        self.assertTrue((op.carpeta(p) / "compose.json").is_file())


class ArchivosYProtocolo(unittest.TestCase):
    @staticmethod
    def zip_de(entradas):
        salida = io.BytesIO()
        with zipfile.ZipFile(salida, "w") as z:
            for ruta, contenido in entradas:
                z.writestr(ruta, contenido)
        return salida.getvalue()

    def test_zip_rechaza_escape_rutas_y_fuera_de_alcance_antes_de_escribir(self):
        for ruta in ("../escapar.py", "/backend/afuera.py", "backend/../../afuera", "backend\\afuera.py",
                     "otro/archivo.py", "backend/./archivo.py", "backend//archivo.py", "backend/a:archivo"):
            with self.subTest(ruta=ruta), tempfile.TemporaryDirectory() as t:
                raiz = Path(t)
                with self.assertRaises(ensayo.Detenido):
                    ensayo.extraer(self.zip_de([("backend/primero.py", b"ok"), (ruta, b"mal")]), raiz)
                self.assertEqual(list(raiz.iterdir()), [])

    def test_overlay_no_puede_cambiar_la_huella_de_app(self):
        with tempfile.TemporaryDirectory() as t, self.assertRaises(ensayo.Detenido):
            ensayo.extraer(self.zip_de([("backend/app/codigo.py", b"cambio")]), Path(t), cambios=True)

    def test_fuentes_erroneas_se_rechazan_antes_de_efectos(self):
        with patch.object(ensayo, "ejecutar_docker") as docker, patch.object(ensayo.tempfile, "mkdtemp") as crear:
            with self.assertRaisesRegex(ensayo.Detenido, "fuentes_no_corresponden"):
                ensayo.realizar(b"archivo ajeno", b"", confirmar=True)
            docker.assert_not_called()
            crear.assert_not_called()

    def test_fuentes_se_extraen_sin_git_y_conservan_bytes_originales(self):
        xml = '\ufeff<?xml version="1.0" encoding="UTF-16"?>\r\n'.encode('utf-16-le')
        b = self.zip_de([("backend/tests/fixture.xml", xml), ("backend/app/__init__.py", b"")])
        with patch.object(ensayo, "SHA256_FUENTE_BASE", hashlib.sha256(b).hexdigest()):
            ensayo.verificar_fuentes(b)
            with tempfile.TemporaryDirectory() as t:
                destino = Path(t) / "carpeta sin Git con espacios"
                ensayo.extraer(b, destino)
                self.assertEqual((destino / "backend/tests/fixture.xml").read_bytes(), xml)

    def test_un_byte_cambiado_invalida_las_fuentes_completas(self):
        b = self.zip_de([("backend/app/__init__.py", b"")])
        with patch.object(ensayo, "SHA256_FUENTE_BASE", hashlib.sha256(b).hexdigest()):
            ensayo.verificar_fuentes(b)
            cambiado = bytearray(b)
            cambiado[-1] ^= 1
            with self.assertRaises(ensayo.Detenido):
                ensayo.verificar_fuentes(bytes(cambiado))

    def test_zip_rechaza_enlaces_y_duplicados(self):
        with tempfile.TemporaryDirectory() as t:
            b = io.BytesIO()
            with zipfile.ZipFile(b, "w") as z:
                info = zipfile.ZipInfo("backend/enlace")
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(info, "/etc/passwd")
            with self.assertRaises(ensayo.Detenido):
                ensayo.extraer(b.getvalue(), Path(t))
        import warnings
        with warnings.catch_warnings(), tempfile.TemporaryDirectory() as t:
            warnings.simplefilter("ignore", UserWarning)
            b = self.zip_de([("backend/a", b"1"), ("backend/a", b"2")])
            with self.assertRaises(ensayo.Detenido):
                ensayo.extraer(b, Path(t))

    def test_elegir_redes_evade_las_redes_existentes(self):
        with patch.object(ensayo.secrets, "randbelow", side_effect=[0, 1]):
            redes = ensayo.elegir_redes(["10.120.0.0/16", "172.16.0.0/12", "fd00::/8"])
        self.assertEqual(redes, ("10.121.11.0/24", "10.121.12.0/24", "10.121.13.0/24"))

    def test_sin_autorizacion_no_hay_efectos(self):
        with patch.object(ensayo, "ejecutar_docker") as docker, patch.object(ensayo.tempfile, "mkdtemp") as crear:
            with self.assertRaises(ensayo.Detenido):
                ensayo.realizar(b"", b"", confirmar=False)
            docker.assert_not_called()
            crear.assert_not_called()

    def test_zip_evidencia_solo_incluye_json_y_su_huella(self):
        r = {"codigo": 0, "produccion_autorizada": False}
        with zipfile.ZipFile(io.BytesIO(ensayo.paquete_evidencia(r))) as z:
            self.assertEqual(z.namelist(), ["resultado.json", "SHA256SUMS"])
            b = z.read("resultado.json")
            self.assertEqual(json.loads(b), r)
            self.assertEqual(z.read("SHA256SUMS").decode(), hashlib.sha256(b).hexdigest() + "  resultado.json\n")

    def test_protocolo_stdin_real_no_falla_por_future_import(self):
        codigo = (RAIZ / "despliegue/pc_local/ensayo.py").read_bytes()
        lanzador = ("import base64\nexec(compile(base64.b64decode(" + repr(base64.b64encode(codigo).decode()) +
            "), '<e107>', 'exec'), {'__name__': '__main__', 'FUENTE_BASE64': '!', 'CAMBIOS_BASE64': ''})\n")
        r = subprocess.run([sys.executable, "-I", "-B", "-", "--autorizar-ensayo-sintetico"],
            input=lanzador.encode(), capture_output=True, timeout=5)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr, b"")
        linea, = r.stdout.splitlines()
        self.assertTrue(linea.startswith(b"E107_RESULTADO_JSON:"))
        d = json.loads(linea.split(b":", 1)[1])
        b = base64.b64decode(d["evidencia_base64"])
        self.assertEqual(hashlib.sha256(b).hexdigest(), d["evidencia_sha256"])
        self.assertFalse(d["resumen"]["produccion_autorizada"])

    def test_detencion_auxiliar_rechaza_todo_el_conjunto_si_hay_ajeno(self):
        with tempfile.TemporaryDirectory() as t:
            e = ensayo.Ensayo(Path(t))
            e.imagenes = {"api": "sha256:" + "a" * 64}
            d = {"Config": {"Labels": {ensayo.ETIQUETA: "ajeno"}}, "Name": "/e107-ajeno", "Image": e.imagenes["api"]}
            with patch.object(ensayo, "ejecutar_docker", return_value=b"a" * 64) as cmd, \
                    patch.object(ensayo, "json_docker", return_value=[d]):
                self.assertFalse(e.detener())
                self.assertEqual(cmd.call_count, 1)
                self.assertEqual(cmd.call_args.args[0][:2], ["ps", "-aq"])


class TLSLocalReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="e107-tls-")
        cls.raiz = Path(cls.tmp.name)
        cls.pki = cls.raiz / "pki"
        preparar.crear_pki(cls.pki)
        shutil.copyfile(cls.pki / "ca.crt", cls.pki / "ca-servidor.crt")
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"base":"disponible"}')
            def log_message(self, *args):
                pass
        cls.servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        c = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        c.load_cert_chain(str(cls.pki / "servidor.crt"), str(cls.pki / "servidor.key"))
        c.load_verify_locations(cafile=str(cls.pki / "ca.crt"))
        c.verify_mode = ssl.CERT_REQUIRED
        cls.servidor.socket = c.wrap_socket(cls.servidor.socket, server_side=True)
        cls.hilo = threading.Thread(target=cls.servidor.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        cls.hilo.start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        cls.hilo.join(3)
        cls.tmp.cleanup()

    def plan(self):
        return Plan.de(dict(datos(self.raiz), permiso_local="0" * 64, puerto=self.servidor.server_port))

    def test_sonda_mtls_real_con_ca_y_cliente_validos(self):
        self.assertEqual(Docker(None, "1" * 32)._tls(self.plan(), time.monotonic() + 5), {"base": "disponible"})

    def test_pki_admite_la_verificacion_x509_estricta(self):
        original = ssl.create_default_context
        def estricto(*args, **kw):
            c = original(*args, **kw)
            c.verify_flags |= ssl.VERIFY_X509_STRICT
            return c
        with patch("despliegue.operacion_consulta.docker.ssl.create_default_context", side_effect=estricto):
            self.assertEqual(Docker(None, "1" * 32)._tls(self.plan(), time.monotonic() + 5), {"base": "disponible"})

    def test_sonda_tls_rechaza_nombre_del_servidor_incorrecto(self):
        p = replace(self.plan(), host="ajeno.invalid")
        with self.assertRaises(ssl.SSLCertVerificationError):
            Docker(None, "1" * 32)._tls(p, time.monotonic() + 5)

    def test_tls_real_rechaza_cliente_sin_certificado(self):
        c = http.client.HTTPSConnection("localhost", self.servidor.server_port,
            context=ssl.create_default_context(cafile=str(self.pki / "ca.crt")), timeout=3)
        c._create_connection = lambda *a, **kw: socket.create_connection(("127.0.0.1", self.servidor.server_port), 3)
        try:
            with self.assertRaises((ssl.SSLError, ConnectionError, http.client.RemoteDisconnected)):
                c.request("GET", "/api/v1/estado")
                c.getresponse()
        finally:
            c.close()

    def test_certificados_locales_no_se_instalan_y_claves_son_privadas(self):
        self.assertEqual(stat.S_IMODE((self.pki / "cliente.key").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.pki / "servidor.key").stat().st_mode), 0o600)
        self.assertFalse((self.pki / "ca.key").exists())


if __name__ == "__main__":
    unittest.main()
