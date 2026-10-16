"""Fase 4 - caso de uso comun `GenerarPredicciones` (centro de predicciones):
generacion para los cuatro juegos con el flujo de Producto 5, lectura pura,
respeto de la configuracion y de la version registrada, sin fuga de
informacion y fiabilidad por linea. Datos sinteticos; nada es real."""
from __future__ import annotations

import dataclasses
import json

import pytest

from app.application.ml import laboratorio_artefactos as la
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import predicciones_explicacion as pe
from app.application.use_cases.predicciones import PrediccionesError
from tests.unit import fixtures_fase4 as f4


@pytest.fixture
def entorno(tmp_path):
    e = f4.entorno(tmp_path)
    yield e
    f4.limpiar()


def _reemplazar_posteriores(e, juego, despues_de, semilla):
    """Cambia los numeros de los sorteos cargados posteriores a `despues_de`
    (mismos numeros de sorteo y fechas; otro contenido)."""
    j = e.juegos.obtener_por_codigo(juego)
    destino = e.resultados.colorloto if juego == "COLORLOTO" else e.resultados.numericos
    viejos = [r for r in destino[j.id] if r.numero_sorteo > despues_de]
    nuevos = f4.f3.f4.historico(juego, len(viejos), semilla=semilla)
    cambio = {v.numero_sorteo: dataclasses.replace(n, numero_sorteo=v.numero_sorteo, fecha=v.fecha)
              for v, n in zip(viejos, nuevos)}
    destino[j.id] = [cambio.get(r.numero_sorteo, r) for r in destino[j.id]]


# ---------------------------------------------------------------------------
# Generar con el flujo de Producto 5
# ---------------------------------------------------------------------------

def test_genera_y_explica_para_los_cuatro_juegos_con_su_configuracion(entorno):
    modelos = {"BALOTO": "logistica_regularizada", "BALOTO_REVANCHA": "uniforme", "MILOTO": "random_forest_clasificador",
               "COLORLOTO": "uniforme_paleta"}
    for juego, modelo in modelos.items():
        entorno.configurar(juego, modelo, cantidad=2)
    centro = entorno.centro()
    for juego, modelo in modelos.items():
        r = centro.ahora(juego)
        p = r["prediccion"]
        assert p["estado"] == "exito" and p["cartera"]["estado"] == "terminado", p
        assert p["explicacion"]["estado"] == "guardada" and p["solicitud"]["combinaciones"] == 2
        d = centro.consultar(juego)["prediccion"]
        assert d["clave"] == p["cartera"]["clave"] and d["de_la_configuracion"] and d["modelo"]["id"] == modelo
        assert d["explicacion"]["clave"] == p["explicacion"]["clave"] and d["reproduccion"]["exacta"]
        assert len(d["combinaciones"]) == 2 and d["proyeccion"]["columnas"]["nivel_confianza"] is None
    indice = centro.indice()
    assert [j["juego"] for j in indice["juegos"]] == list(modelos)
    assert all(j["ultima"]["explicacion"] for j in indice["juegos"])


def test_equivale_a_la_cartera_configurada_de_producto_5(entorno):
    """Misma configuracion -> misma entrada: el centro reutiliza la cartera que
    genero la operacion de Producto 5, y su contenido es el mismo archivo."""
    entorno.configurar("MILOTO", "logistica_regularizada", cantidad=3)
    carteras = entorno.carteras()
    directa = carteras.ahora("carteras_configuradas", ["MILOTO"])["juegos"]["MILOTO"]
    assert directa["estado"] == "terminado"
    centro = entorno.centro(carteras)
    r = centro.ahora("MILOTO")["juegos"]["MILOTO"]
    assert r["estado"] == "reutilizado" and r["resultado"] == directa["resultado"]
    assert carteras.cartera(r["resultado"]).artefacto == carteras.cartera(directa["resultado"]).artefacto


