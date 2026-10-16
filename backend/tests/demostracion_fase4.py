"""Demostracion sintetica de la Fase 4 (predicciones explicables y fiabilidad
observada) en los cuatro juegos: elegir la configuracion (Baloto con una
version registrada) -> generar con el caso de uso comun (cartera de Producto 5
+ explicacion) -> repetir (misma cartera y misma explicacion) -> cinco
combinaciones sin cambiar la configuracion -> rankings con sus unidades,
importancias del estimador persistido y reproduccion exacta -> consultar sin
escribir -> resultados observados y fiabilidad con su intervalo -> sin fuga
de informacion en el corte.

Las importancias de la version registrada se leen en el proceso trabajador
real del laboratorio, con la carga restringida. Historicos SINTETICOS en un
directorio temporal, sin PostgreSQL ni Internet. No exige que ningun modelo
gane a la uniforme: las cifras se informan tal cual.

Uso (desde `backend`):

  python -m tests.demostracion_fase4

Sale con 0 si cada paso da lo esperado y con 1 si alguno no.
"""
from __future__ import annotations

import dataclasses
import sys
import tempfile
import time
from pathlib import Path

from app.infrastructure.laboratorio_trabajador import EjecutorEnProceso
from tests.unit import fixtures_fase4 as f4
from tests.unit import fixtures_producto4 as p4

MODELOS = {"BALOTO": "random_forest_clasificador", "BALOTO_REVANCHA": "logistica_regularizada",
           "MILOTO": "logistica_regularizada", "COLORLOTO": "uniforme_paleta"}
CICLOS = 32


def _paso(numero: int, texto: str, correcto: bool) -> bool:
    print(f"[{'OK' if correcto else 'FALLO'}] {numero}. {texto}")
    return correcto


def _reemplazar_posteriores(e, juego: str, despues_de: int, semilla: int) -> None:
    j = e.juegos.obtener_por_codigo(juego)
    destino = e.resultados.colorloto if juego == "COLORLOTO" else e.resultados.numericos
    viejos = [r for r in destino[j.id] if r.numero_sorteo > despues_de]
    nuevos = p4.historico(juego, len(viejos), semilla=semilla)
    cambio = {v.numero_sorteo: dataclasses.replace(n, numero_sorteo=v.numero_sorteo, fecha=v.fecha)
              for v, n in zip(viejos, nuevos)}
    destino[j.id] = [cambio.get(r.numero_sorteo, r) for r in destino[j.id]]


