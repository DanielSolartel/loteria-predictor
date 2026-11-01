"""Issue #103: comparador del OpenAPI público completo (`scripts/comparar_openapi_publica.py`).

Acepta solo la excepción auditada de 9.4: el `description` de la respuesta 422 en cinco operaciones GET, con el
versionado en «Unprocessable Entity» y el generado en «Unprocessable Content», la leyenda de `http.client` en
CPython 3.13 o posterior. Aun así registra que los documentos son distintos.

Los controles negativos comprueban que la excepción no oculta ningún otro cambio en rutas, métodos, seguridad,
parámetros, restricciones, esquemas, respuestas, descripciones o tipos. El OpenAPI versionado solo se lee; las
mutaciones se hacen sobre copias en memoria. El exportador `--comprobar` y la prueba de deriva no cambian.

v2 (auditoría I103-ROB-01 e I103-ROB-02): regresiones con textos JSON literales para claves duplicadas a cualquier
profundidad, constantes no JSON (`NaN`, `Infinity`, `-Infinity`), números que `float` no distingue y un informe que
conserva literales y tipos sin redondear.
"""
from __future__ import annotations

import copy
import http.client
import json
from pathlib import Path

import pytest

from scripts import comparar_openapi_publica as comparador
from scripts import exportar_openapi_publica as exportar

OPENAPI = Path(__file__).resolve().parents[4] / "frontend" / "src" / "api" / "openapi.json"
TEXTO = OPENAPI.read_text(encoding="utf-8")
BASE = json.loads(TEXTO)
CINCO = ["/api/v1/juegos/{codigo}/modelos-guardados", "/api/v1/juegos/{codigo}/modelos-guardados/{clave}",
         "/api/v1/juegos/{codigo}/carteras-guardadas", "/api/v1/juegos/{codigo}/carteras-guardadas/{clave}",
         "/api/v1/juegos/{codigo}/resultados"]


def _texto(doc: dict) -> str:
    return exportar.texto(doc)


def _con_excepcion(doc: dict) -> dict:
    d = copy.deepcopy(doc)
    for ruta in CINCO:
        d["paths"][ruta]["get"]["responses"]["422"]["description"] = "Unprocessable Content"
    return d


def _primera(doc: dict, condicion):
    for ruta, ops in doc["paths"].items():
        for metodo, op in ops.items():
            if condicion(ruta, metodo, op):
                return ruta, metodo, op
    raise AssertionError("El OpenAPI versionado no tiene el elemento que requiere el control")


def test_el_versionado_conserva_la_leyenda_historica_en_las_cinco_rutas_y_solo_en_ellas():
    leyendas = {(r, m): op["responses"]["422"]["description"] for r, ops in BASE["paths"].items()
                for m, op in ops.items() if "422" in op.get("responses", {})}
    assert {k for k, v in leyendas.items() if v == "Unprocessable Entity"} == {(r, "get") for r in CINCO}
    assert "Unprocessable Content" not in TEXTO


def test_texto_identico():
    r = comparador.comparar(TEXTO, TEXTO)
    assert (r["clasificacion"], r["texto_igual"], r["documentos_json_iguales"], r["codigo"]) == ("identicos_texto", True, True, 0)


def test_mismo_json_con_otro_formato_y_orden_de_claves():
    r = comparador.comparar(TEXTO, json.dumps(BASE, indent=4, sort_keys=True))
    assert r["clasificacion"] == "iguales_json_formato_distinto"
    assert r["documentos_json_iguales"] is True and r["texto_igual"] is False and r["codigo"] == 0


@pytest.mark.parametrize("leyenda_runtime", [None, "Unprocessable Content"])
def test_solo_las_cinco_descripciones_auditadas_se_aceptan_sin_declarar_iguales_los_documentos(leyenda_runtime):
    r = comparador.comparar(TEXTO, _texto(_con_excepcion(BASE)), leyenda_runtime)
    assert r["clasificacion"] == "solo_excepcion_422_auditada" and r["codigo"] == 0
    assert r["documentos_json_iguales"] is False and r["texto_igual"] is False
    assert r["total_diferencias"] == 5 and r["excepcion_422"]["aplicadas"] == 5 and not r["diferencias_no_aceptadas"]
    assert r["campos_excluidos"] == []
    assert {d["ruta"] for d in r["diferencias"]} == comparador.RUTAS_EXCEPCION_422


