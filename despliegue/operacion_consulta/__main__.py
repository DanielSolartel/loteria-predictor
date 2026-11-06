"""CLI local. Ejecutar desde la raíz con PYTHONPATH=backend, sin instalar paquetes."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import auditoria, observabilidad as ob
from .ciclo import Motor
from .docker import Docker
from .estado import Almacen
from .exportador import crear_servidor
from .modelo import Rechazo, json_estricto, leer_plan


def parser():
    p = argparse.ArgumentParser(description="E10.5/E10.6: operación de ensayo de la consulta privada")
    p.add_argument("--control", required=True, type=Path, help="carpeta privada nueva o ya inicializada")
    s = p.add_subparsers(dest="orden", required=True)
    s.add_parser("inicializar")
    for nombre in ("renderizar", "activar"):
        q = s.add_parser(nombre)
        q.add_argument("--plan", type=Path, required=True)
        if nombre == "activar":
            q.add_argument("--confirmar-ensayo", action="store_true", required=True)
    for nombre in ("recuperar", "revertir"):
        q = s.add_parser(nombre)
        q.add_argument("--confirmar-ensayo", action="store_true", required=True)
    q = s.add_parser("observar")
    q.add_argument("--reglas", type=Path, help="umbrales de ensayo explícitos, JSON")
    q = s.add_parser("registrar")
    q.add_argument("--tipo", required=True, choices=("contacto_pc", "captura_rechazada"))
    q.add_argument("--en", help="ISO-8601 con zona; por defecto, ahora")
    q = s.add_parser("calendario")
    q.add_argument("--archivo", type=Path, required=True, help="calendario explícito por juego; no se infieren horarios")
    q = s.add_parser("exportar")
    q.add_argument("--puerto", type=int, default=9125)
    s.add_parser("auditar")
    s.add_parser("estado")
    return p


def observar(a: Almacen, ahora: datetime, reglas: dict | None = None) -> dict:
    from app.infrastructure.generaciones.importacion import verificar_publicada
    with a.exclusivo():
        e = a.inicializar()
        senales = ob.validar_senales(a.leer("senales.json", ob.senales_iniciales()))
        m, servicio = None, None
        if e["activa"]:
            plan = a.plan(e["activa"])
            try:
                v = verificar_publicada(Path(plan.directorio_generacion), Path(plan.clave_publica))
                if (v["sha256_manifiesto"] != plan.manifiesto_sha256
                        or v["manifiesto"]["codigo"]["huella_app"] != plan.huella_app):
                    raise Rechazo("generacion_de_otro_plan")
                m = v["manifiesto"]
                senales = ob.registrar(senales, "captura_verificada", m["creada_en"], ahora=ahora)
            except (ValueError, OSError, KeyError, TypeError):
                m = None
            try:
                op = Docker(a, e["propietario"])
                import time
                op.sonda(plan, time.monotonic() + 10)
                ob.servicio_de(op.ultimo_estado)
                servicio = op.ultimo_estado
            except (ValueError, OSError, KeyError, TypeError):
                servicio = None
        v = ob.muestra(e, m, servicio, senales, ahora, reglas)
        a.escribir("senales.json", senales)
        a.escribir("observacion.json", v)
        return {"codigo": 0, **ob.evaluar(v, ahora)}


def ejecutar(args) -> dict | None:
    ahora = datetime.now(timezone.utc)
    crear = args.orden == "inicializar"
    with Almacen(args.control, crear=crear) as a:
        if args.orden == "inicializar":
            with a.exclusivo():
                a.inicializar()
            return {"codigo": 0, "resultado": "control_inicializado"}
        if args.orden == "renderizar":
            plan = leer_plan(args.plan)
            with a.exclusivo():
                e = a.inicializar()
                a.guardar_plan(plan)
                Docker(a, e["propietario"]).materializar(plan)
            return {"codigo": 0, "resultado": "renderizado_sin_ejecutar", "plan": plan.id}
        if args.orden in ("activar", "recuperar", "revertir"):
            motor = Motor(a, lambda propietario: Docker(a, propietario))
            if args.orden == "activar":
                return motor.activar(leer_plan(args.plan))
            return getattr(motor, args.orden)()
        if args.orden in ("registrar", "calendario"):
            with a.exclusivo():
                a.inicializar()
                s = ob.validar_senales(a.leer("senales.json", ob.senales_iniciales()))
                if args.orden == "registrar":
                    s = ob.registrar(s, args.tipo, args.en or ahora.isoformat(), ahora=ahora)
                else:
                    with args.archivo.open("rb") as f:
                        s["calendario"] = json_estricto(f.read(262145))
                    ob.validar_senales(s)
                a.escribir("senales.json", s)
            return {"codigo": 0, "resultado": "senal_registrada"}
        if args.orden == "observar":
            reglas = None
            if args.reglas:
                with args.reglas.open("rb") as f:
                    reglas = ob.reglas_de(json_estricto(f.read(262145)))
            return observar(a, ahora, reglas)
        if args.orden in ("estado", "auditar"):
            with a.exclusivo():
                e = a.inicializar()
                if args.orden == "auditar":
                    return auditoria.informe(e, a.leer("observacion.json"), ahora)
                return {"codigo": 0, "activa": a.plan(e["activa"]).generacion if e["activa"] else None,
                        "acceso": e["acceso"], "recuperacion_pendiente": e["pendiente"] is not None,
                        "contadores": e["contadores"]}
        if args.orden == "exportar":
            servidor = crear_servidor(a, args.puerto)
            try:
                print(json.dumps({"exportador": "127.0.0.1", "puerto": servidor.server_port}), flush=True)
                servidor.serve_forever(poll_interval=0.25)
            except KeyboardInterrupt:
                pass
            finally:
                servidor.server_close()
            return {"codigo": 0, "resultado": "exportador_detenido"}
    raise Rechazo("orden_no_valida")


def main() -> int:
    args = parser().parse_args()
    try:
        r = ejecutar(args)
    except (Exception, KeyboardInterrupt):
        # Nunca imprimir traceback, la entrada ni el mensaje de una biblioteca.
        r = {"codigo": 2, "resultado": "rechazado_o_interrumpido"}
    print(json.dumps(r, sort_keys=True, ensure_ascii=False), flush=True)
    return r["codigo"]


if __name__ == "__main__":
    sys.exit(main())
