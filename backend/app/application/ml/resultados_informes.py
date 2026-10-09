"""
Producto 6: informes guardados de la vista de resultados (modulo puro).

Un informe es una FOTOGRAFIA: conserva filtros, politica de seleccion,
procedencias, lineas, artefactos de origen, resultados observados usados y
las probabilidades congeladas de cada emision incluida, ademas de los
calculos. Asi se puede comprobar despues sin reentrenar ni depender de que la
base siga igual. JSON canonico (AE-52) con huella SHA-256: `clave` = huella
del cuerpo (sin los datos volatiles de guardado) y `sello` = huella del
artefacto sin el sello. Repetir el mismo contenido reutiliza el informe; una
fotografia distinta crea otro, sin sobrescribir.

La verificacion separa tres preguntas:
1. integridad del archivo (bytes canonicos, sello y clave);
2. reproduccion del calculo congelado, por partes: metricas por objetivo con
   las funciones actuales, resumenes, comparacion y calibracion de los
   modelos, y los aciertos, resumenes y comparacion de las CARTERAS
   (recalculados con sus combinaciones y el resultado congelados y la
   funcion de aciertos de Producto 5);
3. coincidencia con la consulta actual de la base: estado, motivo,
   historico, resultado observado (por su contenido: el orden de los numeros
   o de los pares no importa, la multiplicidad de un par si) y metricas de
   cada emision, y lo mismo para cada cartera elegida. Unas perdidas iguales
   no bastan: con una fuente uniforme, dos resultados distintos pierden lo
   mismo. Sin acceso a los datos necesarios no hay coincidencia, sino
   «no disponible» o «no comparable».
Una huella local no es una firma externa ni una prueba de anterioridad.

Formatos: `resultados-informe/2` congela tambien las combinaciones de las
carteras incluidas y el resultado observado de cada emision. Los informes
`resultados-informe/1` se siguen leyendo sin reescribirlos; sus carteras no
se pueden recalcular y se informan como «no verificable», nunca exactas.
"""
from __future__ import annotations

import hashlib
import json
import math
from types import SimpleNamespace

from app.application.ml import carteras_artefactos as ca
from app.application.ml import resultados_calibracion as rc
from app.application.ml import resultados_evaluacion as re_
from app.application.ml import resultados_procedencias as rp
from app.application.ml.registro_prospectivo import serializar_entrada

ESQUEMA_INFORME = "resultados-informe/2"
ESQUEMAS_ADMITIDOS = ("resultados-informe/1", ESQUEMA_INFORME)
VERSION_IMPLEMENTACION = "producto6-2"
VOLATILES = ("guardado", "sello")
ESTADO_DE_USO = "experimental_no_acreditado"
NOTA = ("Fotografía local de la vista de resultados. Su huella SHA-256 detecta alteraciones del archivo; no es una "
        "firma externa ni una prueba de que algo se emitiera antes de un sorteo.")


def json_canonico(objeto) -> bytes:
    """Bytes canonicos (AE-52) de un informe o de una exportacion."""
    return serializar_entrada(objeto)


def huella(objeto) -> str:
    return hashlib.sha256(json_canonico(objeto)).hexdigest()


def contexto() -> dict:
    return {"uso": ESTADO_DE_USO, "AUTORIZA_EVALUACION": False, "no_go_ae39": "vigente",
            "resultado_acreditado": False}


def _emision_congelada(fila: dict) -> dict:
    salida = {k: fila[k] for k in ("procedencia", "linea", "clave_linea", "objetivo", "tipo", "identificador",
                                   "integridad", "historico", "resultado_estado", "estado", "motivo", "fecha_sorteo",
                                   "aciertos", "de", "metricas", "superbalota", "universo", "carteras")}
    salida["resultado"] = fila["resultado"]
    if fila["estado"] == "incluido":
        salida["congelado"] = fila["congelado"]
    return salida


