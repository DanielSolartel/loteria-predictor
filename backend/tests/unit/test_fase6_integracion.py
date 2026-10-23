"""Fase 6 integrada: SQLite aislado, adquisición controlada y ML real congelado.

SQLite comprueba las transacciones/repositorios y no acredita advisory de
PostgreSQL. El proveedor nunca usa red. Markov se entrena de verdad en la
preparación y después se prohíbe ajustar en todos los consumidores.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import JSON, MetaData, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.application.exceptions import OperacionConcurrenteError
from app.application.interfaces.draw_source_connector import DrawDetail, DrawSummary
from app.application.ml import laboratorio_artefactos as la
from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import modelos_registrados as mr
from app.application.use_cases.carteras import EjecutorCarterasEnEsteProceso
from app.application.use_cases.laboratorio import EjecutorEnEsteProceso
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.color import Color, ColorNumberPair
from app.domain.value_objects.combination import Combination
from app.infrastructure.connectors.base_connector import BaseConnector
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import ColorORM, JuegoORM
from app.infrastructure.operacion_advisory import proteger_ciclo, proteger_escritura
from app.infrastructure.operacion_automatica_adaptador import AdaptadorOperacion, BloqueoOperacion
from app.infrastructure.repositories.sorteo_repository_sqlalchemy import SorteoRepositorySQLAlchemy
from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from tests.unit import fixtures_fase4 as f4
from tests.unit import fixtures_producto1 as fx
from tests.unit.test_ml_cinco_flujo import sin_entrenamiento

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")


class Reloj:
    def __init__(self, instante):
        self.instante = instante
    def __call__(self):
        return self.instante


def detalle(codigo, resultado):
    pares = getattr(resultado, "pares", ())
    return DrawDetail(str(resultado.numero_sorteo), resultado.numero_sorteo, resultado.fecha,
                      numeros=tuple(p[0] for p in pares) if pares else resultado.numeros,
                      superbalota=getattr(resultado, "superbalota", None),
                      colores=tuple(p[1] for p in pares), html_crudo="fixture pública sintética",
                      fuente_url="https://fixture.invalid/" + codigo)


class ConectorControlado:
    def __init__(self, codigo, detalles=()):
        self.game_code = codigo
        self.detalles = {d.draw_id: d for d in detalles}
        self.listados = []
        self.detalles_pedidos = []
    def fetch_draws(self, ultimo_conocido=None, max_paginas=None):
        self.listados.append((ultimo_conocido, max_paginas))
        return [DrawSummary(d.draw_id, d.numero_sorteo, d.fecha) for d in self.detalles.values()]
    def fetch_draw_detail(self, draw_id):
        self.detalles_pedidos.append(draw_id)
        return self.detalles[draw_id]


def _registrar_modelo(store, codigo, completo):
    entrada = lm.CATALOGO["markov_pares" if codigo == "COLORLOTO" else "markov_apariciones"]
    uniforme = lm.CATALOGO["uniforme_paleta" if codigo == "COLORLOTO" else "uniforme"]
    ins = lv.validar_instantanea(codigo, completo[:-5])
    protocolo = le.Protocolo(bloques=1, perfil="reducido")
    identidad = la.identidad_del_experimento(ins, [uniforme, entrada], protocolo)
    evaluacion, _ = le.evaluar(ins, [uniforme, entrada], protocolo)
    informe = la.componer(la.cuerpo_del_experimento(ins, identidad, evaluacion), "ejecucion", {})
    store.guardar_experimento(informe)
    entrenado = mr.entrenar(informe, entrada)
    cuerpo = mr.cuerpo_del_modelo(informe, entrada, mr.identidad_del_modelo(informe, entrada),
                                 {k: v for k, v in entrenado.items() if k != "contenido"})
    guardado = store.guardar_modelo(mr.componer(cuerpo, {"terminado_en": "2026-10-01T00:00:00+00:00"}),
                                    entrenado["contenido"])
    return entrada.id, guardado.identificador


def entorno(raiz, codigo="BALOTO", *, registrar=True):
    e = f4.entorno(raiz / "f", {j: 120 for j in JUEGOS})
    engine = create_engine("sqlite+pysqlite:///" + str(raiz / "datos.sqlite"), poolclass=NullPool)
    # Mismos nombres, columnas y repositorios de producción. La variante
    # JSON solo adapta el DDL del fixture a SQLite, sin tocar el esquema PG.
    meta = MetaData()
    for tabla in Base.metadata.sorted_tables:
        tabla.to_metadata(meta)
    for tabla in meta.tables.values():
        for columna in tabla.columns:
            if isinstance(columna.type, JSONB):
                columna.type = JSON()
    meta.create_all(engine)
    with Session(engine) as session:
        for j in e.juegos.listar_activos():
            session.add(JuegoORM(**asdict(j)))
        jcolor = e.juegos.obtener_por_codigo("COLORLOTO")
        for color in fx.COLORES:
            session.add(ColorORM(juego_id=jcolor.id, codigo=color, nombre=color.title(), activo=True))
        session.flush()
        repo = SorteoRepositorySQLAlchemy(session)
        for j in JUEGOS:
            entidad = e.juegos.obtener_por_codigo(j)
            for r in e.historicos[j]:
                if j == "COLORLOTO":
                    comb = Combination(pares=tuple(ColorNumberPair(n, Color(c, c.title())) for n, c in r.pares))
                else:
                    comb = Combination(numeros=r.numeros, superbalota=r.superbalota)
                repo.guardar(Sorteo(None, entidad.id, r.numero_sorteo, r.fecha, r.dia_semana, comb,
                                   "fixture_sintetica", datetime(2026, 1, 1, tzinfo=timezone.utc)))
        session.commit()
    ajustes = SimpleNamespace(database_url=str(engine.url),
        directorio_laboratorio_modelos=str(raiz / "lab"),
        directorio_carteras_modelos=str(raiz / "car"),
        directorio_predicciones_modelos=str(raiz / "pre"),
        directorio_resultados_modelos=str(raiz / "res"),
        directorio_pronosticos_experimentales=str(raiz / "pro"),
        tiempo_maximo_trabajador_carteras=90, tiempo_maximo_trabajador_laboratorio=90)
    reloj = Reloj(datetime(2026, 10, 20, 12, tzinfo=timezone.utc))
    registro = AlmacenAutomatizacion(raiz / "aut")
    conector = ConectorControlado(codigo)
    ad = AdaptadorOperacion(ajustes, registrar_revision=registro.guardar_revision,
        obtener_revision=registro.revision, registrar_decision_revision=registro.guardar_decision_revision,
        obtener_decisiones_revision=registro.decisiones_revision, reloj=reloj, engine=engine,
        obtener_conector=lambda j: conector if j == codigo else ConectorControlado(j))
    servicios = ad._servicios(codigo)
    # Motores ML reales ejecutados en el mismo proceso, para que los
    # guardianes fit cubran todas sus clases. Otro caso cubre spawn real.
    servicios[0]._ejecutor = EjecutorCarterasEnEsteProceso()
    servicios[1]._ejecutor = EjecutorEnEsteProceso()
    ad._servicios_factory = lambda j, r: servicios
    modelo = clave = None
    if registrar:
        modelo, clave = _registrar_modelo(LaboratorioFileStore(ajustes.directorio_laboratorio_modelos),
                                        codigo, e.historicos[codigo])
        servicios[0].configurar(codigo, modelo, 2, "libre", 17, registrado=clave)
    return SimpleNamespace(e=e, engine=engine, ajustes=ajustes, reloj=reloj, registro=registro,
                           conector=conector, adaptador=ad, servicios=servicios, modelo=modelo, clave=clave,
                           raiz=raiz, codigo=codigo)


@pytest.mark.parametrize("juego", JUEGOS)
def test_cuatro_juegos_novedad_resultados_siguiente_congelada_sin_ajuste(tmp_path, juego):
    t = entorno(tmp_path, juego)
    modelos_antes = f4.arbol(Path(t.ajustes.directorio_laboratorio_modelos))
    with t.adaptador.por_juego(juego) as dep, sin_entrenamiento():
        conf = dep.configuracion()
        inicial = dep.instantanea()
        previo = dep.generar(conf, inicial["ultimo_sorteo"] + 1, t.reloj() + timedelta(hours=1), t.reloj())
        assert previo["estado"] == "exito" and previo["explicacion"]["estado"] == "guardada"
        fuente = t.e.siguiente(juego)[0]
        t.conector.detalles = {str(fuente.numero_sorteo): detalle(juego, fuente)}
        arbol_emitido = {n: b for n, b in f4.arbol(t.raiz).items() if n.startswith(("car/", "pre/"))}
        sync = dep.sincronizar()
        assert sync["estado"] == "completado" and sync["nuevos"] == 1 and not sync["pendientes_revision"]
        siguiente = dep.instantanea()
        assert siguiente["ultimo_sorteo"] == inicial["ultimo_sorteo"] + 1 and siguiente["sorteos"] == inicial["sorteos"] + 1
        seguimiento = dep.reconciliar()
        assert seguimiento["estado"] == "completado" and seguimiento["emisiones"] >= 1
        vista = t.servicios[2].emisiones(juego)
        assert any(f["objetivo"] == fuente.numero_sorteo and f["estado"] == "incluido" for f in vista["filas"])
        generada = dep.generar(conf, siguiente["ultimo_sorteo"] + 1, t.reloj() + timedelta(hours=1), t.reloj())
        repetida = dep.generar(conf, siguiente["ultimo_sorteo"] + 1, t.reloj() + timedelta(hours=1), t.reloj())
        assert generada["estado"] == repetida["estado"] == "exito"
        assert generada["cartera"]["clave"] == repetida["cartera"]["clave"]
        assert repetida["explicacion"]["estado"] == "reutilizada"
        assert dep.configuracion() == conf
        assert all(f4.arbol(t.raiz)[n] == b for n, b in arbol_emitido.items())
        assert f4.arbol(Path(t.ajustes.directorio_laboratorio_modelos)) == modelos_antes
        otra = "BALOTO_REVANCHA" if juego == "BALOTO" else "BALOTO"
        with t.adaptador._abrir_lectura() as lectura:
            entidad = lectura.juego_repository.obtener_por_codigo(otra)
            assert len(lectura.resultados_repository.listar_resultados_numericos(entidad.id)) == 120
        # Consultas reales de los consumidores, sin escribir ficheros.
        antes_get = f4.arbol(t.raiz)
        t.servicios[1].consultar(juego)
        t.servicios[1].fiabilidad(juego)
        t.servicios[2].consultar(juego)
        assert f4.arbol(t.raiz) == antes_get


def test_lectura_y_prediccion_cargada_en_proceso_real(tmp_path):
    t = entorno(tmp_path)
    t.adaptador._servicios_factory = None  # ejecutores spawn reales originales
    modelos_antes = f4.arbol(Path(t.ajustes.directorio_laboratorio_modelos))
    with t.adaptador.por_juego("BALOTO") as dep:
        conf = dep.configuracion()
        r = dep.generar(conf, dep.instantanea()["ultimo_sorteo"] + 1,
                        t.reloj() + timedelta(hours=1), t.reloj())
        assert r["estado"] == "exito" and r["registrado"]["clave"] == t.clave
    assert f4.arbol(Path(t.ajustes.directorio_laboratorio_modelos)) == modelos_antes


def test_seleccion_cambia_despues_de_congelar_sin_cambiar_version_emitida(tmp_path):
    t = entorno(tmp_path)
    with t.adaptador.por_juego("BALOTO") as dep, sin_entrenamiento():
        conf = dep.configuracion()
        t.servicios[0].configurar("BALOTO", "uniforme", 3, "libre", 98)
        actual = dep.configuracion()
        r = dep.generar(conf, dep.instantanea()["ultimo_sorteo"] + 1,
                        t.reloj() + timedelta(hours=1), t.reloj())
        assert r["estado"] == "exito" and r["registrado"]["clave"] == conf["modelo"]["registrado"]["clave"]
        assert dep.configuracion() == actual and actual != conf


def test_sin_version_no_entrena_ni_usa_fallback(tmp_path):
    t = entorno(tmp_path, registrar=False)
    t.servicios[0].configurar("BALOTO", "logistica_regularizada", 2, "libre", 17, "reducido")
    with t.adaptador.por_juego("BALOTO") as dep, sin_entrenamiento():
        with pytest.raises(BloqueoOperacion, match="version registrada"):
            dep.generar(dep.configuracion(), dep.instantanea()["ultimo_sorteo"] + 1,
                        t.reloj() + timedelta(hours=1), t.reloj())
    assert not list((t.raiz / "car").rglob("carteras/*/*.json"))


@pytest.mark.parametrize("despues_de_calcular", [False, True])
def test_plazo_bloquea_antes_de_publicar_incluso_si_calculo_empezo_a_tiempo(tmp_path, monkeypatch, despues_de_calcular):
    t = entorno(tmp_path)
    limite = t.reloj() + timedelta(seconds=30)
    if despues_de_calcular:
        original = t.servicios[0]._fuente
        def fuente(*a, **kw):
            resultado = original(*a, **kw)
            t.reloj.instante = limite
            return resultado
        monkeypatch.setattr(t.servicios[0], "_fuente", fuente)
    else:
        t.reloj.instante = limite
    with t.adaptador.por_juego("BALOTO") as dep, sin_entrenamiento():
        if despues_de_calcular:
            r = dep.generar(dep.configuracion(), dep.instantanea()["ultimo_sorteo"] + 1, limite, limite - timedelta(seconds=30))
            assert r["estado"] == "fallo" and r["cartera"]["estado"] == "fallo"
        else:
            with pytest.raises(BloqueoOperacion, match="plazo"):
                dep.generar(dep.configuracion(), dep.instantanea()["ultimo_sorteo"] + 1, limite, limite)
    assert not t.servicios[0]._almacen.lineas("BALOTO")


@pytest.mark.parametrize("juego", JUEGOS)
def test_correccion_se_detecta_sin_sobrescribir_y_aceptacion_es_explicita(tmp_path, juego):
    t = entorno(tmp_path, juego)
    ultimo = t.e.historicos[juego][-1]
    if juego == "COLORLOTO":
        pares = list(ultimo.pares)
        pares[0] = (pares[0][0] % 7 + 1, pares[0][1])
        cambio = replace(ultimo, pares=tuple(pares))
    elif juego == "MILOTO":
        numeros = list(ultimo.numeros)
        numeros[0] = next(n for n in range(1, 40) if n not in numeros)
        cambio = replace(ultimo, numeros=tuple(sorted(numeros)))
    else:
        cambio = replace(ultimo, superbalota=(ultimo.superbalota % 16) + 1)
    t.conector.detalles = {str(ultimo.numero_sorteo): detalle(juego, cambio)}
    # Una emisión histórica que referencia precisamente el resultado
    # corregido: un informe vacío puede reutilizarse legítimamente porque
    # no contiene ninguna métrica afectada por la corrección.
    t.servicios[0].ahora("cartera", [juego], {"modelo": t.modelo, "registrado": t.clave,
        "perfil": "reducido", "cantidad": 2, "diversidad": "libre", "semilla": 17,
        "corte": ultimo.numero_sorteo - 1})
    with t.adaptador.por_juego(juego) as dep:
        antes = dep.instantanea()
        creacion_original = dep.sorteos.obtener_por_numero(dep.juego.id, ultimo.numero_sorteo).creado_en
        informe_viejo = dep.reconciliar()["informe_retrospectivo"]["clave"]
        r = dep.sincronizar()
        clave, = r["pendientes_revision"]
        propuesta = t.registro.revision(clave)
        bytes_primera = (t.raiz / "aut/r" / (clave + ".json")).read_bytes()
        assert dep.instantanea() == antes
        t.reloj.instante += timedelta(minutes=15)
        repetida = dep.sincronizar()
        assert repetida["pendientes_revision"] == [clave]
        assert (t.raiz / "aut/r" / (clave + ".json")).read_bytes() == bytes_primera
        decision = dep.aplicar_revision(propuesta, "Fuente oficial revisada en fixture")
        assert decision["estado"] == "aceptada"
        assert dep.instantanea()["huella"] != antes["huella"]
        informe_nuevo = dep.reconciliar()["informe_retrospectivo"]["clave"]
        assert informe_nuevo != informe_viejo
        assert any(x["clave"] == informe_viejo for x in t.servicios[2].informes(juego))
        dep.aplicar_revision(propuesta, "Fuente oficial revisada en fixture")
        assert len(t.registro.decisiones_revision(clave)) == 1
        assert not dep.sincronizar()["pendientes_revision"]
        corte_resuelto = dep.instantanea()
        assert not t.registro.revisiones_pendientes(juego, corte_resuelto["primer_sorteo"], corte_resuelto["ultimo_sorteo"])
        actual = dep.sorteos.obtener_por_numero(dep.juego.id, ultimo.numero_sorteo)
        assert actual.creado_en == creacion_original
        assert propuesta["metadatos_antes"]["fuente"] == "fixture_sintetica"
        assert t.registro.revision(clave) == propuesta


def test_revision_rechazada_conserva_propuesta_y_no_bloquea_el_mismo_hash(tmp_path):
    t = entorno(tmp_path, registrar=False)
    ultimo = t.e.historicos["BALOTO"][-1]
    t.conector.detalles = {str(ultimo.numero_sorteo): detalle("BALOTO", replace(ultimo, superbalota=(ultimo.superbalota % 16) + 1))}
    with t.adaptador.por_juego("BALOTO") as dep:
        anterior = dep.instantanea()
        clave, = dep.sincronizar()["pendientes_revision"]
        t.registro.guardar_decision_revision(clave, {"estado": "rechazada", "nota": "No aceptada en fixture"})
        repetida = dep.sincronizar()
        assert repetida["pendientes_revision"] == [] and repetida["revisiones_rechazadas"] == [clave]
        corte_resuelto = dep.instantanea()
        assert not t.registro.revisiones_pendientes("BALOTO", corte_resuelto["primer_sorteo"], corte_resuelto["ultimo_sorteo"])
        assert dep.instantanea() == anterior
        assert t.registro.revision(clave)["estado"] == "pendiente"


def test_importacion_parcial_conserva_resultado_valido_pero_no_parece_exito(tmp_path):
    t = entorno(tmp_path, registrar=False)
    primero, segundo = t.e.siguiente("BALOTO", cantidad=2)
    valido = detalle("BALOTO", primero)
    invalido = replace(detalle("BALOTO", segundo), superbalota=99)
    t.conector.detalles = {valido.draw_id: valido, invalido.draw_id: invalido}
    with t.adaptador.por_juego("BALOTO") as dep:
        r = dep.sincronizar()
        assert r["estado"] == "fallido" and r["nuevos"] == 1 and r["fallidos"] == 1
    with t.adaptador.por_juego("BALOTO") as dep:
        assert dep.instantanea()["ultimo_sorteo"] == primero.numero_sorteo


def test_resultado_de_fecha_futura_se_rechaza_sin_importarlo(tmp_path):
    t = entorno(tmp_path, registrar=False)
    r = t.e.siguiente("BALOTO")[0]
    r = replace(r, fecha=(t.reloj() + timedelta(days=1)).date())
    d = detalle("BALOTO", r);t.conector.detalles = {d.draw_id: d}
    with t.adaptador.por_juego("BALOTO") as dep:
        antes = dep.instantanea()
        assert dep.sincronizar()["estado"] == "fallido"
        assert dep.instantanea() == antes


class _HtmlMemoria:
    def guardar(self, *a):return "memoria"


class ConectorPaginas(BaseConnector):
    game_code = "BALOTO"
    def __init__(self, detalles):
        super().__init__(_HtmlMemoria(), pausa_entre_peticiones=0)
        self.detalles = {d.draw_id: d for d in detalles}
        self.paginas = []
    def _url_listado(self, pagina):return "pagina/" + str(pagina)
    def _url_detalle(self, draw_id):return "detalle/" + draw_id
    def _get(self, url):
        if url.startswith("pagina/"):self.paginas.append(int(url.split("/")[1]))
        return url
    def _parsear_pagina_listado(self, html):
        pagina = int(html.split("/")[1]);orden = sorted(self.detalles.values(), key=lambda d:d.numero_sorteo, reverse=True)
        lote = orden[(pagina-1)*3:pagina*3]
        return [DrawSummary(d.draw_id,d.numero_sorteo,d.fecha) for d in lote], pagina*3 < len(orden)
    def _parsear_pagina_detalle(self, html, draw_id, url):return self.detalles[draw_id]


def test_recuperacion_prolongada_avanza_ventanas_sin_releer_el_historico(tmp_path):
    t = entorno(tmp_path, registrar=False)
    source = [detalle("BALOTO", r) for r in t.e.siguiente("BALOTO", cantidad=20)]
    t.conector = ConectorPaginas(source)
    t.adaptador._obtener_conector = lambda codigo:t.conector
    cursor = 1
    ventanas = []
    with t.adaptador.por_juego("BALOTO") as dep:
        for i in range(3):
            t.conector.paginas = []
            r = dep.sincronizar(max_paginas=3, pagina_recuperacion=cursor)
            cursor = r["pagina_recuperacion_siguiente"]
            ventanas.append(list(t.conector.paginas))
            assert r["estado"] == "completado" and len(t.conector.paginas) <= 3
            if i < 2:assert dep.instantanea()["huecos"] > 0
        assert ventanas == [[1,2,3],[1,4,5],[1,6,7]]
        assert cursor == 1 and dep.instantanea()["sorteos"] == 140 and dep.instantanea()["huecos"] == 0


class ConexionPGControlada:
    dialect = SimpleNamespace(name="postgresql")
    def __init__(self, libre=True):self.libre=libre;self.traza=[]
    def execute(self, sentencia, params):
        self.traza.append((str(sentencia),params));return SimpleNamespace(scalar_one=lambda:self.libre)
    def commit(self):self.traza.append("commit")
    def rollback(self):self.traza.append("rollback")


def test_coordinador_pg_conserva_lock_de_sesion_tras_commits_y_libera_ante_fallo():
    conn = ConexionPGControlada()
    with pytest.raises(RuntimeError, match="fallo deliberado"):
        with proteger_ciclo(conn, "juego-fijo"):
            conn.commit()
            raise RuntimeError("fallo deliberado")
    assert "pg_try_advisory_lock" in conn.traza[0][0]
    assert conn.traza[1:4] == ["commit", "commit", "rollback"]
    assert "pg_advisory_unlock" in conn.traza[4][0] and conn.traza[-1] == "commit"


def test_coordinador_pg_rechaza_ciclo_ocupado_y_escritura_manual():
    conn = ConexionPGControlada(False)
    with pytest.raises(OperacionConcurrenteError):
        with proteger_ciclo(conn, "juego-fijo"):pytest.fail("No debería entrar al ciclo")
    assert all("unlock" not in str(x) for x in conn.traza)
    class Sesion:
        def get_bind(self):return conn
        def execute(self,*a):return conn.execute(*a)
    with pytest.raises(OperacionConcurrenteError):proteger_escritura(Sesion(),"juego-fijo")
    assert "pg_try_advisory_xact_lock" in conn.traza[-1][0]


@pytest.mark.parametrize("valor", ["7200", "Tue, 20 Oct 2026 14:00:00 GMT"])
def test_retry_after_del_detalle_detiene_consultas_y_llega_al_ciclo(tmp_path, valor):
    import requests
    from app.infrastructure.connectors.base_connector import ConectorFetchError
    from app.application.use_cases.operacion_automatica import OperacionAutomatica
    t = entorno(tmp_path, registrar=False)
    source = [detalle("BALOTO", r) for r in t.e.siguiente("BALOTO", cantidad=2)]
    t.conector.detalles = {d.draw_id: d for d in source}
    pedidos = []
    def limitado(draw_id):
        pedidos.append(draw_id)
        respuesta = requests.Response();respuesta.status_code = 429
        respuesta.headers["Retry-After"] = valor
        error = ConectorFetchError("límite controlado");error.response = respuesta
        raise error
    t.conector.fetch_draw_detail = limitado
    t.registro.actualizar_configuracion({"activada": True, "pausada": False})
    op = OperacionAutomatica(t.registro, t.adaptador, reloj=t.reloj)
    r = op.ciclo(["BALOTO"])["juegos"]["BALOTO"]
    assert len(pedidos) == 1 and r["estado"] == "fallo_consulta"
    assert r["reintentar_despues_segundos"] == 7200
    t.reloj.instante += timedelta(hours=1)
    assert op.ciclo(["BALOTO"], forzar=True)["estado"] == "sin_consultas_debidas"
    assert len(pedidos) == 1
