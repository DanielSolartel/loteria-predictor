"""Fase 8 v2: arranque soportado (F8-SEC-02, F8-LIM-01 y F8-SEC-01 en el
proceso real) y cobertura de Windows.

Se ejecuta el arranque del paso «Arrancar» de `docs/fase8_api_publica.md` tal
cual, como proceso Uvicorn real; solo cambian el puerto (0) y, para provocar
un fallo, la aplicacion. Debe:
- no escribir la URL ni su consulta (una clave enviada por error en
  `?api_key=`) y conservar el registro propio sanitizado;
- ignorar `X-Forwarded-For`: desde un unico origen local, variar esa cabecera
  no elude la cuota por IP;
- convertir un fallo inesperado en un 500 sanitizado, sin traza ni mensaje en
  el registro del proceso.
Claves sinteticas generadas en cada prueba; SQLite temporal, sin PostgreSQL.
Los fallos solo muestran indicadores, nunca el registro ni la clave."""
from __future__ import annotations

import httpx

from app.api.publica.seguridad import generar_clave, huella
from tests.unit.api_publica import fixtures_api_publica as fa

RAIZ = fa.BACKEND.parent
OPCIONES = {"--no-access-log", "--no-proxy-headers"}
SONDA = '''import os

from app.api.publica import dependencias as d
from app.api.publica.aplicacion import crear_app

app = crear_app()


def fallar():
    raise RuntimeError("F8_SONDA_INTERNA=" + os.environ["F8_SONDA_CANARIO"])


app.dependency_overrides[d.estado_de_la_base] = fallar
'''


def test_el_proceso_real_no_registra_la_url_ni_la_excepcion(tmp_path):
    clave = generar_clave()
    (tmp_path / "sonda_f8_v2.py").write_text(SONDA, encoding="utf-8")
    registro = tmp_path / "uvicorn.log"
    entorno = fa.entorno_de_proceso(tmp_path, API_PUBLICA_CLAVES=f"pruebas:sha256:{huella(clave)}",
                                    F8_SONDA_CANARIO=clave)
    with fa.proceso_uvicorn(fa.arranque_documentado("sonda_f8_v2:app"), entorno, registro, app_dir=tmp_path) as base:
        with httpx.Client(base_url=base, trust_env=False, timeout=10) as c:
            en_url = c.get("/api/v1/juegos", params={"api_key": clave})
            inesperado = c.get("/api/v1/estado", headers={"X-API-Key": clave})
    texto = registro.read_text(encoding="utf-8", errors="replace")
    cuerpo = inesperado.json().get("error", {})
    propias = [x for x in texto.splitlines() if "app.api.publica api_publica" in x]
    criterios = {
        "clave_en_url_401": en_url.status_code == 401 and en_url.json()["error"]["codigo"] == "no_autenticado",
        "error_500_sanitizado": inesperado.status_code == 500 and cuerpo.get("codigo") == "error_interno",
        "id_coherente": cuerpo.get("solicitud") is not None
        and inesperado.headers.get("X-Request-ID") == cuerpo["solicitud"],
        "no_store": inesperado.headers.get("Cache-Control") == "no-store",
        "sin_clave": clave not in texto, "sin_huella": huella(clave) not in texto,
        "sin_consulta": "api_key" not in texto, "sin_registro_de_acceso": '"GET /api/v1/' not in texto,
        "sin_traza": "Traceback" not in texto, "sin_mensaje": "F8_SONDA_INTERNA" not in texto,
        "sin_error_asgi": "Exception in ASGI application" not in texto,
        "registro_propio_401": any(" GET /api/v1/juegos 401 " in x and "clave=-" in x for x in propias),
        "registro_propio_500": any(" GET /api/v1/estado 500 " in x and "clave=pruebas" in x for x in propias),
        "error_propio_sin_mensaje": f"error_interno=RuntimeError solicitud={cuerpo.get('solicitud')}" in texto,
    }
    incumplidos = sorted(k for k, v in criterios.items() if not v)
    assert not incumplidos, "incumplidos: " + ", ".join(incumplidos)  # v1: registro de acceso, traza, id...


def test_el_proceso_real_ignora_x_forwarded_for(tmp_path):
    clave = generar_clave()
    entorno = fa.entorno_de_proceso(tmp_path, API_PUBLICA_CLAVES=f"pruebas:sha256:{huella(clave)}",
                                    API_PUBLICA_FICHAS_POR_MINUTO_IP="2")
    with fa.proceso_uvicorn(fa.arranque_documentado(), entorno, tmp_path / "uvicorn.log") as base:
        with httpx.Client(base_url=base, trust_env=False, timeout=10) as c:
            codigos = [c.get("/api/v1/salud", headers={"X-Forwarded-For": f"198.51.100.{i}"}).status_code
                       for i in range(1, 6)]
            sin_cabecera = c.get("/api/v1/salud")
    assert codigos == [200, 200, 429, 429, 429]  # v1: 200 x 5
    assert sin_cabecera.status_code == 429 and int(sin_cabecera.headers["Retry-After"]) >= 1


def test_todos_los_ejemplos_de_arranque_usan_las_opciones_soportadas():
    documentos = [RAIZ / "README.md", RAIZ / "ROADMAP.md", RAIZ / "ARCHITECTURE.md", fa.BACKEND / ".env.example",
                  *sorted((fa.BACKEND / "docs").glob("fase8*.md")),
                  *sorted((fa.BACKEND / "app" / "api" / "publica").glob("*.py"))]
    completos: dict[str, list[bool]] = {}
    for documento in documentos:
        for comando in fa.COMANDO.findall(documento.read_text(encoding="utf-8")):
            completos.setdefault(documento.name, []).append(OPCIONES <= set(comando.split()))
    assert {"README.md", "ROADMAP.md", "ARCHITECTURE.md", ".env.example", "fase8_api_publica.md",
            "fase8_windows.md", "aplicacion.py"} <= set(completos)
    assert all(all(v) for v in completos.values()), completos
    assert OPCIONES <= set(fa.arranque_documentado())
    assert "fa.arranque_documentado()" in (fa.BACKEND / "tests" / "postgres_fase8.py").read_text(encoding="utf-8")


def test_la_seleccion_de_windows_incluye_la_api_publica_y_sus_regresiones():
    lista = fa.BACKEND / "tests" / "seleccion_windows.txt"
    seleccion = [x for x in lista.read_text(encoding="utf-8").splitlines() if x]
    assert "tests/unit/api_publica" in seleccion  # la carpeta: las pruebas de v1 y las regresiones de v2
    guia = (fa.BACKEND / "docs" / "fase8_windows.md").read_text(encoding="utf-8")
    assert "entrega aparte" not in guia and "no cambia la lista" not in guia and "pendiente" in guia
