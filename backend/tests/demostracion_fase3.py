"""Demostracion sintetica de la Fase 3 (modelos registrados) en los cuatro
juegos: comparar (con Random Forest y Extra Trees) -> entrenar y guardar una
version -> repetir (misma version) -> recargar en otra instancia ("reinicio")
-> verificar -> generar sin reentrenar -> elegirla en la configuracion de
carteras -> carteras configuradas con el modelo congelado -> resultado
observado.

Entrena como la aplicacion: en procesos trabajadores dedicados con tiempo
maximo. Usa las RECETAS PREDETERMINADAS sobre historicos SINTETICOS del tamano
real, en un directorio temporal, sin PostgreSQL ni Internet. No exige que
ningun modelo gane a la uniforme: la comparacion frente a la uniforme se
informa tal cual.

Uso (desde `backend`):

  python -m tests.demostracion_fase3

Sale con 0 si cada paso da lo esperado y con 1 si alguno no.
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

from app.application.ml import laboratorio_evaluacion as le
from app.application.use_cases.laboratorio import JUEGOS, NOMBRES
from app.infrastructure.carteras_trabajador import EjecutorCarterasEnProceso
from app.infrastructure.laboratorio_trabajador import EjecutorEnProceso
from tests.unit import fixtures_fase3 as f3
from tests.unit import fixtures_producto4 as f4

MODELOS = {"BALOTO": "random_forest_clasificador", "BALOTO_REVANCHA": "extra_trees_clasificador",
           "MILOTO": "random_forest_clasificador", "COLORLOTO": "extra_trees_poisson"}


def _paso(numero: int, texto: str, correcto: bool) -> bool:
    print(f"[{'OK' if correcto else 'FALLO'}] {numero}. {texto}")
    return correcto


def main() -> int:
    with tempfile.TemporaryDirectory() as temporal:
        e = f3.entorno(Path(temporal), f4.TAMANOS_REALES)
        ejecutor = EjecutorEnProceso(tiempo_maximo=1800)
        lab = e.laboratorio(ejecutor=ejecutor)
        resultados = []

        inicio = time.perf_counter()
        comparacion = {j: lab.comparar_ahora([j], le.Protocolo(bloques=3), "demostracion",
                                             corte=e.corte(j, 5))["juegos"][j] for j in JUEGOS}
        textos = []
        for j, r in comparacion.items():
            informe = lab.experimento(r["experimento"]).artefacto
            bosques = [c for c in informe["candidatos"] if c["familia"] == "bosques"]
            textos.append(f"{NOMBRES[j]} {len(informe['candidatos'])} candidatos, bosques "
                          + ", ".join(f"{c['id']} {c['estado']} dif. LL {c['agregado']['diferencia_log_loss']:+.4f}"
                                      for c in bosques))
        resultados.append(_paso(1, f"Comparar con corte explicito ({time.perf_counter() - inicio:.1f} s): "
                                + "; ".join(textos),
                                all(r["estado"] in ("terminado", "parcial") for r in comparacion.values())))

        registrados = {j: lab.entrenar_ahora(comparacion[j]["experimento"], MODELOS[j], "demostracion")["juegos"][j]
                       for j in JUEGOS}
        resultados.append(_paso(2, "Entrenar y guardar: " + "; ".join(
            f"{NOMBRES[j]} {MODELOS[j]} v{r['numero']} ({r['estado']})" for j, r in registrados.items()),
            all(r["estado"] == "terminado" and r["numero"] == 1 for r in registrados.values())))

        repetidos = {j: lab.entrenar_ahora(comparacion[j]["experimento"], MODELOS[j], "demostracion")["juegos"][j]
                     for j in JUEGOS}
        resultados.append(_paso(3, "Repetir la misma entrada reutiliza la version (sin otra version)",
                                all(r["estado"] == "reutilizado" and r["numero"] == 1 for r in repetidos.values())))

        reiniciado = e.laboratorio(ejecutor=EjecutorEnProceso(tiempo_maximo=1800))  # otra instancia: "reinicio"
        verificados = {j: reiniciado.verificar_modelo(r["modelo_registrado"]) for j, r in registrados.items()}
        resultados.append(_paso(4, "Recargar y verificar en otra instancia: " + "; ".join(
            f"{NOMBRES[j]} {v['integridad']}, {v['carga']['clase']}, control "
            f"{'exacto' if v['reproduccion']['exacta'] else 'distinto'}" for j, v in verificados.items()),
            all(v["reproduccion"]["exacta"] for v in verificados.values())))

        generados = {j: reiniciado.generar_con_modelo(r["modelo_registrado"], origen="demostracion")
                     for j, r in registrados.items()}
        resultados.append(_paso(5, "Generar con el modelo cargado, sin reentrenar: " + "; ".join(
            f"{NOMBRES[j]} objetivo {g.objetivo} ({g.linea})" for j, g in generados.items()),
            all(g.artefacto["identidad"]["modelo_registrado"]["numero"] == 1 for g in generados.values())))

        carteras = e.carteras(ejecutor=EjecutorCarterasEnProceso(600))
        for j, r in registrados.items():
            carteras.configurar(j, MODELOS[j], 3, "libre", 42, registrado=r["modelo_registrado"])
        diaria = carteras.ahora("carteras_configuradas", list(JUEGOS), origen="demostracion")
        congeladas = {j: carteras.cartera(r["resultado"]).artefacto["fuente"]["detalle"].get("modelo_registrado")
                      for j, r in diaria["juegos"].items() if r["estado"] == "terminado"}
        resultados.append(_paso(6, "Elegir la version en la configuracion y generar carteras configuradas: "
                                + ", ".join(f"{NOMBRES[j]} {diaria['juegos'][j]['estado']}" for j in JUEGOS),
                                diaria["estado"] == "exito"
                                and all(congeladas[j] == registrados[j]["modelo_registrado"] for j in JUEGOS)))

        e.anadir("MILOTO", e.siguiente("MILOTO"))
        s = reiniciado.seguimiento("MILOTO", generados["MILOTO"].linea)["lineas"][generados["MILOTO"].linea]
        fila = next(f for f in s["filas"] if f["objetivo"] == generados["MILOTO"].objetivo)
        resultados.append(_paso(7, f"Resultado observado (MiLoto, sorteo sintetico {fila['objetivo']}): "
                                   f"{fila['estado']}, {fila['coincidencias']['numeros']} de 5, Log Loss "
                                   f"{fila['metricas']['log_loss']:.5f} frente a {fila['metricas']['log_loss_uniforme']:.5f}",
                                fila["estado"] == "incluido"))
        print("Datos sinteticos: ninguna cifra corresponde a sorteos reales. Finalizacion tecnica, no ventaja "
              "predictiva acreditada.")
        return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
