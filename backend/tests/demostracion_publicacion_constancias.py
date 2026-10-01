"""Demostracion reproducible de la Etapa AE-81, validada localmente como
trabajo preparatorio -NO OPERATIVA.

Escribe en un directorio temporal el material sintetico de AE-79 y AE-80,
politicas de rol, checkpoints, observaciones e inventarios, y ejecuta el
comando real `python -m scripts.verificar_publicacion_constancias` dos veces
por escenario en procesos aparte, con el directorio temporal como directorio
de trabajo y rutas relativas. Comprueba el codigo de salida, los motivos
esperados y que las dos salidas JSON sean identicas; borra el directorio
temporal al terminar.

Uso (desde `backend`):

  python -m tests.demostracion_publicacion_constancias

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

from app.application.ml import constancias_auditoria as ca
from app.application.ml import publicacion_constancias as pc
from tests.unit.ml import fixtures_expediente_portable as fp
from tests.unit.ml import fixtures_publicacion_constancias as fpc

BACKEND = Path(__file__).resolve().parents[1]


def escenarios():
    """(nombre, checkpoints, observaciones, inventario o None, codigo,
    motivos que deben aparecer)."""
    c1, c2, sust = fpc.c1(), fpc.c2(), fpc.c2_sustituto()
    obs = fpc.observacion
    ajeno = fpc.checkpoint(fpc.cabezas_c2(), 2, c1, publicador="ajeno")
    return [
        ("continuidad_valida", [c1, c2], [obs(c2, "m1"), obs(c2, "m2")], fpc.inventario(), 0, []),
        ("cabeza_omitida", [c1, sust], [obs(sust, "m1"), obs(sust, "m2")],
         fpc.inventario(checkpoints=[c1, sust]), 4, ["cabeza_no_publicada"]),
        ("predecesor_omitido", [c2], [obs(c2, "m1"), obs(c2, "m2")], fpc.inventario(), 5,
         ["predecesor_no_presentado"]),
        ("sustitucion_de_checkpoint", [c1, sust], [obs(c2, "m1"), obs(c2, "m2")], fpc.inventario(), 4,
         ["checkpoint_no_coincide_con_referencia"]),
        ("firma_o_clave_incorrecta", [c1, ajeno], [obs(c2, "m1")], fpc.inventario(), 4, ["clave_no_admitida"]),
        ("bifurcacion_del_publicador", [c1, c2, sust], [obs(c2, "m1"), obs(c2, "m2")], fpc.inventario(), 1,
         ["bifurcacion_firmada_del_publicador"]),
        ("monitores_con_contenidos_incompatibles", [c1, c2], [obs(c2, "m1"), obs(sust, "m2")], fpc.inventario(), 6,
         ["discrepancia_entre_monitores"]),
        ("observaciones_compatibles_de_una_progresion", [c1, c2], [obs(c1, "m1"), obs(c2, "m2")],
         fpc.inventario(monitores=("m2",)), 0, []),
        ("inventario_incompleto", [c1, c2], [obs(c2, "m1"), obs(c2, "m2")],
         fpc.inventario(monitores=("m1", "m2", "m3")), 5, ["monitor_esperado_sin_observacion"]),
        ("referencias_no_proporcionadas", [c1, c2], [obs(c2, "m1"), obs(c2, "m2")], None, 5,
         ["inventario_no_aportado"]),
    ]


def _motivos(informe: dict) -> set:
    vistos = {m for grupo in informe["motivos"].values() for m in grupo}
    vistos |= {h["motivo"] for h in informe["hallazgos"]}
    return vistos


def ejecutar(raiz: Path) -> list:
    base = fpc.entradas()
    for i, archivos in enumerate(base["expedientes"], start=1):
        fp.escribir(raiz / f"e{i}", archivos)
    fp.escribir(raiz / "politica", base["politica_del_verificador"])
    fp.escribir(raiz / "politica_auditoria", base["politica_de_auditoria"])
    fp.escribir(raiz / "capturas", base["capturas"][0])
    fp.escribir(raiz / "politica_constancias", base["politica_de_constancias"])
    fp.escribir(raiz / "constancias", ca.componer_constancias(list(fpc.constancias())))
    fp.escribir(raiz / "publicadores", fpc.politica("publicador", ("p", "q")))
    fp.escribir(raiz / "monitores", fpc.politica("monitor", ("m1", "m2", "m3")))
    entorno = {**os.environ, "PYTHONPATH": str(BACKEND), "PYTHONDONTWRITEBYTECODE": "1"}
    resultados = []
    for nombre, checkpoints, observaciones, inventario, codigo, motivos in escenarios():
        fp.escribir(raiz / nombre / "checkpoints", pc.componer_checkpoints(checkpoints))
        fp.escribir(raiz / nombre / "observaciones", pc.componer_observaciones(observaciones))
        argumentos = ["e1", "e2", "--politica", "politica", "--politica-auditoria", "politica_auditoria",
                      "--capturas", "capturas", "--politica-constancias", "politica_constancias",
                      "--constancias", "constancias", "--politica-publicadores", "publicadores",
                      "--politica-monitores", "monitores", "--checkpoints", f"{nombre}/checkpoints",
                      "--observaciones", f"{nombre}/observaciones", "--formato", "json"]
        if inventario is not None:
            fp.escribir(raiz / nombre / "inventario", inventario)
            argumentos[-2:-2] = ["--inventario", f"{nombre}/inventario"]
        procesos = [subprocess.run([sys.executable, "-m", "scripts.verificar_publicacion_constancias", *argumentos],
                                   cwd=raiz, env=entorno, capture_output=True, check=False) for _ in range(2)]
        informe = json.loads(procesos[0].stdout.decode("utf-8"))
        vistos = _motivos(informe)
        resultados.append({
            "escenario": nombre, "comando": " ".join(argumentos), "codigo": procesos[0].returncode,
            "codigo_esperado": codigo, "resultado": informe["resultado"], "motivos_esperados": motivos,
            "determinista": procesos[0].stdout == procesos[1].stdout and procesos[0].returncode == procesos[1].returncode,
            "stderr_vacio": all(p.stderr == b"" for p in procesos),
            "correcto": (procesos[0].returncode == codigo and all(m in vistos for m in motivos)
                         and procesos[0].stdout == procesos[1].stdout and all(p.stderr == b"" for p in procesos))})
    return resultados


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ae81-demo-") as temporal:
        resultados = ejecutar(Path(temporal))
    for r in resultados:
        marca = "OK " if r["correcto"] else "ERR"
        print(f"{marca} {r['escenario']}: codigo {r['codigo']} (esperado {r['codigo_esperado']}), resultado "
              f"{r['resultado']}; determinista {r['determinista']}")
        print(f"    motivos esperados: {', '.join(r['motivos_esperados']) or '-'}")
        print(f"    python -m scripts.verificar_publicacion_constancias {r['comando']}")
    fallidos = [r["escenario"] for r in resultados if not r["correcto"]]
    print(f"demostracion AE-81: {len(resultados) - len(fallidos)}/{len(resultados)} escenarios como se esperaba")
    return 1 if fallidos else 0


if __name__ == "__main__":
    sys.exit(main())
