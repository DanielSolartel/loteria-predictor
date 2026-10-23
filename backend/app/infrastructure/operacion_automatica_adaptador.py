"""Adaptador del ciclo Fase 6 a adquisicion y consumidores ya existentes.

No contiene un motor ML, no llama HTTP a la aplicacion y no selecciona
modelos. La construccion no abre la BD; cada juego fija una conexion para
el advisory de sesion y la unidad de trabajo de sus importaciones.
"""
from __future__ import annotations

import copy
import hashlib
from contextlib import contextmanager
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime

from app.application.exceptions import JuegoNoEncontradoError, SorteoInvalidoError
from app.application.interfaces.draw_source_connector import DrawDetail, DrawFetchError, SyncFetchResult
from app.application.mappers.draw_detail_mapper import draw_detail_a_combination
from app.application.ml import carteras_artefactos as ca
from app.application.ml import laboratorio_variables as lv
from app.application.use_cases.editar_sorteo import EditarSorteo, EditarSorteoInput
from app.application.use_cases.game_factory import GameFactory
from app.application.use_cases.laboratorio import Lectura, leer_historico
from app.application.use_cases.sincronizar_sorteos import SincronizarSorteos
from app.application.operacion_calendario import zona_bogota
from app.infrastructure.operacion_advisory import proteger_ciclo


def _ahora():
    return datetime.now(timezone.utc)


class BloqueoOperacion(Exception):
    def __init__(self, codigo: str, mensaje: str):
        self.codigo = codigo
        super().__init__(mensaje)


def _contenido(numero, fecha, combinacion):
    return {"numero_sorteo": numero, "fecha": fecha.isoformat(),
            "numeros": sorted(combinacion.numeros), "superbalota": combinacion.superbalota,
            "pares": sorted([[p.numero, p.color.codigo] for p in combinacion.pares])}


class _LoteValidado:
    """Puerto de obtencion ya consultado; la persistencia sigue en el UC."""
    def __init__(self, codigo, draws, fallidos):
        self.game_code = codigo
        self._resultado = SyncFetchResult(draws=draws, fallidos=fallidos)

    def sync(self, ultimo_conocido=None, max_paginas=None):
        return self._resultado


