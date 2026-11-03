"""PR #109 (CI109-02): comportamiento del ARNES de la demostracion E10.2 (`despliegue/consulta-privada/
demostracion.py`) con las ordenes Docker SUSTITUIDAS: no se ejecuta Docker, red, PostgreSQL ni navegador, ni se
toca la operacion de Fase 6. Cubre salida relativa y absoluta (con espacios), estados parciales (antes de
imagenes, de publicacion o durante ella), errores de limpieza, conservacion del informe y del motivo original,
saneado y recursos ajenos. La demostracion real completa se ejecuta aparte con Docker aislado."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ARCHIVO = Path(__file__).resolve().parents[3] / "despliegue" / "consulta-privada" / "demostracion.py"
FASES = ("comprobar_entorno", "preparar_pki", "preparar_secretos", "construir_imagenes", "preparar_publicacion",
         "levantar")
COMPROBACIONES = ("tls_e_identidad", "identidad_falsa", "cuotas", "acceso_directo", "matriz", "solo_lectura",
                  "recursos", "claves", "revocacion", "navegador", "api_alterada", "almacen_vaciado_o_mal_apuntado",
                  "ausencia_de_almacen", "integridad_y_registros")
AJENO = "volumen-ajeno-de-otro-proyecto"


class Detener(Exception):
    pass


def _modulo(nombre: str):
    spec = importlib.util.spec_from_file_location(f"demostracion_e102_{nombre}", ARCHIVO)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulo.puerto_libre = lambda _p: True
    return modulo


class DockerSustituto:
    """Simula las ordenes Docker y anota cada una. `volumenes` contiene los existentes (propios y ajenos)."""

    def __init__(self, modulo, demo_ref, *, fallo_en=None, ignora_filtros=False):
        self.m, self.demo_ref, self.fallo_en, self.ignora_filtros = modulo, demo_ref, fallo_en, ignora_filtros
        self.llamadas: list[list[str]] = []
        self.entornos: list[dict] = []
        self.volumenes = {AJENO}
        self.etiquetados: set[str] = set()  # creados con la etiqueta del proyecto (`volume create --label`)

    def __call__(self, args, **kw):
        partes = [str(a) for a in args]
        self.llamadas.append(partes)
        if kw.get("env") is not None:
            self.entornos.append(kw["env"])
        d = self.demo_ref()
        for prefijo in self.fallo_en or ():
            if partes[:len(prefijo)] == list(prefijo):
                raise RuntimeError("FALLO_LIMPIEZA_" + "_".join(prefijo[1:]).upper())
        salida = b""
        if partes[:3] == ["docker", "volume", "create"]:
            self.volumenes.add(partes[-1])
            if "--label" in partes:
                self.etiquetados.add(partes[-1])
        elif partes[:3] == ["docker", "volume", "ls"]:
            filtro = next((partes[i + 1] for i, p in enumerate(partes) if p == "--filter"), "")
            if self.ignora_filtros or not filtro:
                nombres = sorted(self.volumenes)
            elif filtro.startswith("label="):
                nombres = sorted(v for v in self.volumenes if v in self.etiquetados)
            else:
                nombres = sorted(v for v in self.volumenes if filtro.split("=", 1)[1] in v)
            salida = ("\n".join(nombres) + "\n").encode()
        elif partes[:3] == ["docker", "volume", "rm"]:
            for v in partes[3:]:
                self.volumenes.discard(v)
        codigo = 1 if partes[:2] == ["docker", "logs"] else 0
        return subprocess.CompletedProcess(partes, codigo, salida, b"")


def _demo(tmp_path, monkeypatch, nombre, *, salida="salida demo", **sustituto):
    m = _modulo(nombre)
    monkeypatch.chdir(tmp_path)
    ref = {}
    docker = DockerSustituto(m, lambda: ref["d"], **sustituto)
    m.ejecutar = docker
    d = m.Demostracion(Path(salida), "python-sustituto", None, False)
    ref["d"] = d
    return m, d, docker


def _simular(d, *, falla=None, mensaje="MOTIVO_ORIGINAL", ok=True):
    """Fases y comprobaciones sustituidas; `falla` es la fase que lanza. Crea el volumen propio al publicar."""
    def fase(nombre):
        def f():
            if nombre == "construir_imagenes":
                d.imagenes = {"api": {"etiqueta": "api-sustituta"}, "pasarela": {"etiqueta": "pasarela-sustituta"}}
            if nombre == "preparar_publicacion":
                d.m_ejecutar(["docker", "volume", "create", "--label", f"e102.demostracion={d.proyecto}", d.volumen])
            if nombre == falla:
                raise RuntimeError(mensaje)
            if nombre == "preparar_publicacion":
                d.publicacion = d.trabajo / "preparacion" / "publicacion"
        return f
    for n in FASES:
        setattr(d, n, fase(n))
    for n in COMPROBACIONES:
        setattr(d, n, (lambda n=n: d.anotar(n, n, ok, 0.0)))


def _informe(d) -> dict:
    return json.loads((d.salida / "demostracion.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------- rutas

@pytest.mark.parametrize("salida", ["salida relativa", "anidada/con espacios/demo", None])
def test_salida_relativa_o_absoluta_da_origenes_absolutos(tmp_path, monkeypatch, salida):
    salida = salida or str(tmp_path / "ruta absoluta con espacios")
    m, d, docker = _demo(tmp_path, monkeypatch, "rutas", salida=salida)
    assert d.salida.is_absolute() and d.salida == (tmp_path / salida if not Path(salida).is_absolute() else Path(salida))
    for ruta in (d.trabajo, d.secretos, d.pki, d.pki_proxy, d.generado, d.registros):
        assert ruta.is_absolute() and str(ruta).startswith(str(d.salida))

    def corta(args, **kw):
        partes = [str(a) for a in args]
        if partes[:2] == ["docker", "run"]:
            raise Detener(partes)
        return docker(args, **kw)
    m.ejecutar = corta
    with pytest.raises(Detener) as orden:
        d.preparar_publicacion()
    partes = orden.value.args[0]
    origenes = [partes[i + 1].rsplit(":", 2)[0] for i, p in enumerate(partes) if p == "-v"]
    binds = [o for o in origenes if "/" in o]
    assert binds and all(Path(o).is_absolute() for o in binds), binds
    assert d.volumen in origenes  # el volumen nombrado sigue siendo un nombre


def test_entorno_compose_valido_en_cualquier_estado_y_con_rutas_absolutas(tmp_path, monkeypatch):
    _m, d, _docker = _demo(tmp_path, monkeypatch, "entorno")
    for estado in ("inicial", "imagenes", "publicacion"):
        if estado == "imagenes":
            d.imagenes = {"api": {"etiqueta": "a"}, "pasarela": {"etiqueta": "p"}}
        if estado == "publicacion":
            d.publicacion = d.trabajo / "preparacion" / "publicacion"
        env = d.entorno_compose()
        for clave in ("E102_SECRETOS", "E102_PUBLICACION", "E102_PKI_PROXY", "E102_PROXY_GENERADO"):
            assert Path(env[clave]).is_absolute(), (estado, clave)
        assert env["E102_IMAGEN_API"] and env["E102_IMAGEN_PASARELA"]


# ------------------------------------------------------------------------- fallos y limpieza

@pytest.mark.parametrize("fase", ["comprobar_entorno", "preparar_secretos", "construir_imagenes",
                                  "preparar_publicacion", "levantar"])
def test_fallo_en_una_fase_conserva_motivo_limpia_y_escribe_informe(tmp_path, monkeypatch, fase):
    m, d, docker = _demo(tmp_path, monkeypatch, f"fase_{fase}")
    d.m_ejecutar = docker
    _simular(d, falla=fase, mensaje=f"MOTIVO_{fase.upper()}")
    codigo = d.ejecutar()
    assert codigo == 1
    inf = _informe(d)
    assert inf["todas_correctas"] is False
    assert inf["error_inicial"]["fase"] == fase and f"MOTIVO_{fase.upper()}" in inf["error_inicial"]["mensaje"]
    assert inf["errores_limpieza"] == []
    assert any(c[:3] == ["docker", "compose", "-p"] and "down" in c for c in docker.llamadas)  # compose down intentado
    assert AJENO in docker.volumenes and not any(v.startswith(d.proyecto) for v in docker.volumenes)
    assert next(r for r in inf["resultados"] if r["id"] == "Z01")["ok"] is True


def test_error_en_pasos_de_limpieza_no_impide_los_demas_ni_el_informe(tmp_path, monkeypatch):
    m, d, docker = _demo(tmp_path, monkeypatch, "limpieza", fallo_en=[("docker", "logs"), ("docker", "compose")])
    d.m_ejecutar = docker
    _simular(d, falla="preparar_publicacion")
    assert d.ejecutar() == 1
    inf = _informe(d)
    pasos = [e["paso"] for e in inf["errores_limpieza"]]
    assert pasos[:4] == [f"registro final de {s}" for s in ("proxy", "pasarela", "api", "postgres")]
    assert "compose down" in pasos
    assert any(c[:3] == ["docker", "volume", "rm"] for c in docker.llamadas)  # los siguientes pasos se intentaron
    assert not any(v.startswith(d.proyecto) for v in docker.volumenes) and AJENO in docker.volumenes
    assert "MOTIVO_ORIGINAL" in inf["error_inicial"]["mensaje"]  # el error de limpieza no sustituye al original
    z01 = next(r for r in inf["resultados"] if r["id"] == "Z01")
    assert z01["ok"] is False and inf["todas_correctas"] is False


def test_un_volumen_ajeno_sobrevive_aunque_el_filtro_no_se_aplique(tmp_path, monkeypatch):
    m, d, docker = _demo(tmp_path, monkeypatch, "ajeno", ignora_filtros=True)
    d.m_ejecutar = docker
    _simular(d, falla="levantar")
    d.ejecutar()
    assert AJENO in docker.volumenes
    assert not any(c[:3] == ["docker", "volume", "rm"] and AJENO in c for c in docker.llamadas)


def test_exito_solo_sin_fallos_residuos_ni_errores_de_limpieza(tmp_path, monkeypatch):
    m, d, docker = _demo(tmp_path, monkeypatch, "exito")
    d.m_ejecutar = docker
    _simular(d)
    assert d.ejecutar() == 0
    inf = _informe(d)
    assert inf["todas_correctas"] is True and inf["error_inicial"] is None and inf["errores_limpieza"] == []


def test_una_comprobacion_fallida_o_un_residuo_dan_fallo(tmp_path, monkeypatch):
    m, d, docker = _demo(tmp_path, monkeypatch, "residuo")
    d.m_ejecutar = docker
    _simular(d, ok=False)
    assert d.ejecutar() == 1 and _informe(d)["todas_correctas"] is False
    m2, d2, docker2 = _demo(tmp_path, monkeypatch, "residuo2", salida="otra")
    d2.m_ejecutar = docker2
    _simular(d2)
    docker2.volumenes.add(f"{d2.proyecto}-resto")  # un volumen propio que no lleva la etiqueta
    assert d2.ejecutar() == 1
    z01 = next(r for r in _informe(d2)["resultados"] if r["id"] == "Z01")
    assert z01["ok"] is False and z01["restos"]["volumenes"]


def test_informe_saneado_sin_secretos_ni_rutas_de_trabajo(tmp_path, monkeypatch):
    m, d, docker = _demo(tmp_path, monkeypatch, "saneado")
    d.m_ejecutar = docker
    secreto = "s3cr3t0-sintetico-0123456789abcdef"
    d.valores_secretos.append(secreto)
    _simular(d, falla="preparar_publicacion", mensaje=f"fallo con {secreto} en {d.secretos / 'pg_super'}")
    d.ejecutar()
    texto = (d.salida / "demostracion.json").read_text(encoding="utf-8")
    assert secreto not in texto and str(d.trabajo) not in texto and str(tmp_path) not in texto
    assert "[secreto]" in texto and "[trabajo]" in texto


def test_main_rechaza_una_salida_existente_sin_tocarla(tmp_path, monkeypatch, capsys):
    m = _modulo("existente")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ya-existe").mkdir()
    m.ejecutar = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe ejecutar Docker"))
    assert m.main(["--salida", "ya-existe", "--python-preparacion", "python"]) == 2
    assert list((tmp_path / "ya-existe").iterdir()) == []