def test_la_leyenda_runtime_debe_corresponder_al_valor_generado():
    r = comparador.comparar(TEXTO, _texto(_con_excepcion(BASE)), "Unprocessable Entity")
    assert r["clasificacion"] == "diferencias_no_aceptadas" and r["codigo"] == 1


def _mutar_422_ajena(d):
    ruta, _, op = _primera(d, lambda r, m, o: "422" in o.get("responses", {}) and r not in CINCO)
    op["responses"]["422"]["description"] = "Unprocessable Content"


def _mutar_texto_parecido(d):
    d["paths"][CINCO[0]]["get"]["responses"]["422"]["description"] = "Unprocessable content"


def _mutar_otra_respuesta_de_las_cinco(d):
    respuestas = d["paths"][CINCO[2]]["get"]["responses"]
    codigo = next(c for c in respuestas if c not in ("422", "200"))
    respuestas[codigo]["description"] = respuestas[codigo].get("description", "") + " (cambio)"


def _mutar_resumen(d):
    d["paths"][CINCO[1]]["get"]["summary"] += " (cambio)"


def _mutar_descripcion_de_parametro(d):
    _, _, op = _primera(d, lambda r, m, o: any("description" in p for p in o.get("parameters", [])))
    next(p for p in op["parameters"] if "description" in p)["description"] += " (cambio)"


def _mutar_descripcion_de_esquema(d):
    esquema = next(e for e in d["components"]["schemas"].values() if "description" in e)
    esquema["description"] += " (cambio)"


def _quitar_ruta(d):
    d["paths"].pop(CINCO[4])


def _anadir_ruta(d):
    d["paths"]["/api/v1/juegos/{codigo}/nueva"] = copy.deepcopy(d["paths"][CINCO[0]])


def _anadir_metodo(d):
    d["paths"][CINCO[0]]["post"] = copy.deepcopy(d["paths"][CINCO[0]]["get"])


def _quitar_seguridad_de_operacion(d):
    _, _, op = _primera(d, lambda r, m, o: "security" in o)
    op.pop("security")


def _cambiar_esquema_de_seguridad(d):
    nombre = next(iter(d["components"]["securitySchemes"]))
    d["components"]["securitySchemes"][nombre]["name"] = "X-Otra-Clave"


def _cambiar_patron(d):
    _, _, op = _primera(d, lambda r, m, o: any("pattern" in p.get("schema", {}) for p in o.get("parameters", [])))
    next(p for p in op["parameters"] if "pattern" in p.get("schema", {}))["schema"]["pattern"] = "^.*$"


def _cambiar_maximo(d):
    _, _, op = _primera(d, lambda r, m, o: any("maximum" in p.get("schema", {}) for p in o.get("parameters", [])))
    p = next(p for p in op["parameters"] if "maximum" in p.get("schema", {}))
    p["schema"]["maximum"] = p["schema"]["maximum"] + 1


def _cambiar_obligatoriedad(d):
    _, _, op = _primera(d, lambda r, m, o: any("required" in p for p in o.get("parameters", [])))
    p = next(p for p in op["parameters"] if "required" in p)
    p["required"] = not p["required"]


def _quitar_parametro(d):
    _, _, op = _primera(d, lambda r, m, o: len(o.get("parameters", [])) > 1)
    op["parameters"].pop()


def _reordenar_parametros(d):
    _, _, op = _primera(d, lambda r, m, o: len(o.get("parameters", [])) > 1)
    op["parameters"].reverse()


def _cambiar_tipo_de_propiedad(d):
    esquema = next(e for e in d["components"]["schemas"].values()
                   if any(v.get("type") == "integer" for v in e.get("properties", {}).values()))
    prop = next(v for v in esquema["properties"].values() if v.get("type") == "integer")
    prop["type"] = "string"


def _reordenar_requeridas(d):
    esquema = next(e for e in d["components"]["schemas"].values() if len(e.get("required", [])) > 1)
    esquema["required"].reverse()