def test_cinco_combinaciones_no_cambia_la_configuracion(entorno):
    entorno.configurar("MILOTO", "logistica_regularizada", cantidad=3)
    carteras = entorno.carteras()
    antes = carteras.configuracion_vigente("MILOTO")
    centro = entorno.centro(carteras)
    r = centro.ahora("MILOTO", "cinco")
    p = r["prediccion"]
    assert p["estado"] == "exito" and p["solicitud"]["combinaciones"] == 5
    cartera = carteras.cartera(p["cartera"]["clave"]).artefacto
    assert len(cartera["cartera"]["combinaciones"]) == 5 and cartera["linea"]["id"].endswith("-n5-libre-s42-reducido")
    despues = carteras.configuracion_vigente("MILOTO")
    assert despues.identificador == antes.identificador and despues.artefacto == antes.artefacto
    assert len(carteras.configuraciones("MILOTO")) == 1
    d = centro.consultar("MILOTO", p["cartera"]["clave"])["prediccion"]
    assert d["peticion_de_cinco"] and not d["de_la_configuracion"]
    with pytest.raises(PrediccionesError) as error:
        centro.iniciar("MILOTO", "siete")
    assert error.value.codigo == "no_valido"


def test_no_cambia_de_modelo_aunque_otro_gane_una_comparacion(entorno):
    entorno.configurar("MILOTO", "uniforme", cantidad=2)
    lab = entorno.laboratorio()
    lab.comparar_ahora(["MILOTO"], f4.f3.PROTOCOLO, corte=entorno.corte("MILOTO"))
    centro = entorno.centro()
    p = centro.ahora("MILOTO")["prediccion"]
    assert centro.consultar("MILOTO")["prediccion"]["modelo"]["id"] == "uniforme"
    assert p["cartera"]["linea"].startswith("uniforme-v")


def test_version_registrada_se_recarga_sin_reentrenar(entorno, monkeypatch):
    lab = entorno.laboratorio()
    r = entorno.registrar(lab, "BALOTO", "random_forest_clasificador")
    entorno.configurar("BALOTO", "random_forest_clasificador", registrado=r["modelo_registrado"])

    def prohibido(*args, **kwargs):
        raise AssertionError("una version registrada no se reentrena")
    monkeypatch.setattr(lm, "ajustar_candidato", prohibido)
    centro = entorno.centro()
    p = centro.ahora("BALOTO")["prediccion"]
    assert p["estado"] == "exito", p
    d = centro.consultar("BALOTO")["prediccion"]
    assert d["linea_del_artefacto"]["registrado"]["clave"] == r["modelo_registrado"]
    assert d["explicacion"]["importancias"]["estado"] == "disponible"
    assert d["explicacion"]["metodo"]["registrado"]["corte_de_entrenamiento"] == entorno.corte("BALOTO")
    assert d["enlaces"]["modelo_registrado"] == f"/laboratorio/modelo/{r['modelo_registrado']}"


def test_version_registrada_incompatible_no_genera_y_se_muestra(entorno, monkeypatch):
    lab = entorno.laboratorio()
    r = entorno.registrar(lab, "MILOTO", "random_forest_clasificador")
    entorno.configurar("MILOTO", "random_forest_clasificador", registrado=r["modelo_registrado"])
    centro = entorno.centro()
    centro.ahora("MILOTO")
    real = la.entorno()
    monkeypatch.setattr(la, "entorno", lambda: {**real, "scikit-learn": "0.1"})
    with pytest.raises(PrediccionesError) as error:
        centro.iniciar("MILOTO")
    assert error.value.codigo == "incompatible"
    vista = centro.consultar("MILOTO")
    assert vista["registrado"]["estado"] == "incompatible" and vista["registrado"]["motivos"]
    assert vista["prediccion"] is not None  # lo ya generado se sigue consultando
    # Explicar de nuevo en este entorno: no se carga el estimador; se dice por que.
    centro._almacen = f4.PrediccionesFileStore(entorno.raiz / "otro")
    e = centro.explicar(vista["prediccion"]["clave"])
    assert e["importancias"] == "no_disponible"


def test_sin_configuracion_y_base_caida(entorno):
    centro = entorno.centro()
    vacio = centro.consultar("BALOTO_REVANCHA")
    assert vacio["configuracion"]["estado"] == "sin_configuracion" and vacio["prediccion"] is None
    with pytest.raises(PrediccionesError) as error:
        centro.iniciar("BALOTO_REVANCHA")
    assert error.value.codigo == "sin_configuracion"
    entorno.configurar("MILOTO", "uniforme")
    centro.ahora("MILOTO")
    entorno.base_caida = True
    vista = centro.consultar("MILOTO")
    assert vista["base"]["estado"] == "base_no_disponible" and vista["prediccion"]["explicacion"]
    fi = centro.fiabilidad("MILOTO")
    assert fi["base"]["estado"] != "consultada"
    assert {ev["estado"] for ev in fi["lineas"][0]["evaluaciones"]} <= {"sin_base", "sin_datos"}
    with pytest.raises(PrediccionesError):
        centro.consultar("XX")


