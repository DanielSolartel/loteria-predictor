"""Fase 6: invariantes del ciclo con adquisición/modelos simulados.

Se usan calendario, registro, cerrojos y procesos reales. Este módulo no
acredita ajuste o inferencia ML: el adaptador de producto tiene su integración
con estimadores registrados en una batería independiente.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
import hashlib
import json
import multiprocessing
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.unit.fixtures_tiempo_fase6 import fijar_marca

from app.application.operacion_calendario import ExcepcionCalendario, calendario_defecto
from app.application.use_cases.operacion_automatica import JUEGOS, OperacionAutomatica
from app.infrastructure.storage.automatizacion_file_store import AlmacenAutomatizacion

AHORA = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
ID_AUSENTE = "20261019T120000Z-abcdef12"
ANTERIORES = {"BALOTO": "2026-10-14", "BALOTO_REVANCHA": "2026-10-14",
              "MILOTO": "2026-10-15", "COLORLOTO": "2026-10-12"}
ULTIMAS = {"BALOTO": "2026-10-17", "BALOTO_REVANCHA": "2026-10-17",
           "MILOTO": "2026-10-16", "COLORLOTO": "2026-10-15"}


class Reloj:
    def __init__(self, ahora=AHORA):
        self.ahora = ahora

    def __call__(self):
        return self.ahora


class ConsultaFallida(RuntimeError):
    def __init__(self, retry_after=None):
        super().__init__("postgresql://usuario:SECRETO_NO_PUBLICAR@localhost/base")
        self.response = SimpleNamespace(status_code=503,
                                        headers={} if retry_after is None else {"Retry-After": retry_after})


class AdaptadorControlado:
    """Proveedor y predicción simulados; deja ficheros sintéticos inmutables."""
    def __init__(self, directorio, *, errores=None, hook=None, seleccion=True):
        self.directorio = Path(directorio)
        self.errores = errores or {}
        self.hook = hook
        self.llamadas = []
        self.generaciones = []
        self.paginas = []
        self.huecos_actuales = {}
        self.siguiente_pagina = {}
        self.selecciones = {j: {"juego": j, "modelo": {"id": "simulado",
                               "registrado": {"clave": "a" * 64, "numero": 1}}, "cantidad": 2}
                            if seleccion else None for j in JUEGOS}
        self.pendientes_revision = []

    def _paso(self, juego, paso):
        self.llamadas.append((juego, paso))
        if self.hook:
            self.hook(juego, paso, self)
        error = self.errores.get((juego, paso))
        if error:
            raise error

    @contextmanager
    def por_juego(self, juego):
        self._paso(juego, "abrir")
        yield DependenciaControlada(self, juego)

    def datos(self, juego):
        p = self.directorio / "datos" / (juego + ".json")
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {"ultimo_sorteo": 100, "fecha": ANTERIORES[juego], "sorteos": 100}


class DependenciaControlada:
    def __init__(self, adaptador, juego):
        self.a, self.juego = adaptador, juego

    def instantanea(self):
        self.a._paso(self.juego, "instantanea")
        return {**self.a.datos(self.juego), "huecos": self.a.huecos_actuales.get(self.juego, 0)}

    def configuracion(self):
        self.a._paso(self.juego, "configuracion")
        # Devuelve la referencia mutable deliberadamente: el caso de uso
        # debe congelar su propio contenido antes de llamar al proveedor.
        return self.a.selecciones[self.juego]

    def sincronizar(self, max_paginas, reconciliar_ultimos, pagina_recuperacion=1):
        assert max_paginas <= 10 and reconciliar_ultimos <= 100
        self.a.paginas.append((self.juego, pagina_recuperacion))
        self.a._paso(self.juego, "sincronizar")
        p = self.a.directorio / "datos" / (self.juego + ".json")
        previo = self.a.datos(self.juego)
        nuevo = {"ultimo_sorteo": 101, "fecha": ULTIMAS[self.juego], "sorteos": 101}
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("xb") as f:
                f.write(json.dumps(nuevo, sort_keys=True).encode("utf-8"))
        return {"estado": "completado", "nuevos": int(previo != nuevo),
                "pendientes_revision": self.a.pendientes_revision,
                "pagina_recuperacion_siguiente": self.a.siguiente_pagina.get(self.juego, 1)}

    def reconciliar(self):
        self.a._paso(self.juego, "reconciliar")
        return {"estado": "correcto", "juego": self.juego, "observado": 101,
                "procedencia": "simulada_control_de_ciclo"}

    def generar(self, configuracion_congelada, objetivo, fecha_limite, ahora):
        self.a._paso(self.juego, "generar")
        assert ahora < fecha_limite
        contenido = {"juego": self.juego, "objetivo": objetivo,
                     "configuracion": deepcopy(configuracion_congelada),
                     "fuente": "simulada_no_ML"}
        raw = json.dumps(contenido, sort_keys=True).encode("utf-8")
        clave = hashlib.sha256(raw).hexdigest()
        p = self.a.directorio / "artefactos" / (clave + ".json")
        reutilizado = p.exists()
        if not reutilizado:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        else:
            assert p.read_bytes() == raw
        self.a.generaciones.append(contenido)
        return {"estado": "reutilizado" if reutilizado else "terminado", "clave": clave,
                "cartera": clave, "explicacion": clave, "reutilizado": reutilizado}


def _crear(tmp_path, *, reloj=None, adaptador=None, calendarios=None):
    a = AlmacenAutomatizacion(tmp_path / "operacion")
    a.guardar_configuracion({"activada": True, "pausada": False})
    d = adaptador or AdaptadorControlado(tmp_path / "recursos")
    return OperacionAutomatica(a, d, reloj=reloj or Reloj(), calendarios=calendarios), a, d


def _bytes(directorio):
    return {p.relative_to(directorio).as_posix(): p.read_bytes()
            for p in directorio.rglob("*") if p.is_file()}


def test_cuatro_juegos_importan_asocian_y_reutilizan_sin_duplicar(tmp_path):
    op, almacen, adaptador = _crear(tmp_path)
    primera = op.ciclo()
    assert primera["estado"] == "exito" and set(primera["juegos"]) == set(JUEGOS)
    for j, r in primera["juegos"].items():
        assert r["estado"] == "correcto" and r["ultimo_sorteo"] == 101 and r["objetivo"] == 102
        assert r["configuracion_modelo"]["juego"] == j
        assert [p["paso"] for p in r["pasos"]] == [
            "instantanea_inicial", "congelar_configuracion", "sincronizacion",
            "resultados_fiabilidad", "admisibilidad_temporal", "prediccion_explicada"]
        assert r["pasos"][3]["resultado"]["juego"] == j
        assert almacen.estado(j)["prediccion"]["clave"] == r["prediccion"]["clave"]
    assert len(adaptador.generaciones) == 4
    originales = _bytes(adaptador.directorio)
    segunda = op.ciclo(forzar=True)
    assert segunda["id"] != primera["id"] and segunda["estado"] == "exito"
    assert all(x["prediccion"]["reutilizado"] for x in segunda["juegos"].values())
    assert _bytes(adaptador.directorio) == originales
    assert len(almacen.recientes()) == 2


@pytest.mark.parametrize("paso", ["abrir", "sincronizar"])
def test_fallo_bd_o_red_no_oculta_los_otros_juegos_ni_expone_secretos(tmp_path, paso):
    d = AdaptadorControlado(tmp_path / "recursos", errores={("BALOTO", paso): ConsultaFallida()})
    op, a, _ = _crear(tmp_path, adaptador=d)
    e = op.ciclo()
    assert e["estado"] == "parcial" and e["juegos"]["BALOTO"]["estado"] == "fallo_consulta"
    assert all(e["juegos"][j]["estado"] == "correcto" for j in JUEGOS if j != "BALOTO")
    assert not any(x["juego"] == "BALOTO" for x in d.generaciones)
    assert "SECRETO_NO_PUBLICAR" not in json.dumps(a.recientes())
    assert "SECRETO_NO_PUBLICAR" not in json.dumps(a.estado("BALOTO"))


def test_cambio_de_seleccion_durante_consulta_no_cambia_version_del_ciclo(tmp_path):
    def cambiar(j, paso, d):
        if paso == "sincronizar":
            d.selecciones[j]["modelo"]["registrado"] = {"clave": "b" * 64, "numero": 2}
    d = AdaptadorControlado(tmp_path / "recursos", hook=cambiar)
    op, _, _ = _crear(tmp_path, adaptador=d)
    e = op.ciclo(["BALOTO"])
    r = e["juegos"]["BALOTO"]
    assert d.selecciones["BALOTO"]["modelo"]["registrado"]["clave"] == "b" * 64
    assert r["configuracion_modelo"]["modelo"]["registrado"]["clave"] == "a" * 64
    assert d.generaciones[0]["configuracion"]["modelo"]["registrado"]["numero"] == 1


@pytest.mark.parametrize("seleccion", [None, {"modelo": {"id": "receta_entrenable"}},
                                       {"modelo": {"registrado": {"clave": "alterado"}}}])
def test_sin_version_congelada_se_importa_y_compara_pero_no_se_genera(tmp_path, seleccion):
    op, _, d = _crear(tmp_path)
    d.selecciones["MILOTO"] = seleccion
    r = op.ciclo(["MILOTO"])["juegos"]["MILOTO"]
    assert r["estado"] == "modelo_no_congelado" and r["motivo"]
    assert ("MILOTO", "sincronizar") in d.llamadas and ("MILOTO", "reconciliar") in d.llamadas
    assert ("MILOTO", "generar") not in d.llamadas and not d.generaciones


@pytest.mark.parametrize("juego", JUEGOS)
def test_base_atrasada_no_reasigna_el_objetivo_antiguo_a_un_evento_futuro(tmp_path, juego):
    # Todos los eventos siguientes al corte local ya pasaron, pero el
    # proveedor aún no entrega el resultado. No basta ausencia en la BD.
    reloj = Reloj(datetime(2026, 10, 23, 12, tzinfo=timezone.utc))
    op, _, d = _crear(tmp_path, reloj=reloj)
    r = op.ciclo([juego])["juegos"][juego]
    assert r["estado"] == "resultado_retrasado" and r["objetivo"] == 102
    assert r["fecha_objetivo"] == "2026-10-19"
    assert datetime.fromisoformat(r["fecha_limite"]) < reloj.ahora
    assert r["estado_evento"] == "horario_alcanzado_sin_confirmar"
    assert not d.generaciones


@pytest.mark.parametrize("desplazamiento,admitido", [(-1, True), (0, False), (1, False)])
def test_instante_de_inicio_del_evento_cierra_la_emision_automatica(tmp_path, desplazamiento, admitido):
    # Baloto del lunes 19 comienza a las 23:00 Bogotá = martes04:00UTC.
    reloj = Reloj(datetime(2026, 10, 20, 4, tzinfo=timezone.utc) + timedelta(seconds=desplazamiento))
    op, _, d = _crear(tmp_path, reloj=reloj)
    r = op.ciclo(["BALOTO"])["juegos"]["BALOTO"]
    assert bool(d.generaciones) is admitido
    assert r["objetivo"] == 102 and r["fecha_objetivo"] == "2026-10-19"
    assert (r["estado"] == "correcto") is admitido


def test_pausa_entre_importar_y_emitir_conserva_datos_y_seguimiento(tmp_path):
    a = AlmacenAutomatizacion(tmp_path / "operacion")
    def pausar(j, paso, d):
        if paso == "reconciliar":
            a.actualizar_configuracion({"pausada": True})
    d = AdaptadorControlado(tmp_path / "recursos", hook=pausar)
    op, _, _ = _crear(tmp_path, adaptador=d)
    r = op.ciclo(["COLORLOTO"])["juegos"]["COLORLOTO"]
    assert r["estado"] == "pausada" and r["ultimo_sorteo"] == 101
    assert (d.directorio / "datos/COLORLOTO.json").exists()
    assert ("COLORLOTO", "reconciliar") in d.llamadas and not d.generaciones
    antes = _bytes(tmp_path)
    assert op.ciclo()["estado"] == "pausada"
    assert _bytes(tmp_path) == antes


@pytest.mark.parametrize("cabecera", ["1800", "fecha_http"])
def test_retry_after_respeta_espera_aunque_se_pida_forzar(tmp_path, cabecera):
    reloj = Reloj()
    valor = format_datetime(reloj.ahora + timedelta(minutes=30), usegmt=True) if cabecera == "fecha_http" else cabecera
    d = AdaptadorControlado(tmp_path / "recursos", errores={("BALOTO", "sincronizar"): ConsultaFallida(valor)})
    op, a, _ = _crear(tmp_path, reloj=reloj, adaptador=d)
    r = op.ciclo(["BALOTO"])["juegos"]["BALOTO"]
    assert datetime.fromisoformat(r["proxima_consulta"]) >= reloj.ahora + timedelta(minutes=30)
    n = len(d.llamadas)
    assert op.ciclo(["BALOTO"], forzar=True)["estado"] == "sin_consultas_debidas"
    assert len(d.llamadas) == n and len(a.recientes()) == 1


def test_espera_progresiva_acotada_y_recuperacion_sin_esperar_tiempo_real(tmp_path):
    reloj = Reloj()
    d = AdaptadorControlado(tmp_path / "recursos", errores={("BALOTO", "sincronizar"): ConsultaFallida()})
    op, _, _ = _crear(tmp_path, reloj=reloj, adaptador=d)
    esperas = []
    for _ in range(6):
        r = op.ciclo(["BALOTO"])["juegos"]["BALOTO"]
        siguiente = datetime.fromisoformat(r["proxima_consulta"])
        esperas.append(int((siguiente - reloj.ahora).total_seconds()))
        reloj.ahora = siguiente
    assert esperas == [300, 600, 1200, 2400, 3600, 3600]
    d.errores.clear()
    r = op.ciclo(["BALOTO"])["juegos"]["BALOTO"]
    assert r["estado"] == "correcto" and r["fallos_consecutivos"] == 0


def test_error_posterior_conserva_ultimo_resultado_y_ultima_actualizacion_visibles(tmp_path):
    op, a, d = _crear(tmp_path)
    correcto = op.ciclo(["BALOTO"])["juegos"]["BALOTO"]
    d.errores[("BALOTO", "sincronizar")] = ConsultaFallida()
    fallido = op.ciclo(["BALOTO"], forzar=True)["juegos"]["BALOTO"]
    assert fallido["estado"] == "fallo_consulta"
    assert fallido["ultimo_sorteo"] == correcto["ultimo_sorteo"]
    assert fallido["ultima_actualizacion"] == correcto["ultima_actualizacion"]
    assert a.estado("BALOTO")["ultimo_sorteo"] == 101


def test_revision_detectada_no_reescribe_ni_emite_sobre_ella(tmp_path):
    op, _, d = _crear(tmp_path)
    d.pendientes_revision = ["f" * 64]
    r = op.ciclo(["BALOTO"])["juegos"]["BALOTO"]
    assert r["estado"] == "revision_pendiente" and r["motivo"]
    assert ("BALOTO", "reconciliar") in d.llamadas and not d.generaciones


def test_recuperacion_paginada_persiste_cursor_y_no_emite_hasta_cerrar_huecos(tmp_path):
    def atraso(j, paso, d):
        if paso == "sincronizar":
            d.huecos_actuales[j] = 2
            d.siguiente_pagina[j] = 4
    d = AdaptadorControlado(tmp_path / "recursos", hook=atraso)
    op, a, _ = _crear(tmp_path, adaptador=d)
    r = op.ciclo(["BALOTO"])["juegos"]["BALOTO"]
    assert r["estado"] == "historico_incompleto" and not d.generaciones
    assert d.paginas == [("BALOTO", 1)] and a.estado("BALOTO")["pagina_recuperacion"] == 4
    # Otro proceso/instancia debe tomar la página persistida, no reiniciar la
    # recuperación en las mismas tres páginas frontales. El puerto informa
    # que los huecos se cerraron; este test no simula adquisición HTTP real.
    d2 = AdaptadorControlado(tmp_path / "recursos")
    op2 = OperacionAutomatica(AlmacenAutomatizacion(a.directorio), d2, reloj=Reloj())
    r2 = op2.ciclo(["BALOTO"], forzar=True)["juegos"]["BALOTO"]
    assert d2.paginas == [("BALOTO", 4)] and r2["pagina_recuperacion"] == 1
    assert r2["estado"] == "correcto" and len(d2.generaciones) == 1


def test_cancelacion_no_verificada_no_autoriza_saltar_al_siguiente_evento(tmp_path):
    calendarios = calendario_defecto()
    calendarios["BALOTO"] = replace(calendarios["BALOTO"], excepciones=(
        ExcepcionCalendario(date(2026, 10, 19), motivo="Cancelación pendiente de verificar",
                            fuente_url="https://example.invalid/cambio-controlado", verificada=False),))
    op, _, d = _crear(tmp_path, calendarios=calendarios)
    r = op.ciclo(["BALOTO"])["juegos"]["BALOTO"]
    assert r["estado"] != "correcto" and r["motivo"]
    assert not d.generaciones


def test_lecturas_panel_y_ejecucion_no_inicializan_almacenes(tmp_path):
    destino = tmp_path / "no_creado"
    a = AlmacenAutomatizacion(destino)
    d = AdaptadorControlado(tmp_path / "recursos_ausentes")
    op = OperacionAutomatica(a, d, reloj=Reloj())
    assert op.panel()["estado"] == "pausada"
    assert op.consultar_ejecucion(ID_AUSENTE) is None
    assert not destino.exists() and not d.directorio.exists() and not d.llamadas


def _ejecutar_bloqueado(ruta, listo, continuar, cola, bloquear_en):
    base = Path(ruta)
    def bloquear(j, paso, d):
        if j == "BALOTO" and paso == bloquear_en:
            listo.set()
            assert continuar.wait(30)
    a = AlmacenAutomatizacion(base / "operacion")
    d = AdaptadorControlado(base / "recursos", hook=bloquear)
    resultado = OperacionAutomatica(a, d, reloj=Reloj()).ciclo(["BALOTO"])
    cola.put(resultado["juegos"]["BALOTO"]["estado"])


def _cerrar(p, continuar):
    # No volver a tocar un semáforo del proceso que terminó por SIGTERM:
    # una interrupción puede dejar su condición adquirida. Solo el proceso
    # vivo recibe el aviso cooperante; después se espera/termina lo propio.
    if p.is_alive():
        continuar.set()
    p.join(10)
    if p.is_alive():
        p.terminate()
        p.join(10)


def test_dos_procesos_no_duplican_un_juego_y_otro_juego_puede_continuar(tmp_path):
    op, a, _ = _crear(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    listo, continuar, cola = ctx.Event(), ctx.Event(), ctx.Queue()
    p = ctx.Process(target=_ejecutar_bloqueado, args=(str(tmp_path), listo, continuar, cola, "sincronizar"))
    try:
        p.start()
        assert listo.wait(15)
        primero, = a.recientes()
        assert a.viva(primero["id"])
        segundo = op.ciclo(["BALOTO", "MILOTO"], forzar=True)
        assert segundo["estado"] == "exito" and set(segundo["juegos"]) == {"MILOTO"}
        assert segundo["ocupados"] == {"BALOTO": primero["id"]}
        continuar.set()
        p.join(15)
        assert p.exitcode == 0 and cola.get(timeout=5) == "correcto"
        artefactos = [json.loads(q.read_text(encoding="utf-8")) for q in (tmp_path / "recursos/artefactos").glob("*.json")]
        assert sorted(x["juego"] for x in artefactos) == ["BALOTO", "MILOTO"]
    finally:
        _cerrar(p, continuar)


def test_interrupcion_real_preserva_importacion_y_se_recupera_sin_reescribirla(tmp_path):
    op, a, _ = _crear(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    listo, continuar, cola = ctx.Event(), ctx.Event(), ctx.Queue()
    p = ctx.Process(target=_ejecutar_bloqueado, args=(str(tmp_path), listo, continuar, cola, "reconciliar"))
    try:
        p.start()
        assert listo.wait(15)
        e, = a.recientes()
        importado = tmp_path / "recursos/datos/BALOTO.json"
        bytes_importados = importado.read_bytes()
        registro = deepcopy(a.obtener_ejecucion(e["id"]))
        p.terminate()
        p.join(10)
        assert not p.is_alive() and not a.viva(e["id"])
        assert op.consultar_ejecucion(e["id"])["estado"] == "interrumpida"
        assert a.obtener_ejecucion(e["id"]) == registro
        assert op.recuperar()["interrumpidas_marcadas"] == [e["id"]]
        recuperada = a.obtener_ejecucion(e["id"])
        assert recuperada["estado"] == "interrumpida"
        assert recuperada["juegos"]["BALOTO"]["estado"] == "interrumpido"
        assert importado.read_bytes() == bytes_importados
        repetida = op.ciclo(["BALOTO"], forzar=True)
        assert repetida["juegos"]["BALOTO"]["estado"] == "correcto"
        assert importado.read_bytes() == bytes_importados
        assert len(list((tmp_path / "recursos/artefactos").glob("*.json"))) == 1
    finally:
        _cerrar(p, continuar)


def test_reintentos_tienen_limite_y_recuperacion_explicita_sin_consultas(tmp_path):
    reloj = Reloj()
    d = AdaptadorControlado(tmp_path / "recursos", errores={("BALOTO", "sincronizar"): ConsultaFallida()})
    op, a, _ = _crear(tmp_path, reloj=reloj, adaptador=d)
    a.actualizar_configuracion({"politica": {"max_reintentos": 2}})
    assert op.ciclo(["BALOTO"])["juegos"]["BALOTO"]["fallos_consecutivos"] == 1
    reloj.ahora += timedelta(hours=2)
    assert op.ciclo(["BALOTO"])["juegos"]["BALOTO"]["estado"] == "reintentos_agotados"
    reloj.ahora += timedelta(days=1)
    antes = list(d.llamadas)
    assert op.ciclo(["BALOTO"], forzar=True)["estado"] == "reintentos_agotados"
    assert d.llamadas == antes
    assert op.recuperar()["reintentos_rearmados"] == ["BALOTO"]
    assert d.llamadas == antes  # recuperar no consulta fuentes ni genera
    d.errores.clear()
    assert op.ciclo(["BALOTO"])["juegos"]["BALOTO"]["fallos_consecutivos"] == 0


def test_recuperar_no_rearma_reintentos_de_juego_ocupado(tmp_path):
    op, a, d = _crear(tmp_path)
    a.guardar_estado("BALOTO", {"estado": "reintentos_agotados", "fallos_consecutivos": 8})
    lease = a.adquirir(["BALOTO"], ID_AUSENTE)
    try:
        antes = a.estado("BALOTO")
        assert op.recuperar()["reintentos_rearmados"] == []
        assert a.estado("BALOTO") == antes and not d.llamadas
    finally:
        lease.liberar()


@pytest.mark.parametrize("estado_decision", [None, "aceptada", "rechazada"])
def test_panel_solo_muestra_revisiones_sin_decision_y_conserva_su_evidencia(tmp_path, estado_decision):
    import os

    op, almacen, adaptador = _crear(tmp_path)
    clave = "b" * 64
    propuesta = {"clave": clave, "juego": "BALOTO", "numero_sorteo": 101,
                 "antes": {"numeros": [1, 2, 3, 4, 5]},
                 "propuesta": {"numeros": [2, 3, 4, 5, 6]},
                 "huellas": {"antes": "a" * 64, "propuesta": "c" * 64},
                 "estado": "pendiente"}
    almacen.guardar_revision(propuesta)
    decisiones = []
    if estado_decision is not None:
        # Una decisión posterior prevalece para la proyección, conservando
        # tanto la propuesta original como todas las decisiones anteriores.
        for i, estado in enumerate(("rechazada" if estado_decision == "aceptada" else "aceptada",
                                    estado_decision), start=1):
            d = almacen.guardar_decision_revision(clave, {"estado": estado, "nota": "revisión " + str(i),
                "en": "2026-10-19T12:0" + str(i) + ":00+00:00"})
            fijar_marca(almacen.directorio / "d" / (d["clave"] + ".json"), i)
        decisiones = almacen.decisiones_revision(clave)
    antes = {p.relative_to(almacen.directorio).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
             for p in almacen.directorio.rglob("*") if p.is_file()}
    panel = op.panel()
    assert panel["revisiones"] == ([propuesta] if estado_decision is None else [])
    assert panel["historial_revisiones"] == [{"revision": propuesta, "decisiones": decisiones}]
    if estado_decision is not None:
        assert panel["historial_revisiones"][0]["decisiones"][0]["decision"]["estado"] == estado_decision
    assert op.panel() == panel
    assert {p.relative_to(almacen.directorio).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in almacen.directorio.rglob("*") if p.is_file()} == antes
    assert almacen.revision(clave) == propuesta and propuesta["estado"] == "pendiente"
    assert not adaptador.llamadas and not adaptador.directorio.exists()


def _cierre_entre_lectura_y_vida(almacen, monkeypatch, estado_final):
    """Publica el cierre y suelta el cerrojo tras devolver la copia vieja."""
    lease = almacen.adquirir(["BALOTO"], ID_AUSENTE)
    assert not isinstance(lease, dict)
    en_curso = {"id": ID_AUSENTE, "estado": "en_curso", "iniciada_en": AHORA.isoformat(),
                "juegos": {"BALOTO": {"estado": "correcto", "pasos": [{"paso": "publicado"}]}}}
    terminado = {**en_curso, "estado": estado_final, "finalizada_en": AHORA.isoformat()}
    almacen.guardar_ejecucion(en_curso)
    obtener = almacen.obtener_ejecucion
    pendiente = True

    def leer(identificador):
        nonlocal pendiente
        instantanea = obtener(identificador)
        if pendiente:
            pendiente = False
            almacen.guardar_ejecucion(terminado)
            lease.liberar()
        return instantanea

    monkeypatch.setattr(almacen, "obtener_ejecucion", leer)
    return lease, obtener, terminado


@pytest.mark.parametrize("estado_final", ["exito", "parcial"])
def test_consultar_con_cierre_entre_lectura_y_vida_no_inventa_interrupcion(tmp_path, monkeypatch, estado_final):
    op, almacen, adaptador = _crear(tmp_path)
    lease, obtener, terminado = _cierre_entre_lectura_y_vida(almacen, monkeypatch, estado_final)
    try:
        observado = op.consultar_ejecucion(ID_AUSENTE)
        assert observado["estado"] in ("en_curso", estado_final)
        assert obtener(ID_AUSENTE) == terminado
        assert not adaptador.llamadas
    finally:
        lease.liberar()


@pytest.mark.parametrize("estado_final", ["exito", "parcial"])
def test_recuperar_durante_cierre_conserva_resultado_y_pasos_publicados(tmp_path, monkeypatch, estado_final):
    op, almacen, adaptador = _crear(tmp_path)
    lease, obtener, terminado = _cierre_entre_lectura_y_vida(almacen, monkeypatch, estado_final)
    try:
        assert op.recuperar()["interrumpidas_marcadas"] == []
        assert obtener(ID_AUSENTE) == terminado
        assert not adaptador.llamadas
    finally:
        lease.liberar()


def test_dos_recuperaciones_revalidan_bajo_recurso_y_solo_una_publica(tmp_path, monkeypatch):
    # Un registro sin lease representa un trabajador muerto. La primera
    # recuperación retiene el recurso real hasta que la segunda ha intentado
    # adquirirlo; no se usan sleeps ni ordenaciones basadas en tiempo.
    op, primero, adaptador = _crear(tmp_path)
    segundo = AlmacenAutomatizacion(primero.directorio)
    otro = OperacionAutomatica(segundo, object(), reloj=Reloj(AHORA + timedelta(minutes=1)))
    primero.guardar_ejecucion({"id": ID_AUSENTE, "estado": "en_curso",
        "iniciada_en": AHORA.isoformat(), "juegos": {"BALOTO": {"estado": "en_curso", "pasos": ["importado"]}}})
    escribiendo, segundo_intenta = threading.Event(), threading.Event()
    guardar, recurso = primero._registro.guardar, segundo._recurso
    escrituras = []

    def guardar_controlado(registro):
        escrituras.append(deepcopy(registro))
        escribiendo.set()
        assert segundo_intenta.wait(10), "La segunda recuperación no alcanzó el recurso"
        return guardar(registro)

    @contextmanager
    def recurso_controlado(nombre):
        if nombre == "ejecucion:" + ID_AUSENTE:
            segundo_intenta.set()
        with recurso(nombre):
            yield

    monkeypatch.setattr(primero._registro, "guardar", guardar_controlado)
    monkeypatch.setattr(segundo, "_recurso", recurso_controlado)
    resultados, errores = [], []

    def ejecutar(servicio):
        try:
            resultados.append(servicio.recuperar())
        except BaseException as error:
            errores.append(error)

    uno = threading.Thread(target=ejecutar, args=(op,))
    dos = threading.Thread(target=ejecutar, args=(otro,))
    uno.start()
    try:
        assert escribiendo.wait(10), "La primera recuperación no alcanzó la publicación"
        dos.start()
    finally:
        # Desbloquear también ante una aserción fallida del propio arnés.
        if dos.ident is None:
            segundo_intenta.set()
        uno.join(15)
        if dos.ident is not None:
            dos.join(15)
    assert not uno.is_alive() and not dos.is_alive()
    assert not errores
    assert len(escrituras) == 1
    assert sorted(len(r["interrumpidas_marcadas"]) for r in resultados) == [0, 1]
    final = primero.obtener_ejecucion(ID_AUSENTE)
    assert final == escrituras[0]
    assert final["estado"] == "interrumpida"
    assert final["juegos"]["BALOTO"]["pasos"] == ["importado"]
    assert final["juegos"]["BALOTO"]["estado"] == "interrumpido"
    assert not adaptador.llamadas


def test_recuperar_revalida_proyeccion_obsoleta_tras_cierre_publicado(tmp_path, monkeypatch):
    op, almacen, adaptador = _crear(tmp_path)
    lease = almacen.adquirir(["BALOTO"], ID_AUSENTE)
    assert not isinstance(lease, dict)
    abierto = {"id": ID_AUSENTE, "estado": "en_curso", "iniciada_en": AHORA.isoformat(),
               "juegos": {"BALOTO": {"estado": "correcto", "pasos": ["publicado"]}}}
    terminado = {**abierto, "estado": "exito", "finalizada_en": AHORA.isoformat()}
    almacen.guardar_ejecucion(abierto)

    def candidata_obsoleta(identificador):
        assert identificador == ID_AUSENTE
        # Inyecta exclusivamente la proyección obsoleta que motivó la
        # auditoría. El cierre y la liberación son reales, en ese orden.
        # Recuperar debe revalidarla, aunque su lector entregue esa copia.
        almacen.guardar_ejecucion(terminado)
        lease.liberar()
        return {**abierto, "estado": "interrumpida"}

    monkeypatch.setattr(op, "consultar_ejecucion", candidata_obsoleta)
    try:
        assert op.recuperar()["interrumpidas_marcadas"] == []
        assert almacen.obtener_ejecucion(ID_AUSENTE) == terminado
        assert not adaptador.llamadas
    finally:
        lease.liberar()


def test_panel_proyecta_interrupcion_persistida_sobre_estado_juego_obsoleto(tmp_path):
    almacen=AlmacenAutomatizacion(tmp_path/'operacion')
    almacen.guardar_estado('BALOTO',{'estado':'en_curso','ejecucion':ID_AUSENTE,'pasos':['importado']})
    almacen.guardar_ejecucion({'id':ID_AUSENTE,'estado':'en_curso','iniciada_en':AHORA.isoformat(),
        'juegos':{'BALOTO':{'codigo':'BALOTO','estado':'en_curso','pasos':['importado']}}})
    servicio=OperacionAutomatica(almacen,object(),reloj=lambda:AHORA)
    assert servicio.recuperar()['interrumpidas_marcadas']==[ID_AUSENTE]
    evidencia={p.relative_to(almacen.directorio).as_posix():(p.read_bytes(),p.stat().st_mtime_ns)
               for p in almacen.directorio.rglob('*') if p.is_file()}
    juego=next(j for j in servicio.panel()['juegos'] if j['codigo']=='BALOTO')
    assert juego['estado']=='interrumpido'
    assert juego['ejecucion']==ID_AUSENTE and juego['pasos']==['importado']
    assert {p.relative_to(almacen.directorio).as_posix():(p.read_bytes(),p.stat().st_mtime_ns)
            for p in almacen.directorio.rglob('*') if p.is_file()}==evidencia


def test_panel_no_reaviva_interrupcion_anterior_a_un_cierre_correcto(tmp_path):
    almacen=AlmacenAutomatizacion(tmp_path/'operacion')
    servicio=OperacionAutomatica(almacen,object(),reloj=lambda:AHORA)
    almacen.guardar_ejecucion({'id':ID_AUSENTE,'estado':'en_curso','iniciada_en':AHORA.isoformat(),
        'juegos':{'BALOTO':{'codigo':'BALOTO','estado':'en_curso','pasos':['anterior']}}})
    # Esta intercalación es la misma que antes de persistir Recuperar; el
    # cierre nuevo debe prevalecer al proyectar las ejecuciones recientes.
    almacen.guardar_estado('BALOTO',{'estado':'correcto','ejecucion':"20261019T120100Z-12345679",'pasos':['nuevo publicado']})
    almacen.guardar_ejecucion({'id':"20261019T120100Z-12345679",'estado':'exito','iniciada_en':AHORA.isoformat(),
        'juegos':{'BALOTO':{'codigo':'BALOTO','estado':'correcto','pasos':['nuevo publicado']}}})
    juego=next(j for j in servicio.panel()['juegos'] if j['codigo']=='BALOTO')
    assert juego['estado']=='correcto'
    assert juego['ejecucion']=="20261019T120100Z-12345679" and juego['pasos']==['nuevo publicado']
