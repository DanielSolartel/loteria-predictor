"""E10.4 v2: regresiones de la auditoria de la v1 (E104-LIM-03, PLA-04, GEN-02, DAT-06) SIN PostgreSQL.

Solo usan interfaces que ya tenia la v1 (`capturar`, `comprobar_generacion`, `recorrer`) para que FALLEN sobre la
v1 por el comportamiento auditado, no por campos o funciones nuevos. Las de IMP-01, RES-05 y los plazos con un
servidor real estan en `test_propiedad_y_restauracion_pg.py` (PostgreSQL real aislado).
"""
from __future__ import annotations

import os
import shutil
import socket
import stat
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from app.infrastructure.generaciones import captura as ca
from app.infrastructure.generaciones import consultas
from app.infrastructure.generaciones import firma
from tests.unit.generaciones import paquete_sintetico as ps
from tests.unit.generaciones.conftest import BACKEND

posix = pytest.mark.skipif(sys.platform == "win32", reason="enlaces y modos POSIX")


def _modos(*rutas):
    return [stat.S_IMODE(os.lstat(r).st_mode) for r in rutas]


@pytest.fixture
def claves(tmp_path):
    privada, publica = tmp_path / "firma.pem", tmp_path / "firma.pub"
    firma.generar(privada, publica)
    return privada, publica


@pytest.fixture
def ajeno(tmp_path):
    carpeta = tmp_path / "fuera"
    (carpeta / "sub").mkdir(parents=True)
    os.chmod(carpeta, 0o700)
    secreto = carpeta / "sub" / "sentinela.txt"
    secreto.write_text("datos sinteticos")
    secreto.chmod(0o400)
    os.chmod(carpeta / "sub", 0o500)
    yield carpeta, secreto
    for r in (carpeta, carpeta / "sub"):
        os.chmod(r, 0o700)


# --- E104-LIM-03 ---------------------------------------------------------------------------------------------
@posix
def test_lim03_resto_enlazado_fuera_del_destino_no_se_sigue_ni_cambia_permisos(tmp_path, claves, ajeno):
    carpeta, secreto = ajeno
    destino = tmp_path / "capturas"
    destino.mkdir()
    (destino / ".preparando-ajeno").symlink_to(carpeta, target_is_directory=True)
    antes = _modos(carpeta, carpeta / "sub", secreto)
    with patch.object(ca, "_intento", side_effect=RuntimeError("sin PostgreSQL")):
        try:
            ca.capturar(ca.Fuente("postgresql://modelo/prueba_e104", {}), destino, claves[0], intentos=1)
            error = None
        except Exception as e:  # noqa: BLE001 - primero se comprueba lo que se toco fuera
            error = e
    assert _modos(carpeta, carpeta / "sub", secreto) == antes  # nada fuera del destino cambio de permisos
    assert secreto.read_text() == "datos sinteticos"
    assert isinstance(error, ca.CapturaRechazada), repr(error)
    assert (destino / ".preparando-ajeno").is_symlink()  # no es propio: se deja y se avisa


@posix
def test_lim03_enlace_dentro_de_la_preparacion_no_se_sigue_al_limpiar(tmp_path, claves, ajeno):
    """Un descendiente de la preparacion propia sustituido por un enlace a algo de fuera durante el intento."""
    carpeta, secreto = ajeno
    antes = _modos(carpeta, carpeta / "sub", secreto)

    def intento(_fuente, prep, *_a, **_k):
        (prep / "archivos").mkdir()
        (prep / "archivos" / "pronosticos").symlink_to(carpeta, target_is_directory=True)
        (prep / "fichero-enlazado").symlink_to(secreto)
        raise OSError("fallo sintetico tras la copia")

    destino = tmp_path / "capturas"
    with patch.object(ca, "_intento", side_effect=intento):
        with pytest.raises(ca.CapturaRechazada):
            ca.capturar(ca.Fuente("postgresql://modelo/prueba_e104", {}), destino, claves[0], intentos=1)
    assert _modos(carpeta, carpeta / "sub", secreto) == antes
    assert secreto.read_text() == "datos sinteticos" and (carpeta / "sub").is_dir()
    assert not list(destino.glob(".preparando-*"))  # la preparacion propia si se retiro (sin seguir los enlaces)


