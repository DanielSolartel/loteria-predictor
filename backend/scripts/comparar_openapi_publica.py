"""Compara el OpenAPI público versionado con el generado (issue #103), sin escribir en el repositorio.

    python -m scripts.comparar_openapi_publica --versionado ../frontend/src/api/openapi.json --salida <carpeta nueva>
    python -m scripts.comparar_openapi_publica --versionado <a.json> --generado <b.json> --salida <carpeta nueva>

Sin `--generado`, construye el documento con el exportador versionado (`scripts.exportar_openapi_publica`, app
cerrada, sin claves ni base de datos) en este intérprete y registra Python, FastAPI, Starlette, Pydantic y la leyenda
`http.client.responses[422]` en uso. Con `--generado` solo usa la biblioteca estándar.

Lectura estricta de ambos textos (UTF-8, JSON), antes de comparar:
- una clave repetida en un mismo objeto, a cualquier profundidad, invalida la entrada: no se elige ninguna de las dos;
- `NaN`, `Infinity` y `-Infinity` no son JSON e invalidan la entrada;
- cada número conserva su literal original y su valor decimal exacto; nunca se convierte a `float`.
Una entrada no válida termina con un informe `entrada_no_valida` y el código 3, sin declarar compatibilidad.

Compara los documentos COMPLETOS:
- igualdad textual: bytes idénticos;
- igualdad semántica: mismo JSON, es decir, sin depender del formato ni del orden de las claves de los objetos. Las
  listas conservan su orden y longitud, y los tipos se distinguen: `1` (entero), `1.0` (número con parte decimal o
  exponente) y `true` son distintos. Dos números del mismo tipo son iguales solo si su valor decimal exacto coincide
  (`1.0` y `1.00` lo son; `1.0000000000000000` y `1.0000000000000001`, o `1e400` y `2e400`, no);
- no se excluye ningún campo ni se ignoran las descripciones.

Única excepción admitida, auditada en la validación nativa de 9.4: el valor de `description` de la respuesta 422 en
las cinco operaciones GET de modelos guardados, carteras guardadas y resultados. El versionado lleva exactamente
«Unprocessable Entity» y el generado, exactamente «Unprocessable Content». Cuando el documento se genera en este
proceso, además debe coincidir con la leyenda 422 del intérprete.

Esa excepción no declara iguales los documentos: el informe registra `documentos_json_iguales=false`. Cualquier otra
diferencia, en esas u otras rutas, campos o valores, la rechaza.

El informe escribe los números con su literal original exacto y cada diferencia lleva sus tipos explícitos (y, si son
números, sus literales como texto); nunca se redondea al serializar.

Códigos de salida: 0 si el texto es idéntico, el JSON es igual o solo está la excepción auditada; 1 si hay otra
diferencia; 3 si una entrada no es JSON válido y estricto. El exportador `--comprobar` sigue siendo la comparación
textual estricta y no cambia.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import http.client
import json
import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

VERSION = "issue103-openapi-comparador/2"
EXIT_ACEPTADO, EXIT_RECHAZADO, EXIT_ENTRADA_NO_VALIDA = 0, 1, 3
LEYENDA_HISTORICA, LEYENDA_ACTUAL = "Unprocessable Entity", "Unprocessable Content"
RUTAS_EXCEPCION_422 = frozenset(
    "/paths/" + r.replace("~", "~0").replace("/", "~1") + "/get/responses/422/description"
    for r in ("/api/v1/juegos/{codigo}/modelos-guardados", "/api/v1/juegos/{codigo}/modelos-guardados/{clave}",
              "/api/v1/juegos/{codigo}/carteras-guardadas", "/api/v1/juegos/{codigo}/carteras-guardadas/{clave}",
              "/api/v1/juegos/{codigo}/resultados"))
MAX_PROBLEMAS = 50


@dataclass(frozen=True)
class Numero:
    """Número JSON exacto: `tipo` es "integer" (sin parte decimal ni exponente) o "number"; `literal`, el texto original."""
    tipo: str
    valor: Decimal
    literal: str = field(compare=False)


class EntradaNoValida(ValueError):
    """Una o ambas entradas no son JSON válido y estricto. `problemas` asocia cada documento con sus motivos."""

    def __init__(self, problemas: dict[str, list[str]]):
        self.problemas = problemas
        super().__init__("; ".join(f"{doc}: {', '.join(p[:3])}{' …' if len(p) > 3 else ''}"
                                   for doc, p in problemas.items()))


class _Objeto(dict):
    """Objeto JSON leído; `duplicadas` registra las claves repetidas en él (no se elige ninguna)."""
    duplicadas: dict


class _Constante:
    def __init__(self, nombre: str):
        self.nombre = nombre


def _puntero(base: str, clave) -> str:
    return f"{base}/{str(clave).replace('~', '~0').replace('/', '~1')}"


def _objeto(pares: list) -> _Objeto:
    d, cuenta = _Objeto(), {}
    for k, v in pares:
        cuenta[k] = cuenta.get(k, 0) + 1
        d[k] = v
    d.duplicadas = {k: n for k, n in cuenta.items() if n > 1}
    return d


def _numero(tipo: str):
    def leer(literal: str) -> Numero:
        return Numero(tipo, Decimal(literal), literal)
    return leer


def _problemas(v, ruta: str, salida: list[str]) -> None:
    if isinstance(v, _Constante):
        salida.append(f"constante no JSON {v.nombre} en {ruta or '/'}")
    elif isinstance(v, dict):
        for k, n in v.duplicadas.items():
            salida.append(f"clave duplicada {json.dumps(k, ensure_ascii=False)} ({n} veces) en {ruta or '/'}")
        for k, x in v.items():
            _problemas(x, _puntero(ruta, k), salida)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            _problemas(x, _puntero(ruta, i), salida)


def leer_json(texto: str):
    """Lee un texto JSON de forma estricta; devuelve (valor, problemas). Sin problemas, el valor es fiel al texto."""
    try:
        valor = json.loads(texto, object_pairs_hook=_objeto, parse_constant=_Constante,
                           parse_int=_numero("integer"), parse_float=_numero("number"))
    except (ValueError, InvalidOperation, RecursionError) as e:  # JSONDecodeError es ValueError
        return None, [f"JSON no válido: {type(e).__name__}: {e}"]
    problemas: list[str] = []
    _problemas(valor, "", problemas)
    return valor, problemas


def _nombre_tipo(v) -> str:
    if isinstance(v, Numero):
        return v.tipo
    for t, nombre in ((bool, "boolean"), (str, "string"), (list, "array"), (dict, "object"), (type(None), "null")):
        if isinstance(v, t):
            return nombre
    raise TypeError(f"valor JSON inesperado: {type(v).__name__}")


def _detalle_numerico(a, b) -> dict:
    lits = [x.literal if isinstance(x, Numero) else None for x in (a, b)]
    return {"literales": lits} if any(x is not None for x in lits) else {}


def diferencias(a, b, ruta: str = "") -> list[dict]:
    """Diferencias entre dos valores JSON leídos con `leer_json`. Las listas se comparan por posición; los tipos y los
    números, de forma exacta."""
    ta, tb = _nombre_tipo(a), _nombre_tipo(b)
    if ta != tb:
        return [{"ruta": ruta or "/", "clase": "tipo", "versionado": a, "generado": b, "tipos": [ta, tb]}
                | _detalle_numerico(a, b)]
    if ta == "object":
        salida = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in b:
                salida.append({"ruta": _puntero(ruta, k), "clase": "ausente_en_generado", "versionado": a[k],
                               "tipo": _nombre_tipo(a[k])})
            elif k not in a:
                salida.append({"ruta": _puntero(ruta, k), "clase": "ausente_en_versionado", "generado": b[k],
                               "tipo": _nombre_tipo(b[k])})
            else:
                salida += diferencias(a[k], b[k], _puntero(ruta, k))
        return salida
    if ta == "array":
        salida = [x for i, (u, v) in enumerate(zip(a, b)) for x in diferencias(u, v, _puntero(ruta, i))]
        if len(a) != len(b):
            salida.append({"ruta": ruta or "/", "clase": "longitud_de_lista", "versionado": len(a), "generado": len(b)})
        return salida
    if a == b:
        return []
    return [{"ruta": ruta or "/", "clase": "valor", "versionado": a, "generado": b, "tipos": [ta, tb]}
            | _detalle_numerico(a, b)]


def es_excepcion_422(d: dict, leyenda_runtime: str | None) -> bool:
    return (d["clase"] == "valor" and d["ruta"] in RUTAS_EXCEPCION_422
            and d.get("versionado") == LEYENDA_HISTORICA and d.get("generado") == LEYENDA_ACTUAL
            and (leyenda_runtime is None or leyenda_runtime == LEYENDA_ACTUAL))


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def comparar(texto_versionado: str, texto_generado: str, leyenda_runtime: str | None = None) -> dict:
    """Compara dos textos JSON completos. `leyenda_runtime` es la leyenda 422 del intérprete que generó el documento
    (None si se comparan dos archivos ya generados y no es verificable). Lanza `EntradaNoValida` si alguno de los
    textos no es JSON válido y estricto."""
    a, problemas_a = leer_json(texto_versionado)
    b, problemas_b = leer_json(texto_generado)
    problemas = {doc: p for doc, p in (("versionado", problemas_a), ("generado", problemas_b)) if p}
    if problemas:
        raise EntradaNoValida(problemas)
    lista = diferencias(a, b)
    aceptadas = [d for d in lista if es_excepcion_422(d, leyenda_runtime)]
    otras = [d for d in lista if d not in aceptadas]
    texto_igual = texto_versionado == texto_generado
    if texto_igual:
        clasificacion = "identicos_texto"
    elif not lista:
        clasificacion = "iguales_json_formato_distinto"
    elif not otras:
        clasificacion = "solo_excepcion_422_auditada"
    else:
        clasificacion = "diferencias_no_aceptadas"
    return {
        "version": VERSION,
        "texto_igual": texto_igual,
        "documentos_json_iguales": not lista,
        "campos_excluidos": [],
        "normalizacion": ("solo formato y orden de claves de objetos; listas, tipos y valores decimales exactos intactos; "
                          "claves duplicadas y constantes no JSON rechazadas"),
        "diferencias": lista,
        "total_diferencias": len(lista),
        "excepcion_422": {"rutas_admitidas": sorted(RUTAS_EXCEPCION_422), "versionado": LEYENDA_HISTORICA,
                          "generado": LEYENDA_ACTUAL, "aplicadas": len(aceptadas),
                          "leyenda_runtime": leyenda_runtime,
                          "leyenda_runtime_verificada": leyenda_runtime is not None},
        "diferencias_no_aceptadas": otras,
        "clasificacion": clasificacion,
        "codigo": EXIT_RECHAZADO if otras else EXIT_ACEPTADO,
        "sha256": {"versionado": _sha256(texto_versionado), "generado": _sha256(texto_generado)},
    }


def informe_entrada_no_valida(error: EntradaNoValida, sha256: dict) -> dict:
    return {
        "version": VERSION,
        "clasificacion": "entrada_no_valida",
        "codigo": EXIT_ENTRADA_NO_VALIDA,
        "texto_igual": None,
        "documentos_json_iguales": None,
        "campos_excluidos": [],
        "problemas": {doc: p[:MAX_PROBLEMAS] for doc, p in error.problemas.items()},
        "total_problemas": {doc: len(p) for doc, p in error.problemas.items()},
        "nota": "No se compara ni se declara compatibilidad: la entrada no es JSON válido y estricto.",
        "sha256": sha256,
    }


def volcar(v, nivel: int = 0) -> str:
    """Serializa el informe como JSON con sangría de 2: los números conservan su literal exacto; no admite `float`."""
    if isinstance(v, Numero):
        return v.literal
    if v is None or isinstance(v, (bool, str)) or type(v) is int:
        return json.dumps(v, ensure_ascii=False)
    sangria, interior = "  " * nivel, "  " * (nivel + 1)
    if isinstance(v, dict):
        if not v:
            return "{}"
        if not all(isinstance(k, str) for k in v):
            raise TypeError("clave de objeto no textual en el informe")
        partes = [f"{interior}{json.dumps(k, ensure_ascii=False)}: {volcar(x, nivel + 1)}" for k, x in v.items()]
        return "{\n" + ",\n".join(partes) + "\n" + sangria + "}"
    if isinstance(v, (list, tuple)):
        if not v:
            return "[]"
        return "[\n" + ",\n".join(interior + volcar(x, nivel + 1) for x in v) + "\n" + sangria + "]"
    raise TypeError(f"valor no serializable sin pérdida en el informe: {type(v).__name__}")


def _entorno() -> dict:
    import fastapi
    import pydantic
    import starlette
    return {"python": sys.version.split()[0], "plataforma": sys.platform, "fastapi": fastapi.__version__,
            "starlette": starlette.__version__, "pydantic": pydantic.__version__,
            "leyenda_http_client_422": http.client.responses.get(422)}


def _decodificar(datos: bytes, documento: str, problemas: dict) -> str | None:
    try:
        return datos.decode("utf-8")
    except UnicodeDecodeError as e:
        problemas[documento] = [f"UTF-8 no válido: {e}"]
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--versionado", type=Path, required=True)
    p.add_argument("--generado", type=Path, help="Documento ya generado; sin él, se genera en este proceso")
    p.add_argument("--salida", type=Path, required=True, help="Carpeta nueva para el informe; no se sobrescribe")
    a = p.parse_args(argv)
    if a.salida.exists():
        raise SystemExit("La carpeta de salida ya existe; no se sobrescribe")
    datos_versionado = a.versionado.read_bytes()
    if a.generado:
        datos_generado, entorno, leyenda = a.generado.read_bytes(), None, None
    else:
        from scripts import exportar_openapi_publica as exportar
        datos_generado = exportar.texto(exportar.openapi_publico()).encode("utf-8")
        entorno = _entorno()
        leyenda = entorno["leyenda_http_client_422"]
    sha256 = {"versionado": hashlib.sha256(datos_versionado).hexdigest(),
              "generado": hashlib.sha256(datos_generado).hexdigest()}
    problemas: dict[str, list[str]] = {}
    versionado = _decodificar(datos_versionado, "versionado", problemas)
    generado = _decodificar(datos_generado, "generado", problemas)
    try:
        if problemas:
            raise EntradaNoValida(problemas)
        informe = comparar(versionado, generado, leyenda)
    except EntradaNoValida as e:
        informe = informe_entrada_no_valida(e, sha256)
        # ASCII con escapes: la consola (p. ej., cp1252 en Windows) no debe provocar un error al informar.
        print("entrada no valida: " + str(e).encode("ascii", "backslashreplace").decode("ascii"), file=sys.stderr)
    informe["origen_generado"] = str(a.generado) if a.generado else "exportador en este proceso"
    informe["entorno_generacion"] = entorno
    a.salida.mkdir(parents=True)
    if not a.generado:
        (a.salida / "openapi-generado.json").write_bytes(datos_generado)
    (a.salida / "comparacion.json").write_bytes((volcar(informe) + "\n").encode("utf-8"))
    if versionado is not None and generado is not None:
        diff = difflib.unified_diff(versionado.splitlines(keepends=True), generado.splitlines(keepends=True),
                                    "versionado", "generado")
        (a.salida / "diferencia-texto.diff").write_bytes("".join(diff).encode("utf-8"))
    resumen = {k: informe[k] for k in ("clasificacion", "texto_igual", "documentos_json_iguales", "codigo")}
    if informe["clasificacion"] == "entrada_no_valida":
        resumen["total_problemas"] = informe["total_problemas"]
    else:
        resumen |= {"total_diferencias": informe["total_diferencias"],
                    "excepcion_422_aplicadas": informe["excepcion_422"]["aplicadas"],
                    "no_aceptadas": len(informe["diferencias_no_aceptadas"])}
    print(json.dumps(resumen | {"entorno": entorno}, ensure_ascii=True))
    return informe["codigo"]


if __name__ == "__main__":
    sys.exit(main())
