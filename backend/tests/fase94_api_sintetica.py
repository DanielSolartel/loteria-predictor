"""Datos SINTETICOS para consultas guardadas de Fase 9.4.

Solo la preparacion emite artefactos: dos candidatos por experimento (uniforme
+ modelo lineal), un bloque reducido y modelos registrados reales. Las consultas
posteriores usan los lectores reales; no son respuestas HTTP interceptadas. No
lee PostgreSQL ni almacenes operativos. Las versiones calculadas se conservan en
memoria por proceso para no repetir ajustes identicos entre pruebas.
"""
from __future__ import annotations

import copy
import os
from functools import lru_cache
from pathlib import Path

from app.application.ml import laboratorio_artefactos as la
from app.application.ml import laboratorio_evaluacion as le
from app.application.ml import laboratorio_modelos as lm
from app.application.ml import laboratorio_variables as lv
from app.application.ml import modelos_registrados as mr
from tests import fase9_api_sintetica as anterior
from tests.unit import fixtures_fase4 as f4
from tests.unit import fixtures_producto4 as fp4
from tests.unit.simulaciones import fixtures_fase7 as f7

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
ESCENARIO = anterior.ESCENARIO
MODELOS = {j: "poisson_regularizado" if j == "COLORLOTO" else "logistica_regularizada" for j in JUEGOS}
ESTADOS = ("normal", "vacio", "alterado", "incompatible")


@lru_cache(maxsize=8)
def _version(juego: str, atras: int = 5):
    """Una version real, independiente del destino; copia antes de publicar."""
    tamanos = {"BALOTO": 110, "BALOTO_REVANCHA": 100, "MILOTO": 87, "COLORLOTO": 90}
    historico = fp4.historico(juego, tamanos[juego])
    instantanea = lv.validar_instantanea(juego, historico[:-atras])
    entrada = lm.CATALOGO[MODELOS[juego]]
    uniforme = lm.CATALOGO["uniforme_paleta" if juego == "COLORLOTO" else "uniforme"]
    entradas = (uniforme, entrada)
    protocolo = le.Protocolo(bloques=1, perfil="reducido")
    identidad = la.identidad_del_experimento(instantanea, entradas, protocolo)
    evaluacion, _ = le.evaluar(instantanea, entradas, protocolo)
    informe = la.componer(la.cuerpo_del_experimento(instantanea, identidad, evaluacion), "ejecucion", {})
    entrenado = mr.entrenar(informe, entrada)
    cuerpo = mr.cuerpo_del_modelo(informe, entrada, mr.identidad_del_modelo(informe, entrada),
                                 {k: v for k, v in entrenado.items() if k != "contenido"})
    artefacto = mr.componer(cuerpo, {"terminado_en": "2026-10-27T10:00:00+00:00", "segundos": 0.0})
    return informe, artefacto, entrenado["contenido"]


def registrar(e4, juego: str, *, atras: int = 5, incompatible: bool = False):
    informe, artefacto, contenido = copy.deepcopy(_version(juego, atras))
    almacen = e4.almacen_laboratorio
    if almacen.obtener_experimento(informe["clave"]) is None:
        almacen.guardar_experimento(informe)
    if incompatible:
        cuerpo = mr.cuerpo_de(artefacto)
        cuerpo["identidad"]["entorno"]["scikit-learn"] = "0.0.1"
        cuerpo["clave"] = mr.huella(cuerpo["identidad"])
        artefacto = mr.componer(cuerpo, artefacto["publicacion"])
    return almacen.guardar_modelo(artefacto, contenido)


def preparar(raiz: Path, *, estado: str = "normal") -> dict:
    """Almacenes nuevos; el estado defectuoso se prepara ANTES de consultar."""
    if estado not in ESTADOS:
        raise ValueError("estado sintetico desconocido")
    raiz.mkdir(parents=True, exist_ok=True)
    e7, e4 = f7.entorno(raiz / "datos"), f4.entorno(raiz / "f4")
    modelos, carteras = {j: [] for j in JUEGOS}, {j: [] for j in JUEGOS}
    if estado != "vacio":
        for juego in JUEGOS:
            if juego == "BALOTO":
                modelos[juego].append(registrar(e4, juego, atras=6))
            modelo = registrar(e4, juego)
            modelos[juego].append(modelo)
            e4.configurar(juego, MODELOS[juego], registrado=modelo.identificador)
            e4.centro().ahora(juego)
            e4.anadir(juego, e4.siguiente(juego))
            e4.centro().ahora(juego)
            servicio = e4.carteras()
            for linea in servicio.lineas(juego):
                carteras[juego].extend(servicio.carteras_de_linea(juego, linea))
            carteras[juego].sort(key=lambda c: (c.objetivo, c.identificador))
        if estado == "alterado":
            modelo = modelos["BALOTO"][-1]
            objeto = next((e4.directorio / "modelos" / "BALOTO" / "estimadores").glob(
                modelo.artefacto["estimador"]["sha256"] + ".*"))
            objeto.write_bytes(objeto.read_bytes() + b"alteracion sintetica")
            cartera = carteras["COLORLOTO"][-1]
            ruta = next((e4.raiz / "carteras" / "carteras" / "COLORLOTO").rglob(
                "*" + cartera.identificador + ".json"))
            ruta.write_bytes(ruta.read_bytes() + b"alteracion sintetica")
        elif estado == "incompatible":
            modelos["BALOTO"].append(registrar(e4, "BALOTO", atras=7, incompatible=True))
    from app.application.use_cases.consultas_guardadas import ConsultasGuardadas
    guardados = ConsultasGuardadas(e4.almacen_laboratorio, e4.carteras(), e4.centro_de_resultados())
    return {"e7": e7, "e4": e4, "guardados": guardados, "modelos": modelos, "carteras": carteras,
            "series": {}, "estado": estado}


def crear(raiz: Path, configuracion=None, *, preparada: dict | None = None, estado: str = "normal"):
    """API real y pasarela aparte: solo sustituye proveedores por almacenes aislados."""
    from app.api.publica import dependencias as d
    datos = preparada or preparar(raiz, estado=estado)
    app = anterior.crear(raiz, configuracion, preparada=datos)
    app.dependency_overrides[d.consultas_guardadas] = lambda: datos["guardados"]
    return app


def _desde_entorno():
    raiz = os.environ.get("F94_RAIZ")
    return crear(Path(raiz), estado=os.environ.get("F94_ESTADO", "normal")) if raiz else None


app = _desde_entorno()
