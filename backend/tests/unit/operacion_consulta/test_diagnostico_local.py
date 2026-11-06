"""Diagnostico E107 de lectura: alcance, comandos y salida sin texto libre."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

if (Path(__file__).resolve().parent / "diagnosticar.py").is_file():
    import diagnosticar as d
else:
    RAIZ = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(RAIZ))
    from despliegue.pc_local import diagnosticar as d

ENSAYO = Path("/tmp/e107pc-prueba123")
RUN = "1" * 32


def contenedor(cid="a" * 64, modo="generar", raiz=ENSAYO):
    return {"Id": cid, "Name": "/e107" + RUN + "-preparacion-3", "Image": next(i for i in d.IMAGENES if i.startswith("sha256:3f")),
        "Labels": {d.ETIQUETA: RUN}, "User": "1000:1000",
        "Cmd": ["-B", str(raiz / "fuente/despliegue/pc_local/preparar.py"), modo, str(raiz), str(raiz / "fuente")],
        "State": {"Running": False, "ExitCode": 1, "OOMKilled": False, "Error": ""},
        "Mounts": [{"Type": "bind", "Source": str(raiz), "Destination": str(raiz), "RW": True},
                   {"Type": "bind", "Source": str(raiz / "fuente"), "Destination": str(raiz / "fuente"), "RW": False}]}


class DiagnosticoLectura(unittest.TestCase):
    def ejecutar(self, objetos, logs=b""):
        llamadas = []
        def consultar(args):
            llamadas.append(args)
            if args[0] == "ps": return "\n".join(o["Id"][:12] for o in objetos).encode()
            if args[0] == "inspect": return b"\n".join(json.dumps(o).encode() for o in objetos)
            if args[0] == "logs": return logs
            raise AssertionError("comando inesperado")
        with patch.object(d, "metadatos", return_value={}):
            return d.diagnosticar(str(ENSAYO), consultar=consultar), llamadas

    def test_lectura_identifica_el_paso_sin_exportar_secretos(self):
        secreto = "postgresql://cuenta:SECRETO-NO-EXPORTAR@127.0.0.1/base"
        logs = (json.dumps({"id": "D01", "ok": False,
            "detalle": "ModuleNotFoundError: No module named 'httpx'; " + secreto}) +
            '\nE107_PREPARACION:{"codigo":1,"resultado":"preparacion_sintetica_rechazada"}').encode()
        r, cmds = self.ejecutar([contenedor()], logs)
        self.assertNotIn(secreto, json.dumps(r))
        self.assertNotIn("SECRETO-NO-EXPORTAR", json.dumps(r))
        c, = r["contenedores"]
        self.assertEqual(c["resumen_logs"]["pasos"], [{"id": "D01", "ok": False}])
        self.assertEqual(c["resumen_logs"]["modulos_ausentes"], ["httpx"])
        self.assertEqual(c["resumen_logs"]["tipos_de_error"], ["ModuleNotFoundError"])
        self.assertEqual([a[0] for a in cmds], ["ps", "inspect", "logs"])

    def test_no_consulta_logs_de_otro_ensayo(self):
        ajeno = contenedor("b" * 64, raiz=Path("/tmp/e107pc-otro1234"))
        r, cmds = self.ejecutar([contenedor(), ajeno])
        self.assertEqual(len(r["contenedores"]), 1)
        self.assertEqual([a[-1] for a in cmds if a[0] == "logs"], ["a" * 64])

    def test_rechaza_imagen_y_etiqueta_no_propias(self):
        for campo, valor in (("Image", "sha256:" + "f" * 64), ("Labels", {d.ETIQUETA: "ajeno"})):
            c = contenedor(); c[campo] = valor
            with self.subTest(campo=campo):
                r, cmds = self.ejecutar([c])
                self.assertEqual(r["codigo"], 1)
                self.assertFalse(any(a[0] == "logs" for a in cmds))

    def test_oom_y_error_runtime_son_campos_cerrados(self):
        c = contenedor(); c["State"].update(ExitCode=137, OOMKilled=True, Error="SECRETO-ERROR")
        r, _ = self.ejecutar([c])
        self.assertTrue(r["contenedores"][0]["terminado_por_memoria"])
        self.assertTrue(r["contenedores"][0]["error_runtime_presente"])
        self.assertNotIn("SECRETO-ERROR", json.dumps(r))

    def test_directorios_ajenos_se_rechazan_antes_de_docker(self):
        for ruta in ("/", "/tmp/../etc", "/tmp/e107pc-a/../b", "/home/usuario", "/tmp/e107pc-prueba123/"):
            with self.subTest(ruta=ruta):
                with self.assertRaises(d.Rechazo):
                    d.diagnosticar(ruta, consultar=lambda *_: self.fail("no debe consultar"))

    def test_comandos_mutables_se_rechazan_antes_de_crear_procesos(self):
        with patch.object(d.subprocess, "Popen") as proceso:
            for orden in ("start", "stop", "exec", "run", "create", "rm", "prune", "compose"):
                with self.subTest(orden=orden), self.assertRaises(d.Rechazo):
                    d.ejecutar([orden])
            proceso.assert_not_called()

    def test_ids_de_inspeccion_no_se_pueden_sustituir(self):
        c = contenedor()
        def consultar(args):
            if args[0] == "ps": return b"b" * 12
            if args[0] == "inspect": return json.dumps(c).encode()
            self.fail("no debe leer logs de un ID distinto")
        with self.assertRaises(d.Rechazo):
            d.diagnosticar(str(ENSAYO), consultar=consultar)

    def test_logs_truncados_tambien_conservan_solo_el_resultado_del_paso(self):
        r = d.resumir_logs(b'{"id": "D01", "ok": false, "detalle":"Permission denied: NO-COPIAR')
        self.assertEqual(r["pasos"], [{"id": "D01", "ok": False}])
        self.assertEqual(r["indicios"], ["permiso_denegado"])
        self.assertNotIn("NO-COPIAR", json.dumps(r))

    def test_montajes_traducidos_por_desktop_conservan_el_alcance(self):
        c = contenedor()
        for i,m in enumerate(c["Mounts"]): m["Source"] = "/run/desktop/mnt/host/wsl/origen-" + str(i)
        r, _ = self.ejecutar([c])
        self.assertEqual(len(r["contenedores"]), 1)
        self.assertTrue(r["contenedores"][0]["origenes_de_montaje_traducidos"])

    def test_traza_solo_exporta_archivo_relativo_y_linea(self):
        log = json.dumps({"id":"D01","ok":False,"detalle":'File "/tmp/e107pc-prueba123/fuente/backend/tests/e102_preparar_publicacion.py", line 120\nValueError: SECRETO'}).encode()
        r = d.resumir_logs(log)
        self.assertEqual(r["puntos_de_codigo"], [{"archivo_relativo":"backend/tests/e102_preparar_publicacion.py","linea":120}])
        self.assertNotIn("SECRETO",json.dumps(r))


if __name__ == "__main__": unittest.main()
