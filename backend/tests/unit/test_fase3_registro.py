"""Fase 3 -registro de modelos entrenados: identidad, publicacion atomica en
tres archivos, exclusividad e idempotencia entre procesos, interrupcion,
alteraciones, compatibilidad, carga restringida, rutas y contrato de
inferencia del modelo congelado. Datos sinteticos; nada es real."""
from __future__ import annotations

import builtins
import hashlib
import multiprocessing
import os
import pickle
import threading
from pathlib import Path

import numpy as np
import pytest

from app.application.interfaces.laboratorio_store import GuardadoModelo, IlegibleModelo
from app.application.ml import laboratorio_artefactos as la
from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import modelos_registrados as mr
from app.application.use_cases.laboratorio import LaboratorioError
from app.infrastructure.storage import laboratorio_file_store as modulo
from app.infrastructure.storage.laboratorio_file_store import LaboratorioFileStore
from tests.unit import fixtures_fase3 as f3
from tests.unit import fixtures_producto4 as f4

ESPERA = 120


def _informe(codigo: str, n: int, atras: int = 5, bloques: int = 2) -> dict:
    completo = f4.historico(codigo, n)
    instantanea = lv.validar_instantanea(codigo, completo[:len(completo) - atras])
    entradas = lm.candidatos_del_juego(codigo)
    protocolo = le.Protocolo(bloques=bloques, perfil="reducido")
    identidad = la.identidad_del_experimento(instantanea, entradas, protocolo)
    evaluacion, _ = le.evaluar(instantanea, entradas, protocolo)
    return la.componer(la.cuerpo_del_experimento(instantanea, identidad, evaluacion), "ejecucion", {})


def _version(informe: dict, modelo: str) -> tuple[dict, bytes]:
    entrada = lm.CATALOGO[modelo]
    entrenado = mr.entrenar(informe, entrada)
    identidad = mr.identidad_del_modelo(informe, entrada)
    cuerpo = mr.cuerpo_del_modelo(informe, entrada, identidad, {k: v for k, v in entrenado.items() if k != "contenido"})
    return mr.componer(cuerpo, {"terminado_en": "2026-10-07T01:00:00+00:00", "segundos": 0.1}), entrenado["contenido"]


@pytest.fixture(scope="module")
def baloto():
    informe = _informe("BALOTO", 110)
    return {"informe": informe, "rf": _version(informe, "random_forest_clasificador"),
            "lineal": _version(informe, "logistica_regularizada")}


@pytest.fixture(scope="module")
def colorloto():
    informe = _informe("COLORLOTO", 90)
    return {"informe": informe, "et": _version(informe, "extra_trees_poisson")}


