"""Regresion de D07/R08: HTTP real, sin TestClient ni httpx."""
import builtins
import hashlib
import json
import os
import socket
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "backend"))
from scripts._http_generaciones import ClienteLocal, ConsultaLocalNoValida
from despliegue.pc_local import ensayo, preparar


def sin_cliente_de_pruebas():
    original = builtins.__import__
    def importar(nombre, *args, **kw):
        if nombre.split(".")[0] in {"httpx", "httpcore"} or nombre in {"fastapi.testclient", "starlette.testclient"}:
            raise AssertionError("la validacion no puede depender del cliente de pruebas")
        return original(nombre, *args, **kw)
    return patch("builtins.__import__", side_effect=importar)


class HTTPGeneraciones(unittest.TestCase):
    def app(self, *, estado=200, json_valido=True):
        async def responder(scope, receive, send):
            self.ultima = scope
            cuerpo = json.dumps({"ruta": scope["path"], "query": scope["query_string"].decode()}).encode() if json_valido else b"no-json"
            await send({"type":"http.response.start", "status":estado, "headers":[(b"content-type",b"application/json")]})
            await send({"type":"http.response.body", "body":cuerpo})
        return responder

    def test_http_real_autenticado_sin_httpx_y_cierre_del_socket(self):
        with sin_cliente_de_pruebas(), ClienteLocal(self.app()) as cliente:
            estado,cuerpo = cliente.get("/api/v1/estado?prueba=1", "clave-sintetica")
            self.assertEqual((estado,cuerpo), (200,{"ruta":"/api/v1/estado","query":"prueba=1"}))
            self.assertEqual(dict(self.ultima["headers"])[b"x-api-key"], b"clave-sintetica")
            self.assertEqual(self.ultima["client"][0],"127.0.0.1")
            puerto=cliente.puerto
        self.assertFalse(cliente.hilo.is_alive())
        with self.assertRaises(OSError): socket.create_connection(("127.0.0.1",puerto),0.1)

    def test_conserva_estado_http_y_rechaza_json_invalido(self):
        with ClienteLocal(self.app(estado=404,json_valido=False)) as cliente:
            self.assertEqual(cliente.get("/api/v1/inexistente","clave"),(404,None))

    def test_no_permite_urls_externas_ni_rutas_fuera_de_api(self):
        with ClienteLocal(self.app()) as cliente, patch("scripts._http_generaciones.http.client.HTTPConnection") as conexion:
            for ruta in ("https://externo.invalid/api/v1/estado", "//externo.invalid/api/v1/estado", "/otra", "/api/v1/estado\r\nX:1", None):
                with self.subTest(ruta=ruta),self.assertRaises(ConsultaLocalNoValida): cliente.get(ruta,"clave")
            conexion.assert_not_called()

    def test_cierra_el_servidor_si_el_recorrido_falla(self):
        cliente=ClienteLocal(self.app())
        with self.assertRaisesRegex(ValueError,"fallo sintetico"):
            with cliente: raise ValueError("fallo sintetico")
        self.assertFalse(cliente.hilo.is_alive())
        self.assertIsNone(cliente.socket)

    def test_fallo_de_arranque_se_cierra_sin_exportar_mensaje_libre(self):
        class ServidorFallido:
            started=False
            def __init__(self,*args,**kw): pass
            def run(self,**kw): raise RuntimeError("SECRETO-NO-EXPORTAR")
        cliente=ClienteLocal(self.app())
        with patch("uvicorn.Server",ServidorFallido),self.assertRaises(ConsultaLocalNoValida) as error:
            cliente.__enter__()
        self.assertNotIn("SECRETO",str(error.exception))
        self.assertFalse(cliente.hilo.is_alive())
        self.assertIsNone(cliente.socket)


