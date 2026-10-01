"""Demostracion reproducible de la Etapa AE-79, validada localmente como
trabajo preparatorio -NO OPERATIVA.

Escribe expedientes, politicas y capturas sinteticos en un directorio
temporal y ejecuta el comando real
`python -m scripts.auditar_expedientes_cruzados` en un proceso aparte para
cada escenario, con el directorio temporal como directorio de trabajo y
rutas relativas. Comprueba el codigo de salida y el estado entre expedientes
esperados y borra el directorio temporal al terminar.

Uso (desde `backend`):

  python -m tests.demostracion_auditoria_cruzada

Sale con 0 si todos los escenarios dan lo esperado y con 1 si alguno no.
Sin red ni reloj como evidencia; todo el material es de fixture.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.application.ml import auditoria_cruzada as ac
from tests.unit.ml import fixtures_auditoria_cruzada as fa
from tests.unit.ml import fixtures_expediente_portable as fp

BACKEND = Path(__file__).resolve().parents[1]


def escenarios():
    """(nombre, expedientes, capturas, codigo, estado entre expedientes,
    motivos que deben aparecer)."""
    e1, e2, e3, e4 = fa.e1(), fa.e2(), fa.e3(), fa.e4()
    a1 = fa.capturar(e1, "a")
    b1 = fa.capturar(e2, "b")
    a2 = fa.capturar(e2, "a", 2, a1)
    c1 = fa.capturar(e3, "c")
    c4 = fa.capturar(e4, "c")
    return [
        ("dos_capturas_compatibles", {"e1": e1, "e2": e2}, [a1, b1], 0, "compatibles", []),
        ("tercera_captura_extiende_la_historia", {"e1": e1, "e2": e2}, [a1, b1, a2], 0,
         "progresion_demostrable", []),
        ("conflicto_firmado_solo_visible_en_la_auditoria_cruzada", {"e1": e1, "e2": e2, "e3": e3},
         [a1, b1, a2, c1], 1, "contradiccion_comprobada",
         ["discrepancia_entre_firmantes", "omision_comprobable", "acuses_contradictorios_del_canal"]),
        ("protocolos_distintos_incomparables", {"e1": e1, "e4": e4}, [a1, c4], 0, "incomparables", []),
        ("manifiesto_sustituido_frente_a_captura_firmada", {"e1": e1, "e2": fa.e2_sin_un_sello()}, [a1, b1], 4,
         "compatibles", []),
    ]


def comando(expedientes, capturas) -> list:
    """Argumentos del comando real, con rutas relativas al directorio de la
    demostracion."""
    return [*expedientes, "--politica", "politica", "--politica-auditoria", "politica_auditoria",
            *(a for c in capturas for a in ("--capturas", c)), "--formato", "json"]


def ejecutar(raiz: Path) -> list:
    fp.escribir(raiz / "politica", fa.politica_del_verificador())
    fp.escribir(raiz / "politica_auditoria", fa.politica_de_auditoria())
    resultados = []
    for nombre, expedientes, capturas, codigo, estado, motivos in escenarios():
        base = raiz / nombre
        for clave, archivos in expedientes.items():
            fp.escribir(base / clave, archivos)
        fp.escribir(base / "capturas", ac.componer_capturas(capturas))
        argumentos = comando([f"{nombre}/{c}" for c in expedientes], [f"{nombre}/capturas"])
        entorno = {**os.environ, "PYTHONPATH": str(BACKEND), "PYTHONDONTWRITEBYTECODE": "1"}
        proceso = subprocess.run([sys.executable, "-m", "scripts.auditar_expedientes_cruzados", *argumentos],
                                 cwd=raiz, env=entorno, capture_output=True, check=False)
        informe = json.loads(proceso.stdout.decode("utf-8"))
        entre = informe["entre_expedientes"]
        correcto = (proceso.returncode == codigo and entre["estado"] == estado
                    and all(m in entre["motivos"] for m in motivos))
        resultados.append({"escenario": nombre, "comando": " ".join(argumentos), "codigo": proceso.returncode,
                           "codigo_esperado": codigo, "estado": entre["estado"], "estado_esperado": estado,
                           "motivos": entre["motivos"], "resultado": informe["resultado"],
                           "capturas": [c["estado"] for c in informe["capturas"]],
                           "ae78": [f["ae78"]["resultado"] for f in informe["expedientes"] if "ae78" in f],
                           "correcto": correcto})
    return resultados


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ae79-demo-") as temporal:
        resultados = ejecutar(Path(temporal))
    for r in resultados:
        marca = "OK " if r["correcto"] else "ERR"
        print(f"{marca} {r['escenario']}: codigo {r['codigo']} (esperado {r['codigo_esperado']}), "
              f"entre expedientes {r['estado']} (esperado {r['estado_esperado']}), resultado {r['resultado']}")
        print(f"    motivos: {', '.join(r['motivos']) or '-'}; AE-78 individual: {', '.join(r['ae78'])}; "
              f"capturas: {', '.join(r['capturas'])}")
        print(f"    python -m scripts.auditar_expedientes_cruzados {r['comando']}")
    fallidos = [r["escenario"] for r in resultados if not r["correcto"]]
    print(f"demostracion AE-79: {len(resultados) - len(fallidos)}/{len(resultados)} escenarios como se esperaba")
    return 1 if fallidos else 0


if __name__ == "__main__":
    sys.exit(main())