class DependenciasOperacion:
    def __init__(self, codigo, *, juegos, sorteos, colores, estadisticas, sincronizaciones,
                 unit_of_work, lectura, conector, carteras, predicciones, resultados,
                 registrar_revision, registrar_decision_revision=None, obtener_revision=None,
                 obtener_decisiones_revision=None, reloj=_ahora):
        self.codigo = codigo
        self.juegos, self.sorteos, self.colores = juegos, sorteos, colores
        self.estadisticas, self.sincronizaciones = estadisticas, sincronizaciones
        self.unit_of_work, self.lectura, self.conector = unit_of_work, lectura, conector
        self.carteras, self.predicciones, self.resultados = carteras, predicciones, resultados
        self.registrar_revision = registrar_revision
        self.registrar_decision_revision = registrar_decision_revision
        self.obtener_revision = obtener_revision
        self.obtener_decisiones_revision = obtener_decisiones_revision
        self.reloj = reloj
        self.juego = juegos.obtener_por_codigo(codigo)
        if self.juego is None:
            raise JuegoNoEncontradoError(codigo)
        self.game_factory = GameFactory(color_repository=colores)

    def instantanea(self):
        completo = list(leer_historico(self.lectura, self.codigo))
        if not completo:
            return {"ultimo_sorteo": None, "primer_sorteo": None, "fecha": None, "sorteos": 0, "huella": None, "huecos": 0}
        ins = lv.validar_instantanea(self.codigo, completo)
        canonicos = lv.sorteos_canonicos(ins)
        return {"ultimo_sorteo": ins.corte,
                "primer_sorteo": ins.sorteos[0].numero_sorteo,
                "fecha": max(completo, key=lambda r: r.numero_sorteo).fecha.isoformat(),
                "sorteos": len(completo), "huella": ca.huella(canonicos),
                "huecos": ins.corte - ins.sorteos[0].numero_sorteo + 1 - len(ins.sorteos)}

    def configuracion(self):
        guardada = self.carteras.configuracion_vigente(self.codigo)
        return None if guardada is None else copy.deepcopy(guardada.artefacto)

    def _validar_draw(self, resumen, draw):
        if (draw.draw_id != resumen.draw_id or draw.numero_sorteo != resumen.numero_sorteo
                or draw.fecha != resumen.fecha or not isinstance(draw.fecha, date)
                or isinstance(draw.fecha, datetime) or type(resumen.numero_sorteo) is not int
                or not isinstance(draw.numero_sorteo, int)
                or isinstance(draw.numero_sorteo, bool) or draw.numero_sorteo <= 0):
            raise ValueError("Identidad, numeracion o fecha de detalle no coincide con el listado")
        if draw.fecha > self.reloj().astimezone(zona_bogota()).date():
            raise ValueError("Un resultado observado no puede pertenecer a una fecha futura")
        colores = {c.codigo: c for c in self.colores.listar_vigentes(self.juego.id)} if self.juego.tiene_color else {}
        combinacion = draw_detail_a_combination(draw, self.juego, colores)
        valido = self.game_factory.crear(self.juego).validate_draw(combinacion)
        if not valido:
            raise SorteoInvalidoError(valido.errors)
        return combinacion

    def sincronizar(self, max_paginas=3, reconciliar_ultimos=12, pagina_recuperacion=1):
        if type(max_paginas) is not int or not 1 <= max_paginas <= 10 or \
                type(reconciliar_ultimos) is not int or not 0 <= reconciliar_ultimos <= 100 or \
                type(pagina_recuperacion) is not int or pagina_recuperacion < 1:
            raise ValueError("Consulta acotada: 1..10 paginas, 0..100 revisiones y cursor positivo")
        if self.conector.game_code != self.codigo:
            raise ValueError("El conector no corresponde al juego pedido")
        # Solo se enumeran paginas recientes limitadas; se descargan detalles
        # nuevos y, como maximo, el prefijo de reconciliacion explicitado.
        antes_ciclo = self.instantanea()
        if pagina_recuperacion > 1:
            if max_paginas < 2 or not callable(getattr(self.conector, "fetch_draws_desde", None)):
                raise BloqueoOperacion("recuperacion_no_disponible", "El conector o el presupuesto no permite continuar la ventana histórica")
            frente = self.conector.fetch_draws(ultimo_conocido=None, max_paginas=1)
            historicos = self.conector.fetch_draws_desde(pagina_recuperacion, max_paginas=max_paginas - 1)
            resumenes = [*frente, *historicos]
            leidas = getattr(self.conector, "_ultimas_paginas_leidas", max_paginas - 1)
            proxima_pagina = pagina_recuperacion + leidas
        else:
            resumenes = self.conector.fetch_draws(ultimo_conocido=None, max_paginas=max_paginas)
            proxima_pagina = 1 + getattr(self.conector, "_ultimas_paginas_leidas", max_paginas)
        if not getattr(self.conector, "_hay_mas_paginas", True):
            proxima_pagina = 1
        nuevos, errores, revisiones = [], [], []
        rechazadas = []
        espera_proveedor = 0
        if not resumenes:
            errores.append(DrawFetchError("listado", None, "El listado no contiene resultados reconocibles"))
        vistos = {}; revisados = 0
        for resumen in sorted(resumenes, key=lambda x: x.numero_sorteo, reverse=True):
            # Recuperar huecos del tramo disponible no amplía silenciosamente
            # hacia un histórico anterior al corte inicial del operador.
            if antes_ciclo["primer_sorteo"] is not None and resumen.numero_sorteo < antes_ciclo["primer_sorteo"]:
                continue
            identidad = (resumen.draw_id, resumen.fecha)
            if resumen.numero_sorteo in vistos:
                if vistos[resumen.numero_sorteo] != identidad:
                    errores.append(DrawFetchError(resumen.draw_id, resumen.numero_sorteo,
                                                  "Listado con identidades contradictorias"))
                continue
            vistos[resumen.numero_sorteo] = identidad
            existente = self.sorteos.obtener_por_numero(self.juego.id, resumen.numero_sorteo)
            if existente is not None:
                if revisados >= reconciliar_ultimos:
                    continue
                revisados += 1
            try:
                draw = self.conector.fetch_draw_detail(resumen.draw_id)
                combinacion = self._validar_draw(resumen, draw)
                if existente is None:
                    nuevos.append(draw)
                    continue
                antes = _contenido(existente.numero_sorteo, existente.fecha, existente.resultado)
                propuesta = _contenido(draw.numero_sorteo, draw.fecha, combinacion)
                if antes != propuesta:
                    identidad_revision = {"juego": self.codigo, "numero_sorteo": draw.numero_sorteo,
                                          "antes": antes, "propuesta": propuesta}
                    clave = ca.huella(identidad_revision)
                    revision = {"clave": clave, **identidad_revision, "estado": "pendiente",
                                "huellas": {"antes": ca.huella(antes), "propuesta": ca.huella(propuesta),
                                            "html": hashlib.sha256(draw.html_crudo.encode("utf-8")).hexdigest()},
                                "fuente_url": draw.fuente_url, "detectada_en": self.reloj().isoformat(),
                                "metadatos_antes": {"fuente": existente.fuente,
                                                    "creado_en": str(existente.creado_en)}}
                    previa = self.obtener_revision(clave) if self.obtener_revision else None
                    if previa is None:
                        self.registrar_revision(revision)
                    elif any(previa.get(k) != identidad_revision[k] for k in identidad_revision):
                        raise ValueError("La revisión guardada no corresponde con la identidad observada")
                    # Conservar la primera evidencia y su fecha. Consultas
                    # posteriores no reescriben metadatos de una propuesta.
                    decisiones = self.obtener_decisiones_revision(clave) if self.obtener_decisiones_revision else []
                    if (decisiones and not decisiones[0].get("orden_ambiguo")
                            and decisiones[0].get("decision", {}).get("estado") == "rechazada"):
                        rechazadas.append(clave)
                    else:
                        revisiones.append(clave)
            except Exception as error:
                # No guardar mensajes de red/BD que puedan contener secretos.
                errores.append(DrawFetchError(resumen.draw_id, resumen.numero_sorteo,
                                              "Detalle no disponible o invalido: " + type(error).__name__))
                respuesta = getattr(error, "response", None)
                valor = (getattr(respuesta, "headers", {}) or {}).get("Retry-After")
                if isinstance(valor, str):
                    try:
                        espera_proveedor = max(0, min(31536000, int(valor) if valor.isdigit() else
                            int((parsedate_to_datetime(valor) - self.reloj()).total_seconds())))
                    except (ValueError, TypeError, OverflowError):
                        pass
                    # No continuar solicitando detalles tras el límite del
                    # proveedor. Los resultados ya validados se conservan.
                    break
        lote = _LoteValidado(self.codigo, sorted(nuevos, key=lambda d: d.numero_sorteo), errores)
        caso = SincronizarSorteos(self.juegos, self.sorteos, self.sincronizaciones, self.colores,
                                  self.game_factory, lambda codigo: lote, self.unit_of_work, self.estadisticas)
        reporte = caso.ejecutar(self.codigo, max_paginas=max_paginas)
        e = reporte.ejecucion
        despues_ciclo = self.instantanea()
        if despues_ciclo["huecos"] == 0:
            proxima_pagina = 1
        return {"estado": "fallido" if e.sorteos_fallidos else e.estado, "nuevos": e.sorteos_nuevos, "observados": len(resumenes),
                "fallidos": e.sorteos_fallidos, "pendientes_revision": revisiones,
                "reintentar_despues_segundos": espera_proveedor,
                "revisiones_rechazadas": rechazadas, "huecos": despues_ciclo["huecos"],
                "pagina_recuperacion_siguiente": proxima_pagina,
                "reconciliados": revisados, "max_paginas": max_paginas,
                "ejecucion_sincronizacion": str(e.id)}

    def reconciliar(self):
        from app.application.use_cases.resultados import Filtros
        vista = self.resultados.consultar(self.codigo, completa=True)
        if vista["base"]["estado"] != "consultada":
            raise BloqueoOperacion("base_no_disponible", "No se pudo consultar la base para reconciliar")
        informe = self.resultados.guardar_informe(self.codigo, origen="fase6_automatica")
        retrospectiva = self.resultados.consultar(self.codigo, Filtros(tipo="retrospectiva"), completa=True)
        informe_retrospectivo = None
        if retrospectiva["historial"]["total"]:
            informe_retrospectivo = self.resultados.guardar_informe(
                self.codigo, Filtros(tipo="retrospectiva"), origen="fase6_reconciliacion_retrospectiva")
        return {"estado": "completado", "informe": informe,
                "informe_retrospectivo": informe_retrospectivo,
                "ultimo_sorteo": vista["base"]["ultimo_sorteo"],
                "emisiones": vista["historial"]["total"]}

    def generar(self, configuracion_congelada, objetivo, fecha_limite, ahora):
        conf = copy.deepcopy(configuracion_congelada or {})
        registrado = conf.get("modelo", {}).get("registrado")
        if not registrado:
            raise BloqueoOperacion("version_congelada_requerida",
                                    "Seleccione explicitamente una version registrada compatible; no se reajustan recetas")
        if conf.get("juego") != self.codigo or not ca.integro(conf):
            raise BloqueoOperacion("configuracion_alterada", "La seleccion congelada no es integra")
        if fecha_limite.tzinfo is None or ahora.tzinfo is None:
            raise ValueError("El plazo requiere fecha/hora con zona")

        def guardia():
            if self.reloj() >= fecha_limite:
                raise BloqueoOperacion("fuera_de_plazo", "El evento objetivo ya alcanzo su plazo operativo")
            actual = self.instantanea()
            if actual["huecos"]:
                raise BloqueoOperacion("historico_incompleto", "Recupere los huecos de numeración antes de emitir automáticamente")
            if actual["ultimo_sorteo"] is None or actual["ultimo_sorteo"] + 1 != objetivo:
                raise BloqueoOperacion("objetivo_cambio", "La base ya conoce el objetivo o cambio durante la operacion")

        if ahora >= fecha_limite:
            raise BloqueoOperacion("fuera_de_plazo", "No se emite despues del plazo del evento")
        guardia()
        # El caso de uso valida la version/receta exacta y la referencia; no
        # se lee otra seleccion vigente ni se sustituye un modelo ausente.
        inicio = self.predicciones.iniciar(self.codigo, origen="fase6_automatica",
                                           configuracion_congelada=conf, guardia_publicacion=guardia)
        final = self.predicciones.ejecutar(inicio)
        p = final["prediccion"]
        return {"estado": p["estado"], "ejecucion": p["id"], "objetivo": objetivo,
                "cartera": p["cartera"], "explicacion": p["explicacion"],
                "configuracion": {"version": conf["version"], "linea": conf["linea"]},
                "registrado": copy.deepcopy(registrado)}

    def aplicar_revision(self, revision, nota):
        if not isinstance(nota, str) or not nota.strip() or len(nota) > 1000:
            raise ValueError("La aceptacion requiere una nota explicita de hasta 1000 caracteres")
        if self.registrar_decision_revision is None:
            raise RuntimeError("Falta el almacen de decisiones; no se inicia una aceptacion")
        if revision.get("juego") != self.codigo or revision.get("estado") != "pendiente":
            raise ValueError("Revision pendiente de otro juego o invalida")
        n = revision["numero_sorteo"]
        identidad = {k: revision[k] for k in ("juego", "numero_sorteo", "antes", "propuesta")}
        if ca.huella(identidad) != revision["clave"]:
            raise ValueError("Revision con identidad alterada")
        existente = self.sorteos.obtener_por_numero(self.juego.id, n)
        if existente is None:
            raise BloqueoOperacion("revision_conflicto", "El sorteo que se iba a revisar ya no existe")
        actual = _contenido(n, existente.fecha, existente.resultado)
        if actual not in (revision["antes"], revision["propuesta"]):
            raise BloqueoOperacion("revision_conflicto", "El resultado actual difiere de la evidencia revisada")
        recuperada = actual == revision["propuesta"]
        anteriores = self.obtener_decisiones_revision(revision["clave"]) if self.obtener_decisiones_revision else []
        vigente = anteriores[0].get("decision", {}) if anteriores and not anteriores[0].get("orden_ambiguo") else {}
        if (recuperada and vigente.get("estado") == "aceptada"
                and vigente.get("nota") == nota.strip()
                and vigente.get("propuesta_sha256") == ca.huella(revision["propuesta"])):
            return {"clave": revision["clave"], "estado": "aceptada", "recuperada_tras_commit": True, "reutilizada": True}
        if not recuperada:
            p = revision["propuesta"]
            pares = p.get("pares", [])
            draw = DrawDetail(str(n), n, date.fromisoformat(p["fecha"]),
                              numeros=tuple(x[0] for x in pares) if pares else tuple(p["numeros"]),
                              superbalota=p["superbalota"], colores=tuple(x[1] for x in pares))
            colores = {c.codigo: c for c in self.colores.listar_vigentes(self.juego.id)} if self.juego.tiene_color else {}
            combinacion = draw_detail_a_combination(draw, self.juego, colores)
            caso = EditarSorteo(self.juegos, self.sorteos, self.game_factory, self.estadisticas)
            caso.ejecutar(EditarSorteoInput(existente.id, draw.fecha, combinacion,
                                          fuente="revision_fase6:" + revision["clave"]))
            self.unit_of_work.confirmar()
        decision = {"estado": "aceptada", "nota": nota.strip(), "en": self.reloj().isoformat(),
                    "recuperada_tras_commit": recuperada, "propuesta_sha256": ca.huella(revision["propuesta"])}
        self.registrar_decision_revision(revision["clave"], decision)
        return {"clave": revision["clave"], "estado": "aceptada", "recuperada_tras_commit": recuperada}