def _quitar_propiedad(d):
    esquema = next(e for e in d["components"]["schemas"].values() if len(e.get("properties", {})) > 1)
    esquema["properties"].pop(next(iter(esquema["properties"])))


def _cambiar_propiedades_adicionales(d):
    esquema = next(e for e in d["components"]["schemas"].values() if "additionalProperties" in e)
    esquema["additionalProperties"] = not esquema["additionalProperties"] if isinstance(esquema["additionalProperties"], bool) else True


def _anadir_respuesta(d):
    d["paths"][CINCO[3]]["get"]["responses"]["418"] = {"description": "I'm a teapot"}


def _cambiar_esquema_de_respuesta(d):
    d["paths"][CINCO[3]]["get"]["responses"]["422"]["content"]["application/json"]["schema"] = {"type": "object"}


def _cambiar_version(d):
    d["info"]["version"] += "-cambio"


def _entero_a_real(d):
    _, _, op = _primera(d, lambda r, m, o: any(type(p.get("schema", {}).get("maximum")) is int for p in o.get("parameters", [])))
    p = next(p for p in op["parameters"] if type(p.get("schema", {}).get("maximum")) is int)
    p["schema"]["maximum"] = float(p["schema"]["maximum"])


def _booleano_a_entero(d):
    _, _, op = _primera(d, lambda r, m, o: any(p.get("required") is True for p in o.get("parameters", [])))
    next(p for p in op["parameters"] if p.get("required") is True)["required"] = 1


MUTACIONES = {
    "422 de otra ruta con la leyenda nueva": _mutar_422_ajena,
    "una de las cinco con texto parecido": _mutar_texto_parecido,
    "otra respuesta de una de las cinco rutas": _mutar_otra_respuesta_de_las_cinco,
    "resumen de operación": _mutar_resumen,
    "descripción de parámetro": _mutar_descripcion_de_parametro,
    "descripción de esquema": _mutar_descripcion_de_esquema,
    "ruta eliminada": _quitar_ruta,
    "ruta añadida": _anadir_ruta,
    "método añadido": _anadir_metodo,
    "seguridad de operación eliminada": _quitar_seguridad_de_operacion,
    "esquema de seguridad cambiado": _cambiar_esquema_de_seguridad,
    "patrón de parámetro": _cambiar_patron,
    "máximo de parámetro": _cambiar_maximo,
    "obligatoriedad de parámetro": _cambiar_obligatoriedad,
    "parámetro eliminado": _quitar_parametro,
    "orden de parámetros": _reordenar_parametros,
    "tipo de propiedad": _cambiar_tipo_de_propiedad,
    "orden de requeridas": _reordenar_requeridas,
    "propiedad eliminada": _quitar_propiedad,
    "propiedades adicionales": _cambiar_propiedades_adicionales,
    "respuesta añadida": _anadir_respuesta,
    "esquema de respuesta 422": _cambiar_esquema_de_respuesta,
    "versión de la API": _cambiar_version,
    "entero a real": _entero_a_real,
    "booleano a entero": _booleano_a_entero,
}


@pytest.mark.parametrize("sobre_excepcion", [False, True], ids=["sola", "con-excepcion-422"])
@pytest.mark.parametrize("nombre", sorted(MUTACIONES))
def test_controles_negativos_cualquier_otro_cambio_se_rechaza(nombre, sobre_excepcion):
    generado = _con_excepcion(BASE) if sobre_excepcion else copy.deepcopy(BASE)
    MUTACIONES[nombre](generado)
    r = comparador.comparar(TEXTO, _texto(generado), "Unprocessable Content" if sobre_excepcion else None)
    assert r["clasificacion"] == "diferencias_no_aceptadas" and r["codigo"] == 1, nombre
    assert r["documentos_json_iguales"] is False and r["diferencias_no_aceptadas"]
    # La excepción nunca absorbe el cambio añadido: cada diferencia no aceptada queda registrada aparte.
    assert all(not comparador.es_excepcion_422(d, None) for d in r["diferencias_no_aceptadas"])


