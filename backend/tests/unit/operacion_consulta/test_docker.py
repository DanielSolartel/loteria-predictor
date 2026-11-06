from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

from despliegue.operacion_consulta.docker import Docker, SONDA_API, SONDA_VINCULO
from despliegue.operacion_consulta.infraestructura import PREFIJO, componer, montajes, nginx
from despliegue.operacion_consulta.modelo import Plan, Rechazo, canonico


class CLI:
    """Modelo de la CLI: contrasta argumentos e inspect; no ejecuta contenedores."""
    def __init__(self, plan, propietario, carpeta):
        self.p, self.propietario, self.carpeta = plan, propietario, carpeta
        self.cs, self.ordenes = {}, []
        self.detener_ignorado = False

    def __call__(self, args, plazo):
        self.ordenes.append(args)
        assert plazo > 0
        if args[0] == "ps":
            return "\n".join(self.cs).encode()
        if args[0] == "inspect":
            return canonico([self.cs[i] for i in args[1:]])
        if args[:2] == ["network", "inspect"]:
            return canonico([{"Name": self.p.red_datos, "Internal": True,
                             "Labels": {PREFIJO + ".modo": "ensayo"},
                             "IPAM": {"Config": [{"Subnet": "172.29.0.0/24"}]}}])
        if args[0] == "compose":
            c = json.loads(Path(args[args.index("-f") + 1]).read_bytes())
            assert c == componer(self.p, self.propietario, self.carpeta)
            assert "--no-build" in args and args[args.index("--pull") + 1] == "never"
            assert c["services"]["proxy"]["ports"][0]["host_ip"] == "127.0.0.1"
            for nombre in ("api", "pasarela", "proxy"):
                if nombre not in args:
                    continue
                servicio = c["services"][nombre]
                iid = hashlib.sha256((self.p.id + nombre).encode()).hexdigest()
                labs = dict(servicio["labels"], **{"com.docker.compose.project": c["name"],
                                                  "com.docker.compose.service": nombre})
                redes = {self.p.red_datos if n == "datos" else c["name"] + "_" + n:
                         {"IPAddress": v.get("ipv4_address", "172.30.0.2")} for n, v in servicio["networks"].items()}
                puertos = {"18443/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(self.p.puerto)}]} if nombre == "proxy" else {}
                self.cs[iid] = {"Id": iid, "Config": {"Image": servicio["image"], "Labels": labs,
                                                      "User": servicio["user"], "Entrypoint": servicio["entrypoint"],
                                                      "Cmd": servicio["command"],
                                                      "Env": [k + "=" + v for k, v in servicio["environment"].items()]},
                                "HostConfig": {"Privileged": False, "ReadonlyRootfs": True, "PortBindings": puertos},
                                "Mounts": [{"Destination": d, "Source": o, "RW": False, "Type": "bind"}
                                           for d, o in montajes(self.p, self.carpeta, nombre).items()],
                                "State": {"Running": True}, "NetworkSettings": {"Networks": redes}}
            return b""
        if args[0] == "stop":
            if not self.detener_ignorado:
                for i in args[3:]:
                    self.cs[i]["State"]["Running"] = False
            return b""
        if args[0] == "exec":
            assert args[1] in self.cs
            if args[-1] == SONDA_VINCULO:
                return canonico({"id": self.p.generacion, "sha256_manifiesto": self.p.manifiesto_sha256,
                                 "huella_app": self.p.huella_app, "revision_esquema": "0006"})
            if args[-1] == SONDA_API:
                return canonico({"base": "disponible", "solicitudes": 1})
            assert args[2] == "nginx" and args[-1] in ("-t", "reload")
            return b""
        pytest.fail("orden no prevista: " + repr(args))


def preparado(almacen, plan):
    with almacen.exclusivo():
        e = almacen.inicializar()
        almacen.guardar_plan(plan)
    cli = CLI(plan, e["propietario"], str(almacen.ruta / ("r-" + plan.id)))
    op = Docker(almacen, e["propietario"], ejecutar=cli,
                sonda_tls=lambda *_: {"base": "disponible", "solicitudes": 1}, sonda_cierre=lambda *_: None)
    op.materializar(plan)
    op.arrancar(plan, time.monotonic() + 30)
    return op, cli


def test_render_endurecido_sin_publicar_secretos(almacen, plan):
    op, cli = preparado(almacen, plan)
    c = json.loads((op.carpeta(plan) / "compose.json").read_bytes())
    assert set(c["services"]) == {"api", "pasarela", "proxy"}
    for servicio in c["services"].values():
        assert servicio["read_only"] and servicio["cap_drop"] == ["ALL"] and servicio["pull_policy"] == "never"
        assert "build" not in servicio and all(m["read_only"] for m in servicio["volumes"])
    assert "DATABASE_URL" not in c["services"]["api"]["environment"]
    assert "PASARELA_CLAVE_API" not in c["services"]["pasarela"]["environment"]
    assert "ports" not in c["services"]["api"] and "ports" not in c["services"]["pasarela"]
    assert c["networks"]["datos"]["external"]
    assert (op.carpeta(plan).stat().st_mode & 0o777) == 0o755  # UID 101 puede leer el bind
    assert (almacen.ruta.stat().st_mode & 0o777) == 0o700
    assert "ssl_verify_client on" in nginx(plan) and "worker_shutdown_timeout 30s" in nginx(plan)


def test_ordenes_reales_del_adaptador_validan_y_paran_solo_ids(almacen, plan):
    op, cli = preparado(almacen, plan)
    plazo = time.monotonic() + 30
    op.validar(plan, plazo)
    op.publicar(plan, plazo)
    op.mantenimiento(plan, False, plazo)
    op.sonda(plan, plazo)
    op.mantenimiento(plan, True, plazo)
    ids = set(cli.cs)
    op.detener(plan, plazo)
    assert set(cli.cs) == ids  # parar conserva contenedores, bases y montajes
    orden = next(o for o in cli.ordenes if o[0] == "stop")
    assert set(orden[3:]) == ids
    assert not any(o[0] in ("rm", "down", "volume", "prune", "build", "push", "pull") for o in cli.ordenes)


@pytest.mark.parametrize("mutacion", ["propietario", "plan", "generacion", "imagen", "usuario", "rootfs",
                                     "privilegiado", "montaje", "escritura", "servicio_extra",
                                     "entorno", "comando", "red_extra", "puerto_publico", "volumen"])
def test_un_ajeno_impide_parar_todo_el_conjunto(almacen, plan, mutacion):
    op, cli = preparado(almacen, plan)
    d = next(iter(cli.cs.values()))
    if mutacion in ("propietario", "plan", "generacion"):
        d["Config"]["Labels"][PREFIJO + "." + mutacion] = "ajeno"
    elif mutacion == "imagen":
        d["Config"]["Image"] = "otra@sha256:" + "1" * 64
    elif mutacion == "usuario":
        d["Config"]["User"] = "0:0"
    elif mutacion == "rootfs":
        d["HostConfig"]["ReadonlyRootfs"] = False
    elif mutacion == "privilegiado":
        d["HostConfig"]["Privileged"] = True
    elif mutacion == "montaje":
        d["Mounts"][0]["Source"] = "/fuente/ajena"
    elif mutacion == "escritura":
        d["Mounts"][0]["RW"] = True
    elif mutacion == "servicio_extra":
        d["Config"]["Labels"]["com.docker.compose.service"] = "postgres"
    elif mutacion == "entorno":
        d["Config"]["Env"] = [v for v in d["Config"]["Env"] if not v.startswith("GENERACION_DIRECTORIO=")]
    elif mutacion == "comando":
        d["Config"]["Cmd"] = ["app.main:app"]
    elif mutacion == "red_extra":
        d["NetworkSettings"]["Networks"]["red-operativa"] = {"IPAddress": "172.27.0.20"}
    elif mutacion == "puerto_publico":
        d["HostConfig"]["PortBindings"] = {"8010/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8010"}]}
    elif mutacion == "volumen":
        d["Mounts"].append({"Type": "volume", "Destination": "/srv/otra"})
    antes = copy.deepcopy(cli.cs)
    with pytest.raises(Rechazo):
        op.detener(plan, time.monotonic() + 30)
    assert cli.cs == antes
    assert not any(o[0] == "stop" for o in cli.ordenes)


