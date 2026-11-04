"""Consultas de humo y de comparacion de una generacion (DAT-04 y R-L), con la API publica EN PROCESO.

Recorre los endpoints de `/api/v1` en los cuatro juegos, mas `/resultados` por cada procedencia, y guarda por
ruta el estado y la huella del cuerpo canonico. `/salud` y `/estado` (latencias y contadores del proceso) solo
comparan el estado; en los cuerpos de error se excluye `error.solicitud` (identificador aleatorio de cada
peticion, parte del contrato).

E104-DAT-06: `recorrer` valida FUENTES REALES; solo falla por DANO o PERDIDA, nunca por una ausencia legitima:

- estados distintos de los del contrato (200 en listados; un detalle solo se pide con una clave REAL tomada de
  su listado no vacio, y una simulacion inexistente debe dar 404) o `ilegibles` > 0;
- con `esperado` (recuentos sellados: sorteos del manifiesto y artefactos por familia de `coherencia.json`):
  sorteos o ultimo sorteo distintos, menos modelos o carteras de los sellados, una procedencia con artefactos
  sellados y 0 emisiones, o una prediccion sellada que la API no devuelve.

Una generacion sin carteras, sin prediccion o con `/fiabilidad` sin muestra es VALIDA y se describe en
`contenido`. Los requisitos NO VACIOS de la demostracion (datos sinteticos completos) estan aparte, en
`requisitos_de_demostracion`, y solo los aplica la demostracion.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
PROCEDENCIAS = ("operacion", "laboratorio", "carteras")
VOLATILES = ("/api/v1/salud", "/api/v1/estado")
# familia de `coherencia.json` -> procedencia de `/resultados` que la emite
FAMILIA_DE_PROCEDENCIA = {"operacion": "pronostico_experimental", "laboratorio": "pronostico_laboratorio",
                          "carteras": "cartera"}
SIMULACION_INEXISTENTE = "00000000-0000-4000-8000-000000000e10"


def _huella(cuerpo) -> str:
    if isinstance(cuerpo, dict) and isinstance(cuerpo.get("error"), dict):  # `solicitud`: id aleatorio por peticion
        cuerpo = {**cuerpo, "error": {k: v for k, v in cuerpo["error"].items() if k != "solicitud"}}
    return hashlib.sha256(json.dumps(cuerpo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def _ilegibles(valor) -> int:
    if isinstance(valor, dict):
        return sum((v if k == "ilegibles" and isinstance(v, int) else _ilegibles(v)) for k, v in valor.items())
    if isinstance(valor, list):
        return sum(_ilegibles(v) for v in valor)
    return 0


def esperado_de(juegos: dict, coherencia: dict) -> dict:
    """Recuentos sellados de una generacion: `manifiesto["juegos"]` y `coherencia.json` completo."""
    por_juego: dict[str, Counter] = {}
    for a in coherencia.get("artefactos", []):
        por_juego.setdefault(a["juego"], Counter())[a["familia"]] += 1
    return {"juegos": {j: {"sorteos": v.get("sorteos"), "ultimo_sorteo": v.get("ultimo_sorteo")}
                       for j, v in sorted(juegos.items())},
            "artefactos": {j: dict(sorted(c.items())) for j, c in sorted(por_juego.items())}}


def _total(cuerpo: dict) -> int:
    total = cuerpo.get("total")
    return total if isinstance(total, int) else len(cuerpo.get("elementos") or [])


def recorrer(get, esperado: dict | None = None) -> dict:
    """`get(ruta) -> (estado, cuerpo)`. Devuelve rutas con huella, contenido descrito y fallos (dano o perdida)."""
    rutas, fallos, contenido = {}, [], {}

    def pedir(ruta, estado_esperado=200):
        estado, cuerpo = get(ruta)
        rutas[ruta] = {"estado": estado, "sha256": None if ruta in VOLATILES else _huella(cuerpo)}
        if estado != estado_esperado:
            fallos.append(f"{ruta}: estado {estado}, se esperaba {estado_esperado}")
        elif _ilegibles(cuerpo):
            fallos.append(f"{ruta}: {_ilegibles(cuerpo)} ilegibles")
        return cuerpo if isinstance(cuerpo, dict) and estado == 200 else {}

    pedir("/api/v1/salud")
    pedir("/api/v1/estado")
    pedir("/api/v1/juegos")
    pedir(f"/api/v1/simulaciones/{SIMULACION_INEXISTENTE}", estado_esperado=404)  # control negativo del contrato
    for j in JUEGOS:
        b = f"/api/v1/juegos/{j}"
        sellado = (esperado or {}).get("juegos", {}).get(j)
        familias = (esperado or {}).get("artefactos", {}).get(j, {})
        pedir(b)
        sorteos = pedir(f"{b}/sorteos?por_pagina=5")
        primeros = sorteos.get("sorteos") or []
        if primeros and isinstance(primeros[0], dict) and "numero_sorteo" in primeros[0]:
            pedir(f"{b}/sorteos/{primeros[0]['numero_sorteo']}")
        indice = pedir(f"{b}/estadisticas")
        pedir(f"{b}/estadisticas/resumen")
        pedir(f"{b}/estadisticas/panel")
        metrica = next((m["metrica"] for m in indice.get("metricas", []) if not m.get("parametro")), None)
        if metrica:
            pedir(f"{b}/estadisticas/{metrica}")
        prediccion = pedir(f"{b}/predicciones")
        fiabilidad = pedir(f"{b}/fiabilidad")
        modelos = pedir(f"{b}/modelos-guardados")
        for e in (modelos.get("elementos") or [])[:1]:
            pedir(f"{b}/modelos-guardados/{e['clave']}")
        carteras = pedir(f"{b}/carteras-guardadas")
        for e in (carteras.get("elementos") or [])[:1]:
            pedir(f"{b}/carteras-guardadas/{e['clave']}")
        pedir(f"{b}/resultados?por_pagina=100")
        simulaciones = pedir(f"{b}/simulaciones")
        for s in (simulaciones.get("simulaciones") or [])[:1]:
            pedir(f"/api/v1/simulaciones/{s['id']}")
        procedencias = {}
        for p in PROCEDENCIAS:
            d = pedir(f"{b}/resultados?procedencia={p}&por_pagina=100")
            info = (d.get("procedencias") or {}).get(p, {})
            observadas = sum(1 for l in d.get("lineas", [])
                             if ((d.get("resumenes") or {}).get(l.get("clave"), {}).get("incluidos") or 0) > 0)
            procedencias[p] = {"emisiones": info.get("emisiones") or 0, "lineas": len(d.get("lineas", [])),
                               "lineas_con_resultado_observado": observadas}
            ajenas = [l for l in d.get("lineas", []) if l.get("procedencia") != p]
            if ajenas:
                fallos.append(f"{j}: /resultados?procedencia={p} devuelve {len(ajenas)} lineas de otra procedencia")
            if familias.get(FAMILIA_DE_PROCEDENCIA[p], 0) > 0 and not procedencias[p]["emisiones"]:
                fallos.append(f"{j}: procedencia {p} sin emisiones con {familias[FAMILIA_DE_PROCEDENCIA[p]]} "
                              "artefactos sellados (perdida)")
        evaluaciones = [e for l in fiabilidad.get("lineas", []) for e in l.get("evaluaciones", [])]
        con_muestra = [e for e in evaluaciones if ((e.get("muestra") or {}).get("sorteos") or 0) >= 1]
        fiab = {"base": (fiabilidad.get("base") or {}).get("estado"), "lineas": len(fiabilidad.get("lineas", [])),
                "evaluaciones": len(evaluaciones), "con_muestra": len(con_muestra),
                "estados": sorted({str(e.get("estado")) for e in evaluaciones}),
                "receta": (fiabilidad.get("receta") or {}).get("estado")}
        descrito = {"procedencias": procedencias, "fiabilidad": fiab, "carteras": _total(carteras),
                    "modelos": _total(modelos), "prediccion": prediccion.get("prediccion") is not None,
                    "ultimo_sorteo": (primeros[0] if primeros and isinstance(primeros[0], dict) else {})
                    .get("numero_sorteo"), "sorteos": sorteos.get("total")}
        if sellado is not None:
            for campo in ("sorteos", "ultimo_sorteo"):
                if descrito[campo] != sellado.get(campo):
                    fallos.append(f"{j}: {campo} {descrito[campo]} distinto del sellado {sellado.get(campo)}")
        for campo, familia in (("modelos", "modelo"), ("carteras", "cartera")):
            if descrito[campo] < familias.get(familia, 0):
                fallos.append(f"{j}: {descrito[campo]} {campo} de {familias[familia]} sellados (perdida)")
        if familias.get("explicacion", 0) > 0 and not descrito["prediccion"]:
            fallos.append(f"{j}: /predicciones sin prediccion con {familias['explicacion']} selladas (perdida)")
        contenido[j] = descrito
    return {"rutas": rutas, "contenido": contenido, "fallos": fallos, "total": len(rutas)}


def requisitos_de_demostracion(resultado: dict) -> list[str]:
    """Requisitos NO VACIOS de la demostracion sintetica (no se aplican a fuentes reales): cada procedencia con
    emisiones y resultado observado, `/fiabilidad` con alguna evaluacion con muestra, prediccion, carteras y
    modelos en cada juego."""
    faltan = []
    for j, c in resultado["contenido"].items():
        for p, v in c["procedencias"].items():
            if not (v["emisiones"] > 0 and v["lineas_con_resultado_observado"] > 0):
                faltan.append(f"{j}: procedencia {p} sin emisiones o sin resultado observado")
        f = c["fiabilidad"]
        if f["base"] != "consultada" or not f["lineas"] or not f["con_muestra"]:
            faltan.append(f"{j}: /fiabilidad sin evaluacion con muestra {f}")
        if not c["prediccion"]:
            faltan.append(f"{j}: sin prediccion guardada")
        if not c["carteras"] or not c["modelos"]:
            faltan.append(f"{j}: sin carteras o sin modelos")
    return faltan


def comparar(a: dict, b: dict) -> list[str]:
    """Diferencias de estado o de cuerpo (salvo los volatiles) entre dos recorridos."""
    salida = []
    for ruta in sorted(set(a["rutas"]) | set(b["rutas"])):
        if a["rutas"].get(ruta) != b["rutas"].get(ruta):
            salida.append(ruta)
    return salida