def cuerpo_de_informe(vista: dict) -> dict:
    """`vista`: salida completa (sin paginar) de la consulta del caso de uso."""
    seleccion = vista["seleccion"]
    emisiones = [_emision_congelada(f) for f in vista["emisiones_de_la_seleccion"]]
    limitaciones = []
    if vista["base"]["estado"] != "consultada":
        limitaciones.append("base de datos no disponible al guardar: sin resultados observados")
    for p, info in vista["procedencias"].items():
        if info.get("error"):
            limitaciones.append(f"{p}: {info['error']}")
    if vista["comparacion"]["estado"] != "con_muestra_comun":
        limitaciones.append("sin muestra comun para la comparacion directa")
    return {
        "esquema": ESQUEMA_INFORME, "implementacion": VERSION_IMPLEMENTACION, "estado_de_uso": ESTADO_DE_USO,
        "contexto": contexto(), "juego": vista["juego"], "politica": vista["politica"],
        # La seleccion efectiva queda fijada en los filtros: verificar despues
        # consulta exactamente las mismas lineas y carteras, no una seleccion
        # por defecto que pudo cambiar al aparecer lineas nuevas.
        "filtros": {**vista["filtros"], "lineas": list(seleccion),
                    "carteras": list((vista["carteras"] or {}).get("lineas") or vista["filtros"]["carteras"])},
        "nota_seguimiento": vista["nota_seguimiento"], "signo": vista["signo"],
        "base": vista["base"], "procedencias": vista["procedencias"],
        "lineas": [linea for linea in vista["lineas"] if linea["clave"] in seleccion],
        "seleccion": seleccion,
        "artefactos_de_origen": [{"procedencia": p, "linea": l, "objetivo": o, "identificador": i}
                                 for p, l, o, i in sorted({(e["procedencia"], e["linea"], e["objetivo"],
                                                            e["identificador"]) for e in emisiones
                                                           if e["identificador"]})],
        "emisiones": emisiones,
        "calculos": {"resumenes": {clave: vista["resumenes"][clave] for clave in seleccion},
                     "comparacion": vista["comparacion"], "calibracion": vista["calibracion"],
                     "carteras": vista["carteras"]},
        "estado": "parcial" if limitaciones else "completo", "limitaciones": limitaciones, "nota": NOTA,
    }


def componer(cuerpo: dict, guardado: dict) -> dict:
    artefacto = {"clave": huella(cuerpo), **cuerpo, "guardado": guardado}
    return {**artefacto, "sello": huella(artefacto)}


def cuerpo_de(artefacto: dict) -> dict:
    return {k: v for k, v in artefacto.items() if k not in VOLATILES and k != "clave"}


def integro(artefacto: dict) -> bool:
    if artefacto.get("esquema") not in ESQUEMAS_ADMITIDOS:
        return False
    sin_sello = {k: v for k, v in artefacto.items() if k != "sello"}
    return artefacto.get("sello") == huella(sin_sello) and artefacto.get("clave") == huella(cuerpo_de(artefacto))


def _iguales(a, b, tolerancia: float = 1e-12) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and math.isclose(a, b, rel_tol=0.0, abs_tol=tolerancia)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_iguales(a[k], b[k], tolerancia) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_iguales(x, y, tolerancia) for x, y in zip(a, b))
    return a == b


def _canonico(objeto):
    """Lo recalculado con la forma que tiene en el JSON guardado (claves de texto, listas)."""
    return json.loads(json_canonico(objeto))


def _sorteo(juego: str, resultado: dict) -> SimpleNamespace:
    """Resultado congelado con la forma que esperan las funciones de Producto 5."""
    if juego == "COLORLOTO":
        return SimpleNamespace(pares=[tuple(p) for p in resultado["pares"]])
    return SimpleNamespace(numeros=list(resultado["numeros"]), superbalota=resultado.get("superbalota"))


def _reproducir_carteras(artefacto: dict, diferencias: list) -> tuple[str, int]:
    """Aciertos por combinacion, maximo, superbalota, resumen de cada cartera y
    comparacion entre carteras, recalculados con lo congelado en el informe."""
    carteras = artefacto["calculos"].get("carteras")
    if not carteras or not carteras.get("lineas"):
        return "sin_carteras", 0
    juego, tipo = artefacto["juego"], artefacto["filtros"]["tipo"]
    incluidas = [f for c in carteras["lineas"].values() for f in c["filas"] if f["estado"] == "incluido"]
    if artefacto["esquema"] == "resultados-informe/1" or any(
            not (f.get("congelado") or {}).get("combinaciones") or not f.get("resultado") for f in incluidas):
        diferencias.append({"parte": "carteras", "motivo": "carteras_no_verificables",
                            "detalle": "el informe no congela las combinaciones de sus carteras: sus aciertos no se "
                                       "pueden recalcular"})
        return "no_verificable", 0
    distinta = False
    recalculadas = {}
    for linea, c in carteras["lineas"].items():
        filas = []
        for f in c["filas"]:
            if f["estado"] != "incluido":
                filas.append(f)
                continue
            try:
                aciertos = ca.aciertos_observados({"juego": juego, "cartera": f["congelado"]},
                                                  _sorteo(juego, f["resultado"]))
            except Exception as error:  # cualquier fallo es una no reproduccion, nunca una coincidencia
                diferencias.append({"parte": "carteras", "linea": linea, "objetivo": f["objetivo"],
                                    "motivo": f"aciertos_no_recalculables: {error}"})
                distinta = True
                filas.append(f)
                continue
            aciertos = _canonico(aciertos)
            if not _iguales(aciertos, f.get("aciertos")):
                diferencias.append({"parte": "carteras", "linea": linea, "objetivo": f["objetivo"],
                                    "motivo": "aciertos_de_cartera_distintos"})
                distinta = True
            filas.append({**f, "aciertos": aciertos})
        if not _iguales(_canonico(re_.resumen_de_cartera(filas)), c["resumen"]):
            diferencias.append({"parte": "carteras", "linea": linea, "motivo": "resumen_de_cartera_distinto"})
            distinta = True
        recalculadas[linea] = {**c, "filas": filas}
    if not _iguales(_canonico(re_.comparar_carteras(recalculadas, list(recalculadas), tipo)), carteras["comparacion"]):
        diferencias.append({"parte": "carteras", "motivo": "comparacion_de_carteras_distinta"})
        distinta = True
    return ("distinta" if distinta else "exacta"), len(incluidas)