class AdaptadorOperacion:
    def __init__(self, ajustes, *, registrar_revision, obtener_revision=None,
                 registrar_decision_revision=None, obtener_decisiones_revision=None, reloj=_ahora, engine=None,
                 obtener_conector=None, servicios_factory=None):
        self.ajustes, self.reloj = ajustes, reloj
        self.registrar_revision, self.obtener_revision = registrar_revision, obtener_revision
        self.registrar_decision_revision = registrar_decision_revision
        self.obtener_decisiones_revision = obtener_decisiones_revision
        self._engine, self._obtener_conector = engine, obtener_conector
        self._servicios_factory = servicios_factory

    def _servicios(self, codigo):
        if self._servicios_factory is not None:
            return self._servicios_factory(codigo, self.reloj)
        from app.application.use_cases.carteras import CarterasDeModelos
        from app.application.use_cases.predicciones import CentroDePredicciones
        from app.application.use_cases.resultados import CentroDeResultados
        from app.infrastructure.carteras_trabajador import EjecutorCarterasEnProceso
        from app.infrastructure.laboratorio_trabajador import EjecutorEnProceso
        from app.infrastructure.storage.carteras_file_store import CarterasFileStore
        from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
        from app.infrastructure.storage.operacion_file_store import CerrojoPorJuego, RegistroEjecucionesArchivo
        from app.infrastructure.storage.predicciones_file_store import PrediccionesFileStore
        from app.infrastructure.storage.pronostico_experimental_file_store import PronosticoExperimentalFileStore
        from app.infrastructure.storage.resultados_file_store import ResultadosFileStore
        a = self.ajustes
        cartera_store = CarterasFileStore(a.directorio_carteras_modelos)
        modelos = LaboratorioFileStore(a.directorio_laboratorio_modelos)
        op = str(cartera_store.directorio / "operacion")
        carteras = CarterasDeModelos(cartera_store, RegistroEjecucionesArchivo(op), CerrojoPorJuego(op),
                                    self._abrir_lectura, ejecutor=EjecutorCarterasEnProceso(a.tiempo_maximo_trabajador_carteras),
                                    modelos=modelos, reloj=self.reloj)
        resultados = CentroDeResultados(PronosticoExperimentalFileStore(a.directorio_pronosticos_experimentales),
                                         modelos, cartera_store, ResultadosFileStore(a.directorio_resultados_modelos),
                                         self._abrir_lectura, carteras_servicio=lambda: carteras, reloj=self.reloj)
        op_p = str(a.directorio_predicciones_modelos) + "/operacion"
        predicciones = CentroDePredicciones(carteras, resultados, PrediccionesFileStore(a.directorio_predicciones_modelos),
                                            modelos, EjecutorEnProceso(tiempo_maximo=a.tiempo_maximo_trabajador_laboratorio),
                                            RegistroEjecucionesArchivo(op_p), cerrojo=CerrojoPorJuego(op_p), reloj=self.reloj)
        return carteras, predicciones, resultados

    def _motor(self):
        if self._engine is None:
            from sqlalchemy import create_engine
            # El DSN ya fue cotejado por la configuración explícita del
            # ejecutor. No reutilizar un singleton importado bajo otro cwd.
            self._engine = create_engine(self.ajustes.database_url, pool_pre_ping=True, future=True)
        return self._engine

    @contextmanager
    def _abrir_lectura(self):
        from sqlalchemy import text
        from sqlalchemy.orm import Session
        from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
        from app.infrastructure.repositories.resultados_historicos_repository_sqlalchemy import ResultadosHistoricosRepositorySQLAlchemy
        with Session(self._motor(), autoflush=False) as session:
            if session.get_bind().dialect.name == "postgresql":
                session.execute(text("SET TRANSACTION READ ONLY"))
            try:
                yield Lectura(JuegoRepositorySQLAlchemy(session), ResultadosHistoricosRepositorySQLAlchemy(session))
            finally:
                session.rollback()

    @contextmanager
    def por_juego(self, codigo):
        from sqlalchemy.orm import Session
        from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
        from app.infrastructure.repositories.juego_repository_sqlalchemy import JuegoRepositorySQLAlchemy
        from app.infrastructure.repositories.sorteo_repository_sqlalchemy import SorteoRepositorySQLAlchemy
        from app.infrastructure.repositories.color_repository_sqlalchemy import ColorRepositorySQLAlchemy
        from app.infrastructure.repositories.estadistica_repository_sqlalchemy import EstadisticaRepositorySQLAlchemy
        from app.infrastructure.repositories.sincronizacion_repository_sqlalchemy import SincronizacionRepositorySQLAlchemy
        from app.infrastructure.repositories.resultados_historicos_repository_sqlalchemy import ResultadosHistoricosRepositorySQLAlchemy
        if self._obtener_conector is None:
            from app.infrastructure.connectors.registry import ConnectorRegistry
            from app.infrastructure.storage.html_file_storage import HtmlFileStorage
            self._obtener_conector = ConnectorRegistry(HtmlFileStorage()).obtener
        with self._motor().connect() as conexion:
            with Session(bind=conexion, autoflush=False, expire_on_commit=False) as session:
                juegos = JuegoRepositorySQLAlchemy(session)
                juego = juegos.obtener_por_codigo(codigo)
                if juego is None:
                    raise JuegoNoEncontradoError(codigo)
                session.rollback()
                with proteger_ciclo(conexion, juego.id):
                    carteras, predicciones, resultados = self._servicios(codigo)
                    try:
                        yield DependenciasOperacion(codigo, juegos=juegos,
                            sorteos=SorteoRepositorySQLAlchemy(session), colores=ColorRepositorySQLAlchemy(session),
                            estadisticas=EstadisticaRepositorySQLAlchemy(session),
                            sincronizaciones=SincronizacionRepositorySQLAlchemy(session), unit_of_work=SqlAlchemyUnitOfWork(session),
                            lectura=Lectura(juegos, ResultadosHistoricosRepositorySQLAlchemy(session)),
                            conector=self._obtener_conector(codigo), carteras=carteras, predicciones=predicciones,
                            resultados=resultados, registrar_revision=self.registrar_revision,
                            registrar_decision_revision=self.registrar_decision_revision,
                            obtener_revision=self.obtener_revision,
                            obtener_decisiones_revision=self.obtener_decisiones_revision, reloj=self.reloj)
                    finally:
                        session.rollback()

    def aplicar_revision(self, clave, nota):
        if self.obtener_revision is None or self.registrar_decision_revision is None:
            raise RuntimeError("El almacen de revisiones/decisiones no esta configurado")
        revision = self.obtener_revision(clave)
        if revision is None:
            raise ValueError("No existe esa revision")
        with self.por_juego(revision["juego"]) as dep:
            return dep.aplicar_revision(revision, nota)
