"""Ayudante EXPLÍCITO de pruebas para la consola local (Fase 10, E10.1).

No desactiva la seguridad: crea un almacén de seguridad temporal con una cuenta, lo inyecta en
`app.state.almacen_seguridad`, inicia sesión por el flujo real (`GET`/`POST /acceso`, con presesión y CSRF)
y devuelve un cliente con la cookie de sesión. Ese cliente añade la cabecera `X-CSRF-Token` en las
escrituras, como hace `static/js/consola_csrf.js` en las solicitudes HTMX de la consola.

Los parámetros de scrypt son bajos solo en este almacén de prueba (el de la CLI usa los de producción).
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.seguridad_consola.almacen import AlmacenSeguridad, derivar_csrf, ruta_predeterminada
from app.seguridad_consola.credenciales import ParametrosScrypt

PARAMETROS_PRUEBA = ParametrosScrypt(n=2 ** 10, r=8, p=1)
CONTRASENA_PRUEBA = "contrasena-de-prueba-larga"
LOCAL = ("127.0.0.1", 50000)
_CSRF_ACCESO = re.compile(r'name="csrf_token" value="([0-9a-f]{64})"')


def almacen_de_prueba(directorio: str | Path | None = None, cuentas=(("admin", "administrador"),), reloj=None) -> AlmacenSeguridad:
    carpeta = Path(directorio) if directorio is not None else Path(tempfile.mkdtemp(prefix="lp-consola-prueba-"))
    kw = {"parametros": PARAMETROS_PRUEBA, "minimos": PARAMETROS_PRUEBA}
    if reloj is not None:
        kw["reloj"] = reloj
    archivo = ruta_predeterminada(carpeta / "seguridad")
    almacen = AlmacenSeguridad(archivo, **kw) if archivo.exists() else AlmacenSeguridad.crear(archivo, **kw)
    existentes = {c["usuario"] for c in almacen.cuentas()}
    for usuario, rol in cuentas:
        if usuario not in existentes:
            almacen.crear_cuenta(usuario, CONTRASENA_PRUEBA, rol, actor="prueba")
    return almacen


class ClienteConsola(TestClient):
    """TestClient que envía `X-CSRF-Token` en las escrituras (como `consola_csrf.js` en HTMX)."""

    csrf: str | None = None

    def request(self, method, url, *args, **kwargs):
        if method.upper() not in ("GET", "HEAD", "OPTIONS") and self.csrf:
            cabeceras = dict(kwargs.pop("headers", None) or {})
            cabeceras.setdefault("X-CSRF-Token", self.csrf)
            kwargs["headers"] = cabeceras
        return super().request(method, url, *args, **kwargs)


def iniciar_sesion(cliente: TestClient, usuario: str, contrasena: str = CONTRASENA_PRUEBA):
    pagina = cliente.get("/acceso")
    token = _CSRF_ACCESO.search(pagina.text)
    assert token, "el formulario de acceso no trae su token"
    return cliente.post("/acceso", data={"csrf_token": token.group(1), "usuario": usuario, "contrasena": contrasena,
                                         "siguiente": "/"}, follow_redirects=False)


def cliente_autenticado(app, rol: str = "administrador", *, usuario: str | None = None, almacen: AlmacenSeguridad | None = None,
                        base_url: str = "http://localhost:8000", client=LOCAL, **kw) -> ClienteConsola:
    """Cliente con una sesión legítima del rol pedido. Si `client` no es local, la sesión se obtiene desde
    loopback y después se usa con ese cliente (que la consola rechazará por su límite local)."""
    usuario = usuario or {"lector": "lectora", "operador": "operadora", "administrador": "admin"}.get(rol, rol)
    almacen = almacen or almacen_de_prueba(cuentas=((usuario, rol),))
    if usuario not in {c["usuario"] for c in almacen.cuentas()}:
        almacen.crear_cuenta(usuario, CONTRASENA_PRUEBA, rol, actor="prueba")
    app.state.almacen_seguridad = almacen
    acceso = TestClient(app, base_url=base_url, client=LOCAL)
    r = iniciar_sesion(acceso, usuario)
    assert r.status_code == 303, f"inicio de sesión de prueba fallido: {r.status_code}"
    cliente = ClienteConsola(app, base_url=base_url, client=client, **kw)
    for nombre, valor in acceso.cookies.items():
        cliente.cookies.set(nombre, valor)
    cliente.csrf = derivar_csrf(acceso.cookies.get("lp_consola_sesion"), "sesion")
    cliente.almacen = almacen
    return cliente


_COMPARTIDO: dict = {}


def almacen_compartido() -> AlmacenSeguridad:
    """Almacén temporal único por proceso de pruebas (se borra al terminar el intérprete)."""
    if "almacen" not in _COMPARTIDO:
        _COMPARTIDO["carpeta"] = tempfile.TemporaryDirectory(prefix="lp-consola-pruebas-")
        _COMPARTIDO["almacen"] = almacen_de_prueba(_COMPARTIDO["carpeta"].name, cuentas=())
        _COMPARTIDO["n"] = 0
    return _COMPARTIDO["almacen"]


def cliente_de_consola(app, *, rol: str = "administrador", base_url: str = "http://localhost:8000", client=LOCAL,
                       **kw) -> ClienteConsola:
    """Para las pruebas preexistentes de la consola: sesión legítima de una cuenta propia del almacén compartido.

    Cada cliente usa una cuenta distinta, de modo que varios clientes de una misma prueba conservan su sesión
    (el límite de sesiones por cuenta no los desaloja) y comparten el almacén que queda inyectado en la app.
    """
    almacen = almacen_compartido()
    _COMPARTIDO["n"] += 1
    return cliente_autenticado(app, rol, usuario=f"prueba-{_COMPARTIDO['n']}", almacen=almacen, base_url=base_url,
                               client=client, **kw)