def reproducir(artefacto: dict) -> dict:
    """Recalcula con los datos congelados, por partes: metricas por emision
    incluida, resumenes, comparacion y calibracion de los modelos y los
    calculos de las carteras. No usa la base ni los almacenes ni reentrena.
    `estado`: exacta | no_exacta (algun calculo no coincide) | parcial (todo lo
    verificable coincide, pero alguna parte no se puede verificar)."""
    juego = artefacto["juego"]
    tipo = artefacto["filtros"]["tipo"]
    diferencias = []
    partes = {}
    emisiones = artefacto["emisiones"]
    distintas = 0
    for e in emisiones:
        if e["estado"] != "incluido":
            continue
        try:
            metricas, superbalota = rp.metricas_de_congelado(juego, e["objetivo"], e["congelado"], e["resultado"])
        except Exception as error:  # cualquier fallo es una no reproduccion, nunca una coincidencia
            diferencias.append({"parte": "emisiones", "objetivo": e["objetivo"], "linea": e["clave_linea"],
                                "motivo": f"no_recalculable: {error}"})
            distintas += 1
            continue
        if not _iguales(metricas, e["metricas"]) or not _iguales(superbalota, e["superbalota"]):
            diferencias.append({"parte": "emisiones", "objetivo": e["objetivo"], "linea": e["clave_linea"],
                                "motivo": "metricas_distintas"})
            distintas += 1
    partes["emisiones"] = "distinta" if distintas else "exacta"
    por_linea: dict[str, list] = {}
    for e in emisiones:
        por_linea.setdefault(e["clave_linea"], []).append(e)
    calculos = artefacto["calculos"]
    seleccion = artefacto["seleccion"]
    vistas = {clave: [e for e in por_linea.get(clave, []) if rp.de_tipo(e, tipo)] for clave in seleccion}
    for parte, recalculado, motivo in (
            ("resumenes", {clave: re_.agregado(vistas[clave], juego) for clave in seleccion}, "resumenes_distintos"),
            ("comparacion", re_.comparar(seleccion, vistas, juego, tipo), "comparacion_distinta"),
            ("calibracion", {clave: rc.diagnostico(vistas[clave]) for clave in seleccion}, "calibracion_distinta")):
        igual = _iguales(_canonico(recalculado), calculos[parte])
        partes[parte] = "exacta" if igual else "distinta"
        if not igual:
            diferencias.append({"parte": parte, "motivo": motivo})
    partes["carteras"], carteras_recalculadas = _reproducir_carteras(artefacto, diferencias)
    if any(v == "distinta" for v in partes.values()):
        estado = "no_exacta"
    elif any(v == "no_verificable" for v in partes.values()):
        estado = "parcial"
    else:
        estado = "exacta"
    return {"exacta": estado == "exacta", "estado": estado, "partes": partes, "diferencias": diferencias,
            "emisiones_recalculadas": sum(1 for e in emisiones if e["estado"] == "incluido"),
            "carteras_recalculadas": carteras_recalculadas}


def resultado_normalizado(resultado: dict | None):
    """Contenido de un resultado observado, sin depender de su presentacion: los
    mismos numeros en otro orden son el mismo sorteo; en ColorLoto el orden de
    los pares no cambia el multiconjunto, pero una multiplicidad distinta si.
    La superbalota forma parte del resultado."""
    if not resultado:
        return None
    if resultado.get("pares") is not None:
        return ("pares", tuple(sorted((int(n), str(c)) for n, c in resultado["pares"])))
    return ("numeros", tuple(sorted(int(n) for n in resultado["numeros"])), resultado.get("superbalota"))