def test_stop_no_confirmado_es_error(almacen, plan):
    op, cli = preparado(almacen, plan)
    cli.detener_ignorado = True
    with pytest.raises(Rechazo, match="sigue_activo"):
        op.detener(plan, time.monotonic() + 30)


def test_drenaje_espera_limite_solo_con_proxy_propio(almacen, plan):
    from .conftest import Reloj
    op, cli = preparado(almacen, plan)
    reloj = Reloj()
    op.reloj = reloj
    op.dormir = lambda segundos: setattr(reloj, "t", reloj.t + segundos)
    op.drenar(plan, 120)
    assert reloj.t == 0  # candidato sin ingreso: no hay lectores que drenar
    op.publicar(plan, 120)
    op.drenar(plan, 120)
    assert reloj.t == 30
    with pytest.raises(Rechazo, match="sin_plazo"):
        op.drenar(plan, 40)


def test_reload_asincrono_se_confirma_antes_de_contar_el_drenaje(almacen, plan):
    from .conftest import Reloj
    op, cli = preparado(almacen, plan)
    op.publicar(plan, time.monotonic() + 30)
    reloj = Reloj()
    op.reloj = reloj
    op.dormir = lambda s: setattr(reloj, "t", reloj.t + s)
    intentos = []
    def cierre(*args):
        assert any(o[0] == "exec" and o[-1] == "reload" for o in cli.ordenes)
        intentos.append(reloj.t)
        if len(intentos) < 3:
            raise Rechazo("todavia_abierto")
    op.sonda_cierre = cierre
    op.mantenimiento(plan, True, 120)
    assert len(intentos) == 3 and reloj.t == pytest.approx(0.2)
    op.drenar(plan, 120)
    assert reloj.t == pytest.approx(30.2)


