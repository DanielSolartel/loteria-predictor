"""Demostracion sintetica de Producto 6 en los cuatro juegos: emisiones reales
de operacion diaria, laboratorio y carteras con el objetivo todavia ausente ->
consulta (pendientes, sin resultados de seguimiento) -> informe guardado ->
llega el resultado -> la consulta se actualiza -> comparacion de las tres
procedencias sobre los objetivos comunes -> calibracion -> informe nuevo ->
verificacion de los dos (integridad, reproduccion, consulta actual) ->
exportacion completa -> ninguna emision original cambio.

Incluye al menos un caso en que la uniforme tiene menor perdida y se muestra
como tal en la pagina. No exige que ningun modelo gane.

Historicos SINTETICOS y entrenamientos reducidos en un directorio temporal,
sin PostgreSQL ni Internet. Ninguna cifra corresponde a sorteos reales.

Uso (desde `backend`):

  python -m tests.demostracion_producto6

Sale con 0 si cada paso da lo esperado y con 1 si alguno no.
"""
from __future__ import annotations

import csv
import io
import sys
import tempfile
from pathlib import Path

from app.application.use_cases.resultados import JUEGOS, NOMBRES, SLUGS
from tests.unit import fixtures_producto6 as f6


def _paso(numero: int, texto: str, correcto: bool) -> bool:
    print(f"[{'OK' if correcto else 'FALLO'}] {numero}. {texto}", flush=True)
    return correcto


def main() -> int:
    resultados = []
    with tempfile.TemporaryDirectory(prefix="p6-") as tmp:
        e = f6.entorno(Path(tmp))
        e.poblar(JUEGOS)
        centro = e.centro()
        originales = {d: f6.foto(Path(tmp) / d) for d in ("p3", "laboratorio", "carteras")}

        indice = centro.indice()
        pendientes = {j["juego"]: j["seguimiento"]["pendiente"] for j in indice["juegos"]}
        resultados.append(_paso(1, "Indice: ultimo sorteo cargado y emisiones pendientes por juego: " + ", ".join(
            f"{NOMBRES[j['juego']]} {j['base']['ultimo_sorteo']} ({j['base']['fecha']}) -> {pendientes[j['juego']]}"
            for j in indice["juegos"]),
            all(j["base"]["ultimo_sorteo"] for j in indice["juegos"]) and all(n >= 2 for n in pendientes.values())))

        antes = {j: centro.consultar(j) for j in JUEGOS}
        resultados.append(_paso(2, "Objetivo todavia ausente: sin resultados de seguimiento en los cuatro juegos, "
                                   "tipo seguimiento sin cambio automatico",
                                all(v["sin_resultados_de_seguimiento"] and v["filtros"]["tipo"] == "seguimiento"
                                    and v["comparacion"]["estado"] == "sin_muestra_comun" for v in antes.values())))
        previos = {j: centro.guardar_informe(j, origen="demostracion")["clave"] for j in JUEGOS}

        for j in JUEGOS:
            e.llega_el_resultado(j)
        despues = {j: centro.consultar(j, completa=True) for j in JUEGOS}
        incluidos = {j: sum(1 for f in v["emisiones_de_la_seleccion"] if f["estado"] == "incluido")
                     for j, v in despues.items()}
        resultados.append(_paso(3, "Llega el resultado: emisiones incluidas por juego " + ", ".join(
            f"{NOMBRES[j]} {n}" for j, n in incluidos.items()),
            all(n == len(despues[j]["seleccion"]) >= 2 for j, n in incluidos.items())))

        print("    Comparacion directa (diferencia de Log Loss = modelo - uniforme; negativa = menor perdida):")
        uniforme_mejor = []
        for j, v in despues.items():
            c = v["comparacion"]
            for f in c["clasificacion"]:
                print(f"      {NOMBRES[j]:<16} {f['linea']:<58} {f['diferencia']:+.5f} {f['veredicto']}")
                if f["veredicto"] == "la_uniforme_fue_mejor":
                    uniforme_mejor.append((j, f["linea"]))
        resultados.append(_paso(4, "Comparacion de las procedencias sobre los objetivos comunes, con la uniforme en "
                                   "la clasificacion",
                                all(v["comparacion"]["estado"] == "con_muestra_comun"
                                    and len({k.split(':')[0] for k in v["seleccion"]}) == 3
                                    and any(f["linea"] == "uniforme" for f in v["comparacion"]["clasificacion"])
                                    for v in despues.values())))

        c = f6.cliente(e, centro=centro)
        try:
            juego, linea = uniforme_mejor[0] if uniforme_mejor else (None, None)
            html = c.get(f"/resultados/{SLUGS[juego]}").text if juego else ""
            resultados.append(_paso(5, f"La uniforme gana en {len(uniforme_mejor)} linea(s) y se muestra como tal "
                                       f"(p. ej. {NOMBRES.get(juego, '-')}: {linea})",
                                    bool(uniforme_mejor) and "la uniforme fue mejor" in html
                                    and "Uniforme (referencia)" in html))
            cal = despues["COLORLOTO"]["calibracion"]
            pares = [d["diagnosticos"].get("pares") for d in cal.values()]
            numeros = despues["BALOTO"]["calibracion"]
            resultados.append(_paso(6, "Calibracion: ColorLoto como fraccion de balotas, Baloto con superbalota "
                                       "aparte; intervalos vacios sin valor",
                                    all(p and "fracción de balotas" in p["etiqueta_observado"] for p in pares)
                                    and all({"numeros", "superbalota"} <= set(d["diagnosticos"])
                                            for d in numeros.values())
                                    and any(i["probabilidad_media"] is None for p in pares for i in p["intervalos"])))

            nuevos = {j: centro.guardar_informe(j, origen="demostracion") for j in JUEGOS}
            repetidos = {j: centro.guardar_informe(j, origen="demostracion") for j in JUEGOS}
            v_prev = {j: centro.verificar_informe(previos[j]) for j in JUEGOS}
            v_new = {j: centro.verificar_informe(nuevos[j]["clave"]) for j in JUEGOS}
            resultados.append(_paso(7, "Informes: el anterior sigue integro y reproducible pero la consulta cambio; el "
                                       "nuevo coincide; repetirlo lo reutiliza",
                                    all(v_prev[j]["integridad"] == "correcta" and v_prev[j]["reproduccion"]["exacta"]
                                        and v_prev[j]["base_actual"]["estado"] == "cambio"
                                        and v_new[j]["reproduccion"]["exacta"]
                                        and v_new[j]["base_actual"]["estado"] == "coincide"
                                        and repetidos[j]["reutilizado"] and repetidos[j]["clave"] == nuevos[j]["clave"]
                                        for j in JUEGOS)))

            filas = list(csv.reader(io.StringIO(c.get("/resultados/miloto/exportar.csv").text)))
            api = c.get("/api/resultados/MILOTO", params={"por_pagina": 1}).json()
            resultados.append(_paso(8, f"Exportacion CSV completa: {len(filas) - 1} filas aunque la pagina muestre "
                                       f"{len(api['historial']['filas'])}",
                                    len(filas) - 1 == api["historial"]["total"] > 1))
        finally:
            f6.limpiar()

        resultados.append(_paso(9, "Ninguna emision original de Productos 1-5 cambio (huella de cada archivo)",
                                {d: f6.foto(Path(tmp) / d) for d in originales} == originales))
        print("Datos sinteticos: ninguna cifra corresponde a sorteos reales. Producto 6 es experimental_no_acreditado; "
              "AUTORIZA_EVALUACION = False.")
        return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
