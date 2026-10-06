"""
Comparacion de pronosticos guardados con resultados observados -Producto 2.

Para cada artefacto (Baloto, Revancha, MiLoto o ColorLoto) se busca su
sorteo objetivo en el historico ACTUAL, en lectura y sin tocar los bytes
del artefacto:

- `observado`: el objetivo figura; se dan fecha, resultado y coincidencias;
- `pendiente`: el objetivo es posterior al ultimo sorteo cargado;
- `no_corresponde`: no hay historico cargado, o el objetivo falta aunque
  hay sorteos posteriores (hueco de la base).

`emision` distingue un pronostico generado cuando el objetivo NO figuraba
en la base local (`emitido_sin_el_resultado_en_la_base_local`) de una
reconstruccion retrospectiva (`reconstruccion_retrospectiva`). La fecha de
generacion es del reloj local: no acredita anterioridad frente al sorteo
real. `historico_hasta_el_corte` dice si la entrada del artefacto se pudo
comprobar contra la base actual:
- `coincide`: la huella de los sorteos hasta el corte es la guardada;
- `cambio`: la huella difiere (tambien figura en `discrepancias`);
- `no_disponible`: no queda ningun sorteo hasta el corte en la base, asi
  que la entrada no se puede verificar; no es una coincidencia ni un
  cambio demostrado.
`discrepancias` solo recoge cambios demostrados: del historico hasta el
corte o del resultado observado desde que se genero el artefacto.

Coincidencias:
- Baloto/Revancha: numeros sugeridos acertados (0..5) y superbalota;
- MiLoto: numeros sugeridos acertados (0..5);
- ColorLoto: pares acertados con repeticion (0..6), y aparte numeros y
  colores acertados con repeticion.

Modulo puro.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from app.application.ml import pronostico_colorloto as colorloto
from app.application.ml.pronostico_experimental import huella_del_historico

NOTA_SOBRE_FECHAS = ("la fecha de generacion es del reloj local de quien genero el artefacto y no acredita "
                     "anterioridad frente al sorteo real")


def _huella(codigo_juego: str, resultados: Sequence) -> str | None:
    if not resultados:
        return None
    return colorloto.huella_del_historico(resultados) if codigo_juego == "COLORLOTO" else huella_del_historico(resultados)


def _resultado(codigo_juego: str, r) -> dict:
    if codigo_juego == "COLORLOTO":
        return {"pares": [list(p) for p in r.pares]}
    return {"numeros": list(r.numeros), "superbalota": r.superbalota}


def _coincidencias(codigo_juego: str, artefacto: dict, r) -> dict:
    pronostico = artefacto["pronostico"]
    if codigo_juego == "COLORLOTO":
        sugeridos = [(f["numero"], f["color"]) for f in pronostico["pares"]]
        return {"pares": colorloto.coincidencias(sugeridos, r.pares),
                "numeros": sum((Counter(n for n, _ in sugeridos) & Counter(n for n, _ in r.pares)).values()),
                "colores": sum((Counter(c for _, c in sugeridos) & Counter(c for _, c in r.pares)).values()),
                "de": len(r.pares)}
    sugeridos = set(pronostico["numeros_sugeridos"])
    ranking = [f["numero"] for f in pronostico["ranking"]]
    salida = {"numeros": len(sugeridos & set(r.numeros)), "de": len(r.numeros),
              "posicion_en_el_ranking": {str(n): ranking.index(n) + 1 for n in r.numeros if n in ranking}}
    superbalota = (artefacto.get("superbalota") or {}).get("pronostico", {}).get("sugerida")
    if superbalota is not None and r.superbalota is not None:
        salida["superbalota"] = superbalota == r.superbalota
    return salida


def _emision(artefacto: dict) -> str:
    tipo = ((artefacto.get("generacion") or {}).get("clasificacion_temporal") or {}).get("tipo")
    if tipo == "pronostico_sobre_el_ultimo_dato_disponible":
        return "emitido_sin_el_resultado_en_la_base_local"
    if tipo in ("simulacion_retrospectiva", "objetivo_no_cargado_con_sorteos_posteriores"):
        return "reconstruccion_retrospectiva"
    return "sin_clasificacion_al_generar"


def comparar_con_resultado(artefacto: dict, historico_completo: Sequence) -> dict:
    """Comparacion de lectura de un artefacto con el historico actual."""
    codigo = artefacto["juego"]
    objetivo = artefacto["pronostico"]["objetivo"]
    ordenado = sorted(historico_completo, key=lambda r: r.numero_sorteo)
    base = {"objetivo": objetivo, "emision": _emision(artefacto), "nota_sobre_fechas": NOTA_SOBRE_FECHAS}

    discrepancias = []
    corte = artefacto["datos"]["corte"]
    hasta_corte = [r for r in ordenado if r.numero_sorteo <= corte]
    actual = _huella(codigo, hasta_corte)
    if actual is None:
        base["historico_hasta_el_corte"] = {
            "estado": "no_disponible",
            "motivo": f"el historico hasta el corte (sorteo {corte}) no esta disponible en la base actual: no se "
                      "puede verificar la entrada del artefacto; no es una coincidencia ni un cambio demostrado"}
    elif actual != artefacto["datos"]["sha256_historico"]:
        base["historico_hasta_el_corte"] = {
            "estado": "cambio", "motivo": "la huella del historico actual hasta el corte difiere de la guardada"}
        discrepancias.append({"tipo": "historico_hasta_el_corte_cambio",
                              "detalle": "el historico actual hasta el corte no coincide con el usado al generar; "
                                         "el artefacto no se modifica"})
    else:
        base["historico_hasta_el_corte"] = {
            "estado": "coincide", "motivo": "la huella del historico actual hasta el corte es la guardada"}
    if not ordenado:
        return {**base, "estado": "no_corresponde", "motivo": "no hay historico cargado para este juego",
                "fecha": None, "resultado": None, "coincidencias": None, "discrepancias": discrepancias}
    observado = next((r for r in ordenado if r.numero_sorteo == objetivo), None)
    if observado is None:
        ultimo = ordenado[-1].numero_sorteo
        if objetivo > ultimo:
            return {**base, "estado": "pendiente",
                    "motivo": f"el sorteo {objetivo} aun no figura en la base (ultimo cargado: {ultimo})",
                    "fecha": None, "resultado": None, "coincidencias": None, "discrepancias": discrepancias}
        return {**base, "estado": "no_corresponde",
                "motivo": f"hueco: el sorteo {objetivo} no figura en la base aunque hay sorteos posteriores "
                          f"(hasta {ultimo})",
                "fecha": None, "resultado": None, "coincidencias": None, "discrepancias": discrepancias}
    resultado = _resultado(codigo, observado)
    guardado = ((artefacto.get("generacion") or {}).get("clasificacion_temporal") or {}).get("resultado_observado")
    if guardado:
        anterior = ({"pares": guardado.get("pares")} if codigo == "COLORLOTO"
                    else {"numeros": guardado.get("numeros"), "superbalota": guardado.get("superbalota")})
        normal = (lambda x: sorted(map(tuple, x["pares"]))) if codigo == "COLORLOTO" else (lambda x: x)
        if anterior.get("pares" if codigo == "COLORLOTO" else "numeros") is not None and normal(anterior) != normal(resultado):
            discrepancias.append({"tipo": "resultado_observado_cambio",
                                  "detalle": "el resultado del objetivo en la base difiere del registrado al generar",
                                  "al_generar": anterior})
    return {**base, "estado": "observado", "motivo": "el sorteo objetivo figura en la base",
            "fecha": observado.fecha.isoformat(), "resultado": resultado,
            "coincidencias": _coincidencias(codigo, artefacto, observado), "discrepancias": discrepancias}


def clasificar_objetivo(codigo_juego: str, pronostico: dict, superbalota_sugerida: int | None,
                        disponibles: Sequence) -> dict:
    """Clasificacion temporal del objetivo frente a todo el historico
    cargado. Para los juegos numericos es la de Producto 1
    (`pronostico_experimental.clasificar_objetivo`); para ColorLoto, la
    misma regla con el resultado observado expresado en pares."""
    from app.application.ml import pronostico_experimental as pe

    if codigo_juego != "COLORLOTO":
        return pe.clasificar_objetivo(pronostico["objetivo"], disponibles,
                                      numeros_sugeridos=pronostico["numeros_sugeridos"],
                                      superbalota_sugerida=superbalota_sugerida)
    if not disponibles:
        raise pe.PronosticoExperimentalError("no hay sorteos cargados para clasificar el objetivo")
    objetivo = pronostico["objetivo"]
    ordenado = sorted(disponibles, key=lambda r: r.numero_sorteo)
    ultimo = ordenado[-1]
    observado = next((r for r in ordenado if r.numero_sorteo == objetivo), None)
    base = {"objetivo": objetivo, "objetivo_en_la_base": observado is not None,
            "ultimo_sorteo_disponible": ultimo.numero_sorteo, "ultima_fecha_disponible": ultimo.fecha.isoformat()}
    if observado is not None:
        sugeridos = [(f["numero"], f["color"]) for f in pronostico["pares"]]
        return {**base, "tipo": "simulacion_retrospectiva",
                "descripcion": (f"Simulacion retrospectiva: el sorteo objetivo {objetivo} ya figura en la base. El "
                                "pronostico usa solo datos hasta el corte y se compara con el resultado observado."),
                "resultado_observado": {"pares": [list(p) for p in observado.pares],
                                        "aciertos_pares": colorloto.coincidencias(sugeridos, observado.pares)}}
    if objetivo > ultimo.numero_sorteo:
        return {**base, "tipo": "pronostico_sobre_el_ultimo_dato_disponible",
                "descripcion": (f"Pronostico experimental sobre el ultimo dato disponible: el objetivo {objetivo} es "
                                f"el siguiente al ultimo sorteo cargado ({ultimo.numero_sorteo}, "
                                f"{ultimo.fecha.isoformat()}). Esto no prueba que el sorteo no se haya celebrado: "
                                "no hay evidencia de calendario ni de que el historico este actualizado."),
                "resultado_observado": None}
    return {**base, "tipo": "objetivo_no_cargado_con_sorteos_posteriores",
            "descripcion": (f"El objetivo {objetivo} no figura en la base, pero hay sorteos posteriores cargados "
                            f"(hasta {ultimo.numero_sorteo}): es una simulacion retrospectiva sobre un hueco del "
                            "historico, sin resultado observado para comparar."),
            "resultado_observado": None}