# --- E104-PLA-04 ---------------------------------------------------------------------------------------------
def test_pla04_un_intento_que_agota_el_plazo_no_se_sella(tmp_path, claves):
    datos = {"instantes": {}, "catalogo": {}, "esquema": {"revision_alembic": "0006", "huella": "0" * 64},
             "juegos": {}, "huellas": {}, "copiados": {}, "coherencia": ps.COHERENCIA}

    def lento(*_a, **_k):
        time.sleep(0.2)
        return datos

    with patch.object(ca, "_intento", side_effect=lento):
        with pytest.raises(ca.CapturaRechazada) as error:
            ca.capturar(ca.Fuente("postgresql://modelo/prueba_e104", {}), tmp_path / "c", claves[0], intentos=1,
                        plazo=0.05)
    assert error.value.motivos[-1]["motivo"] == "plazo_total_agotado"
    assert not [p for p in (tmp_path / "c").iterdir() if p.is_dir() and not p.name.startswith(".")
                and p.name != "alertas"]


def test_pla04_servidor_que_no_responde_no_bloquea_mas_alla_del_plazo(tmp_path, claves):
    """Conexion lenta: un servidor que acepta TCP y nunca contesta. La captura (proceso aparte, para poder
    cortarla si se bloquea) debe terminar dentro del plazo con un rechazo y sin generacion."""
    servidor = socket.socket()
    servidor.bind(("127.0.0.1", 0))
    servidor.listen(8)
    puerto = servidor.getsockname()[1]
    codigo = textwrap.dedent(f"""
        import sys, time
        from pathlib import Path
        from app.infrastructure.generaciones import captura as ca
        inicio = time.monotonic()
        try:
            ca.capturar(ca.Fuente("postgresql://u:p@127.0.0.1:{puerto}/prueba_e104", {{}}), Path(sys.argv[1]),
                        Path(sys.argv[2]), intentos=3, espera=0.0, plazo=2.0)
            print("SELLADA")
        except ca.CapturaRechazada as e:
            print("RECHAZADA", e.motivos[-1]["motivo"], round(time.monotonic() - inicio, 1))
    """)
    try:
        inicio = time.monotonic()
        try:
            r = subprocess.run([sys.executable, "-B", "-c", codigo, str(tmp_path / "c"), str(claves[0])],
                               cwd=BACKEND, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            pytest.fail("la captura siguio bloqueada en la conexion 30 s con un plazo de 2 s")
        duracion = time.monotonic() - inicio
    finally:
        servidor.close()
    assert r.stdout.startswith("RECHAZADA"), r.stdout + r.stderr[-500:]
    assert duracion < 15


# --- E104-GEN-02 ---------------------------------------------------------------------------------------------
class _Motor:
    def __init__(self, fila, revisiones):
        self.fila, self.revisiones = fila, revisiones

    def connect(self):
        motor = self

        class _C:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, sql):
                class _R:
                    def one(self):
                        return motor.fila

                    def all(self):
                        return motor.revisiones if "alembic_version" in str(sql) else []
                return _R()
        return _C()


def _aceptada(tmp_path, cambio=None):
    from app.infrastructure.generaciones import importacion as im
    from app.infrastructure.generaciones.formato import sha256_archivo

    paquete, privada, publica = ps.construir(tmp_path / "p")
    if cambio:
        paquete = ps.refirmar(paquete, privada, cambio)
    carpeta = tmp_path / "srv" / "generaciones" / paquete.name
    shutil.copytree(paquete, carpeta, ignore=shutil.ignore_patterns("base"))
    fila = (im.nombre_base(paquete.name, True), im.comentario(paquete.name,
                                                             sha256_archivo(carpeta / "manifiesto.json")[1]), "on")
    return carpeta, publica, fila


def test_gen02_generacion_firmada_de_otro_codigo_de_la_api_no_arranca(tmp_path):
    from app.api.publica import perfil_privado as pp

    def otro(m):
        m["codigo"]["huella_app"] = "f" * 64
    carpeta, publica, fila = _aceptada(tmp_path, otro)
    with pytest.raises(pp.PerfilPrivadoNoValido, match="otro codigo"):
        pp.comprobar_generacion(carpeta, publica, _Motor(fila, [("0006",)]))


