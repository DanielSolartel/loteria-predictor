"""Demostracion sintetica de Producto 5: catalogo -> comparacion exterior del
modelo combinado -> pesos visibles -> cinco combinaciones por juego ->
simulacion de las dos hipotesis -> repeticion sin recalcular -> verificacion
-> objetivo sintetico en una copia -> seguimiento observado -> interrupcion
y recuperacion.

Trabaja como la aplicacion: entrena, calcula el vector fuente y simula en
procesos trabajadores dedicados (`EjecutorCarterasEnProceso`, con su tiempo
maximo) y comprueba que los hilos numericos de este proceso no cambian.

Usa las RECETAS PREDETERMINADAS y el protocolo completo (6 bloques) sobre
historicos SINTETICOS del tamano real (Baloto, Revancha y ColorLoto
completos y la MiLoto corta), en un directorio temporal, sin PostgreSQL ni
Internet. El resultado del objetivo se anade a una copia sintetica para el
seguimiento. Pasa aunque la uniforme tenga menor perdida: no exige que el
modelo combinado gane.

Uso (desde `backend`):

  python -m tests.demostracion_producto5

Sale con 0 si cada paso da lo esperado y con 1 si alguno no.
"""
from __future__ import annotations

import multiprocessing
import sys
import tempfile
import time
from itertools import combinations
from pathlib import Path

from threadpoolctl import threadpool_info

from app.application.ml import carteras_construccion as cc
from app.application.ml import carteras_ensemble as ce
from app.application.ml import laboratorio_variables as lv
from app.application.use_cases.carteras import JUEGOS, NOMBRES, EjecutorCarterasEnEsteProceso
from app.infrastructure.carteras_trabajador import EjecutorCarterasEnProceso
from tests.unit import fixtures_producto4 as f4
from tests.unit import fixtures_producto5 as f5

ESPERA = 300
CARTERA = {"modelo": ce.ID_ENSEMBLE, "cantidad": cc.CANTIDAD_PREDETERMINADA, "semilla": cc.SEMILLA_PREDETERMINADA,
           "diversidad": "limitada"}


def _paso(numero: int, texto: str, correcto: bool) -> bool:
    print(f"[{'OK' if correcto else 'FALLO'}] {numero}. {texto}", flush=True)
    return correcto


def _hilos():
    return sorted((i["internal_api"], i["num_threads"]) for i in threadpool_info())


def _valida(juego: str, combinaciones: list[dict]) -> bool:
    reglas = lv.REGLAS[juego]
    vistas = set()
    for c in combinaciones:
        if reglas.colores:
            if len(c["pares"]) != 6 or any(not 1 <= n <= 7 for n, _ in c["pares"]):
                return False
        elif len(set(c["numeros"])) != 5 or not all(reglas.rango[0] <= n <= reglas.rango[1] for n in c["numeros"]) \
                or (reglas.superbalota is not None) != ("superbalota" in c):
            return False
        vistas.add(cc.identidad_de_combinacion(c, reglas.colores))
    limite = cc.LIMITE_COINCIDENCIAS_COLORLOTO if reglas.colores else cc.LIMITE_NUMEROS_COMPARTIDOS
    return len(vistas) == len(combinaciones) and all(cc.compartidos(a, b, reglas.colores) <= limite
                                                     for a, b in combinations(combinaciones, 2))


class _Bloqueado(EjecutorCarterasEnEsteProceso):
    def __init__(self, listo, nunca):
        self.listo, self.nunca = listo, nunca

    def fuente(self, *a, **k):
        self.listo.put("calculando")
        self.nunca.wait(ESPERA)
        return super().fuente(*a, **k)


def _generar_y_morir(directorio, listo, nunca):
    """Proceso aparte que se queda a mitad de una cartera (para matarlo). Usa un
    modelo que calcula su vector fuente en el ejecutor (la uniforme no)."""
    e = f5.entorno(Path(directorio), {"MILOTO": 87})
    parametros = {**CARTERA, "modelo": "logistica_regularizada", "semilla": 7}
    e.carteras(ejecutor=_Bloqueado(listo, nunca)).ahora("cartera", ["MILOTO"], parametros, origen="demostracion")


