"""Composición portable del ejecutor. No conecta ni activa tareas al importar.

El archivo de arranque fija rutas absolutas y una huella de la conexión;
no contiene credenciales. Debe prepararse explícitamente en el worktree
actual. La web y la CLI verifican los mismos destinos antes de escribir.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, time
import hashlib
import json
from pathlib import Path
import threading

from app.application.operacion_calendario import calendario_defecto, ExcepcionCalendario
from app.application.use_cases.operacion_automatica import OperacionAutomatica, ahora_utc
from app.core.config import get_settings
from app.infrastructure.operacion_automatica_adaptador import AdaptadorOperacion
from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion

BACKEND = Path(__file__).resolve().parents[2]
RUTAS = ("directorio_pronosticos_experimentales", "directorio_operacion", "directorio_laboratorio_modelos",
         "directorio_carteras_modelos", "directorio_resultados_modelos", "directorio_predicciones_modelos",
         "directorio_automatizacion")


def destinos_resueltos(ajustes, backend=BACKEND):
    base = Path(backend).resolve()
    def resolver(v):
        p = Path(v)
        return str((p if p.is_absolute() else base / p).resolve())
    destinos = {k: resolver(getattr(ajustes, k)) for k in RUTAS}
    destinos["html_crudo"] = str(base / "storage" / "html")
    return destinos


def archivo_configuracion(ajustes, solicitado=None, backend=BACKEND):
    valor = solicitado if solicitado is not None else ajustes.archivo_operacion_automatica
    if valor:
        p = Path(valor)
        if not p.is_absolute():
            raise ValueError("El archivo operativo configurado debe tener ruta absoluta.")
        return p.resolve()
    return Path(destinos_resueltos(ajustes, backend)["directorio_automatizacion"]) / "config-ejecucion.json"


def referencia_destinos(ajustes, backend=BACKEND):
    return {"version": 1, "backend": str(Path(backend).resolve()),
            "database_sha256": hashlib.sha256(ajustes.database_url.encode("utf-8")).hexdigest(),
            "destinos": destinos_resueltos(ajustes, backend), "excepciones": {}}


def leer_configuracion_arranque(ruta):
    p = Path(ruta)
    if not p.is_file():
        return None
    if p.stat().st_size > 262144:
        raise ValueError("El archivo de arranque operativo supera el límite permitido.")
    def no_finito(_):
        raise ValueError("Configuración operativa no finita.")
    c = json.loads(p.read_text(encoding="utf-8-sig"), parse_constant=no_finito)
    if not isinstance(c, dict) or c.get("version") != 1:
        raise ValueError("Versión de configuración de arranque desconocida.")
    if set(c) - {"version", "backend", "database_sha256", "destinos", "excepciones"}:
        raise ValueError("El archivo de arranque no admite credenciales ni campos ajenos.")
    _calendarios(c)
    return c


def _calendarios(boot):
    calendarios = calendario_defecto()
    cambios = (boot or {}).get("excepciones", {})
    if not isinstance(cambios, dict) or set(cambios) - set(calendarios):
        raise ValueError("Juego de calendario desconocido.")
    for codigo, filas in cambios.items():
        if not isinstance(filas, list) or len(filas) > 100:
            raise ValueError("Las excepciones deben ser una lista acotada por juego.")
        excepciones = []
        for f in filas:
            if not isinstance(f, dict) or set(f) - {"fecha", "hora_local", "hora_fin_local", "motivo", "fuente_url", "verificada"}:
                raise ValueError("Excepción de calendario inválida.")
            excepciones.append(ExcepcionCalendario(
                fecha=date.fromisoformat(f["fecha"]),
                hora_local=time.fromisoformat(f["hora_local"]) if f.get("hora_local") else None,
                hora_fin_local=time.fromisoformat(f["hora_fin_local"]) if f.get("hora_fin_local") else None,
                motivo=f.get("motivo", ""), fuente_url=f.get("fuente_url", ""), verificada=f.get("verificada", False)))
        calendarios[codigo] = replace(calendarios[codigo], excepciones=tuple(excepciones))
    return calendarios


def construir_automatizacion(configuracion_archivo=None, *, ajustes=None, adaptador=None, almacen=None,
                            reloj=ahora_utc, backend=BACKEND):
    ajustes = ajustes or get_settings()
    referencia = referencia_destinos(ajustes, backend)
    ruta = archivo_configuracion(ajustes, configuracion_archivo, backend)
    # Solo leer archivos públicos/operativos concretos; no escanear almacenes.
    try:
        boot = leer_configuracion_arranque(ruta)
    except (ValueError, OSError):
        boot = None
    def validar():
        try:
            actual = leer_configuracion_arranque(ruta)
            return actual is not None and all(actual.get(k) == referencia[k]
                                              for k in ("version", "backend", "database_sha256", "destinos"))
        except (ValueError, OSError):
            return False
    efectivos = ajustes.model_copy(update={k: referencia["destinos"][k] for k in RUTAS})
    store = almacen if almacen is not None else AlmacenAutomatizacion(efectivos.directorio_automatizacion)
    def obtener_conector(codigo):
        # Construcción diferida: HtmlFileStorage inicializa su carpeta solo
        # al ejecutar una comprobación explícita, nunca al consultar el panel.
        from app.infrastructure.connectors.registry import ConnectorRegistry
        from app.infrastructure.storage.html_file_storage import HtmlFileStorage
        return ConnectorRegistry(HtmlFileStorage(referencia["destinos"]["html_crudo"])).obtener(codigo)
    adaptador = adaptador if adaptador is not None else AdaptadorOperacion(
        efectivos, registrar_revision=store.guardar_revision, obtener_revision=store.revision,
        registrar_decision_revision=store.guardar_decision_revision, reloj=reloj,
        obtener_conector=obtener_conector, obtener_decisiones_revision=store.decisiones_revision)
    servicio = OperacionAutomatica(store, adaptador, reloj=reloj, calendarios=_calendarios(boot),
                                  validar_destinos=validar)
    servicio.archivo_arranque = str(ruta)
    return servicio


def get_automatizacion():
    """Dependencia web sin parámetros de consulta que alteren los destinos."""
    return construir_automatizacion()


def get_lanzador_automatizacion():
    def lanzar(funcion):
        # Un trabajo manual por POST; no es un planificador por Uvicorn.
        # El ciclo adquiere cerrojos y conserva pasos antes de operaciones.
        threading.Thread(target=funcion, name="fase6-manual", daemon=True).start()
    return lanzar
