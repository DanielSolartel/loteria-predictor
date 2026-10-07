"""Demostracion sintetica completa de Producto 3: actualizacion ->
generacion -> resultado nuevo -> rendimiento.

Todo ocurre en un directorio temporal, con historicos SINTETICOS en memoria
y un importador falso (sin Internet ni PostgreSQL). Usa el mismo caso de
uso que el panel y el comando. Los numeros que imprime no son sorteos
reales.

Uso (desde `backend`):

  python -m tests.demostracion_producto3

Sale con 0 si cada paso da lo esperado y con 1 si alguno no.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from app.application.use_cases.pronostico_experimental import JUEGOS
from app.application.use_cases.rendimiento import ConsultarRendimiento
from tests.unit import fixtures_producto3 as f3


def _paso(numero: int, texto: str, correcto: bool) -> bool:
    print(f"[{'OK' if correcto else 'FALLO'}] {numero}. {texto}")
    return correcto


def main() -> int:
    with tempfile.TemporaryDirectory() as temporal:
        e = f3.entorno(Path(temporal))
        operacion = e.operacion()
        resultados = []

        primera = operacion.ejecutar_ahora(JUEGOS, "local", "demostracion")
        resultados.append(_paso(1, "Generar con datos locales (4 juegos): " + ", ".join(
            f"{j} -> objetivo {r['pronostico']['objetivo']}" for j, r in primera["juegos"].items()),
            primera["estado"] == "exito"))

        repetida = operacion.ejecutar_ahora(JUEGOS, "local", "demostracion")
        resultados.append(_paso(2, "Repetir sin datos nuevos reutiliza los cuatro pronosticos",
                                all(r["pronostico"]["reutilizado"] for r in repetida["juegos"].values())))

        e.importador.pendientes["MILOTO"] = e.siguiente("MILOTO")
        actualizada = operacion.ejecutar_ahora(["MILOTO"], "actualizar", "demostracion")
        m = actualizada["juegos"]["MILOTO"]
        resultados.append(_paso(3, f"Actualizar datos y generar (MiLoto): {m['sincronizacion']['sorteos_nuevos']} sorteo "
                                   f"nuevo, ultimo {m['ultimo_antes']['ultimo_sorteo']} -> "
                                   f"{m['ultimo_despues']['ultimo_sorteo']}, nuevo objetivo {m['pronostico']['objetivo']}",
                                actualizada["estado"] == "exito" and m["pronostico"]["objetivo"] == 86))
        resultados.append(_paso(4, f"El pronostico del objetivo 85 ya tiene resultado: {m['resultados']['observados']} "
                                   "observado(s)", m["resultados"]["observados"] == 1))

        rendimiento = ConsultarRendimiento(e.almacen, e.juegos, e.resultados).ejecutar("MILOTO")
        seguimiento = rendimiento["por_tipo"]["seguimiento"]
        fila = next(f for f in rendimiento["filas"] if f["objetivo"] == 85)
        resultados.append(_paso(5, f"Rendimiento MiLoto (seguimiento): {seguimiento['incluidos']} incluido, "
                                   f"{seguimiento['pendientes']} pendiente; objetivo 85: {fila['aciertos']} de "
                                   f"{fila['de']}, Log Loss {fila['metricas']['log_loss']:.5f} frente a "
                                   f"{fila['metricas']['log_loss_uniforme']:.5f} (uniforme)",
                                seguimiento["incluidos"] == 1 and seguimiento["pendientes"] == 1))

        e.importador.fallar["COLORLOTO"] = "origen inaccesible (simulado)"
        parcial = operacion.ejecutar_ahora(JUEGOS, "actualizar", "demostracion")
        resultados.append(_paso(6, "Si el origen de ColorLoto falla: estado global "
                                   f"{parcial['estado']}, ColorLoto {parcial['juegos']['COLORLOTO']['estado']}",
                                parcial["estado"] == "parcial" and parcial["juegos"]["COLORLOTO"]["pronostico"] is None))
        print("Datos sinteticos: ninguna cifra corresponde a sorteos reales.")
        return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
