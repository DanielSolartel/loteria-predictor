"""Lista cerrada de consultas `/api/v1` que la pasarela reenvia (Fase 9.1; la 9.2 anade
`color` y `pagina` a la ruta de metrica y la 9.3 la ruta de fiabilidad con `hasta`,
como el OpenAPI publico).

Cada plantilla es una ruta GET del OpenAPI publico versionado
(`frontend/src/api/openapi.json`); las pruebas comprueban la igualdad de
plantillas y nombres de parametros. No hay exclusiones dentro de `paths`: la
documentacion (`/api/v1/docs`) y el propio OpenAPI (`/api/v1/openapi.json`) no
figuran en `paths` y no se reenvian.

Los parametros se acotan de forma sintactica (juego de caracteres, longitud y
una sola aparicion). La validacion semantica (juego existente, rangos, fechas,
metrica disponible) es de la API, que responde con sus 404 y 422.
"""
from __future__ import annotations

import dataclasses
import re
from urllib.parse import urlencode

_SEGMENTO = {
    "codigo": r"[A-Z][A-Z_]{0,31}",
    "numero_sorteo": r"[0-9]{1,10}",
    "metrica": r"[a-z0-9][a-z0-9-]{0,63}",
    "identificador": r"[0-9A-Za-z-]{1,64}",
}
_VALOR = re.compile(r"[A-Za-z0-9_.:-]{1,80}")
MAXIMO_CONSULTA = 512
EXCLUIDAS = frozenset({"/api/v1/docs", "/api/v1/openapi.json"})


@dataclasses.dataclass(frozen=True)
class RutaPublica:
    plantilla: str
    consulta: frozenset[str]

    @property
    def patron(self) -> re.Pattern:
        partes = re.split(r"\{(\w+)\}", self.plantilla)
        texto = "".join(re.escape(p) if i % 2 == 0 else f"(?P<{p}>{_SEGMENTO[p]})" for i, p in enumerate(partes))
        return re.compile(texto)


RUTAS: tuple[RutaPublica, ...] = (
    RutaPublica("/api/v1/salud", frozenset()),
    RutaPublica("/api/v1/estado", frozenset()),
    RutaPublica("/api/v1/juegos", frozenset()),
    RutaPublica("/api/v1/juegos/{codigo}", frozenset()),
    RutaPublica("/api/v1/juegos/{codigo}/sorteos",
                frozenset({"pagina", "por_pagina", "desde", "hasta", "numero_desde", "numero_hasta", "orden"})),
    RutaPublica("/api/v1/juegos/{codigo}/sorteos/{numero_sorteo}", frozenset()),
    RutaPublica("/api/v1/juegos/{codigo}/estadisticas", frozenset()),
    RutaPublica("/api/v1/juegos/{codigo}/estadisticas/resumen", frozenset({"hasta_numero_sorteo"})),
    RutaPublica("/api/v1/juegos/{codigo}/estadisticas/panel", frozenset({"hasta_numero_sorteo"})),
    RutaPublica("/api/v1/juegos/{codigo}/estadisticas/{metrica}",
                frozenset({"hasta_numero_sorteo", "anio", "mes", "dia_semana", "ventana", "color", "pagina"})),
    RutaPublica("/api/v1/juegos/{codigo}/predicciones", frozenset({"cartera", "historial"})),
    RutaPublica("/api/v1/juegos/{codigo}/fiabilidad", frozenset({"hasta"})),
    RutaPublica("/api/v1/juegos/{codigo}/simulaciones", frozenset({"limite"})),
    RutaPublica("/api/v1/simulaciones/{identificador}", frozenset()),
)
_PATRONES = tuple((r, r.patron) for r in RUTAS)


class ConsultaNoAdmitida(ValueError):
    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo, self.mensaje = codigo, mensaje


def buscar(ruta: str) -> RutaPublica | None:
    """La plantilla que casa ENTERA con `ruta`; las literales van antes que `{metrica}`."""
    for publica, patron in _PATRONES:
        if patron.fullmatch(ruta):
            return publica
    return None


def consulta_reenviable(publica: RutaPublica, pares: list[tuple[str, str]], longitud: int) -> str:
    """Consulta saneada y recodificada; sin parametros ajenos, repetidos, largos o con caracteres raros."""
    if longitud > MAXIMO_CONSULTA:
        raise ConsultaNoAdmitida("consulta_demasiado_larga", "La consulta supera el tamaño admitido")
    vistos: set[str] = set()
    for nombre, valor in pares:
        if nombre not in publica.consulta:
            raise ConsultaNoAdmitida("parametro_no_admitido", "Parámetro no admitido en esta consulta")
        if nombre in vistos:
            raise ConsultaNoAdmitida("parametro_repetido", "Un parámetro aparece más de una vez")
        if not _VALOR.fullmatch(valor):
            raise ConsultaNoAdmitida("parametro_no_valido", "Valor de parámetro no admitido")
        vistos.add(nombre)
    return urlencode(pares)