def test_una_sexta_ruta_con_el_mismo_par_de_leyendas_se_rechaza():
    # Simula una ruta futura que declara 422 sin descripción: aunque el par Entity -> Content sea el mismo,
    # la excepción se limita a las cinco rutas auditadas.
    versionado = copy.deepcopy(BASE)
    ruta, metodo, op = _primera(versionado, lambda r, m, o: "422" in o.get("responses", {}) and r not in CINCO)
    op["responses"]["422"]["description"] = "Unprocessable Entity"
    generado = _con_excepcion(versionado)
    generado["paths"][ruta][metodo]["responses"]["422"]["description"] = "Unprocessable Content"
    r = comparador.comparar(_texto(versionado), _texto(generado), "Unprocessable Content")
    assert r["clasificacion"] == "diferencias_no_aceptadas" and r["codigo"] == 1
    assert r["excepcion_422"]["aplicadas"] == 5 and len(r["diferencias_no_aceptadas"]) == 1


def test_direccion_inversa_no_se_acepta():
    r = comparador.comparar(_texto(_con_excepcion(BASE)), TEXTO)
    assert r["clasificacion"] == "diferencias_no_aceptadas" and r["excepcion_422"]["aplicadas"] == 0


def test_la_generacion_de_este_interprete_solo_difiere_en_la_excepcion_auditada():
    leyenda = http.client.responses[422]
    r = comparador.comparar(TEXTO, exportar.texto(exportar.openapi_publico()), leyenda)
    if leyenda == "Unprocessable Entity":  # CPython 3.12 o anterior
        assert r["clasificacion"] == "identicos_texto"
    else:  # CPython 3.13 o posterior
        assert leyenda == "Unprocessable Content"
        assert r["clasificacion"] == "solo_excepcion_422_auditada" and r["excepcion_422"]["aplicadas"] == 5
    assert r["codigo"] == 0


def test_cli_compara_archivos_sin_sobrescribir(tmp_path):
    generado = tmp_path / "generado.json"
    generado.write_text(_texto(_con_excepcion(BASE)), encoding="utf-8")
    salida = tmp_path / "informe"
    assert comparador.main(["--versionado", str(OPENAPI), "--generado", str(generado), "--salida", str(salida)]) == 0
    informe = json.loads((salida / "comparacion.json").read_text(encoding="utf-8"))
    assert informe["clasificacion"] == "solo_excepcion_422_auditada" and informe["documentos_json_iguales"] is False
    assert (salida / "diferencia-texto.diff").read_text(encoding="utf-8").count("+            \"description\": \"Unprocessable Content\"") == 5
    with pytest.raises(SystemExit):
        comparador.main(["--versionado", str(OPENAPI), "--generado", str(generado), "--salida", str(salida)])


# --- v2: lectura estricta y números exactos (auditoría I103-ROB-01 e I103-ROB-02) ---------------------------------
# Estas regresiones parten de TEXTOS JSON literales: un diccionario serializado con json.dumps no puede contener una
# clave duplicada ni un literal numérico que float no represente, así que no reproduciría los defectos.

def _limite(literal: str) -> str:
    return '{"openapi":"3.1.0","info":{"title":"Sonda","version":"1"},"paths":{},' \
           '"components":{"schemas":{"Limite":{"type":"number","maximum":' + literal + '}}}}'


def _no_valida(versionado: str, generado: str) -> dict:
    # El tipo de la excepción solo se evalúa si se lanza algo: un comparador que acepte la entrada falla con el
    # motivo observado en la auditoría (clasificación y código), no por un nombre ausente.
    try:
        r = comparador.comparar(versionado, generado)
    except comparador.EntradaNoValida as e:
        return e.problemas
    pytest.fail(f"entrada no válida aceptada: {r['clasificacion']}, código {r['codigo']}, "
                f"documentos_json_iguales={r['documentos_json_iguales']}")