def main() -> int:
    with tempfile.TemporaryDirectory() as temporal:
        e = f4.entorno(Path(temporal))
        ejecutor = EjecutorEnProceso(tiempo_maximo=1800)
        lab = e.laboratorio(ejecutor=ejecutor)
        resultados = []

        r = e.registrar(lab, "BALOTO", MODELOS["BALOTO"])
        for juego, modelo in MODELOS.items():
            e.configurar(juego, modelo, cantidad=3,
                         registrado=r["modelo_registrado"] if juego == "BALOTO" else None)
        carteras = e.carteras()
        centro = e.centro(carteras, ejecutor=ejecutor)
        resultados.append(_paso(1, f"Configuracion elegida en los cuatro juegos (Baloto con la version registrada "
                                   f"{r['numero']})", all(centro.consultar(j)["configuracion"]["estado"] == "vigente"
                                                          for j in MODELOS)))

        inicio = time.perf_counter()
        generados = {j: centro.ahora(j, origen="demostracion")["prediccion"] for j in MODELOS}
        resultados.append(_paso(2, f"Generar con el caso de uso comun ({time.perf_counter() - inicio:.1f} s): "
                                + "; ".join(f"{j} {p['estado']}, cartera {p['cartera']['estado']}, explicacion "
                                            f"{p['explicacion']['estado']}" for j, p in generados.items()),
                                all(p["estado"] == "exito" for p in generados.values())))

        repetidos = {j: centro.ahora(j, origen="demostracion")["prediccion"] for j in MODELOS}
        resultados.append(_paso(3, "Repetir la misma entrada reutiliza la cartera y la explicacion",
                                all(repetidos[j]["cartera"]["clave"] == generados[j]["cartera"]["clave"]
                                    and repetidos[j]["explicacion"]["estado"] == "reutilizada" for j in MODELOS)))

        antes = carteras.configuracion_vigente("MILOTO").identificador
        cinco = centro.ahora("MILOTO", "cinco", "demostracion")["prediccion"]
        resultados.append(_paso(4, f"Cinco combinaciones ({cinco['cartera']['linea']}) sin cambiar la configuracion",
                                cinco["estado"] == "exito" and cinco["solicitud"]["combinaciones"] == 5
                                and carteras.configuracion_vigente("MILOTO").identificador == antes))

        b = centro.consultar("BALOTO")["prediccion"]
        c = centro.consultar("COLORLOTO")["prediccion"]
        imp = b["explicacion"]["importancias"]
        mayor = max(imp["valores"], key=lambda v: v["valor"])
        resultados.append(_paso(5, f"Baloto: {b['rankings']['numeros']['denominador']}, superbalota aparte "
                                   f"({b['rankings']['superbalota']['denominador']}); importancias del "
                                   f"{imp['estimador']} persistido (mayor: {mayor['variable']} {mayor['valor']:.3f}); "
                                   f"ColorLoto: {c['rankings']['pares']['denominador']}, "
                                   f"{c['rankings']['numeros']['denominador']}, reproduccion exacta",
                                imp["estado"] == "disponible" and ejecutor.lanzados >= 2
                                and c["rankings"]["numeros"]["universo"] == 7
                                and b["reproduccion"]["exacta"] and c["reproduccion"]["exacta"]))

        foto = f4.arbol(e.raiz)
        centro.indice()
        for j in MODELOS:
            centro.consultar(j)
            centro.fiabilidad(j)
        resultados.append(_paso(6, "Consultar el indice, las predicciones y la fiabilidad no escribe nada",
                                f4.arbol(e.raiz) == foto))

        inicio = time.perf_counter()
        for k in range(CICLOS):
            e.anadir("BALOTO", e.siguiente("BALOTO", semilla=500 + k))
            centro.ahora("BALOTO", origen="demostracion")
        fi = centro.fiabilidad("BALOTO")
        seg = fi["lineas"][0]["evaluaciones"][0]
        ll = seg["componentes"]["numeros"]["metricas"]["diferencia_log_loss"]
        resultados.append(_paso(7, f"{CICLOS} resultados observados ({time.perf_counter() - inicio:.1f} s): seguimiento "
                                   f"{seg['estado']}, {seg['muestra']['sorteos']} sorteos, delta Log Loss "
                                   f"{ll['media']:+.5f} [{ll['intervalo'][0]:+.5f}, {ll['intervalo'][1]:+.5f}] "
                                   f"(bloque {ll['bloque']}); receta en su informe: {fi['receta']['estado']}",
                                seg["estado"] == "estimable" and ll["intervalo"] is not None
                                and fi["receta"]["estado"] in ("estimable", "muestra_insuficiente")))

        historial = centro.consultar("BALOTO")["historial"]
        elegida = centro.consultar("BALOTO", historial[len(historial) // 2]["clave"])["prediccion"]
        corte = elegida["datos"]["corte"]
        a = (elegida["explicacion"], centro.fiabilidad("BALOTO", hasta=corte)["lineas"])
        _reemplazar_posteriores(e, "BALOTO", corte, semilla=9999)
        b2 = (centro.consultar("BALOTO", elegida["clave"])["prediccion"]["explicacion"],
              centro.fiabilidad("BALOTO", hasta=corte)["lineas"])
        resultados.append(_paso(8, f"Cambiar los sorteos posteriores al corte {corte} no cambia la explicacion ni la "
                                   "evidencia en ese corte", a == b2))
        print("Datos sinteticos: ninguna cifra corresponde a sorteos reales. Siguen experimental_no_acreditado, el "
              "NO-GO de AE-39 y AUTORIZA_EVALUACION = False; ninguna cifra es un nivel de confianza.")
        return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
