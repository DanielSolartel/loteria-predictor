"""Flujo de limpieza con PowerShell real y controlador simulado, sin Programador.

La copia de fixture sustituye exclusivamente la guarda de Windows y la raiz
creada para este ensayo. Nunca se ejecuta el testigo ni se consulta una tarea
real; no acredita Windows PowerShell 5.1 o el Programador nativo.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest

from tests.unit.test_fase6_tarea_windows import _ejecutar_powershell, _ps_literal

ENSAYO = Path(__file__).resolve().parents[2] / "tests/ensayar_tarea_fase6_windows.ps1"
GUARDA_WINDOWS = "if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Este ensayo requiere Windows nativo; el parser de Linux no lo acredita.' }"

CONTROL_SIMULADO = r'''
[CmdletBinding()]
param([string]$Worktree,[string]$PythonExe,[string]$Configuracion,[string]$Evidencia,
      [string]$PlanHorario,[string]$XmlAnterior,
      [switch]$Plan,[switch]$Instalar,[switch]$Activar,[switch]$Pausar,
      [switch]$Desinstalar,[switch]$Estado,[switch]$Migrar,[switch]$Revertir,[switch]$Reanudar)
$accion = if($Plan){'Plan'}elseif($Instalar){'Instalar'}elseif($Activar){'Activar'}elseif($Pausar){'Pausar'}elseif($Desinstalar){'Desinstalar'}else{'Estado'}
[void]$global:Controles.Add($accion)
[void][IO.Directory]::CreateDirectory($Evidencia)
$r=[ordered]@{estado='consultada';codigo=0;error=$null;tarea='LP6-solo-simulada';tarea_modificada=$false;habilitada=$false;estado_programador='Disabled'}
$rc=0
if($accion -eq 'Plan'){$r.estado='plan_no_instalado'}
elseif($accion -eq 'Instalar'){$r.estado='error';$r.error='ERROR_PRIMARIO_INSTALACION';$rc=31}
elseif($accion -eq 'Estado'){
    if($global:Escenario -eq 'ausente' -or $global:Retirada){$r.estado='no_instalada'}
    elseif($global:Escenario -eq 'permiso'){$r.estado='error';$r.error='ACCESO_DENEGADO_CONSULTA';$rc=41}
    elseif($global:Escenario -eq 'ajena'){$r.estado='error';$r.error='TAREA_AJENA_NO_MODIFICAR';$rc=42}
    elseif($global:Escenario -eq 'desconocida'){$r.estado='sin_confirmacion'}
    elseif($global:Escenario -eq 'viva'){$r.estado_programador='Running';$r.habilitada=$true}
    else{$r.estado_programador='Ready';$r.habilitada=$true}
}
elseif($accion -eq 'Pausar'){
    if($global:Escenario -eq 'ausente'){$r.estado='error';$r.error='LA_TAREA_NO_EXISTE';$rc=43}
    elseif($global:Escenario -eq 'permiso' -or $global:Escenario -eq 'pausa_denegada'){$r.estado='error';$r.error='ACCESO_DENEGADO_PAUSA';$rc=44}
    elseif($global:Escenario -eq 'ajena'){$r.estado='error';$r.error='TAREA_AJENA_NO_MODIFICAR';$rc=42}
    else{$r.estado='tarea_pausada';$r.habilitada=$false}
}
elseif($accion -eq 'Desinstalar'){
    if($global:Escenario -eq 'viva'){$r.estado='error';$r.error='CICLO_VIVO_NO_RETIRAR';$rc=45}
    else{$r.estado='desinstalada';if($global:Escenario -ne 'retirada_incierta'){$global:Retirada=$true}}
}
else {throw 'NO SE DEBE ACTIVAR EL ENSAYO TRAS FALLO DE INSTALACION'}
$r.codigo=$rc
[IO.File]::WriteAllText((Join-Path $Evidencia 'resultado.json'),(($r|ConvertTo-Json -Depth 8)+"`n"),(New-Object Text.UTF8Encoding($false,$true)))
exit $rc
'''


@pytest.fixture
def raiz_limpieza():
    # Directorio propio corto en TEMP normal; no modifica TEMP/TMP ni basetemp.
    with tempfile.TemporaryDirectory(prefix="f6l ") as carpeta:
        yield Path(carpeta)


def _ensayar_fallo_instalacion(raiz_limpieza, escenario):
    return _ensayar(raiz_limpieza, escenario)


def _ensayar(raiz_limpieza, escenario, control=CONTROL_SIMULADO, previo=""):
    """Ensayo con el controlador simulado `control`; `previo` añade sustitutos tras los predeterminados."""
    raiz = raiz_limpieza / "ensayo con espacios y ñ"
    raiz.mkdir()
    backend = raiz / "backend"
    (backend / "tests").mkdir(parents=True)
    (backend / "scripts/windows").mkdir(parents=True)
    temporales = raiz / "temporales solo fixture"
    temporales.mkdir()
    original = ENSAYO.read_text(encoding="utf-8")
    assert original.count(GUARDA_WINDOWS) == 1
    assert original.count("[IO.Path]::GetTempPath()") == 1
    copia = original.replace(GUARDA_WINDOWS, "# Fixture: plataforma sustituida; no es un ensayo nativo.")
    copia = copia.replace("[IO.Path]::GetTempPath()", _ps_literal(temporales))
    probe = backend / "tests/ensayar_tarea_fase6_windows.ps1"
    probe.write_text(copia, encoding="utf-8-sig")
    (backend / "scripts/windows/fase6_tarea.ps1").write_text(control, encoding="utf-8-sig")
    # El ensayo analiza tambien el controlador anterior archivado (version 1) que usa en la migracion.
    (backend / "tests/fixtures/fase6").mkdir(parents=True)
    (backend / "tests/fixtures/fase6/fase6_tarea_v1.ps1").write_text(control, encoding="utf-8-sig")
    plan = raiz / "plan de horario.json"
    plan.write_text('{"solo_fixture": true}\n', encoding="utf-8")
    python = raiz / "python ficticio.exe"
    python.write_bytes(b"NO_EJECUTAR")
    evidencia = raiz / "evidencia"
    traza = raiz / "controles.json"
    wrapper = raiz / "invocar aislado.ps1"
    wrapper.write_text(
        "$global:Controles=New-Object Collections.Generic.List[string]\n"
        "$global:Retirada=$false\n$global:Escenario=" + _ps_literal(escenario) + "\n"
        "function Start-ScheduledTask { throw 'NO_DISPARAR_TAREA_REAL' }\n"
        "function Get-ScheduledTask { throw 'NO_CONSULTAR_TAREA_REAL' }\n"
        "function Get-ScheduledTaskInfo { throw 'NO_CONSULTAR_TAREA_REAL' }\n"
        "function Export-ScheduledTask { throw 'NO_EXPORTAR_TAREA_REAL' }\n"
        + previo +
        "& " + _ps_literal(probe) + " -PythonExe " + _ps_literal(python)
        + " -Evidencia " + _ps_literal(evidencia) + " -PlanHorario " + _ps_literal(plan) + " -Ejecutar\n"
        "$rc=$LASTEXITCODE\n"
        "[IO.File]::WriteAllText(" + _ps_literal(traza)
        + ",(($global:Controles.ToArray()|ConvertTo-Json)+\"`n\"),(New-Object Text.UTF8Encoding($false,$true)))\n"
        "exit $rc\n",
        encoding="utf-8-sig",
    )
    p = _ejecutar_powershell({"raiz": raiz}, wrapper, nombre="limpieza-" + escenario, timeout=30)
    resultado = json.loads((evidencia / "resultado-tarea-nativa.json").read_text(encoding="utf-8"))
    controles = json.loads(traza.read_text(encoding="utf-8"))
    raiz_testigo = Path(resultado["raiz_sintetica"])
    carpeta_evidencia = Path(os.environ.get("FASE4_EVIDENCIA") or raiz)
    clave = hashlib.sha256((os.environ.get("PYTEST_CURRENT_TEST", "sin_pytest") + escenario).encode("utf-8")).hexdigest()[:16]
    registro = {"tipo": "ensayo_limpieza_controlador_simulado", "escenario": escenario,
                "caso": os.environ.get("PYTEST_CURRENT_TEST"), "resultado": resultado,
                "controles": controles, "raiz_conservada": raiz_testigo.exists(),
                "limite": "Copia con guarda OS/raiz de fixture; no Programador nativo"}
    (carpeta_evidencia / ("limp-" + clave + ".json")).write_text(
        json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    assert raiz_testigo.parent == temporales
    assert not (raiz_testigo / "marca-testigo.json").exists()
    return p, resultado, controles, raiz_testigo


def _assert_error_instalacion_conservado(p, resultado):
    assert p.returncode == resultado["codigo"] == 1
    assert resultado["estado"] == "error"
    assert "ERROR_PRIMARIO_INSTALACION" in resultado["error"]
    instalacion = next(paso for paso in resultado["pasos"] if paso["accion"] == "Instalar")
    assert instalacion["codigo"] == 31
    assert instalacion["resultado"]["error"] == "ERROR_PRIMARIO_INSTALACION"
    assert resultado["producto_ejecutado"] is resultado["datos_reales"] is False


def test_limpieza_ausencia_confirmada_no_intenta_pausar_y_conserva_fallo(raiz_limpieza):
    p, r, controles, raiz = _ensayar_fallo_instalacion(raiz_limpieza, "ausente")
    assert controles == ["Plan", "Instalar", "Estado"]
    assert r["estado_limpieza"] == "completa" and r["avisos_limpieza"] == []
    assert not raiz.exists()
    _assert_error_instalacion_conservado(p, r)


def test_limpieza_retirada_confirmada_no_convierte_instalacion_fallida_en_exito(raiz_limpieza):
    p, r, controles, raiz = _ensayar_fallo_instalacion(raiz_limpieza, "retirada_correcta")
    assert controles == ["Plan", "Instalar", "Estado", "Pausar", "Desinstalar", "Estado"]
    assert r["estado_limpieza"] == "completa" and r["avisos_limpieza"] == []
    assert not raiz.exists()
    _assert_error_instalacion_conservado(p, r)


@pytest.mark.parametrize(
    ("escenario", "controles_esperados", "aviso"),
    [
        ("permiso", ["Plan", "Instalar", "Estado"], "ACCESO_DENEGADO_CONSULTA"),
        ("ajena", ["Plan", "Instalar", "Estado"], "TAREA_AJENA_NO_MODIFICAR"),
        ("viva", ["Plan", "Instalar", "Estado"], "ciclo vivo"),
        ("desconocida", ["Plan", "Instalar", "Estado"], "no confirma"),
        ("pausa_denegada", ["Plan", "Instalar", "Estado", "Pausar"], "ACCESO_DENEGADO_PAUSA"),
        ("retirada_incierta", ["Plan", "Instalar", "Estado", "Pausar", "Desinstalar", "Estado"], "ausencia"),
    ],
)
def test_limpieza_sin_retirada_segura_conserva_raiz_y_error_original(raiz_limpieza, escenario, controles_esperados, aviso):
    p, r, controles, raiz = _ensayar_fallo_instalacion(raiz_limpieza, escenario)
    assert controles == controles_esperados
    assert r["estado_limpieza"] == "pendiente" and r["temporal_pendiente"] == str(raiz)
    assert any(aviso in a for a in r["avisos_limpieza"])
    assert raiz.is_dir() and (raiz / "config-testigo.json").is_file()
    _assert_error_instalacion_conservado(p, r)



# F92-NAT-01: tras instalar, el ensayo comprueba StartWhenAvailable en la exportación nativa. El
# Programador puede omitir el elemento (predeterminado documentado false); la comprobación debe leerlo
# de forma semántica y estricta, sin acceder a una propiedad XML inexistente ni reescribir el XML.
CONTROL_SWA = r"""
[CmdletBinding()]
param([string]$Worktree,[string]$PythonExe,[string]$Configuracion,[string]$Evidencia,
      [string]$PlanHorario,[string]$XmlAnterior,
      [switch]$Plan,[switch]$Instalar,[switch]$Activar,[switch]$Pausar,
      [switch]$Desinstalar,[switch]$Estado,[switch]$Migrar,[switch]$Revertir,[switch]$Reanudar)