def _cli(tmp_path, versionado: str, generado: str):
    (tmp_path / "v.json").write_bytes(versionado.encode("utf-8"))
    (tmp_path / "g.json").write_bytes(generado.encode("utf-8"))
    codigo = comparador.main(["--versionado", str(tmp_path / "v.json"), "--generado", str(tmp_path / "g.json"),
                              "--salida", str(tmp_path / "informe")])
    texto = (tmp_path / "informe" / "comparacion.json").read_text(encoding="utf-8")
    # Los reales del informe se leen como (tipo, literal) para comprobar que no se redondearon.
    return codigo, texto, json.loads(texto, parse_float=lambda s: ("number", s))


TEXTO_EXCEPCION = _texto(_con_excepcion(BASE))
assert TEXTO_EXCEPCION.count('"security": [') == 18 and TEXTO.count('"security": [') == 18


def test_seguridad_duplicada_sobre_la_excepcion_se_rechaza_sin_elegir_una_clave():
    # Un «security» vacío seguido del original: un lector que conserva la última clave solo vería la excepción.
    generado = TEXTO_EXCEPCION.replace('"security": [', '"security": [],\n        "security": [', 1)
    problemas = _no_valida(TEXTO, generado)
    assert list(problemas) == ["generado"]
    assert problemas["generado"] == ['clave duplicada "security" (2 veces) en /paths/~1api~1v1~1estado/get']


@pytest.mark.parametrize("texto, puntero", [
    ('{"a": 1, "a": 1}', "/"),
    ('{"x": {"y": [{"z": true, "z": true}]}}', "/x/y/0"),
    ('{"p": {"a/b": {"c~d": {"k": "1", "k": "2"}}}}', "/p/a~1b/c~0d"),
])
def test_clave_duplicada_a_cualquier_profundidad(texto, puntero):
    for problemas in (_no_valida(texto, '{}'), _no_valida('{}', texto)):
        (lista,) = problemas.values()
        assert len(lista) == 1 and lista[0].startswith("clave duplicada ") and lista[0].endswith(f" en {puntero}")


def test_duplicada_en_ambos_documentos_y_varias_a_la_vez():
    texto = '{"a": 1, "a": 2, "b": {"c": 0, "c": 0, "c": 0}}'
    problemas = _no_valida(texto, texto)
    assert problemas["versionado"] == problemas["generado"] == [
        'clave duplicada "a" (2 veces) en /', 'clave duplicada "c" (3 veces) en /b']