def main() -> int:
    hilos_antes = _hilos()
    with tempfile.TemporaryDirectory() as temporal:
        e = f5.entorno(Path(temporal), f4.TAMANOS_REALES)
        ejecutor = EjecutorCarterasEnProceso()
        s = e.carteras(ejecutor=ejecutor)
        resultados = []

        catalogo = s.catalogo()
        resultados.append(_paso(1, "Catalogo: " + "; ".join(
            f"{NOMBRES[j]} {len(m)} modelos de cartera ({', '.join(ce.COMPONENTES[j])} en el combinado)"
            for j, m in catalogo["modelos_de_cartera"].items()),
            all(ce.ID_ENSEMBLE in m for m in catalogo["modelos_de_cartera"].values())))

        inicio = time.perf_counter()
        comparacion = s.ahora("comparacion", list(JUEGOS), {}, origen="demostracion")
        segundos = time.perf_counter() - inicio
        informes = {j: s.comparacion(r["resultado"]).artefacto for j, r in comparacion["juegos"].items()}
        resultados.append(_paso(2, f"Comparacion exterior con recetas predeterminadas ({segundos:.1f} s): " + "; ".join(
            f"{NOMBRES[j]} {a['muestra_comun']['total_objetivos']} objetivos, "
            f"{a['resumen']['estado'].replace('_', ' ')} (mejor: {a['resumen']['ranking'][0]['id']})"
            for j, a in informes.items()),
            all(r["estado"] in ("terminado", "parcial") for r in comparacion["juegos"].values())
            and all(next(c for c in a["candidatos"] if c["id"] == ce.ID_ENSEMBLE)["estado"] == "completo"
                    for a in informes.values())))

        textos, correcto = [], True
        for j, a in informes.items():
            internos = a["ensemble"]["bloques_internos"]
            ens = next(c for c in a["candidatos"] if c["id"] == ce.ID_ENSEMBLE)
            correcto &= all(len(b["perdidas"]) == 66 and abs(sum(b["pesos"].values()) - 1) < 1e-12 for b in internos)
            textos.append(f"{NOMBRES[j]}: " + " | ".join("/".join(str(n) for n in b["numeradores"]) for b in internos)
                          + f" (uniforme elegida en {a['ensemble']['bloques_que_eligieron_la_uniforme']} de "
                            f"{len(internos)}; exterior {ens['agregado']['diferencia_log_loss']:+.5f} vs uniforme, "
                            f"{ens['veredicto'].replace('_', ' ')})")
        resultados.append(_paso(3, "Pesos por bloque (decimos uniforme/lineal/arboles): " + "; ".join(textos), correcto))

        inicio = time.perf_counter()
        carteras = {}
        for j in JUEGOS:
            r = s.ahora("cartera", [j], CARTERA, origen="demostracion")["juegos"][j]
            carteras[j] = s.cartera(r["resultado"]) if r["estado"] == "terminado" else None
        segundos = time.perf_counter() - inicio
        resultados.append(_paso(4, f"Cinco combinaciones por juego con el modelo combinado ({segundos:.1f} s): " + "; ".join(
            f"{NOMBRES[j]} {' '.join(str(n) for n in g.artefacto['cartera']['combinaciones'][0].get('numeros', []))}"
            f"{' '.join(f'{n}{c[:2]}' for n, c in g.artefacto['cartera']['combinaciones'][0].get('pares', []))}…"
            for j, g in carteras.items() if g),
            all(g is not None and len(g.artefacto["cartera"]["combinaciones"]) == 5
                and _valida(j, g.artefacto["cartera"]["combinaciones"]) for j, g in carteras.items())))

        inicio = time.perf_counter()
        simulaciones = {}
        for j, g in carteras.items():
            r = s.ahora("simulacion", [j], {"cartera": g.identificador, "simulaciones": cs_predeterminadas(),
                                            "semilla": cc.SEMILLA_PREDETERMINADA}, origen="demostracion")["juegos"][j]
            simulaciones[j] = s.simulacion(r["resultado"]).artefacto if r["estado"] == "terminado" else None
        segundos = time.perf_counter() - inicio
        textos, correcto = [], True
        for j, a in simulaciones.items():
            for escenario, r in (a or {}).get("resultados", {}).items():
                e_, u_ = r["carteras"]["elegida"], r["carteras"]["uniforme"]
                correcto &= e_["maximo_de_la_cartera"]["denominador"] == r["simulaciones_efectivas"] == 10000
                correcto &= sum(e_["maximo_de_la_cartera"]["conteos"]) == 10000
                textos.append(f"{NOMBRES[j]}/{escenario}: >=2 {e_['al_menos']['2']['conteo']} vs "
                              f"{u_['al_menos']['2']['conteo']}")
        resultados.append(_paso(5, f"Simulacion de las dos hipotesis, 10000 sorteos ({segundos:.1f} s): "
                                + "; ".join(textos), correcto and all(simulaciones.values())))

        lanzados = ejecutor.lanzados
        inicio = time.perf_counter()
        otra = s.ahora("comparacion", list(JUEGOS), {}, origen="demostracion")
        cartera = s.ahora("cartera", ["BALOTO"], CARTERA, origen="demostracion")["juegos"]["BALOTO"]
        sim = s.ahora("simulacion", ["BALOTO"], {"cartera": carteras["BALOTO"].identificador,
                                                 "simulaciones": cs_predeterminadas(), "semilla": 42})["juegos"]["BALOTO"]
        segundos = time.perf_counter() - inicio
        resultados.append(_paso(6, f"Repeticion ({segundos:.2f} s): comparaciones "
                                   f"{sorted({r['estado'] for r in otra['juegos'].values()})}, cartera {cartera['estado']}, "
                                   f"simulacion {sim['estado']}; trabajadores nuevos {ejecutor.lanzados - lanzados}",
                                all(r["estado"] == "reutilizado" for r in otra["juegos"].values())
                                and cartera["estado"] == sim["estado"] == "reutilizado" and ejecutor.lanzados == lanzados))

        inicio = time.perf_counter()
        vc = s.verificar_cartera(carteras["COLORLOTO"].identificador)
        vs = s.verificar_simulacion(next(iter(s.simulaciones_de_cartera(carteras["MILOTO"].identificador))).identificador)
        vk = s.verificar_comparacion(comparacion["juegos"]["MILOTO"]["resultado"])
        segundos = time.perf_counter() - inicio
        resultados.append(_paso(7, f"Verificacion ({segundos:.1f} s): cartera ColorLoto {vc['integridad']}, "
                                   f"huella {'exacta' if vc['reproduccion']['huella_exacta'] else 'distinta'}, base "
                                   f"{vc['base_actual']['historico_hasta_el_corte']}; simulacion MiLoto "
                                   f"{'exacta' if vs['reproduccion']['huella_exacta'] else 'distinta'}; comparacion "
                                   f"MiLoto {'exacta' if vk['reproduccion']['huella_exacta'] else 'distinta'}",
                                vc["reproduccion"]["huella_exacta"] and vs["reproduccion"]["huella_exacta"]
                                and vk["reproduccion"]["huella_exacta"]
                                and vc["base_actual"]["historico_hasta_el_corte"] == "coincide"))

        nuevo = e.siguiente("MILOTO")[0]
        e.anadir("MILOTO", [nuevo])  # copia sintetica en memoria: el resultado del objetivo
        linea = carteras["MILOTO"].linea
        fila = s.seguimiento("MILOTO")["lineas"][linea]["filas"][0]
        esperado = max(len(set(c["numeros"]) & set(nuevo.numeros))
                       for c in carteras["MILOTO"].artefacto["cartera"]["combinaciones"])
        resultados.append(_paso(8, f"Objetivo sintetico {nuevo.numero_sorteo} ({' '.join(map(str, nuevo.numeros))}) "
                                   f"anadido a la copia de MiLoto", nuevo.numero_sorteo == carteras["MILOTO"].objetivo))
        resultados.append(_paso(9, f"Seguimiento observado: {fila['tipo']}, {fila['estado']}, maximo de la cartera "
                                   f"{fila['aciertos']['maximo']} de 5 (por linea "
                                   f"{[x['aciertos'] for x in fila['aciertos']['por_linea']]})",
                                fila["estado"] == "incluido" and fila["tipo"] == "seguimiento"
                                and fila["aciertos"]["maximo"] == esperado))

        contexto = multiprocessing.get_context("spawn")
        listo, nunca = contexto.Queue(), contexto.Event()
        interrumpido = Path(temporal) / "interrumpido"
        proceso = contexto.Process(target=_generar_y_morir, args=(str(interrumpido), listo, nunca))
        proceso.start()
        try:
            listo.get(timeout=ESPERA)
        finally:
            proceso.kill()
            proceso.join(ESPERA)
        otro = f5.entorno(interrumpido, {"MILOTO": 87}).carteras()
        marcadas = otro.recuperar()
        estado_marcada = otro.consultar_ejecucion(marcadas[0])["estado"] if marcadas else "-"
        repetida = otro.ahora("cartera", ["MILOTO"], {**CARTERA, "modelo": "logistica_regularizada", "semilla": 7})
        resultados.append(_paso(10, f"Interrupcion: proceso detenido a mitad de una cartera; recuperadas {len(marcadas)}"
                                    f" ejecuciones ({estado_marcada}); "
                                    f"al repetir: {repetida['juegos']['MILOTO']['estado']}",
                                 len(marcadas) == 1 and repetida["juegos"]["MILOTO"]["estado"] == "terminado"))

        resultados.append(_paso(11, f"Aislamiento: {ejecutor.lanzados} procesos trabajadores (maximo simultaneo "
                                    f"{ejecutor.maximo_simultaneo}); hilos de este proceso antes {hilos_antes} y "
                                    f"despues {_hilos()}",
                                 _hilos() == hilos_antes and ejecutor.maximo_simultaneo == 1))
        print("Datos sinteticos: ninguna cifra corresponde a sorteos reales.")
        return 0 if all(resultados) else 1


def cs_predeterminadas() -> int:
    from app.application.ml import carteras_simulacion as cs
    return cs.SIMULACIONES_PREDETERMINADAS


if __name__ == "__main__":
    sys.exit(main())