def test_gen02_base_conectada_en_otra_revision_del_esquema_no_arranca(tmp_path):
    """El manifiesto declara la revision correcta (etiqueta); la base conectada esta en otra: se contrasta."""
    from app.api.publica import perfil_privado as pp

    carpeta, publica, fila = _aceptada(tmp_path)
    with pytest.raises(pp.PerfilPrivadoNoValido, match="revision"):
        pp.comprobar_generacion(carpeta, publica, _Motor(fila, [("0005",)]))


def test_gen02_mismo_codigo_y_misma_revision_arranca(tmp_path):
    from app.api.publica import perfil_privado as pp

    carpeta, publica, fila = _aceptada(tmp_path)
    assert pp.comprobar_generacion(carpeta, publica, _Motor(fila, [("0006",)]))["id"] == carpeta.name


# --- E104-DAT-06 ---------------------------------------------------------------------------------------------
def _api(vacio: bool, pedidas: list, dano: str | None = None):
    import re
    from urllib.parse import parse_qs, urlsplit

    def get(url):
        pedidas.append(url)
        ruta = urlsplit(url).path
        if dano == "estado_500" and ruta.endswith("/estadisticas/panel"):
            return 500, {"error": {"codigo": "interno"}}
        if ruta.startswith("/api/v1/simulaciones/"):
            return 404, {"error": {"codigo": "no_encontrado", "solicitud": "x"}}
        if re.search(r"/(modelos-guardados|carteras-guardadas)/[0-9a-f]+$", ruta) or re.search(r"/sorteos/\d+$", ruta):
            return (404, {"error": {"codigo": "no_encontrado"}}) if vacio else (200, {})
        if ruta.endswith("/sorteos"):
            return 200, {"total": 0 if vacio else 1, "sorteos": [] if vacio else [{"numero_sorteo": 1}]}
        if ruta.endswith("/estadisticas"):
            return 200, {"metricas": [{"metrica": "frecuencia", "parametro": False}]}
        if ruta.endswith("/predicciones"):
            return 200, {"prediccion": None if vacio else {"objetivo": 2}}
        if ruta.endswith("/fiabilidad"):
            return 200, {"base": {"estado": "consultada"}, "lineas": [] if vacio else [
                {"evaluaciones": [{"estado": "muestra_insuficiente", "muestra": {"sorteos": 1}}]}]}
        if ruta.endswith(("/modelos-guardados", "/carteras-guardadas")):
            cuerpo = {"total": 0 if vacio else 1, "elementos": [] if vacio else [{"clave": "a" * 64}]}
            if dano == "ilegibles" and ruta.endswith("/carteras-guardadas"):
                cuerpo["ilegibles"] = 2
            return 200, cuerpo
        if ruta.endswith("/simulaciones"):
            return 200, {"simulaciones": []}
        if ruta.endswith("/resultados"):
            p = parse_qs(urlsplit(url).query).get("procedencia", ["operacion"])[0]
            return 200, {"lineas": [] if vacio else [{"clave": "a", "procedencia": p}],
                         "resumenes": {} if vacio else {"a": {"incluidos": 1}},
                         "procedencias": {q: {"emisiones": 0 if vacio else 1} for q in consultas.PROCEDENCIAS}}
        return 200, {}
    return get


def test_dat06_fuente_real_vacia_es_valida_y_no_se_inventan_claves():
    pedidas = []
    resultado = consultas.recorrer(_api(True, pedidas))
    assert resultado["fallos"] == []
    assert not [u for u in pedidas if u.endswith("0" * 64)]  # ningun detalle con una clave inventada
    assert not [u for u in pedidas if "/sorteos/" in u]  # ni un sorteo que el listado no contiene


@pytest.mark.parametrize("dano", ["ilegibles", "estado_500"])
def test_dat06_los_danos_siguen_siendo_estrictos(dano):
    resultado = consultas.recorrer(_api(False, [], dano))
    assert resultado["fallos"], dano
