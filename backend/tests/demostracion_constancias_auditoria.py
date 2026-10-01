"""Demostracion reproducible de la Etapa AE-80, validada localmente como
trabajo preparatorio -NO OPERATIVA.

Escribe en un directorio temporal expedientes, capturas, politicas y
constancias sinteticos y ejecuta el comando real
`python -m scripts.verificar_constancias_auditoria` en un proceso aparte
para cada escenario, con el directorio temporal como directorio de trabajo
y rutas relativas. Comprueba el codigo de salida y los motivos esperados y
borra el directorio temporal al terminar.

Uso (desde `backend`):

  python -m tests.demostracion_constancias_auditoria

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
from app.application.ml import constancias_auditoria as ca
from tests.unit.ml import fixtures_constancias_auditoria as fc
from tests.unit.ml import fixtures_expediente_portable as fp

BACKEND = Path(__file__).resolve().parents[1]


def escenarios():
    """(nombre, estado presentado, constancias, politica de constancias,
    codigo esperado, motivos que deben aparecer)."""
    x1 = fc.constancia("s1")
    x2 = fc.constancia("s2", "x", 2, x1)
    rama = fc.constancia("s1", "x", 2, x1)
    informe_falso = fc.constancia("s1", sha256_informe_ae79="0" * 64)
    y_en_desacuerdo = fc.constancia("s1", "y", resultado_ae79={"resultado": "contradiccion_comprobada",
                                                               "entre_expedientes": "contradiccion_comprobada"})
    return [
        ("continuidad_valida", "s2", [x1, x2], "politica_constancias", 0, ["coincide"]),
        ("informe_sustituido", "s1", [informe_falso], "politica_constancias", 4, ["informe_no_coincide"]),
        ("expediente_sustituido", "sustituido", [x1], "politica_constancias", 4,
         ["entrada_atestada_no_presentada", "entrada_presentada_no_atestada"]),
        ("bifurcacion_firmada", "s2", [x1, x2, rama], "politica_constancias", 1, ["bifurcacion_firmada"]),
        ("discrepancia_entre_firmantes", "s1", [x1, y_en_desacuerdo], "politica_constancias", 1,
         ["desacuerdo_entre_firmantes"]),
        ("predecesor_omitido", "s2", [x2], "politica_constancias", 0, ["predecesor_no_presentado"]),
        ("clave_no_admitida", "s1", [fc.constancia("s1", "ajeno")], "politica_constancias", 4,
         ["clave_no_admitida"]),
        ("politica_de_claves_incorrecta", "s1", [x1], "politica_constancias_solo_y", 4, ["clave_no_admitida"]),
    ]


def comando(nombre: str, n_expedientes: int, politica_constancias: str) -> list:
    return [*(f"{nombre}/e{i}" for i in range(1, n_expedientes + 1)), "--politica", "politica",
            "--politica-auditoria", "politica_auditoria", "--capturas", f"{nombre}/capturas",
            "--politica-constancias", politica_constancias, "--constancias", f"{nombre}/constancias",
            "--formato", "json"]


def _motivos(informe: dict) -> set:
    vistos = set(informe["entre_constancias"]["motivos"])
    for c in informe["constancias"]:
        vistos.update(c["motivos"])
        vistos.update(c.get("cotejo", []))
        vistos.add(c["estado"])
    for s in informe["series"]:
        vistos.update(p["motivo"] for p in s["pendientes"])
    return vistos


def ejecutar(raiz: Path) -> list:
    fp.escribir(raiz / "politica", fc.fa.politica_del_verificador())
    fp.escribir(raiz / "politica_auditoria", fc.fa.politica_de_auditoria())
    fp.escribir(raiz / "politica_constancias", fc.politica_de_constancias())
    fp.escribir(raiz / "politica_constancias_solo_y", fc.politica_de_constancias(("y",)))
    entorno = {**os.environ, "PYTHONPATH": str(BACKEND), "PYTHONDONTWRITEBYTECODE": "1"}
    resultados = []
    for nombre, estado, constancias, politica, codigo, motivos in escenarios():
        entradas = fc.entradas(estado)
        for i, archivos in enumerate(entradas["expedientes"], start=1):
            fp.escribir(raiz / nombre / f"e{i}", archivos)
        fp.escribir(raiz / nombre / "capturas", entradas["capturas"][0])
        fp.escribir(raiz / nombre / "constancias", ca.componer_constancias(constancias))
        argumentos = comando(nombre, len(entradas["expedientes"]), politica)
        proceso = subprocess.run([sys.executable, "-m", "scripts.verificar_constancias_auditoria", *argumentos],
                                 cwd=raiz, env=entorno, capture_output=True, check=False)
        informe = json.loads(proceso.stdout.decode("utf-8"))
        vistos = _motivos(informe)
        resultados.append({
            "escenario": nombre, "comando": " ".join(argumentos), "codigo": proceso.returncode,
            "codigo_esperado": codigo, "resultado": informe["resultado"], "motivos_esperados": motivos,
            "continuidad": [s["continuidad"] for s in informe["series"]],
            "ae79": informe["informe_ae79"]["resultado"],
            "correcto": proceso.returncode == codigo and all(m in vistos for m in motivos)})
    return resultados


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ae80-demo-") as temporal:
        resultados = ejecutar(Path(temporal))
    for r in resultados:
        marca = "OK " if r["correcto"] else "ERR"
        print(f"{marca} {r['escenario']}: codigo {r['codigo']} (esperado {r['codigo_esperado']}), "
              f"resultado {r['resultado']}; AE-79 recalculado {r['ae79']}")
        print(f"    motivos esperados: {', '.join(r['motivos_esperados'])}; continuidad: "
              f"{', '.join(r['continuidad']) or '-'}")
        print(f"    python -m scripts.verificar_constancias_auditoria {r['comando']}")
    fallidos = [r["escenario"] for r in resultados if not r["correcto"]]
    print(f"demostracion AE-80: {len(resultados) - len(fallidos)}/{len(resultados)} escenarios como se esperaba")
    return 1 if fallidos else 0


if __name__ == "__main__":
    sys.exit(main())
