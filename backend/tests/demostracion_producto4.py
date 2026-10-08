"""Demostracion sintetica de Producto 4: catalogo -> comparacion ->
generacion -> repeticion -> verificacion -> seguimiento -> aislamiento y
recuperacion.

Entrena como la aplicacion: en procesos trabajadores dedicados
(`EjecutorEnProceso`). Comprueba que los hilos numericos de este proceso no
cambian y que un trabajador interrumpido no publica nada.

Usa las RECETAS PREDETERMINADAS (no el perfil reducido de algunas pruebas)
sobre historicos SINTETICOS del tamano real (Baloto, Revancha y ColorLoto
completos y la MiLoto corta), en un directorio temporal, sin PostgreSQL ni
Internet. El resultado del objetivo se anade a una copia sintetica para
comprobar el seguimiento. No exige que ningun modelo gane a la uniforme.

Uso (desde `backend`):

  python -m tests.demostracion_producto4

Sale con 0 si cada paso da lo esperado y con 1 si alguno no.
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

from threadpoolctl import threadpool_info

from app.application.ml import laboratorio_evaluacion as le
from app.application.use_cases.laboratorio import JUEGOS, NOMBRES
from app.infrastructure.laboratorio_trabajador import EjecutorEnProceso
from tests.unit import fixtures_producto4 as f4

NUEVOS = {"BALOTO": "hgb_clasificador", "BALOTO_REVANCHA": "logistica_regularizada",
          "MILOTO": "logistica_regularizada", "COLORLOTO": "hgb_poisson"}


def _paso(numero: int, texto: str, correcto: bool) -> bool:
    print(f"[{'OK' if correcto else 'FALLO'}] {numero}. {texto}")
    return correcto


def _hilos():
    return sorted((i["internal_api"], i["num_threads"]) for i in threadpool_info())


def main() -> int:
    hilos_antes = _hilos()
    with tempfile.TemporaryDirectory() as temporal:
        e = f4.entorno(Path(temporal), f4.TAMANOS_REALES)
        ejecutor = EjecutorEnProceso()
        lab = e.laboratorio(ejecutor=ejecutor)
        resultados = []

        catalogo = lab.catalogo()
        resultados.append(_paso(1, "Catalogo: " + "; ".join(
            f"{NOMBRES[j]} {len(c)} candidatos ({sum(x['tipo'] == 'modelo_nuevo' for x in c)} nuevos)"
            for j, c in catalogo["juegos"].items()),
            all(sum(x["tipo"] == "modelo_nuevo" for x in c) == 2 for c in catalogo["juegos"].values())))

        inicio = time.perf_counter()
        comparacion = lab.comparar_ahora(JUEGOS, origen="demostracion")
        segundos = time.perf_counter() - inicio
        resumen = {j: r for j, r in comparacion["juegos"].items()}
        resultados.append(_paso(2, f"Comparacion de los cuatro juegos en {segundos:.1f} s: " + "; ".join(
            f"{NOMBRES[j]} {r['estado']} ({r['resumen']})" for j, r in resumen.items()),
            comparacion["estado"] == "exito"))

        generados = {}
        for j in JUEGOS:
            generados[j] = lab.generar(resumen[j]["experimento"], NUEVOS[j])
        texto = "; ".join(f"{NOMBRES[j]} {NUEVOS[j]} -> objetivo {g.objetivo}: " + (
            " ".join(f"{p['numero']}{p['color'][0]}" for p in g.artefacto["pronostico"]["pares"]) if j == "COLORLOTO"
            else " ".join(map(str, g.artefacto["pronostico"]["numeros_sugeridos"]))) for j, g in generados.items())
        resultados.append(_paso(3, "Generar con el modelo elegido: " + texto,
                                all(not g.reutilizado for g in generados.values())))

        repetidos = [lab.generar(resumen[j]["experimento"], NUEVOS[j]) for j in JUEGOS]
        otra = lab.comparar_ahora(["MILOTO"], origen="demostracion")["juegos"]["MILOTO"]
        resultados.append(_paso(4, "Repetir la misma entrada devuelve los mismos pronosticos y el mismo informe",
                                all(r.reutilizado and r.identificador == generados[j].identificador
                                    for r, j in zip(repetidos, JUEGOS)) and otra["estado"] == "reutilizado"))

        verificacion = lab.verificar_pronostico(generados["MILOTO"].identificador)
        resultados.append(_paso(5, f"Verificar (MiLoto): integridad {verificacion['integridad']}, reproduccion "
                                   f"{'exacta' if verificacion['reproduccion']['huella_exacta'] else 'distinta'}, "
                                   f"base actual {verificacion['base_actual']['estado']}",
                                verificacion["integridad"] == "correcta" and verificacion["reproduccion"]["huella_exacta"]))

        e.anadir("MILOTO", e.siguiente("MILOTO"))
        s = lab.seguimiento("MILOTO")["lineas"][generados["MILOTO"].linea]
        fila = s["filas"][0]
        resultados.append(_paso(6, f"Seguimiento (MiLoto, resultado sintetico del objetivo {fila['objetivo']}): "
                                   f"{fila['estado']}, {fila['coincidencias']['numeros']} de 5 aciertos, Log Loss "
                                   f"{fila['metricas']['log_loss']:.5f} frente a {fila['metricas']['log_loss_uniforme']:.5f}",
                                fila["estado"] == "incluido" and fila["tipo"] == "seguimiento"))

        resultados.append(_paso(7, f"Aislamiento: {ejecutor.lanzados} procesos trabajadores; hilos numericos de este "
                                   f"proceso antes {hilos_antes} y despues {_hilos()}",
                                _hilos() == hilos_antes and ejecutor.lanzados > 0))

        roto = e.laboratorio(ejecutor=EjecutorEnProceso(al_lanzar=lambda proceso: proceso.kill()))
        e.anadir("COLORLOTO", e.siguiente("COLORLOTO"))
        caida = roto.comparar_ahora(["COLORLOTO"], le.Protocolo(bloques=1, perfil="reducido"), origen="demostracion")
        repetida = lab.comparar_ahora(["COLORLOTO"], le.Protocolo(bloques=1, perfil="reducido"), origen="demostracion")
        resultados.append(_paso(8, f"Trabajador interrumpido: {caida['juegos']['COLORLOTO']['estado']} sin publicar; "
                                   f"al repetir: {repetida['juegos']['COLORLOTO']['estado']}",
                                caida["juegos"]["COLORLOTO"]["estado"] == "fallo"
                                and repetida["juegos"]["COLORLOTO"]["estado"] == "terminado"))
        print("Datos sinteticos: ninguna cifra corresponde a sorteos reales.")
        return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