class AuditoriaHTTP(unittest.TestCase):
    def comprobar(self, escribir):
        from scripts import generaciones as g
        from app.infrastructure.generaciones import inventario as inv
        from app.infrastructure.generaciones import consultas
        with tempfile.TemporaryDirectory(prefix="e107-http-") as t:
            r=Path(t); entorno={}
            for a in inv.ALMACENES:
                p=r/a.nombre;p.mkdir();entorno[a.ajuste.upper()]=str(p)
            publico=next(a for a in inv.PUBLICABLES if not a.publicables)
            dato=r/publico.nombre/"muestra.json";dato.write_text('{"sintetico":true}')
            async def app(scope,receive,send):
                h=dict(scope["headers"])
                esperado=os.environ["API_PUBLICA_CLAVES"].split(":")[-1]
                self.assertEqual(hashlib.sha256(h[b"x-api-key"]).hexdigest(),esperado)
                b=dato.read_bytes()
                if escribir: dato.write_bytes(b)
                await send({"type":"http.response.start","status":200,"headers":[(b"content-type",b"application/json")]})
                await send({"type":"http.response.body","body":b})
            modulo=types.ModuleType("app.api.publica.aplicacion");modulo.app=app
            def recorrer(get,esperado):
                self.assertEqual(get("/api/v1/estado"),(200,{"sintetico":True}))
                return {"fallos":[],"rutas":{},"contenido":{},"total":1}
            salida=r/"respuesta.json"
            with patch.dict(os.environ,entorno),patch.dict(sys.modules,{"app.api.publica.aplicacion":modulo}),patch.object(consultas,"recorrer",side_effect=recorrer),sin_cliente_de_pruebas():
                codigo=g._consultas(types.SimpleNamespace(esperado=None,salida=str(salida)))
            return codigo,json.loads(salida.read_text())

    def test_audita_lecturas_del_servidor_en_otro_hilo(self):
        codigo,r=self.comprobar(False)
        self.assertEqual(codigo,0)
        self.assertTrue(r["lecturas"]["por_subarbol"])
        self.assertFalse(r["lecturas"]["fuera_de_lo_declarado"])
        self.assertFalse(r["lecturas"]["escrituras"])

    def test_la_api_que_escribe_sigue_siendo_rechazada(self):
        codigo,r=self.comprobar(True)
        self.assertEqual(codigo,1)
        self.assertTrue(r["lecturas"]["escrituras"])
        self.assertTrue(r["fallos"])


class ErrorPreparacion(unittest.TestCase):
    def test_los_controles_aprobados_se_conservan_si_falla_la_activacion(self):
        with tempfile.TemporaryDirectory(prefix="e107-previo-") as t:
            e=ensayo.Ensayo(Path(t));(Path(t)/"secretos-servicio").mkdir()
            datos={"generacion":"1"*32,"restauracion":{"estado":"completa"},"comprobaciones":[{"id":"R08","ok":True}]}
            with patch.object(ensayo,"ejecutar_docker") as docker,self.assertRaises(FileExistsError):
                e.activar(datos)
            docker.assert_not_called()
            self.assertEqual(e.informe["comprobaciones"],[{"id":"R08","ok":True}])
            self.assertEqual(e.informe["codigo"],1)

    def test_no_continua_tras_d07_fallido(self):
        llamadas=[]
        class Demo:
            def __init__(self,*a): pass
            def anotar(self,ident,desc,ok,**kw): llamadas.append(ident);return ok
            def preparar(self): self.anotar("D01","fuente",True)
            def g1(self):
                self.anotar("D07","importacion",False)
                llamadas.append("NO-CONTINUAR")
            def api_ligada(self): llamadas.append("NO-API")
            def respaldo(self): llamadas.append("NO-RESPALDO")
        with tempfile.TemporaryDirectory(prefix="e107-prep-") as t:
            raiz=Path(t);fuente=raiz/"fuente";(fuente/"backend").mkdir(parents=True)
            (raiz/"urls.json").write_text('{}')
            control={"fase":"inicio","pasos":[]};actual=Path.cwd()
            try:
                with patch.object(preparar,"_modulo",return_value=types.SimpleNamespace(Demo=Demo)),patch.dict(os.environ,dict(os.environ)),self.assertRaises(preparar.PasoNoSuperado) as error:
                    preparar.ejecutar("generar",raiz,fuente,control=control)
            finally: os.chdir(actual)
        self.assertEqual(error.exception.paso,"D07")
        self.assertEqual(llamadas,["D01","D07"])
        self.assertEqual(control["fase"],"captura_importacion")

    def test_el_fallo_auxiliar_conserva_solo_campos_cerrados(self):
        with tempfile.TemporaryDirectory(prefix="e107-reporte-") as t:
            e=ensayo.Ensayo(Path(t));e.imagenes["preparacion"]="sha256:"+"a"*64
            mensaje={"codigo":1,"fase_preparacion":"captura_importacion","paso_fallido":"D07","tipo_error":"PasoNoSuperado","comprobaciones":[{"id":"D07","ok":False}],"motivo":"SECRETO-NO-EXPORTAR"}
            def docker(args,**kw):
                if args[0]=="create": return b"a"*64
                self.assertTrue(kw["permitir_error"])
                return b"E107_PREPARACION:"+json.dumps(mensaje).encode()+b"\n"
            with patch.object(ensayo,"ejecutar_docker",side_effect=docker),self.assertRaises(ensayo.Detenido): e.auxiliar("generar")
            self.assertEqual(e.informe["fallo_auxiliar"]["paso_fallido"],"D07")
            self.assertEqual(e.informe["comprobaciones"],[{"id":"D07","ok":False}])
            self.assertNotIn("SECRETO",json.dumps(e.informe))


if __name__=="__main__": unittest.main()
