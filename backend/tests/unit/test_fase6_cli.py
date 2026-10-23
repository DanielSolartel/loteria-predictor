"""CLI y binding de destinos reales, sin abrir una BD/proveedor del usuario."""
from io import StringIO
from pathlib import Path
import json

import pytest

from app.api.automatizacion_dependencies import construir_automatizacion, referencia_destinos
from app.core.config import Settings
from scripts.operacion_automatica import ejecutar


class SinAcceso:
    def por_juego(self, codigo):
        raise AssertionError("Estas órdenes no deben abrir recursos de un juego")


@pytest.fixture
def cli(tmp_path):
    backend = tmp_path / "worktree con espacios" / "backend"
    backend.mkdir(parents=True)
    ajustes = Settings(_env_file=None, directorio_automatizacion="storage/automatizacion", database_url="postgresql+psycopg://usuario:MARCADOR_PRIVADO@127.0.0.1:1/pruebas")
    ruta = tmp_path / "operacion con espacios.json"
    def servicio_factory(**kw):
        return construir_automatizacion(**kw, adaptador=SinAcceso())
    def llamar(*args):
        out, err = StringIO(), StringIO()
        codigo = ejecutar(["--config", str(ruta), *args], ajustes=ajustes, backend=backend,
                          servicio_factory=servicio_factory, salida=out, errores=err)
        assert "MARCADOR_PRIVADO" not in out.getvalue() + err.getvalue()
        return codigo, out.getvalue(), err.getvalue()
    return backend, ajustes, ruta, llamar


def test_rutas_son_absolutas_y_no_crean_almacenes(cli):
    backend, _, ruta, llamar = cli
    codigo, out, _ = llamar("rutas")
    assert codigo == 0 and not ruta.exists() and not (backend / "storage").exists()
    dato = json.loads(out)
    assert all(Path(v).is_absolute() for v in dato["destinos"].values())
    assert "database_url" not in out and "usuario:" not in out


def test_preparar_requiere_confirmar_y_estado_no_crea_datos(cli):
    backend, _, ruta, llamar = cli
    assert llamar("preparar")[0] == 2
    assert not ruta.exists()
    codigo, out, _ = llamar("estado")
    assert codigo == 0 and json.loads(out)["estado"] == "sin_configurar"
    assert not (backend / "storage").exists()


def test_preparar_pausa_reanudar_y_pausar_no_consultan_juegos(cli):
    _, _, ruta, llamar = cli
    assert llamar("preparar", "--confirmar-destinos")[0] == 0
    b = ruta.read_bytes();t = ruta.stat().st_mtime_ns
    assert llamar("preparar", "--confirmar-destinos")[0] == 0
    assert ruta.read_bytes() == b and ruta.stat().st_mtime_ns == t
    assert json.loads(llamar("estado")[1])["estado"] == "pausada"
    assert llamar("reanudar")[0] == 0
    assert json.loads(llamar("estado")[1])["estado"] == "habilitada"
    assert llamar("pausar")[0] == 0
    assert json.loads(llamar("ciclo")[1])["estado"] == "pausada"
    assert "MARCADOR_PRIVADO" not in ruta.read_text(encoding="utf-8")


def test_cambio_cwd_no_cambia_destinos_y_cambio_backend_rechaza(cli, tmp_path, monkeypatch):
    backend, ajustes, ruta, llamar = cli
    assert llamar("preparar", "--confirmar-destinos")[0] == 0
    monkeypatch.chdir(tmp_path)
    assert llamar("reanudar")[0] == 0
    otro = construir_automatizacion(str(ruta), ajustes=ajustes, backend=tmp_path / "otra copia", adaptador=SinAcceso())
    assert otro.panel()["estado"] == "sin_configurar"
    with pytest.raises(ValueError):
        otro.reanudar()
    assert referencia_destinos(ajustes, backend)["destinos"] == json.loads(ruta.read_bytes())["destinos"]