# ---------------------------------------------------------------------------
# Lectura pura y almacen
# ---------------------------------------------------------------------------

def test_consultar_fiabilidad_indice_y_ejecucion_no_escriben(entorno):
    entorno.configurar("MILOTO", "logistica_regularizada")
    centro = entorno.centro()
    r = centro.ahora("MILOTO")
    entorno.anadir("MILOTO", entorno.siguiente("MILOTO"))
    antes = f4.arbol(entorno.raiz)
    centro.indice()
    centro.consultar("MILOTO")
    centro.consultar("MILOTO", r["prediccion"]["cartera"]["clave"])
    centro.fiabilidad("MILOTO")
    centro.fiabilidad("MILOTO", hasta=5)
    centro.ejecucion(r["prediccion"]["id"])
    assert f4.arbol(entorno.raiz) == antes


def test_explicar_es_idempotente_y_no_sobrescribe_un_archivo_alterado(entorno):
    entorno.configurar("MILOTO", "uniforme")
    centro = entorno.centro()
    r = centro.ahora("MILOTO")["prediccion"]
    clave_cartera = r["cartera"]["clave"]
    otra = centro.explicar(clave_cartera, "comando")
    assert otra["reutilizado"] and otra["clave"] == r["explicacion"]["clave"]
    archivos = list((entorno.raiz / "predicciones" / "explicaciones" / "MILOTO").glob("*.json"))
    assert len(archivos) == 1
    datos = json.loads(archivos[0].read_text(encoding="utf-8"))
    datos["rankings"]["numeros"]["todos"][0]["probabilidad"] = 0.5
    archivos[0].write_text(json.dumps(datos), encoding="utf-8")
    alterado = archivos[0].read_bytes()
    with pytest.raises(PrediccionesError) as error:
        centro.explicar(clave_cartera)
    assert error.value.codigo == "alterado" and archivos[0].read_bytes() == alterado
    d = centro.consultar("MILOTO")["prediccion"]
    assert d["explicacion"] is None and d["explicaciones_ilegibles"][0]["clave"] == r["explicacion"]["clave"]


def test_un_fallo_inesperado_al_explicar_no_deja_la_generacion_en_curso(entorno, monkeypatch):
    entorno.configurar("MILOTO", "uniforme")
    centro = entorno.centro()

    def disco_lleno(artefacto):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(centro._almacen, "guardar", disco_lleno)
    p = centro.ahora("MILOTO")["prediccion"]
    assert p["estado"] == "parcial" and p["fase"] == "terminado" and p["cartera"]["estado"] == "terminado"
    assert p["explicacion"]["estado"] == "fallo" and p["explicacion"]["codigo"] == "fallo_inesperado"
    assert centro.ejecucion(p["id"])["prediccion"]["estado"] == "parcial"


def test_explicar_no_toca_la_cartera_ni_otros_almacenes(entorno):
    entorno.configurar("MILOTO", "uniforme")
    carteras = entorno.carteras()
    centro = entorno.centro(carteras)
    r = centro.ahora("MILOTO")["prediccion"]
    cartera = entorno.raiz / "carteras"
    antes = f4.arbol(cartera)
    centro._almacen = f4.PrediccionesFileStore(entorno.raiz / "otro")
    centro.explicar(r["cartera"]["clave"])
    assert f4.arbol(cartera) == antes
    assert carteras.verificar_cartera(r["cartera"]["clave"])["integridad"] == "correcta"


# ---------------------------------------------------------------------------
# Sin fuga de informacion
# ---------------------------------------------------------------------------

