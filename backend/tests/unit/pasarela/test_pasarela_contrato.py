"""Fase 9.1: el OpenAPI versionado del frontend (`frontend/src/api/openapi.json`)
sigue a la API publica de esta base. Se compara la parte contractual que usa
el frontend (rutas, metodos, parametros y esquemas con sus propiedades); los
detalles que dependen de la version de FastAPI se ignoran. La app se construye
cerrada y sin consultar ninguna base."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import exportar_openapi_publica as exportar

FRONTEND = Path(__file__).resolve().parents[4] / "frontend"
OPENAPI = FRONTEND / "src" / "api" / "openapi.json"
RESPUESTAS = FRONTEND / "src" / "pruebas" / "respuestas"


def _tipo(esquema: dict) -> object:
    if "$ref" in esquema:
        return esquema["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in esquema:
        return sorted(str(_tipo(x)) for x in esquema["anyOf"])
    if esquema.get("type") == "array":
        return ["array", _tipo(esquema.get("items", {}))]
    return esquema.get("type", "any")


def proyeccion(doc: dict) -> dict:
    rutas = {}
    for ruta, operaciones in doc["paths"].items():
        for metodo, op in operaciones.items():
            parametros = sorted((p["name"], p["in"], p.get("required", False), str(_tipo(p.get("schema", {}))),
                                 p.get("schema", {}).get("pattern"), p.get("schema", {}).get("minimum"),
                                 p.get("schema", {}).get("maximum")) for p in op.get("parameters", []))
            respuestas = {e: _tipo(r.get("content", {}).get("application/json", {}).get("schema", {}))
                          for e, r in op.get("responses", {}).items()}
            rutas[f"{metodo} {ruta}"] = {"parametros": parametros, "respuestas": respuestas,
                                         "seguridad": op.get("security")}
    esquemas = {n: {"propiedades": {k: str(_tipo(v)) for k, v in e.get("properties", {}).items()},
                    "requeridas": sorted(e.get("required", [])),
                    "adicionales": e.get("additionalProperties")}
                for n, e in doc["components"]["schemas"].items()}
    return {"rutas": rutas, "esquemas": esquemas,
            "seguridad": doc["components"].get("securitySchemes")}


def test_el_openapi_versionado_coincide_con_la_api_publica_de_la_base():
    versionado = json.loads(OPENAPI.read_text(encoding="utf-8"))
    actual = exportar.openapi_publico()
    assert proyeccion(versionado) == proyeccion(actual)
    assert OPENAPI.read_bytes().endswith(b"\n") and versionado["info"]["version"] == actual["info"]["version"]


def test_hasta_describe_objetivos_sin_acreditar_disponibilidad_temporal():
    """Un filtro numérico no acredita cuándo existía un informe o una emisión."""
    for documento in (exportar.openapi_publico(), json.loads(OPENAPI.read_text(encoding="utf-8"))):
        operacion = documento["paths"]["/api/v1/juegos/{codigo}/fiabilidad"]["get"]
        parametro = next(p for p in operacion["parameters"] if p["name"] == "hasta")
        campo = documento["components"]["schemas"]["Fiabilidad"]["properties"]["hasta"]
        for descripcion in (parametro["description"], campo["description"]):
            texto = descripcion.lower()
            assert "objetivos" in texto and "no acredita" in texto
            assert "evidencia disponible en el corte" not in texto


def test_las_respuestas_sinteticas_del_frontend_siguen_los_contratos_publicos():
    from app.api.publica import esquemas as e
    from app.api.publica import esquemas_guardados as g

    contratos = {"juegos": e.Juegos, "juego": e.JuegoDetalle, "sorteos": e.PaginaDeSorteos, "sorteo": e.Sorteo,
                 "indice": e.IndiceDeEstadisticas, "resumen": e.Resumen, "panel": e.Estadisticas,
                 "metrica": e.RespuestaDeMetrica, "predicciones": e.Predicciones, "fiabilidad": e.Fiabilidad,
                 "simulaciones": e.Simulaciones,
                 "simulacion": e.Simulacion, "estado": e.EstadoDelServicio, "salud": e.Salud,
                 "modelos": g.ModelosGuardados, "modelo": g.FichaModeloGuardado,
                 "carteras": g.CarterasGuardadas, "cartera": g.FichaCarteraGuardada,
                 "resultados": g.ResultadosGuardados}
    archivos = sorted(RESPUESTAS.glob("*.json"))
    assert len(archivos) >= 20
    for archivo in archivos:
        muestra = json.loads(archivo.read_text(encoding="utf-8"))
        if muestra["estado"] != 200:
            e.ErrorRespuesta.model_validate(muestra["cuerpo"])
            continue
        tipo = archivo.stem.split("--")[1]
        contratos[tipo].model_validate(muestra["cuerpo"])
        assert muestra["escenario"] == "fase9-sintetico/1", archivo.name


def test_formatos_y_etiquetas_del_frontend_son_los_de_la_consola_htmx():
    """`formatos.json` (casos que Vitest comprueba contra `formatear` del frontend) es
    la salida actual del `formatear` de la consola HTMX, y las etiquetas del tipo de
    p-value de `formatos.ts` son las del backend."""
    import re

    from app.application.estadisticas.descriptivas import ETIQUETAS_TIPO_P_VALUE
    from tests.generar_respuestas_fase9 import casos_de_formato

    versionado = json.loads((FRONTEND / "src" / "pruebas" / "formatos.json").read_text(encoding="utf-8"))
    assert versionado == casos_de_formato()
    codigo = (FRONTEND / "src" / "api" / "formatos.ts").read_text(encoding="utf-8")
    bloque = re.search(r"ETIQUETAS_TIPO_P[^=]*=\s*\{(.*?)\};", codigo, re.S).group(1)
    etiquetas = dict(re.findall(r'(\w+):\s*"([^"]*)"', bloque))
    assert etiquetas == ETIQUETAS_TIPO_P_VALUE
