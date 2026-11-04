"""Fase 10 (E10.2, v4, F1023-WIN-02/03/04/05): COMPORTAMIENTO de la finalizacion del ensayo focal de Brave.

Ejecuta PowerShell de verdad (Windows PowerShell 5.1 y/o PowerShell 7, los que haya):
- el NUCLEO real (`ensayo_brave_mtls_e102_nucleo.ps1`) con una plataforma sustituta en memoria
  (`ensayo_brave_e102/sustitutos_nucleo.ps1`): coleccion de procesos vacia, uno o varios propios con uno ajeno,
  consulta de procesos que falla, fallo de arranque, sin interaccion, excepcion en cada fase de limpieza, clave
  privada huerfana, identificador de clave ausente, resumen no escribible en uno o en ambos destinos (el JSON
  de consola y el codigo coinciden) y un registro diagnostico manipulado que nunca se consume;
- el GUION PRINCIPAL completo (`ensayo_brave_e102/guion_completo.ps1`) con los cmdlets de Windows sustituidos,
  incluida la retirada de `-Recuperar` (v4).
  Controles negativos: con `E102_GUION_ENSAYO` en el guion v2 fallan las del guion completo (WIN-02); con el
  guion/nucleo v3 fallan la de `-Recuperar` (WIN-04) y la de ambos destinos (WIN-05).

Acredita la logica de finalizacion en la plataforma donde corre; NO el proveedor de certificados de Windows,
CNG, Brave ni el ensayo nativo (pendiente). Sin PowerShell disponible se omite, salvo en CI (`CI`), donde falla.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
WINDOWS = RAIZ / "despliegue" / "consulta-privada" / "windows"
GUION = Path(os.environ.get("E102_GUION_ENSAYO") or WINDOWS / "ensayo_brave_mtls_e102.ps1")
NUCLEO = Path(os.environ.get("E102_NUCLEO_ENSAYO") or GUION.parent / "ensayo_brave_mtls_e102_nucleo.ps1")
ARNES = Path(__file__).resolve().parent / "ensayo_brave_e102"
ID = "e102-mtls-0123456789ab"


def _interpretes() -> list[str]:
    indicados = [p for p in os.environ.get("E102_POWERSHELL", "").split(os.pathsep) if p]
    if indicados:
        return indicados
    candidatos = ["powershell.exe", "pwsh"] if sys.platform == "win32" else ["pwsh"]
    return [c for c in (shutil.which(n) for n in candidatos) if c]


INTERPRETES = _interpretes()
if not INTERPRETES:
    if os.environ.get("CI"):
        raise RuntimeError("PowerShell no disponible en CI: las pruebas de comportamiento del ensayo son obligatorias")
    pytestmark = pytest.mark.skip(reason="PowerShell no disponible (defina E102_POWERSHELL)")


@pytest.fixture(params=INTERPRETES or ["sin-powershell"], ids=lambda p: Path(p).name)
def ps(request):
    return request.param


def _ejecutar(ps: str, archivo: Path, *argumentos: str, timeout: int = 180) -> subprocess.CompletedProcess:
    orden = [ps, "-NoProfile", "-NonInteractive"]
    if sys.platform == "win32":
        orden += ["-ExecutionPolicy", "Bypass"]
    entorno = {**os.environ, "POWERSHELL_TELEMETRY_OPTOUT": "1"}
    return subprocess.run([*orden, "-File", str(archivo), *argumentos], capture_output=True, text=True,
                          timeout=timeout, env=entorno)


def _nucleo(ps: str, tmp_path: Path, escenario: str) -> dict:
    informe = tmp_path / "informe.json"
    r = _ejecutar(ps, ARNES / "sustitutos_nucleo.ps1", "-Nucleo", str(NUCLEO), "-Escenario", escenario,
                  "-Trabajo", str(tmp_path), "-Informe", str(informe))
    assert informe.exists(), f"sin informe del arnes (codigo {r.returncode}):\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
    datos = json.loads(informe.read_text(encoding="utf-8-sig"))
    assert datos["excepcion_escapada"] is None, datos["excepcion_escapada"]
    emitido = datos["resumen"] if datos["resumen"] is not None else datos["resumen_consola"]
    assert emitido is not None, "el resumen no se escribio ni se emitio en la consola"
    assert emitido["codigo"] == datos["codigo"], "el resumen emitido y el codigo de salida difieren"
    if datos["resumen"] is not None:
        assert datos["resumen"]["resumen_guardado"] is True and datos["resumen_consola"] is None
    return datos


def _hubo(llamadas: list, prefijo: str) -> bool:
    return any(x == prefijo or x.startswith(prefijo + ":") for x in llamadas)


def _pasos(datos: dict) -> dict:
    return {p["paso"]: p["ok"] for p in datos["resumen"]["pasos"]}


def _limpieza_total(datos: dict, *, almacen: str = "almacen") -> None:
    a = datos[almacen]
    assert (a["personal"], a["raiz"], a["claves"], a["procesos_propios"]) == (0, 0, 0, 0), a
    assert a["clave_ajena"] is True, "se borro la clave ajena sintetica"


# ---------------------------------------------------------------- caminos del ensayo

def test_exito_coleccion_vacia_limpieza_completa_y_claves_eliminadas(ps, tmp_path):
    d = _nucleo(ps, tmp_path, "exito")
    assert d["codigo"] == 0 and d["resumen"]["limpieza_completa"] is True and d["resumen"]["residuos"] == []
    _limpieza_total(d)
    assert not d["diagnostico_existe"] and d["resumen"]["diagnostico"] is None and not d["temporal_existe"]
    for rol in ("ca", "cliente", "servidor"):
        assert _hubo(d["llamadas"], f"borrar:{rol}")
    assert all(p["clave"] for p in d["resumen"]["propios"]) and len(d["resumen"]["propios"]) == 3


@pytest.mark.parametrize("n", [1, 3])
def test_cierra_solo_los_procesos_propios(ps, tmp_path, n):
    d = _nucleo(ps, tmp_path, f"procesos={n}+proceso_ajeno")
    assert d["codigo"] == 0
    detenidos = [x for x in d["llamadas"] if x.startswith("detener:")]
    assert detenidos == [f"detener:{1001 + i}" for i in range(n)]  # nunca el proceso ajeno (pid 1)
    assert d["almacen"]["procesos_propios"] == 0 and d["almacen"]["procesos_ajenos"] == 1


def test_consulta_de_procesos_fallida_no_es_cero_y_no_salta_limpiezas(ps, tmp_path):
    d = _nucleo(ps, tmp_path, "consulta_falla")
    assert d["codigo"] == 4 and d["resumen"]["limpieza_completa"] is False
    assert any("consulta fallida" in r for r in d["resumen"]["residuos"])
    _limpieza_total(d)  # las limpiezas siguientes se hicieron igualmente
    assert d["diagnostico_existe"] and d["resumen"]["diagnostico"]


def test_fallo_de_arranque_codigo_3_con_limpieza(ps, tmp_path):
    d = _nucleo(ps, tmp_path, "arranque_falla")
    assert d["codigo"] == 3 and d["resumen"]["limpieza_completa"] is True
    _limpieza_total(d)
    assert "abrir_brave" not in d["llamadas"]


def test_sin_interaccion_codigo_2_con_limpieza(ps, tmp_path):
    d = _nucleo(ps, tmp_path, "sin_interaccion")
    assert d["codigo"] == 2 and d["resumen"]["limpieza_completa"] is True
    _limpieza_total(d)


def test_fallo_al_crear_un_certificado_limpia_lo_ya_creado(ps, tmp_path):
    d = _nucleo(ps, tmp_path, "fallo=crear_cliente")
    assert d["codigo"] == 1 and d["resumen"]["limpieza_completa"] is True
    assert [p["rol"] for p in d["resumen"]["propios"]] == ["ca"]
    assert _hubo(d["llamadas"], "borrar:ca") and not _hubo(d["llamadas"], "borrar:cliente")
    _limpieza_total(d)


# ---------------------------------------------------------------- excepcion en cada fase de limpieza

POSTERIORES = ["consultar_procesos", "borrar:ca", "borrar:cliente", "borrar:servidor", "borrar_carpeta"]


@pytest.mark.parametrize("escenario, paso", [
    ("fallo=servidor+sin_interaccion", "limpieza: servidor local detenido"),
    ("fallo=detener+procesos=2", "limpieza: procesos de Brave del perfil temporal"),
    ("fallo=raiz", "limpieza: CA retirada de la raiz del usuario"),
    ("fallo=borrar_ca", "limpieza: certificado y clave privada de ca"),
    ("fallo=borrar_cliente", "limpieza: certificado y clave privada de cliente"),
    ("fallo=borrar_servidor", "limpieza: certificado y clave privada de servidor"),
    ("fallo=carpeta", "limpieza: carpeta temporal y perfil de Brave"),
    ("fallo=verificacion", "verificacion final de la limpieza"),
])
def test_excepcion_en_una_fase_no_pierde_resumen_ni_las_demas_limpiezas(ps, tmp_path, escenario, paso):
    d = _nucleo(ps, tmp_path, escenario)
    assert d["codigo"] == 4 and d["resumen"]["limpieza_completa"] is False
    fallidos = [p for p, ok in _pasos(d).items() if not ok and p.startswith(paso)]
    assert fallidos, f"el paso {paso!r} no quedo anotado como fallido"
    for llamada in POSTERIORES:
        assert _hubo(d["llamadas"], llamada), f"se salto {llamada} tras fallar {paso}"
    assert d["resumen"]["errores"] or d["resumen"]["residuos"]
    assert d["diagnostico_existe"] and d["resumen"]["diagnostico"]


# ---------------------------------------------------------------- claves privadas (WIN-03)

def test_clave_privada_huerfana_se_detecta_como_residuo(ps, tmp_path):
    """Como en v2 (Remove-Item sin -DeleteKey): el certificado desaparece y la clave queda."""
    d = _nucleo(ps, tmp_path, "clave_huerfana")
    assert d["codigo"] == 4
    claves = [r for r in d["resumen"]["residuos"] if "clave privada" in r]
    assert len(claves) == 3 and d["almacen"]["personal"] == 0 and d["almacen"]["claves"] == 3


def test_clave_sin_identificador_no_se_da_por_eliminada(ps, tmp_path):
    d = _nucleo(ps, tmp_path, "sin_nombre_clave")
    assert d["codigo"] == 4
    assert any(r.startswith("cliente: clave privada no verificado") for r in d["resumen"]["residuos"])


def test_registro_diagnostico_conserva_identificadores_y_residuos(ps, tmp_path):
    d = _nucleo(ps, tmp_path, "fallo=servidor+sin_interaccion")
    assert d["codigo"] == 4
    diag = d["diagnostico"]
    assert diag["uso"].startswith("solo diagnostico") and "no es una autorizacion" in diag["uso"]
    assert diag["servidor"] == "en ejecucion" and any("servidor local" in r for r in diag["residuos"])
    assert [p["rol"] for p in diag["propios"]] == ["ca", "cliente", "servidor"]


def test_registro_diagnostico_manipulado_no_se_consume_como_autorizacion(ps, tmp_path):
    """WIN-04: el registro apunta ahora a la clave ajena y a otra huella; una ejecucion posterior no lo lee."""
    d = _nucleo(ps, tmp_path, "fallo=borrar_cliente+diagnostico_manipulado")
    assert d["codigo"] == 4 and d["almacen"]["personal"] == 1 and d["almacen"]["claves"] == 1
    s = d["segunda"]
    assert s["codigo"] == 0 and s["excepcion_escapada"] is None
    assert s["almacen"]["clave_ajena"] is True                      # la clave ajena sigue intacta
    assert (s["almacen"]["personal"], s["almacen"]["claves"]) == (1, 1)  # el residuo previo NO se toca
    propios = {(p["huella"], p["clave"]) for p in s["resumen"]["propios"]}
    borrados = [x.split(":")[1:] for x in s["llamadas"] if x.startswith("borrar:")]  # rol, huella, clave
    assert len(borrados) == 3 and all((h, k) in propios for _rol, h, k in borrados)  # solo lo de su memoria
    manipulado = {(p["huella"], p["clave"]) for p in d["diagnostico_manipulado"]["propios"]}
    assert not (manipulado & {(h, k) for _rol, h, k in borrados})


def test_resumen_garantizado_aunque_la_salida_no_sea_escribible(ps, tmp_path):
    d = _nucleo(ps, tmp_path, "salida_invalida")
    assert d["resumen_en"].endswith("ensayo-brave-mtls-e102-resumen-0123456789ab.json")
    assert d["codigo"] == 0 and d["resumen"]["limpieza_completa"] is True and d["resumen"]["codigo"] == 0


def test_ambos_destinos_fallidos_el_json_de_consola_lleva_el_codigo_final(ps, tmp_path):
    """WIN-05: sin ningun archivo, el codigo 6 se decide ANTES de emitir el JSON, que coincide con el proceso."""
    d = _nucleo(ps, tmp_path, "salidas_invalidas")
    assert d["resumen"] is None and d["codigo"] == 6
    c = d["resumen_consola"]
    assert c is not None and c["codigo"] == 6 and c["resumen_guardado"] is False and c["codigo_ensayo"] == 0
    assert c["limpieza_completa"] is True
    assert d["ultima_linea_consola"].endswith("codigo 6")


# ---------------------------------------------------------------- guion principal completo

@pytest.mark.parametrize("escenario, codigo, limpia", [("sin_brave", 1, True), ("consulta_falla", 4, False)])
def test_guion_completo_escribe_resumen_y_codigo(ps, tmp_path, escenario, codigo, limpia):
    informe = tmp_path / "informe.json"
    r = _ejecutar(ps, ARNES / "guion_completo.ps1", "-Guion", str(GUION), "-Escenario", escenario,
                  "-Trabajo", str(tmp_path), "-Informe", str(informe))
    assert informe.exists(), r.stdout[-2000:] + r.stderr[-2000:]
    d = json.loads(informe.read_text(encoding="utf-8-sig"))
    assert d["excepcion_escapada"] is None, d["excepcion_escapada"]
    assert d["resumen_existe"], "el guion termino sin escribir el resumen"
    assert d["codigo"] == codigo and d["resumen"]["codigo"] == codigo
    assert d["resumen"]["limpieza_completa"] is limpia


def test_recuperar_retirado_se_rechaza_sin_tocar_nada(ps, tmp_path):
    """WIN-04: un registro con formato v3 bien formado ya no puede usarse para limpiar (v3 lo aceptaba)."""
    informe = tmp_path / "informe.json"
    r = _ejecutar(ps, ARNES / "guion_completo.ps1", "-Guion", str(GUION), "-Escenario", "recuperar",
                  "-Trabajo", str(tmp_path), "-Informe", str(informe))
    assert informe.exists(), r.stdout[-2000:] + r.stderr[-2000:]
    d = json.loads(informe.read_text(encoding="utf-8-sig"))
    assert d["excepcion_escapada"] and "ParameterBindingException" in d["excepcion_escapada"]
    assert d["llamadas"] == [] and d["archivos_nuevos"] == [] and d["registro_existe_tras"] is True
    assert not d["resumen_existe"]


def test_los_guiones_se_analizan_sin_errores(ps, tmp_path):
    archivos = [GUION, NUCLEO, ARNES / "sustitutos_nucleo.ps1", ARNES / "guion_completo.ps1"]
    lista = ",".join("'" + str(a).replace("'", "''") + "'" for a in archivos)
    orden = ("$e = 0; foreach ($a in @(" + lista + ")) { $t = $null; $x = $null; "
             "[void][System.Management.Automation.Language.Parser]::ParseFile($a, [ref]$t, [ref]$x); "
             "$e += @($x).Count; foreach ($i in @($x)) { Write-Output ($a + ': ' + $i.Message) } }; exit $e")
    r = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-Command", orden], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------- contrato estatico complementario

def _texto(ruta: Path) -> str:
    return ruta.read_text(encoding="ascii")  # ASCII: Windows PowerShell 5.1 sin BOM


def test_ascii_modo_estricto_y_sin_desactivarlo():
    for ruta in (GUION, NUCLEO):
        texto = _texto(ruta)
        assert "Set-StrictMode -Off" not in texto
    assert "Set-StrictMode -Version 2.0" in _texto(GUION)


def test_borrado_de_claves_explicito_y_sin_barridos():
    nucleo = _texto(NUCLEO)
    assert "Remove-Item -LiteralPath $ruta -DeleteKey" in nucleo
    assert "CngKey]::Open([string]$r.clave" in nucleo and "$k.Delete()" in nucleo
    assert not re.search(r"Get-ChildItem\s+[^\n]*Cert:", nucleo)  # nunca se recorren almacenes
    assert not re.search(r"Stop-Process\s+-Name", nucleo + _texto(GUION))
    assert "FriendlyName -ne $r.marca" in nucleo


def test_ningun_json_externo_se_lee_para_borrar():
    guion, nucleo = _texto(GUION), _texto(NUCLEO)
    assert "Recuperar" not in guion and "Recuperacion" not in nucleo
    lecturas = [l for l in nucleo.splitlines() if "ConvertFrom-Json" in l]
    assert len(lecturas) == 1 and "$Estado.Resultado" in lecturas[0]  # solo el resultado del servidor local
    assert "Get-Content" not in "".join(l for l in nucleo.splitlines() if "Diagnostico" in l)


def test_confirmacion_previa_y_sin_espera_humana_tras_instalar():
    guion = _texto(GUION)
    assert guion.index("Read-Host") < guion.index("Invoke-EnsayoCompletoE102 -Plataforma")
    assert "Read-Host" not in _texto(NUCLEO)
    assert "AGREGA TEMPORALMENTE" in guion and "AddHours(2)" in _texto(NUCLEO)
