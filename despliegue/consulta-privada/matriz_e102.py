"""Fase 10 (E10.2, v2): matriz ESTRICTA 19 endpoints x 4 juegos contra la API PRIVADA, desde la red de servicio
(dentro del contenedor de la pasarela, el unico cliente admitido; la clave se lee de su archivo montado y no se
imprime). Solo biblioteca estandar.

La demostracion antepone a este guion `ESPERADO = {...}` (la vista que la preparacion calculo con los MISMOS
casos de uso antes de publicar) y, opcionalmente, `DESTINO = "ip:puerto"` (una API auxiliar). Cada endpoint tiene
su propia comprobacion de contrato y contenido (v2, F1023-DAT-01): no se cuenta "algo no vacio" de forma
generica. Clases:

- `presente_verificado`: 200 y el contenido coincide con lo esperado (IDs, procedencias, emisiones, lineas,
  objetivos observados, totales, claves de modelos y carteras);
- `vacio_declarado`: 200 con una lista vacia que lo esperado declara (juego sin simulaciones);
- `ausencia_declarada`: 404 controlado esperado (simulacion inexistente);
- `fallo`: cualquier otra cosa, incluido un 200 cuyo contenido no coincide (p. ej. `sin_artefactos` donde la
  publicacion tiene emisiones).
"""
import http.client
import json
import os

JUEGOS = ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO")
PROCEDENCIAS = ("operacion", "laboratorio", "carteras")
ESPERADO = globals().get("ESPERADO") or {}
CLAVE = open("/run/secretos/pasarela_clave_api", encoding="ascii").read().strip()
HOST, PUERTO = (globals().get("DESTINO") or os.environ["PASARELA_API_URL"][len("http://"):]).rsplit(":", 1)


def get(ruta):
    c = http.client.HTTPConnection(HOST, int(PUERTO), timeout=60)
    c.request("GET", ruta, headers={"X-API-Key": CLAVE, "Accept": "application/json"})
    r = c.getresponse()
    cuerpo = r.read()
    c.close()
    try:
        return r.status, json.loads(cuerpo)
    except ValueError:
        return r.status, None


def vista_resultados(d):
    return {"procedencias": {n: {k: p.get(k) for k in ("estado", "lineas", "emisiones", "ilegibles")}
                             for n, p in d.get("procedencias", {}).items()},
            "lineas": sorted(l.get("clave") for l in d.get("lineas", [])),
            "resumenes": {c: {"objetivos": s.get("objetivos"), "incluidos": s.get("incluidos"),
                              "pendientes": s.get("pendientes"), "aciertos": (s.get("aciertos") or {}).get("suma")}
                          for c, s in d.get("resumenes", {}).items()}}


filas, discrepancias = [], []


def fila(juego, plantilla, ruta, comprobar, *, clase_ok="presente_verificado", esperar=200):
    estado, datos = get(ruta)
    try:
        ok, detalle = (estado == esperar and isinstance(datos, dict)), ""
        if ok:
            ok, detalle = comprobar(datos)
    except Exception as error:  # comprobacion mal planteada o respuesta inesperada: nunca un acierto
        ok, detalle = False, f"{type(error).__name__}: {error}"
    clase = clase_ok if ok else "fallo"
    filas.append({"juego": juego, "plantilla": plantilla, "estado": estado, "clase": clase,
                  "codigo": datos.get("error", {}).get("codigo") if isinstance(datos, dict) and "error" in datos else None,
                  "detalle": None if ok else str(detalle)[:300]})
    if not ok:
        discrepancias.append({"juego": juego, "plantilla": plantilla, "estado": estado, "detalle": str(detalle)[:300]})
    return datos if isinstance(datos, dict) else {}


def igual(observado, esperado, que):
    return (observado == esperado), (None if observado == esperado else f"{que}: esperado {esperado!r}, recibido {observado!r}")


