"""Fase 10 (E10.4): generaciones, importacion, validacion y respaldos (CLI local).

Las consultas internas usan HTTP exclusivamente en loopback, dentro del mismo
proceso que registra las aperturas de archivos. No requieren TestClient/httpx.

Desde `backend/`. Las URL de base se leen de ARCHIVOS (`--url-*-archivo`), nunca de argumentos; las claves
privadas, de archivos 0600. Ninguna orden pausa Fase 6, toma sus cerrojos ni cambia su tarea programada.

    python -m scripts.generaciones claves-firma --privada <pem> --publica <pub>
    python -m scripts.generaciones capturar --destino <dir> --clave-privada <pem> [--alcance publicacion|respaldo]
           [--intentos 3 --espera 30 --plazo 900] [--autorizacion-d10 <referencia>]
    python -m scripts.generaciones verificar --paquete <dir> --clave-publica <pub> [--alcance ...]
    python -m scripts.generaciones importar --paquete <dir> --clave-publica <pub> --raiz <srv-pub>
           --url-admin-archivo <f> --url-lector-archivo <f>
    python -m scripts.generaciones activar --raiz <srv-pub> --id <id> --clave-publica <pub> --url-admin-archivo <f>
    python -m scripts.generaciones claves-respaldo --privada <pem> --publica <pub>
    python -m scripts.generaciones respaldar --paquete <dir> --clave-publica-firma <pub> --clave-publica-respaldo <pub>
           --destino <dir>
    python -m scripts.generaciones verificar-respaldo --archivo <.lpr> --clave-privada-respaldo <pem>
           --clave-publica-firma <pub>
    python -m scripts.generaciones restaurar --archivo <.lpr> --clave-privada-respaldo <pem>
           --clave-publica-firma <pub> --destino <dir nuevo> --url-admin-archivo <f> [--base <nombre nuevo>]
    python -m scripts.generaciones retener --destino <dir> [--diarios 14 --semanales 8 --mensuales 12] [--aplicar]

USO REAL BLOQUEADO (D10 pendiente): `capturar` solo acepta una base cuyo nombre contenga `prueba` salvo
`--autorizacion-d10 <referencia>` (la referencia queda en el manifiesto). Codigo de salida: 0 bien,
1 rechazo controlado (motivo en JSON), 2 uso incorrecto.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path


def _leer_url(ruta: str) -> str:
    texto = Path(ruta).read_text(encoding="ascii").strip()
    if not texto or "\n" in texto:
        raise SystemExit("archivo de URL vacio o con varias lineas")
    return texto


def _imprimir(valor) -> None:
    print(json.dumps(valor, ensure_ascii=False, indent=1))


def _claves_firma(a) -> int:
    from app.infrastructure.generaciones import firma
    _imprimir({"clave_firma": firma.generar(Path(a.privada), Path(a.publica))})
    return 0


def _capturar(a) -> int:
    from sqlalchemy.engine import make_url

    from app.core.config import get_settings
    from app.infrastructure.generaciones import captura

    ajustes = get_settings()
    base = make_url(ajustes.database_url).database or ""
    if "prueba" not in base and not a.autorizacion_d10:
        sys.stderr.write("NEGADO: D10 pendiente; la captura de datos reales exige --autorizacion-d10\n")
        return 2
    fuente = captura.Fuente.desde_ajustes(ajustes)
    try:
        g = captura.capturar(fuente, Path(a.destino), Path(a.clave_privada), alcance=a.alcance,
                             intentos=a.intentos, espera=a.espera, plazo=a.plazo,
                             autorizacion=a.autorizacion_d10 or "base_de_prueba")
    except captura.CapturaRechazada as rechazo:
        _imprimir({"resultado": "rechazada", "motivos": rechazo.motivos})
        return 1
    _imprimir({"resultado": "sellada", "generacion": g.name})
    return 0


def _verificar(a) -> int:
    from app.infrastructure.generaciones.formato import GeneracionNoValida
    from app.infrastructure.generaciones.verificacion import verificar

    try:
        m = verificar(Path(a.paquete), Path(a.clave_publica), alcance=a.alcance)
    except GeneracionNoValida as error:
        _imprimir({"resultado": "no_valida", "motivo": str(error)})
        return 1
    _imprimir({"resultado": "valida", "id": m["id"], "archivos": len(m["archivos"]), "coherencia": m["coherencia"]})
    return 0


def _importar(a) -> int:
    from app.infrastructure.generaciones import importacion as im

    destino = im.Destino(Path(a.raiz), _leer_url(a.url_admin_archivo), _leer_url(a.url_lector_archivo),
                         a.rol_lector)
    try:
        informe = im.importar(Path(a.paquete), Path(a.clave_publica), destino)
    except im.ImportacionRechazada as rechazo:
        _imprimir({"resultado": "rechazada", "paso": rechazo.paso, "motivo": rechazo.motivo})
        return 1
    _imprimir({k: v for k, v in informe.items() if k != "huellas_consultas"})
    return 0


def _activar(a) -> int:
    from app.infrastructure.generaciones import importacion as im
    from app.infrastructure.generaciones.formato import GeneracionNoValida

    try:
        _imprimir(im.activar(Path(a.raiz), a.id, Path(a.clave_publica), _leer_url(a.url_admin_archivo)))
    except GeneracionNoValida as error:
        _imprimir({"resultado": "no_activada", "motivo": str(error)})
        return 1
    return 0


def _consultas(a) -> int:
    """Uso interno del importador y de R-L: API publica en proceso con los ajustes del entorno, una clave
    efimera y el registro de cada apertura de archivo bajo los `DIRECTORIO_*` (DAT-01)."""
    from app.infrastructure.generaciones import inventario as inv

    clave = secrets.token_urlsafe(32)
    os.environ["API_PUBLICA_CLAVES"] = f"humo:sha256:{hashlib.sha256(clave.encode('ascii')).hexdigest()}"
    os.environ["API_PUBLICA_FICHAS_POR_MINUTO"] = os.environ["API_PUBLICA_FICHAS_POR_MINUTO_IP"] = "100000"
    raices = {a_.nombre: Path(os.environ[a_.ajuste.upper()]).resolve() for a_ in inv.ALMACENES}
    declaradas = {}
    for alm in inv.PUBLICABLES:
        for sub in (alm.publicables or ("",)):
            declaradas[f"{alm.nombre}/{sub}".rstrip("/")] = raices[alm.nombre] / sub if sub else raices[alm.nombre]
    lecturas, escrituras, ejemplos = {}, [], {}

    def auditar(evento, argumentos):
        if evento not in ("open", "os.listdir", "os.scandir") or not argumentos:
            return
        ruta = argumentos[0]
        if not isinstance(ruta, (str, bytes, os.PathLike)):
            return
        try:
            p = Path(os.fsdecode(ruta)).absolute()
        except (TypeError, ValueError):
            return
        if not any(r == p or r in p.parents for r in raices.values()):
            return
        if evento == "open" and len(argumentos) > 1 and isinstance(argumentos[1], str) and \
                any(c in argumentos[1] for c in "wax+"):
            escrituras.append(str(p))
        almacen, raiz = next((n, r) for n, r in raices.items() if r == p or r in p.parents)
        if p == raiz:
            clave_l = f"raiz:{almacen}"  # listar la raiz de un almacen no lee datos
        else:
            clave_l = next((n for n, r in declaradas.items() if r == p or r in p.parents), None)
            if clave_l is None:
                # Sondeo de algo que la generacion NO contiene por diseno (p. ej. el cerrojo de Producto 5 para
                # saber si hay una ejecucion activa): no lee datos y su ausencia es la respuesta correcta.
                clave_l = f"{'ausente' if not os.path.lexists(p) else 'fuera'}:{almacen}"
                muestras = ejemplos.setdefault(clave_l, [])
                if len(muestras) < 10 and p.relative_to(raiz).as_posix() not in muestras:
                    muestras.append(p.relative_to(raiz).as_posix())
        lecturas[clave_l] = lecturas.get(clave_l, 0) + 1

    sys.addaudithook(auditar)
    from scripts._http_generaciones import ClienteLocal

    from app.api.publica.aplicacion import app
    from app.infrastructure.generaciones import consultas

    esperado = json.loads(Path(a.esperado).read_text(encoding="utf-8")) if a.esperado else None
    with ClienteLocal(app) as cliente:
        resultado = consultas.recorrer(lambda ruta: cliente.get(ruta, clave), esperado)
    fuera = [f"{k}: {ejemplos.get(k)}" for k in sorted(lecturas) if k.startswith("fuera:")]
    resultado["lecturas"] = {"por_subarbol": dict(sorted(lecturas.items())), "fuera_de_lo_declarado": fuera,
                             "sondeos_de_lo_ausente": {k: ejemplos.get(k) for k in sorted(lecturas)
                                                       if k.startswith("ausente:")},
                             "no_leidos": sorted(n for n in declaradas if n not in lecturas),
                             "escrituras": escrituras}
    if escrituras:
        resultado["fallos"].append(f"la API intento escribir: {escrituras[:3]}")
    Path(a.salida).write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if resultado["fallos"] else 0


def _claves_respaldo(a) -> int:
    from app.infrastructure.generaciones import respaldo
    _imprimir({"receptor": respaldo.generar_claves(Path(a.privada), Path(a.publica))})
    return 0


def _respaldar(a) -> int:
    from app.infrastructure.generaciones import respaldo
    from app.infrastructure.generaciones.formato import GeneracionNoValida
    from app.infrastructure.generaciones.verificacion import verificar

    try:
        alcance = json.loads((Path(a.paquete) / "manifiesto.json").read_text(encoding="utf-8"))["alcance"]
        verificar(Path(a.paquete), Path(a.clave_publica_firma), alcance=alcance)
    except (GeneracionNoValida, OSError, ValueError, KeyError) as error:
        _imprimir({"resultado": "no_respaldado", "motivo": str(error)})
        return 1
    _imprimir(respaldo.respaldar(Path(a.paquete), Path(a.clave_publica_respaldo), Path(a.destino)))
    return 0


def _verificar_respaldo(a) -> int:
    import tempfile

    from app.infrastructure.generaciones import respaldo
    from app.infrastructure.generaciones.formato import GeneracionNoValida
    from app.infrastructure.generaciones.verificacion import verificar

    try:
        catalogo = respaldo.comprobar_sin_descifrar(Path(a.archivo))
        with tempfile.TemporaryDirectory(prefix="e104-verificar-") as tmp:
            paquete = respaldo.descifrar(Path(a.archivo), Path(a.clave_privada_respaldo), Path(tmp) / "p")
            m = verificar(paquete, Path(a.clave_publica_firma), alcance=catalogo["alcance"])
    except (GeneracionNoValida, OSError, ValueError, KeyError) as error:
        _imprimir({"resultado": "no_valido", "motivo": str(error)})
        return 1
    _imprimir({"resultado": "valido", "generacion": m["id"], "alcance": m["alcance"], "archivos": len(m["archivos"])})
    return 0


def _restaurar(a) -> int:
    from app.infrastructure.generaciones import respaldo
    from app.infrastructure.generaciones.formato import GeneracionNoValida

    try:
        r = respaldo.restaurar(Path(a.archivo), Path(a.clave_privada_respaldo), Path(a.clave_publica_firma),
                               Path(a.destino), _leer_url(a.url_admin_archivo), a.base or None)
    except (GeneracionNoValida, RuntimeError) as error:  # RuntimeError: exclusion del servidor no acreditada
        _imprimir({"resultado": "no_restaurado", "motivo": str(error),
                   "diagnostico": getattr(error, "diagnostico", None)})
        return 1
    _imprimir({"resultado": "restaurado", "generacion": r.manifiesto["id"], "base": r.base,
               "almacenes": str(r.almacenes), "tarea_programada": "no se registra ni se activa (R-W pendiente)"})
    return 0


def _retener(a) -> int:
    from app.infrastructure.generaciones import respaldo

    plan = respaldo.plan_de_retencion(Path(a.destino), a.diarios, a.semanales, a.mensuales, a.minimo)
    plan["aplicado"] = bool(a.aplicar)
    if a.aplicar:
        plan["borrados"] = respaldo.aplicar_retencion(Path(a.destino), plan)
    _imprimir(plan)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="scripts.generaciones", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="orden", required=True)
    s = sub.add_parser("claves-firma")
    s.add_argument("--privada", required=True)
    s.add_argument("--publica", required=True)
    s.set_defaults(f=_claves_firma)
    s = sub.add_parser("capturar")
    s.add_argument("--destino", required=True)
    s.add_argument("--clave-privada", required=True)
    s.add_argument("--alcance", choices=("publicacion", "respaldo"), default="publicacion")
    s.add_argument("--intentos", type=int, default=3)
    s.add_argument("--espera", type=float, default=30.0)
    s.add_argument("--plazo", type=float, default=900.0)
    s.add_argument("--autorizacion-d10", default="")
    s.set_defaults(f=_capturar)
    s = sub.add_parser("verificar")
    s.add_argument("--paquete", required=True)
    s.add_argument("--clave-publica", required=True)
    s.add_argument("--alcance", choices=("publicacion", "respaldo"), default="publicacion")
    s.set_defaults(f=_verificar)
    s = sub.add_parser("importar")
    s.add_argument("--paquete", required=True)
    s.add_argument("--clave-publica", required=True)
    s.add_argument("--raiz", required=True)
    s.add_argument("--url-admin-archivo", required=True)
    s.add_argument("--url-lector-archivo", required=True)
    s.add_argument("--rol-lector", default="consulta_lector")
    s.set_defaults(f=_importar)
    s = sub.add_parser("activar")
    s.add_argument("--raiz", required=True)
    s.add_argument("--id", required=True)
    s.add_argument("--clave-publica", required=True)
    s.add_argument("--url-admin-archivo", required=True)
    s.set_defaults(f=_activar)
    s = sub.add_parser("consultas")
    s.add_argument("--salida", required=True)
    s.add_argument("--esperado", help="recuentos sellados (consultas.esperado_de): falla solo por dano o perdida")
    s.set_defaults(f=_consultas)
    s = sub.add_parser("claves-respaldo")
    s.add_argument("--privada", required=True)
    s.add_argument("--publica", required=True)
    s.set_defaults(f=_claves_respaldo)
    s = sub.add_parser("respaldar")
    s.add_argument("--paquete", required=True)
    s.add_argument("--clave-publica-firma", required=True)
    s.add_argument("--clave-publica-respaldo", required=True)
    s.add_argument("--destino", required=True)
    s.set_defaults(f=_respaldar)
    s = sub.add_parser("verificar-respaldo")
    s.add_argument("--archivo", required=True)
    s.add_argument("--clave-privada-respaldo", required=True)
    s.add_argument("--clave-publica-firma", required=True)
    s.set_defaults(f=_verificar_respaldo)
    s = sub.add_parser("restaurar")
    s.add_argument("--archivo", required=True)
    s.add_argument("--clave-privada-respaldo", required=True)
    s.add_argument("--clave-publica-firma", required=True)
    s.add_argument("--destino", required=True)
    s.add_argument("--url-admin-archivo", required=True)
    s.add_argument("--base", default="")
    s.set_defaults(f=_restaurar)
    s = sub.add_parser("retener")
    s.add_argument("--destino", required=True)
    s.add_argument("--diarios", type=int, default=14)
    s.add_argument("--semanales", type=int, default=8)
    s.add_argument("--mensuales", type=int, default=12)
    s.add_argument("--minimo", type=int, default=1)
    s.add_argument("--aplicar", action="store_true")
    s.set_defaults(f=_retener)
    a = p.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    raise SystemExit(main())
