from __future__ import annotations

import os
import stat

import pytest

from despliegue.operacion_consulta.estado import Almacen
from despliegue.operacion_consulta.modelo import Plan, Rechazo, canonico, json_estricto


@pytest.mark.parametrize("campo,valor", [
    ("modo", "produccion"), ("formato", "otro/1"), ("generacion", "../ajeno"),
    ("manifiesto_sha256", "A" * 64), ("imagen_api", "prueba/api:latest"),
    ("imagen_pasarela", "prueba/img@sha256:" + "0" * 63), ("imagen_proxy", "x\norden"),
    ("host", "x;return 200;"), ("host", "consulta.$variable"), ("puerto", True), ("puerto", 80),
    ("drenaje_s", 0), ("presupuesto_corte_s", 20), ("red_interna", "0.0.0.0/24"),
    ("red_servicio", "172.28.2.0/24"), ("red_datos", "postgres-operativo"),
    ("ip_datos_api", "8.8.8.8"), ("ip_datos_api", "172.28.2.20"),
    ("secretos", "/tmp/../privado"), ("secretos", "/tmp/$HOME"), ("clave_publica", "relativa"),
    ("pki_sonda", "/tmp/x\nreturn"), ("directorio_generacion", "/tmp/otra")])
def test_plan_rechaza_entradas_antes_de_efectos(plan, campo, valor):
    v = plan.objeto()
    v[campo] = valor
    with pytest.raises(Rechazo):
        Plan.de(v)


def test_plan_cerrado_y_huella_de_toda_la_configuracion(plan):
    assert Plan.de(json_estricto(canonico(plan.objeto()))) == plan
    v = plan.objeto()
    v["orden_shell"] = "no"
    with pytest.raises(Rechazo):
        Plan.de(v)
    v = plan.objeto()
    v["imagen_api"] = "otra/api@sha256:" + "0" * 64
    assert Plan.de(v).id != plan.id


@pytest.mark.parametrize("datos", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'\xff', b'{'])
def test_json_no_admite_ambiguedad(datos):
    with pytest.raises(Rechazo):
        json_estricto(datos)


def test_control_privado_archivos_y_bloqueo(almacen):
    assert stat.S_IMODE(os.fstat(almacen.fd).st_mode) == 0o700
    with almacen.exclusivo():
        almacen.inicializar()
        almacen.escribir("prueba.json", {"x": 1})
        with Almacen(almacen.ruta) as otro:
            with pytest.raises(Rechazo, match="otra_operacion"):
                with otro.exclusivo():
                    pytest.fail("no adquirible")
    assert stat.S_IMODE((almacen.ruta / "prueba.json").stat().st_mode) == 0o600
    assert almacen.leer("prueba.json") == {"x": 1}
    with pytest.raises(Rechazo, match="sin_bloqueo"):
        almacen.escribir("prueba.json", {})


def test_no_corrige_permisos_de_una_carpeta_ajena(tmp_path):
    ruta = tmp_path / "ajena"
    ruta.mkdir(mode=0o755)
    with pytest.raises(Rechazo, match="no_es_privado"):
        Almacen(ruta, crear=True)
    assert stat.S_IMODE(ruta.stat().st_mode) == 0o755 and not list(ruta.iterdir())


def test_rechaza_ancestro_enlace_sin_tocarlo(tmp_path):
    real, enlace = tmp_path / "real", tmp_path / "enlace"
    real.mkdir()
    enlace.symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError):
        Almacen(enlace / "control", crear=True)
    assert not list(real.iterdir())


@pytest.mark.parametrize("tipo", ["simbolico", "duro", "fifo"])
def test_no_lee_ni_sustituye_archivos_ajenos(almacen, tmp_path, tipo):
    ajeno = tmp_path / "centinela"
    ajeno.write_bytes(b"conservar")
    os.chmod(ajeno, 0o600)
    enlace = almacen.ruta / "prueba.json"
    if tipo == "simbolico":
        enlace.symlink_to(ajeno)
    elif tipo == "duro":
        os.link(ajeno, enlace)
    else:
        os.mkfifo(enlace, 0o600)
    with pytest.raises((OSError, Rechazo)):
        almacen.leer("prueba.json")
    with almacen.exclusivo():
        with pytest.raises((OSError, Rechazo)):
            almacen.escribir("prueba.json", {})
    assert ajeno.read_bytes() == b"conservar"


def test_plan_alterado_no_se_usa_para_recuperacion(almacen, plan):
    with almacen.exclusivo():
        e = almacen.inicializar()
        almacen.guardar_plan(plan)
        e["activa"] = plan.id
        e["acceso"] = "abierto"
        almacen.escribir("estado.json", e)
        d = plan.objeto()
        d["secretos"] = "/tmp/ajeno"
        almacen.escribir("p-" + plan.id + ".json", d)
    with almacen.exclusivo():
        with pytest.raises(Rechazo, match="plan_alterado"):
            almacen.inicializar()


def test_estado_ambiguo_no_se_adopta(almacen):
    with almacen.exclusivo():
        e = almacen.inicializar()
        e["orden"] = "borrar"
        almacen.escribir("estado.json", e)
        with pytest.raises(Rechazo, match="estado_no_valido"):
            almacen.inicializar()


def test_null_no_se_confunde_con_control_ausente(almacen):
    with almacen.exclusivo():
        almacen.escribir("estado.json", None)
        with pytest.raises(Rechazo, match="estado_no_valido"):
            almacen.inicializar()
    assert (almacen.ruta / "estado.json").read_bytes() == b"null\n"


def test_copia_del_control_no_adopta_recursos_de_otra_raiz(almacen, tmp_path):
    import shutil
    with almacen.exclusivo():
        almacen.inicializar()
    copia = tmp_path / "control-copiado"
    shutil.copytree(almacen.ruta, copia)
    with Almacen(copia) as a:
        with a.exclusivo():
            with pytest.raises(Rechazo, match="otra_raiz"):
                a.inicializar()
