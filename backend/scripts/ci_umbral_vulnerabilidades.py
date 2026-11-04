"""Fase 10 (E10.3, v2): umbral de vulnerabilidades del CI de seguridad (solo biblioteca estandar).

Lee el informe JSON de un escaner y FALLA (codigo 1) si hay algun hallazgo `high` o `critical` que no cubra
una excepcion ACEPTADA, concreta y vigente de `despliegue/seguridad/excepciones-vulnerabilidades.json`.

Informe: falta, vacio, no JSON, de error o de otro formato -> FALLO. Ademas se valida su estructura y su
coherencia interna con el modelo del formato real (v2, F1023-ROB-01):

- `npm` (`npm audit --json`, `auditReportVersion` 2): cada paquete de `vulnerabilities` tiene sus campos y
  tipos; cada `via` es un aviso propio (objeto) o el nombre de OTRO paquete vulnerable del informe (aviso
  heredado); la severidad de cada paquete es la maxima de sus avisos propios y de los paquetes de los que
  hereda; y el recuento por severidad de `metadata.vulnerabilities` (que npm calcula por PAQUETE) coincide con
  los paquetes del informe y con `total`. Un informe que declara criticos sin detallarlos no es limpio.
- `grype` (`grype -o json`): `descriptor` de grype con version, `matches` como lista y cada coincidencia con
  `vulnerability.id`, `vulnerability.severity` (valor de grype) y `artifact.name`/`artifact.version`.

Excepcion (v2, F1023-SEC-01): solo se activa con `estado` exactamente `aceptada`, `aceptada_por` y
`fecha_aceptacion` (AAAA-MM-DD, no posterior a hoy), y si cubre ese aviso (`id`), ese paquete (`paquete`) y
ese artefacto (`artefacto`) sin haber caducado (`caduca`, inclusive). Pendientes, rechazadas, retiradas, sin
estado o con estado desconocido NO se activan. No se rebaja ninguna severidad ni se excluyen paquetes enteros.

PR #109, opcion B: para grype tambien son obligatorias la version EXACTA de `artifact.version` y la severidad
aceptada (`high` o `critical`). Si aparecen dos versiones del mismo aviso/paquete, ambas deben estar cubiertas;
no se descarta una por deduplicar. No se interpretan rangos ni comodines. Las excepciones no corrigen avisos.

Uso: python scripts/ci_umbral_vulnerabilidades.py --formato npm|grype --artefacto <nombre> <informe.json>
     [--excepciones <json>] [--hoy AAAA-MM-DD] [--resumen <archivo>]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path

GRAVES = frozenset({"high", "critical"})
NPM_SEVERIDADES = ("info", "low", "moderate", "high", "critical")
GRYPE_SEVERIDADES = frozenset({"negligible", "low", "medium", "high", "critical", "unknown"})
EXCEPCIONES = Path(__file__).resolve().parents[2] / "despliegue" / "seguridad" / "excepciones-vulnerabilidades.json"


class InformeNoValido(ValueError):
    """El informe no permite afirmar nada: se trata como fallo."""


def _exigir(condicion: bool, motivo: str) -> None:
    if not condicion:
        raise InformeNoValido(motivo)


def _es_entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0


def hallazgos_npm(datos) -> list[tuple[str, str, str]]:
    _exigir(isinstance(datos, dict), "no es un objeto JSON")
    _exigir("error" not in datos, "npm audit devolvio un informe de error")
    _exigir(datos.get("auditReportVersion") == 2, "no es `npm audit --json` (auditReportVersion 2)")
    paquetes, metadata = datos.get("vulnerabilities"), datos.get("metadata")
    _exigir(isinstance(paquetes, dict) and isinstance(metadata, dict), "faltan vulnerabilities o metadata")
    cuenta = metadata.get("vulnerabilities")
    _exigir(isinstance(cuenta, dict) and all(_es_entero(cuenta.get(s)) for s in (*NPM_SEVERIDADES, "total")),
            "metadata.vulnerabilities incompleto")
    filas, propios, heredados = set(), {}, {}
    for nombre, v in paquetes.items():
        _exigir(isinstance(v, dict) and v.get("name") == nombre, f"paquete {nombre!r} mal formado")
        _exigir(v.get("severity") in NPM_SEVERIDADES, f"severidad no valida en {nombre!r}")
        _exigir(isinstance(v.get("via"), list) and v["via"], f"{nombre!r} sin via")
        _exigir(isinstance(v.get("effects"), list) and isinstance(v.get("nodes"), list)
                and isinstance(v.get("range"), str) and isinstance(v.get("isDirect"), bool),
                f"campos de {nombre!r} incompletos")
        propios[nombre], heredados[nombre] = [], []
        for via in v["via"]:
            if isinstance(via, str):
                _exigir(via in paquetes and via != nombre, f"{nombre!r} hereda de un paquete ausente: {via!r}")
                heredados[nombre].append(via)
                continue
            _exigir(isinstance(via, dict) and via.get("severity") in NPM_SEVERIDADES
                    and isinstance(via.get("url") or via.get("source"), (str, int))
                    and isinstance(via.get("name"), str), f"aviso mal formado en {nombre!r}")
            aviso = str(via.get("url") or via.get("source")).rstrip("/").rsplit("/", 1)[-1]
            propios[nombre].append(via["severity"])
            filas.add((aviso, nombre, via["severity"]))

    rango = {s: i for i, s in enumerate(NPM_SEVERIDADES)}
    efectiva: dict[str, int] = {}

    def severidad(nombre: str, camino: frozenset = frozenset()) -> int:
        if nombre in efectiva:
            return efectiva[nombre]
        if nombre in camino:  # ciclo de herencia: solo cuentan los avisos propios del ciclo
            return max((rango[s] for s in propios[nombre]), default=-1)
        valor = max([rango[s] for s in propios[nombre]]
                    + [severidad(h, camino | {nombre}) for h in heredados[nombre]], default=-1)
        efectiva[nombre] = valor
        return valor

    for nombre, v in paquetes.items():
        _exigir(severidad(nombre) == rango[v["severity"]],
                f"severidad de {nombre!r} incoherente con sus avisos propios y heredados")
    por_paquete = Counter(v["severity"] for v in paquetes.values())
    _exigir(all(cuenta[s] == por_paquete.get(s, 0) for s in NPM_SEVERIDADES) and cuenta["total"] == len(paquetes),
            "metadata.vulnerabilities no coincide con los paquetes detallados")
    return sorted(filas)


def hallazgos_grype(datos) -> list[tuple[str, str, str]]:
    _exigir(isinstance(datos, dict), "no es un objeto JSON")
    descriptor, coincidencias = datos.get("descriptor"), datos.get("matches")
    _exigir(isinstance(descriptor, dict) and descriptor.get("name") == "grype"
            and isinstance(descriptor.get("version"), str), "no es un informe de `grype -o json`")
    _exigir(isinstance(coincidencias, list), "matches no es una lista")
    filas = set()
    for m in coincidencias:
        vul, art = (m.get("vulnerability"), m.get("artifact")) if isinstance(m, dict) else (None, None)
        _exigir(isinstance(vul, dict) and isinstance(art, dict), "coincidencia mal formada")
        severidad = str(vul.get("severity", "")).lower()
        _exigir(isinstance(vul.get("id"), str) and vul["id"] and severidad in GRYPE_SEVERIDADES,
                "vulnerabilidad sin id o con severidad no valida")
        _exigir(isinstance(art.get("name"), str) and isinstance(art.get("version"), str), "artefacto incompleto")
        filas.add((vul["id"], art["name"], severidad))
    return sorted(filas)


def _version_exacta(valor) -> bool:
    return (isinstance(valor, str) and bool(valor) and valor == valor.strip()
            and not any(c.isspace() or c in "*?[]<>=|," for c in valor))


def activa(excepcion: dict, artefacto: str, hoy: dt.date, *, formato: str | None = None) -> bool:
    """Solo una aceptacion explicita, concreta y vigente activa la excepcion."""
    try:
        return (excepcion.get("estado") == "aceptada" and excepcion.get("artefacto") == artefacto
                and (formato is None or excepcion.get("formato", formato) == formato)
                and (formato != "grype" or (_version_exacta(excepcion.get("version"))
                                           and excepcion.get("severidad") in GRAVES))
                and isinstance(excepcion.get("aceptada_por"), str) and excepcion["aceptada_por"].strip() != ""
                and dt.date.fromisoformat(excepcion["fecha_aceptacion"]) <= hoy
                and dt.date.fromisoformat(excepcion["caduca"]) >= hoy
                and all(isinstance(excepcion.get(k), str) and excepcion[k] and "*" not in excepcion[k]
                        for k in ("id", "paquete")))
    except (KeyError, TypeError, ValueError):
        return False


def evaluar(formato: str, artefacto: str, datos, excepciones: list[dict], hoy: dt.date) -> dict:
    filas = hallazgos_npm(datos) if formato == "npm" else hallazgos_grype(datos)
    if not isinstance(excepciones, list) or not all(isinstance(e, dict) for e in excepciones):
        raise InformeNoValido("excepciones mal formadas")
    aceptadas = [e for e in excepciones if activa(e, artefacto, hoy, formato=formato)]
    versiones = {}
    if formato == "grype":
        for m in datos["matches"]:  # hallazgos_grype ya ha validado cada coincidencia
            f = (m["vulnerability"]["id"], m["artifact"]["name"], m["vulnerability"]["severity"].lower())
            versiones.setdefault(f, set()).add(m["artifact"]["version"])
        vigentes = {(e["id"], e["paquete"], e["severidad"], e["version"]) for e in aceptadas}

        def cubierta(f):
            return all((*f, version) in vigentes for version in versiones[f])
    else:
        vigentes = {(e["id"], e["paquete"]) for e in aceptadas}

        def cubierta(f):
            return (f[0], f[1]) in vigentes
    graves = [f for f in filas if f[2] in GRAVES]
    cubiertos = [f for f in graves if cubierta(f)]
    abiertos = [f for f in graves if not cubierta(f)]
    no_activas = sum(1 for e in excepciones if e.get("artefacto") == artefacto
                     and not activa(e, artefacto, hoy, formato=formato))
    return {"formato": formato, "artefacto": artefacto, "hallazgos": len(filas),
            "por_severidad": {s: sum(f[2] == s for f in filas) for s in sorted({f[2] for f in filas})},
            "graves_cubiertos": cubiertos, "graves_abiertos": abiertos, "excepciones_no_activas": no_activas,
            "versiones_por_hallazgo": [{"id": f[0], "paquete": f[1], "severidad": f[2],
                                        "versiones": sorted(versiones[f])} for f in filas] if versiones else [],
            "correcto": not abiertos}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("informe")
    p.add_argument("--formato", choices=("npm", "grype"), required=True)
    p.add_argument("--artefacto", required=True)
    p.add_argument("--excepciones", default=str(EXCEPCIONES))
    p.add_argument("--hoy", default=None)
    p.add_argument("--resumen", default=None)
    a = p.parse_args(argv)
    hoy = dt.date.fromisoformat(a.hoy) if a.hoy else dt.datetime.now(dt.timezone.utc).date()
    try:
        texto = Path(a.informe).read_text(encoding="utf-8")
        if not texto.strip():
            raise InformeNoValido("informe vacio")
        excepciones = json.loads(Path(a.excepciones).read_text(encoding="utf-8")).get("excepciones")
        resultado = evaluar(a.formato, a.artefacto, json.loads(texto), excepciones, hoy)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"umbral {a.artefacto}: ERROR, el informe no es valido ({type(error).__name__}: {error})")
        return 1
    linea = (f"umbral {a.artefacto} ({a.formato}): {'CORRECTO' if resultado['correcto'] else 'FALLO'}; "
             f"{resultado['hallazgos']} hallazgos {resultado['por_severidad']}; graves con excepcion aceptada "
             f"vigente {len(resultado['graves_cubiertos'])}; graves abiertos {len(resultado['graves_abiertos'])}; "
             f"excepciones no activas {resultado['excepciones_no_activas']}")
    versiones = {(f["id"], f["paquete"], f["severidad"]): " versiones=" + ",".join(f["versiones"])
                 for f in resultado["versiones_por_hallazgo"]}
    detalle = [f"  abierto: {i} {pkg} {sev}" + versiones.get((i, pkg, sev), "")
               for i, pkg, sev in resultado["graves_abiertos"]]
    detalle += [f"  excepcion aceptada: {i} {pkg} {sev}" + versiones.get((i, pkg, sev), "")
                for i, pkg, sev in resultado["graves_cubiertos"]]
    if resultado["graves_cubiertos"]:
        detalle.append("  Avisos aceptados temporalmente; siguen presentes y no se consideran corregidos.")
    print("\n".join([linea, *detalle]))
    if a.resumen:
        with open(a.resumen, "a", encoding="utf-8") as f:
            f.write("\n".join([linea, *detalle]) + "\n")
    return 0 if resultado["correcto"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
