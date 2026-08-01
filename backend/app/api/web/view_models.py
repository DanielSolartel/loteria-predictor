"""
View Models del adaptador web.

Ninguna plantilla Jinja2 recibe una entidad de dominio directamente.
Recibe el resultado de estas funciones: dicts/dataclasses simples,
con formato ya pensado para mostrarse (fechas legibles, listas ya
armadas, flags de UI). Esto mantiene al dominio ignorante de que
existe una interfaz HTML, y evita lógica de presentación dispersa
dentro de los templates.
"""
from __future__ import annotations

from app.application.use_cases.consultar_juegos import JuegoConReglas
from app.domain.entities.juego import Juego
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.color import Color

MESES_ES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_legible(fecha) -> str:
    return f"{fecha.day} de {MESES_ES[fecha.month]} de {fecha.year}"


def juego_a_vm(juego: Juego) -> dict:
    return {
        "id": str(juego.id),
        "codigo": juego.codigo,
        "nombre": juego.nombre,
        "rango": f"{juego.rango_min}–{juego.rango_max}",
        "cantidad_numeros": juego.cantidad_numeros,
        "tiene_superbalota": juego.tiene_superbalota,
        "superbalota_rango": (
            f"{juego.superbalota_min}–{juego.superbalota_max}" if juego.tiene_superbalota else None
        ),
        "tiene_color": juego.tiene_color,
        "permite_repeticion": juego.permite_repeticion,
        "activo": juego.activo,
    }


def juego_con_reglas_a_vm(datos: JuegoConReglas) -> dict:
    vm = juego_a_vm(datos.juego)
    vm["espacio_muestral"] = f"{datos.espacio_muestral:,}".replace(",", ".")
    vm["dimensiones"] = datos.dimensiones
    return vm


def sorteo_a_vm(sorteo: Sorteo) -> dict:
    numeros = list(sorteo.resultado.numeros)
    pares = [
        {"numero": p.numero, "color_codigo": p.color.codigo, "color_nombre": p.color.nombre}
        for p in sorteo.resultado.pares
    ]
    return {
        "id": str(sorteo.id),
        "juego_id": str(sorteo.juego_id),
        "numero_sorteo": sorteo.numero_sorteo,
        "fecha": sorteo.fecha.isoformat(),
        "fecha_legible": _fecha_legible(sorteo.fecha),
        "dia_semana": sorteo.dia_semana.capitalize(),
        "numeros": numeros,
        "superbalota": sorteo.resultado.superbalota,
        "pares": pares,
        "fuente": sorteo.fuente or "—",
    }


def color_a_vm(color: Color) -> dict:
    return {
        "codigo": color.codigo,
        "nombre": color.nombre,
        "activo": color.activo,
        "vigente_desde": color.vigente_desde.isoformat() if color.vigente_desde else None,
        "vigente_hasta": color.vigente_hasta.isoformat() if color.vigente_hasta else None,
        "css_class": f"color-swatch color-{color.codigo.lower()}",
    }