def test_plazo_mata_grupo_propio_incluido_hijo(almacen, tmp_path, monkeypatch):
    binario = tmp_path / "bin"
    binario.mkdir()
    centinela = tmp_path / "hijo-sobrevivio"
    hijo = "import time;from pathlib import Path;time.sleep(0.5);Path(" + repr(str(centinela)) + ").write_text('fallo')"
    programa = binario / "docker"
    programa.write_text("#!" + sys.executable + "\nimport subprocess,sys,time\n"
                        "subprocess.Popen([sys.executable,'-c'," + repr(hijo) + "])\ntime.sleep(10)\n")
    programa.chmod(0o700)
    monkeypatch.setenv("PATH", str(binario))
    with pytest.raises(Rechazo, match="docker_no_completo"):
        Docker(almacen, "a" * 32)._ejecutar(["version"], time.monotonic() + 0.2)
    time.sleep(0.6)
    assert not centinela.exists()


def test_configuracion_alterada_no_se_adopta(almacen, plan):
    op, cli = preparado(almacen, plan)
    (op.carpeta(plan) / "nginx.conf").write_text("return 200;\n")
    cli.ordenes.clear()
    with pytest.raises(Rechazo, match="configuracion_alterada"):
        op.publicar(plan, time.monotonic() + 30)
    assert not any(o[0] == "compose" for o in cli.ordenes)


def test_release_con_enlace_no_se_sigue(almacen, plan, tmp_path):
    with almacen.exclusivo():
        e = almacen.inicializar()
    ajena = tmp_path / "ajena"
    ajena.mkdir()
    (almacen.ruta / ("r-" + plan.id)).symlink_to(ajena, target_is_directory=True)
    op = Docker(almacen, e["propietario"], ejecutar=lambda *_: pytest.fail("Docker no procede"))
    with pytest.raises(OSError):
        op.materializar(plan)
    assert list(ajena.iterdir()) == []


def test_verifica_firma_e104_antes_de_docker(almacen, plan, tmp_path):
    from tests.unit.generaciones.paquete_sintetico import construir
    raiz = tmp_path / "publicacion"
    carpeta, _, publica = construir(raiz)
    # Forma publicada: base/ ya reside en PostgreSQL, fuera de los archivos montados.
    import shutil
    shutil.rmtree(carpeta / "base")
    m = json.loads((carpeta / "manifiesto.json").read_bytes())
    v = plan.objeto()
    v.update(generacion=m["id"], directorio_generacion=str(carpeta), clave_publica=str(publica),
             huella_app=m["codigo"]["huella_app"],
             manifiesto_sha256=hashlib.sha256((carpeta / "manifiesto.json").read_bytes()).hexdigest())
    p = Plan.de(v)
    for nombre in ("secretos", "pki_proxy", "pki_sonda"):
        Path(getattr(p, nombre)).mkdir()
    for nombre in ("api_database_url", "api_claves", "pasarela_ingreso", "pasarela_clave_api", "proxy_ingreso.conf"):
        (Path(p.secretos) / nombre).write_bytes(b"dato sintetico\n")
    for nombre in ("servidor.crt", "servidor.key", "ca-consulta.crt", "crl.pem"):
        (Path(p.pki_proxy) / nombre).write_bytes(b"sintetico\n")
    for nombre in ("ca-servidor.crt", "cliente.crt", "cliente.key"):
        (Path(p.pki_sonda) / nombre).write_bytes(b"sintetico\n")
    with almacen.exclusivo():
        e = almacen.inicializar()
    cli = CLI(p, e["propietario"], str(almacen.ruta / ("r-" + p.id)))
    op = Docker(almacen, e["propietario"], ejecutar=cli)
    op.preparar(p, time.monotonic() + 30)
    assert any(o[:2] == ["network", "inspect"] for o in cli.ordenes)
    cli.ordenes.clear()
    (carpeta / "coherencia.json").write_bytes(b"alterado\n")
    with pytest.raises(ValueError):
        op.preparar(p, time.monotonic() + 30)
    assert cli.ordenes == []