def _diferencia(seccion: str, clave: tuple, campo: str, en_el_informe, ahora) -> dict:
    motivo = "resultado_observado_cambio" if campo == "resultado" else f"{campo}_cambio"
    return {"seccion": seccion, "linea": clave[0], "objetivo": clave[1], "tipo": clave[2], "motivo": motivo,
            "en_el_informe": en_el_informe, "ahora": ahora}


def _comparar_filas(seccion: str, guardadas: dict, actuales: dict, campos: tuple, anterior: bool) -> list:
    diferencias = []
    for clave in sorted(set(actuales) | set(guardadas), key=str):
        a, g = actuales.get(clave), guardadas.get(clave)
        if a is None or g is None:
            diferencias.append({"seccion": seccion, "linea": clave[0], "objetivo": clave[1], "tipo": clave[2],
                                "motivo": "solo_en_el_informe" if a is None else "solo_en_la_consulta_actual"})
            continue
        for campo in campos:
            if campo == "resultado":
                vg, va = resultado_normalizado(g.get("resultado")), resultado_normalizado(a.get("resultado"))
                # un informe del formato anterior solo guardaba el resultado de las emisiones incluidas
                if vg != va and not (anterior and vg is None):
                    diferencias.append(_diferencia(seccion, clave, campo, g.get("resultado"), a.get("resultado")))
                    break
            elif not _iguales(a.get(campo), g.get(campo)):
                diferencias.append(_diferencia(seccion, clave, campo, g.get(campo), a.get(campo)))
                break
    return diferencias


CAMPOS_EMISION = ("identificador", "estado", "motivo", "historico", "resultado", "metricas", "superbalota", "aciertos")
CAMPOS_CARTERA = ("identificador", "estado", "motivo", "historico_hasta_el_corte", "resultado", "aciertos")


def comparar_con_consulta(artefacto: dict, vista_actual: dict | None) -> dict:
    """Cada emision y cada fila de cartera del informe frente a la consulta
    actual con los mismos filtros. Sin base: «no_disponible»; sin acceso a una
    procedencia o a las carteras: «no_comparable» (nunca «coincide»)."""
    if vista_actual is None or vista_actual["base"]["estado"] != "consultada":
        return {"estado": "no_disponible", "motivo": "la base no responde: no se puede comparar con la consulta actual",
                "diferencias": []}
    anterior = artefacto["esquema"] == "resultados-informe/1"
    caidas = {p for p, info in vista_actual["procedencias"].items() if info.get("error")}
    no_comparables = [{"seccion": "emisiones" if p != "carteras" else "emisiones y carteras", "procedencia": p,
                       "motivo": info["error"]} for p, info in vista_actual["procedencias"].items() if p in caidas]
    clave = lambda f: (f["clave_linea"], f["objetivo"], f["tipo"])  # noqa: E731
    actuales = {clave(f): f for f in vista_actual["emisiones_de_la_seleccion"] if f["procedencia"] not in caidas}
    guardadas = {clave(e): e for e in artefacto["emisiones"] if e["procedencia"] not in caidas}
    diferencias = _comparar_filas("emisiones", guardadas, actuales, CAMPOS_EMISION, anterior)
    carteras = artefacto["calculos"].get("carteras")
    if carteras and carteras.get("lineas"):
        ahora = vista_actual.get("carteras")
        if ahora is None or "carteras" in caidas:
            if "carteras" not in caidas:
                no_comparables.append({"seccion": "carteras", "motivo": "la consulta actual no tiene la seccion de "
                                                                        "carteras"})
        else:
            def filas(seccion):
                return {(linea, f["objetivo"], f.get("tipo")): f
                        for linea, c in seccion["lineas"].items() for f in c["filas"]}
            diferencias += _comparar_filas("carteras", filas(carteras), filas(ahora), CAMPOS_CARTERA, anterior)
    if diferencias:
        salida = {"estado": "cambio", "diferencias": diferencias,
                  "motivo": "la consulta actual difiere de la fotografia guardada"}
    elif no_comparables:
        salida = {"estado": "no_comparable", "diferencias": [],
                  "motivo": "faltan datos de la consulta actual para comparar: no se puede afirmar que coincida"}
    else:
        return {"estado": "coincide", "diferencias": [], "motivo": None}
    if no_comparables:
        salida["no_comparables"] = no_comparables
    return salida