@pytest.mark.parametrize("alterar", ["database", "ruta", "credencial", "json"])
def test_estado_ajeno_o_config_rota_no_habilita_operacion(cli, alterar):
    _, _, ruta, llamar = cli
    assert llamar("preparar", "--confirmar-destinos")[0] == 0
    c = json.loads(ruta.read_bytes())
    if alterar == "database":c["database_sha256"] = "0" * 64
    elif alterar == "ruta":c["destinos"]["directorio_carteras_modelos"] += "-otra"
    elif alterar == "credencial":c["password"] = "MARCADOR_PRIVADO"
    if alterar == "json":ruta.write_text("{", encoding="utf-8")
    else:ruta.write_text(json.dumps(c), encoding="utf-8")
    original = ruta.read_bytes()
    assert llamar("reanudar")[0] == 2
    assert ruta.read_bytes() == original
    assert json.loads(llamar("estado")[1])["estado"] == "sin_configurar"


def test_rechazar_revision_reutiliza_decision_y_conserva_propuesta(cli):
    backend, ajustes, ruta, llamar = cli
    assert llamar("preparar", "--confirmar-destinos")[0] == 0
    servicio = construir_automatizacion(str(ruta), ajustes=ajustes, backend=backend, adaptador=SinAcceso())
    propuesta = {"clave": "a" * 64, "juego": "BALOTO", "numero_sorteo": 42,
                 "estado": "pendiente", "antes": {"x": 1}, "propuesta": {"x": 2}, "huellas": {}}
    servicio.almacen.guardar_revision(propuesta)
    args = ("revision", "--clave", "a" * 64, "--rechazar", "--nota", "Fuente discrepante revisada")
    assert llamar(*args)[0] == 0
    antes = {p: (p.read_bytes(),p.stat().st_mtime_ns) for p in servicio.almacen.directorio.rglob("*.json")}
    codigo, out, _ = llamar(*args)
    assert codigo == 0 and json.loads(out)["reutilizada"]
    assert all((p.read_bytes(),p.stat().st_mtime_ns)==v for p,v in antes.items())
    assert servicio.almacen.revision("a" * 64) == propuesta


def test_ayuda_no_necesita_configuracion(cli):
    assert cli[3]("--help")[0] == 0


def test_rechazo_explicitamente_posterior_no_reutiliza_rechazo_obsoleto(cli, monkeypatch):
    from datetime import datetime, timezone, timedelta
    import scripts.operacion_automatica as comando

    backend, ajustes, ruta, llamar = cli
    assert llamar("preparar", "--confirmar-destinos")[0] == 0
    servicio = construir_automatizacion(str(ruta), ajustes=ajustes, backend=backend, adaptador=SinAcceso())
    clave = "a" * 64
    propuesta = {"clave": clave, "juego": "BALOTO", "numero_sorteo": 42,
                 "estado": "pendiente", "antes": {"x": 1}, "propuesta": {"x": 2}, "huellas": {}}
    servicio.almacen.guardar_revision(propuesta)
    inicio = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
    servicio.almacen.guardar_decision_revision(clave, {"estado": "rechazada", "nota": "Fuente cotejada", "en": inicio.isoformat()})
    servicio.almacen.guardar_decision_revision(clave, {"estado": "observacion", "nota": "Revisar de nuevo", "en": (inicio + timedelta(minutes=1)).isoformat()})
    anteriores = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in servicio.almacen.directorio.rglob("*.json")}
    monkeypatch.setattr(comando, "ahora_utc", lambda: inicio + timedelta(minutes=2))
    args = ("revision", "--clave", clave, "--rechazar", "--nota", "Fuente cotejada")
    codigo, out, _ = llamar(*args)
    assert codigo == 0 and not json.loads(out)["reutilizada"]
    assert len(servicio.almacen.decisiones_revision(clave)) == 3
    assert not servicio.almacen.revisiones_pendientes("BALOTO", 1, 100)
    assert all((p.read_bytes(), p.stat().st_mtime_ns) == valor for p, valor in anteriores.items())
    despues = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in servicio.almacen.directorio.rglob("*.json")}
    assert json.loads(llamar(*args)[1])["reutilizada"]
    assert all((p.read_bytes(), p.stat().st_mtime_ns) == valor for p, valor in despues.items())