for j in JUEGOS:
    exp = ESPERADO.get("juegos", {}).get(j, {})
    b = f"/api/v1/juegos/{j}"
    fila(j, "/api/v1/salud", "/api/v1/salud", lambda d: igual((d["estado"], d["api"]), ("ok", "v1"), "salud"))
    fila(j, "/api/v1/estado", "/api/v1/estado", lambda d: igual((d["api"], d["base"]), ("v1", "disponible"), "estado"))
    fila(j, "/api/v1/juegos", "/api/v1/juegos",
         lambda d: igual(sorted(x["codigo"] for x in d["juegos"]), sorted(JUEGOS), "juegos"))
    fila(j, "/api/v1/juegos/{codigo}", b, lambda d: igual(d["codigo"], j, "codigo"))
    sorteos = fila(j, "/api/v1/juegos/{codigo}/sorteos", f"{b}/sorteos?por_pagina=5",
                   lambda d: igual((d["juego"], d["total"], len(d["sorteos"]) > 0),
                                   (j, ESPERADO["sorteos"][j], True), "sorteos"))
    numero = (sorteos.get("sorteos") or [{}])[0].get("numero_sorteo", 1)
    fila(j, "/api/v1/juegos/{codigo}/sorteos/{numero_sorteo}", f"{b}/sorteos/{numero}",
         lambda d: igual(d["numero_sorteo"], numero, "numero_sorteo"))
    indice = fila(j, "/api/v1/juegos/{codigo}/estadisticas", f"{b}/estadisticas",
                  lambda d: igual((d["juego"], len(d["metricas"]) > 0), (j, True), "indice"))
    fila(j, "/api/v1/juegos/{codigo}/estadisticas/resumen", f"{b}/estadisticas/resumen",
         lambda d: igual(d["total_sorteos"], ESPERADO["sorteos"][j], "total_sorteos"))
    fila(j, "/api/v1/juegos/{codigo}/estadisticas/panel", f"{b}/estadisticas/panel",
         lambda d: igual((d["juego"]["codigo"], bool(d["muestra"])), (j, True), "panel"))
    metrica = next((m["metrica"] for m in indice.get("metricas", []) if not m.get("parametro")),
                   (indice.get("metricas") or [{"metrica": "frecuencia"}])[0]["metrica"])
    fila(j, "/api/v1/juegos/{codigo}/estadisticas/{metrica}", f"{b}/estadisticas/{metrica}",
         lambda d: igual((d["juego"]["codigo"], d["metrica"]["slug"], d["metrica"]["estado"]), (j, metrica, "ok"),
                         "metrica"))
    fila(j, "/api/v1/juegos/{codigo}/predicciones", f"{b}/predicciones",
         lambda d: igual((d["juego"], d["prediccion"] is not None, d["historial_total"] >= 1), (j, True, True),
                         "prediccion guardada"))
    fila(j, "/api/v1/juegos/{codigo}/fiabilidad", f"{b}/fiabilidad",
         lambda d: igual((d["juego"], len(d["lineas"]) > 0), (j, True), "fiabilidad con lineas"))
    modelos = fila(j, "/api/v1/juegos/{codigo}/modelos-guardados", f"{b}/modelos-guardados",
                   lambda d: igual(sorted(e["clave"] for e in d["elementos"]), exp["modelos"], "modelos"))
    clave_m = (modelos.get("elementos") or [{}])[0].get("clave", "0" * 64)
    fila(j, "/api/v1/juegos/{codigo}/modelos-guardados/{clave}", f"{b}/modelos-guardados/{clave_m}",
         lambda d: igual((d["juego"], d["modelo"].get("clave") if isinstance(d["modelo"], dict) else None),
                         (j, clave_m), "ficha de modelo"))
    carteras = fila(j, "/api/v1/juegos/{codigo}/carteras-guardadas", f"{b}/carteras-guardadas",
                    lambda d: igual(d["total"], len(exp["carteras"]), "total de carteras"))
    clave_c = (carteras.get("elementos") or [{}])[0].get("clave", "0" * 64)
    fila(j, "/api/v1/juegos/{codigo}/carteras-guardadas/{clave}", f"{b}/carteras-guardadas/{clave_c}",
         lambda d: igual((d["juego"], d["cartera"].get("clave") if isinstance(d["cartera"], dict) else None,
                          len(d["combinaciones"]) > 0), (j, clave_c, True), "ficha de cartera"))
    fila(j, "/api/v1/juegos/{codigo}/resultados", f"{b}/resultados?por_pagina=100",
         lambda d: igual(vista_resultados(d), {k: exp[k] for k in ("procedencias", "lineas", "resumenes")},
                         "resultados de las tres procedencias"))
    con_simulacion = j == ESPERADO.get("simulacion_juego")
    simulaciones = fila(j, "/api/v1/juegos/{codigo}/simulaciones", f"{b}/simulaciones",
                        lambda d: igual(len(d["simulaciones"]), 1 if con_simulacion else 0, "simulaciones"),
                        clase_ok="presente_verificado" if con_simulacion else "vacio_declarado")
    lista = simulaciones.get("simulaciones") or []
    if lista:
        fila(j, "/api/v1/simulaciones/{identificador}", f"/api/v1/simulaciones/{lista[0]['id']}",
             lambda d: igual((d["id"], d["integridad"]), (lista[0]["id"], "verificada"), "simulacion"))
    else:
        fila(j, "/api/v1/simulaciones/{identificador}", "/api/v1/simulaciones/00000000-0000-4000-8000-000000000e10",
             lambda d: igual(d["error"]["codigo"], "no_encontrado", "simulacion inexistente"),
             clase_ok="ausencia_declarada", esperar=404)

procedencias = {}
for j in JUEGOS:  # cada procedencia por separado: emisiones y solo sus lineas
    exp = ESPERADO.get("juegos", {}).get(j, {})
    for n in PROCEDENCIAS:
        estado, d = get(f"/api/v1/juegos/{j}/resultados?procedencia={n}&por_pagina=100")
        d = d if isinstance(d, dict) else {}
        p = d.get("procedencias", {}).get(n, {})
        observadas = sum(1 for l in d.get("lineas", []) if (d.get("resumenes", {}).get(l.get("clave"), {})
                                                            .get("incluidos") or 0) > 0)
        ok = (estado == 200 and p.get("emisiones") == exp.get("procedencias", {}).get(n, {}).get("emisiones")
              and (p.get("emisiones") or 0) > 0 and observadas >= 1
              and all(l.get("procedencia") == n for l in d.get("lineas", []))
              and len(d.get("lineas", [])) == exp.get("por_procedencia", {}).get(n))
        procedencias[f"{j}:{n}"] = {"estado": estado, "estado_procedencia": p.get("estado"),
                                    "emisiones": p.get("emisiones"), "lineas": len(d.get("lineas", [])),
                                    "lineas_con_resultado_observado": observadas, "coincide": ok}
        if not ok:
            discrepancias.append({"juego": j, "plantilla": f"resultados?procedencia={n}", "estado": estado,
                                  "detalle": json.dumps(procedencias[f"{j}:{n}"])})

por_clase = {}
for f in filas:
    por_clase[f["clase"]] = por_clase.get(f["clase"], 0) + 1
print(json.dumps({"total": len(filas), "por_clase": por_clase, "procedencias": procedencias,
                  "discrepancias": discrepancias, "filas": filas, "destino": f"{HOST}:{PUERTO}"}))
