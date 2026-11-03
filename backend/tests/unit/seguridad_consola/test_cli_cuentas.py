"""E10.1: CLI de cuentas (`scripts.consola_cuentas`) sobre almacenes temporales; parámetros scrypt de producción."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess

import pytest

from app.seguridad_consola import almacen as al
from scripts import consola_cuentas as cli

CONTRASENA = "contrasena-de-la-cli-larga"


def _ejecutar(monkeypatch, capsys, directorio, *argumentos, entrada=None):
    if entrada is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(entrada))
    codigo = cli.main(["--directorio", str(directorio), *argumentos])
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err


def test_crear_listar_cambiar_y_comprobar(monkeypatch, capsys, tmp_path):
    d = tmp_path / "seg"
    codigo, out, _ = _ejecutar(monkeypatch, capsys, d, "crear", "--usuario", "daniel", "--rol", "administrador",
                               "--contrasena-stdin", entrada=CONTRASENA + "\n")
    assert codigo == 0 and "creado" in out and CONTRASENA not in out
    archivo = al.ruta_predeterminada(d)
    if os.name != "nt":
        assert oct(archivo.stat().st_mode & 0o777) == "0o600" and oct(d.stat().st_mode & 0o777) == "0o700"
    assert CONTRASENA.encode() not in archivo.read_bytes()
    codigo, out, _ = _ejecutar(monkeypatch, capsys, d, "listar")
    assert codigo == 0 and json.loads(out) == [{"usuario": "daniel", "rol": "administrador", "activa": True, "sesiones": 0}]
    assert _ejecutar(monkeypatch, capsys, d, "comprobar")[:2] == (0, '{"estado": "disponible"}\n')
    codigo, _, err = _ejecutar(monkeypatch, capsys, d, "cambiar-rol", "--usuario", "daniel", "--rol", "lector")
    assert codigo == 1 and "único administrador" in err
    assert _ejecutar(monkeypatch, capsys, d, "crear", "--usuario", "ana", "--rol", "operador", "--contrasena-stdin",
                     entrada=CONTRASENA + "\r\n")[0] == 0
    a = al.AlmacenSeguridad(archivo)
    assert a.autenticar("ana", CONTRASENA, a.crear_presesion(), "l")[0] == "ok"  # CRLF de Windows recortado
    assert _ejecutar(monkeypatch, capsys, d, "cambiar-contrasena", "--usuario", "ana", "--contrasena-stdin",
                     entrada="otra-contrasena-larga\n")[0] == 0
    assert _ejecutar(monkeypatch, capsys, d, "desactivar", "--usuario", "ana")[0] == 0
    assert _ejecutar(monkeypatch, capsys, d, "revocar-sesiones")[0] == 0
    codigo, out, _ = _ejecutar(monkeypatch, capsys, d, "auditoria", "--limite", "20")
    eventos = [e["evento"] for e in json.loads(out)]
    assert {"cuenta_creada", "contrasena_cambiada", "cuenta_desactivada", "sesiones_revocadas"} <= set(eventos)
    assert CONTRASENA not in out and "otra-contrasena-larga" not in out


def test_contrasena_nunca_como_argumento(monkeypatch, capsys, tmp_path):
    with pytest.raises(SystemExit) as e:
        cli.main(["--directorio", str(tmp_path), "crear", "--usuario", "x1x", "--rol", "lector", "--contrasena", "abc"])
    assert e.value.code == 2


def test_contrasena_debil_y_cuenta_duplicada_rechazadas(monkeypatch, capsys, tmp_path):
    d = tmp_path / "seg"
    assert _ejecutar(monkeypatch, capsys, d, "crear", "--usuario", "daniel", "--rol", "administrador",
                     "--contrasena-stdin", entrada="corta\n")[0] == 1
    assert not d.exists()  # la validación ocurre antes de crear nada
    assert _ejecutar(monkeypatch, capsys, d, "crear", "--usuario", "daniel", "--rol", "administrador",
                     "--contrasena-stdin", entrada=CONTRASENA + "\n")[0] == 0
    assert _ejecutar(monkeypatch, capsys, d, "crear", "--usuario", "daniel", "--rol", "lector",
                     "--contrasena-stdin", entrada=CONTRASENA + "\n")[0] == 1


def test_comprobar_sin_almacen(monkeypatch, capsys, tmp_path):
    codigo, out, _ = _ejecutar(monkeypatch, capsys, tmp_path / "nada", "comprobar")
    assert codigo == 1 and json.loads(out) == {"estado": "no_disponible", "motivo": "no_provisionada"}
    assert not (tmp_path / "nada").exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="requiere git")
def test_no_crea_dentro_de_un_repositorio_si_git_no_lo_ignora(monkeypatch, capsys, tmp_path):
    repo = tmp_path / "repo con espacios"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    destino = repo / "privado" / "consola"
    codigo, _, err = _ejecutar(monkeypatch, capsys, destino, "crear", "--usuario", "daniel", "--rol", "administrador",
                               "--contrasena-stdin", entrada=CONTRASENA + "\n")
    assert codigo == 1 and "Git no ignora" in err and not destino.exists()
    (repo / ".gitignore").write_text("privado/\n", encoding="utf-8")
    assert _ejecutar(monkeypatch, capsys, destino, "crear", "--usuario", "daniel", "--rol", "administrador",
                     "--contrasena-stdin", entrada=CONTRASENA + "\n")[0] == 0
    estado = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout
    assert "privado" not in estado


def test_ruta_relativa_se_resuelve_desde_backend_y_esta_ignorada(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # el directorio actual no influye
    archivo = al.ruta_predeterminada("privado/consola")
    assert archivo == al.BACKEND / "privado" / "consola" / "seguridad.sqlite3"
    assert al.ruta_predeterminada(tmp_path / "x") == tmp_path / "x" / "seguridad.sqlite3"
    if shutil.which("git") and (al.BACKEND.parent / ".git").exists():
        r = subprocess.run(["git", "-C", str(al.BACKEND.parent), "check-ignore", "-q", "--no-index",
                            "backend/privado/consola/seguridad.sqlite3"])
        assert r.returncode == 0
