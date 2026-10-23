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
      [switch]$Plan,[switch]$Instalar,[switch]$Activar,[switch]$Pausar,
      [switch]$Desinstalar,[switch]$Estado)
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
    (backend / "scripts/windows/fase6_tarea.ps1").write_text(CONTROL_SIMULADO, encoding="utf-8-sig")
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
        "& " + _ps_literal(probe) + " -PythonExe " + _ps_literal(python)
        + " -Evidencia " + _ps_literal(evidencia) + " -Ejecutar\n"
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
