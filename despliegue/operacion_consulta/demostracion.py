"""Demostración local: HTTP real, datos sintéticos y procesos de servicio sustituidos.

No ejecuta Docker, nginx, PostgreSQL ni un despliegue. Todo vive en un temporal
propio y en puertos loopback asignados por el sistema, sin PKI ni cuentas reales.
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .auditoria import informe
from .ciclo import Motor
from .estado import Almacen
from .exportador import crear_servidor
from .modelo import Plan, canonico
from .observabilidad import JUEGOS, muestra, registrar, senales_iniciales


def exigir(condicion, caso):
    if not condicion:
        raise AssertionError(caso)


class Interrupcion(BaseException):
    pass


class ServicioSintetico:
    def __init__(self, raiz):
        self.raiz = raiz
        self.cv = threading.Condition()
        self.parejas, self.bases = {}, {}
        self.proxy, self.cerrado, self.lectores, self.solicitudes = None, True, 0, 0
        self.fallar, self.interrumpir = None, None
        self.lector_dentro, self.liberar_lector, self.mantenimiento_iniciado = (threading.Event() for _ in range(3))
        self.drenaje_iniciado = threading.Event()
        propio = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                with propio.cv:
                    propio.solicitudes += 1
                    p = propio.proxy
                    admitido = not propio.cerrado and p is not None
                    if admitido:
                        propio.lectores += 1
                if not admitido:
                    self.send_response(503)
                    self.send_header("Retry-After", "1")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                try:
                    if self.path == "/lenta":
                        propio.lector_dentro.set()
                        exigir(propio.liberar_lector.wait(5), "lector_lento_con_plazo")
                    # Las dos fuentes pertenecen al par capturado al admitir la solicitud.
                    with propio.cv:
                        b = canonico({"base": propio.bases[p.id], "archivos":
                                      (propio.raiz / p.generacion).read_text().strip()})
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                finally:
                    with propio.cv:
                        propio.lectores -= 1
                        propio.cv.notify_all()

            def log_message(self, *args):
                pass

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.hilo = threading.Thread(target=self.servidor.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.hilo.start()

    def close(self):
        self.liberar_lector.set()
        self.servidor.shutdown()
        self.servidor.server_close()
        self.hilo.join(2)

    def _despues(self, fase, p):
        if self.fallar == (fase, p.id):
            self.fallar = None
            raise RuntimeError("fallo sintético")
        if self.interrumpir == (fase, p.id):
            self.interrumpir = None
            raise Interrupcion()

    def preparar(self, p, plazo):
        f = self.raiz / p.generacion
        if not f.exists():
            f.write_text(p.generacion + "\n")
        exigir(f.read_text().strip() == p.generacion, "archivos_inmutables")
        self.bases.setdefault(p.id, p.generacion)
        self._despues("preparar", p)

    def arrancar(self, p, plazo):
        self.parejas[p.id] = p
        self._despues("arrancar", p)

    def validar(self, p, plazo):
        exigir(p.id in self.parejas and self.bases[p.id] == p.generacion, "vinculo_del_par")
        self._despues("validar", p)

    def mantenimiento(self, p, cerrar, plazo):
        with self.cv:
            if self.proxy and self.proxy.id == p.id:
                self.cerrado = cerrar
                if cerrar:
                    self.mantenimiento_iniciado.set()
            elif not cerrar:
                raise RuntimeError("proxy ausente")
        self._despues("cerrar" if cerrar else "abrir", p)

    def drenar(self, p, plazo):
        with self.cv:
            if not self.proxy or self.proxy.id != p.id:
                return
            exigir(self.cerrado, "entrada_cerrada_antes_del_drenaje")
            self.drenaje_iniciado.set()
            while self.lectores:
                restante = plazo - time.monotonic()
                exigir(restante > 0, "drenaje_con_plazo")
                self.cv.wait(min(restante, 0.1))
        self._despues("drenar", p)

    def detener(self, p, plazo):
        with self.cv:
            if self.proxy and self.proxy.id == p.id:
                exigir(self.lectores == 0, "no_parar_con_lectores")
                self.proxy, self.cerrado = None, True
            self.parejas.pop(p.id, None)
        self._despues("detener", p)

    def publicar(self, p, plazo):
        with self.cv:
            exigir(self.proxy is None or self.proxy.id == p.id, "un_solo_ingreso")
            self.proxy, self.cerrado = p, True
        self._despues("publicar", p)

    def sonda(self, p, plazo):
        r = self.leer()
        exigir(r == {"base": p.generacion, "archivos": p.generacion}, "sonda_coherente")
        self._despues("sonda", p)

    def leer(self, ruta="/"):
        url = "http://127.0.0.1:" + str(self.servidor.server_port) + ruta
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=5) as r:
            return json.load(r)


def plan_sintetico(raiz: Path, n: int) -> Plan:
    gid = f"{n:032x}"
    return Plan.de({"formato": "operacion-consulta/1", "modo": "ensayo", "generacion": gid,
                    "manifiesto_sha256": "a" * 64, "huella_app": "b" * 64,
                    "imagen_api": "sintetico/api@sha256:" + "c" * 64,
                    "imagen_pasarela": "sintetico/pasarela@sha256:" + "d" * 64,
                    "imagen_proxy": "sintetico/proxy@sha256:" + "e" * 64,
                    "host": "consulta.ensayo.invalid", "puerto": 18443,
                    "red_interna": f"172.28.{n * 2}.0/24", "red_servicio": f"172.28.{n * 2 + 1}.0/24",
                    "red_datos": "e105ensayodatosdemostracion", "ip_datos_api": f"172.29.0.{20 + n}",
                    "directorio_generacion": str(raiz / gid), "clave_publica": str(raiz / "no-usada.pub"),
                    "secretos": str(raiz / "no-usados"), "pki_proxy": str(raiz / "no-usada-pki"),
                    "pki_sonda": str(raiz / "no-usada-sonda")})


def ejecutar() -> dict:
    casos = []
    with tempfile.TemporaryDirectory(prefix="e105-e106-demo-") as temporal:
        raiz = Path(temporal)
        with Almacen(raiz / "control", crear=True) as a:
            servicio = ServicioSintetico(raiz)
            trabajadores = []
            try:
                motor = Motor(a, lambda _: servicio)
                p, q, r = (plan_sintetico(raiz, n) for n in (1, 2, 3))
                exigir(motor.activar(p)["codigo"] == 0, "primera_activacion")
                casos.append("activacion_inicial")
                resultados = {}
                errores = []

                def trabajo(nombre, funcion):
                    try:
                        resultados[nombre] = funcion()
                    except BaseException as error:
                        errores.append(type(error).__name__)

                lenta = threading.Thread(target=trabajo, args=("lectura", lambda: servicio.leer("/lenta")), daemon=True)
                trabajadores.append(lenta)
                lenta.start()
                exigir(servicio.lector_dentro.wait(2), "solicitud_abierta")
                cambio = threading.Thread(target=trabajo, args=("cambio", lambda: motor.activar(q)), daemon=True)
                trabajadores.append(cambio)
                cambio.start()
                exigir(servicio.mantenimiento_iniciado.wait(2), "mantenimiento_iniciado")
                exigir(servicio.drenaje_iniciado.wait(2), "controlador_espera_drenaje")
                with servicio.cv:
                    exigir(servicio.lectores == 1 and servicio.proxy.id == p.id
                           and cambio.is_alive() and "cambio" not in resultados, "cambio_bloqueado_por_lector")
                try:
                    servicio.leer()
                except urllib.error.HTTPError as error:
                    exigir(error.code == 503 and error.headers["Retry-After"] == "1", "mantenimiento_503")
                else:
                    exigir(False, "mantenimiento_503")
                casos.append("nuevas_solicitudes_503_con_retry_after")
                servicio.liberar_lector.set()
                lenta.join(5)
                cambio.join(5)
                exigir(not lenta.is_alive() and not cambio.is_alive() and not errores, "hilos_finalizados")
                exigir(resultados["lectura"] == {"base": p.generacion, "archivos": p.generacion}, "lector_solo_G")
                exigir(resultados["cambio"]["codigo"] == 0 and servicio.leer() == {
                    "base": q.generacion, "archivos": q.generacion}, "nuevo_lector_solo_G_mas_1")
                casos.append("lector_abierto_conserva_generacion_y_nuevo_lector_cambia_completo")
                servicio.fallar = ("sonda", r.id)
                exigir(motor.activar(r)["codigo"] == 1 and servicio.leer()["base"] == q.generacion, "reversion")
                casos.append("fallo_de_sonda_revierte")
                servicio.interrumpir = ("publicar", r.id)
                try:
                    motor.activar(r)
                except Interrupcion:
                    pass
                exigir(a.leer("estado.json")["pendiente"] is not None, "diario_conservado")
                exigir(Motor(a, lambda _: servicio).recuperar()["codigo"] == 0, "recuperacion")
                exigir(servicio.leer()["base"] == q.generacion, "recupera_anterior")
                casos.append("interrupcion_modelada_y_recuperacion_persistida")
                exigir(all((raiz / x.generacion).read_text().strip() == x.generacion for x in (p, q, r)), "retencion")
                casos.append("generaciones_y_bases_sinteticas_conservadas")
                ahora = datetime.now(timezone.utc)
                senales = registrar(senales_iniciales(), "contacto_pc", ahora.isoformat(), ahora=ahora)
                m = {"id": q.generacion, "creada_en": ahora.isoformat(), "juegos": {
                    j: {"ultima_fecha": ahora.date().isoformat()} for j in JUEGOS}}
                api = {"base": "disponible", "solicitudes": servicio.solicitudes, "por_clase": {},
                       "segundos_activo": 1, "rutas": []}
                v = muestra(a.leer("estado.json"), m, api, senales, ahora)
                with a.exclusivo():
                    a.escribir("observacion.json", v)
                reloj = [ahora]
                exporter = crear_servidor(a, 0, ahora=lambda: reloj[0])
                hilo = threading.Thread(target=exporter.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
                hilo.start()
                try:
                    url = "http://127.0.0.1:" + str(exporter.server_port) + "/metricas"
                    abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
                    with abrir(url, timeout=2) as respuesta:
                        exigir(b"loteria_consulta_verificada 1" in respuesta.read(), "muestra_fresca")
                    reloj[0] += timedelta(seconds=121)
                    with abrir(url, timeout=2) as respuesta:
                        b = respuesta.read()
                        exigir(b"loteria_consulta_verificada 0" in b and b"observacion_obsoleta" in b, "muestra_vencida")
                finally:
                    exporter.shutdown()
                    exporter.server_close()
                    hilo.join(2)
                casos.append("exportador_http_distingue_muestra_fresca_y_vencida")
                exigir(informe(a.leer("estado.json"), v, ahora)["produccion_autorizada"] is False, "auditoria_abierta")
                casos.append("ensayo_no_cierra_autorizacion_de_produccion")
            finally:
                servicio.liberar_lector.set()
                for trabajador in trabajadores:
                    trabajador.join(5)
                servicio.close()
    return {"formato": "demostracion-e105-e106/1", "codigo": 0, "casos": casos, "aprobados": len(casos),
            "transporte": "HTTP_loopback_real", "servicios": "sustitutos_sinteticos",
            "docker_postgresql_nginx": "no_ejecutados"}


if __name__ == "__main__":
    try:
        resultado = ejecutar()
    except BaseException:
        resultado = {"codigo": 1, "resultado": "demostracion_fallida"}
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
    raise SystemExit(resultado["codigo"])
