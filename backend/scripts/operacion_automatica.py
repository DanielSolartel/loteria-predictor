"""Fase 6: ejecución independiente. Ningún comando instala tareas Windows.

La configuración de arranque contiene destinos y una huella, nunca la URL
de conexión. Preparar/reanudar y aceptar una revisión son acciones explícitas.
La consulta de estado no abre una sesión de BD ni ejecuta el ciclo.

`ciclo` exige declarar quién lo inicia:
- `ciclo --programado --plan <huella>`: lo usa la tarea programada; consulta solo lo que admite
  el horario y solo si la huella coincide con el plan de la política vigente (si no, código 4);
- `ciclo --manual [--juego J] [--forzar]`: comprobación explícita de una persona, sin franjas, con
  las mismas esperas, cerrojos y bloqueos de emisión.
Un `ciclo` sin modo (la acción de la tarea anterior a la política de horario) sale con código 2 y no
consulta nada. `horario plan` imprime el plan de la tarea; `horario migrar --confirmar` pasa
explícitamente la configuración de la versión 1 a la 2 con la propuesta inicial (sin activar nada).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.api.automatizacion_dependencies import (
    BACKEND, archivo_configuracion, construir_automatizacion, destinos_resueltos,
    leer_configuracion_arranque, referencia_destinos,
)
from app.application import operacion_horario as horario
from app.application.use_cases.operacion_automatica import JUEGOS, InvocacionProgramada, ahora_utc
from app.core.config import get_settings
from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion
from app.infrastructure.storage.operacion_file_store import _publicar_temporal


def _imprimir(objeto, salida):
    salida.write(json.dumps(objeto, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _preparar(ajustes, ruta, *, confirmar, reemplazar=False, backend=BACKEND):
    if not confirmar:
        raise ValueError("Primero revise rutas; preparar requiere --confirmar-destinos explícito.")
    esperado = referencia_destinos(ajustes, backend)
    store = AlmacenAutomatizacion(esperado["destinos"]["directorio_automatizacion"])
    if any(store.activa(j) for j in JUEGOS):
        raise ValueError("Hay un ciclo activo. Pause y espere antes de cambiar el arranque.")
    actual = leer_configuracion_arranque(ruta)
    if actual is not None:
        comparable = {k: actual.get(k) for k in esperado}
        # Conservar las excepciones explícitas existentes al preparar de nuevo.
        comparable["excepciones"] = {}
        if comparable == esperado:
            return {"estado": "reutilizada", "archivo": str(ruta), "destinos": esperado["destinos"]}
        if not reemplazar:
            raise ValueError("El archivo fija otros destinos. Revise y use --reemplazar solo si corresponde.")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    import secrets
    temporal = ruta.parent / (".arranque-" + secrets.token_hex(4) + ".tmp")
    try:
        with temporal.open("xb") as f:
            f.write((json.dumps(esperado, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
            f.flush()
            import os
            os.fsync(f.fileno())
        _publicar_temporal(temporal, ruta)
    finally:
        if temporal.exists():
            temporal.unlink()
    # Preparar no habilita ciclos: la activación del núcleo y la tarea son
    # pasos separados. Tampoco se copian configuraciones/modelos anteriores.
    store.actualizar_configuracion({"activada": False, "pausada": True})
    return {"estado": "preparada_en_pausa", "archivo": str(ruta), "destinos": esperado["destinos"]}


def _horario(servicio, args):
    servicio._verificar_destinos()
    conf = servicio.almacen.configuracion()
    if args.accion == "plan":  # solo lectura de la configuración; el archivo de salida es nuevo
        politica = horario.de_configuracion(conf)
        if politica is None:
            raise ValueError("Configuración de versión 1 sin horario: migre antes de generar el plan.")
        horario.validar_con_calendario(politica, servicio.calendarios)
        plan = horario.plan_windows(politica)
        if args.salida:
            destino = Path(args.salida)
            if not destino.is_absolute():
                raise ValueError("La salida del plan debe ser una ruta absoluta.")
            with destino.open("x", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        return plan
    if not args.confirmar:
        raise ValueError("Migrar escribe la configuración: requiere --confirmar.")
    if any(servicio.almacen.activa(j) for j in JUEGOS):
        raise ValueError("Hay un ciclo activo. Espere a que termine antes de migrar.")
    propuesta = horario.propuesta_inicial()
    horario.validar_con_calendario(propuesta, servicio.calendarios)
    actual = horario.de_configuracion(conf)
    if actual is not None and horario.como_dict(actual) == horario.como_dict(propuesta):
        return {"estado": "reutilizada", "version": 2, "huella_plan": horario.huella_plan(actual)}
    if actual is not None and not args.reemplazar:
        raise ValueError("Ya hay otra política de versión 2; use --reemplazar solo si corresponde.")
    nueva = servicio.almacen.actualizar_configuracion({"version": 2, "horario": horario.como_dict(propuesta)})
    return {"estado": "migrada", "version": nueva["version"], "anterior": conf.get("version"),
            "activada": nueva["activada"], "pausada": nueva["pausada"], "huella_plan": horario.huella_plan(propuesta),
            "aviso": "La tarea de Windows no cambia: registre el plan con fase6_tarea.ps1 siguiendo el procedimiento."}


def ejecutar(argv=None, *, ajustes=None, servicio_factory=construir_automatizacion,
             salida=sys.stdout, errores=sys.stderr, backend=BACKEND):
    p = argparse.ArgumentParser(description="Operación automática Fase 6, sin depender del servidor web")
    p.add_argument("--config", help="Archivo de arranque absoluto; no contiene credenciales")
    sub = p.add_subparsers(dest="orden", required=True)
    sub.add_parser("rutas", help="Destinos resueltos sin DSN ni credenciales")
    q = sub.add_parser("preparar", help="Fija destinos revisados; queda en pausa")
    q.add_argument("--confirmar-destinos", action="store_true")
    q.add_argument("--reemplazar", action="store_true")
    for nombre in ("estado", "pausar", "reanudar", "recuperar"):
        sub.add_parser(nombre)
    q = sub.add_parser("ciclo", help="Una comprobación acotada; respeta pausa/backoff")
    modo = q.add_mutually_exclusive_group()
    modo.add_argument("--programado", action="store_true", help="Invocación de la tarea programada (requiere --plan)")
    modo.add_argument("--manual", action="store_true", help="Comprobación manual explícita, sin franjas")
    q.add_argument("--plan", help="Huella del plan con el que se registró la tarea")
    q.add_argument("--juego", choices=[*JUEGOS, "todos"], default="todos")
    q.add_argument("--forzar", action="store_true", help="Anticipa la consulta manual sin saltar espera de un fallo")
    q = sub.add_parser("horario", help="Plan de la tarea o migración explícita de la configuración")
    acciones = q.add_subparsers(dest="accion", required=True)
    x = acciones.add_parser("plan", help="Imprime el plan de la tarea (solo lectura)")
    x.add_argument("--salida", help="Archivo nuevo donde escribir el plan (no se sobrescribe)")
    x = acciones.add_parser("migrar", help="Versión 1 -> 2 con la propuesta inicial; no activa nada")
    x.add_argument("--confirmar", action="store_true")
    x.add_argument("--reemplazar", action="store_true", help="Sustituye una política de versión 2 distinta")
    q = sub.add_parser("revision", help="Revisión explícita; nunca aceptación automática")
    q.add_argument("--clave", required=True)
    q.add_argument("--nota", required=True)
    modos = q.add_mutually_exclusive_group(required=True)
    modos.add_argument("--aceptar", action="store_true")
    modos.add_argument("--rechazar", action="store_true")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 2
    try:
        ajustes = ajustes or get_settings()
        ruta = archivo_configuracion(ajustes, args.config, backend)
        if args.orden == "rutas":
            _imprimir({"backend": str(Path(backend).resolve()), "archivo_operativo": str(ruta),
                       "destinos": destinos_resueltos(ajustes, backend)}, salida)
            return 0
        if args.orden == "preparar":
            _imprimir(_preparar(ajustes, ruta, confirmar=args.confirmar_destinos,
                               reemplazar=args.reemplazar, backend=backend), salida)
            return 0
        if args.orden == "ciclo" and not (args.programado or args.manual):
            errores.write("Indique quién inicia el ciclo: --programado --plan <huella> (tarea) o --manual. "
                          "No se consulta nada.\n")
            return 2
        if args.orden == "ciclo" and args.programado and (args.plan is None or args.juego != "todos" or args.forzar):
            errores.write("La invocación programada requiere --plan y elige los juegos por horario. No se consulta nada.\n")
            return 2
        if args.orden == "ciclo" and args.manual and args.plan is not None:
            errores.write("--plan solo acompaña a --programado.\n")
            return 2
        servicio = servicio_factory(configuracion_archivo=str(ruta), ajustes=ajustes, backend=backend)
        if args.orden == "horario":
            resultado = _horario(servicio, args)
            _imprimir(resultado, salida)
            return 0
        if args.orden == "estado":
            resultado = servicio.panel()
        elif args.orden in ("pausar", "reanudar", "recuperar"):
            resultado = getattr(servicio, args.orden)()
        elif args.orden == "revision":
            servicio._verificar_destinos()
            propuesta = servicio.almacen.revision(args.clave)
            if propuesta is None or not args.nota.strip() or len(args.nota) > 1000:
                raise ValueError("Revisión o nota inválida.")
            if args.aceptar:
                resultado = servicio.adaptador.aplicar_revision(args.clave, args.nota)
            else:
                previas = servicio.almacen.decisiones_revision(args.clave)
                vigente = previas[0].get("decision", {}) if previas and not previas[0].get("orden_ambiguo") else {}
                misma = vigente if vigente.get("estado") == "rechazada" and vigente.get("nota") == args.nota.strip() else None
                decision = misma or {"estado": "rechazada", "nota": args.nota.strip(), "en": ahora_utc().isoformat()}
                servicio.almacen.guardar_decision_revision(args.clave, decision)
                resultado = {"clave": args.clave, "estado": "rechazada", "reutilizada": misma is not None}
        elif args.programado:
            resultado = servicio.ciclo(programado=InvocacionProgramada(args.plan))
        else:
            juegos = None if args.juego == "todos" else [args.juego]
            resultado = servicio.ciclo(juegos=juegos, forzar=args.forzar, origen="comando")
        _imprimir(resultado, salida)
        estado = resultado.get("estado") if isinstance(resultado, dict) else None
        if estado in ("horario_no_configurado", "horario_no_valido", "plan_divergente"):
            return 4
        return 6 if estado == "ocupado" else 5 if estado == "parcial" else 7 if estado in ("fallo", "error") else 0
    except ValueError:
        errores.write("Configuración, destinos o revisión no válidos. Use rutas/estado y conserve los registros.\n")
        return 2
    except OSError:
        errores.write("No se pudo acceder al recurso operativo. Conserve los registros y revise rutas/permisos.\n")
        return 3
    except Exception as error:
        # No volcar DSN, respuestas del proveedor ni contenido de .env.
        errores.write("Fallo operativo (" + type(error).__name__ + "). Conserve el historial para el diagnóstico.\n")
        return 7


def main(argv=None):
    return ejecutar(argv)


if __name__ == "__main__":
    raise SystemExit(main())
