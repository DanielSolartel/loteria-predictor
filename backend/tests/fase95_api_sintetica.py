"""Preparación SINTÉTICA propia de 9.5 para API/pasarela/SPA reales.

Reutiliza fixtures existentes, nunca PostgreSQL ni almacenes operativos. Las
escrituras y ajustes reducidos ocurren exclusivamente antes de los GET. Los
nombres con controles/fórmulas son datos de prueba públicos para las descargas.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path

from app.application.ml import carteras_artefactos as ca
from app.application.use_cases.consultas_guardadas import ConsultasGuardadas
from tests import fase9_api_sintetica as f9
from tests import fase94_api_sintetica as f94

JUEGOS = f94.JUEGOS
ESTADOS = ("normal", "vacio", "alterado", "incompatible")


def _carteras(datos, juego):
    servicio = datos["e4"].carteras()
    return sorted((c for linea in servicio.lineas(juego) for c in servicio.carteras_de_linea(juego, linea)),
                  key=lambda c: (c.objetivo, c.identificador))


def _reescribir(datos, cartera, cambiar):
    artefacto = copy.deepcopy(cartera.artefacto)
    cambiar(artefacto)
    nuevo = ca.componer(ca.cuerpo_de(artefacto), "generacion", artefacto["generacion"])
    assert ca.integro(nuevo) and nuevo["identidad"] == cartera.artefacto["identidad"]
    ruta = next((datos["e4"].raiz / "carteras").rglob("*" + cartera.identificador + ".json"))
    ruta.write_bytes(ca.json_canonico(nuevo))


def preparar(raiz: Path, *, estado: str = "normal"):
    if estado not in ESTADOS:
        raise ValueError("Escenario 9.5 desconocido")
    if estado == "vacio":
        return f94.preparar(raiz, estado="vacio")
    datos = f9.preparar(raiz)
    # Cada juego dispone de un detalle de simulación íntegro para la matriz.
    datos["e7"].servicio().ahora("BALOTO_REVANCHA", 100, 20261029, origen="fase95_sintetico")
    registrados = {juego: f94.registrar(datos["e4"], juego) for juego in JUEGOS}
    # Las carteras previas de BALOTO conservan el bosque registrado original.
    # Sólo la preparación selecciona/emite una nueva logístico registrada: al
    # abrir una cartera histórica, la fiabilidad de la configuración actual no
    # puede acreditarse como si perteneciera a aquella identidad anterior.
    datos["e4"].configurar("BALOTO", f94.MODELOS["BALOTO"],
                           registrado=registrados["BALOTO"].identificador)
    datos["e4"].centro().ahora("BALOTO")
    # Opcional ausente, Unicode, saltos y fórmulas: canon y lectores reales.
    nombres = {"BALOTO": '=SUM(1,2)', "BALOTO_REVANCHA": ' +1\n"á,ñ"',
               "COLORLOTO": ' \t@SUM(1,2)\r\nÁmbar “ñ”'}
    for juego, nombre in nombres.items():
        _reescribir(datos, _carteras(datos, juego)[0], lambda a, n=nombre: a["modelo"].update(nombre=n))
    _reescribir(datos, _carteras(datos, "MILOTO")[0], lambda a: a["modelo"].pop("nombre", None))
    if estado == "alterado":
        # F94-ROB-01: metadato necesario ausente, canon y huellas correctos.
        _reescribir(datos, _carteras(datos, "BALOTO")[-1], lambda a: a["datos"].pop("corte"))
        modelos = datos["e4"].almacen_laboratorio.modelos("BALOTO")
        modelo = modelos[-1]
        estimador = next((datos["e4"].directorio / "modelos" / "BALOTO" / "estimadores").glob(
            modelo.artefacto["estimador"]["sha256"] + ".*"))
        estimador.write_bytes(estimador.read_bytes() + b"alteracion sintetica 9.5")
    elif estado == "incompatible":
        f94.registrar(datos["e4"], "BALOTO", atras=7, incompatible=True)
    datos["guardados"] = ConsultasGuardadas(datos["e4"].almacen_laboratorio,
                                            datos["e4"].carteras(), datos["e4"].centro_de_resultados())
    datos["estado"] = estado
    return datos


def crear(raiz: Path, *, estado="normal"):
    from app.api.publica import dependencias as d
    datos = preparar(raiz, estado=estado)
    app = f9.crear(raiz, preparada=datos)
    app.dependency_overrides[d.consultas_guardadas] = lambda: datos["guardados"]
    return app


raiz = os.environ.get("F95_RAIZ")
app = crear(Path(raiz), estado=os.environ.get("F95_ESTADO", "normal")) if raiz else None