def _sha_de_archivos(raiz: Path) -> dict:
    return {str(p.relative_to(raiz)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(raiz.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------------------
# Identidad
# ---------------------------------------------------------------------------

def test_identidad_distingue_receta_datos_entrenamiento_y_entorno(baloto, monkeypatch):
    informe = baloto["informe"]
    rf = lm.CATALOGO["random_forest_clasificador"]
    base = mr.huella(mr.identidad_del_modelo(informe, rf))
    assert base == mr.huella(mr.identidad_del_modelo(informe, rf))  # determinista
    assert base != mr.huella(mr.identidad_del_modelo(informe, lm.CATALOGO["extra_trees_clasificador"]))  # receta
    otro_corte = _informe("BALOTO", 110, atras=6)
    assert base != mr.huella(mr.identidad_del_modelo(otro_corte, rf))  # datos y corte
    predeterminado = {**informe, "identidad": {**informe["identidad"],
                                               "protocolo": {**informe["identidad"]["protocolo"],
                                                             "perfil": "predeterminado"}}}
    assert base != mr.huella(mr.identidad_del_modelo(predeterminado, rf))  # entrenamiento (perfil y parametros)
    real = la.entorno()
    monkeypatch.setattr(la, "entorno", lambda: {**real, "sistema": "OtroSistema"})
    assert base != mr.huella(mr.identidad_del_modelo(informe, rf))  # entorno


def test_la_procedencia_no_cambia_la_identidad_mismo_modelo_desde_otro_informe(baloto):
    """Dos informes con la misma instantanea y otro protocolo piden el mismo
    entrenamiento: la version se reutiliza (la procedencia no es identidad)."""
    otro = _informe("BALOTO", 110, bloques=1)
    assert otro["clave"] != baloto["informe"]["clave"]
    rf = lm.CATALOGO["random_forest_clasificador"]
    assert mr.huella(mr.identidad_del_modelo(otro, rf)) == mr.huella(mr.identidad_del_modelo(baloto["informe"], rf))


def test_solo_se_registran_modelos_con_parametros_aprendidos():
    registrables = {e.id for e in lm.CATALOGO.values() if lm.registrable(e)}
    assert registrables == {"actual_logistica_ae36", "logistica_regularizada", "hgb_clasificador",
                            "random_forest_clasificador", "extra_trees_clasificador", "poisson_regularizado",
                            "hgb_poisson", "random_forest_poisson", "extra_trees_poisson",
                            "xgboost_binario", "lightgbm_binario", "red_neuronal_binaria", "bayes_jerarquico_binario",
                            "markov_apariciones", "xgboost_poisson", "lightgbm_poisson", "red_neuronal_poisson",
                            "bayes_jerarquico_pares", "markov_pares"}
    with pytest.raises(mr.ModeloRegistradoError) as error:
        mr.entrenar(_informe("MILOTO", 87), lm.CATALOGO["actual_frecuencia_contraida"])
    assert error.value.estado == "no_registrable"


# ---------------------------------------------------------------------------
# Guardar, recargar e inferir sin reentrenar
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave_version", ["rf", "lineal"])
def test_modelo_guardado_y_recargado_reproduce_la_inferencia(tmp_path, baloto, clave_version):
    artefacto, contenido = baloto[clave_version]
    almacen = LaboratorioFileStore(tmp_path)
    guardado = almacen.guardar_modelo(artefacto, contenido)
    assert isinstance(guardado, GuardadoModelo) and guardado.numero == 1
    leido = LaboratorioFileStore(tmp_path).obtener_modelo(guardado.identificador)  # otra instancia: "reinicio"
    estimador = mr.deserializar_estimador(almacen.leer_estimador(leido), leido.artefacto["estimador"]["sha256"],
                                          leido.artefacto["estimador"]["bytes"])
    instantanea = la.instantanea_del_experimento(baloto["informe"])
    candidatos, p = mr.predecir_congelado(estimador, leido.artefacto["identidad"], instantanea)
    assert mr.control_de(candidatos, p)["sha256_probabilidades"] == leido.artefacto["control"]["sha256_probabilidades"]
    assert abs(p.sum() - 5) < 1e-9 and np.all((p > 0) & (p < 1))


def test_colorloto_guarda_su_representacion_de_pares(tmp_path, colorloto):
    artefacto, contenido = colorloto["et"]
    guardado = LaboratorioFileStore(tmp_path).guardar_modelo(artefacto, contenido)
    a = guardado.artefacto
    assert a["identidad"]["modelo"]["salida"] == "distribucion_de_pares"
    assert a["identidad"]["transformacion"]["tipo"] == "normalizacion_de_poisson"
    assert a["identidad"]["variables"]["nombres"][0] == "par"
    estimador = mr.deserializar_estimador(contenido, a["estimador"]["sha256"], a["estimador"]["bytes"])
    instantanea = la.instantanea_del_experimento(colorloto["informe"])
    candidatos, p = mr.predecir_congelado(estimador, a["identidad"], instantanea)
    assert all(isinstance(c, tuple) and len(c) == 2 for c in candidatos) and abs(p.sum() - 1) < 1e-12


def test_generar_con_una_version_cargada_no_reentrena(tmp_path, monkeypatch):
    e = f3.entorno(tmp_path)
    lab = e.laboratorio()
    r = e.registrar(lab, "MILOTO")
    assert r["estado"] == "terminado"

    def prohibido(*args, **kwargs):
        raise AssertionError("no debe reentrenar")
    monkeypatch.setattr(lm, "ajustar_candidato", prohibido)
    monkeypatch.setattr(lm, "_ajustar", prohibido)
    otro = e.laboratorio()  # proceso "reiniciado": otra instancia, mismo almacen
    g = otro.generar_con_modelo(r["modelo_registrado"])
    assert g.artefacto["identidad"]["modelo_registrado"]["clave"] == r["modelo_registrado"]
    assert g.linea == "random_forest_clasificador-v1-reg1-reducido"
    assert otro.verificar_modelo(r["modelo_registrado"])["reproduccion"]["exacta"] is True


# ---------------------------------------------------------------------------
# Idempotencia, versiones nuevas y conservacion de bytes
# ---------------------------------------------------------------------------

def test_misma_entrada_reutiliza_la_version_y_conserva_los_bytes(tmp_path):
    e = f3.entorno(tmp_path)
    lab = e.laboratorio()
    primera = e.registrar(lab, "BALOTO")
    antes = _sha_de_archivos(e.directorio / "modelos")
    segunda = lab.entrenar_ahora(primera["experimento"], f3.MODELOS["BALOTO"])["juegos"]["BALOTO"]
    assert segunda["estado"] == "reutilizado" and segunda["numero"] == 1
    assert segunda["modelo_registrado"] == primera["modelo_registrado"]
    assert _sha_de_archivos(e.directorio / "modelos") == antes


def test_cambiar_el_corte_crea_una_version_nueva_y_conserva_la_anterior(tmp_path):
    e = f3.entorno(tmp_path)
    lab = e.laboratorio()
    primera = e.registrar(lab, "BALOTO", atras=5)
    antes = _sha_de_archivos(e.directorio / "modelos")
    segunda = e.registrar(lab, "BALOTO", atras=3)
    assert segunda["estado"] == "terminado" and segunda["numero"] == 2
    assert segunda["modelo_registrado"] != primera["modelo_registrado"]
    despues = _sha_de_archivos(e.directorio / "modelos")
    assert all(despues[k] == v for k, v in antes.items())  # nada se reescribe ni se borra
    numeros = [(v["modelo"], v["numero"]) for v in lab.modelos("BALOTO")["versiones"]]
    assert numeros == [("random_forest_clasificador", 2), ("random_forest_clasificador", 1)]


def _proceso_guardar(directorio, artefacto, contenido, barrera, cola):
    try:
        barrera.wait(ESPERA)
        cola.put(("ok", LaboratorioFileStore(directorio).guardar_modelo(artefacto, contenido).numero))
    except FileExistsError:
        cola.put(("existe", None))
    except BaseException as error:  # noqa: BLE001 - se informa al proceso principal
        cola.put(("error", repr(error)))


def _en_paralelo(directorio, trabajos) -> list:
    contexto = multiprocessing.get_context("spawn")
    barrera, cola = contexto.Barrier(len(trabajos)), contexto.Queue()
    procesos = [contexto.Process(target=_proceso_guardar, args=(str(directorio), a, c, barrera, cola))
                for a, c in trabajos]
    for p in procesos:
        p.start()
    salidas = [cola.get(timeout=ESPERA) for _ in procesos]
    for p in procesos:
        p.join(ESPERA)
    return salidas


def test_publicacion_concurrente_de_la_misma_entrada_deja_una_sola_version(tmp_path, baloto):
    artefacto, contenido = baloto["rf"]
    salidas = _en_paralelo(tmp_path, [(artefacto, contenido)] * 4)
    assert sorted(s[0] for s in salidas) == ["existe", "existe", "existe", "ok"], salidas
    almacen = LaboratorioFileStore(tmp_path)
    versiones = almacen.modelos("BALOTO")
    assert len(versiones) == 1 and isinstance(versiones[0], GuardadoModelo)
    assert almacen.reservas_sin_modelo("BALOTO") == [] and almacen.huerfanos() == []


def test_publicacion_concurrente_de_entradas_distintas_da_numeros_distintos(tmp_path):
    informes = [_informe("MILOTO", 87, atras=a) for a in (3, 4, 5)]
    trabajos = [_version(i, "extra_trees_clasificador") for i in informes]
    salidas = _en_paralelo(tmp_path, trabajos)
    assert sorted(s[1] for s in salidas) == [1, 2, 3], salidas
    versiones = LaboratorioFileStore(tmp_path).modelos("MILOTO")
    assert sorted(v.numero for v in versiones) == [1, 2, 3] and len({v.identificador for v in versiones}) == 3


# ---------------------------------------------------------------------------
# Lector concurrente y proceso interrumpido
# ---------------------------------------------------------------------------

class _EscrituraPausada:
    def __init__(self, flujo, a_medias, continuar):
        self._flujo, self._a_medias, self._continuar = flujo, a_medias, continuar

    def write(self, datos):
        mitad = len(datos) // 2
        self._flujo.write(datos[:mitad])
        self._flujo.flush()
        self._a_medias.set()
        assert self._continuar.wait(ESPERA)
        return mitad + self._flujo.write(datos[mitad:])

    def __getattr__(self, nombre):
        return getattr(self._flujo, nombre)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self._flujo.__exit__(*exc)


def _proceso_manifiesto_pausado(directorio, artefacto, contenido, a_medias, continuar, cola):
    """Publica una version y se detiene a mitad de escribir el MANIFIESTO (el
    estimador y la reserva del numero ya estan en el disco)."""
    original = builtins.open

    def abrir(ruta, modo="r", *args, **kwargs):
        flujo = original(ruta, modo, *args, **kwargs)
        # el temporal del manifiesto es el que se crea en la carpeta del juego (el del estimador, en `estimadores`)
        manifiesto = "x" in modo and Path(ruta).parent.name == artefacto["juego"]
        return _EscrituraPausada(flujo, a_medias, continuar) if manifiesto else flujo

    modulo.open = abrir
    try:
        cola.put(("ok", LaboratorioFileStore(directorio).guardar_modelo(artefacto, contenido).numero))
    except BaseException as error:  # noqa: BLE001
        cola.put(("error", repr(error)))


def _escritor_pausado(directorio, artefacto, contenido):
    contexto = multiprocessing.get_context("spawn")
    a_medias, continuar, cola = contexto.Event(), contexto.Event(), contexto.Queue()
    proceso = contexto.Process(target=_proceso_manifiesto_pausado,
                               args=(str(directorio), artefacto, contenido, a_medias, continuar, cola))
    proceso.start()
    return proceso, a_medias, continuar, cola


def test_un_lector_nunca_ve_una_version_incompleta(tmp_path, baloto):
    artefacto, contenido = baloto["rf"]
    escritor, a_medias, continuar, cola = _escritor_pausado(tmp_path, artefacto, contenido)
    almacen = LaboratorioFileStore(tmp_path)
    try:
        assert a_medias.wait(ESPERA), "el escritor no llego al manifiesto"
        vistos = almacen.modelos("BALOTO")
        obtenido = almacen.obtener_modelo(artefacto["clave"])
        estimadores = list((tmp_path / "modelos" / "BALOTO" / "estimadores").glob("*.pkl"))
    finally:
        continuar.set()
        salida = cola.get(timeout=ESPERA)
        escritor.join(ESPERA)
    assert vistos == [] and obtenido is None  # el estimador ya esta, pero sin manifiesto no hay version
    assert len(estimadores) == 1
    assert salida == ("ok", 1)
    assert [v.numero for v in almacen.modelos("BALOTO")] == [1]


def test_proceso_interrumpido_no_deja_un_modelo_valido_y_se_informa(tmp_path, baloto):
    artefacto, contenido = baloto["rf"]
    escritor, a_medias, _continuar, _cola = _escritor_pausado(tmp_path, artefacto, contenido)
    try:
        assert a_medias.wait(ESPERA), "el escritor no llego al manifiesto"
    finally:  # interrupcion a mitad del manifiesto (no se despierta a un proceso muerto)
        escritor.kill()
        escritor.join(ESPERA)
    almacen = LaboratorioFileStore(tmp_path)
    assert almacen.modelos("BALOTO") == [] and almacen.obtener_modelo(artefacto["clave"]) is None
    reservas = almacen.reservas_sin_modelo("BALOTO")
    assert [(r.numero, r.estado) for r in reservas] == [(1, "sin_publicar")]
    huerfanos = almacen.huerfanos()
    assert any(h.endswith(".pkl") for h in huerfanos) and any(h.endswith(".tmp") for h in huerfanos)
    temporales = sorted(p for p in (tmp_path / "modelos" / "BALOTO").iterdir() if p.name.endswith(".tmp"))
    # reintento: publica con otro numero; el hueco y el temporal se conservan e informan
    guardado = almacen.guardar_modelo(artefacto, contenido)
    assert guardado.numero == 2
    assert [(r.numero, r.estado) for r in almacen.reservas_sin_modelo("BALOTO")] == [(1, "duplicada")]
    assert all(t.exists() for t in temporales)
    assert not any(h.endswith(".pkl") for h in almacen.huerfanos())  # el estimador ya lo cita un manifiesto


# ---------------------------------------------------------------------------
# Alteraciones, compatibilidad, carga restringida y rutas
# ---------------------------------------------------------------------------

def _guardado(tmp_path, version) -> GuardadoModelo:
    artefacto, contenido = version
    return LaboratorioFileStore(tmp_path).guardar_modelo(artefacto, contenido)


def test_estimador_alterado_o_ausente_no_se_carga(tmp_path, baloto):
    g = _guardado(tmp_path, baloto["rf"])
    objeto = tmp_path / "modelos" / "BALOTO" / "estimadores" / f"{g.artefacto['estimador']['sha256']}.pkl"
    datos = bytearray(objeto.read_bytes())
    datos[-10] ^= 0xFF
    objeto.chmod(0o644)
    objeto.write_bytes(bytes(datos))
    leido = LaboratorioFileStore(tmp_path).obtener_modelo(g.identificador)
    assert isinstance(leido, IlegibleModelo) and leido.motivo == "estimador_alterado"
    objeto.unlink()
    leido = LaboratorioFileStore(tmp_path).obtener_modelo(g.identificador)
    assert isinstance(leido, IlegibleModelo) and leido.motivo == "estimador_ausente"


def test_manifiesto_o_reserva_alterados(tmp_path, baloto):
    g = _guardado(tmp_path, baloto["rf"])
    carpeta = tmp_path / "modelos" / "BALOTO"
    reserva = carpeta / "random_forest_clasificador-000001.version"
    reserva.write_text("0" * 64 + "\n", encoding="ascii")
    assert LaboratorioFileStore(tmp_path).obtener_modelo(g.identificador).motivo == "numero_no_reservado_para_esta_clave"
    reserva.write_text(g.identificador + "\n", encoding="ascii")
    manifiesto = carpeta / f"{g.identificador}.json"
    texto = manifiesto.read_bytes().replace(b'"corte":', b'"corte" :', 1)
    manifiesto.write_bytes(texto)
    assert LaboratorioFileStore(tmp_path).obtener_modelo(g.identificador).motivo == "json_no_canonico"


def test_alterado_desde_el_caso_de_uso(tmp_path):
    e = f3.entorno(tmp_path)
    lab = e.laboratorio()
    r = e.registrar(lab, "MILOTO")
    objeto = next((e.directorio / "modelos" / "MILOTO" / "estimadores").glob("*.pkl"))
    objeto.write_bytes(objeto.read_bytes() + b"x")
    assert lab.verificar_modelo(r["modelo_registrado"])["integridad"] == "alterado"
    with pytest.raises(LaboratorioError) as error:
        lab.generar_con_modelo(r["modelo_registrado"])
    assert error.value.codigo == "alterado"
    assert lab.modelos("MILOTO")["ilegibles"][0]["motivo"] == "estimador_alterado"


def test_entorno_incompatible_no_deserializa(tmp_path, monkeypatch):
    e = f3.entorno(tmp_path)
    lab = e.laboratorio()
    r = e.registrar(lab, "MILOTO")
    real = la.entorno()
    monkeypatch.setattr(la, "entorno", lambda: {**real, "scikit-learn": "0.0.1"})
    llamadas = []
    original = mr.deserializar_estimador
    monkeypatch.setattr(mr, "deserializar_estimador", lambda *a, **k: llamadas.append(1) or original(*a, **k))
    v = lab.verificar_modelo(r["modelo_registrado"])
    assert v["compatibilidad"]["compatible"] is False and v["carga"]["estado"] == "no_intentada"
    assert any("scikit-learn" in m for m in v["compatibilidad"]["motivos"])
    with pytest.raises(LaboratorioError) as error:
        lab.generar_con_modelo(r["modelo_registrado"])
    assert error.value.codigo == "incompatible"
    assert llamadas == []
    assert lab.modelos("MILOTO")["versiones"][0]["compatible"] is False


class _Malicioso:
    def __reduce__(self):
        return (os.system, ("echo inyectado > /dev/null",))


class _NumpyLoad:
    def __reduce__(self):
        return (np.load, ("x.npy", None, True))


@pytest.mark.parametrize("objeto", [_Malicioso(), _NumpyLoad(), threading.Thread])
def test_la_carga_restringida_rechaza_nombres_no_admitidos(objeto):
    contenido = pickle.dumps(objeto, protocol=5)
    with pytest.raises(mr.ModeloRegistradoError) as error:
        mr.deserializar_estimador(contenido, mr.sha256(contenido), len(contenido))
    assert error.value.estado == "estimador_no_admitido"


def test_la_carga_comprueba_sha256_y_tamano_antes_de_deserializar(baloto, monkeypatch):
    artefacto, contenido = baloto["rf"]

    class Prohibido:
        def __init__(self, *args, **kwargs):
            raise AssertionError("no debe deserializar bytes que no coinciden con el manifiesto")
    monkeypatch.setattr(mr, "_DeserializadorRestringido", Prohibido)
    for malo, args in ((contenido + b"x", (artefacto["estimador"]["sha256"], None)),
                       (contenido, ("0" * 64, None)), (contenido, (artefacto["estimador"]["sha256"], 1))):
        with pytest.raises(mr.ModeloRegistradoError) as error:
            mr.deserializar_estimador(malo, *args)
        assert error.value.estado == "alterado"


@pytest.mark.parametrize("clave", ["../../etc/passwd", "A" * 64, "0" * 63, "", "modelos/../x"])
def test_rutas_no_validas_no_se_leen(tmp_path, clave):
    assert LaboratorioFileStore(tmp_path).obtener_modelo(clave) is None


def test_juego_no_valido_y_enlaces_simbolicos(tmp_path, baloto, monkeypatch):
    almacen = LaboratorioFileStore(tmp_path)
    with pytest.raises(ValueError):
        almacen.modelos("../BALOTO")
    g = _guardado(tmp_path, baloto["rf"])
    carpeta = tmp_path / "modelos" / "BALOTO"
    manifiesto = carpeta / f"{g.identificador}.json"
    destino = tmp_path / "fuera.json"
    destino.write_bytes(manifiesto.read_bytes())
    manifiesto.unlink()
    try:
        manifiesto.symlink_to(destino)
    except OSError:  # Windows sin permiso para crear enlaces: el almacen ve un enlace simulado (misma rama)
        manifiesto.write_bytes(destino.read_bytes())
        original = type(manifiesto).is_symlink
        monkeypatch.setattr(type(manifiesto), "is_symlink", lambda ruta: ruta == manifiesto or original(ruta))
    assert almacen.obtener_modelo(g.identificador).motivo == "nombre_o_tipo_de_archivo_no_admitido"


def test_guardar_rechaza_estimador_que_no_coincide(tmp_path, baloto):
    artefacto, contenido = baloto["rf"]
    with pytest.raises(ValueError):
        LaboratorioFileStore(tmp_path).guardar_modelo(artefacto, contenido + b"x")
    assert not (tmp_path / "modelos").exists() or not list((tmp_path / "modelos").rglob("*.json"))


# ---------------------------------------------------------------------------
# Contrato de inferencia: sin fuga temporal
# ---------------------------------------------------------------------------

def test_corte_de_entrada_anterior_al_entrenamiento_se_rechaza(baloto):
    artefacto, contenido = baloto["rf"]
    artefacto = mr.con_numero(artefacto, 1)
    estimador = mr.deserializar_estimador(contenido, artefacto["estimador"]["sha256"])
    completo = f4.historico("BALOTO", 110)
    corte = artefacto["identidad"]["corte"]
    anterior = lv.validar_instantanea("BALOTO", [r for r in completo if r.numero_sorteo < corte])
    with pytest.raises(mr.ModeloRegistradoError) as error:
        mr.cuerpo_del_pronostico_registrado(artefacto, estimador, anterior)
    assert error.value.estado == "corte_no_valido"


def test_historico_cambiado_hasta_el_corte_de_entrenamiento_se_rechaza(baloto):
    import dataclasses

    artefacto, contenido = baloto["rf"]
    artefacto = mr.con_numero(artefacto, 1)
    estimador = mr.deserializar_estimador(contenido, artefacto["estimador"]["sha256"])
    completo = list(f4.historico("BALOTO", 110))
    completo[50] = dataclasses.replace(completo[50], numeros=tuple(n for n in range(1, 44)
                                                                   if n not in completo[50].numeros)[:5])
    with pytest.raises(mr.ModeloRegistradoError) as error:
        mr.cuerpo_del_pronostico_registrado(artefacto, estimador, lv.validar_instantanea("BALOTO", completo))
    assert error.value.estado == "corte_no_valido"


def test_el_pronostico_congelado_no_usa_el_resultado_del_objetivo_ni_posteriores(baloto):
    """Las variables del objetivo C + 1 solo usan los sorteos <= C: cambiar el
    resultado del objetivo o de sorteos posteriores no cambia nada."""
    import dataclasses

    artefacto, contenido = baloto["rf"]
    artefacto = mr.con_numero(artefacto, 1)
    estimador = mr.deserializar_estimador(contenido, artefacto["estimador"]["sha256"])
    completo = list(f4.historico("BALOTO", 110))
    corte_entrada = completo[-3].numero_sorteo

    def hasta(historico):  # lo que lee el caso de uso: solo los sorteos <= corte de entrada
        return lv.validar_instantanea("BALOTO", [r for r in historico if r.numero_sorteo <= corte_entrada],
                                      corte_entrada)
    with pytest.raises(lv.HistoricoNoValidoError):  # un sorteo posterior al corte se rechaza, no se usa
        lv.validar_instantanea("BALOTO", completo, corte_entrada)
    a = mr.cuerpo_del_pronostico_registrado(artefacto, estimador, hasta(completo))
    cambiado = list(completo)
    for i in (len(completo) - 2, len(completo) - 1):  # el objetivo y el siguiente
        cambiado[i] = dataclasses.replace(cambiado[i], numeros=(1, 2, 3, 4, 5))
    b = mr.cuerpo_del_pronostico_registrado(artefacto, estimador, hasta(cambiado))
    assert a["pronostico"] == b["pronostico"] and a["clave_de_entrada"] == b["clave_de_entrada"]
    assert a["pronostico"]["objetivo"] == corte_entrada + 1 and a["pronostico"]["calculado_hasta_sorteo"] == corte_entrada
    # con un corte de entrada posterior, el estimador es el mismo pero las variables avanzan
    c = mr.cuerpo_del_pronostico_registrado(artefacto, estimador, lv.validar_instantanea("BALOTO", completo))
    assert c["identidad"]["modelo_registrado"] == a["identidad"]["modelo_registrado"]
    assert c["pronostico"]["objetivo"] == completo[-1].numero_sorteo + 1


def test_proyeccion_a_las_tablas_de_la_fase_1(baloto):
    artefacto, _ = baloto["rf"]
    proyeccion = mr.proyeccion_a_tablas(mr.con_numero(artefacto, 3))
    m = proyeccion["modelos"]
    assert m["version"] == "v3" and len(m["nombre_modelo"]) <= 60 and len(m["metodo_validacion"]) <= 50
    assert m["activo"] is None  # el vigente lo decide la configuracion de carteras
    assert all(len(x["nombre_metrica"]) <= 30 for x in proyeccion["metricas_modelo"])
    assert {"log_loss", "log_loss_uniforme", "diferencia_log_loss"} <= {x["nombre_metrica"]
                                                                        for x in proyeccion["metricas_modelo"]}


def test_la_reserva_de_una_version_alterada_no_se_presenta_como_interrumpida(tmp_path, baloto):
    g = _guardado(tmp_path, baloto["rf"])
    objeto = tmp_path / "modelos" / "BALOTO" / "estimadores" / f"{g.artefacto['estimador']['sha256']}.pkl"
    objeto.write_bytes(objeto.read_bytes() + b"x")
    almacen = LaboratorioFileStore(tmp_path)
    assert [e.motivo for e in almacen.modelos("BALOTO")] == ["estimador_alterado"]
    assert almacen.reservas_sin_modelo("BALOTO") == []  # se informa una vez, como version alterada