$accion = if($Plan){'Plan'}elseif($Instalar){'Instalar'}elseif($Activar){'Activar'}elseif($Pausar){'Pausar'}elseif($Desinstalar){'Desinstalar'}else{'Estado'}
[void]$global:Controles.Add($accion)
[void][IO.Directory]::CreateDirectory($Evidencia)
$r=[ordered]@{estado='consultada';codigo=0;error=$null;tarea='LP6-solo-simulada';tarea_modificada=$false;habilitada=$false;estado_programador='Disabled';plan_horario=@{huella=('a'*64)}}
$rc=0
if($accion -eq 'Plan'){$r.estado='plan_no_instalado'}
elseif($accion -eq 'Instalar'){$r.estado='instalada_deshabilitada';$r.tarea_modificada=$true}
elseif($accion -eq 'Activar'){$r.estado='error';$r.error='ALTO_TRAS_COMPROBACION_SWA';$rc=51}
elseif($accion -eq 'Estado'){if($global:Retirada){$r.estado='no_instalada'}}
elseif($accion -eq 'Pausar'){$r.estado='tarea_pausada'}
elseif($accion -eq 'Desinstalar'){$r.estado='desinstalada';$global:Retirada=$true}
$r.codigo=$rc
[IO.File]::WriteAllText((Join-Path $Evidencia 'resultado.json'),(($r|ConvertTo-Json -Depth 8)+"`n"),(New-Object Text.UTF8Encoding($false,$true)))
exit $rc
"""


def _exportacion_swa(valores):
    """Exportación como la del Programador: sin el elemento si `valores` está vacío."""
    swa = "".join("<StartWhenAvailable>" + v + "</StartWhenAvailable>" for v in valores)
    return ('<?xml version="1.0" encoding="UTF-16"?>\n'
            '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
            "<RegistrationInfo><Source>LoteriaPredictor/Fase6/tarea/2</Source></RegistrationInfo>"
            "<Triggers><CalendarTrigger><StartBoundary>2026-01-05T22:30:00-05:00</StartBoundary><Enabled>true</Enabled>"
            "<ScheduleByWeek><DaysOfWeek><Monday /></DaysOfWeek><WeeksInterval>1</WeeksInterval></ScheduleByWeek>"
            "</CalendarTrigger></Triggers>"
            "<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" + swa + "<Enabled>false</Enabled></Settings>"
            "</Task>")


def _ensayar_swa(raiz_limpieza, valores):
    xml = _exportacion_swa(valores)
    previo = ("$global:ExportacionSwa=" + _ps_literal(xml) + "\n"
              "function Export-ScheduledTask { [CmdletBinding()]param([string]$TaskName,[string]$TaskPath) "
              "return $global:ExportacionSwa }\n")
    return _ensayar(raiz_limpieza, "swa", control=CONTROL_SWA, previo=previo)


@pytest.mark.parametrize("valores", [[], ["false"], ["0"]], ids=["omitido", "false", "cero"])
def test_ensayo_acepta_start_when_available_false_omitido_o_explicito(raiz_limpieza, valores):
    p, r, controles, raiz = _ensayar_swa(raiz_limpieza, valores)
    assert "ALTO_TRAS_COMPROBACION_SWA" in r["error"], r["error"]
    assert r["registrada"]["disparadores"] == ["CalendarTrigger"]
    assert r["registrada"]["inicios"] == ["2026-01-05T22:30:00-05:00"]
    assert controles == ["Plan", "Instalar", "Activar", "Estado", "Pausar", "Desinstalar", "Estado"]
    assert r["estado_limpieza"] == "completa" and not raiz.exists()


@pytest.mark.parametrize("valores", [["true"], ["1"], ["false", "false"], [""], ["si"]],
                         ids=["true", "uno", "duplicado", "vacio", "no_booleano"])
def test_ensayo_rechaza_start_when_available_distinto_de_false(raiz_limpieza, valores):
    p, r, controles, raiz = _ensayar_swa(raiz_limpieza, valores)
    assert p.returncode == 1 and "StartWhenAvailable" in r["error"], r["error"]
    assert "registrada" not in r and "Activar" not in controles
    assert controles == ["Plan", "Instalar", "Estado", "Pausar", "Desinstalar", "Estado"]
    assert r["estado_limpieza"] == "completa" and not raiz.exists()


def test_ensayo_no_lee_start_when_available_como_propiedad_xml():
    """Con StrictMode, `$x.Task.Settings.StartWhenAvailable` falla si el Programador omitió el elemento."""
    assert ".Settings.StartWhenAvailable" not in ENSAYO.read_text(encoding="utf-8")
