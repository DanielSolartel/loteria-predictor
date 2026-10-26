"""Fase 6: ciclo desatendido, sin servidor web ni selección de modelos.

El reloj y los puertos se inyectan. La admisión temporal se liga al primer
evento posterior al último resultado cargado, nunca al próximo desde hoy.
La persistencia, adquisición y predicción pertenecen a sus adaptadores/UC.

Dos formas de iniciar un ciclo:
- programada (la tarea de Windows): `ciclo(programado=InvocacionProgramada(plan))`. Exige una
  configuración de versión 2 con política de horario válida y la huella de su plan; solo consulta
  los juegos habilitados cuya franja (o recuperación) admite esa oportunidad, revalidando cada juego
  justo antes de empezarlo. Sin política, con otra huella o fuera de horario no consulta nada;
- manual explícita (CLI `ciclo --manual`, botón del panel local): la comprobación de siempre, sin
  franjas, que respeta pausa, cerrojos, espera por fallos, Retry-After y el cierre de emisión.
La etiqueta `origen` solo describe; no concede ni quita una admisión.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
from typing import Callable

from app.application import operacion_horario as horario
from app.application.operacion_calendario import calendario_defecto, eventos, clasificar, admisible_emitir
from app.application.use_cases.operacion_diaria import nuevo_identificador

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
ORIGEN_PROGRAMADO = "programado"
_HUELLA = re.compile(r"[0-9a-f]{64}")


class InvocacionProgramada:
    """Invocación de la tarea programada: lleva la huella del plan con el que se registró."""

    def __init__(self, plan: str):
        if not isinstance(plan, str) or not _HUELLA.fullmatch(plan):
            raise ValueError("La invocación programada requiere la huella SHA-256 de su plan.")
        self.plan = plan


def ahora_utc():
    return datetime.now(timezone.utc)


def _instante(valor):
    if valor is None:
        return None
    d = datetime.fromisoformat(valor) if isinstance(valor, str) else valor
    if not isinstance(d, datetime) or d.tzinfo is None:
        raise ValueError("El instante operativo debe incluir zona horaria.")
    return d.astimezone(timezone.utc)


def _huella(objeto):
    return hashlib.sha256(json.dumps(objeto, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _error_seguro(error, paso):
    # No serializar DSN, cuerpos HTTP, variables locales ni credenciales de
    # excepciones de librerías. Conservar clase, etapa y metadatos tipados.
    r = {"tipo": type(error).__name__, "paso": paso,
         "mensaje": "No se pudo completar este paso; conserve el registro y revise la conexión o el recurso indicado."}
    codigo = getattr(error, "codigo", None)
    if isinstance(codigo, str) and re.fullmatch(r"[a-z0-9_]{1,80}", codigo):
        r["codigo"] = codigo
    respuesta = getattr(error, "response", None)
    estado = getattr(respuesta, "status_code", None)
    if isinstance(estado, int):
        r["http_status"] = estado
    return r


class OperacionAutomatica:
    def __init__(self, almacen, adaptador, *, reloj: Callable = ahora_utc,
                 calendarios=None, validar_destinos: Callable | None = None):
        self.almacen = almacen
        self.adaptador = adaptador
        self.reloj = reloj
        self.calendarios = calendario_defecto() if calendarios is None else calendarios
        self.validar_destinos = validar_destinos or (lambda: True)

    def _ahora(self):
        return _instante(self.reloj())

    def _verificar_destinos(self):
        if not self.validar_destinos():
            raise ValueError("Los destinos operativos no coinciden con la aplicación; prepare y revise la configuración.")

    def pausar(self):
        return self.almacen.actualizar_configuracion({"pausada": True})

    def reanudar(self):
        self._verificar_destinos()
        return self.almacen.actualizar_configuracion({"activada": True, "pausada": False})

    def consultar_ejecucion(self, identificador):
        e = self.almacen.obtener_ejecucion(identificador)
        if e and e.get("estado") == "en_curso" and not self.almacen.viva(identificador):
            # El escritor publica el cierre antes de liberar su lease. La
            # primera lectura puede ser anterior a ese cierre y la prueba
            # de vida posterior: releer evita proyectar una interrupción
            # desde una instantánea vieja. Esta consulta no persiste nada.
            e = self.almacen.obtener_ejecucion(identificador)
            if not e or e.get("estado") != "en_curso":
                return e
            return {**e, "estado": "interrumpida", "motivo": "El proceso terminó sin registrar su cierre. Se conserva lo ya publicado."}
        return e

    def panel(self):
        conf = self.almacen.configuracion()
        ejecuciones = [self.consultar_ejecucion(e["id"]) for e in self.almacen.recientes(20)]
        juegos = []
        for codigo in JUEGOS:
            estado = self.almacen.estado(codigo)
            actual = {"codigo": codigo, "juego": codigo, "estado": "sin_comprobar", **estado}
            for e in ejecuciones:
                if e and codigo in e.get("juegos", {}):
                    r = e["juegos"][codigo]
                    if (e.get("estado") in ("en_curso", "interrumpida")
                            and r.get("estado") in ("pendiente", "en_curso", "interrumpido")):
                        actual.update(r)
                        actual["ejecucion"] = e["id"]
                        if e["estado"] == "interrumpida":
                            actual.update(estado="interrumpido", motivo=e.get("motivo"))
                    # Solo la última ejecución de este juego puede proyectar
                    # actividad/interrupción. Un cierre posterior no revive
                    # la interrupción de una ejecución anterior.
                    break
            juegos.append(actual)
        avisos = [{"juego": x["codigo"], "motivo": x.get("motivo"), "error": x.get("error")}
                  for x in juegos if x.get("error") or x.get("motivo")]
        pendientes = []
        historial_revisiones = []
        for revision in self.almacen.revisiones(100):
            decisiones = self.almacen.decisiones_revision(revision["clave"])
            historial_revisiones.append({"revision": revision, "decisiones": decisiones})
            # La propuesta es inmutable y conserva estado="pendiente".
            # Solo una decisión vigente no ambigua resuelve la revisión;
            # no convierte una revisión ya resuelta en un pendiente del panel.
            ultima = decisiones[0].get("decision", {}) if decisiones and not decisiones[0].get("orden_ambiguo") else {}
            if ultima.get("estado") not in ("aceptada", "rechazada"):
                pendientes.append(revision)
        verificado = bool(self.validar_destinos())
        return {"estado": "sin_configurar" if not verificado else "pausada" if conf.get("pausada", True) or not conf.get("activada") else "habilitada",
                "configuracion": conf, "juegos": juegos, "ejecuciones": ejecuciones,
                "horario": self._horario_panel(conf),
                "avisos": avisos, "revisiones": pendientes, "historial_revisiones": historial_revisiones,
                "rutas_verificadas": verificado,
                "programacion_windows": "Verificar por separado en el Programador de tareas; la web no instala ni activa tareas.",
                "aviso": "experimental_no_acreditado; AE-39 NO-GO; AUTORIZA_EVALUACION = False"}

    def _politica(self, conf):
        politica = horario.de_configuracion(conf)
        if politica is not None:
            horario.validar_con_calendario(politica, self.calendarios)
        return politica

    def _horario_panel(self, conf):
        """Franjas, próxima oportunidad y motivo de espera por juego. Solo lee: no consulta ni escribe."""
        try:
            politica = self._politica(conf)
        except ValueError as error:
            return {"estado": "no_valida", "motivo": str(error), "juegos": {}}
        if politica is None:
            return {"estado": "sin_migrar", "juegos": {},
                    "motivo": "Configuración de versión 1 sin horario: la tarea programada no consulta hasta migrarla "
                              "(`horario migrar --confirmar`); la comprobación manual sigue disponible."}
        ahora = self._ahora()
        maximo = int(conf.get("politica", {}).get("max_reintentos", 8))
        juegos = {}
        for codigo in JUEGOS:
            habilitado = codigo in conf.get("juegos", JUEGOS)
            estado = self.almacen.estado(codigo)
            d = horario.decidir(politica, codigo, ahora, estado, max_reintentos=maximo)
            pendiente = d.motivo not in ("fuera_de_horario", "evento_completo") or estado.get("estado") != "correcto"
            siguiente = horario.proxima_oportunidad(politica, codigo, ahora, incluir_recuperacion=pendiente)
            juegos[codigo] = {
                "habilitado_en_nucleo": habilitado,
                "franjas": [{"dia": horario.DIAS[f.dia], "inicio": horario._hhmm(f.inicio), "fin": horario._hhmm(f.fin),
                             "termina_al_dia_siguiente": f.fin <= f.inicio} for f in politica.franjas_de(codigo)],
                "motivo": "deshabilitado" if not habilitado else d.motivo, "detalle": d.detalle,
                "proxima_oportunidad": None if siguiente is None else siguiente[0].isoformat(),
                "tipo_proxima": None if siguiente is None else siguiente[1].tipo}
        return {"estado": "valida", "politica": horario.como_dict(politica), "huella_plan": horario.huella_plan(politica),
                "recuperacion": None if politica.recuperacion is None else horario._hhmm(politica.recuperacion),
                "intervalo_minutos": politica.intervalo_minutos, "ahora": ahora.isoformat(), "juegos": juegos}

    def recuperar(self):
        """Solo registro y planificación: no sincroniza, genera o borra nada."""
        marcadas = []
        for original in self.almacen.recientes(200):
            e = self.consultar_ejecucion(original["id"])
            if original.get("estado") == "en_curso" and e and e.get("estado") == "interrumpida":
                def interrumpir(actual):
                    actual = deepcopy(actual)
                    actual.update(estado="interrumpida", finalizada_en=self._ahora().isoformat(),
                                  motivo="El proceso terminó sin registrar su cierre. Se conserva lo ya publicado.")
                    for r in actual.get("juegos", {}).values():
                        if r.get("estado") in ("pendiente", "en_curso"):
                            r["estado"] = "interrumpido"
                            r["motivo"] = "Recuperación pendiente; repetir conserva las publicaciones anteriores."
                    return actual
                # La proyección de lectura solo selecciona candidatos. La
                # actualización relee y comprueba la vida bajo el mismo
                # recurso que usa el escritor para publicar su cierre.
                guardada = self.almacen.actualizar_ejecucion_interrumpida(original["id"], interrumpir)
                if guardada is not None:
                    marcadas.append(guardada["id"])
        rearmados = []
        maximo = int(self.almacen.configuracion().get("politica", {}).get("max_reintentos", 8))
        for codigo in JUEGOS:
            # La recuperación no puede reescribir el estado de un proceso vivo.
            lease = self.almacen.adquirir([codigo], nuevo_identificador(self._ahora()))
            if isinstance(lease, dict):
                continue
            try:
                estado = self.almacen.estado(codigo)
                if int(estado.get("fallos_consecutivos", 0)) >= maximo:
                    estado.update(fallos_consecutivos=0, proxima_consulta=self._ahora().isoformat(),
                                  estado="recuperacion_pendiente",
                                  motivo="Reintentos rearmados explícitamente; revise el próximo ciclo.")
                    self.almacen.guardar_estado(codigo, estado)
                    rearmados.append(codigo)
            finally:
                lease.liberar()
        return {"interrumpidas_marcadas": marcadas, "reintentos_rearmados": rearmados,
                "estado": "recuperacion_registrada"}

    def _guardar_paso(self, ejecucion, r, paso, datos):
        r["pasos"].append({"paso": paso, "en": self._ahora().isoformat(), "resultado": datos})
        ejecucion["juegos"][r["codigo"]] = r
        self.almacen.guardar_ejecucion(ejecucion)

    def _evento_del_objetivo(self, calendario, ultimo):
        f = ultimo.get("fecha")
        if not f or ultimo.get("ultimo_sorteo") is None:
            return None
        f = date.fromisoformat(f) if isinstance(f, str) else f
        candidatos = eventos(calendario, f + timedelta(days=1), f + timedelta(days=21))
        return candidatos[0] if candidatos else None

    def _proxima_consulta(self, politica, r, anterior, ahora, error):
        if error:
            intentos = min(int(anterior.get("fallos_consecutivos", 0)) + 1, 30)
            espera = min(int(politica.get("reintento_maximo_segundos", 3600)),
                         int(politica.get("reintento_inicial_segundos", 300)) * 2 ** min(intentos - 1, 20))
            # Retry-After es un límite inferior del proveedor, nunca un permiso
            # para consultar más rápido. Se conserva separado del error seguro.
            espera = max(espera, int(r.get("reintentar_despues_segundos", 0)))
            return ahora + timedelta(seconds=espera), intentos
        evento = _instante(r.get("proximo_evento"))
        minutos = int(politica.get("intervalo_minutos", 15))
        fuera = int(politica.get("intervalo_fuera_ventana_minutos", 180))
        if evento and evento > ahora + timedelta(minutes=30):
            return min(ahora + timedelta(minutes=fuera), evento - timedelta(minutes=30)), 0
        return ahora + timedelta(minutes=minutos), 0

    def _un_juego(self, e, codigo, conf, oportunidad=None, confirmar=None):
        previo = self.almacen.estado(codigo)
        conservar_espera = False
        r = {"codigo": codigo, "juego": codigo, "estado": "en_curso", "pasos": [], "motivo": None,
             "ejecucion": e["id"], "ultima_comprobacion": self._ahora().isoformat(), "error": None}
        for campo in ("ultimo_sorteo", "fecha_ultimo_sorteo", "sorteos", "ultima_actualizacion", "pagina_recuperacion",
                      "horario"):
            if campo in previo:
                r[campo] = previo[campo]
        if oportunidad is not None:  # slot programado consumido por este intento, aunque falle
            r["horario"] = oportunidad.registro()
        paso = "abrir_recursos"
        politica = conf.get("politica", {})
        try:
            with self.adaptador.por_juego(codigo) as dep:
                paso = "instantanea_inicial"
                antes = dep.instantanea()
                self._guardar_paso(e, r, paso, antes)
                paso = "congelar_configuracion"
                try:
                    seleccion = deepcopy(dep.configuracion())
                    r["configuracion_modelo"] = seleccion
                    r["huella_configuracion"] = _huella(seleccion)
                except Exception as error:
                    seleccion = None
                    r["bloqueo_modelo"] = _error_seguro(error, paso)
                self._guardar_paso(e, r, paso, {"huella": r.get("huella_configuracion"), "disponible": seleccion is not None})
                if self.almacen.configuracion().get("pausada", True):
                    r.update(estado="pausada", motivo="La operación se pausó antes de consultar.")
                    return r
                if oportunidad is not None and confirmar is not None:
                    # Borde real de la consulta al proveedor: el mismo slot admitido, con el reloj de ahora.
                    paso = "confirmar_horario"
                    confirmada = confirmar(oportunidad)
                    self._guardar_paso(e, r, paso, {"admitido": confirmada.admitido, "motivo": confirmada.motivo,
                                                    "oportunidad": oportunidad.oportunidad.isoformat()})
                    if not confirmada.admitido:
                        # La preparación cruzó el cierre: no se inicia `sincronizar`, no se consume otro slot y
                        # se conservan la espera y los fallos anteriores (F92-HOR-01).
                        r["horario"] = {**oportunidad.registro(), "consulta": "no_iniciada", "motivo": confirmada.motivo}
                        r.update(estado="omitido_horario", motivo=confirmada.detalle)
                        conservar_espera = True
                        return r
                paso = "sincronizacion"
                parametros = {"max_paginas": int(politica.get("max_paginas", 3)),
                              "reconciliar_ultimos": int(politica.get("reconciliar_ultimos", 12)),
                              "pagina_recuperacion": int(previo.get("pagina_recuperacion", 1))}
                sync = dep.sincronizar(**parametros)
                r["pagina_recuperacion"] = int(sync.get("pagina_recuperacion_siguiente", previo.get("pagina_recuperacion", 1)))
                self._guardar_paso(e, r, paso, sync)
                if sync.get("estado") not in ("completado", "correcto", "exito"):
                    r.update(estado="fallo_consulta", motivo="La adquisición no terminó correctamente; no se emite con datos anteriores.")
                    r["error"] = {"paso": paso, "tipo": "AdquisicionIncompleta", "mensaje": r["motivo"]}
                    r["reintentar_despues_segundos"] = max(0, int(sync.get("reintentar_despues_segundos", 0)))
                    return r
                despues = dep.instantanea()
                r.update(ultimo_sorteo=despues.get("ultimo_sorteo"), fecha_ultimo_sorteo=despues.get("fecha"),
                         sorteos=despues.get("sorteos"), ultima_actualizacion=previo.get("ultima_actualizacion"))
                if despues != antes:
                    r["ultima_actualizacion"] = self._ahora().isoformat()
                paso = "resultados_fiabilidad"
                seguimiento = dep.reconciliar()
                self._guardar_paso(e, r, paso, seguimiento)
                if despues.get("huecos", 0):
                    r.update(estado="historico_incompleto", motivo="Faltan sorteos dentro del intervalo cargado. La recuperación paginada continúa; no se emite sobre huecos.")
                    return r
                persistidas = self.almacen.revisiones_pendientes(
                    codigo, despues.get("primer_sorteo"), despues.get("ultimo_sorteo"))
                # Una propuesta no deja de afectar a este histórico al salir
                # de las páginas recientes o de las 100 entradas del panel.
                # Los puertos que detecten una discrepancia sin persistirla
                # todavía tampoco autorizan la emisión (fallo cerrado).
                sin_propuesta = [clave for clave in sync.get("pendientes_revision", [])
                                 if self.almacen.revision(clave) is None]
                pendientes = list(dict.fromkeys([x["clave"] for x in persistidas] + sin_propuesta))
                if pendientes:
                    r["revisiones_pendientes"] = pendientes
                    r["aviso_revision"] = "Hay resultados discrepantes pendientes de revisión explícita; no se sobrescribieron."
                    # No emitir sobre un histórico cuya corrección ya fue
                    # detectada y está pendiente de aceptación/rechazo.
                    r.update(estado="revision_pendiente", motivo=r["aviso_revision"])
                    return r
                calendario = self.calendarios.get(codigo)
                if calendario is None or not calendario.verificado:
                    r.update(estado="calendario_no_verificado", motivo="Verifique la fuente oficial y la excepción de calendario antes de emitir.")
                    return r
                paso = "admisibilidad_temporal"
                evento = self._evento_del_objetivo(calendario, despues)
                if evento is None:
                    r.update(estado="sin_corte_admisible", motivo="No hay un último resultado válido con evento siguiente identificable.")
                    return r
                ahora = self._ahora()
                objetivo = int(despues["ultimo_sorteo"]) + 1
                r.update(objetivo=objetivo, proximo_evento=evento.instante.isoformat(),
                         fecha_objetivo=evento.fecha_local.isoformat(), fecha_limite=evento.instante.isoformat(),
                         estado_evento=clasificar(evento, ahora))
                self._guardar_paso(e, r, paso, {"objetivo": objetivo, "evento": evento.instante.isoformat(), "estado": r["estado_evento"]})
                if ahora >= evento.instante or not evento.fuente_verificada:
                    r.update(estado="resultado_retrasado", motivo="El horario del objetivo del corte cargado ya se alcanzó o no está verificado. Se bloquea la emisión, aunque el resultado aún no esté en la BD.")
                    return r
                if not admisible_emitir(calendario, evento.fecha_local, ahora):
                    r.update(estado="calendario_no_verificado", motivo="La cronología tiene una excepción sin verificar. Revise el calendario antes de emitir.")
                    return r
                ref = ((seleccion or {}).get("modelo") or {}).get("registrado")
                if not isinstance(ref, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(ref.get("clave", ""))):
                    r.update(estado="modelo_no_congelado", motivo="Elija una versión registrada compatible. La operación no entrena, selecciona ganadores ni utiliza un fallback.")
                    return r
                if self.almacen.configuracion().get("pausada", True):
                    r.update(estado="pausada", motivo="La operación se pausó antes de emitir; importación y seguimiento ya realizados se conservan.")
                    return r
                paso = "prediccion_explicada"
                generada = dep.generar(configuracion_congelada=seleccion, objetivo=objetivo,
                                       fecha_limite=evento.instante, ahora=ahora)
                self._guardar_paso(e, r, paso, generada)
                if generada.get("estado") in ("terminada", "terminado", "reutilizado", "exito", "correcto"):
                    r.update(estado="correcto", motivo=None, prediccion=generada)
                else:
                    r.update(estado="generacion_bloqueada", motivo="La predicción no se publicó; revise el bloqueo registrado.", prediccion=generada)
                return r
        except Exception as error:
            r.update(estado="fallo_consulta" if paso in ("abrir_recursos", "sincronizacion", "instantanea_inicial") else "fallo",
                     error=_error_seguro(error, paso), motivo="Falló un recurso o paso del juego. Los demás juegos continúan.")
            respuesta = getattr(error, "response", None)
            valor = (getattr(respuesta, "headers", {}) or {}).get("Retry-After")
            if isinstance(valor, str):
                if valor.isdigit():
                    r["reintentar_despues_segundos"] = min(int(valor), 31536000)
                else:
                    try:
                        fecha = parsedate_to_datetime(valor)
                        if fecha.tzinfo is not None:
                            r["reintentar_despues_segundos"] = max(0, min(31536000, int((fecha - self._ahora()).total_seconds())))
                    except (ValueError, TypeError, OverflowError):
                        pass
            return r
        finally:
            ahora = self._ahora()
            if conservar_espera:
                for campo in ("error", "fallos_consecutivos", "proxima_consulta", "reintentar_despues_segundos"):
                    if campo in previo:
                        r[campo] = previo[campo]
                r["finalizada_en"] = ahora.isoformat()
            else:
                siguiente, intentos = self._proxima_consulta(politica, r, previo, ahora, bool(r.get("error")))
                r.update(finalizada_en=ahora.isoformat(), proxima_consulta=siguiente.isoformat(), fallos_consecutivos=intentos)
                if intentos >= int(politica.get("max_reintentos", 8)):
                    r.update(estado="reintentos_agotados",
                             motivo="Se alcanzó el límite de fallos consecutivos. Revise el recurso y use Recuperar explícitamente.")
            self.almacen.guardar_estado(codigo, r)
            e["juegos"][codigo] = r
            self.almacen.guardar_ejecucion(e)

    def ciclo(self, juegos=None, forzar=False, origen="manual", programado: InvocacionProgramada | None = None):
        self._verificar_destinos()
        conf = self.almacen.configuracion()
        if programado is not None:
            if juegos is not None or forzar:
                raise ValueError("La invocación programada elige los juegos por horario; no admite juegos ni forzar.")
            return self._ciclo_programado(conf, programado)
        if origen == ORIGEN_PROGRAMADO:
            raise ValueError("El origen programado exige la invocación de la tarea con su plan.")
        if not conf.get("activada") or conf.get("pausada", True):
            return {"estado": "pausada", "juegos": {}, "motivo": "La tarea no activa la configuración operativa."}
        elegidos = list(dict.fromkeys(conf.get("juegos", JUEGOS) if juegos is None else juegos))
        if not elegidos or any(j not in JUEGOS or j not in conf.get("juegos", JUEGOS) for j in elegidos):
            raise ValueError("Juego no habilitado en la configuración operativa.")
        ahora = self._ahora()
        debidos = []
        agotados = []
        for j in elegidos:
            estado = self.almacen.estado(j)
            if int(estado.get("fallos_consecutivos", 0)) >= int(conf.get("politica", {}).get("max_reintentos", 8)):
                agotados.append(j)
                continue
            siguiente = _instante(estado.get("proxima_consulta"))
            # Forzar permite una comprobación manual anticipada, pero no
            # soslaya la espera progresiva o Retry-After de un fallo previo.
            if siguiente is None or ahora >= siguiente or (forzar and not estado.get("error")):
                debidos.append(j)
        if not debidos:
            return {"estado": "reintentos_agotados" if agotados else "sin_consultas_debidas",
                    "juegos": {}, "reintentos_agotados": agotados}
        return self._ejecutar(conf, debidos, ahora, {"origen": origen})

    def _ciclo_programado(self, conf, programado):
        """Solo los juegos habilitados cuya oportunidad de horario está abierta y su trabajo pendiente."""
        if not conf.get("activada") or conf.get("pausada", True):
            return {"estado": "pausada", "juegos": {}, "motivo": "La tarea no activa la configuración operativa."}
        try:
            politica = self._politica(conf)
        except ValueError as error:
            return {"estado": "horario_no_valido", "juegos": {}, "motivo": str(error)}
        if politica is None:
            return {"estado": "horario_no_configurado", "juegos": {},
                    "motivo": "Configuración de versión 1 sin horario: migre con `horario migrar --confirmar` y "
                              "registre la tarea con el plan resultante. No se consulta."}
        if programado.plan != horario.huella_plan(politica):
            return {"estado": "plan_divergente", "juegos": {},
                    "motivo": "La tarea se registró con otro plan de horario; actualícela con el plan vigente. No se consulta."}
        ahora = self._ahora()
        maximo = int(conf.get("politica", {}).get("max_reintentos", 8))
        decisiones = {j: horario.decidir(politica, j, ahora, self.almacen.estado(j), max_reintentos=maximo)
                      for j in conf.get("juegos", JUEGOS)}
        admitidos = sorted((j for j, d in decisiones.items() if d.admitido),
                           key=lambda j: (decisiones[j].ventana.inicio, JUEGOS.index(j)))
        motivos = {j: {"motivo": d.motivo, "detalle": d.detalle} for j, d in decisiones.items()}
        if not admitidos:
            return {"estado": "sin_consultas_debidas", "juegos": {}, "horario": motivos,
                    "reintentos_agotados": [j for j, d in decisiones.items() if d.motivo == "reintentos_agotados"]}

        def revalidar(codigo):
            # Un ciclo empezado dentro del horario no autoriza a empezar más tarde la consulta de
            # otro juego cuyo turno ya terminó: se decide de nuevo con el reloj de este momento.
            return horario.decidir(politica, codigo, self._ahora(), self.almacen.estado(codigo), max_reintentos=maximo)

        def confirmar(admitida):
            # Tras preparar el juego e inmediatamente antes de consultar al proveedor (ver `_un_juego`).
            return horario.confirmar(politica, admitida, self._ahora(), self.almacen.estado(admitida.juego),
                                     max_reintentos=maximo)
        return self._ejecutar(conf, admitidos, ahora, {"origen": ORIGEN_PROGRAMADO, "plan": programado.plan,
                                                       "horario": motivos}, revalidar=revalidar, confirmar=confirmar)

    def _ejecutar(self, conf, debidos, ahora, datos, revalidar=None, confirmar=None):
        identificador = nuevo_identificador(ahora)
        ocupados = {}
        restantes = debidos[:]
        while restantes:
            cerrojos = self.almacen.adquirir(restantes, identificador)
            if not isinstance(cerrojos, dict):
                break
            if not cerrojos:
                raise RuntimeError("El cerrojo rechazó la adquisición sin identificar recursos ocupados.")
            ocupados.update(cerrojos)
            restantes = [j for j in restantes if j not in cerrojos]
        if not restantes:
            return {"estado": "ocupado", "juegos": {}, "activas": ocupados}
        e = {"id": identificador, "estado": "en_curso", "iniciada_en": ahora.isoformat(), "finalizada_en": None,
             **datos, "juegos": {j: {"codigo": j, "estado": "pendiente", "pasos": []} for j in restantes},
             "ocupados": ocupados, "politica": deepcopy(conf.get("politica", {})), "version": 1}
        try:
            self.almacen.guardar_ejecucion(e)
            for codigo in restantes:
                decision = revalidar(codigo) if revalidar is not None else None
                if decision is not None and not decision.admitido:
                    e["juegos"][codigo] = {"codigo": codigo, "estado": "omitido_horario", "pasos": [],
                                           "motivo": decision.detalle, "horario": {"motivo": decision.motivo}}
                    self.almacen.guardar_ejecucion(e)
                    cerrojos.liberar(codigo)
                    continue
                self._un_juego(e, codigo, conf, oportunidad=decision, confirmar=confirmar)
                cerrojos.liberar(codigo)
            estados = [r["estado"] for r in e["juegos"].values() if r["estado"] != "omitido_horario"]
            e.update(estado="sin_consultas_debidas" if not estados else
                     "exito" if all(s == "correcto" for s in estados) else "parcial",
                     finalizada_en=self._ahora().isoformat())
            self.almacen.guardar_ejecucion(e)
            return e
        finally:
            cerrojos.liberar()