@pytest.mark.parametrize("constante", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("documento", ["versionado", "generado", "ambos"])
def test_constantes_no_json_se_rechazan(constante, documento):
    malo, bueno = _limite(constante), _limite("1")
    v, g = {"versionado": (malo, bueno), "generado": (bueno, malo), "ambos": (malo, malo)}[documento]
    problemas = _no_valida(v, g)
    esperado = {"versionado", "generado"} if documento == "ambos" else {documento}
    assert set(problemas) == esperado
    for lista in problemas.values():
        assert lista == [f"constante no JSON {constante} en /components/schemas/Limite/maximum"]


def test_texto_no_json_se_rechaza_de_forma_controlada():
    problemas = _no_valida(TEXTO, TEXTO[:-3])
    assert list(problemas) == ["generado"] and problemas["generado"][0].startswith("JSON no válido: JSONDecodeError")


@pytest.mark.parametrize("versionado, generado", [
    ("1.0000000000000000", "1.0000000000000001"),
    ("1e400", "2e400"),
    ("-1e400", "-2e400"),
    ("1e-400", "2e-400"),
    ("12345678901234567890123", "12345678901234567890124"),
    ("0.1", "0.10000000000000001"),
])
def test_numeros_distintos_se_comparan_desde_el_texto_exacto(versionado, generado):
    r = comparador.comparar(_limite(versionado), _limite(generado))
    assert r["clasificacion"] == "diferencias_no_aceptadas" and r["codigo"] == 1 and r["documentos_json_iguales"] is False
    (d,) = r["diferencias_no_aceptadas"]
    assert d["ruta"] == "/components/schemas/Limite/maximum" and d["clase"] == "valor"
    assert d["literales"] == [versionado, generado] and d["tipos"][0] == d["tipos"][1]


@pytest.mark.parametrize("versionado, generado", [("1.0", "1.00"), ("1e2", "100.0"), ("1E+2", "1e2"), ("0.0", "-0.0")])
def test_mismo_numero_con_otra_escritura_es_formato(versionado, generado):
    r = comparador.comparar(_limite(versionado), _limite(generado))
    assert r["clasificacion"] == "iguales_json_formato_distinto" and r["documentos_json_iguales"] is True


@pytest.mark.parametrize("versionado, generado, tipos", [
    ("1", "1.0", ["integer", "number"]),
    ("1", "true", ["integer", "boolean"]),
    ("0", "false", ["integer", "boolean"]),
    ("1", '"1"', ["integer", "string"]),
    ("100", "1e2", ["integer", "number"]),
])
def test_enteros_reales_booleanos_y_textos_no_se_confunden(versionado, generado, tipos):
    r = comparador.comparar(_limite(versionado), _limite(generado))
    (d,) = r["diferencias_no_aceptadas"]
    assert d["clase"] == "tipo" and d["tipos"] == tipos and r["codigo"] == 1


def test_el_informe_conserva_literales_y_tipos_sin_redondear(tmp_path):
    codigo, texto, informe = _cli(tmp_path, _limite("1.0000000000000000"), _limite("1.0000000000000001"))
    assert codigo == 1 and informe["clasificacion"] == "diferencias_no_aceptadas"
    assert '"versionado": 1.0000000000000000,' in texto and '"generado": 1.0000000000000001,' in texto
    (d,) = informe["diferencias_no_aceptadas"]
    assert d["versionado"] == ("number", "1.0000000000000000") and d["generado"] == ("number", "1.0000000000000001")
    assert d["tipos"] == ["number", "number"] and d["literales"] == ["1.0000000000000000", "1.0000000000000001"]
    (tmp_path / "grande").mkdir()
    codigo, texto, informe = _cli(tmp_path / "grande", _limite("1e400"), _limite("2e400"))
    assert codigo == 1 and '"versionado": 1e400,' in texto and '"generado": 2e400,' in texto
    assert "Infinity" not in texto and informe["diferencias_no_aceptadas"][0]["literales"] == ["1e400", "2e400"]


def test_el_informe_no_admite_float():
    with pytest.raises(TypeError):
        comparador.volcar({"x": 0.1})


@pytest.mark.parametrize("generado", [
    TEXTO_EXCEPCION.replace('"security": [', '"security": [],\n        "security": [', 1),
    _limite("Infinity"),
    _limite("NaN"),
])
def test_cli_rechaza_entradas_no_validas_con_informe_y_codigo_3(tmp_path, generado, capsys):
    versionado = TEXTO if generado.startswith("{\n") else _limite("1")
    codigo, _, informe = _cli(tmp_path, versionado, generado)
    assert (codigo, informe["clasificacion"]) == (3, "entrada_no_valida")
    assert informe["documentos_json_iguales"] is None and comparador.EXIT_ENTRADA_NO_VALIDA == 3
    assert informe["codigo"] == 3 and informe["total_problemas"] == {"generado": 1}
    salida = capsys.readouterr()
    assert "Traceback" not in salida.out + salida.err and salida.err.startswith("entrada no valida: generado: ")


def test_cli_rechaza_utf8_no_valido(tmp_path):
    (tmp_path / "v.json").write_bytes(TEXTO.encode("utf-8"))
    (tmp_path / "g.json").write_bytes(b'{"a": "\xff"}')
    codigo = comparador.main(["--versionado", str(tmp_path / "v.json"), "--generado", str(tmp_path / "g.json"),
                              "--salida", str(tmp_path / "informe")])
    informe = json.loads((tmp_path / "informe" / "comparacion.json").read_text(encoding="utf-8"))
    assert codigo == 3 and informe["problemas"]["generado"][0].startswith("UTF-8 no válido")


def test_la_excepcion_historica_sigue_aceptada_desde_texto_literal(tmp_path):
    codigo, texto, informe = _cli(tmp_path, TEXTO, TEXTO_EXCEPCION)
    assert codigo == 0 and informe["clasificacion"] == "solo_excepcion_422_auditada"
    assert informe["documentos_json_iguales"] is False and informe["excepcion_422"]["aplicadas"] == 5
    assert all(d["tipos"] == ["string", "string"] for d in informe["diferencias"])