def test_sorteos_posteriores_al_corte_no_cambian_la_prediccion_ni_su_evidencia(entorno):
    entorno.configurar("MILOTO", "logistica_regularizada", cantidad=2)
    centro = entorno.centro()
    claves = []
    for k in range(4):
        claves.append(centro.ahora("MILOTO")["prediccion"]["cartera"]["clave"])
        entorno.anadir("MILOTO", entorno.siguiente("MILOTO", semilla=300 + k))
    elegida = centro.consultar("MILOTO", claves[2])["prediccion"]
    corte = elegida["datos"]["corte"]

    def lectura():
        d = centro.consultar("MILOTO", claves[2])["prediccion"]
        f = centro.fiabilidad("MILOTO", hasta=corte)
        return d["explicacion"], d["rankings"], d["combinaciones"], f["lineas"], f["receta"]

    a = lectura()
    _reemplazar_posteriores(entorno, "MILOTO", corte, semilla=999)
    b = lectura()
    assert a == b
    ev = a[3][0]["evaluaciones"][0]
    assert ev["muestra"]["sorteos"] == 2 and ev["muestra"]["periodo"][1] == corte
    # Recalcular la explicacion desde la cartera guardada da la misma clave.
    cartera = entorno.carteras().cartera(claves[2]).artefacto
    cuerpo = pe.cuerpo_de_explicacion(cartera, a[0]["importancias"])
    assert pe.huella(cuerpo) == a[0]["clave"]
    # La evidencia completa si depende de los sorteos posteriores: la cartera
    # cuyo historico ya no coincide con la base queda excluida, con su motivo.
    muestra = centro.fiabilidad("MILOTO")["lineas"][0]["evaluaciones"][0]["muestra"]
    assert muestra["emisiones"] == 4 and muestra["sorteos"] == 3
    assert muestra["exclusiones"] == [{"estado": "excluido", "motivo": "historico_hasta_el_corte_cambio",
                                       "emisiones": 1}]


# ---------------------------------------------------------------------------
# Fiabilidad por linea
# ---------------------------------------------------------------------------

def test_fiabilidad_separa_lineas_y_evalua_la_receta_de_la_version_registrada(entorno):
    lab = entorno.laboratorio()
    r = entorno.registrar(lab, "BALOTO", "random_forest_clasificador")
    entorno.configurar("BALOTO", "random_forest_clasificador", registrado=r["modelo_registrado"])
    centro = entorno.centro()
    for k in range(3):
        centro.ahora("BALOTO")
        entorno.anadir("BALOTO", entorno.siguiente("BALOTO", semilla=400 + k))
    fi = centro.fiabilidad("BALOTO")
    lineas = [l["linea"] for l in fi["lineas"]]
    assert lineas == ["carteras:random_forest_clasificador-v1-reg1-reducido",
                      "laboratorio:random_forest_clasificador-v1-reg1-reducido"]
    seg = fi["lineas"][0]["evaluaciones"][0]
    assert seg["tipo"] == "seguimiento" and seg["estado"] == "muestra_insuficiente" and seg["muestra"]["sorteos"] == 3
    assert set(seg["componentes"]) == {"numeros", "superbalota"}
    assert "congelado" in fi["lineas"][0]["estimador"]
    assert fi["receta"]["origen"] == "informe de procedencia de la versión registrada"
    assert fi["receta"]["informe"] == r["experimento"] and fi["receta"]["estado"] == "muestra_insuficiente"
    assert fi["metodo"]["version"] == "fase4-fiabilidad-1"
    with pytest.raises(PrediccionesError) as error:
        centro.fiabilidad("BALOTO", "carteras:otra")
    assert error.value.codigo == "no_valido"
    with pytest.raises(PrediccionesError):
        centro.fiabilidad("BALOTO", hasta=0)
    # Pedir explicitamente una linea que ya esta no la duplica.
    assert fi["lineas_disponibles"] == [lineas[0]]
    assert [l["linea"] for l in centro.fiabilidad("BALOTO", lineas[0])["lineas"]] == lineas


def test_importancias_en_el_proceso_trabajador_real_con_la_carga_restringida(entorno):
    from app.infrastructure.laboratorio_trabajador import EjecutorEnProceso

    lab = entorno.laboratorio()
    r = entorno.registrar(lab, "MILOTO", "random_forest_clasificador")
    entorno.configurar("MILOTO", "random_forest_clasificador", registrado=r["modelo_registrado"])
    ejecutor = EjecutorEnProceso(tiempo_maximo=600)
    carteras = entorno.carteras()
    centro = entorno.centro(carteras, ejecutor=ejecutor)
    p = centro.ahora("MILOTO")["prediccion"]
    assert p["explicacion"]["estado"] == "guardada"
    assert ejecutor.lanzados == 1 and ejecutor.activos == 0  # solo la explicacion usa el trabajador
    trabajador = centro.consultar("MILOTO")["prediccion"]["explicacion"]
    assert trabajador["importancias"]["estado"] == "disponible"
    # Mismo estimador en este proceso: la misma explicacion (misma clave).
    local = entorno.centro(carteras)
    local._almacen = f4.PrediccionesFileStore(entorno.raiz / "local")
    assert local.explicar(p["cartera"]["clave"])["clave"] == trabajador["clave"]
