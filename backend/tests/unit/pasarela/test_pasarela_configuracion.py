"""Fase 9.1, pasarela: configuracion solo del servidor, destino loopback fijo y
validado, hosts y origenes explicitos, clave fuera de Git y modo cerrado."""
from __future__ import annotations

import subprocess

import pytest
from pydantic import SecretStr

from app.pasarela.configuracion import (
    ARCHIVO_PRIVADO,
    DIST_POR_DEFECTO,
    AjustesPasarela,
    ConfiguracionNoValida,
    desde_ajustes,
    leer_consola,
    leer_destino,
    leer_hosts,
    leer_origenes,
)
from tests.unit.pasarela import fixtures_pasarela as fp


def test_valores_por_defecto_locales_y_cerrados(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # sin archivo privado
    for nombre in ("CLAVE_API", "API_URL", "HOSTS", "ORIGENES", "DIST", "CONSOLA_LOCAL"):
        monkeypatch.delenv(f"PASARELA_{nombre}", raising=False)
    conf = desde_ajustes(AjustesPasarela())
    assert conf.destino.url == "http://127.0.0.1:8010" and not conf.abierta
    assert conf.hosts == {"127.0.0.1:8020", "localhost:8020"}
    assert conf.origenes == {"http://127.0.0.1:8020", "http://localhost:8020"}
    assert conf.dist == DIST_POR_DEFECTO and conf.consola_local is None


@pytest.mark.parametrize("url", [
    "https://127.0.0.1:8010", "http://10.0.0.5:8010", "http://localhost:8010", "http://ejemplo.com:8010",
    "http://127.0.0.1", "http://u:p@127.0.0.1:8010", "http://127.0.0.1:8010/api", "http://127.0.0.1:8010?x=1",
    "http://127.0.0.1:8010#f", "http://127.0.0.1:0", "http://127.0.0.1:99999", "ftp://127.0.0.1:8010", "",
    "http://[::ffff:8.8.8.8]:8010"])
def test_destino_no_local_o_con_partes_extra_impide_arrancar(url):
    with pytest.raises(ConfiguracionNoValida) as error:
        leer_destino(url)
    assert "u:p" not in str(error.value)


@pytest.mark.parametrize("url, host, puerto", [("http://127.0.0.1:8010", "127.0.0.1", 8010),
                                               ("http://127.0.0.2:9000/", "127.0.0.2", 9000),
                                               ("http://[::1]:8010", "::1", 8010)])
def test_destino_loopback_valido(url, host, puerto):
    d = leer_destino(url)
    assert (d.host, d.puerto) == (host, puerto)


@pytest.mark.parametrize("texto", ["*", "127.0.0.1", "evil.example:8020", "127.0.0.1:*", "0.0.0.0:8020",
                                   "127.0.0.1:0", "", "localhost:8020,*.example:8020"])
def test_hosts_explicitos_y_locales(texto):
    with pytest.raises(ConfiguracionNoValida):
        leer_hosts(texto)
    assert leer_hosts("127.0.0.1:8020, 127.0.0.1:5173") == {"127.0.0.1:8020", "127.0.0.1:5173"}


@pytest.mark.parametrize("texto", ["*", "null", "http://evil.example:8020", "https://127.0.0.1:8020",
                                   "http://127.0.0.1:8020/ruta", "http://127.0.0.1", ""])
def test_origenes_explicitos_y_locales(texto):
    with pytest.raises(ConfiguracionNoValida):
        leer_origenes(texto)
    assert leer_origenes("http://127.0.0.1:5173") == {"http://127.0.0.1:5173"}


def test_enlace_a_la_consola_opcional_y_local():
    assert leer_consola("") is None and leer_consola("  ") is None
    assert leer_consola("http://127.0.0.1:8000") == "http://127.0.0.1:8000/"
    for malo in ("https://127.0.0.1:8000", "http://ejemplo.com:8000", "http://127.0.0.1:8000/admin",
                 "javascript:alert(1)", "http://127.0.0.1"):
        with pytest.raises(ConfiguracionNoValida):
            leer_consola(malo)


@pytest.mark.parametrize("clave, abierta", [("", False), ("corta", False), ("x" * 31, False),
                                            ("con espacio " * 4, False), ("lpk_" + "a" * 43, True)])
def test_sin_clave_valida_la_pasarela_queda_cerrada(clave, abierta, tmp_path):
    conf = fp.configuracion(fp.Destino("127.0.0.1", 9), tmp_path, clave)
    assert conf.abierta is abierta
    assert clave not in repr(conf) or not clave


def test_archivo_privado_reconocible_y_fuera_de_git(monkeypatch, tmp_path):
    clave = fp.clave_sintetica()
    (tmp_path / ARCHIVO_PRIVADO).write_text(f"PASARELA_CLAVE_API={clave}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PASARELA_CLAVE_API", raising=False)
    ajustes = AjustesPasarela()
    assert ajustes.clave_api.get_secret_value() == clave and clave not in repr(ajustes)
    backend = fp.Path(__file__).resolve().parents[3]
    r = subprocess.run(["git", "-C", str(backend), "check-ignore", "-q", ARCHIVO_PRIVADO], check=False)
    assert r.returncode == 0  # ignorado por backend/.gitignore
    assert isinstance(ajustes.clave_api, SecretStr)
